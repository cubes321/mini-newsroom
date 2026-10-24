"""Generation workers: planned Segment -> scripted -> voiced -> ready.

A worker thread pulls jobs from the buffer and runs `generate()` on each.
Every job is wrapped in try/except: a failure marks the slot `failed` and
the thread keeps going. A silently dead worker is the number one way a
system like this stalls, so a watchdog restarts any thread that dies.

Caching: segment JSON and per-line WAVs are stored under data/cache keyed
by (type, date, slot, town, broadcast day). Restarting during development
replays the same slots without calling the LLM or TTS.
"""
from __future__ import annotations

import hashlib
import json
import logging
import threading
import time
from datetime import date
from pathlib import Path

from . import tts, world as world_mod, writers
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

    key = (f"{seg.type.value}|{date.today().isoformat()}|{seg.slot_id}|{world.town}|"
           f"{world.broadcast_day}|{provider_for(seg.type.value)}")
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _cache_paths(h: str) -> tuple[Path, Path]:
    return CONFIG.paths.cache / f"{h}.json", CONFIG.paths.cache


def _load_cached(seg: Segment, h: str) -> Segment | None:
    meta, _ = _cache_paths(h)
    if not meta.exists():
        return None
    try:
        cached = Segment.model_validate_json(meta.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("cache %s unreadable (%s); regenerating", h, e)
        return None
    if not all(l.wav_path and Path(l.wav_path).exists() for l in cached.lines):
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


# --------------------------------------------------------------- pipeline


def voice_segment(seg: Segment, world: World, h: str) -> Segment:
    """Synthesize every line to its own WAV; fill duration and mouth envelope."""
    for i, line in enumerate(seg.lines):
        out = CONFIG.paths.cache / f"{h}_{i:02d}.wav"
        res = tts.synthesize(line.text, world.voice_for(line.speaker, line.guest_name), out)
        line.wav_path, line.duration_s, line.mouth_env = res.wav_path, res.duration_s, res.mouth_env
    seg.state = SegmentState.voiced
    return seg


def generate(seg: Segment, world: World, buffer: Buffer | None = None) -> Segment:
    """Full pipeline for one segment. Returns the ready Segment."""
    t0 = time.perf_counter()
    h = content_hash(seg, world)
    seg.content_hash = h

    if seg.type is SegmentType.bumper:
        from .assets import bumper_segment

        ready = bumper_segment(seg)
        if buffer:
            buffer.mark(ready, SegmentState.ready)
        return ready
    if seg.type is SegmentType.documentary:
        from .special import generate_special

        return generate_special(seg, world, buffer)

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

    seg.state = SegmentState.ready
    _save_cached(seg, h)
    if buffer:
        buffer.mark(seg, SegmentState.ready)
    log.info("slot %d %s ready: %.1fs of audio in %.1fs wall", seg.slot_id, seg.type.value,
             seg.duration_s, time.perf_counter() - t0)
    return seg


# ----------------------------------------------------------------- threads


class WorkerPool:
    def __init__(self, buffer: Buffer, world: World, n: int = 1) -> None:
        self.buffer, self.world, self.n = buffer, world, n
        self.stop = threading.Event()
        self._threads: list[threading.Thread] = []
        self.jobs_done = 0
        self.jobs_failed = 0

    def start(self) -> None:
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
        while not self.stop.is_set():
            seg = self.buffer.next_job(timeout=0.5)
            if seg is None:
                self._maybe_run_editor()
                continue
            try:
                generate(seg, self.world, self.buffer)
                self.jobs_done += 1
            except Exception as e:  # noqa: BLE001
                self.jobs_failed += 1
                log.exception("slot %d %s failed", seg.slot_id, seg.type.value)
                self.buffer.mark(seg, SegmentState.failed, error=str(e)[:200])

    def _maybe_run_editor(self) -> None:
        """When idle, occasionally let the editor look for a special to commission."""
        from . import special

        try:
            if self.buffer.special_pending():
                return
            force = special.take_force()
            if not force and not special.should_check(self.world):
                return
            decision = special.decide(self.world, force=force)
            world_mod.save(self.world)
            if decision.commission:
                self.buffer.submit_special(special.commission(self.world, decision))
        except Exception:  # noqa: BLE001
            log.exception("editor check failed")

    def shutdown(self) -> None:
        self.stop.set()


# --------------------------------------------------------------------- CLI


def _cli(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m newsroom.workers")
    p.add_argument("type", choices=[t.value for t in SegmentType if t not in (SegmentType.filler, SegmentType.documentary)])
    p.add_argument("--slot", type=int, default=0)
    p.add_argument("--target", type=float, default=45.0)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")

    w = world_mod.load()
    seg = Segment(slot_id=a.slot, type=SegmentType(a.type), target_s=a.target)
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
