"""The buffer between generation and playout.

Two halves:
- Intake: a PriorityQueue of jobs ordered by (deadline, priority). Workers
  pull from it. A documentary job has priority 9 and a far deadline, so it
  only runs when nothing live is waiting.
- Ready side: a dict keyed by slot id. The player asks "is slot N ready?"
  rather than "give me the next thing", so one slow segment never hides a
  finished one behind it.

Everything here is thread-safe; nothing here blocks for long.
"""
from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass, field

from .models import Segment, SegmentState, SegmentType

log = logging.getLogger(__name__)


@dataclass(order=True)
class Job:
    deadline: float
    priority: int
    segment: Segment = field(compare=False)


class Buffer:
    def __init__(self) -> None:
        self._q: queue.PriorityQueue[Job] = queue.PriorityQueue()
        self._lock = threading.Lock()
        self._segments: dict[int, Segment] = {}      # every slot we know about
        self._ready: dict[int, Segment] = {}         # subset in state ready
        self._specials_ready: list[Segment] = []     # side pocket: specials waiting for a bumper boundary
        self.transitions: list[tuple[float, int, str]] = []   # (ts, slot, state) for logs/soak

    # ------------------------------------------------------------- intake

    def submit(self, seg: Segment) -> None:
        with self._lock:
            if seg.slot_id in self._segments:
                return
            seg.state = SegmentState.planned
            self._segments[seg.slot_id] = seg
            self.transitions.append((time.time(), seg.slot_id, seg.state))
        self._q.put(Job(seg.nominal_start_ts, seg.priority, seg))
        log.debug("submitted slot %d %s due %.0fs", seg.slot_id, seg.type.value, seg.nominal_start_ts - time.time())

    def submit_special(self, seg: Segment) -> None:
        """A commissioned special: lowest priority, far deadline, outside the rundown."""
        with self._lock:
            seg.state = SegmentState.planned
            self._segments[seg.slot_id] = seg
            self.transitions.append((time.time(), seg.slot_id, seg.state))
        self._q.put(Job(seg.nominal_start_ts, seg.priority, seg))
        log.info("special commissioned: %r", seg.headline)

    def requeue(self, seg: Segment) -> None:
        """Put a multi-stage job back for its next stage; live jobs get served in between."""
        self._q.put(Job(seg.nominal_start_ts, seg.priority, seg))

    def special_pending(self) -> bool:
        """True while a special is being made or waiting to air."""
        with self._lock:
            return any(s.type is SegmentType.documentary and s.state not in (SegmentState.done, SegmentState.failed)
                       for s in self._segments.values())

    def pop_special(self) -> Segment | None:
        with self._lock:
            return self._specials_ready.pop(0) if self._specials_ready else None

    def next_job(self, timeout: float = 0.5) -> Segment | None:
        try:
            return self._q.get(timeout=timeout).segment
        except queue.Empty:
            return None

    # -------------------------------------------------------------- state

    def mark(self, seg: Segment, state: SegmentState, error: str | None = None) -> None:
        with self._lock:
            seg.state = state
            seg.error = error
            self._segments[seg.slot_id] = seg
            if state is SegmentState.ready and seg.type is SegmentType.documentary:
                self._specials_ready.append(seg)
            elif state is SegmentState.ready:
                self._ready[seg.slot_id] = seg
            elif seg.slot_id in self._ready and state not in (SegmentState.playing,):
                self._ready.pop(seg.slot_id, None)
            self.transitions.append((time.time(), seg.slot_id, state))
        lvl = logging.WARNING if state is SegmentState.failed else logging.INFO
        log.log(lvl, "slot %d %s -> %s%s", seg.slot_id, seg.type.value, state.value, f" ({error})" if error else "")

    def get_ready(self, slot_id: int) -> Segment | None:
        with self._lock:
            return self._ready.get(slot_id)

    def state_of(self, slot_id: int) -> SegmentState | None:
        with self._lock:
            seg = self._segments.get(slot_id)
            return seg.state if seg else None

    def segment(self, slot_id: int) -> Segment | None:
        with self._lock:
            return self._segments.get(slot_id)

    def forget(self, slot_id: int) -> None:
        """Drop a finished slot so memory doesn't grow over a long run."""
        with self._lock:
            self._segments.pop(slot_id, None)
            self._ready.pop(slot_id, None)

    # ------------------------------------------------------------ metrics

    def ready_depth_s(self) -> float:
        """Seconds of finished audio waiting to play."""
        with self._lock:
            return sum(s.duration_s for s in self._ready.values())

    def pending_depth_s(self) -> float:
        """Seconds of content not yet played: real duration when ready, target otherwise.

        This is what the producer plans against, so a burst of early-finishing
        segments cannot make it over-plan.
        """
        unplayed = (SegmentState.planned, SegmentState.scripted, SegmentState.voiced, SegmentState.ready)
        with self._lock:
            return sum(
                s.duration_s if s.state is SegmentState.ready else s.target_s
                for s in self._segments.values()
                if s.state in unplayed and s.type is not SegmentType.documentary
            )

    def counts(self) -> dict[str, int]:
        with self._lock:
            out: dict[str, int] = {}
            for s in self._segments.values():
                out[s.state.value] = out.get(s.state.value, 0) + 1
            return out

    def last_ready_slot(self) -> int | None:
        with self._lock:
            return max(self._ready) if self._ready else None
