"""The hour and the day in the writers' prompts: what has happened yet, the small hours, and the weekend."""
from __future__ import annotations

from datetime import datetime

from newsroom import darts, schedule


def _ts(*a):
    return datetime(*a).timestamp()


def test_the_clock_says_what_has_not_happened_yet():
    line = schedule.clock_line(_ts(2026, 11, 23, 14, 0))           # a Monday afternoon
    assert "anything timed later today has not happened yet" in line
    assert "small hours" not in line and "Sunday" not in line and "Saturday" not in line


def test_the_small_hours_are_not_the_morning():
    """At 02:15 and 03:17 on Sunday 22 November the documentaries told that morning as done."""
    line = schedule.clock_line(_ts(2026, 11, 22, 2, 15))
    assert "small hours of Sunday: Sunday's morning hasn't come yet" in line
    assert '"last night" and "yesterday" are Saturday' in line
    assert "small hours" not in schedule.clock_line(_ts(2026, 11, 22, 6, 0))


def test_a_weekend_is_not_a_weekday():
    """Morning Tide, Sunday 22 November: a school run at 06:07, shops sold out "before nine"."""
    assert "no school run" in schedule.day_note(_ts(2026, 11, 22, 6, 7))
    assert "no school run" in schedule.day_note(_ts(2026, 11, 21, 9, 0))
    assert schedule.day_note(_ts(2026, 11, 23, 6, 7)) == ""
    assert "It is Sunday" in schedule.clock_line(_ts(2026, 11, 22, 6, 7))


def test_the_special_and_the_documentary_are_told_when_they_air(monkeypatch):
    """A special is written in the small hours and airs as soon as it's made; a documentary written at 18:42 airs in
    its 21:00 slot. Neither airs at nominal_start_ts, which is a far deadline six hours on."""
    from newsroom import special
    from newsroom.models import Segment, SegmentType as T

    monkeypatch.setattr(schedule, "now", lambda: _ts(2026, 11, 22, 2, 15))
    seg = Segment(slot_id=1, type=T.documentary, nominal_start_ts=_ts(2026, 11, 22, 8, 15))
    assert special.airs_at(seg).startswith("WHEN IT AIRS: It is 02:15 on the broadcast clock")
    assert "small hours of Sunday" in special.airs_at(seg)
    monkeypatch.setattr(schedule, "now", lambda: _ts(2026, 11, 21, 18, 42))
    doc = Segment(slot_id=2, type=T.documentary, nominal_start_ts=_ts(2026, 11, 22, 0, 42), work={"format": "documentary"})
    assert special.airs_at(doc).startswith("WHEN IT AIRS: It is 21:00 on the broadcast clock")


def test_the_last_darts_night_is_not_tonight():
    """Saturday 21 November: "the Thursday match night has just been settled", live from the Cannery Tap."""
    facts = darts.for_prompt(datetime(2026, 11, 21, 18, 40))
    assert "That was 2 days ago, not tonight: there is no darts tonight" in facts
    assert "told as Thursday's" in facts
    assert "match night tonight too" in darts.for_prompt(datetime(2026, 11, 24, 21, 0))
