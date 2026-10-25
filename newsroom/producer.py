"""The producer plans the rundown ahead of the clock.

It keeps a cursor of nominal start times and, on every tick, submits enough
upcoming slots to the buffer to cover `horizon_s` of broadcast. When the
player reports a slot's real duration, the cursor is corrected so later
nominal times (and therefore job deadlines) stay honest.

Which show a slot belongs to comes from the schedule at the slot's nominal
start (`schedule.show_at(cursor_ts)`), not from the current time, because
planning runs up to the horizon ahead. Each show loops its own pattern; when
the show changes, the new one starts from the top of its pattern, so it
opens on its bumper. The switch lands on a segment boundary near the hour.
"""
from __future__ import annotations

import logging

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
        self._planned_until = self.cursor_ts
        self._show: str | None = None
        self._pos = 0                      # position within the current show's pattern

    def plan_one(self) -> Segment:
        show = schedule.show_at(self.cursor_ts)
        if show.id != self._show:
            if self._show is not None:
                log.info("schedule: %s -> %s from slot %d", self._show, show.id, self.next_slot)
            self._show, self._pos = show.id, 0
        seg_type = show.pattern[self._pos % len(show.pattern)]
        self._pos += 1
        seg = Segment(
            slot_id=self.next_slot,
            type=seg_type,
            target_s=show.target_s[seg_type],
            nominal_start_ts=self.cursor_ts,
            priority=0,
            show=show.id,
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
        self.cursor_ts = max(self.cursor_ts, now)
        while self.buffer.pending_depth_s() < self.horizon_s and added < 20:
            self.plan_one()
            added += 1
        if added:
            log.debug("producer planned %d slot(s); next=%d planned_until=+%.0fs",
                      added, self.next_slot, self._planned_until - now)
        return added

    def retime(self, slot_id: int, actual_start_ts: float, actual_duration_s: float) -> None:
        """Shift the cursor by the drift between planned and real timing of a played slot."""
        seg = self.buffer.segment(slot_id)
        if seg is None:
            return
        planned_end = seg.nominal_start_ts + seg.target_s
        real_end = actual_start_ts + actual_duration_s
        drift = real_end - planned_end
        if abs(drift) > 1.0:
            # Nominal times only order the job queue; never let the cursor fall
            # into the past, or deadlines stop meaning anything.
            self.cursor_ts = max(schedule.now(), self.cursor_ts + drift)
            self._planned_until = self.cursor_ts
            log.debug("retime after slot %d: drift %+.1fs", slot_id, drift)
