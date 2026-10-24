"""The producer plans the rundown ahead of the clock.

It keeps a cursor of nominal start times and, on every tick, submits enough
upcoming slots to the buffer to cover `horizon_s` of broadcast. When the
player reports a slot's real duration, the cursor is corrected so later
nominal times (and therefore job deadlines) stay honest.

Milestone 1 pattern loops forever: bumper, weather, bulletin, field report,
bumper. A later version reads a schedule table and inserts specials.
"""
from __future__ import annotations

import logging
import time

from .buffer import Buffer
from .models import Segment, SegmentType

log = logging.getLogger(__name__)

PATTERN: list[SegmentType] = [
    SegmentType.bumper,
    SegmentType.weather,
    SegmentType.bulletin,
    SegmentType.field_report,
]

TARGET_S: dict[SegmentType, float] = {
    SegmentType.bumper: 8.0,
    SegmentType.weather: 60.0,
    SegmentType.bulletin: 75.0,
    SegmentType.field_report: 90.0,
}


class Producer:
    def __init__(self, buffer: Buffer, horizon_s: float, start_ts: float | None = None) -> None:
        self.buffer = buffer
        self.horizon_s = horizon_s
        self.next_slot = 0
        self.cursor_ts = start_ts or time.time()
        self._planned_until = self.cursor_ts

    def plan_one(self) -> Segment:
        seg_type = PATTERN[self.next_slot % len(PATTERN)]
        seg = Segment(
            slot_id=self.next_slot,
            type=seg_type,
            target_s=TARGET_S[seg_type],
            nominal_start_ts=self.cursor_ts,
            priority=0,
        )
        self.buffer.submit(seg)
        self.next_slot += 1
        self.cursor_ts += seg.target_s
        self._planned_until = self.cursor_ts
        return seg

    def tick(self, now: float | None = None) -> int:
        """Submit slots until the plan covers now + horizon. Returns how many were added."""
        now = now or time.time()
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
            self.cursor_ts = max(time.time(), self.cursor_ts + drift)
            self._planned_until = self.cursor_ts
            log.debug("retime after slot %d: drift %+.1fs", slot_id, drift)
