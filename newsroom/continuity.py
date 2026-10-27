"""Continuity: what Channel 7 puts out between programmes when the next one isn't ready.

Three kinds, all voiced by the continuity announcer, none needing the model:
- ident: the logo builds to the station tune (the show's arrangement), then a line from the
  announcer ("This is Channel 7."). Rebuilt when the show's tune stem changes.
- programmes: "Later on Channel 7": the next shows and their times, valid until the next one starts.
- notice: a 70s information slide read out. The daily tides and the Saltby ferry from
  tides.py (rebuilt each day), and a few hand-written ones from the town.

They are segments of type `continuity` with `work["continuity"] = {"kind", "title", "lines", ...}`,
outside the rundown like adverts. The player mixes them with adverts in a gap (`GAP_PATTERN`).
Items live in [paths] continuity (data/continuity/) as <id>.json plus their WAVs.

    python -m newsroom.continuity          # list the pool
    python -m newsroom.continuity --bake   # bake everything due now
"""
from __future__ import annotations

import argparse
import logging
import random
import threading
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import soundfile as sf
from pydantic import BaseModel

from . import assets, schedule, tides, tts
from .config import CONFIG
from .models import Line, Segment, SegmentState, SegmentType

log = logging.getLogger(__name__)

VOICE = "bf_isabella"           # the continuity announcer: nobody else on the station uses her
SHOWS = ("news", "breakfast", "magazine", "late")

# In a gap: ident, advert, a card (programmes or a notice), advert, advert, ident... then the filler card.
GAP_PATTERN = ("ident", "advert", "card", "advert", "advert", "ident", "card")

IDENT_LINES = {
    "news": ["This is Channel 7.", "Channel 7, for Port Wexley and the Greymouth coast."],
    "breakfast": ["Good morning. This is Channel 7.", "Channel 7. Good morning, Port Wexley."],
    "magazine": ["Channel 7, this evening.", "This is Channel 7, for the Greymouth coast."],
    "late": ["Channel 7, late.", "You're still with Channel 7."],
}

NOTICES: dict[str, tuple[str, list[str]]] = {          # each line a whole sentence or two: a block on the slide
    "lost_property": ("HARBOUR OFFICE", [
        "Lost property handed in this week: a child's red wellington, keys on a lifeboat fob and a folding umbrella.",
        "Collect them from the Harbour Office on the quay, nine till four."]),
    "recycling": ("COUNCIL NOTICE", [
        "Port Wexley Town Council reminds residents that glass and tins go out on Tuesdays.",
        "Bins on the seafront are emptied twice a day until the end of the month."]),
    "library": ("PORT WEXLEY LIBRARY", [
        "The library on Market Street is open late on Thursdays, until eight.",
        "The local history room has the cannery ledgers and the old harbour photographs."]),
    "lifeboat": ("RNLI PORT WEXLEY", [
        "The lifeboat crew thank everyone who gave to Saturday's collection on the quay.",
        "The boathouse is open to visitors on Sunday afternoons."]),
    "reception": ("CHANNEL 7", [
        "Viewers in Saltby and the upper valley may see a weaker picture during high winds.",
        "Engineers are aware. Please don't adjust your sets."]),
}


class Item(BaseModel):
    id: str
    kind: str                        # ident | programmes | notice
    show: str = ""                   # an ident: whose tune
    valid_from: float = 0.0          # 0 = always
    valid_until: float = 0.0         # 0 = never expires
    source_mtime: float = 0.0        # an ident: its tune stem's time, so a new stem rebuilds it
    segment: Segment


class Pool:
    """Continuity items on disk; the player picks on the main thread, the worker bakes."""

    def __init__(self, folder: Path) -> None:
        self.dir = folder
        self._lock = threading.Lock()
        self._items: dict[str, Item] = {}
        self._aired: dict[str, float] = {}
        self._rng = random.Random()
        self.load()

    def load(self) -> None:
        items = {}
        for meta in sorted(self.dir.glob("*.json")) if self.dir.exists() else []:
            try:
                it = Item.model_validate_json(meta.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                log.warning("continuity %s unreadable (%s); skipping", meta.name, e)
                continue
            if all(l.wav_path and Path(l.wav_path).exists() for l in it.segment.lines):
                items[it.id] = it
        with self._lock:
            self._items = items

    def __len__(self) -> int:
        with self._lock:
            return len(self._items)

    def get(self, item_id: str) -> Item | None:
        with self._lock:
            return self._items.get(item_id)

    def items(self) -> list[Item]:
        with self._lock:
            return list(self._items.values())

    def add(self, it: Item) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        meta = self.dir / f"{it.id}.json"
        tmp = meta.with_suffix(".json.tmp")
        tmp.write_text(it.model_dump_json(indent=1), encoding="utf-8")
        tmp.replace(meta)
        with self._lock:
            self._items[it.id] = it

    def remove(self, item_id: str) -> None:
        with self._lock:
            self._items.pop(item_id, None)
        for f in self.dir.glob(f"{item_id}*"):
            f.unlink(missing_ok=True)

    def pick(self, kind: str, show: str, now: float | None = None) -> Segment | None:
        """The least recently aired item of `kind` that is valid now; an ident in this show's
        tune, a "card" is the programme card or a notice. A copy, ready to play."""
        now = now or schedule.now()
        kinds = ("programmes", "notice") if kind == "card" else (kind,)
        with self._lock:
            ok = [it for it in self._items.values() if it.kind in kinds
                  and (not it.valid_from or it.valid_from <= now) and (not it.valid_until or now < it.valid_until)
                  and (it.kind != "ident" or it.show == (show if show in SHOWS else "news"))]
            if not ok:
                return None
            it = min(ok, key=lambda i: (self._aired.get(i.id, 0.0), i.kind != "programmes", self._rng.random()))
            self._aired[it.id] = time.time()
            seg = it.segment.model_copy(deep=True)
        seg.slot_id, seg.state, seg.show = -1, SegmentState.ready, show
        return seg


_pool: Pool | None = None
_pool_lock = threading.Lock()


def pool() -> Pool:
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = Pool(CONFIG.paths.continuity)
        return _pool


# ------------------------------------------------------------------- baking


def _voice(text: str, out: Path) -> tuple[np.ndarray, Line]:
    res = tts.synthesize(text, VOICE, out, speed=0.95)
    audio, _ = sf.read(str(res.wav_path), dtype="float32")
    return audio, Line(speaker="voiceover", text=text, wav_path=res.wav_path, duration_s=res.duration_s,
                       mouth_env=res.mouth_env)


def _segment(kind: str, voiced: list[Line], show: str, **card) -> Segment:
    seg = Segment(slot_id=-1, type=SegmentType.continuity, state=SegmentState.ready, show=show, lines=voiced,
                  work={"continuity": {"kind": kind, **card}})
    seg.target_s = seg.duration_s
    return seg


def bake_ident(show: str, n: int) -> Item:
    from . import jingle

    p = pool()
    item_id = f"ident_{show}_{n}"
    stem = assets.MUSIC / f"ident_{show}.wav"
    if stem.exists():
        music = assets._load(stem)
    else:
        music = assets._load_array(jingle.render(voicing=show), jingle.SR)
    text = IDENT_LINES[show][n]
    voice, line = _voice(text, p.dir / f"{item_id}_vo.wav")
    mix = assets._ident_mix(music, voice, jingle.onsets(voicing=show)[-1] + assets.VOICE_AFTER_S)
    wav = p.dir / f"{item_id}.wav"
    assets._write(wav, mix)
    line = line.model_copy(update={"wav_path": wav, "duration_s": len(mix) / assets.SR, "mouth_env": []})
    return Item(id=item_id, kind="ident", show=show, source_mtime=stem.stat().st_mtime if stem.exists() else 0.0,
                segment=_segment("ident", [line], show))


def _read_card(item_id: str, kind: str, title: str, shown: list[str], spoken: list[str] | None = None,
               show: str = "news") -> Segment:
    """A slide with `shown` on it, the announcer reading `spoken` (the slide's own lines by default)."""
    folder = pool().dir
    voiced = [_voice(t, folder / f"{item_id}_{i:02d}.wav")[1] for i, t in enumerate(spoken or shown)]
    return _segment(kind, voiced, show, title=title, lines=shown)


def _at(day: date, hour: int) -> float:
    return datetime.combine(day, datetime.min.time()).replace(hour=hour).timestamp()


def upcoming(now: float, n: int = 3) -> list[tuple[float, str]]:
    """The next `n` show changes after `now`: (start, show id), over midnight if need be."""
    day = datetime.fromtimestamp(now).date()
    out, prev = [], schedule.show_at(now).id
    for d in (day, date.fromordinal(day.toordinal() + 1)):
        for hour, _ in schedule.SCHEDULE:
            ts = _at(d, hour)
            sid = schedule.show_at(ts).id
            if ts > now and sid != prev:
                out.append((ts, sid))
                prev = sid
    return out[:n]


def _spoken_time(ts: float) -> str:
    h = time.localtime(ts).tm_hour
    words = "midnight one two three four five six seven eight nine ten eleven twelve".split()
    return "midnight" if h == 0 else f"{words[h % 12 or 12]} o'clock"


def bake_programmes(now: float, world=None) -> Item:
    """'Later on Channel 7': the next shows with their times, and tonight's documentary if it is
    still to come. Valid until the first of them starts, so it never says something stale."""
    from . import documentary

    entries = [(ts, schedule.get(sid).title) for ts, sid in upcoming(now)]
    airs = documentary._today_at(CONFIG.documentary.airs_at, now)
    if world is not None and now < airs < entries[-1][0] and documentary.due(world, airs):
        entries.append((airs, CONFIG.documentary.title))
    entries.sort()
    item_id = f"programmes_{datetime.fromtimestamp(now):%Y%m%d}_{time.localtime(entries[0][0]).tm_hour:02d}"
    shown = [f"{time.strftime('%H:%M', time.localtime(ts))}  {title}" for ts, title in entries]
    said = [f"at {_spoken_time(ts)}, {title.title()}" for ts, title in entries]
    spoken = ["Later on Channel 7: " + ", ".join(said[:-1]) + (", and " if len(said) > 1 else "") + said[-1] + "."]
    seg = _read_card(item_id, "programmes", "LATER ON CHANNEL 7", shown, spoken, schedule.show_at(now).id)
    return Item(id=item_id, kind="programmes", valid_from=now, valid_until=entries[0][0], segment=seg)


def bake_tides(day: date) -> Item:
    item_id = f"tides_{day:%Y%m%d}"
    tt = tides.tides(day)
    f = tides.ferry(day)
    high = " and ".join(f"{t:%H:%M}" for t, k, _ in tt if k == "high")
    low = " and ".join(f"{t:%H:%M}" for t, k, _ in tt if k == "low")
    shown = [f"High water  {high}", f"Low water   {low}"]
    spoken = [f"Today's tides at Port Wexley. High water at {high.replace(':', ' ')}; low water at {low.replace(':', ' ')}."]
    if f["sailings"]:
        last = f["sailings"][-1]
        gaps = ", ".join(f"{a:%H:%M}-{b:%H:%M}" for a, b in f["gaps"])
        shown.append(f"Saltby ferry every 30 min, last {last:%H:%M}")
        if gaps:
            shown.append(f"No crossings {gaps}")
        spoken.append(f"The Saltby foot ferry runs every half hour; the last one leaves at {last:%H:%M}"
                      + (f", with no crossings around low water, {gaps.replace('-', ' to ')}." if gaps else "."))
    seg = _read_card(item_id, "notice", "TIDES AND FERRY", shown, spoken)
    return Item(id=item_id, kind="notice", valid_from=_at(day, 0), valid_until=_at(day, 0) + 86400, segment=seg)


def bake_notice(key: str) -> Item:
    title, lines = NOTICES[key]
    return Item(id=f"notice_{key}", kind="notice", segment=_read_card(f"notice_{key}", "notice", title, lines))


def bake_one(world=None, now: float | None = None) -> bool:
    """Bake the one most-needed item, if any (one per idle tick: each is a few TTS lines).
    Order: this show's idents, the programme card, today's tides, then the notices."""
    now = now or schedule.now()
    p = pool()
    show = schedule.show_at(now).id
    order = [show] + [s for s in SHOWS if s != show]
    for s in order:
        if s not in SHOWS:
            continue
        stem = assets.MUSIC / f"ident_{s}.wav"
        mtime = stem.stat().st_mtime if stem.exists() else 0.0
        for n in range(len(IDENT_LINES[s])):
            it = p.get(f"ident_{s}_{n}")
            if it is None or it.source_mtime != mtime:
                return _add(p, lambda: bake_ident(s, n))
    nxt = upcoming(now)
    if nxt and not any(it.kind == "programmes" and it.valid_until == nxt[0][0] for it in p.items()):
        _expire(p, now)
        return _add(p, lambda: bake_programmes(now, world))
    today = datetime.fromtimestamp(now).date()
    if p.get(f"tides_{today:%Y%m%d}") is None:
        _expire(p, now)
        return _add(p, lambda: bake_tides(today))
    for key in NOTICES:
        if p.get(f"notice_{key}") is None:
            return _add(p, lambda: bake_notice(key))
    return False


def _add(p: Pool, bake) -> bool:
    t0 = time.perf_counter()
    it = bake()
    p.add(it)
    log.info("continuity %s baked (%d in the pool, %.1fs)", it.id, len(p), time.perf_counter() - t0)
    return True


def _expire(p: Pool, now: float) -> None:
    for it in p.items():
        if it.valid_until and it.valid_until <= now:
            p.remove(it.id)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--bake", action="store_true", help="bake everything due now")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.bake:
        while bake_one():
            pass
    for it in sorted(pool().items(), key=lambda i: i.id):
        until = time.strftime("%H:%M", time.localtime(it.valid_until)) if it.valid_until else "-"
        print(f"{it.id:28} {it.kind:10} {it.segment.duration_s:5.1f}s  until {until}")


if __name__ == "__main__":
    main()
