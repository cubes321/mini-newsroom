"""Breaking news: a tip-line line starting "BREAKING:" interrupts whatever is on.

The worker reads the tip-line before each job and hands new lines to
`intake()`. A breaking line becomes a segment outside the rundown (its own
slot numbers, like specials) at the front of the job queue. `make()` scripts
it with Dana at the news desk, opens a thread marked as breaking (the light
shows then lead with it), voices it and puts the sting in front. The player
airs it at the next line boundary and then resumes the interrupted programme.

A second breaking line within the cooldown, or one already old when first
read (after a restart), is downgraded to a plain tip for the next bulletin.
"""
from __future__ import annotations

import hashlib
import logging
import time

from . import schedule, tipline
from .config import CONFIG
from .models import Segment, SegmentState, SegmentType
from .world import World

log = logging.getLogger(__name__)

BREAKING_SLOT_BASE = 2_000_000
PREFIX = "BREAKING:"
_counter = 0


def intake(lines: list[str], age_s: float, buffer) -> int:
    """Sort new tip-line lines: plain tips wait for a bulletin, breaking ones are commissioned.
    Returns how many breaking segments were commissioned."""
    n = 0
    for line in lines:
        if not line.upper().startswith(PREFIX):
            tipline.add_tip(line)
            continue
        tip = line[len(PREFIX):].strip()
        if not tip:
            continue
        since = time.time() - tipline.last_breaking_ts()
        if age_s > CONFIG.breaking.max_age_s or since < CONFIG.breaking.cooldown_s:
            log.info("breaking: %r becomes a plain tip (%s)", tip[:60],
                     "read late" if age_s > CONFIG.breaking.max_age_s else f"{since:.0f}s since the last one")
            tipline.add_tip(tip)
            continue
        tipline.set_last_breaking(time.time())
        buffer.submit_breaking(commission(tip))
        n += 1
    return n


def commission(tip: str) -> Segment:
    global _counter
    _counter += 1
    return Segment(
        slot_id=BREAKING_SLOT_BASE + _counter,
        type=SegmentType.breaking,
        show="news",                                     # Dana at the news desk, whatever is on
        target_s=CONFIG.breaking.target_s,
        nominal_start_ts=schedule.now(),
        work={"tip": tip, "interrupting": schedule.show_at(schedule.now()).title.title()},
    )


def _hash(seg: Segment, world: World) -> str:
    from .llm import provider_for

    # The tip is in the key: the counter restarts every run and would replay an old tip's script.
    key = f"breaking|{world.last_date}|{seg.work.get('tip')}|{world.town}|{provider_for('breaking')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def make(seg: Segment, world: World, buffer=None) -> Segment:
    """Script, voice and sting one breaking segment. Runs on the worker."""
    from . import assets, workers, world as world_mod, writers

    h = seg.content_hash = _hash(seg, world)
    cached = workers._load_cached(seg, h)
    if cached is not None:
        seg = cached
    else:
        writers.script_segment(seg, world)
        world.mark_breaking(seg.thread_id, schedule.now())
        world_mod.save(world)
        if buffer:
            buffer.mark(seg, SegmentState.scripted)
        workers.voice_segment(seg, world, h)
        seg.lines.insert(0, assets.sting_line())
        seg.state = SegmentState.ready
        workers._save_cached(seg, h)
    seg.state = SegmentState.ready
    if buffer:
        buffer.mark(seg, SegmentState.ready)
    log.info("breaking news ready: %r (%.0fs)", seg.headline, seg.duration_s)
    return seg
