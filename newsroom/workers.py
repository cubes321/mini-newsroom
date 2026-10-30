"""Generation workers: planned Segment -> scripted -> voiced -> ready.

A worker thread pulls jobs from the buffer and runs `generate()` on each.
Every job is wrapped in try/except: a failure marks the slot `failed` and
the thread keeps going. A silently dead worker is the number one way a
system like this stalls, so a watchdog restarts any thread that dies.

There can be more than one worker (`--workers N`): the world has its own lock
(world.py), one worker at a time reads the tip-line and does the idle work,
TTS runs one line at a time, and a guest's second part waits until the first
part is written. What they gain is model calls in parallel.

Caching: segment JSON and per-line WAVs are stored under data/cache keyed
by (type, date, slot, town, broadcast day). Restarting during development
replays the same slots without calling the LLM or TTS.
"""
from __future__ import annotations

import hashlib
import json
import logging
import random
import threading
import time
from collections import deque
from datetime import date
from pathlib import Path

from . import schedule, tts, world as world_mod, writers
from .buffer import Buffer
from .config import CONFIG
from .models import Line, Segment, SegmentState, SegmentType
from .world import World

log = logging.getLogger(__name__)


# ------------------------------------------------------------------- cache


def content_hash(seg: Segment, world: World) -> str:
    # The provider is part of the key so template content generated with
    # NEWSROOM_LLM=off never replays once a real model is available.
    from .llm import provider_for

    # The show is in the key too: slot numbers restart at 0 on every run, so an
    # evening restart must not replay a breakfast script. News keeps the old key
    # so the existing cache stays valid.
    show = "" if seg.show == "news" else f"|{seg.show}"
    # A running order's part and brief too: a slot planned differently must not replay
    # another plan's script (a "cont" picking up an interview with someone else).
    plan = f"|{seg.part}|{seg.brief}" if seg.part or seg.brief else ""
    key = (f"{seg.type.value}|{date.fromtimestamp(schedule.now()).isoformat()}|{seg.slot_id}|{world.town}|"
           f"{world.broadcast_day}|{provider_for(seg.type.value)}{show}{plan}")
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _cache_paths(h: str) -> tuple[Path, Path]:
    return CONFIG.paths.cache / f"{h}.json", CONFIG.paths.cache


def _load_cached(seg: Segment, h: str) -> Segment | None:
    meta, _ = _cache_paths(h)
    if not meta.exists() or (CONFIG.paths.cache / f"{h}.aired").exists():   # a special that has aired
        return None
    try:
        cached = Segment.model_validate_json(meta.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("cache %s unreadable (%s); regenerating", h, e)
        return None
    if not all(l.wav_path and Path(l.wav_path).exists() for l in cached.lines):
        return None
    if cached.fallback:              # written while the model was unreachable: ask it again
        return None
    # Keep the planned slot's scheduling fields; take content from the cache.
    cached.slot_id, cached.priority = seg.slot_id, seg.priority
    cached.nominal_start_ts, cached.target_s = seg.nominal_start_ts, seg.target_s
    cached.state, cached.error = SegmentState.planned, None
    return cached


def _save_cached(seg: Segment, h: str) -> None:
    meta, _ = _cache_paths(h)
    tmp = meta.with_suffix(".json.tmp")
    tmp.write_text(seg.model_dump_json(indent=1), encoding="utf-8")
    tmp.replace(meta)


# ----------------------------------------------------------------- repeats

REPEATABLE = (SegmentType.weather, SegmentType.bulletin, SegmentType.field_report, SegmentType.sofa,
              SegmentType.interview, SegmentType.feature, SegmentType.vox_pop, SegmentType.consumer)
REPEAT_WINDOW_S = 48 * 3600         # repeat from today and yesterday
_recent_repeats: deque[str] = deque(maxlen=12)


def repeatable(c: Segment) -> bool:
    """A cached segment that suits the overnight repeats: a repeatable type, from a show whose
    scripts aren't tied to its own hours (no breakfast sofa during the test-card block). Not a
    canned fallback: on 2026-10-28 one written in a six-minute outage aired seven times."""
    return c.type in REPEATABLE and schedule.get(c.show).repeats_overnight and not c.fallback


def repeat_segment(seg: Segment) -> Segment:
    """Overnight: fill the slot with an earlier segment from the cache, aired again.

    No model call, no world update, nothing written back to the cache. The
    copy keeps its original show so it is drawn on its own set. With nothing
    to repeat, the slot becomes the test card.
    """
    from .assets import testcard_segment

    cutoff = time.time() - REPEAT_WINDOW_S
    candidates: list[tuple[str, Segment]] = []
    for meta in CONFIG.paths.cache.glob("*.json"):
        if meta.stat().st_mtime < cutoff:
            continue
        try:
            c = Segment.model_validate_json(meta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if repeatable(c) and c.lines and all(l.wav_path and Path(l.wav_path).exists() for l in c.lines):
            candidates.append((meta.stem, c))
    if not candidates:
        log.info("slot %d: nothing to repeat; test card", seg.slot_id)
        seg.type = SegmentType.testcard
        return testcard_segment(seg)
    # Prefer what hasn't aired lately; with a small cache, fall back to anything.
    fresh = [c for c in candidates if c[0] not in _recent_repeats]
    key, rep = random.choice(fresh or candidates)
    _recent_repeats.append(key)
    rep.slot_id, rep.priority, rep.nominal_start_ts = seg.slot_id, seg.priority, seg.nominal_start_ts
    rep.target_s, rep.repeat, rep.error = rep.duration_s, True, None
    rep.state = SegmentState.ready
    log.info("slot %d: repeating %s %r", seg.slot_id, rep.type.value, rep.headline)
    return rep


# --------------------------------------------------------------- pipeline


def voice_line(line: Line, i: int, world: World, h: str) -> None:
    """Synthesize one line to `<hash>_<i>.wav`; fill its duration and mouth envelope."""
    out = CONFIG.paths.cache / f"{h}_{i:02d}.wav"
    res = tts.synthesize(line.text, world.voice_for(line.speaker, line.guest_name), out,
                         speed=world.speed_for(line.speaker, line.guest_name),
                         lang=world.lang_for(line.speaker, line.guest_name))
    line.wav_path, line.duration_s, line.mouth_env = res.wav_path, res.duration_s, res.mouth_env


def voice_segment(seg: Segment, world: World, h: str) -> Segment:
    """Synthesize every line to its own WAV; fill duration and mouth envelope."""
    for i, line in enumerate(seg.lines):
        voice_line(line, i, world, h)
    seg.state = SegmentState.voiced
    return seg


def generate(seg: Segment, world: World, buffer: Buffer | None = None) -> Segment:
    """Full pipeline for one segment. Returns the ready Segment."""
    t0 = time.perf_counter()
    world.roll_day_if_needed()                # an always-on station crosses midnight
    world.fade_threads()                      # stories that stopped moving leave the board

    # Specials and breaking news key their own cache, before the slot-keyed hash below is
    # stamped: their slot numbers restart every run, so a slot key would hand a new special
    # an old one's cache entry.
    if seg.type is SegmentType.breaking:
        from .breaking import make

        return make(seg, world, buffer)
    if seg.type is SegmentType.documentary:
        from .special import advance, generate_special

        # On the worker, one stage per turn so live slots interleave; the CLI runs them all.
        return advance(seg, world, buffer) if buffer is not None else generate_special(seg, world)

    h = content_hash(seg, world)
    seg.content_hash = h

    if seg.type is SegmentType.ad_break:
        # Filled from the advert pool as it airs (player.py): built now, up to the planning horizon
        # ahead, it could find the pool still empty at startup, and the gap adverts would lose
        # track of what aired when.
        seg.state = SegmentState.ready
        if buffer:
            buffer.mark(seg, SegmentState.ready)
        return seg

    if seg.type in (SegmentType.bumper, SegmentType.testcard, SegmentType.repeat):
        from .assets import bumper_segment, testcard_segment

        maker = {SegmentType.bumper: bumper_segment, SegmentType.testcard: testcard_segment,
                 SegmentType.repeat: repeat_segment}[seg.type]
        ready = maker(seg)
        if buffer:
            buffer.mark(ready, SegmentState.ready)
        return ready

    cached = _load_cached(seg, h)
    if cached is not None:
        log.info("slot %d %s: cache hit %s", seg.slot_id, seg.type.value, h)
        cached.state = SegmentState.ready
        if buffer:
            buffer.mark(cached, SegmentState.ready)
        return cached

    writers.script_segment(seg, world)
    if buffer:
        buffer.mark(seg, SegmentState.scripted)
    world_mod.save(world)

    voice_segment(seg, world, h)
    if buffer:
        buffer.mark(seg, SegmentState.voiced)
    if seg.show == "late" and seg.type is SegmentType.interview:
        from .assets import band_line

        seg.lines.insert(0, band_line("button" if seg.part == "cont" else "walkon"))

    seg.state = SegmentState.ready
    _save_cached(seg, h)
    if buffer:
        buffer.mark(seg, SegmentState.ready)
    log.info("slot %d %s ready: %.1fs of audio in %.1fs wall", seg.slot_id, seg.type.value,
             seg.duration_s, time.perf_counter() - t0)
    return seg


# ----------------------------------------------------------------- threads

SPECIAL_RETRIES = 1                 # a failed special stage is tried again this many times before it is dropped


class WorkerPool:
    def __init__(self, buffer: Buffer, world: World, n: int = 1) -> None:
        self.buffer, self.world, self.n = buffer, world, n
        self.stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self.jobs_done = 0
        self.jobs_failed = 0
        self._tipline_lock = threading.Lock()      # one worker reads the tip-line at a time
        self._idle_lock = threading.Lock()         # one does the desk, the editor and the adverts

    def start(self) -> None:
        from .special import resume_partials, resume_ready

        resume_partials(self.buffer)
        resume_ready(self.buffer)
        for i in range(self.n):
            self._spawn(i)
        threading.Thread(target=self._watchdog, name="worker-watchdog", daemon=True).start()

    def _spawn(self, i: int) -> None:
        t = threading.Thread(target=self._loop, name=f"worker-{i}", daemon=True)
        t.start()
        if i < len(self._threads):
            self._threads[i] = t
        else:
            self._threads.append(t)

    def _watchdog(self) -> None:
        while not self.stop.wait(10):
            for i, t in enumerate(self._threads):
                if not t.is_alive():
                    log.error("worker-%d died; restarting", i)
                    self._spawn(i)

    def _loop(self) -> None:
        # No explicit warmup: the first slot is an asset-backed bumper that needs
        # no TTS, so it goes out immediately and the first real synth pays the
        # model-load cost while the bumper is on air.
        from . import breaking, tipline

        while not self.stop.is_set():
            if self._tipline_lock.acquire(blocking=False):
                try:                          # the tip-line, read on a worker: world writes stay off the main thread
                    lines, age = tipline.poll()
                    if lines:
                        breaking.intake(lines, age, self.buffer)
                except Exception:  # noqa: BLE001
                    log.exception("tip-line intake failed")
                finally:
                    self._tipline_lock.release()
            seg = self.buffer.next_job(timeout=0.5)
            if seg is None:
                if self._idle_lock.acquire(blocking=False):
                    try:
                        self._idle_work()
                    finally:
                        self._idle_lock.release()
                continue
            if self._first_part_pending(seg):
                self.buffer.requeue(seg)      # another worker is writing the guest's first part
                self.stop.wait(0.2)
                continue
            try:
                generate(seg, self.world, self.buffer)
                self.jobs_done += 1
            except Exception as e:  # noqa: BLE001
                self.jobs_failed += 1
                log.exception("slot %d %s failed", seg.slot_id, seg.type.value)
                self._failed(seg, e)

    def _first_part_pending(self, seg: Segment) -> bool:
        """A guest's second part carries on from the first (writers.py), so it waits while the
        first part is still unwritten; so does the late couch, for the guest who stays on. A
        failed or forgotten first part doesn't hold it up."""
        first = seg.work.get("first_part")
        return (seg.part in ("cont", "couch") and first is not None
                and self.buffer.state_of(first) is SegmentState.planned)

    def _failed(self, seg: Segment, e: Exception) -> None:
        if seg.type is SegmentType.documentary and seg.work.get("retries", 0) < SPECIAL_RETRIES:
            # A commission is worth one more go (a model timeout, say): the failed stage runs
            # again, from where the last one left off, once the live queue is clear.
            seg.work["retries"] = seg.work.get("retries", 0) + 1
            log.warning("special %r: retrying the %s stage", seg.headline, seg.stage or "outline")
            self.buffer.requeue(seg)
            return
        self.buffer.mark(seg, SegmentState.failed, error=str(e)[:200])

    def _buffer_healthy(self) -> bool:
        need = CONFIG.special.min_buffer_frac * CONFIG.broadcast.horizon_s
        return self.buffer.ready_depth_s() >= need

    def _idle_work(self) -> None:
        """Background work. The hand-written adverts are voiced first, whatever the buffer
        (they are what covers a gap). Then, only when the live buffer is comfortably full:
        the story desk plans developments (and now and then breaks a story itself), every two hours
        the senior editor leaves the desk a memo on the whole board, the day's
        documentary is commissioned, finished pieces get a trail and the day's stories a
        community notice now and then, the model writes a new advert now and then, and the
        editor may commission a special."""
        from . import adverts, breaking, continuity, desk, documentary, senior, special

        try:
            if adverts.seed_one(self.world):
                world_mod.save(self.world)    # their owners joined the cast
                return
            if continuity.bake_one(self.world):
                return                        # an ident, the programme card or a notice: TTS only
            force = special.take_force()
            if not force and not self._buffer_healthy():
                return
            breaking_now = breaking.take_force()
            if breaking_now or desk.should_plan(self.world):
                mode = "now" if breaking_now else "may" if breaking.desk_may_break(self.world) else "no"
                p = desk.plan(self.world, breaking=mode)
                if p is not None and p.breaking:
                    breaking.from_desk(self.world, p.breaking.tip, self.buffer)
                world_mod.save(self.world)
                return                        # one background call per idle tick
            if senior.should_review(self.world):
                senior.review(self.world)     # a memo on the whole board for the desk's next rounds
                world_mod.save(self.world)
                return
            if documentary.take_force() or documentary.should_commission(self.world, self.buffer):
                d = documentary.decide(self.world)
                world_mod.save(self.world)
                if d is not None:
                    self.buffer.submit_special(documentary.commission(self.world, d))
                return
            if continuity.should_make(self.world, self.buffer):
                continuity.make(self.world, self.buffer)   # a trail for a finished piece, or a community notice
                return
            if adverts.should_make():
                adverts.make(self.world)
                world_mod.save(self.world)
                return
            if self.buffer.special_pending("special"):   # a documentary waits for 21:00 all day; not this
                return
            if not force and not special.should_check(self.world):
                return
            decision = special.decide(self.world, force=force)
            world_mod.save(self.world)
            if decision.commission:
                self.buffer.submit_special(special.commission(self.world, decision))
        except Exception:  # noqa: BLE001
            log.exception("idle editorial work failed")

    def shutdown(self) -> None:
        self.stop.set()


# --------------------------------------------------------------------- CLI


def _cli(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m newsroom.workers")
    p.add_argument("type", choices=[t.value for t in SegmentType
                                    if t not in (SegmentType.filler, SegmentType.documentary, SegmentType.breaking,
                                                 SegmentType.advert, SegmentType.continuity)])     # python -m newsroom.adverts --make
    p.add_argument("--show", default="news", help="schedule show id (news, breakfast, overnight)")
    p.add_argument("--slot", type=int, default=0)
    p.add_argument("--target", type=float, default=45.0)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")

    w = world_mod.load()
    seg = Segment(slot_id=a.slot, type=SegmentType(a.type), target_s=a.target, show=a.show)
    out = generate(seg, w)
    print(json.dumps({
        "slot": out.slot_id, "type": out.type.value, "state": out.state.value, "hash": out.content_hash,
        "headline": out.headline, "duration_s": round(out.duration_s, 2),
        "lines": [{"speaker": l.speaker, "dur": round(l.duration_s or 0, 2), "env": len(l.mouth_env),
                   "wav": Path(l.wav_path).name if l.wav_path else None} for l in out.lines],
        "cues": [c.kind for c in out.cues],
    }, indent=1))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
