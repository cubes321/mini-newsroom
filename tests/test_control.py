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
