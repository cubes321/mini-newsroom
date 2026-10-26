"""The news bulletin is read at the desk: the anchor, and Miles in the box, but never Gordon,
whose voice had come out of Dana's close-up (Haiku, 2026-10-26 22:06).
"""
import pytest
from pydantic import ValidationError

from newsroom import schedule
from newsroom.models import SegmentType as T, script_schema

BULLETIN = {"headline": "Ghost tour clears first weekend", "lower_third": "Cannery Lane"}


def _bulletin(*speakers):
    schema = script_schema(T.bulletin, schedule.SHOWS["news"].cast_for(T.bulletin))
    return schema.model_validate({**BULLETIN, "lines": [{"speaker": s, "text": "Good evening."} for s in speakers]})


def test_the_anchor_and_the_reporter_can_read_a_bulletin():
    assert [l.speaker for l in _bulletin("anchor", "reporter", "anchor").lines] == ["anchor", "reporter", "anchor"]


def test_the_weatherman_cannot():
    with pytest.raises(ValidationError):
        _bulletin("anchor", "weather")
