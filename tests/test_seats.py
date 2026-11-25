"""The presenters keep their own seats whoever speaks first (2026-11-24: Nigel in Maggie's seat in six of The Kettle's
On's items, Elis in Tegan's once on The Slipway)."""
from __future__ import annotations

import pytest

import entertainment
from newsroom import world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentType as T
from newsroom.player import Player


@pytest.fixture(autouse=True)
def channel_8():
    undo = entertainment.use()            # Channel 8's shows are in schedule.SHOWS only while it's on
    yield
    undo()


def _seg(show: str, seg_type: T, lines: list[tuple[str, str | None]]) -> Segment:
    return Segment(slot_id=7, type=seg_type, show=show, target_s=60,
                   lines=[Line(speaker=who, text="Right.", guest_name=name, duration_s=1.0, mouth_env=[0.5] * 20)
                          for who, name in lines])


@pytest.mark.parametrize("show, seg_type, a, b", [
    ("kettle", T.call, "kettle_a", "kettle_b"),
    ("slipway", T.links, "slip_a", "slip_b"),
    ("slipway", T.interview, "slip_a", "slip_b"),
])
def test_the_second_presenter_speaking_first_keeps_their_own_seat(show, seg_type, a, b):
    w = world_mod.seed()
    lines = [(b, None), (a, None)] + ([("guest", "Jo Haskett")] if seg_type is not T.links else [])
    pl = Player(Buffer(), w, producer=None, audio=False)
    people = pl._people(_seg(show, seg_type, lines))
    assert people[:2] == [(a, None), (b, None)]


def test_the_lead_speaking_first_is_seated_as_before():
    w = world_mod.seed()
    pl = Player(Buffer(), w, producer=None, audio=False)
    seg = _seg("kettle", T.interview, [("kettle_a", None), ("guest", "Dolores Finch"), ("kettle_b", None)])
    assert pl._people(seg) == [("kettle_a", None), ("kettle_b", None), ("guest", "Dolores Finch")]
