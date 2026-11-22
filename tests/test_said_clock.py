"""Nobody reads the 24-hour clock aloud, and the sport facts say plainly who scored, when, and how long ago."""
from __future__ import annotations

from datetime import datetime

from newsroom import rugby, schedule, sport, writers


def test_a_24_hour_time_read_aloud_is_said_as_people_say_it():
    """On 2026-11-21: "kick-off fifteen hundred" eleven times, "twenty-two forty-eight", "fourteen thirty"."""
    fix = writers.clock_read_out
    assert fix("Polgrey Rangers on the twenty-eighth, kick-off fifteen hundred.") == \
        "Polgrey Rangers on the twenty-eighth, kick-off three o'clock."
    assert fix("Low water came at twenty-two forty-eight and") == "Low water came at twelve minutes to eleven and"
    assert fix("the last one leaves at twenty two forty five") == "the last one leaves at quarter to eleven"
    assert fix("kick-off at fifteen hundred hours") == "kick-off at three o'clock"
    assert fix("fourteen thirty hours") == "half past two"
    # not a year, a count or a time with nothing to say it is one
    for t in ("a near thing in nineteen forty-three.", "In nineteen fifty-two I came over", "twenty twenty-six was a year",
              "There were fifteen twenty people there", "He was nineteen forty when he left",
              "by nineteen thirty the cannery had shut", "before twenty twenty-seven, they say", "by nineteen hundred",
              "The dearest bass went at twenty-three thirty-eight a kilo",       # every reply on record, 2026-11-22
              "the petition is at thirteen hundred and forty-one names"):
        assert fix(t) == t


def test_any_minute_in_words():
    assert schedule.said_clock(15, 0) == "three o'clock"
    assert schedule.said_clock(22, 48) == "twelve minutes to eleven"
    assert schedule.said_clock(10, 1) == "one minute past ten"
    assert schedule.said_clock(23, 38) == "twenty-two minutes to twelve"


def test_the_sport_facts_say_who_scored_how_many_and_how_long_ago():
    """From "(Shore, Kemp, Price)" Full Time gave Shore and Price two goals each and "a clean sheet" in a 3-1, and
    the Wreckers' win of the 14th was "a fortnight ago" on the 21st."""
    now = datetime(2026, 11, 21, 18, 40)
    tides = sport.summary(now)
    assert "on Saturday 21 November (today)" in tides and "(goals: Shore, Kemp, Price, one each)" in tides
    assert "clean sheet" not in tides and "three o'clock (15:00)" in tides
    assert "on Saturday 14 November (a week ago)" in rugby.summary(now) and "half past two (14:30)" in rugby.summary(now)
    assert sport.ago(datetime(2026, 11, 20).date(), now) == "yesterday"
    assert sport.ago(datetime(2026, 11, 7).date(), now) == "a fortnight ago"
