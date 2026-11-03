"""The town's events calendar (calendar.py): the approved events on their days, worked out from the date
alone; each writer's ration of them; the fortnight for the desk; and SEVENTEXT's What's On page."""
from __future__ import annotations

from datetime import date, datetime

from newsroom import calendar, desk, schedule, teletext, writers, world as world_mod
from newsroom.models import SegmentType as T


def _on(name: str, day: date) -> calendar.On:
    o = calendar.next_on(name, day)
    assert o is not None, name
    return o


def test_the_rules_give_the_approved_dates():
    assert calendar.easter(2026) == date(2026, 4, 5) and calendar.easter(2027) == date(2027, 3, 28)
    start = date(2026, 11, 3)
    assert _on("Bonfire Night", start).first == date(2026, 11, 5)
    assert _on("Remembrance Sunday", start).first == date(2026, 11, 8)
    assert _on("the Christmas lights", start).first == date(2026, 11, 27)
    xmas = _on("the Christmas holidays", start)
    assert (xmas.first, xmas.last) == (date(2026, 12, 18), date(2027, 1, 3))     # Friday break-up, back on the 4th
    assert _on("the Pancake Race", start).first == date(2027, 2, 9)
    easter = _on("the Easter holidays", start)
    assert (easter.first, easter.last) == (date(2027, 3, 22), date(2027, 4, 2))
    regatta = _on("Regatta Week", start)
    assert (regatta.first, regatta.last) == (date(2027, 8, 9), date(2027, 8, 14))
    assert _on("the summer holidays", start).first == date(2027, 7, 23)
    assert _on("autumn term starts", start).first == date(2027, 9, 1)


def test_council_dates_come_from_the_council_calendar():
    start = date(2026, 11, 3)
    budget, mayor = _on("budget night", start).first, _on("mayor-making", start).first
    assert budget == date(2027, 2, 25) and mayor == date(2027, 5, 20)
    from newsroom import council
    assert council.meets_on(budget) and council.meets_on(mayor)
    # Before the first meeting there is no council to set a budget: no event, and no endless search.
    assert not [o for o in calendar.held(2026) if o.event.name in ("budget night", "mayor-making")]


def test_elections_every_four_years_from_2027():
    names = lambda y: {o.event.name for o in calendar.held(y)}
    assert "the local elections" in names(2027) and "the local elections" in names(2031)
    assert "the local elections" not in names(2026) and "the local elections" not in names(2028)
    assert _on("the local elections", date(2026, 11, 3)).first == date(2027, 5, 6)


def test_every_event_is_held_every_year_and_suits_real_shows():
    for y in range(2026, 2036):
        assert len(calendar.held(y)) >= len(calendar.EVENTS) - 3      # the elections and, in 2026, the council's two
    for e in calendar.EVENTS:
        assert e.shows and set(e.shows) <= set(schedule.SHOWS), e.name


def test_a_holiday_over_new_year_is_still_on():
    assert "the Christmas holidays" in {o.event.name for o in calendar.events_on(date(2027, 1, 2))}
    assert "the Christmas holidays" not in {o.event.name for o in calendar.events_on(date(2027, 1, 4))}
    assert _on("the Christmas holidays", date(2027, 1, 2)).first == date(2026, 12, 18)    # this one, not next year's


def test_each_show_gets_its_ration_nearest_first():
    day = date(2026, 11, 3)
    names = lambda show: [o.event.name for o in calendar.for_show(show, day)]
    assert names("news") == ["Bonfire Night", "Remembrance Sunday"]
    assert names("rockpool") == ["Bonfire Night"]                       # Remembrance isn't a children's item
    assert names("late") == []
    assert all(len(calendar.for_show(s, d)) <= calendar.RATION
               for s in schedule.SHOWS for d in (date(2027, 8, 9), date(2027, 2, 15), date(2026, 12, 18)))
    # A holiday long under way gives way to an event about to start.
    assert names("rockpool") and [o.event.name for o in calendar.for_show("rockpool", date(2027, 8, 7))] == [
        "Regatta Week", "the summer holidays"]
    assert "budget night" not in {o.event.name for d in range(20, 28)
                                  for o in calendar.for_show("rockpool", date(2027, 2, d))}


def test_the_ration_says_when_and_forbids_inventing():
    day = date(2026, 11, 3)
    text = calendar.for_prompt("news", day)
    assert "Bonfire Night, on Thursday 5 November" in text and "never invent" in text
    assert "Remembrance Sunday" in text
    assert "Do not make up" in calendar.for_prompt("late", day)
    assert _on("Bonfire Night", day).when(date(2026, 11, 4)) == "tomorrow"
    assert _on("Bonfire Night", day).when(date(2026, 11, 5)) == "today"
    regatta = _on("Regatta Week", day)
    assert regatta.when(date(2027, 8, 9)) == "from today until Saturday 14 August"
    assert regatta.when(date(2027, 8, 11)) == "until Saturday 14 August"


def test_the_writers_get_the_ration_but_not_breaking_news():
    w = world_mod.seed()
    at = datetime(2026, 11, 3, 16, 10).timestamp()
    _, user = writers.build_prompt(T.links, w, target_s=60.0, show=schedule.get("rockpool"), at_ts=at)
    assert "TOWN CALENDAR" in user and "Bonfire Night" in user and "Remembrance" not in user
    _, user = writers.build_prompt(T.breaking, w, target_s=60.0, show=schedule.get("news"), at_ts=at,
                                   work={"tip": "Smoke over the old cannery"})
    assert "TOWN CALENDAR" not in user


def test_coming_up_gathers_the_council_the_matches_and_the_auction():
    kinds = lambda day, days: {c.kind for c in calendar.coming_up(day, days)}
    assert kinds(date(2026, 11, 3), 14) >= {"event", "council", "football", "rugby", "darts"}
    sat = calendar.coming_up(date(2026, 11, 7), 3)                      # a weekend: when the auction is back
    assert [c.day for c in sat if c.kind == "quay"] == [date(2026, 11, 9)]
    assert not [c for c in calendar.coming_up(date(2026, 11, 3), 3) if c.kind == "quay"]
    days = [c.day for c in calendar.coming_up(date(2026, 11, 3))]
    assert days == sorted(days) and days[-1] <= date(2026, 11, 16)


def test_the_desk_sees_the_fortnight_and_may_set_a_next_for_it():
    w = world_mod.seed()
    w.last_date = "2026-11-03"
    brief = w.summary_for_editor()
    assert "Thursday 5 November: Bonfire Night" in brief and "Full council meets" in brief
    assert "Coming up" in desk._SYSTEM and "never" in desk._SYSTEM
    assert calendar.due("On Thursday, Bonfire Night, the new barriers are tried out", date(2026, 11, 3)) == date(2026, 11, 5)
    assert calendar.due("Budget night settles the second engine", date(2026, 11, 3)) == date(2027, 2, 25)
    assert calendar.due("The part arrives and does not fit", date(2026, 11, 3)) is None


def test_whats_on_fits_the_page():
    for day in (date(2026, 11, 3), date(2027, 8, 7), date(2026, 12, 19), date(2027, 2, 13)):
        p = teletext._whats_on(day)
        assert p["num"] == 180 and teletext.height(p["rows"]) <= len(teletext.BODY)
        assert all(len(r["t"]) < teletext.COLS for r in p["rows"])
    text = " ".join(r["t"] for r in teletext._whats_on(date(2026, 11, 3))["rows"])
    assert "Bonfire Night" in text and "Full council" in text and "Thursday 5 November" in text
