"""The producer plans the rundown ahead of the clock.

It keeps a cursor: when the next slot it plans is expected to start. On every
tick the cursor is worked out afresh from what is really queued (what is left
of the segment on air, plus the unplayed slots: real lengths once voiced,
targets before), then enough slots are submitted to cover `horizon_s`.
Segments often run shorter or longer than their targets, so a cursor that
only ever added targets would drift away from the clock; one that "corrected"
by each slot's drift double-counted it, and ran an hour ahead in a real run.

Which show a slot belongs to comes from the schedule at the slot's nominal
start (`schedule.show_at(cursor_ts)`), not from the current time, because
planning runs up to the horizon ahead. Each show runs its own pattern; when
the show changes, the new one starts from the top of its pattern, so it
opens on its bumper. The switch lands on a segment boundary near the hour.

A show with a closing (the magazine, the talk show) plans it once when the
time left before the hour is about the closing's length, then signs off: the
next show starts straight after, a little early rather than after a goodbye.
"""
from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import replace

from . import schedule
from .buffer import Buffer
from .models import Segment

log = logging.getLogger(__name__)


class Producer:
    def __init__(self, buffer: Buffer, horizon_s: float, start_ts: float | None = None) -> None:
        self.buffer = buffer
        self.horizon_s = horizon_s
        self.next_slot = 0
        self.cursor_ts = start_ts or schedule.now()
        self.on_air_left: Callable[[float], float] | None = None   # the player: seconds left on air
        self._planned_until = self.cursor_ts
        self._show: str | None = None
        self._pos = 0                      # position within the current show's pattern
        self._ends = 0.0                   # when the current show's time in the schedule is up
        self._closing: list[schedule.Item] = []    # closing items still to plan
        self._closed = False               # the current show has planned its closing
        self._briefs_given: dict = {}      # per type: how many of the show's briefs were handed out

    def _show_now(self) -> schedule.Show:
        """The show to plan for. The producer stays with its show until that show's own end, and
        only then asks the schedule what is next, at the later of the cursor and that end:
        the cursor is an estimate that can move back across the hour (a segment ran short), and a
        show once left must stay left."""
        cur = schedule.SHOWS.get(self._show or "")
        if cur is None:
            return schedule.show_at(self.cursor_ts)
        if self._closing:
            return cur
        over = self.cursor_ts >= self._ends
        if over and cur.closing and not self._closed and self._pos >= 2:
            return cur                    # the hour turned during a long item: the goodbye runs a little over
        if over or self._closed:
            return schedule.show_at(max(self.cursor_ts, self._ends))
        return cur

    def _run_s(self, show: schedule.Show) -> float:
        """The next item's length, with the parts that continue it: close now if less than half would fit."""
        pos = self._pos
        run = show.target_s[show.item(pos).type]
        while show.item(pos + 1).part == "cont":
            pos += 1
            run += show.target_s[show.item(pos).type]
        return run

    def _next_item(self, show: schedule.Show) -> schedule.Item:
        if self._closing:
            return self._closing.pop(0)
        if show.closing and not self._closed and self._pos >= 2 and (self.cursor_ts >= self._ends or (
                show.item(self._pos).part != "cont"            # a guest's second part is never cut
                and self.cursor_ts + self._run_s(show) / 2 + show.closing_s >= self._ends)):
            log.info("schedule: %s closing from slot %d", show.id, self.next_slot)
            self._closing = [schedule.as_item(e) for e in show.closing]
            self._closed = True
            return self._closing.pop(0)
        item = show.item(self._pos)
        self._pos += 1
        angles = show.briefs.get(item.type)
        if angles and not item.brief:
            n = self._briefs_given.get(item.type, 0)
            self._briefs_given[item.type] = n + 1
            item = replace(item, brief=angles[n % len(angles)])
        return item

    def plan_one(self) -> Segment:
        show = self._show_now()
        if show.id != self._show:
            if self._show is not None:
                log.info("schedule: %s -> %s from slot %d", self._show, show.id, self.next_slot)
            self._ends = schedule.show_end(max(self.cursor_ts, self._ends))
            self._show, self._pos, self._closing, self._closed = show.id, 0, [], False
            self._briefs_given = {}
        item = self._next_item(show)
        seg = Segment(
            slot_id=self.next_slot,
            type=item.type,
            target_s=show.target_s[item.type],
            nominal_start_ts=self.cursor_ts,
            priority=0,
            show=show.id,
            part=item.part,
            brief=item.brief,
        )
        self.buffer.submit(seg)
        self.next_slot += 1
        self.cursor_ts += seg.target_s
        self._planned_until = self.cursor_ts
        return seg

    def tick(self, now: float | None = None) -> int:
        """Submit slots until the plan covers now + horizon. Returns how many were added."""
        now = now or schedule.now()
        added = 0
        # Plan against seconds of unplayed content, not nominal clock time:
        # segments often run shorter than their targets, and a clock-based
        # horizon would over-plan in a burst after a run of early finishes.
        on_air = self.on_air_left(now) if self.on_air_left else 0.0
        self.cursor_ts = now + on_air + self.buffer.pending_depth_s()
        while self.buffer.pending_depth_s() < self.horizon_s and added < 20:
            self.plan_one()
            added += 1
        if added:
            log.debug("producer planned %d slot(s); next=%d planned_until=+%.0fs",
                      added, self.next_slot, self._planned_until - now)
        return added
