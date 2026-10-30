"""Quayside at 13:00: Howard Lanyon on the town's money, with the fish auction worked out in quay.py so
every show quotes the same figures."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from newsroom import quay, schedule, world as world_mod, writers
from newsroom.models import SegmentType as T

FRIDAY = datetime(2026, 10, 30, 13, 0)


def test_an_auction_is_the_same_every_time_and_only_on_weekdays():
    a, b = quay.auction(FRIDAY.date()), quay.auction(FRIDAY.date())
    assert a == b and a.lots and a.total > 0
    assert quay.auction(date(2026, 10, 31)) is None and quay.auction(date(2026, 11, 1)) is None
    assert quay.latest(datetime(2026, 11, 1, 13, 0)).day == FRIDAY.date()          # Sunday: Friday's
    assert quay.latest(datetime(2026, 10, 30, 7, 0)).day == date(2026, 10, 29)      # before the hammer


def test_a_rough_day_keeps_the_small_boats_in():
    rough = next(a for d in range(1, 200) if (a := quay.auction(date(2026, 1, 1) + timedelta(days=d))) and a.rough)
    assert not any(kind in quay.SMALL for _, _, kind in rough.boats)


def test_the_briefing_line_and_the_facts_agree():
    line, facts = quay.summary(FRIDAY), quay.for_prompt(FRIDAY)
    a = quay.latest(FRIDAY)
    top = a.lots[0]
    assert f"{top.species} earned most" in line and f"{top.kilos:,} kg" in line
    assert f"  - {top.species}: {top.kilos:,} kg" in facts and "never invent a price" in facts
    assert world_mod.QUAY_LABEL in world_mod.seed().summary_for_prompt() and "BACKGROUND" in world_mod.QUAY_LABEL


def test_quayside_is_at_one_with_howard_and_the_facts():
    lt = time.localtime()

    def at(h, m):
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
    assert schedule.show_at(at(13, 10)).id == "quayside" and schedule.show_end(at(13, 10)) == at(13, 30)
    assert schedule.show_at(at(13, 40)).id == "news"
    show = schedule.get("quayside")
    w = world_mod.seed()
    howard = w.character("business")
    assert howard.name == "Howard Lanyon" and howard.voice not in world_mod.GUEST_VOICES
    user = writers.build_prompt(T.field_report, w, target_s=100.0, show=show, at_ts=FRIDAY.timestamp())[1]
    assert "QUAY FACTS" in user and "Fish auction" not in user.split("QUAY FACTS")[0][-40:]
    assert show.cast_for(T.links) == ("business",) and "reporter" in show.cast_for(T.field_report)
