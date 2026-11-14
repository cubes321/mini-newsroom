"""Tideline, Channel 8's wildlife series (entertainment/wildlife.py): one sight a night from the seasonal list, chosen
in code, its number drawn in code; a plan in the back office with a stand-in; filmed by day, the hide view, and a log
stamped as it airs. The model is stubbed: no network."""
from __future__ import annotations

import time
from datetime import date, timedelta

import pygame
import pytest

import entertainment
from entertainment import seasons, wildlife
from newsroom import llm, player, scenes, schedule, talk, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


@pytest.fixture
def channel():
    undo = entertainment.use()
    yield
    undo()


def _stub(monkeypatch, reply=None, fail=False):
    def complete_json(task, schema, system, user, **kw):
        if fail:
            raise llm.LLMError("down")
        return reply(schema) if reply else _plan()
    monkeypatch.setattr(llm, "complete_json", complete_json)


def _plan(meets=("Gwen Tarrant", "Eamon Trask", "Ruth Hallam")):
    return wildlife.WildEpisode.model_validate({
        "title": "Back on the Mud",
        "watches": [{"angle": f"angle {k} of the sight, what we watch", "shot": "close"}
                    for k in range(1, wildlife.SEQUENCES + 1)],
        "meets": [{"name": n, "role": "counter on the estuary", "gender": "f", "age": "old",
                   "talk": "thirty winters of counting"} for n in meets],
        "close": "Go at dawn on a falling tide, and stay on the path."})


def _world(day="2026-11-20"):
    w = world_mod.seed()
    w.last_date = day
    return w


def _air(w, day, sight, count=None):
    w.wildlife.setdefault("episodes", []).append(
        {"date": day, "sight": sight, "near": None, "count": count, "counted": "", "what": sight, "aired": True,
         "meets": [], "watches": [], "title": "", "close": ""})


# ------------------------------------------------------------------ the schedule

def test_tideline_follows_marina_row_at_twenty_to_nine_and_undo_takes_it_off():
    undo = entertainment.use()
    try:
        assert schedule.show_at(_at(20, 45)).id == "tideline" and schedule.show_end(_at(20, 45)) == _at(21, 0)
        assert schedule.show_at(_at(21, 5)).id == "closedown"
        assert scenes.SCENES["hide"] is wildlife.draw_scene and player.VIEW_HOOKS["tideline"] is wildlife.view
    finally:
        undo()
    assert "tideline" not in schedule.SHOWS and "hide" not in scenes.SCENES and "tideline" not in player.AIRED_HOOKS


def test_spare_minutes_go_to_new_notebook_moments_never_a_planned_item_again():
    sh = wildlife.show_def()
    planned = {sh.item(k).brief for k in range(sh.loop_from)} - {""}          # the bumper and the break have none
    spares = [sh.item(k).brief for k in range(sh.loop_from, sh.loop_from + 4 * (len(sh.pattern) - sh.loop_from))]
    assert not planned & set(spares)
    notebook = [b for b in spares if b.startswith("{x")]
    assert len(notebook) == len(set(notebook)) == wildlife.SPARES
    assert sh.closing[0].brief == "{close}"


# ------------------------------------------------------------------ the sight, in code

@pytest.mark.parametrize("every", [2, 4])
def test_sixty_nights_always_have_a_sight_and_keep_the_rests_and_rarities(every):
    """The advisor's sum: rests of 21 to 60 days on ten sights, a Channel 8 night every two days (every four once the
    travelogue alternates). Never empty; never back inside its rest while another is rested; rare ones once a winter."""
    w = _world()
    start = date(2026, 11, 1)
    leads = []
    for k in range(0, 120, every):
        day = start + timedelta(days=k)
        if day.month not in seasons.WINTER:
            continue
        w.last_date = day.isoformat()
        lead, near = wildlife.pick(w, day)
        assert lead.creature and day.month in lead.months
        assert near is None or (near.place[0] == lead.place[0] and near.id != lead.id)
        eps = wildlife.aired_episodes(w)
        gap = wildlife._since(eps, lead.id, day)
        if gap is not None and gap < lead.rest_days:      # back early only when nothing else is rested
            rested = [s for s in seasons.in_season(day.month) if s.creature and not s.rare
                      and (wildlife._since(eps, s.id, day) or 10 ** 6) >= s.rest_days]
            assert not rested
        _air(w, day.isoformat(), lead.id)
        leads.append(lead.id)
    assert len(set(leads)) >= 6                             # the winter's variety
    for rare in (s.id for s in seasons.SIGHTS if s.rare):
        assert leads.count(rare) <= 1


def test_the_number_is_the_bookings_drawn_in_code_and_the_same_every_time():
    pups = next(s for s in seasons.SIGHTS if s.id == "seal_colony")
    n = wildlife.count_for(pups, date(2026, 11, 20))
    assert n == wildlife.count_for(pups, date(2026, 11, 20)) and pups.count[0] <= n <= pups.count[1]
    roost = next(s for s in seasons.SIGHTS if s.id == "starlings")
    assert wildlife.count_for(roost, date(2026, 12, 2)) % 1000 == 0          # thousands, as a warden says them
    assert wildlife.count_for(next(s for s in seasons.SIGHTS if s.id == "heron"), date(2026, 12, 2)) is None


# ------------------------------------------------------------------ the plan

def test_an_episode_is_booked_once_and_the_residents_met_join_the_town(channel, monkeypatch):
    w = _world()
    _stub(monkeypatch)
    ep = wildlife.commission(w)
    assert wildlife.booked(w) is ep and not ep["stand_in"] and not ep["aired"]
    assert w.person_by_name("Eamon Trask") is not None
    assert ep["sight"] in {s.id for s in seasons.in_season(11)}


def test_a_plan_meeting_a_presenter_or_someone_twice_gives_way_to_the_stand_in(channel, monkeypatch):
    for meets in (("Gwen Tarrant", "Gwen Tarrant", "Ruth Hallam"), ("Rowan Polglase", "Eamon Trask", "Ruth Hallam")):
        w = _world()
        _stub(monkeypatch, lambda schema, m=meets: _plan(m))
        ep = wildlife.commission(w)
        assert ep["stand_in"] and len({m["name"] for m in ep["meets"]}) == wildlife.MEETS
        assert "Rowan Polglase" not in {m["name"] for m in ep["meets"]}


def test_someone_met_lately_isnt_met_again(channel, monkeypatch):
    w = _world()
    w.wildlife["episodes"] = [{"date": "2026-11-18", "sight": "curlew", "near": None, "count": 50, "counted": "",
                               "what": "", "aired": True, "title": "", "close": "", "watches": [],
                               "meets": [{"name": "Eamon Trask", "role": "keeper"}]}]
    _stub(monkeypatch)
    assert wildlife.commission(w)["stand_in"]


# ------------------------------------------------------------------ the items

def test_every_item_is_out_on_location_filmed_by_day_and_narration_is_in_the_hide(channel, monkeypatch):
    w = _world()
    _stub(monkeypatch)
    ep = wildlife.commission(w)
    lead = next(s for s in seasons.SIGHTS if s.id == ep["sight"])
    _stub(monkeypatch, fail=True)                        # the template's items get their places too
    for tok, kind in (("{open}", T.links), ("{w1}", T.links), ("{m1}", T.interview), ("{x2}", T.links),
                      ("{close}", T.links)):
        seg = Segment(slot_id=3, type=kind, show="tideline", brief=tok, target_s=60,
                      part={"{open}": "open", "{close}": "close"}.get(tok, ""))
        writers.script_segment(seg, w)
        assert seg.lines and seg.work["filmed"] and seg.work["location"] == lead.place[0]   # the neighbour shares it
        if tok in ("{w1}", "{x2}"):
            assert seg.work["hide"]["creature"] and {l.speaker for l in seg.lines} == {"naturalist"}
        if tok == "{m1}":
            assert {l.guest_name for l in seg.lines if l.speaker == "guest"} == {ep["meets"][0]["name"]}
        if tok == "{close}":
            assert seg.work["tod"] == "dusk"


def test_the_first_sequence_carries_the_number_and_the_rules_say_filmed_earlier(channel, monkeypatch):
    w = _world()
    _stub(monkeypatch)
    ep = wildlife.commission(w)
    first = wildlife.brief_for(w, "{w1}")
    if ep["count"] is not None:
        assert f"THE NUMBER: {ep['count']}" in first
    assert "THE NUMBER" not in wildlife.brief_for(w, "{w2}")
    assert "FILMED EARLIER" in writers.SHOW_SYSTEMS["tideline"][T.links]


def test_a_meeting_with_someone_who_wasnt_booked_isnt_aired(channel, monkeypatch):
    """(Narration is Rowan's alone by the schema already: Tideline's links cast is "naturalist" only.)"""
    w = _world()
    _stub(monkeypatch)
    ep = wildlife.commission(w)

    def reply(schema):
        return schema.model_validate({
            "headline": "Rowan meets a stranger", "lower_third": "Tideline", "thread_id": None,
            "guest_name": "Ada Quarrie", "guest_role": "passer-by",
            "lines": [{"speaker": "naturalist", "text": "Who's this?"},
                      {"speaker": "guest", "guest_name": "Ada Quarrie", "text": "Me."}]})
    _stub(monkeypatch, reply)
    seg = Segment(slot_id=4, type=T.interview, show="tideline", brief="{m2}", target_s=60)
    writers.script_segment(seg, w)
    assert {l.guest_name for l in seg.lines if l.speaker == "guest"} == {ep["meets"][1]["name"]}


# ------------------------------------------------------------------ on air

def test_the_view_hook_puts_narration_in_the_hide_with_no_live_tag_or_caption(channel, monkeypatch):
    w = _world()
    _stub(monkeypatch)
    wildlife.commission(w)
    _stub(monkeypatch, fail=True)
    seg = Segment(slot_id=3, type=T.links, show="tideline", brief="{w1}", target_s=60)
    writers.script_segment(seg, w)
    v = player.View(mode="field", tag="LIVE", lower_third=("Tideline", "x"))
    wildlife.view(seg, v, 0)
    assert v.mode == "hide" and v.tag == "" and v.lower_third is None and v.scene["creature"]
    pygame.font.init()
    canvas = pygame.Surface((320, 180))
    scenes.render(canvas, v, 1.0)                         # draws, through scenes.SCENES


def test_the_log_is_stamped_when_the_number_airs_and_the_town_talks_of_it_after(channel, monkeypatch):
    w = _world("2026-11-20")
    _stub(monkeypatch)
    ep = wildlife.commission(w)
    seg = Segment(slot_id=3, type=T.links, show="tideline", brief="{w2}", target_s=60)
    wildlife.aired(seg, w)
    assert not ep["aired"]                                 # not the one with the number
    seg.brief = "{w1}"
    wildlife.aired(seg, w)
    assert ep["aired"]
    assert talk.wildlife(w, date(2026, 11, 20)) is None    # tonight's: not talked of yet
    said = talk.wildlife(w, date(2026, 11, 21))
    assert said and "Tideline" in said and ep["what"] in said
    assert talk.wildlife(w, date(2026, 11, 24)) is None    # old news by then


def test_an_episode_never_aired_is_nobodys_talk_and_doesnt_rest_its_sight(channel, monkeypatch):
    w = _world("2026-11-20")
    _stub(monkeypatch)
    ep = wildlife.commission(w)
    assert talk.wildlife(w, date(2026, 11, 21)) is None
    w.last_date = "2026-11-22"
    assert ep["sight"] in {s.id for s in seasons.SIGHTS}
    assert wildlife.aired_episodes(w) == []


def test_the_facts_and_the_number_are_in_the_first_sequence_only_and_every_item_sees_all_said(channel, monkeypatch):
    """The first model run (2026-11-14) said "eight little egrets" and "thirty years ago there were none" in nearly
    every item: the sight's note and number were in every prompt, and only the last ten items, cut short."""
    w = _world()
    _stub(monkeypatch)
    ep = wildlife.commission(w)
    lead = next(s for s in seasons.SIGHTS if s.id == ep["sight"])
    assert lead.note in wildlife.brief_for(w, "{w1}")
    assert lead.note not in wildlife.brief_for(w, "{w2}") and lead.note not in wildlife.for_prompt(w)
    for k in range(12):
        w.archive.append({"date": w.last_date, "show": "tideline", "type": "links", "headline": f"h{k}",
                          "text": f"said number {k}", "aired": False, "ts": 0})
    said = wildlife.for_prompt(w)
    assert "said number 0" in said and "said number 11" in said


def test_good_evening_and_tonight_become_daytime_words(channel, monkeypatch):
    from newsroom.models import Line
    w = _world()
    _stub(monkeypatch)
    wildlife.commission(w)
    seg = Segment(slot_id=3, type=T.links, show="tideline", brief="{open}", target_s=45, part="open")
    seg.lines = [Line(speaker="naturalist", text="Good evening, and welcome to Tideline."),
                 Line(speaker="naturalist", text="The tide is making slowly tonight, this evening.")]
    wildlife.after(seg, w)
    assert [l.text for l in seg.lines] == ["Hello, and welcome to Tideline.",
                                           "The tide is making slowly today, today."]


@pytest.mark.parametrize("sight", [s for s in seasons.SIGHTS if s.creature], ids=lambda s: s.id)
def test_every_sight_in_the_list_goes_through_the_real_path(sight, channel, monkeypatch):
    """Only the egret and the roost went through the scratch runs: every sight's briefs, its place, the template, the
    hide in both shots (a flock always wide) and a frame drawn through scenes.render."""
    pygame.font.init()
    w = _world(f"2026-{sight.months[0]:02d}-20" if sight.months[0] >= 7 else f"2027-{sight.months[0]:02d}-20")
    monkeypatch.setattr(wildlife, "pick", lambda world, today=None: (sight, None))
    _stub(monkeypatch)
    ep = wildlife.commission(w)
    assert ep["sight"] == sight.id and (ep["count"] is None) == (sight.count is None)
    _stub(monkeypatch, fail=True)
    for tok, kind in (("{open}", T.links), ("{w1}", T.links), ("{w2}", T.links), ("{m1}", T.interview),
                      ("{x1}", T.links), ("{close}", T.links)):
        assert wildlife.brief_for(w, tok)
        seg = Segment(slot_id=3, type=kind, show="tideline", brief=tok, target_s=60,
                      part={"{open}": "open", "{close}": "close"}.get(tok, ""))
        writers.script_segment(seg, w)
        assert seg.lines and seg.work["location"] == sight.place[0]
        if "hide" in seg.work:
            h = seg.work["hide"]
            assert h["creature"] == sight.creature and h["spot"] == sight.place[1]
            if sight.creature in ("brent", "starlings"):
                assert h["shot"] == "wide"
            for shot in ("close", "wide"):
                v = player.View(mode="field", tod=seg.work["tod"])
                wildlife.view(seg, v, 0)
                v.scene = {**v.scene, "shot": shot}
                scenes.render(pygame.Surface((320, 180)), v, 1.0)


def test_the_planner_sees_earlier_episodes_and_what_tonights_sight_had(channel, monkeypatch):
    """Sights come round about every sixteen days in November; both model runs called the egret night "The Egrets in
    the Pool"."""
    w = _world("2026-11-20")
    egret = next(s for s in seasons.SIGHTS if s.id == "egret")
    w.wildlife["episodes"] = [{"date": "2026-11-04", "sight": "egret", "near": None, "count": 8, "counted": "",
                               "what": egret.what, "aired": True, "title": "The Egrets in the Pool", "close": "",
                               "watches": [{"angle": "the yellow feet stirring the mud", "shot": "close"}],
                               "meets": [{"name": "Gwen Tarrant", "role": "counter"}]}]
    monkeypatch.setattr(wildlife, "pick", lambda world, today=None: (egret, None))
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append(user)
        return _plan()
    monkeypatch.setattr(llm, "complete_json", complete_json)
    wildlife.commission(w)
    assert "The Egrets in the Pool" in seen[0] and "the yellow feet stirring the mud" in seen[0]
    assert "HAS BEEN ON BEFORE" in seen[0]


def test_a_resident_the_town_knows_keeps_their_own_role(channel, monkeypatch):
    """The second model run's plan made Stan Tully a "skipper and retired joiner" over the role the town had."""
    w = _world()
    w.ensure_person("Eamon Trask", "retired keeper of the Greymouth light", "resident", gender="m", age="old")
    _stub(monkeypatch)
    ep = wildlife.commission(w)
    assert w.person_by_name("Eamon Trask").role == "retired keeper of the Greymouth light"
    assert next(m for m in ep["meets"] if m["name"] == "Eamon Trask")["role"] == "retired keeper of the Greymouth light"
