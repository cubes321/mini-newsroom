"""The buffer's measures: what is really queued, and a history that doesn't grow all night."""
from newsroom import world as world_mod
from newsroom.buffer import TRANSITIONS_KEPT, Buffer
from newsroom.models import Line, Segment, SegmentState, SegmentType
from newsroom.workers import WorkerPool


def _ready(buf: Buffer, slot: int, secs: float) -> Segment:
    seg = Segment(slot_id=slot, type=SegmentType.bulletin, lines=[Line(speaker="anchor", text="x", duration_s=secs)])
    buf.submit(seg)
    buf.mark(seg, SegmentState.ready)
    return seg


def test_the_segment_on_air_is_not_counted_as_queued():
    buf = Buffer()
    on_air = _ready(buf, 1, 600.0)
    assert buf.ready_depth_s() == 600.0
    buf.mark(on_air, SegmentState.playing)
    assert buf.get_ready(1) is on_air                      # the player still finds it
    assert buf.ready_depth_s() == 0.0
    assert not WorkerPool(buf, world_mod.seed())._buffer_healthy()   # so no background work starts on it
    _ready(buf, 2, 90.0)
    assert buf.ready_depth_s() == 90.0


def test_the_transition_history_keeps_only_the_recent_ones():
    buf = Buffer()
    for slot in range(TRANSITIONS_KEPT):
        seg = _ready(buf, slot, 1.0)
        buf.mark(seg, SegmentState.done)
        buf.forget(slot)
    assert len(buf.transitions) == TRANSITIONS_KEPT
    assert buf.transitions[-1][1] == TRANSITIONS_KEPT - 1
