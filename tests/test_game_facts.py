"""Game facts the code already knows, held to the script (TODO, the 2026-11-25 review): a Wits title that gives a
round, the lead or the quiz to the wrong pub is put right in code, and a High Water round that puts a climber on
the wrong step is asked once more. The nights' own facts and lines, copied in: no world, no network."""
from __future__ import annotations

import types

import pytest

from entertainment import highwater_show as hs, quiz
from newsroom import llm
from newsroom.models import SegmentType as T

# 2026-11-24's quiz: the round points 5-4, 2-5, 3-0, 2-6, 4-3, 4-6, 0-3.
WITS = {"teams": [{"name": "The Lugger", "members": ["a", "b"]}, {"name": "The Anchor and Bell", "members": ["c", "d"]}],
        "rounds": [{"kind": k, "title": k, "scores_after": s} for k, s in (
            ("general", [5, 4]), ("local", [7, 9]), ("darts", [10, 9]), ("news", [12, 15]), ("quotes", [16, 18]),
            ("potluck", [20, 24]), ("doubles", [20, 27]))],
        "final": [20, 27]}


def _title(monkeypatch, brief: str, headline: str, q: dict = WITS) -> tuple[str | None, str]:
    monkeypatch.setattr(quiz, "tonight", lambda world: q)
    script = types.SimpleNamespace(headline=headline)
    return quiz.mend_title(types.SimpleNamespace(brief=brief), script, None), script.headline


def test_a_title_giving_the_round_to_the_wrong_pub_is_put_right(monkeypatch):
    was, now = _title(monkeypatch, "{r5}", "Who Said That: The Anchor and Bell Edge Round Five")
    assert was and now == "Round five to The Lugger, four points to three"      # the Anchor led overall, 18-16
    tied = {**WITS, "rounds": [{"kind": "general", "title": "g", "scores_after": [4, 2]},
                               {"kind": "local", "title": "l", "scores_after": [8, 6]}]}
    assert _title(monkeypatch, "{r2}", "Round two on the coast goes to The Lugger", tied)[1] == \
        "Round two shared, four points each"                                    # 2026-11-16's, 4-4
    assert _title(monkeypatch, "{close}", "The Lugger Win Wexley Wits")[1] == \
        "The Anchor and Bell win Wexley Wits, twenty-seven to twenty"


@pytest.mark.parametrize("brief, headline", [
    ("{r1}", "Round one to The Lugger, five points to four"),
    ("{r2}", "Round two to the Anchor and Bell, nine points to seven"),
    ("{r3}", "The Lugger take the darts round, ten points to nine"),
    ("{r4}", "Round four, the week's news, goes to The Anchor and Bell"),
    ("{r4}", "Round four: The Anchor and Bell pull ahead"),                     # the lead, which they had
    ("{r5}", "The Anchor and Bell still lead after Who Said That"),
    ("{r7}", "Darts Doubles Go to The Anchor and Bell on Three to Two"),
    ("{r5}", "Who Said That? A round of quotes"),                               # no pub named: nothing to put right
    ("{r5}", "The Lugger and The Anchor and Bell trade quotes"),               # both: no claim
    ("", "The Anchor and Bell win"),                                            # a chat: not a round
])
def test_a_true_title_is_left_alone(monkeypatch, brief, headline):
    assert _title(monkeypatch, brief, headline) == (None, headline)


def test_a_wrong_lead_is_put_right_as_the_lead(monkeypatch):
    was, now = _title(monkeypatch, "{r3}", "The Anchor and Bell lead after the darts")
    assert was and now == "The Lugger lead after round three, ten to nine"


# 2026-11-24's High Water: Doris 5->7->6->8 in round 2, 11->12->12->12 in round 4; Lenny 1->3->2->1 in round 4.
def _turn(who, frm, to, q):
    return {"who": who, "choice": "swim", "right": to > frm, "from": frm, "to": to,
            "question": {"q": q, "a": "x", "wrong": "y"}}


HW = {"climbers": [{"name": "Lenny Gossard"}, {"name": "Doris Penhallow"}],
      "game": {"rounds": [
          {"turns": [], "after": []},
          {"turns": [_turn("Doris Penhallow", 5, 7, "Which sea lies between Italy and the Balkans?"),
                     _turn("Lenny Gossard", 4, 3, "Which current warms the coast of western Europe?"),
                     _turn("Doris Penhallow", 7, 6, "Which painter made The Fighting Temeraire?"),
                     _turn("Lenny Gossard", 3, 2, "Which planet has the Great Red Spot?"),
                     _turn("Doris Penhallow", 6, 8, "Which composer wrote the Hebrides Overture?"),
                     _turn("Lenny Gossard", 2, 4, "Which element has the symbol Fe?")],
           "after": [{"who": "Lenny Gossard", "step": 4}, {"who": "Doris Penhallow", "step": 8}], "washed": []},
          {"turns": [], "after": []},
          {"turns": [_turn("Doris Penhallow", 11, 12, "Which bird is the national emblem of New Zealand?"),
                     _turn("Lenny Gossard", 1, 3, "Which river flows through Vienna?")],
           "after": [{"who": "Lenny Gossard", "step": 6}, {"who": "Doris Penhallow", "step": 12}],
           "washed": [{"who": "Lenny Gossard", "from": 3, "to": 6}]}]}}       # one turn of Lenny's, so washed from 3


def _l(text, speaker=hs.HOST):
    return types.SimpleNamespace(speaker=speaker, text=text)


ROUND4 = [_l("Doris Penhallow, you're on step eleven, and you're swimming."),
          _l("Which bird is the national emblem of New Zealand?"), _l("The kiwi!", "guest"),
          _l("You're up to step twelve, Doris."),
          _l("Lenny Gossard, you're down on step one."), _l("Which river flows through Vienna?"),
          _l("The Danube.", "guest"), _l("Up you go to step three, Lenny. Doris is on step twelve now."),
          _l("The tide comes in three steps. It reaches Lenny Gossard on step three. Lenny Gossard is on step six.")]


def test_a_climber_is_held_to_the_step_they_are_on_at_that_moment():
    assert hs.step_slips(ROUND4, HW, 3) == []
    wrong = [_l("Doris Penhallow, you're on step twelve, which is a dry perch for now."), *ROUND4[1:]]
    slips = hs.step_slips(wrong, HW, 3)
    assert len(slips) == 1 and "Doris Penhallow is on step 11 there, not 12" in slips[0]   # 2026-11-24, round 4
    late = [*ROUND4[:7], _l("Lenny is back on step one, Doris on twelve.")]
    assert "Lenny Gossard is on step 3 or 6 there, not 1" in hs.step_slips(late, HW, 3)[0]   # before or after the tide
    round2 = [_l("Doris Penhallow, you're on step seven and you've swum for it."),
              _l("Which sea lies between Italy and the Balkans?")]
    assert "Doris Penhallow is on step 5 there, not 7" in hs.step_slips(round2, HW, 1)[0]   # 2026-11-24, round 2
    assert hs.step_slips([_l("The water's at step two, Doris, and climbing.")], HW, 3) == []  # the tide, not her


def test_a_wrong_step_is_asked_again_once_and_then_stands(monkeypatch):
    monkeypatch.setattr(hs, "booked", lambda world: HW)
    monkeypatch.setattr(hs, "_questions", lambda k, brief: [t["question"] for t in HW["game"]["rounds"][3]["turns"]])
    seg = types.SimpleNamespace(type=T.interview, brief="{r4}", work={}, slot_id=7)
    wrong = types.SimpleNamespace(lines=[_l("Doris Penhallow, you're on step twelve."), *ROUND4[1:]])
    with pytest.raises(llm.AskAgain, match="Doris Penhallow is on step 11 there, not 12"):
        hs.check(seg, wrong, None)
    hs.check(seg, wrong, None)                                    # the second time it stands: no template for a step
    seg = types.SimpleNamespace(type=T.interview, brief="{r4}", work={}, slot_id=8)
    hs.check(seg, types.SimpleNamespace(lines=ROUND4), None)      # right: nothing asked
    unasked = types.SimpleNamespace(lines=[l for l in ROUND4 if "Vienna" not in l.text])
    with pytest.raises(llm.AskAgain, match="weren't asked"):
        hs.check(seg, unasked, None)
    with pytest.raises(llm.AskAgain, match="weren't asked"):     # a question still unasked is asked for again
        hs.check(seg, unasked, None)
