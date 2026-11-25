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
    seg = Segment(slot_id=3, type=T.interview, show="coastroad", brief="{m2}", target_s=60)
    tv.aired(seg, w)
    assert not tv.tonight(w)["aired"]                     # not the leg's first meeting
    seg.brief = "{m1}"
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
    for tok in ("{open}", "{m1}", "{r1}", "{x1}", "{close}"):
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
        if tok == "{r1}":
            assert seg.work["location"] == "slipway"           # leg 1 is by the foot ferry
        if tok == "{x1}":                                       # a wait is at the last stop, the travelling done
            assert seg.work["location"] == leg["stops"][-1]["backdrop"]
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
    tv.aired(Segment(slot_id=3, type=T.interview, show="coastroad", brief="{m1}", target_s=60), w)
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
    toks = ["{open}", "{close}"] + [f"{{m{i}}}" for i in range(1, tv.STOPS + 1)] + ["{r1}", "{r2}", "{x5}"]
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
    seg = Segment(slot_id=4, type=T.interview, show="coastroad", brief="{r1}", target_s=60)
    writers.script_segment(seg, w)
    assert {l.guest_name for l in seg.lines} == {tv.HOST}
    assert (len(w.person_by_name(tv.HOST).memories), w.person_by_name(tv.HOST).role) == before


def test_a_resident_lorna_meets_has_no_family_on_air_unless_the_briefing_gives_one():
    """The first run gave Stan Tully a sister he never had ("a cot for my sister's first")."""
    from entertainment import travelogue
    assert "no family on air (no sister" in travelogue._RULES and "unless the briefing gives them one" in travelogue._RULES


def _said(lines, **kw):
    def reply(schema):
        return schema.model_validate({
            "headline": "Lorna on the road", "lower_third": "The Coast Road", "thread_id": None,
            "guest_name": tv.HOST, "guest_role": "comedian", "lines": [
                {"speaker": "guest", "guest_name": who, "text": t} for who, t in lines], **kw})
    return reply


def test_a_sentence_giving_someone_family_off_their_record_goes(channel, monkeypatch, nowhere):
    """The rehearsal of 2026-11-16: "I built the whole front of my wife's dresser" for Stan Tully, whose record has a
    mother (his tug is named after her) and no wife. The rule in the prompt didn't hold."""
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    other = tv.series(w)["legs"][0]["stops"][0]["meet"]
    w.person_by_name(other).memories.append({"date": "2026-11-01", "show": "x", "said": "named the boat after his mother"})
    _stub(monkeypatch, _said([
        (tv.HOST, "What did you do while you waited?"),
        (other, "Joinery, mostly. I built the whole front of my wife's dresser off this very slip."),
        (tv.HOST, "In a boat?"),
        (other, "My mum taught me patience. She named the tide clock."),
        (other, "My sister's boy rows now."),
        (tv.HOST, "Lovely.")], guest_memory="built my wife's dresser while waiting"))
    seg = Segment(slot_id=5, type=T.interview, show="coastroad", brief="{m1}", target_s=150)
    writers.script_segment(seg, w)
    said = [(l.guest_name, l.text) for l in seg.lines]
    assert (other, "Joinery, mostly.") in said                                   # the wife's sentence went
    assert (other, "My mum taught me patience. She named the tide clock.") in said   # a mother is on record
    assert not any("sister" in t for _, t in said)                               # the whole line went
    assert not any("dresser" in m["said"] for m in w.person_by_name(other).memories)


def test_a_piece_lorna_gives_alone_loses_someone_elses_lines_not_the_whole_piece(channel, monkeypatch, nowhere):
    """The rehearsal's arrival at the quay rail had the next resident speaking in it, and the template aired. (The
    road item ends on the arrival since the arrival items went.)"""
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    nxt = tv.series(w)["legs"][0]["stops"][1]["meet"]
    _stub(monkeypatch, _said([(tv.HOST, "Here's the quay rail."), (nxt, "Morning, Lorna."),
                              (tv.HOST, "That's Ellis, off his shift."), (tv.HOST, "The boxes are going over."),
                              (tv.HOST, "On we go.")]))
    seg = Segment(slot_id=6, type=T.interview, show="coastroad", brief="{r1}", target_s=60)
    writers.script_segment(seg, w)
    assert [l.text for l in seg.lines] == ["Here's the quay rail.", "That's Ellis, off his shift.",
                                           "The boxes are going over.", "On we go."]


def test_each_item_knows_where_she_is_in_the_leg(channel, monkeypatch, nowhere):
    """Told only "ON THE ROAD to the quay rail", the writer had her there already; the arrival and the meeting both
    arrived again (rehearsal, 2026-11-16)."""
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    stops = tv.series(w)["legs"][0]["stops"]
    road = tv.brief_for(w, "{r1}")
    assert f"from {stops[0]['place']} to {stops[1]['place']}" in road and "ending as she gets there" in road
    assert f"{stops[1]['meet']} doesn't speak" in road
    assert f"{stops[0]['meet']} doesn't speak" in tv.brief_for(w, "{open}")
    assert stops[0]["what"] in tv.brief_for(w, "{open}")                  # the opening arrives at the first stop
    assert "no arriving again" in tv.brief_for(w, "{m2}") and "no arriving again" in tv.brief_for(w, "{close}")
    assert "The day only moves on" in tv._RULES


def test_a_sentence_already_said_today_goes_and_only_the_close_knows_how_the_day_ends(channel, monkeypatch, nowhere):
    """Rehearsal, 2026-11-16: the meeting at the Crown opened with the arrival's own sentence, word for word, and the
    opening, which saw the leg's ending in every prompt, gave it away."""
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    leg = tv.series(w)["legs"][0]
    w.archive.append({"date": w.last_date, "show": "coastroad", "type": "interview", "headline": "arrives",
                      "text": "Right, I've made it to the back room of the Crown. Right.", "aired": False, "ts": 0})
    other = leg["stops"][0]["meet"]
    _stub(monkeypatch, _said([(tv.HOST, "Right, I've made it to the back room of the Crown. Jan, how long?"),
                              (other, "Since I could reach the oche."), (tv.HOST, "Right."),
                              (other, "Practice, love.")]))
    seg = Segment(slot_id=7, type=T.interview, show="coastroad", brief="{m1}", target_s=150)
    writers.script_segment(seg, w)
    assert [l.text for l in seg.lines][:3] == ["Jan, how long?", "Since I could reach the oche.", "Right."]
    assert leg["ends"] not in tv.for_prompt(w) and leg["ends"] in tv.brief_for(w, "{close}")
    assert "nothing of how the day ends" in tv.brief_for(w, "{open}") and "No hello" in tv.brief_for(w, "{close}")
    assert "Nobody makes up news" in tv._RULES


def test_each_brief_says_what_is_done_and_what_is_still_to_come():
    """A road item said "third leg done" before the third meeting (rehearsal, 2026-11-16)."""
    leg = {"stops": [{"place": f"Stop {k}", "meet": f"Person {k}"} for k in "ABC"], "travel": "a borrowed bike"}
    r2 = tv.day_so_far(leg, "r2")
    done, to_come = r2.split("Still to come: ")
    assert "meeting Person B at Stop B" in done and "meeting Person C at Stop C" in to_come and "the goodbye" in to_come
    assert "the leg isn't over until the goodbye" in r2
    assert "done: nothing yet" in tv.day_so_far(leg, "open")
    wait = tv.day_so_far(leg, "x4")
    assert "meeting Person C at Stop C" in wait.split("Still to come")[0] and "Still to come: the goodbye" in wait
    assert "while she waits at Stop C, the travelling done" in wait
    assert "Still to come: nothing" in tv.day_so_far(leg, "close")


def test_what_has_come_up_in_three_items_is_named_but_not_names_the_vehicle_or_waiting():
    """The bike's brakes came up in seven items of leg 3 (rehearsal, 2026-11-16)."""
    leg = {"stops": [{"place": "the Crown", "meet": "Ellis Porrett"}], "travel": "a borrowed bike with untested brakes"}
    said = ["The brakes squeal and the gulls watch. Ellis waves. I'm waiting on the bike.",
            "Those brakes again, and a gull on the bike. Ellis laughs. Still waiting.",
            "The brakes held! Ellis, the bike, waiting, waiting.", "Nothing about it here."]
    enough = tv.said_enough(said, leg)
    assert "brake" in enough and "gull" not in enough                    # gulls came up in two items
    assert not {"bike", "elli", "ellis", "waiting", "wait"} & set(enough)


def test_items_see_earlier_items_in_full_from_the_cache(channel, monkeypatch, nowhere, tmp_path):
    """The archive keeps an item's first 400 characters; what a meeting established comes later in it."""
    from newsroom.config import CONFIG
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    import dataclasses
    cache = tmp_path / "cache"
    cache.mkdir()
    long_line = "word " * 120 + "and the brakes were tested on the hill."
    (cache / "h1.json").write_text(json.dumps({"lines": [{"text": long_line}]}), encoding="utf-8")
    monkeypatch.setattr("newsroom.config.CONFIG", dataclasses.replace(
        CONFIG, paths=dataclasses.replace(CONFIG.paths, cache=cache)))
    w.archive.append({"date": w.last_date, "show": "coastroad", "type": "interview", "headline": "h",
                      "text": long_line[:400], "hash": "h1", "aired": False, "ts": 0})
    assert "the brakes were tested on the hill" in tv.for_prompt(w)


def test_only_the_opening_hears_the_legs_joke_and_the_plans_notes_are_hers_to_tell(channel, monkeypatch, nowhere):
    """Leg 4's "boots, not the good shoes" went to every item, and the boots came up in nine of ten; the plan's
    first-person note went out word for word; and Gwen quoted Wynn, whom she never met (rehearsal, 2026-11-16)."""
    assert tv.how({"travel": "On foot from the lighthouse gate, down the estuary path - boots, not the good shoes"}) \
        == "On foot from the lighthouse gate"
    assert tv.how({"travel": "A borrowed bike along the coast road \u2014 one gear"}) == "A borrowed bike along the coast road"
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    leg = tv.series(w)["legs"][1]
    leg["travel"] = "the bus, which stops for everyone, rattling"
    w.travelogue["legs"][-1]["n"] = 2
    assert "rattling" in tv.brief_for(w, "{open}")
    assert all("rattling" not in tv.brief_for(w, t) for t in ("{r1}", "{x1}", "{m2}")) and "rattling" not in tv.for_prompt(w)
    assert "in her own words (the plan's note, not to be read out)" in tv.brief_for(w, "{r1}")
    assert "knows nothing of who she met there" in tv.brief_for(w, "{m2}")


def test_lornas_biscuit_is_the_first_openings_alone_and_the_day_so_far_is_not_read_out(channel, monkeypatch, nowhere):
    """Leg 5 of the rehearsal (2026-11-16): the biscuit at every stop, four times, and the links reading the route aloud."""
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    other = tv.series(w)["legs"][0]["stops"][0]["meet"]
    _stub(monkeypatch, _said([(tv.HOST, "Fourteen minutes for a biscuit, once. Anyway, the tea room."),
                              (other, "A biscuit? We do biscuits."), (tv.HOST, "No biscuits for me."),
                              (other, "Suit yourself."), (tv.HOST, "Lovely view.")]))
    seg = Segment(slot_id=8, type=T.interview, show="coastroad", brief="{m1}", target_s=150)
    writers.script_segment(seg, w)
    said = [(l.guest_name, l.text) for l in seg.lines]
    assert (tv.HOST, "Anyway, the tea room.") in said and (other, "A biscuit? We do biscuits.") in said
    assert not any(n == tv.HOST and "biscuit" in t.lower() for n, t in said)
    _stub(monkeypatch, _said([(tv.HOST, t) for t in ("Hello, and welcome.", "Fourteen minutes for a biscuit, once.",
                                                     "So, every slow way there is.", "Off we go.")]))
    seg = Segment(slot_id=1, type=T.interview, show="coastroad", brief="{open}", target_s=50, part="open")
    writers.script_segment(seg, w)
    assert any("biscuit" in l.text for l in seg.lines)                      # leg 1's opening keeps it
    assert "never for saying: no reading out what's ahead" in tv.brief_for(w, "{r1}")



def test_a_leg_is_seven_planned_items_with_no_arrival_items():
    """The user, 2026-11-16: every stop had a road item, an arrival and a meeting, and the editor found each place
    arrived at two or three times, five reviews running."""
    planned = [i.brief for i in tv.show_def().pattern if isinstance(getattr(i, "brief", None), str)]
    assert planned == ["{open}", "{m1}", "{r1}", "{m2}", "{r2}", "{m3}"]
    assert [i.brief for i in tv.show_def().closing] == ["{close}"]
    assert tv.ORDER_STEPS == ("open", "m1", "r1", "m2", "r2", "m3", "close")


def test_the_goodbye_is_the_closes_alone(channel, monkeypatch, nowhere):
    """Leg 6 of the rehearsal (2026-11-16): the last stop's note was the ending itself, and the road there thanked us
    for coming along and said farewell a meeting early."""
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    assert "This is the last stop, but not the end" in tv.brief_for(w, "{r2}")
    assert "last stop" not in tv.brief_for(w, "{r1}")
    _stub(monkeypatch, _said([(tv.HOST, t) for t in (
        "Down the hill to the harbour steps.", "Full circle, and the ferry's coming in.",
        "Thanks for coming along the coast road with me.", "Until next time.", "The step is cold.")]))
    seg = Segment(slot_id=9, type=T.interview, show="coastroad", brief="{r2}", target_s=80)
    writers.script_segment(seg, w)
    assert [l.text for l in seg.lines] == ["Down the hill to the harbour steps.", "Full circle, and the ferry's coming in.",
                                           "The step is cold."]


def test_a_wait_is_at_the_last_stop_not_on_the_way(channel, monkeypatch, nowhere):
    """2026-11-20: told only "WHILE SHE WAITS (The Saltby foot ferry from the town quay)", the waits after she had landed
    at the Saltby slip had her back at the town quay waiting for the boat, and "still on the boat"."""
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    last = tv.series(w)["legs"][0]["stops"][-1]
    for tok in ("{x1}", "{x5}"):
        said = tv.brief_for(w, tok)
        assert said.startswith(f"WHILE SHE WAITS at {last['place']}, after meeting {last['meet']}")
        assert "no boarding, no crossing" in said


# ------------------------------------------------------------------ the map (newsroom/geography.py)

def _off_the_map():
    """The 2026-11-20 ferry leg, as the saved route of 2026-11-14 has it: the town quay, the fish quay, then over."""
    r = _route().model_dump()
    r["legs"][0]["travel"] = "The Saltby foot ferry from the town quay, fourteen minutes if the tide is kind"
    for s, (backdrop, place) in zip(r["legs"][0]["stops"], (
            ("harbour", "The ferry steps at the town quay"), ("fish_quay", "The quay rail above the auction floor"),
            ("slipway", "The Saltby slip, with the ferry's ring worn shiny"))):
        s.update(backdrop=backdrop, place=place)
    for leg in r["legs"][1:]:                       # the rest stay on the Saltby side
        for s in leg["stops"]:
            s.update(backdrop="village", place="Saltby green")
    return tv.Route.model_validate(r)


def test_the_planner_is_given_the_coast_and_the_stand_in_keeps_to_it(channel):
    w = _world()
    assert "THE COAST, in order" in tv._asked(w) and "saltby_slip" in tv._asked(w)
    assert tv.route_trouble(tv._stand_in_route()["legs"]) == []


def test_a_route_against_the_map_is_asked_for_once_more(channel, monkeypatch, nowhere):
    asked = []

    def complete_json(task, schema, system, user, **kw):
        asked.append(user)
        return _off_the_map() if len(asked) == 1 else _route()
    monkeypatch.setattr(llm, "complete_json", complete_json)
    w = _world()
    tv.commission(w)
    assert not tv.series(w)["stand_in"] and len(asked) == 2
    assert "THE ROUTE GOES AGAINST THE MAP" in asked[1] and "leg 1" in asked[1] and "Quay Steps" in asked[1]


def test_a_route_against_the_map_twice_gives_way_to_the_stand_in(channel, monkeypatch, nowhere):
    _stub(monkeypatch, lambda schema: _off_the_map())
    w = _world()
    tv.commission(w)
    assert tv.series(w)["stand_in"]


def test_a_saved_route_against_the_map_is_planned_again(channel, monkeypatch, tmp_path):
    path = tmp_path / "lorna_quayle.json"
    path.write_text(json.dumps({**_off_the_map().model_dump(), "title": "The Saved One", "stand_in": False}),
                    encoding="utf-8")
    monkeypatch.setattr(tv, "_saved_route_path", lambda: path)
    _stub(monkeypatch)
    w = _world()
    tv.commission(w)
    assert tv.series(w)["title"] == "Every Slow Way"


def test_the_route_is_planned_by_sonnet_not_the_chambers_thinking_model():
    """2026-11-20: on The Chamber's route, DeepSeek's thinking spent the whole 32000 tokens and answered nothing, about
    six minutes a time before the fallback. Sonnet plans it, as it plans Marina Row's episodes (soap.py)."""
    from entertainment import soap
    from newsroom.config import CONFIG

    assert tv.TASK == soap.TASK
    assert CONFIG.llm.routes[tv.TASK] == "claude_sonnet" or "travelogue" in CONFIG.llm.routes
    assert "LAST LEG'S LAST STOP are both in Port Wexley" in tv._SYSTEM


def test_the_opening_and_the_road_items_carry_the_route_for_the_map(channel, monkeypatch, nowhere):
    """The journey on the town's map (newsroom/routemap.py): up for the first line of the opening and of each road
    item, with the stop she is heading for; never over a meeting."""
    from newsroom.models import Line, Segment, SegmentType
    from newsroom.player import View

    w = _world()
    _stub(monkeypatch)
    entry = tv.commission(w)

    def item(brief):
        seg = Segment(slot_id=1, type=SegmentType.interview, show=tv.SHOW, brief=brief,
                      lines=[Line(speaker="guest", guest_name=tv.HOST, text="Off we go."),
                             Line(speaker="guest", guest_name=tv.HOST, text="And on.")])
        tv.after(seg, w)
        return seg
    opening, road, meeting = item("{open}"), item("{r1}"), item("{m1}")
    r = road.work["route"]
    assert len(r["legs"]) == tv.LEGS and r["n"] == entry["n"] == 1 and r["to"] == 1
    assert r["caption"].startswith("Leg 1 of 6: ")
    assert opening.work["route"]["to"] is None and "route" not in meeting.work
    v = View()
    tv.view(road, v, 0)
    assert v.scene["route"] == r
    tv.view(road, v, 1)
    assert v.scene["route"] is None                                   # the first line only


def test_a_leg_that_ends_on_the_ferry_says_goodbye_on_the_crossing(channel, monkeypatch, nowhere):
    """2026-11-24: leg 1's plan ended with the ferry bumping the Saltby slip, but the close was told "still at" the
    Quay Steps, so on air she never crossed, and leg 2 starts on the Saltby side (the user, 2026-11-25)."""
    r = _route().model_dump()
    r["legs"][0]["ends"] = "Eight minutes later the ferry bumps the Saltby slip and Lorna steps off on the Saltby side."
    r["legs"][0]["stops"][-1].update(place="The Quay Steps", backdrop="harbour")
    r["legs"][1]["stops"][0].update(place="The top of the Saltby slip", backdrop="slipway")
    w = _world()
    _stub(monkeypatch, lambda schema: tv.Route.model_validate(r))
    tv.commission(w)
    entry, s = tv.booked(w)
    close = tv._item(entry, s, "close")
    assert close["crossing"] and close["backdrop"] == "slipway"            # the ferry's travel backdrop
    said = tv.brief_for(w, "{close}")
    assert "this is the crossing, happening now" in said and "still at" not in said
    assert "bumps the Saltby slip" in said
    wait = tv.brief_for(w, "{x1}")
    assert "the crossing is still to come" in wait and "no boarding, no crossing" in wait
    assert "the crossing, and the goodbye" in tv.day_so_far(s["legs"][0], "x1", crossing=True)
    assert tv.ends_crossing(s, 1) and not tv.ends_crossing(s, 2) and not tv.ends_crossing(s, tv.LEGS)


def test_a_leg_that_ends_at_its_last_stop_says_goodbye_there(channel, monkeypatch, nowhere):
    """Leg 6 of the series planned on 2026-11-24 names the ferry ("where the ferry took her across the Grey at the
    start") but goes home by bus to the town side: no crossing at its end."""
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    entry, s = tv.booked(w)
    close = tv._item(entry, s, "close")
    assert not close["crossing"] and close["backdrop"] == s["legs"][0]["stops"][-1]["backdrop"]
    assert f"still at {s['legs'][0]['stops'][-1]['place']}" in tv.brief_for(w, "{close}")
    assert "the travelling done" in tv.day_so_far(s["legs"][0], "x1")


def test_a_meeting_asks_for_answers_of_a_few_sentences(channel, monkeypatch, nowhere):
    """2026-11-24: twenty lines of a sentence each, 375 words of 525, and seven waits filled the leg."""
    w = _world()
    _stub(monkeypatch)
    tv.commission(w)
    assert "answers run two to four sentences" in tv.brief_for(w, "{m1}")
