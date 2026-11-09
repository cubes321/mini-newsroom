"""The kill switch (control.py): the file says testcard, the player drops what's on and holds the card.

No audio, no model: segments are hand-made and line ends are simulated from their durations.
"""
import pytest

from newsroom import adverts, control, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentState, SegmentType
from newsroom.player import Player
from newsroom.producer import Producer


@pytest.fixture
def switch(tmp_path, monkeypatch):
    f = tmp_path / "control.txt"
    monkeypatch.setattr(control, "path", lambda: f)
    monkeypatch.setitem(control._last, "at", -1e9)
    monkeypatch.setitem(control._last, "held", False)     # and put back after: a test may end held
    monkeypatch.setattr(control, "LOOK_EVERY_S", 0.0)     # every update looks
    return f


def test_no_file_is_on_air_and_the_word_holds_it(switch):
    assert not control.held()
    control.set_state("testcard")
    assert switch.read_text().strip() == "testcard" and control.held()
    assert control.toggle() == "air" and not control.held()
    with pytest.raises(ValueError):
        control.set_state("off")


def _ready(buf, slot, headline, secs=4.0):
    seg = Segment(slot_id=slot, type=SegmentType.bulletin, state=SegmentState.ready, headline=headline,
                  lines=[Line(speaker="anchor", text="Good evening.", duration_s=secs),
                         Line(speaker="anchor", text="More now.", duration_s=secs)])
    buf.submit(seg)
    buf.mark(seg, SegmentState.ready)
    return seg


def test_held_drops_what_is_on_and_comes_back_with_the_next_slot(switch, tmp_path):
    buf = Buffer()
    pl = Player(buf, world_mod.seed(), Producer(buf, 600), audio=False, ads=adverts.AdPool(tmp_path / "ads"))
    first, second = _ready(buf, 0, "Harbour news"), _ready(buf, 1, "Ferry news")
    now = 1_000_000.0
    pl.update(now)
    assert pl.current is first
    pl.ticker.append(("news", "Harbour news"))

    control.set_state("testcard")
    pl.update(now + 1)
    assert pl.current is None and pl.holding and not pl.ticker
    v = pl.view(now + 1)
    assert v.mode == "testcard" and v.held
    pl.update(now + 30)                                  # held: nothing new starts, not even the next slot
    assert pl.current is None

    control.set_state("air")
    pl.update(now + 31)
    assert pl.current is second and not pl.holding and not pl.view(now + 31).held


def test_held_under_breaking_news_drops_the_programme_it_interrupted_too(switch, tmp_path):
    """The programme set aside stayed "playing" in the buffer and was still the next ready slot: back
    on air, it started again from the top."""
    buf = Buffer()
    pl = Player(buf, world_mod.seed(), Producer(buf, 600), audio=False, ads=adverts.AdPool(tmp_path / "ads"))
    first, second = _ready(buf, 0, "Harbour news", secs=20.0), _ready(buf, 1, "Ferry news")
    now = 1_000_000.0
    pl.update(now)
    flash = Segment(slot_id=800_001, type=SegmentType.breaking, headline="Fire at the quay", work={"tip": "fire"},
                    lines=[Line(speaker="anchor", text="We interrupt.", duration_s=10.0)])
    buf.submit_breaking(flash)
    buf.mark(flash, SegmentState.ready)
    pl.update(now + 21)                                  # the first line ends: breaking news cuts in
    assert pl.current is flash and pl.stash[0] is first

    control.set_state("testcard")
    pl.update(now + 22)
    assert pl.current is None and pl.stash is None and pl.next_slot == 1
    assert buf.state_of(0) is SegmentState.done and buf.segment(flash.slot_id) is None

    control.set_state("air")
    pl.update(now + 30)
    assert pl.current is second


def test_a_documentary_dropped_by_the_switch_no_longer_blocks_the_next(switch, tmp_path):
    """It stayed "playing" for good, and buffer.special_pending() kept every later special from being made."""
    buf = Buffer()
    w = world_mod.seed()
    pl = Player(buf, w, Producer(buf, 600), audio=False, ads=adverts.AdPool(tmp_path / "ads"))
    doc = Segment(slot_id=900_001, type=SegmentType.documentary, headline="The harbour wall",
                  work={"format": "documentary"},
                  lines=[Line(speaker="anchor", text="Tonight, the wall.", duration_s=60.0)])
    buf.submit_special(doc)
    buf.mark(doc, SegmentState.ready)
    now = 1_000_000.0
    pl._start(buf.pop_special("documentary"), now)
    assert buf.special_pending()

    control.set_state("testcard")
    pl.update(now + 5)
    assert not buf.special_pending() and buf.segment(doc.slot_id) is None
    assert pl.next_slot == 0                             # a special has no slot in the rundown
    assert w.last_documentary_aired and not w.last_documentary_hash     # tonight's slot is used; no repeat, no history
