"""The annals: a page a day of what the town did, kept for good.

The world remembers a few days in detail: the archive holds the last thousand pieces (about three
days), and the cache's audio can be cleared after a week or two (prune.py). The Sunday review of the
week, and the year's on New Year's Eve (review.py), need longer than that, so the morning after each
day the worker writes its page to data/annals/<date>.json, in code, with no model call:

- the day's stories, the most covered first: each with its headlines that day, where it stood, who
  was in it and what was due next;
- the rest of the day: the weather, the sport, the fish auction, full council's votes, the council's
  promises made and settled, the documentary, the pub quiz, the stories opened and closed;
- keepsakes: for the top few stories, one line of the day's own audio (a guest's quote, or Miles in
  the field), copied to data/annals/clips so a review can play it long after the cache has gone.

A page is about 5 kB and a keepsake about a megabyte: some 40 kB and 20 MB a week. Nothing here is
ever deleted by the station, and clearing the cache never touches it.

    python -m newsroom.annals              # the pages kept, and yesterday's
    python -m newsroom.annals 2026-11-08   # one day's page, as it would be written now
"""
from __future__ import annotations

import json
import logging
import shutil
from datetime import date, datetime, timedelta
from pathlib import Path

from . import quay, schedule, talk
from .config import CONFIG
from .models import Segment

log = logging.getLogger(__name__)

STORIES = 8                    # a day's page holds this many stories
BEATS = 6                      # and this many of a story's headlines that day
CLIPS_PER_DAY = 3
LOOK_BACK = 3                  # days: as far back as the archive can still fill a page
_GUESTED = ("interview", "feature", "vox_pop", "consumer", "field_report", "call", "review")


def folder() -> Path:
    return CONFIG.paths.annals


def path(day: date) -> Path:
    return folder() / f"{day.isoformat()}.json"


def clips_dir() -> Path:
    return folder() / "clips"


def load(day: date) -> dict | None:
    try:
        return json.loads(path(day).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def span(first: date, last: date) -> list[dict]:
    """The pages kept from `first` to `last`, both included, the oldest first."""
    days = [first + timedelta(days=k) for k in range((last - first).days + 1)]
    return [p for d in days if (p := load(d))]


# ----------------------------------------------------------------- one day's page


def _root(world, thread_id: str | None):
    """The story a piece belongs to now: a thread merged into another is that other one."""
    t = world.thread(thread_id) if thread_id else None
    for _ in range(5):
        if t is None or not t.merged_into:
            break
        t = world.thread(t.merged_into)
    return t


def _by(day: date) -> datetime:
    """The moment a day's page is read at: the end of the day, or now if the day isn't over (today's page,
    read live by the Sunday review at six: a match still to kick off has no result)."""
    end = datetime(day.year, day.month, day.day, 23, 59)
    return min(end, datetime.fromtimestamp(schedule.now()))


def _sport(day: date) -> list[str]:
    from . import darts, rugby, sport

    end = _by(day)
    out = []
    for mod in (sport, rugby):
        out += [mod._score_line(r) for r in mod.played(end)
                if mod._ours(r.fixture) and r.fixture.kickoff.date() == day]
    out += [darts._line(r) for r in darts.played(end) if r.fixture.start.date() == day][:2]
    return out


def _keepsake(world, key: str, entries: list[dict], day: date, keep: bool) -> dict | None:
    """One replayable line from these pieces, its audio copied into the annals (`keep`), or None."""
    from . import documentary

    cache: dict[str, Segment] = {}
    for e in entries:
        meta = CONFIG.paths.cache / f"{e.get('hash')}.json"
        if e.get("hash") and meta.exists():
            try:
                cache[e["hash"]] = Segment.model_validate_json(meta.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                continue
    found = documentary.find_clips(world, list(reversed(entries)), cache)      # the day's latest piece first
    if not found:
        return None
    c = found[0]
    name = f"{day.isoformat()}_{key}.wav"
    if keep:
        try:
            clips_dir().mkdir(parents=True, exist_ok=True)
            shutil.copyfile(c["wav"], clips_dir() / name)
        except OSError as e:
            log.warning("annals: could not keep %s: %s", name, e)
            return None
    return {k: c[k] for k in ("date", "type", "headline", "speaker", "who", "guest_name", "guest_role", "text",
                              "duration_s", "mouth_env")} | {"wav": name if keep else c["wav"], "story": key}


def digest(world, day: date, *, keep: bool = False) -> dict:
    """The day's page from the world as it stands. `keep` copies the keepsakes' audio into the annals;
    without it they point at the cache (today's page, read live by the Sunday review)."""
    iso = day.isoformat()
    with world.lock:
        entries = [e for e in world.aired_archive() if e.get("date") == iso]
        threads = list(world.threads)
        chamber = next((c for c in world.chambers if c.get("date") == iso), None)
        promised = [p for p in world.promises if p.get("made") == iso]
        settled = [p for p in world.promises if p.get("settled") == iso]
        docs = [d["title"] for d in world.documentaries if d.get("date") == iso]
    pieces: dict[str, list[dict]] = {}
    loose: list[dict] = []
    for e in entries:
        t = _root(world, e.get("thread_id"))
        (pieces.setdefault(t.id, []) if t else loose).append(e)
    stories = []
    for t in threads:
        if t.merged_into:
            continue
        beats = list(dict.fromkeys(b["headline"] for b in t.beats if b.get("date") == iso and b.get("headline")))
        mine = pieces.get(t.id, [])
        if not beats and not mine:
            continue
        beats = beats or list(dict.fromkeys(e["headline"] for e in mine if e.get("headline")))
        stories.append({"thread_id": t.id, "title": t.title, "phase": t.phase, "status": t.status,
                        "opened": t.opened, "pieces": len(mine), "beats": beats[:BEATS],
                        "people": [p.name for pid in t.people[:4] if (p := world.person(pid))],
                        "next": t.next_development})
    stories.sort(key=lambda s: (-s["pieces"], -len(s["beats"]), s["thread_id"]))
    clips = []
    for s in stories[:STORIES]:
        if len(clips) >= CLIPS_PER_DAY:
            break
        if c := _keepsake(world, s["thread_id"], pieces.get(s["thread_id"], []), day, keep):
            clips.append(c)
    guested = [e for e in loose if e.get("type") in _GUESTED]
    for n, e in enumerate(reversed(guested)):                # a guest with no running story: the day's colour
        if len(clips) >= CLIPS_PER_DAY:
            break
        if c := _keepsake(world, f"x{n}", [e], day, keep):
            clips.append(c)
    weather = [e["headline"] for e in entries if e.get("type") == "weather" and e.get("headline")]
    auction = quay.latest(_by(day))
    auction = auction if auction and auction.day == day else None       # the day's own, once the hammer has gone
    page = {
        "date": iso, "weekday": f"{day:%A}", "pieces": len(entries),
        "stories": stories[:STORIES],
        "headlines": list(dict.fromkeys(e["headline"] for e in entries if e.get("headline")
                                        and e.get("type") in ("bulletin", "field_report", "breaking")))[:20],
        "weather": weather[-1] if weather else "",
        "sport": _sport(day),
        "auction": quay.summary(_by(day)) if auction else "",
        "council": [{"motion": m["motion"], "title": m.get("title", ""), "for": m["for"], "against": m["against"],
                     "carried": m["carried"]} for m in (chamber or {}).get("motions", []) if m.get("applied")],
        "promised": [p["text"] for p in promised],
        "settled": [{"text": p["text"], "state": p["state"], "note": p.get("note", "")} for p in settled
                    if p["state"] in ("kept", "broken")],
        "documentaries": docs,
        "quiz": talk.quiz(world, day + timedelta(days=1)) or "",
        "opened": [t.title for t in threads if t.opened == iso and not t.merged_into][:10],
        "closed": [t.title for t in threads if t.phase == "closed" and t.updated == iso and not t.merged_into][:10],
        "clips": clips,
    }
    return page


def write(world, day: date) -> dict:
    """Write the day's page, with its keepsakes."""
    page = digest(world, day, keep=True)
    folder().mkdir(parents=True, exist_ok=True)
    tmp = path(day).with_suffix(".tmp")
    tmp.write_text(json.dumps(page, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path(day))
    log.info("annals: %s written: %d stories from %d pieces, %d keepsakes", day.isoformat(), len(page["stories"]),
             page["pieces"], len(page["clips"]))
    return page


def pending(world) -> date | None:
    """A finished day with no page yet that the archive can still fill, the oldest first."""
    today = date.fromisoformat(world.last_date)
    with world.lock:
        seen = {e.get("date") for e in world.aired_archive()}
    for k in range(LOOK_BACK, 0, -1):
        day = today - timedelta(days=k)
        if day.isoformat() in seen and not path(day).exists():
            return day
    return None


def tick(world) -> bool:
    """In idle time: write one pending page. True if it did."""
    day = pending(world)
    if day is None:
        return False
    try:
        write(world, day)
    except Exception:  # noqa: BLE001
        log.exception("annals: could not write %s", day)
        try:
            folder().mkdir(parents=True, exist_ok=True)
            path(day).write_text(json.dumps({"date": day.isoformat(), "stories": [], "clips": [], "failed": True}),
                                 encoding="utf-8")     # a stub, so it isn't tried at every idle tick
        except OSError:
            pass
    return True


def main(argv: list[str] | None = None) -> int:
    import sys

    from . import world as world_mod

    args = sys.argv[1:] if argv is None else argv
    w = world_mod.load()
    kept = sorted(folder().glob("*.json")) if folder().exists() else []
    print(f"{len(kept)} pages in {folder()}" + (f", {kept[0].stem} to {kept[-1].stem}" if kept else ""))
    day = date.fromisoformat(args[0]) if args else date.fromisoformat(w.last_date) - timedelta(days=1)
    page = digest(w, day)
    print(f"{page['weekday']} {day.isoformat()}: {page['pieces']} pieces on air")
    for s in page["stories"]:
        print(f"  {s['pieces']:>2}x [{s['thread_id']}] {s['title']} ({s['phase']}): {'; '.join(s['beats'][:3])}")
    for key in ("weather", "auction", "quiz"):
        if page[key]:
            print(f"  {key}: {page[key]}")
    for line in page["sport"]:
        print(f"  sport: {line}")
    for m in page["council"]:
        print(f"  council: {m['motion']} ({m['for']}-{m['against']}, {'carried' if m['carried'] else 'lost'})")
    for c in page["clips"]:
        print(f"  keepsake: {c['who']}: \"{c['text'][:80]}\" ({c['duration_s']:.0f}s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
