"""Nobody makes up council business: no committee decision, minutes or date, and The Panel reads out no briefing."""
from __future__ import annotations

from datetime import date, datetime

from newsroom import council, panel, schedule, world as world_mod, writers
from newsroom.models import SegmentType as T


def test_the_briefing_says_no_committee_has_decided_anything():
    """The Inquiry, 2026-11-21: the budget committee "agreed the two-panel booking. That was a decision", minutes
    and all; The Panel: "Gerald Thorne's committee decides on the twelfth"."""
    line = council.calendar_line(date(2026, 11, 21))
    assert "No committee has met, minuted, agreed or decided anything except what an open story says" in line
    assert "never invent one, or a decision, a vote or minutes" in line


def test_the_inquirys_paper_trail_asks_for_no_minutes():
    briefs = [schedule.as_item(e).brief for e in schedule.SHOWS["inquiry"].pattern]
    trail = next(b for b in briefs if b.startswith("the paper trail"))
    assert "what the minutes" not in trail and "no minutes, vote or decision that the story doesn't have" in trail


def test_the_panel_says_when_it_is_back_and_only_in_its_goodbye():
    """"Back on the third of December, live on The Chamber at eight": the council line, read out as the goodbye.
    The Panel is on every night but a council night (Thursday 3 December 2026)."""
    assert "back tomorrow night at half past eight" in panel.back_on(datetime(2026, 11, 21, 20, 40).timestamp())
    assert "back on Friday at half past eight" in panel.back_on(datetime(2026, 12, 2, 20, 40).timestamp())
    w = world_mod.seed()
    show = schedule.get("panel")
    at = datetime(2026, 11, 21, 20, 40).timestamp()
    middle = writers.build_prompt(T.interview, w, target_s=330.0, show=show, brief="a quick-fire round", at_ts=at)[1]
    close = writers.build_prompt(T.links, w, target_s=40.0, show=show, part="close", at_ts=at)[1]
    assert "THE PANEL is back" not in middle and "never read out the briefing's line about it" in middle
    assert "THE PANEL is back tomorrow night at half past eight" in close
