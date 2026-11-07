"""Wexley Wits, the entertainment channel's pub quiz (entertainment/): two darts pubs, four rounds booked
in the back office, every answer drawn and the score kept in code, the script written to the result.
The model is stubbed: no network."""
from __future__ import annotations

import time
from collections import Counter

import pytest

import entertainment
from entertainment import oche, quiz
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
        if r["kind"] in quiz.DARTS_ROUNDS:
            a, b = r["totals"]
            assert a == sum(d["points"] for d in r["throws"] if d["to"] == 0)
            if r["kind"] == "doubles":                       # more doubles; level, the higher total
                hits = [sum(d["call"].startswith(("Double", "Bullseye")) for d in r["throws"] if d["to"] == t)
                        for t in (0, 1)]
                assert hits == r["doubles"]
                a, b = hits if hits[0] != hits[1] else (a, b)
            score[0] += 1 if a == b else oche.POINTS if a > b else 0
            score[1] += 1 if a == b else oche.POINTS if b > a else 0
            assert r["scores_after"] == score
            continue
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
            right.update(x["to"] for x in r.get("questions", []) if x["right"])
    assert right[0] > right[1] * 1.15


def test_with_no_model_the_stand_in_quiz_asks_the_towns_own_facts(monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, llm.LLMError("down"))
    q = quiz.commission(w)
    asked = [x["q"] for r in q["rounds"] for x in r.get("questions", [])]
    assert q["stand_in"] and len(asked) == 30 and len(set(asked)) == 30
    assert any(str(w.founded) == x["a"] for x in q["rounds"][1]["questions"])


def test_a_round_brief_carries_every_question_and_the_score_clive_reads(monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    q = quiz.commission(w)
    two = quiz.brief_for(w, "{r2}")
    for x in q["rounds"][1]["questions"]:
        assert x["q"] in two and x["who"] in two and f"(the answer: {x['a']})" in two
    s = q["rounds"][1]["scores_after"]
    assert f"for Clive to read out: {q['teams'][0]['name']} {s[0]}, {q['teams'][1]['name']} {s[1]}." in two
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
    _, close = writers.build_prompt(T.interview, w, target_s=110, show=schedule.get("wits"), part="close",
                                    brief="the RESULT, {close}", at_ts=_at(20, 28))
    assert "that's all for tonight" in close and "Port Wexley News" not in close   # the test card follows


def test_with_the_model_down_a_round_is_still_tonights_questions_and_score(channel, monkeypatch):
    w = world_mod.seed()
    q = quiz._record(w, quiz.teams(w), _booking())
    _stub(monkeypatch, llm.LLMError("down"))
    seg = Segment(slot_id=4, type=T.interview, show="wits", brief="{r4}", target_s=240)
    writers.script_segment(seg, w)
    said = " ".join(l.text for l in seg.lines)
    s = q["rounds"][3]["scores_after"]
    assert all(x["q"] in said for x in q["rounds"][3]["questions"])
    assert f"{q['teams'][0]['name']} {s[0]}, {q['teams'][1]['name']} {s[1]}" in said
    close = Segment(slot_id=5, type=T.interview, show="wits", part="close", brief="the RESULT, {close}", target_s=110)
    writers.script_segment(close, w)
    assert f"{q['teams'][q['winner']]['name']} win" in " ".join(l.text for l in close.lines)


def test_a_quiz_round_is_never_offered_a_return_guest(channel, monkeypatch):
    """The scratch run's quiz prompts carried 19 "A RETURN VISIT" offers: Wits is a light show, and a
    light show's interview may book back a guest with a loose end. A quiz's guests are its teams."""
    from test_guest_followups import _remembered_town

    w = _remembered_town()
    hollis = w.person_by_name("Hollis Byrne")
    for end in hollis.loose_ends:
        end["ts"] -= world_mod.RETURN_RIPE_S                     # ripe: a day old
    assert w.return_guests()
    q = quiz._record(w, quiz.teams(w), _booking())
    seen = _stub(monkeypatch, llm.LLMError("down"))
    writers.script_segment(Segment(slot_id=6, type=T.interview, show="wits", brief="{r1}", target_s=240), w)
    assert seen and all("A RETURN VISIT" not in user for _, _, user in seen)


def test_the_board_scores_a_dart_by_where_it_lands():
    assert oche.score_at(0, 0) == (50, "Bullseye!") and oche.score_at(0, 12)[0] == 25
    assert oche.score_at(0, 103) == (60, "Treble twenty!") and oche.score_at(0, 166) == (40, "Double twenty!")
    assert oche.score_at(0, 60) == (20, "Twenty.") and oche.score_at(0, 200) == (0, "No score.")
    assert oche.score_at(0, 240) == (0, "Off the board!")                          # past the number ring
    assert oche.score_at(40, 120)[0] == 1 and oche.score_at(-40, 120)[0] == 5      # either side of the twenty
    assert oche.score_at(0, -103) == (9, "Treble three!")                            # the three, at the bottom
    assert oche.words(66) == "sixty-six" and oche.words(112) == "one hundred and twelve"


def test_every_dart_is_thrown_in_code_and_the_better_pub_scores_more():
    ts = [{"name": "S", "pub": "S", "members": ["A", "B"], "strength": 1.15},
          {"name": "W", "pub": "W", "members": ["C", "D"], "strength": 0.85}]
    import random
    throws, totals = oche.play(random.Random(1), ts)
    assert [d["who"] for d in throws] == ["A"] * 3 + ["C"] * 3 + ["B"] * 3 + ["D"] * 3       # captains first
    assert all(oche.score_at(d["x"], d["y"])[0] == d["points"] for d in throws)
    assert totals == [sum(d["points"] for d in throws if d["to"] == t) for t in (0, 1)]
    won = sum(oche.play(random.Random(k), ts)[1][0] > oche.play(random.Random(k), ts)[1][1] for k in range(200))
    assert 0 < won < 200 and won > 100


def _darts_lines(r, said=lambda d: d["call"]):
    from newsroom.models import PanelLine
    lines = [PanelLine(speaker="mag_b", text="The darts round!")]
    for k, d in enumerate(r["throws"]):
        if k == 0 or r["throws"][k - 1]["who"] != d["who"]:
            lines.append(PanelLine(speaker="mag_b", text=f"{d['who']}, step up."))
        lines.append(PanelLine(speaker="mag_b", text=said(d) + " Lovely."))
        if len(lines) % 6 == 5:
            lines.append(PanelLine(speaker="guest", guest_name=d["who"], text="Ooh."))
    return lines


def test_the_darts_round_is_called_dart_by_dart_and_the_window_follows_the_calls(channel, monkeypatch):
    w = world_mod.seed()
    q = quiz._record(w, quiz.teams(w), _booking())
    r = q["rounds"][2]
    assert r["kind"] == "darts" and len(r["throws"]) == 12
    brief = quiz.brief_for(w, "{r3}")
    assert "THE DARTS ROUND" in brief and all(f'"{d["call"]}"' in brief for d in r["throws"])
    from newsroom.models import PanelScript

    def reply(schema):
        return PanelScript(lines=_darts_lines(r), headline="The darts round", lower_third="Wexley Wits",
                           guest_name=r["throws"][0]["who"])
    _stub(monkeypatch, reply)
    seg = Segment(slot_id=7, type=T.interview, show="wits", brief="{r3}", target_s=200)
    writers.script_segment(seg, w)
    lines = _darts_lines(r)
    assert not seg.fallback and [d["line"] for d in seg.work["darts"]] == [
        i for i, l in enumerate(lines) if l.speaker == "mag_b" and l.text.endswith("Lovely.")]
    assert oche.overlay(seg, 0) == {"who": r["throws"][0]["who"], "to": 0, "darts": [], "total": 0, "call": ""}
    at = [d["line"] for d in seg.work["darts"]]
    two = oche.overlay(seg, at[1])                               # two darts called, the first thrower's
    assert len(two["darts"]) == 2 and two["total"] == sum(d["points"] for d in r["throws"][:2])
    fourth = oche.overlay(seg, at[3])                            # the next thrower's first dart: a fresh board
    assert fourth["who"] == r["throws"][3]["who"] and len(fourth["darts"]) == 1 and fourth["to"] == 1


def test_a_darts_round_with_a_call_missing_is_the_codes_own_round(channel, monkeypatch):
    w = world_mod.seed()
    q = quiz._record(w, quiz.teams(w), _booking())
    r = q["rounds"][2]
    from newsroom.models import PanelScript

    _stub(monkeypatch, lambda schema: PanelScript(lines=_darts_lines(r, lambda d: "What a throw!"),
                                                  headline="The darts round", lower_third="Wexley Wits",
                                                  guest_name=r["throws"][0]["who"]))
    seg = Segment(slot_id=8, type=T.interview, show="wits", brief="{r3}", target_s=200)
    writers.script_segment(seg, w)
    assert seg.lines[0].text.startswith("Round 3, the darts round")    # the code's own round
    assert len(seg.work["darts"]) == 12                                   # which calls every dart itself
    said = " ".join(l.text for l in seg.lines)
    assert f"{q['teams'][0]['name']} {r['scores_after'][0]}, {q['teams'][1]['name']} {r['scores_after'][1]}" in said


def test_twenty_is_not_twenty_five():
    from newsroom.models import PanelLine
    throws = [{"who": "Gav Polglase", "call": "Twenty."}, {"who": "Gav Polglase", "call": "Twenty-five."}]
    lines = [PanelLine(speaker="mag_b", text="Gav Polglase to throw."),
             PanelLine(speaker="mag_b", text="Twenty-five! Outer bull."), PanelLine(speaker="mag_b", text="Twenty."),
             PanelLine(speaker="mag_b", text="Twenty-five.")]
    assert oche.calls_in(lines, throws) == [2, 3]


def test_the_window_draws_the_board_and_the_darts():
    import pygame

    from newsroom import scenes

    pygame.font.init()
    canvas = pygame.Surface(scenes.CANVAS)

    class V:
        show, overlay = "wits", {"who": "Gav Polglase", "to": 0, "darts": [(0.0, 103.0)], "total": 60, "call": ""}
    entertainment.use()()                                        # registers the show for its colour, then undoes
    from newsroom import schedule
    schedule.SHOWS["wits"] = __import__("entertainment.wits", fromlist=["SHOW"]).SHOW
    try:
        oche.draw(canvas, V)
    finally:
        schedule.SHOWS.pop("wits")
    cx, cy = oche.BOX.x + 3 + oche.BOARD_R, oche.BOX.y + 13 + oche.BOARD_R
    assert canvas.get_at((cx, cy))[:3] == (200, 30, 40)                           # the bull
    assert canvas.get_at((cx, round(cy - 103 * oche._SCALE)))[:3] == (255, 255, 255)   # the dart's point, treble 20


def test_the_window_says_the_last_dart_in_darts_shorthand():
    assert [oche.mark(*oche.score_at(x, y)) for x, y in ((0, 103), (0, 166), (0, 60), (0, 12), (0, 0), (0, 200))] == [
        "T20", "D20", "20", "25", "BULL", "MISS"]


def test_a_quiz_round_may_run_to_forty_lines(channel):
    """Six questions with bonuses came to 25 lines and the twelve darts to 34; the debate's cap of 24 failed
    three items of five on the scratch run (2026-11-07)."""
    from newsroom.models import script_schema
    schedule_show = schedule.get("wits")
    schema = script_schema(T.interview, schedule_show.cast_for(T.interview), panel=True,
                           max_lines=writers.LINE_CAPS["wits"])
    lines = [{"speaker": "mag_b", "text": f"Question {i}?"} if i % 2 else
             {"speaker": "guest", "guest_name": "Gav Polglase", "text": "Hmm."} for i in range(36)]
    assert len(schema.model_validate({"headline": "Round one", "lower_third": "Wexley Wits", "lines": lines}).lines) == 36
    assert script_schema(T.interview, ("anchor", "guest"), panel=True).model_fields["lines"].metadata  # others keep 24


def test_the_darts_are_found_whichever_order_the_throwers_come_in():
    """Haiku took the throwers team by team on the scratch run (2026-11-07), not as booked, and every call was
    right: the round still went to the stand-in. Calls now follow the thrower Clive last named."""
    from newsroom.models import PanelLine
    throws = [{"who": w, "call": c} for w, c in (("Gav Polglase", "Twenty."), ("Gav Polglase", "One."),
                                                  ("Shirley Vosper", "Twenty-five."), ("Shirley Vosper", "Five."))]
    say = lambda t: PanelLine(speaker="mag_b", text=t)
    lines = [say("Round three! Shirley Vosper first for the Anchor and Bell."), say("Twenty-five. Lovely."),
             PanelLine(speaker="guest", guest_name="Shirley Vosper", text="Twenty, I said!"), say("Five."),
             say("Thirty for Shirley. Gav, over to you."), say("Twenty."), say("One. Oh, Gav.")]
    assert oche.calls_in(lines, throws) == [5, 6, 1, 3]
    assert oche.calls_in(lines[:6], throws) is None                     # Gav's second dart never called


def test_who_said_that_uses_the_weeks_guests_and_never_gives_the_name_away():
    w = world_mod.seed()
    for i, (name, role, said) in enumerate((
            ("Ruth Fairley", "chandler", "The crane is rebooked for the 17th, so there is time to publish."),
            ("Tam Buchanan", "lifeboat coxswain", "Tam Buchanan says the boat is ready."),         # names himself
            ("Gav Polglase", "darts captain", "Darts on Tuesday, quiz on Saturday."))):              # a contestant
        w.ensure_person(name, role)
        w.remember_guest(name, "Coastwide", said, None)
    ts = [{"pub": "the Lugger", "name": "The Lugger", "members": ["Gav Polglase", "Tracy Hendy"], "strength": 1.0},
          {"pub": "the Pilchard", "name": "The Pilchard", "members": ["Mick Jewell", "Lorraine Oates"], "strength": 1.0}]
    qs = quiz._quotes(w, ts, _booking())
    ours = [q for q in qs if "Coastwide" in q.question]
    assert len(qs) == quiz.PER_ROUND and [q.answer for q in ours] == ["Ruth Fairley, chandler"]
    assert "crane is rebooked for the 17th" in ours[0].question


def test_the_doubles_aim_at_double_twenty_and_the_pair_with_more_take_it():
    import random
    ts = [{"name": "A", "pub": "A", "members": ["a", "b"], "strength": 1.0},
          {"name": "B", "pub": "B", "members": ["c", "d"], "strength": 1.0}]
    calls = [d["call"] for k in range(100) for d in oche.play(random.Random(k), ts, oche.DOUBLE_AIM)[0]]
    # about half land just outside the double, in the number ring; a few miss the board altogether
    assert 0.3 < calls.count("No score.") / len(calls) < 0.6 and calls.count("Off the board!") / len(calls) < 0.06
    assert any(c == "Double twenty!" for c in calls)


def test_a_thrower_may_call_their_own_darts():
    """Haiku's doubles round, 2026-11-07: each thrower called their own darts ("Five.", "No score.")."""
    from newsroom.models import PanelLine
    throws = [{"who": "Gav Polglase", "call": c} for c in ("Five.", "No score.")] + \
             [{"who": "Shirley Vosper", "call": "Double twenty!"}]
    lines = [PanelLine(speaker="mag_b", text="Gav Polglase, you're up."),
             PanelLine(speaker="guest", guest_name="Gav Polglase", text="Five."),
             PanelLine(speaker="guest", guest_name="Gav Polglase", text="No score. Typical."),
             PanelLine(speaker="mag_b", text="Shirley Vosper, over to you."),
             PanelLine(speaker="guest", guest_name="Shirley Vosper", text="Double twenty! Get in.")]
    assert oche.calls_in(lines, throws) == [1, 2, 4]
