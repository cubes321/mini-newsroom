"""The Coast Road, Channel 8's travelogue (entertainment/travelogue.py): Lorna Quayle round the coast in six legs,
alternating with Tideline at 20:40 by what aired, not the weekday. The model is stubbed: no network."""
from __future__ import annotations

import json
import time
from datetime import date

import pygame
import pytest

import entertainment
from entertainment import travelogue as tv
from newsroom import llm, player, scenes, schedule, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


@pytest.fixture
def channel():
    undo = entertainment.use()
    yield
    undo()


def _world(day="2026-11-20"):
    w = world_mod.seed()
    w.last_date = day
    w.ensure_person(tv.HOST, "comedian and singer", "resident", gender="f", age="middle", accent="british")
    w.person_by_name(tv.HOST).voice = "bf_emma"
    return w


def _route(dupe=None):
    legs = []
    for i in range(tv.LEGS):
        stops = [{"backdrop": "harbour", "place": f"stop {i}-{k}", "what": "something happens here",
                  "meet": dupe if (dupe and i == 1 and k == 0) else f"Resident {chr(65 + i)}{chr(65 + k)} Smith",
                  "role": "harbour hand", "gender": "f", "age": "middle", "talk": "a long wait of their own"}
                 for k in range(tv.STOPS)]
        legs.append({"title": f"Leg {i + 1}", "travel": "the Saltby foot ferry" if i == 0 else "the bus",
                     "stops": stops, "ends": f"the end of leg {i + 1}"})
    return tv.Route.model_validate({"title": "Every Slow Way", "why": "to collect waiting stories", "legs": legs})


def _stub(monkeypatch, reply=None, fail=False):
    def complete_json(task, schema, system, user, **kw):
        if fail:
            raise llm.LLMError("down")
        return reply(schema) if reply else _route()
    monkeypatch.setattr(llm, "complete_json", complete_json)


@pytest.fixture
def nowhere(monkeypatch, tmp_path):
    """No saved route on disk for these tests."""
    monkeypatch.setattr(tv, "_saved_route_path", lambda: tmp_path / "none.json")
    return tmp_path


# ------------------------------------------------------------------ the alternation

def _aired_wild(w, day):
    w.wildlife.setdefault("episodes", []).append({"date": day, "sight": "egret", "aired": True})


def test_the_slot_alternates_by_what_aired_not_the_weekday(channel, monkeypatch, nowhere):
    w = _world()
    monkeypatch.setattr(world_mod, "_WORLD", w)
    assert tv.rotation(date(2026, 11, 20)) is None                      # nothing yet: Tideline first
    _aired_wild(w, "2026-11-18")
    assert tv.rotation(date(2026, 11, 20)) == "coastroad"               # Tideline last: the road's turn
    w.travelogue["legs"] = [{"date": "2026-11-20", "made": "x", "n": 1, "aired": True}]
    assert tv.rotation(date(2026, 11, 20)) == "coastroad"               # tonight's holds, aired or not
    assert tv.rotation(date(2026, 11, 22)) is None                      # then Tideline, two days on
    _aired_wild(w, "2026-11-22")
    assert tv.rotation(date(2026, 11, 26)) == "coastroad"               # a gap of days changes nothing


def test_show_at_puts_the_travelogue_on_at_twenty_to_nine_on_its_nights(channel, monkeypatch):
    w = _world(time.strftime("%Y-%m-%d"))
    monkeypatch.setattr(world_mod, "_WORLD", w)
    assert schedule.show_at(_at(20, 45)).id == "tideline"
    _aired_wild(w, "2000-01-01")
    assert schedule.show_at(_at(20, 45)).id == "coastroad" and schedule.show_end(_at(20, 45)) == _at(21, 0)
    assert schedule.show_at(_at(21, 5)).id == "closedown"


def test_a_finished_series_gives_tideline_the_slot(channel, monkeypatch, nowhere):
    w = _world()
    monkeypatch.setattr(world_mod, "_WORLD", w)
    _stub(monkeypatch)
    tv.commission(w)
    made = tv.series(w)["made"]
    w.travelogue["legs"] = [{"date": f"2026-11-{k:02d}", "made": made, "n": k, "aired": True} for k in range(1, 7)]
    _aired_wild(w, "2026-11-19")
    assert tv.finished(w) and tv.rotation(date(2026, 11, 21)) is None


# ------------------------------------------------------------------ the route and the legs

def test_the_first_leg_plans_the_route_casts_the_residents_and_gives_lorna_her_voice(channel, monkeypatch, nowhere):
    w = _world()
    w.ensure_person("Resident AA Smith", "retired keeper of the light", "resident", gender="f", age="old")
    _stub(monkeypatch)
    entry = tv.commission(w)
    s = tv.series(w)
    assert entry["n"] == 1 and s["title"] == "Every Slow Way" and not s["stand_in"]
    assert w.person_by_name("Resident BC Smith") is not None
    assert s["legs"][0]["stops"][0]["role"] == "retired keeper of the light"       # the town's, not the plan's
    assert w.person_by_name(tv.HOST).voice == "bf_quayle"
    assert w.voice_for("guest", tv.HOST) == "bf_quayle"


def test_a_route_meeting_someone_twice_or_a_presenter_gives_way_to_the_stand_in(channel, monkeypatch, nowhere):
    for dupe in ("Resident AA Smith", "Rowan Polglase"):
        w = _world()
        _stub(monkeypatch, lambda schema, d=dupe: _route(d))
        tv.commission(w)
        assert tv.series(w)["stand_in"]


def test_a_saved_route_is_used_as_it_stands(channel, monkeypatch, tmp_path):
    path = tmp_path / "lorna_quayle.json"
    path.write_text(json.dumps({**_route().model_dump(), "title": "The Saved One", "stand_in": False}), encoding="utf-8")
    monkeypatch.setattr(tv, "_saved_route_path", lambda: path)
    _stub(monkeypatch, fail=True)                         # no call needed
    w = _world()
    tv.commission(w)
    assert tv.series(w)["title"] == "The Saved One" and not tv.series(w)["stand_in"]


def test_the_next_leg_follows_the_last_aired_one(channel, monkeypatch, nowhere):
    w = _world("2026-11-20")
    _stub(monkeypatch)
    tv.commission(w)
    seg = Segment(slot_id=3, type=T.interview, show="coastroad", brief="{a2}", target_s=60)
    tv.aired(seg, w)
    assert not tv.tonight(w)["aired"]                     # not the leg's first stop
    seg.brief = "{a1}"
    tv.aired(seg, w)
    assert tv.tonight(w)["aired"]
    w.last_date = "2026-11-24"
    assert tv.commission(w)["n"] == 2
    w.last_date = "2026-11-28"                            # leg 2 never aired: it comes again
    assert tv.commission(w)["n"] == 2


# ------------------------------------------------------------------ the items

def test_every_item_is_on_location_filmed_by_day_with_lorna_and_the_stops_resident(channel, monkeypatch, nowhere):
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    leg = tv.series(w)["legs"][0]
    _stub(monkeypatch, fail=True)
    for tok in ("{open}", "{a1}", "{m1}", "{r1}", "{x1}", "{close}"):
        seg = Segment(slot_id=3, type=T.interview, show="coastroad", brief=tok, target_s=60,
                      part={"{open}": "open", "{close}": "close"}.get(tok, ""))
        writers.script_segment(seg, w)
        names = {l.guest_name for l in seg.lines}
        assert seg.lines and seg.work["filmed"] and all(l.speaker == "guest" for l in seg.lines)
        if tok == "{m1}":
            assert names == {tv.HOST, leg["stops"][0]["meet"]} and seg.work["road"]["other"] == leg["stops"][0]["meet"]
            assert seg.work["location"] == leg["stops"][0]["backdrop"]
        else:
            assert names == {tv.HOST}
        if tok in ("{r1}", "{x1}"):
            assert seg.work["location"] == "slipway"           # leg 1 is by the foot ferry
        if tok == "{close}":
            assert seg.work["tod"] == "dusk"


def test_a_meeting_with_someone_else_isnt_aired_and_the_memory_is_the_residents(channel, monkeypatch, nowhere):
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    other = tv.series(w)["legs"][0]["stops"][0]["meet"]

    def reply(who):
        def r(schema):
            return schema.model_validate({
                "headline": "Lorna meets someone", "lower_third": "The Coast Road", "thread_id": None,
                "guest_name": tv.HOST, "guest_role": "comedian", "guest_memory": "met Lorna on the road",
                "lines": [{"speaker": "guest", "guest_name": tv.HOST, "text": "Hello!"},
                          {"speaker": "guest", "guest_name": who, "text": "Hello, Lorna."},
                          {"speaker": "guest", "guest_name": tv.HOST, "text": "How long have you waited?"},
                          {"speaker": "guest", "guest_name": who, "text": "Since Tuesday."}]})
        return r
    _stub(monkeypatch, reply("Ada Quarrie"))
    seg = Segment(slot_id=4, type=T.interview, show="coastroad", brief="{m1}", target_s=150)
    writers.script_segment(seg, w)
    assert "Ada Quarrie" not in {l.guest_name for l in seg.lines}           # the template instead
    _stub(monkeypatch, reply(other))
    lorna_before = len(w.person_by_name(tv.HOST).memories)
    seg = Segment(slot_id=5, type=T.interview, show="coastroad", brief="{m1}", target_s=150)
    writers.script_segment(seg, w)
    assert {l.guest_name for l in seg.lines} == {tv.HOST, other}
    assert any(m["said"] == "met Lorna on the road" for m in w.person_by_name(other).memories)
    assert len(w.person_by_name(tv.HOST).memories) == lorna_before


def test_the_road_view_draws_lorna_and_the_resident_in_their_looks(channel, monkeypatch, nowhere):
    pygame.font.init()
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    _stub(monkeypatch, fail=True)
    seg = Segment(slot_id=3, type=T.interview, show="coastroad", brief="{m2}", target_s=150)
    writers.script_segment(seg, w)
    for who in (tv.HOST, seg.work["road"]["other"]):
        v = player.View(mode="field", tag="LIVE", guest_name=who, speaker="guest")
        tv.view(seg, v, 0)
        assert v.mode == "road" and v.tag == "" and v.scene["other"] == seg.work["road"]["other"]
        scenes.render(pygame.Surface((320, 180)), v, 1.0)
    assert scenes.PINNED_LOOKS[tv.HOST] is tv.HOST_LOOK
    assert tv.caption(w, tv.HOST) == "The Coast Road: leg 1 of 6"


def test_spare_minutes_go_to_new_waiting_moments_never_a_planned_item_again():
    sh = tv.show_def()
    planned = {sh.item(k).brief for k in range(sh.loop_from)} - {""}
    spares = [sh.item(k).brief for k in range(sh.loop_from, sh.loop_from + 4 * (len(sh.pattern) - sh.loop_from))]
    assert not planned & set(spares)
    waiting = [b for b in spares if b.startswith("{x")]
    assert len(waiting) == len(set(waiting)) == tv.SPARES
    assert sh.closing[0].brief == "{close}"


def test_the_last_leg_keeps_its_slot_all_night_once_its_first_stop_has_aired(channel, monkeypatch, nowhere):
    """The finale was cut off three minutes in: with the sixth leg stamped aired the series counted as finished, and the
    slot went back to Tideline mid-leg."""
    w = _world("2026-12-10")
    monkeypatch.setattr(world_mod, "_WORLD", w)
    _stub(monkeypatch)
    tv.commission(w)
    made = tv.series(w)["made"]
    w.travelogue["legs"] = [{"date": f"2026-11-{k:02d}", "made": made, "n": k, "aired": True} for k in range(1, 6)]
    _aired_wild(w, "2026-12-08")
    assert tv.commission(w)["n"] == 6
    tv.aired(Segment(slot_id=3, type=T.interview, show="coastroad", brief="{a1}", target_s=60), w)
    assert tv.finished(w) and tv.rotation(date(2026, 12, 10)) == "coastroad"
    assert tv.rotation(date(2026, 12, 12)) is None


@pytest.mark.parametrize("n", range(1, 7))
def test_every_item_of_every_leg_goes_through_the_real_path(n, channel, monkeypatch, nowhere):
    pygame.font.init()
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    tv.tonight(w)["n"] = n
    _stub(monkeypatch, fail=True)
    toks = ["{open}", "{close}"] + [f"{{{k}{i}}}" for k in "am" for i in range(1, tv.STOPS + 1)] + ["{r1}", "{r2}", "{x5}"]
    for tok in toks:
        assert tv.brief_for(w, tok)
        seg = Segment(slot_id=3, type=T.interview, show="coastroad", brief=tok, target_s=60,
                      part={"{open}": "open", "{close}": "close"}.get(tok, ""))
        writers.script_segment(seg, w)
        assert seg.lines and seg.work["filmed"]
        v = player.View(mode="field", speaker="guest", guest_name=seg.lines[0].guest_name)
        tv.view(seg, v, 0)
        scenes.render(pygame.Surface((320, 180)), v, 1.0)
    assert ("Next time" in tv.brief_for(w, "{close}")) == (n < tv.LEGS)


def test_a_piece_to_camera_from_the_model_writes_lorna_no_memory(channel, monkeypatch, nowhere):
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)

    def reply(schema):
        return schema.model_validate({
            "headline": "Lorna arrives at the quay", "lower_third": "The Coast Road", "thread_id": None,
            "guest_name": tv.HOST, "guest_role": "travel presenter extraordinaire", "guest_memory": "arrived somewhere",
            "lines": [{"speaker": "guest", "guest_name": tv.HOST, "text": t} for t in ("Here.", "There.", "Look.", "Right.")]})
    _stub(monkeypatch, reply)
    before = (len(w.person_by_name(tv.HOST).memories), w.person_by_name(tv.HOST).role)
    seg = Segment(slot_id=4, type=T.interview, show="coastroad", brief="{a2}", target_s=60)
    writers.script_segment(seg, w)
    assert {l.guest_name for l in seg.lines} == {tv.HOST}
    assert (len(w.person_by_name(tv.HOST).memories), w.person_by_name(tv.HOST).role) == before
