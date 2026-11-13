"""The Kettle's On, Channel 8's teatime magazine (entertainment/kettle.py): a cook, a sofa guest and an expert on
the phones, booked in the back office, with a stand-in when the model is down. The model is stubbed: no network."""
from __future__ import annotations

import random
import time

import pytest

import entertainment
from entertainment import kettle
from newsroom import llm, locations, player, scenes, schedule, sprites, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


@pytest.fixture
def channel():
    undo = entertainment.use()
    yield
    undo()


def _booking(dish="a crab and samphire tart", sofa="Ivy Penhallow"):
    return kettle.KettleBooking.model_validate({
        "dish": {"dish": dish, "cook": "Tegan Moyle", "cook_role": "cook at the Gull's Nest tea room",
                 "cook_gender": "f", "cook_age": "middle", "why": "the samphire is nearly over"},
        "sofa": {"name": sofa, "role": "retired lighthouse keeper's widow", "gender": "f", "age": "old",
                 "about": "she has knitted a jumper for every lifeboat crew member since 1980"},
        "question": "Is it too late to plant garlic?",
        "callers": ["a first-time grower", "someone whose bulbs always rot", "an old hand with a trick",
                    "someone with only a balcony"],
        "notices": ["a jumble sale at the chapel on Saturday at two", "the library's talk on shipwrecks, Thursday at seven",
                    "a lost spaniel called Biscuit near the slipway"]})


def _stub(monkeypatch, reply):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, schema, system, user))
        if isinstance(reply, Exception):
            raise reply
        return reply(schema) if callable(reply) else reply
    monkeypatch.setattr(llm, "complete_json", complete_json)
    return seen


def test_channel_eight_opens_at_seven_with_the_kettles_on_and_undo_takes_it_off():
    seven = _at(19, 10)
    before = schedule.show_at(seven).id
    sofa = locations.MARKS["studio_sofa"]
    undo = entertainment.use()
    try:
        assert schedule.show_at(seven).id == "kettle" and schedule.show_end(seven) == _at(20, 0)
        assert schedule.show_at(_at(20, 10)).id == "wits"
        assert schedule.next_start("closedown", _at(3, 0)) == "19:00"
        assert "The Kettle's On" in entertainment.CLOSEDOWN_TEXT and "Cartoon" not in entertainment.CLOSEDOWN_TEXT
        assert scenes.SHOW_SETS["kettle"] == kettle.STAND_IN_SET and player.SEATS["kettle"] == 1
        assert {"host", "panel_1", "panel_2", "host_a"} <= set(locations.MARKS["studio_sofa"])
        assert sprites.LOOKS["kettle_a"].hair_style == "curly"                    # chosen 2026-11-13: A
        assert "kettle" in writers.BOOKED_SHOWS and "kettle" in writers.UNFILED_SHOWS
    finally:
        undo()
    assert schedule.show_at(seven).id == before and "kettle" not in schedule.SHOWS
    assert locations.MARKS["studio_sofa"] is sofa and "panel_1" not in sofa          # the breakfast sofa as it was
    assert "kettle_a" in sprites.LOOKS and "kettle" not in writers.BOOKED_SHOWS        # a presenter on both channels


def test_the_presenters_are_a_double_act_the_town_knows():
    w = world_mod.seed()
    maggie, nigel = w.character("kettle_a"), w.character("kettle_b")
    assert maggie.name == "Maggie Truscott" and nigel.name == "Nigel Spargo"
    assert maggie.lang == nigel.lang == "b"
    assert len({c.voice for c in w.characters}) == len(w.characters)              # nobody else's voice


def test_tonight_is_booked_once_and_its_people_join_the_town(monkeypatch):
    w = world_mod.seed()
    seen = _stub(monkeypatch, _booking())
    k = kettle.commission(w)
    assert seen[0][0] == kettle.TASK and "THE EXPERT tonight" in seen[0][3] and not k["stand_in"]
    assert kettle.tonight(w) is k and kettle.booked(w) is k and len(seen) == 1
    for name in ("Tegan Moyle", "Ivy Penhallow", k["expert"]["name"]):
        assert w.person_by_name(name) is not None
    kettle.commission(w)
    assert len(w.kettles) == 1                                                     # rebooked, not added


def test_the_experts_take_the_phones_in_turn_one_a_night(monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, llm.LLMError("down"))
    names = []
    for day in ("2026-11-14", "2026-11-16", "2026-11-18", "2026-11-20", "2026-11-22"):
        w.last_date = day
        names.append(kettle.commission(w)["expert"]["name"])
    assert names[:4] == [e["name"] for e in kettle.EXPERTS] and names[4] == names[0]


def test_a_dish_or_sofa_guest_from_the_last_month_is_not_booked_again(monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    first = kettle.commission(w)
    w.last_date = _later(first["date"], 2)
    _stub(monkeypatch, _booking(sofa="Somebody Else"))                             # the same tart again
    assert kettle.commission(w)["stand_in"]


def _later(day, n):
    from datetime import date, timedelta
    return (date.fromisoformat(day) + timedelta(days=n)).isoformat()


def test_with_no_model_the_stand_in_still_has_a_cook_a_guest_and_the_phones(monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, llm.LLMError("down"))
    k = kettle.commission(w)
    assert k["stand_in"] and k["dish"]["dish"] and k["sofa"]["name"] and len(k["callers"]) >= 4
    assert len(k["notices"]) == 3


def test_the_briefs_carry_tonights_booking_and_the_callers_come_in_turn(monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    kettle.commission(w)
    one = kettle.brief_for(w, kettle._RECIPE_1)
    assert "Tegan Moyle" in one and "crab and samphire tart" in one and "{" not in one
    assert "knitted a jumper" in kettle.brief_for(w, kettle._SOFA)
    assert "jumble sale" in kettle.brief_for(w, kettle._NOTICES)
    calls = [kettle.brief_for(w, "{caller}") for _ in range(5)]
    assert "a first-time grower" in calls[0] and "an old hand" in calls[2] and "SOMEONE ELSE" in calls[4]
    assert "Maggie takes it" in calls[0] and "Nigel takes it" in calls[1]          # two calls began alike


def test_a_call_is_written_to_the_phone_in_and_the_caller_joins_the_town(channel, monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    k = kettle.commission(w)
    expert = k["expert"]["name"]

    def reply(schema):
        return schema.model_validate({
            "headline": "Garlic in November", "lower_third": "The Kettle's On: garlic",
            "caller_name": "Doreen Uglow", "caller_from": "Cannery Row", "caller_gender": "f", "caller_age": "old",
            "caller_accent": "british", "caller_memory": "asked about garlic on a windy plot",
            "lines": [{"speaker": "kettle_a", "text": "We've got Doreen on the line."},
                      {"speaker": "guest", "text": "Is it too late for my garlic?"},
                      {"speaker": "guest", "guest_name": expert, "text": "Not at all, get it in this week."},
                      {"speaker": "kettle_b", "text": "How deep, exactly?"},
                      {"speaker": "kettle_a", "text": "Thanks for ringing, Doreen."}]})
    seen = _stub(monkeypatch, reply)
    seg = Segment(slot_id=4, type=T.call, show="kettle", brief="{caller}", target_s=120)
    writers.script_segment(seg, w)
    task, schema, system, user = seen[0]
    assert "THE KETTLE'S ON" in system and "ONE CALL to the phone-in" in user and "TONIGHT:" in user
    assert "A RETURN VISIT" not in user
    assert w.person_by_name("Doreen Uglow") is not None and seg.thread_id is None
    assert seg.work.get("caller") == "Doreen Uglow" and seg.work.get("studio_guest") == expert   # on the set
    # The expert's answer is the expert's, not the caller's: on the first scratch run (2026-11-13) every guest line
    # of a call outside Have Your Say went to the caller, so Ray answered his own question about his kale.
    said = {l.text: l.guest_name for l in seg.lines if l.speaker == "guest"}
    assert said["Not at all, get it in this week."] == expert
    assert said["Is it too late for my garlic?"] == "Doreen Uglow"
    assert w.person_by_name("Doreen Uglow").memories[-1]["show"] == kettle.CALLED   # not Have Your Say's


def test_with_the_model_down_every_item_is_still_tonights(channel, monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    k = kettle.commission(w)
    _stub(monkeypatch, llm.LLMError("down"))
    show = schedule.get("kettle")
    items = [show.item(i) for i in range(len(show.pattern))] + [schedule.as_item(e) for e in show.closing]
    for n, it in enumerate(items):
        if it.type in (T.bumper, T.ad_break):
            continue
        seg = Segment(slot_id=n + 1, type=it.type, show="kettle", part=it.part, brief=it.brief, target_s=100)
        writers.script_segment(seg, w)
        assert seg.lines, it
        said = " ".join(l.text for l in seg.lines)
        if "RECIPE, part one" in (it.brief or ""):
            assert k["dish"]["dish"].lower() in said.lower()
    rng = random.Random(1)
    sofa = kettle.template(T.interview, w, rng, "", {}, kettle._SOFA)
    assert sofa.guest_name == k["sofa"]["name"]


def test_a_guest_remembers_being_on_the_kettles_on_with_a_small_s(channel, monkeypatch):
    """str.title() capitalises after an apostrophe: the scratch run's guests remembered "The Kettle'S On"."""
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    kettle.commission(w)

    def reply(schema):
        return schema.model_validate({
            "headline": "Ivy's jumpers for the lifeboat", "lower_third": "On the sofa", "guest_name": "Ivy Penhallow",
            "guest_role": "knitter", "guest_memory": "talked about her jumpers",
            "lines": [{"speaker": "kettle_a", "text": "Ivy, sit down."}, {"speaker": "guest", "text": "Thank you, love."},
                      {"speaker": "kettle_b", "text": "How many jumpers?"}, {"speaker": "guest", "text": "Hundreds."}]})
    _stub(monkeypatch, reply)
    writers.script_segment(Segment(slot_id=9, type=T.interview, show="kettle", brief=kettle._SOFA, target_s=200), w)
    assert w.person_by_name("Ivy Penhallow").memories[-1]["show"] == "The Kettle's On"


def test_each_lap_of_the_loop_has_its_own_expert_angle_and_every_call_is_remembered(monkeypatch):
    """The second scratch run's hour had the expert on the same three things five times, and callers ringing about
    the same five problems: the expert's loop item had one brief, and a call saw only the last ten items."""
    show = kettle.SHOW_DEF
    n = len(show.pattern)
    laps = [show.item(n - 1 + k * (n - show.loop_from)).brief for k in range(4)]
    assert len(set(laps)) == 4 and all("already said tonight" in b for b in laps)
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    kettle.commission(w)
    w.archive += [{"date": w.last_date, "show": "kettle", "type": "call", "headline": f"Problem {i}", "text": "..."}
                  for i in range(14)]
    said = kettle.for_prompt(w)
    assert "Problem 0" in said and "Problem 13" in said
