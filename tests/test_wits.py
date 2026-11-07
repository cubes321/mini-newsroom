"""Wexley Wits, the entertainment channel's pub quiz (entertainment/): two darts pubs, four rounds booked
in the back office, every answer drawn and the score kept in code, the script written to the result.
The model is stubbed: no network."""
from __future__ import annotations

import time
from collections import Counter

import pytest

import entertainment
from entertainment import quiz
from newsroom import darts, llm, player, scenes, schedule, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


@pytest.fixture
def channel():
    undo = entertainment.use()
    yield
    undo()


def _q(i, kind):
    return {"question": f"{kind} question number {i}?", "answer": f"{kind} {i}", "difficulty": 1 + i % 3}


def _booking(**kw):
    return quiz.QuizBooking.model_validate({
        "general": [_q(i, "general") for i in range(quiz.PER_ROUND)],
        "local": [_q(i, "local") for i in range(quiz.PER_ROUND)], "news": [_q(i, "news") for i in range(quiz.PER_ROUND)],
        "potluck": [_q(i, "potluck") for i in range(quiz.PER_ROUND)],
        "tiebreak": {"question": "How high is Ben Nevis in metres?", "answer": 1345, "unit": "metres"}, **kw})


def _stub(monkeypatch, reply):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, schema, user))
        if isinstance(reply, Exception):
            raise reply
        return reply(schema) if callable(reply) else reply
    monkeypatch.setattr(llm, "complete_json", complete_json)
    return seen


def test_two_different_pubs_with_their_regulars_and_no_rematch_soon():
    w = world_mod.seed()
    ts = quiz.teams(w)
    assert ts == quiz.teams(w) and ts[0]["pub"] != ts[1]["pub"]          # the same draw all day
    by_pub = {p: (s, list(r)) for p, s, r in darts.PUBS}
    for t in ts:
        assert (t["strength"], t["members"]) == by_pub[t["pub"]] and t["name"][0].isupper()
    w.quizzes = [{"date": "2026-01-01", "teams": ts, "rounds": []}]
    assert {t["pub"] for t in quiz.teams(w)} != {t["pub"] for t in ts}   # met last week: someone else


def test_the_quiz_is_played_in_code_and_the_score_adds_up(monkeypatch):
    w = world_mod.seed()
    seen = _stub(monkeypatch, _booking())
    q = quiz.commission(w)
    assert seen[0][0] == quiz.TASK and "THIS WEEK'S HEADLINES" in seen[0][2] and not q["stand_in"]
    assert quiz.tonight(w) is q and quiz.commission(w) is not q and len(w.quizzes) == 1   # rebooked, not added
    q = quiz.tonight(w)
    score = [0, 0]
    for r in q["rounds"]:
        assert len(r["questions"]) == quiz.PER_ROUND
        assert Counter(x["to"] for x in r["questions"]) == {0: 3, 1: 3}         # three each a round
        for x in r["questions"]:
            assert x["who"] in q["teams"][x["to"]]["members"]
            score[x["to"]] += quiz.OWN_POINTS if x["right"] else 0
            score[1 - x["to"]] += quiz.BONUS_POINTS if x["stolen"] else 0
            assert not (x["right"] and x["stolen"])
        assert r["scores_after"] == score
    assert q["final"][0] != q["final"][1] and q["winner"] == (0 if q["final"][0] > q["final"][1] else 1)
    for name in [*q["teams"][0]["members"], *q["teams"][1]["members"]]:
        assert w.person_by_name(name) and quiz.caption(w, name).startswith(
            next(t["name"] for t in q["teams"] if name in t["members"]))


def test_a_level_score_goes_to_the_tiebreak_nearest_guess_wins():
    ts = [{"pub": "the Lugger", "name": "The Lugger", "members": ["Gav Polglase", "Tracy Hendy"], "strength": 1.0},
          {"pub": "the Pilchard", "name": "The Pilchard", "members": ["Mick Jewell", "Lorraine Oates"],
           "strength": 1.0}]
    ties = 0
    for seed in range(300):
        rounds, final, tie = quiz._play(_booking(), ts, f"s{seed}")
        before = rounds[-1]["scores_after"]
        assert (tie is not None) == (before[0] == before[1])
        if tie:
            ties += 1
            near = [abs(g - 1345) for g in tie["guesses"]]
            assert near[tie["winner"]] < near[1 - tie["winner"]]
            assert final[tie["winner"]] == before[tie["winner"]] + 1 and final[0] != final[1]
    assert ties > 5


def test_the_stronger_pub_gets_more_right():
    strong, weak = ({"members": ["A", "B"], "strength": s, "name": n, "pub": n} for s, n in ((1.15, "S"), (0.85, "W")))
    right = Counter()
    for seed in range(200):
        rounds, *_ = quiz._play(_booking(), [strong, weak], f"x{seed}")
        for r in rounds:
            right.update(x["to"] for x in r["questions"] if x["right"])
    assert right[0] > right[1] * 1.15


def test_with_no_model_the_stand_in_quiz_asks_the_towns_own_facts(monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, llm.LLMError("down"))
    q = quiz.commission(w)
    asked = [x["q"] for r in q["rounds"] for x in r["questions"]]
    assert q["stand_in"] and len(asked) == 24 and len(set(asked)) == 24
    assert any(str(w.founded) == x["a"] for x in q["rounds"][1]["questions"])


def test_a_round_brief_carries_every_question_and_the_score_clive_reads(monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    q = quiz.commission(w)
    two = quiz.brief_for(w, "{r2}")
    for x in q["rounds"][1]["questions"]:
        assert x["q"] in two and x["who"] in two and f"(the answer: {x['a']})" in two
    s = q["rounds"][1]["scores_after"]
    assert f"which Clive reads out exactly: {q['teams'][0]['name']} {s[0]}, {q['teams'][1]['name']} {s[1]}." in two
    close = quiz.brief_for(w, "the RESULT, {close}")
    assert f"{q['teams'][0]['name']} {q['final'][0]}, {q['teams'][1]['name']} {q['final'][1]}" in close
    assert ("THE TIEBREAK" in close) == bool(q["tiebreak"])
    assert quiz.brief_for(w, "{chat2}").startswith(q["teams"][1]["name"].upper())


def test_the_channel_puts_wits_on_at_eight_and_undo_gives_back_channel_seven():
    eight = _at(20, 10)
    before = schedule.show_at(eight).id
    undo = entertainment.use()
    try:
        assert schedule.show_at(eight).id == "wits" and schedule.show_at(_at(20, 40)).id == "overnight"
        assert schedule.show_end(eight) == _at(20, 30)
        assert scenes.SHOW_SETS["wits"] == "pub" and player.SEATS["wits"] == 4
    finally:
        undo()
    assert schedule.show_at(eight).id == before and "wits" not in schedule.SHOWS and "wits" not in writers.BOOKED_SHOWS


def test_a_round_is_written_to_the_booking_on_the_pub_set_and_moves_no_story(channel, monkeypatch):
    w = world_mod.seed()
    news = w.update_thread(None, "Harbour wall tender goes to full council", "the vote is Thursday")
    mentions = w.thread(news).mentions
    q = quiz._record(w, quiz.teams(w), _booking())
    home, away = q["teams"]
    asked = []

    def reply(schema):
        lines = [{"speaker": "mag_b", "text": "Round two!"}]
        for x in q["rounds"][1]["questions"]:
            lines += [{"speaker": "mag_b", "text": x["q"]}, {"speaker": "guest", "guest_name": x["who"], "text": "Hmm."}]
        lines.append({"speaker": "mag_b", "text": "That's the score."})
        return schema.model_validate({"headline": "Harbour wall tender goes to full council", "lower_third": "Wexley Wits",
                                      "thread_id": news, "lines": lines})
    _stub(monkeypatch, lambda schema: asked.append(schema) or reply(schema))
    seg = Segment(slot_id=3, type=T.interview, show="wits", brief="{r2}", target_s=240)
    writers.script_segment(seg, w)
    assert len(asked) == 1 and "panel" in asked[0].__name__.lower()          # one call: no re-asks for regulars
    assert seg.work["seats"] == [*home["members"], *away["members"]]
    captions = {l.guest_name: l.guest_role for l in seg.lines if l.speaker == "guest"}
    assert all(c.startswith((home["name"], away["name"])) for c in captions.values())
    assert seg.thread_id is None and w.thread(news).mentions == mentions        # the news round moves nothing
    system, user = writers.build_prompt(T.interview, w, target_s=240, show=schedule.get("wits"), brief="{r2}")
    assert "WEXLEY WITS, a pub quiz" in system and "THE SCORE AFTER ROUND 2" in user and "THE TEAMS" in user


def test_with_the_model_down_a_round_is_still_tonights_questions_and_score(channel, monkeypatch):
    w = world_mod.seed()
    q = quiz._record(w, quiz.teams(w), _booking())
    _stub(monkeypatch, llm.LLMError("down"))
    seg = Segment(slot_id=4, type=T.interview, show="wits", brief="{r3}", target_s=240)
    writers.script_segment(seg, w)
    said = " ".join(l.text for l in seg.lines)
    s = q["rounds"][2]["scores_after"]
    assert all(x["q"] in said for x in q["rounds"][2]["questions"])
    assert f"{q['teams'][0]['name']} {s[0]}, {q['teams'][1]['name']} {s[1]}" in said
    close = Segment(slot_id=5, type=T.interview, show="wits", part="close", brief="the RESULT, {close}", target_s=110)
    writers.script_segment(close, w)
    assert f"{q['teams'][q['winner']]['name']} win" in " ".join(l.text for l in close.lines)
