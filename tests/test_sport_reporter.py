"""Tamsin Jago does Full Time's outside work (the stadium, the darts pub, the Wreckers' supporters at the
Quarry Field), so Miles is no longer on three shows an evening."""
from __future__ import annotations

import time

import pytest
from pydantic import ValidationError

from newsroom import schedule, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentType as T, script_schema
from newsroom.player import Player

FULL_TIME = schedule.get("sport")


def test_full_time_sends_tamsin_not_miles():
    assert "reporter" not in FULL_TIME.cast and "sport_reporter" in FULL_TIME.cast
    briefs = [schedule.as_item(e).brief for e in FULL_TIME.pattern]
    assert not any("Miles" in b for b in briefs)
    outside = [b for b in briefs if "Tamsin" in b]
    assert any("Tidewater Stadium" in b for b in outside) and any("darts pub" in b for b in outside)
    assert any("Quarry Field" in b for b in outside)


def test_a_full_time_report_is_tamsins_and_the_news_is_still_miless():
    lines = [{"speaker": "sport", "text": "Over to Tamsin."}, {"speaker": "sport_reporter", "text": "Thanks, Fran."}]
    report = {"headline": "Anchor and Bell top the table", "lower_third": "Darts", "location": "the Anchor and Bell",
              "backdrop": "pub", "lines": lines}
    script_schema(T.field_report, FULL_TIME.cast_for(T.field_report)).model_validate(report)
    with pytest.raises(ValidationError):
        script_schema(T.field_report, FULL_TIME.cast_for(T.field_report)).model_validate(
            report | {"lines": [{"speaker": "reporter", "text": "Miles here."}]})
    assert "reporter" in schedule.get("news").cast_for(T.field_report)


def test_tamsin_is_in_the_cast_with_a_voice_no_guest_shares():
    w = world_mod.seed()
    tamsin = next(c for c in w.characters if c.id == "sport_reporter")
    assert tamsin.name == "Tamsin Jago" and tamsin.lang == "b"
    assert tamsin.voice not in world_mod.GUEST_VOICES
    assert len({c.voice for c in w.characters}) == len(w.characters)


def test_the_picture_puts_tamsin_on_location():
    w = world_mod.seed()
    pl = Player(Buffer(), w, producer=None, audio=False)
    seg = Segment(slot_id=1, type=T.field_report, show="sport", target_s=60, lines=[
        Line(speaker="sport", text="Over to Tamsin at the Anchor and Bell."),
        Line(speaker="sport_reporter", text="Thanks, Fran. It's loud in here."),
        Line(speaker="sport", text="Thanks, Tamsin.")])
    pl.current, pl.seg_start = seg, time.time()
    for i, (mode, speaker) in enumerate([("studio", "sport"), ("field", "sport_reporter"), ("studio", "sport")]):
        pl.line_idx = i
        v = pl.view()
        assert (v.mode, v.speaker, v.reporter) == (mode, speaker, "sport_reporter")
