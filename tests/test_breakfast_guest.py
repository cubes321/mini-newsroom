"""Morning Tide books a guest for the armchair about every seventeen minutes: the sort a breakfast
show has (an author with a book out, a funny guest, an actor with a series to plug), each booking
a different sort, with both hosts on the sofa and the guest drawn in the orange armchair.

Template scripts only (NEWSROOM_LLM=off, set in conftest): no model, no TTS.
"""
import time

import pytest
from pydantic import ValidationError

from newsroom import scenes, schedule, writers, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import SegmentType as T, script_schema
from newsroom.player import View
from newsroom.producer import Producer

BREAKFAST = schedule.get("breakfast")


def _morning(n: int) -> list:
    lt = time.localtime()
    p = Producer(Buffer(), 600, start_ts=time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 6, 2, 0, 0, 0, -1)))
    return [p.plan_one() for _ in range(n)]


def test_the_morning_has_guests_and_each_is_a_different_sort():
    guests = [s for s in _morning(60) if s.type is T.interview]
    assert len(guests) >= 3 and {s.show for s in guests} == {"breakfast"}
    briefs = [s.brief for s in guests]
    assert len(set(briefs)) == len(briefs) and briefs[0] == BREAKFAST.briefs[T.interview][0]


def _interview(*speakers):
    schema = script_schema(T.interview, BREAKFAST.cast_for(T.interview))
    return schema.model_validate({"headline": "Author brings lighthouse novel home", "lower_third": "Morning Tide",
                                  "guest_name": "Tamsin Rook", "guest_role": "author", "guest_gender": "f",
                                  "lines": [{"speaker": s, "text": "Good morning."} for s in speakers]})


def test_both_hosts_and_the_guest_can_speak():
    assert [l.speaker for l in _interview("host_a", "guest", "host_b", "guest").lines] == \
        ["host_a", "guest", "host_b", "guest"]


def test_the_news_anchor_cannot():
    with pytest.raises(ValidationError):
        _interview("anchor", "guest")


def test_the_writer_gets_the_breakfast_guest_prompt_and_the_sort_of_guest():
    system, user = writers.build_prompt(T.interview, world_mod.seed(), target_s=150.0, show=BREAKFAST,
                                        brief=BREAKFAST.briefs[T.interview][0])
    assert "GUEST ON THE SOFA" in system and "their work are invented" in system
    assert "THIS ITEM: an author with a new book out" in user and "RECENT GUESTS" in user


def test_the_guest_chat_has_no_tide_table_but_the_sofa_still_does():
    from datetime import date

    from newsroom import tides
    tide = tides.for_prompt(date.today()).splitlines()[0]
    w = world_mod.seed()
    _, guest = writers.build_prompt(T.interview, w, target_s=150.0, show=BREAKFAST, brief="a chef")
    _, sofa = writers.build_prompt(T.sofa, w, target_s=75.0, show=BREAKFAST, brief="a chef")
    assert tide not in guest and tide in sofa


def test_the_writer_sees_this_mornings_guests_and_so_does_the_goodbye():
    w = world_mod.seed()
    w.record_aired("interview", "Actor brings The Salt Road to Tidewater Stadium", None, "...", show="breakfast")
    w.record_aired("sofa", "Harbour cat returns", None, "...", show="breakfast")
    _, user = writers.build_prompt(T.interview, w, target_s=150.0, show=BREAKFAST, brief="a chef")
    assert "IN THE ARMCHAIR ALREADY" in user and "The Salt Road" in user
    _, close = writers.build_prompt(T.sofa, w, target_s=75.0, show=BREAKFAST, part="close")
    assert "AND IN THE ARMCHAIR" in close.split("ON THE SOFA THIS MORNING")[1]


def _sofa(people):
    v = View(clock="07:15", ticker=[], buffer_depth_s=0, slot_id=1)
    v.show, v.people = "breakfast", people
    return scenes._sofa_marks(v)


def test_the_guest_sits_in_the_armchair():
    marks = _sofa([("host_a", None), ("host_b", None), ("guest", "Tamsin Rook")])
    assert marks["guest"] == (scenes.SOFA["guest"], "Tamsin Rook")
    assert marks["host_a"][0] == scenes.SOFA["host_a"] and marks["host_b"][0] == scenes.SOFA["host_b"]


def test_a_presenter_booked_as_a_guest_takes_the_armchair_as_themselves():
    assert _sofa([("host_a", None), ("weather", None)])["weather"] == (scenes.SOFA["guest"], None)


def test_a_sofa_chat_is_just_the_hosts():
    assert set(_sofa([])) == {"host_a", "host_b"}
