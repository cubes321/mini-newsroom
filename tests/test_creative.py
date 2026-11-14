"""Channel 8's creative editor (entertainment/creative.py): a review after each programme has aired, notes for the
next planner, a ledger, and plans sent back once before air. The model is stubbed: no network."""
from __future__ import annotations

import json
import time
from datetime import date, timedelta

import pytest

import entertainment
from entertainment import creative, kettle, quiz, soap, travelogue, wildlife
from newsroom import llm, schedule, workers, world as world_mod
from newsroom.config import CONFIG
from test_soap import M, _arc, _episode
from test_wildlife import _plan


def _at(h, m=0, day: str | None = None):
    lt = time.localtime()
    y, mo, d = (int(x) for x in day.split("-")) if day else (lt.tm_year, lt.tm_mon, lt.tm_mday)
    return time.mktime((y, mo, d, h, m, 0, 0, 0, -1))


@pytest.fixture
def channel():
    undo = entertainment.use()
    yield
    undo()


@pytest.fixture
def editor(monkeypatch, channel):
    """An editor to ask (the tests run with the models off), at six in the evening, well before air."""
    monkeypatch.setattr(creative, "_on", lambda: True)
    monkeypatch.setattr(schedule, "now", lambda: _at(18, 0))
    monkeypatch.setattr(creative, "_quiet_until", 0.0)


def _review(**kw):
    return creative.Review.model_validate({
        "mark": "fair", "verdict": "The petition moved; Kerra's secret stood still.",
        "notes": ["Move Kerra's secret on: Queenie must act on what she saw."],
        "series_notes": ["Bring the turning point forward an episode."], "remarks": ["Davey shouts in every scene."],
        "told": ["Sal's joke about the bins"], "established": ["Davey's moorings are on the south pontoon"],
        "planted": ["Queenie saw Kerra at The Loft and has told nobody"], "paid_off": [], **kw})


def _stub(monkeypatch, *, verdicts=(), review=None, second=None, fail=None):
    """Arc and Episode as test_soap's; a Verdict from `verdicts` in turn (passing once they run out); a second
    Episode, after one was sent back, is `second` (or one titled "The Second Draft"). `fail` is {schema: "down" (the
    call fails) or "gone" (its model can't be reached)}."""
    seen, queue, fail = [], list(verdicts), fail or {}

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, schema, system, user, kw))
        if schema in fail:
            raise llm.LLMUnavailable("no key") if fail[schema] == "gone" else llm.LLMError("down")
        if schema is soap.Arc:
            return _arc()
        if schema is soap.Episode:
            again = sum(1 for s in seen if s[1] is soap.Episode) > 1
            return (second or _episode(title="The Second Draft")) if again else _episode()
        if schema is wildlife.WildEpisode:
            return _plan()
        if schema is creative.Verdict:
            return queue.pop(0) if queue else creative.Verdict(ok=True)
        if schema is creative.Review:
            return review or _review()
        raise AssertionError(f"unexpected call for {schema}")
    monkeypatch.setattr(llm, "complete_json", complete_json)
    return seen


def _aired_episode(w, monkeypatch, words=True):
    """Tonight's Marina Row, planned and aired: its last scene stamped, two scenes in the archive, their words in
    the cache."""
    _stub(monkeypatch)
    monkeypatch.setattr(creative, "_on", lambda: False)        # planned before there was an editor to read it
    ep = soap.commission(w, M)
    monkeypatch.setattr(creative, "_on", lambda: True)
    ep["aired"] = True
    CONFIG.paths.cache.mkdir(parents=True, exist_ok=True)
    for h, brief, lines in (("c1", "{s1}", [("Sal Annear", "You've heard, then."), ("Davey Kernick", "Heard what?")]),
                            ("c6", "{s6}", [("Queenie Kernick", "Not one word to your father.")])):
        w.record_aired("interview", f"scene {brief}", None, "", show="marina", brief=brief, content_hash=h, fiction=True)
        path = CONFIG.paths.cache / f"{h}.json"
        path.unlink(missing_ok=True)
        if words:
            path.write_text(json.dumps({"lines": [{"speaker": "guest", "guest_name": n, "text": t} for n, t in lines]}),
                            encoding="utf-8")
    return ep


# ------------------------------------------------------------------ the registry

def test_the_programmes_enrol_and_the_undo_leaves_nothing(channel):
    assert set(creative.SHOWS) == {"marina", "tideline", "coastroad", "kettle", "wits"}
    assert {k for k, e in creative.SHOWS.items() if e.vetted} == {"marina", "tideline", "coastroad"}
    assert workers.IDLE_JOBS[0][0] is creative.urgent_due and workers.IDLE_JOBS[-1][0] is creative.later_due


def test_undo_takes_the_editor_off_again():
    before = list(workers.IDLE_JOBS)
    undo = entertainment.use()
    undo()
    assert creative.SHOWS == {} and workers.IDLE_JOBS == before


def test_with_the_models_off_there_is_no_editor_and_nothing_is_asked(channel, monkeypatch):
    w = world_mod.seed()
    seen = _stub(monkeypatch)
    soap.commission(w, M)
    assert [s[1] for s in seen] == [soap.Arc, soap.Episode]            # no Verdict: the planners run as they did
    assert not creative.later_due(w) and creative.review(w, "marina", w.last_date) is None
    assert w.creative == {} or not w.creative.get("log")


def test_the_editors_record_is_saved_with_the_town(editor, monkeypatch):
    w = world_mod.seed()
    _aired_episode(w, monkeypatch)
    _stub(monkeypatch)
    creative.review(w, "marina", w.last_date)
    back = world_mod._from_dict(json.loads(json.dumps(world_mod._to_dict(w))))
    assert back.creative["notes"]["marina"]["items"] == ["Move Kerra's secret on: Queenie must act on what she saw."]


# ------------------------------------------------------------------ after air

def test_a_review_reads_the_plan_and_the_words_that_went_out_and_keeps_what_it_makes_of_them(editor, monkeypatch):
    w = world_mod.seed()
    _aired_episode(w, monkeypatch)
    seen = _stub(monkeypatch)
    r = creative.review(w, "marina", w.last_date)
    task, schema, system, user, kw = seen[-1]
    assert task == creative.TASK and schema is creative.Review and kw["max_tokens"] == creative.MAX_TOKENS
    assert "THE PROGRAMME: Marina Row (fiction)" in user and "THE PLANNER DECIDES" in user
    assert "\"The Apron\"" in user and "beat of scene 3" in user and "THE ARC it follows" in user      # the plan
    assert "Sal Annear: You've heard, then." in user and "Queenie Kernick: Not one word" in user        # the words
    assert r.mark == "fair"
    c = w.creative
    assert c["notes"]["marina"] == {"date": w.last_date, "items": list(r.notes), "series": list(r.series_notes)}
    led = c["ledger"]["marina"]
    assert led["open"] == [{"planted": w.last_date, "what": "Queenie saw Kerra at The Loft and has told nobody"}]
    assert led["facts"][0]["what"].startswith("Davey's moorings") and led["told"][0]["what"] == "Sal's joke about the bins"
    entry = c["log"][-1]
    assert entry["mark"] == "fair" and entry["words"] and entry["remarks"] == ["Davey shouts in every scene."]
    assert "Davey shouts" in creative.report(w) and "still open" in creative.report(w)


def test_what_a_later_episode_pays_off_leaves_the_ledger_and_long_notes_wait_for_the_next_arc(editor, monkeypatch):
    w = world_mod.seed()
    _aired_episode(w, monkeypatch)
    _stub(monkeypatch)
    creative.review(w, "marina", w.last_date)
    tomorrow = (date.fromisoformat(w.last_date) + timedelta(days=1)).isoformat()
    seen = _stub(monkeypatch, review=_review(paid_off=[1, 7], planted=["Tristan has the letter"], series_notes=[],
                                             notes=[]))
    creative._apply(w, creative.SHOWS["marina"], tomorrow, creative.Review.model_validate(
        {"mark": "good", "verdict": "Paid off.", "paid_off": [1, 7], "planted": ["Tristan has the letter"]}), True)
    led = w.creative["ledger"]["marina"]
    assert [t["what"] for t in led["open"]] == ["Tristan has the letter"]          # number 1 gone; 7 was never there
    assert w.creative["notes"]["marina"]["series"] == ["Bring the turning point forward an episode."]
    assert w.creative["notes"]["marina"]["items"] == [] and not seen


def test_with_the_words_gone_it_judges_the_plan_alone(editor, monkeypatch):
    w = world_mod.seed()
    _aired_episode(w, monkeypatch, words=False)
    seen = _stub(monkeypatch)
    creative.review(w, "marina", w.last_date)
    assert "THE WORDS WERE NOT KEPT" in seen[-1][3] and "WHAT WENT OUT" not in seen[-1][3]
    assert w.creative["log"][-1]["words"] is False


def test_a_stand_in_night_is_not_the_planners_work_and_is_not_reviewed(editor, monkeypatch):
    w = world_mod.seed()
    ep = _aired_episode(w, monkeypatch)
    ep["stand_in"] = True
    seen = _stub(monkeypatch)
    assert creative.review(w, "marina", w.last_date) is None and not seen
    assert w.creative["log"][-1]["mark"] == "" and not creative._pending(w, _at(21, 5))    # and not asked again


def test_a_review_is_owed_only_once_the_programme_has_aired_and_is_over(editor, monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch)
    ep = soap.commission(w, M)                                           # planned; the station never got to it
    assert not creative.later_due(w, _at(21, 5))
    ep["aired"] = True
    assert not creative.later_due(w, _at(20, 30))                        # still on the air
    w.record_aired("interview", "side scene", None, "", show="marina", brief="{x1}", aired=False, fiction=True)
    assert not creative.later_due(w, _at(21, 5))                         # a scene written and still waiting
    w.drop_unaired()
    assert creative.later_due(w, _at(21, 5))
    monkeypatch.setattr(schedule, "now", lambda: _at(21, 5))
    creative.review_later(w)
    assert w.creative["log"][-1]["show"] == "marina" and not creative.later_due(w, _at(21, 10))


def test_a_review_that_fails_is_not_asked_again_at_once_and_a_model_out_of_reach_quiets_the_editor(channel, monkeypatch):
    monkeypatch.setattr(schedule, "now", lambda: _at(21, 5))
    w = world_mod.seed()
    _aired_episode(w, monkeypatch)
    monkeypatch.undo()                                                   # the real _on, with a model routed
    monkeypatch.setattr(llm, "provider_for", lambda task: "claude_sonnet")
    monkeypatch.setattr(creative, "_quiet_until", 0.0)
    _stub(monkeypatch, fail={creative.Review: "down"})
    assert creative.later_due(w, _at(21, 5))
    assert creative.review(w, "marina", w.last_date) is None
    assert not creative.later_due(w, _at(21, 6)) and not w.creative["log"]      # tried; not due again for a while
    w.creative["tried"].clear()
    _stub(monkeypatch, fail={creative.Review: "gone"})
    assert creative.review(w, "marina", w.last_date) is None
    assert not creative._on() and not creative.later_due(w, _at(21, 7))         # quiet for the hour


def test_a_missed_night_is_caught_up_before_the_booking_that_needs_its_notes(editor, monkeypatch):
    w = world_mod.seed()
    last_night = (date.fromisoformat(w.last_date) - timedelta(days=2)).isoformat()
    today, w.last_date = w.last_date, last_night
    _aired_episode(w, monkeypatch)
    w.last_date = today
    assert not creative.urgent_due(w, _at(18, 0))                        # the soap books from 18:30
    assert creative.later_due(w, _at(18, 0))                             # owed all the same, behind the bookings
    monkeypatch.setattr(schedule, "now", lambda: _at(20, 0))
    assert not creative.urgent_due(w, _at(20, 0))                        # too close to air to hold the booking
    monkeypatch.setattr(schedule, "now", lambda: _at(18, 35))
    assert creative.urgent_due(w, _at(18, 35))
    _stub(monkeypatch)
    creative.review_urgent(w)
    assert w.creative["log"][-1]["date"] == last_night and not creative.urgent_due(w, _at(18, 36))


def test_a_programmes_own_callable_that_raises_never_reaches_the_worker(editor, monkeypatch):
    w = world_mod.seed()

    def boom(*a):
        raise RuntimeError("its record is in an older shape")
    undo = creative.register("odd", "Odd", kind="light", brief="x", airs_at="19:00", digest=boom, aired=boom, books=boom)
    try:
        assert creative.later_due(w, _at(21, 5)) is False and creative.urgent_due(w, _at(18, 0)) is False
        assert creative.review(w, "odd", w.last_date) is None
    finally:
        undo()


def test_the_ledger_and_the_log_are_bounded(editor):
    w = world_mod.seed()
    e = creative.SHOWS["kettle"]
    for i in range(70):
        creative._apply(w, e, w.last_date, creative.Review.model_validate(
            {"mark": "good", "verdict": "Fine.", "told": [f"story {i}"], "established": [f"fact {i}"],
             "planted": [f"thread {i}"]}), True)
    led = w.creative["ledger"]["kettle"]
    assert (len(led["told"]), len(led["facts"]), len(led["open"])) == (40, 40, 12) and led["told"][-1]["what"] == "story 69"
    assert len(w.creative["log"]) == creative.KEPT["log"]


def test_overlong_replies_are_cut_not_failed():
    r = creative.Review.model_validate({"mark": "weak", "verdict": "x" * 900, "notes": [f"note {i}" for i in range(9)],
                                        "told": ["y " * 400]})
    assert len(r.verdict) <= 300 and len(r.notes) == 4 and len(r.told[0]) <= 140


# ------------------------------------------------------------------ into the planners' prompts

def test_notes_reach_each_planner_and_no_live_writer(editor, monkeypatch):
    from newsroom import writers

    w = world_mod.seed()
    w.last_date = "2026-11-20"
    for sid in ("marina", "tideline", "kettle", "wits", "coastroad"):
        creative._apply(w, creative.SHOWS[sid], "2026-11-18", creative.Review.model_validate(
            {"mark": "fair", "verdict": "So-so.", "notes": [f"a note for {sid}"], "series_notes": [f"a long note for {sid}"],
             "established": [f"a fact from {sid}"], "told": [f"told on {sid}"], "planted": [f"open on {sid}"]}), True)
    seen = _stub(monkeypatch)
    monkeypatch.setattr(schedule, "now", lambda: _at(18, 0, "2026-11-20"))
    soap.commission(w, M)
    arc, episode = (next(s[3] for s in seen if s[1] is k) for k in (soap.Arc, soap.Episode))
    assert "a long note for marina" in arc and "a note for marina" not in arc
    assert "THE CREATIVE EDITOR'S NOTES" in episode and "a note for marina" in episode
    assert "STILL OPEN" in episode and "open on marina" in episode and "a fact from marina" in episode
    wildlife.commission(w)
    tide = next(s[3] for s in seen if s[1] is wildlife.WildEpisode)
    assert "a note for tideline" in tide and "told on tideline" in tide and "STILL OPEN" not in tide
    assert tide.index("BRIEFING") < tide.index("THE CREATIVE EDITOR'S NOTES")       # after the cached briefing

    def other(task, schema, system, user, **kw):
        seen.append((task, schema, system, user, kw))
        raise llm.LLMError("only the prompt is wanted")
    monkeypatch.setattr(llm, "complete_json", other)
    kettle.commission(w), quiz.commission(w), travelogue.plan_route(w)
    by = {s[1]: s[3] for s in seen}
    assert "a note for kettle" in by[kettle.KettleBooking] and "told on kettle" not in by[kettle.KettleBooking]
    assert "a note for wits" in by[quiz.QuizBooking]
    assert "a long note for coastroad" in by[travelogue.Route] and "a note for coastroad" not in by[travelogue.Route]
    assert all("CREATIVE EDITOR" not in (hook(w) or "") for sid, hook in writers.PROMPT_HOOKS.items()
               if sid in ("kettle", "wits"))                                        # never every item's prompt


def test_notes_grow_stale_and_no_notes_leaves_a_prompt_as_it_was(editor):
    w = world_mod.seed()
    w.last_date = "2026-11-20"
    assert creative.for_planner(w, "kettle") == "" and creative.for_planner(w, "marina", series=True) == ""
    creative._apply(w, creative.SHOWS["kettle"], "2026-10-20", creative.Review.model_validate(
        {"mark": "fair", "verdict": "So-so.", "notes": ["a month old"]}), True)
    assert creative.for_planner(w, "kettle") == ""


# ------------------------------------------------------------------ before air

def test_a_plan_is_sent_back_once_and_the_second_draft_airs(editor, monkeypatch):
    w = world_mod.seed()
    seen = _stub(monkeypatch, verdicts=[creative.Verdict(ok=True),
                                        creative.Verdict(ok=False, notes=["Scene 4: Davey already knows; start there."])])
    ep = soap.commission(w, M)
    assert [s[1] for s in seen] == [soap.Arc, creative.Verdict, soap.Episode, creative.Verdict, soap.Episode]
    assert seen[1][0] == creative.TASK and "has drafted the arc below" in seen[1][2] and "pontoon beat 0" in seen[1][3]
    again = seen[-1][3]
    assert "THE CREATIVE EDITOR SENT IT BACK, once" in again and "Davey already knows" in again and "\"The Apron\"" in again
    assert ep["title"] == "The Second Draft" and not ep["stand_in"]
    assert w.creative["vets"] == [{"date": w.last_date, "show": "marina", "what": "episode", "took": "second",
                                   "notes": ["Scene 4: Davey already knows; start there."]}]


def test_a_second_draft_that_fails_the_planners_own_check_gives_way_to_the_first(editor, monkeypatch):
    w = world_mod.seed()
    bad = _episode(title="The Second Draft")
    bad.scenes[2].characters = ["Queenie Kernick", "Helen Strand"]              # a resident in the fiction
    _stub(monkeypatch, second=bad, verdicts=[creative.Verdict(ok=True), creative.Verdict(ok=False, notes=["Tighter."])])
    ep = soap.commission(w, M)
    assert ep["title"] == "The Apron" and not ep["stand_in"] and w.creative["vets"][-1]["took"] == "first"


def test_tidelines_plan_is_read_too(editor, monkeypatch):
    w = world_mod.seed()
    w.last_date = "2026-11-20"
    monkeypatch.setattr(schedule, "now", lambda: _at(18, 35, "2026-11-20"))
    seen = _stub(monkeypatch, verdicts=[creative.Verdict(ok=False, notes=["Sequence 2 repeats sequence 1."])])
    wildlife.commission(w)
    assert [s[1] for s in seen] == [wildlife.WildEpisode, creative.Verdict, wildlife.WildEpisode]
    vet = seen[1][3]
    assert "THE DRAFT EPISODE" in vet and "Back on the Mud" in vet and "BRIEFING" not in vet    # not the whole town
    assert w.creative["vets"][-1]["show"] == "tideline"


def test_no_plan_is_read_close_to_air_or_once_the_booking_has_run_long(editor, monkeypatch):
    w = world_mod.seed()
    monkeypatch.setattr(schedule, "now", lambda: _at(19, 55))                  # the soap airs at 20:20
    seen = _stub(monkeypatch, verdicts=[creative.Verdict(ok=False, notes=["x"])] * 2)
    soap.commission(w, M)
    assert [s[1] for s in seen] == [soap.Arc, soap.Episode]
    assert creative.vet(w, "marina", "episode", "a plan", started=time.monotonic() - 300, margin=False) is None
    assert creative.vet(w, "kettle", "booking", "a plan", margin=False) is None      # notes only: never vetted
    assert len(seen) == 2


def test_an_editor_that_cant_be_reached_lets_the_plan_stand(editor, monkeypatch):
    w = world_mod.seed()
    seen = _stub(monkeypatch, fail={creative.Verdict: "down"})
    ep = soap.commission(w, M)
    assert ep["title"] == "The Apron" and not ep["stand_in"] and not w.creative.get("vets")
    assert [s[1] for s in seen].count(creative.Verdict) == 2                   # the arc's and the episode's, each once


def test_a_route_planned_ahead_is_read_whatever_the_clock(editor, monkeypatch):
    w = world_mod.seed()
    monkeypatch.setattr(schedule, "now", lambda: _at(20, 39))
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append(schema)
        raise llm.LLMError("only the calls are wanted")
    monkeypatch.setattr(llm, "complete_json", complete_json)
    assert creative.vet(w, "coastroad", "route", "a route") is None and seen == []      # at air time: not read
    assert creative.vet(w, "coastroad", "route", "a route", margin=False) is None and seen == [creative.Verdict]
