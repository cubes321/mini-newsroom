"""Breaking news: a tip-line line starting "BREAKING:" interrupts whatever is on.

The worker reads the tip-line before each job and hands new lines to
`intake()`. A breaking line becomes a segment outside the rundown (its own
slot numbers, like specials) at the front of the job queue. `make()` scripts
it with Dana at the news desk, opens a thread marked as breaking (the light
shows then lead with it), voices it and puts the sting in front. The player
airs it at the next line boundary and then resumes the interrupted programme.

A second breaking line within the cooldown, or one already old when first
read (after a restart), is downgraded to a plain tip for the next bulletin.

The story desk can break a story too (`from_desk`): when `desk_may_break`
allows (the cooldown, once a day at most, never overnight) its plan may carry
something sudden, which airs the same way, from "our own sources". Either
way, Miles then reports from the scene in the next field report
(writers.scene_due).
"""
from __future__ import annotations

import hashlib
import logging
import os
import time

from . import schedule, tipline
from .config import CONFIG
from .models import Segment, SegmentState, SegmentType
from .world import World

log = logging.getLogger(__name__)

BREAKING_SLOT_BASE = 2_000_000
PREFIX = "BREAKING:"
FROM_VIEWER = "it came in from a viewer on the tip-line"
FROM_DESK = "it came in from the newsroom's own sources: the emergency services, the harbour office, a call to the desk"
_counter = 0
_force: bool | None = None


def _cooled_down() -> float | None:
    """Seconds since the last breaking story, or None while still inside the cooldown."""
    since = time.time() - tipline.last_breaking_ts()
    return None if since < CONFIG.breaking.cooldown_s else since


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
        if age_s > CONFIG.breaking.max_age_s or _cooled_down() is None:
            log.info("breaking: %r becomes a plain tip (%s)", tip[:60],
                     "read late" if age_s > CONFIG.breaking.max_age_s else "too soon after the last one")
            tipline.add_tip(tip)
            continue
        tipline.set_last_breaking(time.time())
        buffer.submit_breaking(commission(tip))
        n += 1
    return n


def take_force() -> bool:
    """One-shot per process: NEWSROOM_BREAKING_NOW (--breaking-now) asks the story desk for
    breaking news at its next idle moment, whatever the interval, the cap and the hour."""
    global _force
    if _force is None:
        _force = bool(os.environ.get("NEWSROOM_BREAKING_NOW"))
    if _force:
        _force = False
        return True
    return False


def desk_may_break(world: World) -> bool:
    """The desk may break a story itself: out of the cooldown, under the day's cap, and not
    overnight (the desk keeps planning at three in the morning; nobody is watching the card)."""
    return (schedule.show_at(schedule.now()).id != "overnight"
            and world.desk_breaking.count(world.last_date) < CONFIG.breaking.desk_per_day
            and _cooled_down() is not None)


def from_desk(world: World, tip: str, buffer) -> Segment:
    """Commission the story desk's breaking news, counting it against the cooldown and the day."""
    tipline.set_last_breaking(time.time())
    world.desk_breaking = [d for d in world.desk_breaking if d == world.last_date] + [world.last_date]
    seg = commission(tip, source=FROM_DESK)
    buffer.submit_breaking(seg)
    log.info("breaking: the story desk breaks %r", tip[:80])
    return seg


def commission(tip: str, source: str = FROM_VIEWER) -> Segment:
    global _counter
    _counter += 1
    return Segment(
        slot_id=BREAKING_SLOT_BASE + _counter,
        type=SegmentType.breaking,
        show="news",                                     # Dana at the news desk, whatever is on
        target_s=CONFIG.breaking.target_s,
        nominal_start_ts=schedule.now(),
        work={"tip": tip, "source": source, "interrupting": schedule.show_at(schedule.now()).title.title()},
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
