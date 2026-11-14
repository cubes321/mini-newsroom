"""The soap engine (entertainment/soap.py) playing Marina Row: an episode planned in the back office, its scenes
written to the plan, and nothing of its fiction reaching the town. The model is stubbed: no network."""
from __future__ import annotations

import time
from datetime import date, timedelta

import pytest

import entertainment
from entertainment import soap
from entertainment.marina_row import MARINA_ROW as M
from newsroom import llm, locations, player, scenes, schedule, talk, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T

CHARS = list(M.characters)


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


@pytest.fixture
def channel():
    undo = entertainment.use()
    yield
    undo()


def _arc():
    return soap.Arc.model_validate({"turning_point": "Queenie finds the letter in episode 4", "storylines": [
        {"name": "The pontoon", "characters": ["Davey Kernick", "Tristan Lockwood"],
         "beats": [f"pontoon beat {i}" for i in range(soap.ARC_EPISODES)]},
        {"name": "Kerra's secret", "characters": ["Kerra Kernick", "Queenie Kernick"],
         "beats": [f"secret beat {i}" for i in range(soap.ARC_EPISODES)]}]})


def _episode(**kw):
    sets = ["marina_mermaid", "marina_loft", "marina_kitchen", "marina_row", "marina_mermaid", "marina_row"]
    who = [["Sal Annear", "Davey Kernick"], ["Harriet Lockwood", "Kerra Kernick"],
           ["Queenie Kernick", "Davey Kernick", "Kerra Kernick"], ["Davey Kernick", "Tristan Lockwood"],
           ["Sal Annear", "Queenie Kernick"], ["Queenie Kernick", "Harriet Lockwood"]]
    return soap.Episode.model_validate({
        "title": "The Apron", "cliffhanger": "Will Queenie tell Davey?", "last_line": "Not one word to your father.",
        "said_by": "Queenie Kernick", "summary": "Davey hears of the petition; Queenie sees Kerra at The Loft.",
        "scenes": [{"set": s, "characters": w, "knows": "nobody knows yet", "beats": f"beat of scene {i + 1}",
                    "ends_on": f"end of scene {i + 1}"} for i, (s, w) in enumerate(zip(sets, who))],
        "spares": [{"set": "marina_mermaid", "characters": ["Sal Annear", "Tristan Lockwood"], "knows": "nothing new",
                    "beats": f"spare beat {i + 1}", "ends_on": "a laugh"} for i in range(5)], **kw})


def _stub(monkeypatch, scene=None, fail=False):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, schema, system, user))
        if fail:
            raise llm.LLMError("down")
        if schema is soap.Arc:
            return _arc()
        if schema is soap.Episode:
            return _episode()
        return scene(schema)
    monkeypatch.setattr(llm, "complete_json", complete_json)
    return seen


def test_marina_row_follows_wits_bare_and_never_wraps_onto_a_scene(channel):
    assert schedule.show_at(_at(20, 25)).id == "marina" and schedule.show_end(_at(20, 25)) == _at(20, 40)
    sh = schedule.get("marina")
    loop = [sh.item(pos) for pos in range(soap.SCENES, soap.SCENES + 16)]         # the spare minutes, four laps
    briefs = [it.brief for it in loop if it.type is T.interview]
    assert all(b.startswith("{x") for b in briefs) and len(set(briefs)) == len(briefs) == 12   # never one twice
    assert [it.type for it in loop[:4]] == [T.interview] * 3 + [T.ad_break]           # three side scenes, a break
    assert sh.closing[0].brief == "{s%d}" % soap.SCENES                   # the cliffhanger lands at the end
    assert "marina" in player.BARE_SHOWS and "marina" in writers.FICTION_SHOWS and player.SEATS["marina"] == 3
    assert world_mod.PINNED_VOICES["Queenie Kernick"] == ("bf_trethowan", 1.0, "b")
    assert scenes.PINNED_LOOKS["Sal Annear"] == M.characters["Sal Annear"].look


def test_undo_leaves_no_soap_behind():
    undo = entertainment.use()
    undo()
    assert not world_mod.PINNED_VOICES and not scenes.PINNED_LOOKS
    assert "marina" not in player.BARE_SHOWS and "marina" not in writers.FICTION_SHOWS
    assert "marina" not in schedule.SHOWS and "marina_row" not in locations.BY_ID


def test_an_episode_is_planned_once_and_its_actors_join_the_town_not_its_characters(channel, monkeypatch):
    w = world_mod.seed()
    seen = _stub(monkeypatch)
    ep = soap.commission(w, M)
    assert [s[1] for s in seen] == [soap.Arc, soap.Episode] and seen[0][0] == soap.TASK
    assert not ep["stand_in"] and ep["number"] == 1 and soap.booked(w, M) is ep
    assert "THE FIRST ARC" in seen[0][3] and "nothing yet" in seen[1][3]
    for p in M.cast:
        assert w.person_by_name(p.character) is None                       # fiction
        actor = w.person_by_name(p.actor)
        assert actor is not None and actor.voice == p.voice and "Marina Row" in actor.role


def test_a_plan_that_names_a_stranger_or_a_set_we_dont_have_gives_way_to_the_stand_in(channel, monkeypatch):
    w = world_mod.seed()
    bad = _episode()
    bad.scenes[2].characters = ["Queenie Kernick", "Helen Strand"]          # a real resident in the fiction
    monkeypatch.setattr(llm, "complete_json", lambda task, schema, *a, **k: _arc() if schema is soap.Arc else bad)
    ep = soap.commission(w, M)
    assert ep["stand_in"] and ep["title"] == M.stand_in[0] and len(ep["scenes"]) == soap.SCENES


def test_the_last_scene_carries_the_cliffhanger_line_and_each_scene_its_place(channel, monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch)
    soap.commission(w, M)
    first = soap.brief_for(w, M, "{s1}")
    assert "The Mermaid" in first and "Sal Annear, Davey Kernick" in first and "beat of scene 1" in first
    last = soap.brief_for(w, M, "{s6}")
    assert "LAST scene" in last and "Not one word to your father." in last


def _scene_reply(lines):
    def reply(schema):
        return schema.model_validate({"headline": "Davey hears about the pontoon", "lower_third": "Marina Row",
                                      "thread_id": None, "lines": lines})
    return reply


def test_a_scene_leaves_the_town_as_it_was(channel, monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch)
    soap.commission(w, M)
    people, headlines = len(w.people), list(w.headlines)
    _stub(monkeypatch, _scene_reply([
        {"speaker": "guest", "guest_name": "Sal Annear", "text": "You've heard, then.",
         "guest_memory": "x"},
        {"speaker": "guest", "guest_name": "Davey Kernick", "text": "Heard what?"},
        {"speaker": "guest", "guest_name": "Sal Annear", "text": "The petition. Your moorings, Davey."},
        {"speaker": "guest", "guest_name": "Davey Kernick", "text": "Over my dead body."}]))
    seg = Segment(slot_id=3, type=T.interview, show="marina", brief="{s1}", target_s=170)
    writers.script_segment(seg, w)
    assert [l.guest_name for l in seg.lines] == ["Sal Annear", "Davey Kernick", "Sal Annear", "Davey Kernick"]
    assert seg.work["set"] == "marina_mermaid" and seg.work["seats"] == ["Sal Annear", "Davey Kernick"]
    assert len(w.people) == people and w.headlines == headlines and seg.thread_id is None
    entry = w.archive[-1]
    assert entry["fiction"] and entry["text"] == "" and entry["people"] == [] and "guest" not in entry
    assert w.search_archive("petition moorings Davey") == []
    assert "Sal Annear" in soap.tonight(w, M)["written"]["0"]              # the scenes after it see what it said


def test_with_the_model_down_a_scene_is_still_tonights_people_and_the_town_is_untouched(channel, monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch)
    soap.commission(w, M)
    people, headlines = len(w.people), list(w.headlines)
    _stub(monkeypatch, fail=True)
    seg = Segment(slot_id=9, type=T.interview, show="marina", brief="{s6}", target_s=170)
    writers.script_segment(seg, w)
    assert {l.guest_name for l in seg.lines} <= {"Queenie Kernick", "Harriet Lockwood"}
    assert seg.lines[-1].text == "Not one word to your father." and seg.lines[-1].guest_name == "Queenie Kernick"
    assert len(w.people) == people and w.headlines == headlines and w.archive[-1]["fiction"]


def test_a_scene_with_someone_who_isnt_in_it_is_not_aired(channel, monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch)
    soap.commission(w, M)
    _stub(monkeypatch, _scene_reply([
        {"speaker": "guest", "guest_name": "Sal Annear", "text": "Evening."},
        {"speaker": "guest", "guest_name": "Davey Kernick", "text": "Evening, Sal."},
        {"speaker": "guest", "guest_name": "Sal Annear", "text": "Usual?"},
        {"speaker": "guest", "guest_name": "Harriet Lockwood", "text": "I'm not in this scene."}]))
    seg = Segment(slot_id=3, type=T.interview, show="marina", brief="{s1}", target_s=170)
    writers.script_segment(seg, w)
    assert "Harriet Lockwood" not in {l.guest_name for l in seg.lines}          # the stand-in scene instead


def test_characters_speak_in_their_actors_voices(channel):
    w = world_mod.seed()
    assert w.voice_for("guest", "Davey Kernick") == "bm_carthew" and w.lang_for("guest", "Davey Kernick") == "b"
    assert w.speed_for("guest", "Davey Kernick") == 1.0 and w.age_for("guest", "Davey Kernick") is None


def test_the_town_talks_about_a_cliffhanger_only_once_its_episode_has_aired(channel, monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch)
    ep = soap.commission(w, M)
    today = date.fromisoformat(w.last_date)
    tomorrow = today + timedelta(days=1)
    assert talk.soap(w, tomorrow) == []                                       # planned, not shown
    w.record_aired("interview", "Queenie sees", None, "", show="marina", brief=ep["last_brief"], fiction=True)
    said = talk.soap(w, tomorrow)
    assert said and "Will Queenie tell Davey?" in said[0] and "Marina Row" in said[0]
    assert "Not one word" not in said[0]                                      # the question, never the line
    assert talk.soap(w, today) == []                                          # tonight's: not yet the town's
    assert "Will Queenie tell Davey?" in talk.line(w, tomorrow)
    w.last_date = tomorrow.isoformat()
    _stub(monkeypatch)
    seen = _stub(monkeypatch)
    soap.commission(w, M)
    assert "THE LAST CLIFFHANGER (answer it tonight): Will Queenie tell Davey?" in seen[-1][3]
    assert "Episode 1" in seen[-1][3]                                          # previously: the aired one


def test_an_aired_episode_stays_aired_when_the_archive_has_moved_on(channel, monkeypatch):
    """The archive keeps about two and a half nights: by the fourth Channel 8 night episode 1 had left it, the arc
    stopped moving on and "previously" forgot it. The last scene going out stamps the episode itself."""
    w = world_mod.seed()
    _stub(monkeypatch)
    ep = soap.commission(w, M)
    assert "marina" in player.AIRED_HOOKS
    player.AIRED_HOOKS["marina"](Segment(slot_id=3, type=T.interview, show="marina", brief="{s2}", target_s=170), w)
    assert not ep.get("aired")                                                # a scene, not the last one
    player.AIRED_HOOKS["marina"](Segment(slot_id=9, type=T.interview, show="marina", brief=ep["last_brief"],
                                         target_s=170), w)
    assert ep["aired"] and w.archive == []                                    # nothing of it in the archive at all
    tomorrow = date.fromisoformat(w.last_date) + timedelta(days=1)
    assert "Will Queenie tell Davey?" in talk.soap(w, tomorrow)[0]
    w.last_date = tomorrow.isoformat()
    seen = _stub(monkeypatch)
    soap.commission(w, M)
    assert "Episode 1" in seen[-1][3] and [s[1] for s in seen] == [soap.Episode]   # previously; the arc is in hand


def test_a_scene_is_drawn_bare_on_its_own_set(channel):
    import pygame
    from newsroom.player import View

    pygame.init()
    v = View(mode="studio", show="marina", set="interview", set_id="marina_kitchen", bare=True,
             people=[("guest", "Queenie Kernick"), ("guest", "Kerra Kernick")], speaker="guest",
             guest_name="Queenie Kernick", lower_third=("Queenie Kernick", "Port Wexley"), ticker=["x"])
    assert scenes._interview_set(v) == "marina_kitchen"
    marks = scenes._interview_marks(v)
    assert [m[2] for m in marks] == [M.sets["marina_kitchen"][2]["a"], M.sets["marina_kitchen"][2]["b"]]
    canvas = pygame.Surface((320, 180))
    scenes.render(canvas, v, 1.0)                                             # no lower third, ticker or clock to fail


def test_a_scene_that_starts_before_its_slot_is_still_bare_on_its_set_with_its_cast_seated(channel, monkeypatch):
    """The model-off scratch run (2026-11-13): Wits came in short, the soap began at 20:18, and its scenes wore the
    quiz's captions and ticker, because the view took 'bare' from the show scheduled that minute."""
    from newsroom.buffer import Buffer
    from newsroom.models import Line
    from newsroom.player import Player

    w = world_mod.seed()
    monkeypatch.setattr(schedule, "now", lambda: _at(20, 18))
    assert schedule.show_at(_at(20, 18)).id == "wits"
    pl = Player(Buffer(), w, producer=None, audio=False)
    seg = Segment(slot_id=4, type=T.interview, show="marina", brief="{s1}", target_s=170, headline="Davey hears",
                  work={"set": "marina_mermaid", "seats": ["Sal Annear", "Davey Kernick"]},
                  lines=[Line(speaker="guest", text="Heard, then?", guest_name="Sal Annear", duration_s=2.0,
                              mouth_env=[0.5] * 40),
                         Line(speaker="guest", text="Heard what?", guest_name="Davey Kernick", duration_s=2.0,
                              mouth_env=[0.5] * 40)])
    pl.current, pl.line_idx = seg, 0
    pl.seg_start = pl.line_start = _at(20, 18) - 0.5
    v = pl.view()
    assert v.bare and v.set_id == "marina_mermaid" and v.show == "marina"
    assert v.people == [("guest", "Sal Annear"), ("guest", "Davey Kernick")]
    pl._start(seg, _at(20, 18))
    assert all(show != "marina" for show, _ in pl.ticker)                    # its headlines never join the ticker


def test_spare_minutes_go_to_side_scenes_then_quiet_moments_never_a_planned_scene_again(channel, monkeypatch):
    """The model-off scratch run (2026-11-13): five short scenes in a minute, then adverts for twenty until the
    cliffhanger. Spare minutes are side scenes now, three to a break; past the plan's, a quiet moment in the pub."""
    w = world_mod.seed()
    _stub(monkeypatch)
    soap.commission(w, M)
    spare = soap.brief_for(w, M, "{x2}")
    assert "SHORT SIDE SCENE" in spare and "spare beat 2" in spare and "LAST scene" not in spare
    quiets = [soap.brief_for(w, M, "{x%d}" % k) for k in (6, 7, 8)]          # the plan gave five
    assert all("quiet moment" in q for q in quiets) and len({q.split(". In it:")[0] for q in quiets}) == 3
    _stub(monkeypatch, fail=True)
    seg = Segment(slot_id=12, type=T.interview, show="marina", brief="{x3}", target_s=100)
    writers.script_segment(seg, w)
    assert {l.guest_name for l in seg.lines} <= {"Sal Annear", "Tristan Lockwood"} and seg.work["set"] == "marina_mermaid"
    assert "x2" in soap.tonight(w, M)["written"]
