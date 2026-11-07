"""The writers and the story desk know the time, not just the date and "it is the evening".

On 2026-11-05 the news still said "bonfire gates open at six" at eleven at night: the calendar's
six o'clock start read as still to come. The time goes after the cached briefing, so the prompt
cache still holds.

Template scripts only (NEWSROOM_LLM=off, set in conftest): the desk's model call is stubbed.
"""
from datetime import date, datetime

import pytest

from newsroom import calendar, desk, llm, schedule, writers, world as world_mod
from newsroom.models import SegmentType as T, StoryPlan, ThreadUpdate


@pytest.fixture
def evening(monkeypatch):
    monkeypatch.setattr(schedule, "_offset_s", 0.0)
    schedule.set_clock("21:49")
    yield
    schedule._offset_s = 0.0


def test_the_writers_are_told_the_time_and_that_earlier_plans_have_happened(evening):
    _, user = writers.build_prompt(T.bulletin, world_mod.seed(), target_s=40.0)
    assert "It is 21:49 on the broadcast clock" in user
    assert 'they say "coming up to ten to ten"' in user
    assert "earlier today has already happened" in user


def test_the_time_is_said_in_words_worked_out_in_code():
    """On 2026-11-07 Haiku, told 09:54, 09:57 and 09:59, said "ten to ten" for all three."""
    at = lambda hm: datetime(2026, 11, 7, *map(int, hm.split(":"))).timestamp()
    for hm, said in (("09:59", "coming up to ten o'clock"), ("09:58", "coming up to ten o'clock"),
                     ("09:57", "just after five to ten"), ("09:54", "coming up to five to ten"),
                     ("09:50", "ten to ten"), ("09:41", "just after twenty to ten"),
                     ("09:30", "half past nine"), ("09:15", "quarter past nine"), ("13:25", "twenty-five past one"),
                     ("11:58", "coming up to midday"), ("12:01", "just after midday"),
                     ("23:59", "coming up to midnight"), ("00:02", "just after midnight"),
                     ("22:45", "quarter to eleven"), ("11:40", "twenty to twelve")):
        assert schedule.spoken_time(at(hm)) == said, hm


def test_the_desk_is_told_the_time_after_the_cached_briefing(evening, monkeypatch):
    w = world_mod.seed()
    w.seed_thread("Bonfire gates open at six", "the town bonfire on the Salting", "", [])
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append(user)
        return StoryPlan(updates=[ThreadUpdate(thread_id=t.id, phase="developing", next_development="It moves on.")
                                  for t in desk.batch(w)])
    monkeypatch.setattr(desk.llm, "complete_json", complete_json)
    desk.plan(w, dry=True)
    cached, _, rest = seen[0].partition(llm.CACHE_BREAK)
    assert "21:49" not in cached                     # the cached part stays the same all day
    assert "It is 21:49 on the broadcast clock" in rest


def test_the_calendar_says_when_todays_event_has_begun():
    """Told only the time, Haiku still had the half past seven fireworks to come at 21:49; told by
    the calendar line itself that the bonfire began at six, it wrote them as gone up."""
    before = calendar.for_prompt("news", datetime(2026, 11, 5, 16, 0))
    after = calendar.for_prompt("news", datetime(2026, 11, 5, 21, 49))
    assert "Bonfire Night, today" in before and "It began at" not in before
    assert "It began at 18:00, so by now it is under way or over" in after
    assert "It began" not in calendar.for_prompt("news", datetime(2026, 11, 4, 21, 49))   # tomorrow, still to come
    assert "It began" not in calendar.for_prompt("news", date(2026, 11, 5))           # a date alone: no time
