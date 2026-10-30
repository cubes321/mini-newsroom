"""A show can start on the quarter ("18:45"), not only on the hour: the 15-minute sports show
before Coastwide. Show changes, show ends, "Later on Channel 7" and the announcer's times follow.
"""
import time

import pytest

from newsroom import continuity, schedule


def _at(hh: int, mm: int) -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))


@pytest.fixture
def quarter(monkeypatch):
    """The normal day with The Last Ferry standing in for Full Time at 18:45."""
    rows = [(s, "late" if show == "sport" else show) for s, show in schedule.SCHEDULE]
    monkeypatch.setattr(schedule, "SCHEDULE", tuple(rows))


def test_a_quarter_start_changes_the_show_and_ends_the_one_before(quarter):
    assert schedule.show_at(_at(18, 44)).id == "news"
    assert schedule.show_at(_at(18, 45)).id == "late"
    assert schedule.show_at(_at(19, 0)).id == "magazine"
    assert schedule.show_end(_at(18, 10)) == _at(18, 45)
    assert schedule.show_end(_at(18, 50)) == _at(19, 0)
    assert schedule.next_start("late") == "19:00"


def test_later_on_channel_7_lists_it_and_says_a_quarter_to(quarter):
    ups = continuity.upcoming(_at(18, 0))
    assert ups[0] == (_at(18, 45), "late") and ups[1] == (_at(19, 0), "magazine")
    assert continuity._spoken_time(_at(18, 45)) == "a quarter to seven"
    assert continuity._spoken_time(_at(23, 45)) == "a quarter to midnight"
    assert continuity._spoken_time(_at(19, 0)) == "seven o'clock"


def test_whole_hours_behave_as_before():
    assert schedule.show_end(_at(19, 10)) == _at(20, 0)
    assert schedule.show_end(_at(23, 30)) == _at(0, 0) + 86400
