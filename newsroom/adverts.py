"""Local adverts: an evergreen pool of voiced ads that covers the gaps.

When the next segment isn't ready (the model is slow, a script failed and is
being retried), the player airs an advert from this pool instead of a bare
filler card. Those adverts sit outside the rundown, like specials: no slot
number, nothing for the producer to plan around. The light shows also have
planned breaks in their running orders (`ad_break` items): as one comes on
air, the player fills it with BREAK_ADS adverts from the same pool, joined
into one segment.

The pool lives in data/ads (one JSON per ad, a WAV per line) and outlasts the
day-keyed segment cache. It is never empty for long: a hand-written set of
SEEDS is voiced on the worker's first idle ticks, whatever the buffer and
whether or not a model is available. In idle time, when the live buffer is
healthy, the model writes a new one every `[adverts] make_every_s`, up to
`pool_size` (the oldest model-written ones go first).

An owner who speaks in their own advert joins the town's cast, so their voice
and look are the same wherever they turn up next.

    python -m newsroom.adverts            # list the pool
    python -m newsroom.adverts --make     # write and voice one now (uses the model)
"""
from __future__ import annotations

import logging
import random
import threading
import time
import zlib
from datetime import date
from pathlib import Path

from pydantic import BaseModel

from . import llm, tts
from .config import CONFIG
from .locations import locations_for_prompt
from .models import AdLine, AdvertScript, Line, Segment, SegmentState, SegmentType, VisualCue
from .world import World

log = logging.getLogger(__name__)

# Voiceovers come from the guest voices (every Kokoro voice on disk is in use), a different
# one per advert, as local adverts often are. Never the owner's own voice.
VO_VOICES = ["bm_lewis", "af_nicole", "bm_daniel", "af_kore", "bf_emma", "am_puck"]
MAX_S = 32.0                         # a model-written advert voiced longer than this is dropped
BREAK_ADS = 2                        # adverts in a planned break (about a minute)
COLOURS = [(200, 60, 60), (40, 130, 150), (210, 150, 40), (90, 140, 70), (130, 70, 150), (220, 110, 50),
           (50, 90, 160), (170, 60, 110)]


def _ad(business, tagline, where, backdrop, lines, owner=None, role=None, gender=None) -> AdvertScript:
    return AdvertScript(business=business, tagline=tagline, where=where, backdrop=backdrop, owner_name=owner,
                        owner_role=role, owner_gender=gender,
                        lines=[AdLine(speaker=s, text=t) for s, t in lines])


# The hand-written set: always on hand, with or without a model.
SEEDS: dict[str, AdvertScript] = {
    "seed_bakery": _ad(
        "Ramachandran's Bakery", "Baked before the boats go out", "Harrow Street market, from six", "market_shed",
        [("voiceover", "Up before the gulls, every morning, at Harrow Street market."),
         ("owner", "Mackerel pasties, proper sourdough, and a treacle tart I name after whatever's in the news. "
                   "This week it's the Thirteen O'Clock Tart."),
         ("voiceover", "Ramachandran's Bakery. Baked before the boats go out.")],
        "Dev Ramachandran", "baker, Harrow Street market", "m"),
    "seed_ferry": _ad(
        "The Saltby Foot Ferry", "Across the Grey in eight minutes", "Harbour steps, half-hourly from seven",
        "estuary",
        [("voiceover", "Why drive the long way round the estuary?"),
         ("voiceover", "The Saltby foot ferry crosses the Grey every half hour from seven in the morning, tides "
                       "permitting, and the last ferry leaves at a quarter past eleven."),
         ("voiceover", "Dogs, bikes and shopping welcome. The Saltby Foot Ferry. Across the Grey in eight minutes.")]),
    "seed_ghosts": _ad(
        "Pell's Cannery Ghost Tours", "Bring a torch. Bring a friend.", "The old cannery, nightly at eight", "cannery",
        [("voiceover", "Port Wexley's old cannery has stood empty since nineteen eighty-one."),
         ("owner", "Empty? Not quite. Join me after dark and I'll introduce you to the night foreman "
                   "who never clocked off."),
         ("voiceover", "Pell's Cannery Ghost Tours, nightly at eight. Bring a torch. Bring a friend.")],
        "Gordon Pell", "ghost tour guide, the old cannery", "m"),
    "seed_market": _ad(
        "Harrow Street Market", "Fresh off the boat, the farm and the oven", "Harrow Street, Saturdays from eight",
        "market",
        [("voiceover", "Crab from the Greymouth Maid. Cheese from Saltby. Honey from the hives above Wexley Woods."),
         ("voiceover", "Every Saturday from eight, Harrow Street fills with stalls, and you won't find any of it "
                       "in a supermarket."),
         ("voiceover", "Harrow Street Market. Fresh off the boat, the farm and the oven.")]),
    "seed_football": _ad(
        "Tidewater Town FC", "Come on you Tides!", "Tidewater Stadium, Saturday at three", "stadium",
        [("voiceover", "This Saturday at Tidewater Stadium: the Tides take on Saltby Rovers in the Greymouth "
                       "Coast derby."),
         ("voiceover", "Kick-off three o'clock. Adults six pounds, under-sixteens free, and the pies are "
                       "Ramachandran's."),
         ("voiceover", "Tidewater Town Football Club. Come on you Tides!")]),
    "seed_hardware": _ad(
        "Fowle & Sons Hardware", "If it's broken, we've got the bit", "The high street, by the post office",
        "main_street",
        [("owner", "Dripping tap? Wobbly gate? Gutter full of gull? I've seen it, I've fixed it, and I've got the bit."),
         ("voiceover", "Fowle and Sons Hardware, on the high street since nineteen fifty-four. Nails by the "
                       "handful, advice for free."),
         ("owner", "If it's broken, we've got the bit.")],
        "Jasper Fowle", "owner, Fowle & Sons Hardware", "m"),
    "seed_taxis": _ad(
        "Okonkwo's Taxis", "Missed the last ferry? We haven't.", "Ring Port Wexley four-four-one",
        "residential_street",
        [("voiceover", "Missed the last ferry? Stranded on the wrong side of the estuary?"),
         ("owner", "Don't worry. I'll have you home before your tea's gone cold. Saltby, the station, the "
                   "lighthouse, anywhere."),
         ("voiceover", "Okonkwo's Taxis. Missed the last ferry? We haven't.")],
        "Kenji Okonkwo", "taxi driver, Okonkwo's Taxis", "m"),
    "seed_cafe": _ad(
        "The Lighthouse Café", "Tea with the best view on the coast", "Greymouth Point, daily from ten", "lighthouse",
        [("voiceover", "At the end of Greymouth Point, under the lighthouse, there's a café with a view all the "
                       "way to Saltby."),
         ("owner", "Scones warm from the oven, crab sandwiches, and a pot of tea big enough for two walkers "
                   "and a dog."),
         ("voiceover", "The Lighthouse Café. Tea with the best view on the coast.")],
        "Nuala Brennan", "owner, the Lighthouse Café", "f"),
}


class Advert(BaseModel):
    id: str
    script: AdvertScript
    seed: bool = False
    made: str = ""                       # the date it was written
    voice: str = ""                      # the voiceover's Kokoro voice
    segment: Segment


# ------------------------------------------------------------------- the pool


class AdPool:
    """The voiced adverts on disk. The player picks from it on the main thread; the worker
    adds to it on its own, so everything goes through one lock."""

    def __init__(self, folder: Path) -> None:
        self.dir = folder
        self._lock = threading.Lock()
        self._ads: dict[str, Advert] = {}
        self._aired: dict[str, float] = {}           # this run's airings: id -> when
        self._last_business = ""
        self._rng = random.Random()
        self.load()

    def load(self) -> None:
        ads = {}
        for meta in sorted(self.dir.glob("*.json")) if self.dir.exists() else []:
            try:
                ad = Advert.model_validate_json(meta.read_text(encoding="utf-8"))
            except Exception as e:  # noqa: BLE001
                log.warning("advert %s unreadable (%s); skipping", meta.name, e)
                continue
            if all(l.wav_path and Path(l.wav_path).exists() for l in ad.segment.lines):
                ads[ad.id] = ad
        with self._lock:
            self._ads = ads
        if ads:
            log.info("advert pool: %d ready in %s", len(ads), self.dir)

    def __len__(self) -> int:
        with self._lock:
            return len(self._ads)

    def __contains__(self, ad_id: str) -> bool:
        with self._lock:
            return ad_id in self._ads

    def businesses(self) -> list[str]:
        with self._lock:
            return [a.script.business for a in self._ads.values()]

    def newest_made_ts(self) -> float:
        """When the model last wrote one (file time of the newest non-seed advert), 0 if never."""
        with self._lock:
            ids = [a.id for a in self._ads.values() if not a.seed]
        return max(((self.dir / f"{i}.json").stat().st_mtime for i in ids if (self.dir / f"{i}.json").exists()),
                   default=0.0)

    def add(self, ad: Advert) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        meta = self.dir / f"{ad.id}.json"
        tmp = meta.with_suffix(".json.tmp")
        tmp.write_text(ad.model_dump_json(indent=1), encoding="utf-8")
        tmp.replace(meta)
        with self._lock:
            self._ads[ad.id] = ad
            spare = sorted((a for a in self._ads.values() if not a.seed), key=lambda a: (a.made, a.id))
            drop = spare[:max(0, len(self._ads) - CONFIG.adverts.pool_size)]
            for old in drop:
                del self._ads[old.id]
        for old in drop:                      # our own files: the JSON and its line WAVs
            for f in self.dir.glob(f"{old.id}*"):
                f.unlink(missing_ok=True)
            log.info("advert pool full: dropped %s (%s)", old.id, old.script.business)

    def pick(self, now: float | None = None) -> Segment | None:
        """The advert aired least recently (never-aired first, in a random order), never the
        same business twice running. A copy, ready to play."""
        now = now or time.time()
        with self._lock:
            ads = [a for a in self._ads.values() if a.script.business != self._last_business] or list(self._ads.values())
            if not ads:
                return None
            ad = min(ads, key=lambda a: (self._aired.get(a.id, 0.0), self._rng.random()))
            self._aired[ad.id] = now
            self._last_business = ad.script.business
            seg = ad.segment.model_copy(deep=True)
        seg.slot_id, seg.state = -1, SegmentState.ready
        return seg


def break_segment(seg: Segment, ads_pool: AdPool | None = None) -> Segment:
    """Fill a planned ad break: BREAK_ADS adverts from the pool, one after another, each with its
    own backdrop and end card from where it starts. An empty pool makes an empty break, which
    the player passes straight over."""
    p = ads_pool or pool()
    ads = [ad for ad in (p.pick() for _ in range(BREAK_ADS)) if ad is not None]
    lines, cues, at = [], [], 0.0
    for ad in ads:
        cues += [c.model_copy(update={"at_s": c.at_s + at}) for c in ad.cues]
        cues.append(VisualCue(at_s=at, kind="advert", payload=ad.work.get("advert", {})))
        lines += ad.lines
        at += ad.duration_s
    seg.lines, seg.cues, seg.work = lines, cues, {**seg.work, "ads": len(ads)}
    seg.state = SegmentState.ready
    log.info("slot %d ad break: %s", seg.slot_id,
             ", ".join(ad.work.get("advert", {}).get("business", "?") for ad in ads) or "no adverts yet")
    return seg


_pool: AdPool | None = None
_pool_lock = threading.Lock()


def pool() -> AdPool:
    """The station's pool, in [paths] ads (data/ads)."""
    global _pool
    with _pool_lock:
        if _pool is None:
            _pool = AdPool(CONFIG.paths.ads)
        return _pool


# ----------------------------------------------------------------- making ads


def build(ad_id: str, script: AdvertScript, world: World, *, seed: bool = False) -> Advert:
    """Script -> voiced Advert. The owner joins the cast first, so they are voiced as themselves."""
    owner = (script.owner_name or "").strip() or None
    if owner:
        world.ensure_person(owner, script.owner_role, gender=script.owner_gender)
    h = zlib.crc32(script.business.lower().encode("utf-8"))
    owner_voice = world.voice_for("guest", owner) if owner else ""
    vo = next(v for v in VO_VOICES[h % len(VO_VOICES):] + VO_VOICES if v != owner_voice)
    folder = pool().dir
    folder.mkdir(parents=True, exist_ok=True)
    lines = []
    for i, al in enumerate(script.lines):
        if al.speaker == "owner":
            line = Line(speaker="guest", text=al.text.strip(), guest_name=owner, guest_role=script.owner_role)
            voice, speed = owner_voice, world.speed_for("guest", owner)
        else:
            line = Line(speaker="voiceover", text=al.text.strip())
            voice, speed = vo, 0.97
        res = tts.synthesize(line.text, voice, folder / f"{ad_id}_{i:02d}.wav", speed=speed)
        line.wav_path, line.duration_s, line.mouth_env = res.wav_path, res.duration_s, res.mouth_env
        lines.append(line)
    card = {"business": script.business, "tagline": script.tagline, "where": script.where, "owner": owner,
            "colour": COLOURS[h % len(COLOURS)]}
    seg = Segment(slot_id=-1, type=SegmentType.advert, state=SegmentState.ready, lines=lines,
                  cues=[VisualCue(at_s=0, kind="backdrop", payload={"backdrop": script.backdrop})],
                  work={"advert": card})
    seg.target_s = seg.duration_s
    return Advert(id=ad_id, script=script, seed=seed, made=date.today().isoformat(), voice=vo, segment=seg)


def seed_one(world: World) -> bool:
    """Voice one hand-written advert the pool doesn't have yet. False when they are all there."""
    p = pool()
    for ad_id, script in SEEDS.items():
        if ad_id not in p:
            t0 = time.perf_counter()
            p.add(build(ad_id, script, world, seed=True))
            log.info("advert %s voiced in %.1fs (%d in the pool)", ad_id, time.perf_counter() - t0, len(p))
            return True
    return False


def should_make(now: float | None = None) -> bool:
    return (now or time.time()) - pool().newest_made_ts() >= CONFIG.adverts.make_every_s


_SYSTEM = """\
You write local TV adverts for channel seven in the FICTIONAL town in the briefing: its shops, cafés,
trades, clubs, events and services. Each one runs 15 to 30 seconds: 40 to 55 words in all, in two to
four short lines. A voiceover ("voiceover") and, if it suits, the owner speaking for themselves
("owner"). Warm and a little homemade, like real local adverts: what it is, one detail that makes it
this town's, a gentle joke if it fits, then the tagline. A business can belong to someone in the
briefing (a resident we have met) or to a new local who fits the town. Never a real brand, a real
person or a real place outside the town; everything is fiction. Return ONLY JSON.
"""


def write_script(world: World) -> AdvertScript:
    from .writers import _keys_hint

    user = (f"TOWN BRIEFING\n{world.summary_for_prompt()}\n\n"
            f"LOCATIONS (choose the backdrop id where the advert is set):\n{locations_for_prompt()}\n\n"
            f"ADVERTS ALREADY ON AIR (advertise something else): {', '.join(pool().businesses()) or 'none'}\n"
            + _keys_hint(AdvertScript))
    return llm.complete_json("advert", AdvertScript, _SYSTEM, user)


def make(world: World) -> Advert | None:
    """Have the model write a new advert, voice it and add it to the pool. None if the model was
    unavailable or advertised something already on air."""
    try:
        script = write_script(world)
    except llm.LLMError as e:
        log.warning("advert not written: %s", e)
        return None
    if script.business.strip().lower() in {b.lower() for b in pool().businesses()}:
        log.info("advert for %r is already on air; skipping", script.business)
        return None
    ad = build(f"ad_{zlib.crc32((script.business + date.today().isoformat()).encode()):08x}", script, world)
    if ad.segment.duration_s > MAX_S:            # a gap filler that outstays the gap
        for line in ad.segment.lines:
            Path(line.wav_path).unlink(missing_ok=True)
        log.info("advert for %r ran %.0fs; dropped", script.business, ad.segment.duration_s)
        return None
    pool().add(ad)
    log.info("new advert: %s, %r (%.0fs; %d in the pool)", script.business, script.tagline,
             ad.segment.duration_s, len(pool()))
    return ad


def _cli(argv: list[str]) -> int:
    import argparse

    from . import world as world_mod

    ap = argparse.ArgumentParser(prog="python -m newsroom.adverts")
    ap.add_argument("--make", action="store_true", help="write and voice one advert now (calls the model)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")
    if a.make:
        w = world_mod.load()
        while seed_one(w):
            pass
        if make(w):
            world_mod.save(w)
    with pool()._lock:
        ads = sorted(pool()._ads.values(), key=lambda x: (not x.seed, x.made, x.id))
    for ad in ads:
        print(f"{ad.id:<16} {ad.segment.duration_s:5.1f}s  {ad.script.business}: {ad.script.tagline}"
              f"{'  (seed)' if ad.seed else ''}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
