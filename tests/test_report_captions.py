"""A report's caption is the reporter's: once the piece is over and the presenter is back in the studio, it comes
down. On 2026-11-28 "Miles Okafor, live from the fish quay" stayed up over Howard Lanyon on Quayside."""
from __future__ import annotations

from newsroom import schedule, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentType as T, VisualCue
from newsroom.player import Player


def _view(seg, idx):
    pl = Player(Buffer(), world_mod.seed(), producer=None, audio=False)
    pl.current, pl.line_idx = seg, idx
    pl.seg_start = pl.line_start = schedule.now() - 0.5
    return pl.view()


def _report(show, lead):
    return Segment(slot_id=14, type=T.field_report, show=show, target_s=90, lines=[
        Line(speaker=lead, text="Miles, the quay has had a good Friday."),
        Line(speaker="reporter", text="Eleven of the twelve boats went out."),
        Line(speaker=lead, text="Thanks, Miles."),
    ], cues=[VisualCue(kind="lower_third", payload={"title": "Miles Okafor, live from the fish quay",
                                                     "subtitle": "Under the market canopy"}),
             VisualCue(kind="backdrop", payload={"backdrop": "harbour"})])


def test_the_reporters_caption_comes_down_when_the_studio_takes_it_back():
    for show, lead in (("quayside", "business"), ("news", "anchor")):
        seg = _report(show, lead)
        assert _view(seg, 0).lower_third[0] == "Miles Okafor, live from the fish quay"    # handing over to him
        assert _view(seg, 1).lower_third[0] == "Miles Okafor, live from the fish quay"    # him, live
        back = _view(seg, 2)
        assert back.mode == "studio" and back.lower_third is None, show


def test_meg_has_no_studio_to_come_back_to():
    seg = _report("outabout", "travel")
    seg.lines = [Line(speaker="travel", text="Here I am."), Line(speaker="travel", text="And here still.")]
    assert _view(seg, 1).lower_third[0] == "Miles Okafor, live from the fish quay"
