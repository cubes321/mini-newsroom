"""Town talk (talk.py): last night's Wexley Wits result reaches the writers' briefing as talk, for two days,
once the quiz has really been on air.

The quiz entry is hand-made, as entertainment/quiz.py records one: no model, and none of that channel's code.
"""
from datetime import date, timedelta

from newsroom import llm, talk, world as world_mod

TODAY = date(2026, 11, 9)


def _town(night=TODAY - timedelta(days=1), aired=True, **over):
    w = world_mod.seed()
    w.last_date = TODAY.isoformat()
    quiz = {"date": night.isoformat(), "venue": "The Railway",
            "teams": [{"pub": "the Railway", "name": "The Railway", "members": ["Kev Moyle", "Bev Carne"]},
                      {"pub": "the Harbour Lights", "name": "The Harbour Lights", "members": ["Shirley Vosper", "Dennis Rowe"]}],
            "rounds": [{"kind": "general", "scores_after": [6, 8]}, {"kind": "potluck", "scores_after": [14, 18]},
                       {"kind": "doubles", "scores_after": [24, 21]}],
            "tiebreak": None, "final": [24, 21], "winner": 0, "stand_in": False} | over
    w.quizzes.append(quiz)
    if aired:
        w.archive.append({"date": night.isoformat(), "day": 15, "type": "links", "headline": "The Railway take it",
                          "thread_id": None, "people": [], "text": "And that is the final score.", "show": "wits",
                          "brief": "{close}", "hash": ""})
    return w


def test_last_nights_quiz_is_in_the_briefing_as_talk_after_the_cache_break():
    w = _town()
    said = talk.quiz(w, TODAY)
    assert said == ("Wexley Wits, the television pub quiz, Sunday night at The Railway: The Railway (Kev Moyle and "
                    "Bev Carne) beat The Harbour Lights (Shirley Vosper and Dennis Rowe) 24-21, from behind going "
                    "into the last round.")
    head, _, tail = w.summary_for_prompt().partition(llm.CACHE_BREAK)
    assert "Town talk" in tail and said in tail and "never a headline" in tail and "Wexley Wits" not in head
    assert "Wexley Wits" not in w.summary_for_editor()          # the desk never sees it: no thread grows from talk


def test_the_losers_win_and_a_tiebreak_are_told_as_they_were():
    w = _town(winner=1, final=[21, 22], tiebreak={"winner": 1},
              rounds=[{"kind": "general", "scores_after": [10, 9]}, {"kind": "doubles", "scores_after": [21, 21]}])
    assert "The Harbour Lights (Shirley Vosper and Dennis Rowe) beat The Railway" in talk.quiz(w, TODAY)
    assert talk.quiz(w, TODAY).endswith("22-21, on the tiebreak.")


def test_it_is_talk_for_two_days_and_never_before_it_has_been_on():
    assert talk.line(_town(night=TODAY), TODAY) == ""                           # tonight's: booked, not played
    assert talk.line(_town(aired=False), TODAY) == ""                           # booked, and the station was off
    assert talk.line(_town(night=TODAY - timedelta(days=2)), TODAY) != ""
    assert talk.line(_town(night=TODAY - timedelta(days=3)), TODAY) == ""
    assert talk.line(world_mod.seed(), TODAY) == ""                             # a station with no quiz says nothing
    w = _town()
    w.quizzes.append({"date": "2026-11-08"})                                    # an entry in a shape it can't read
    assert talk.quiz(w, TODAY).startswith("Wexley Wits")
