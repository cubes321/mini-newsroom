"""Wexley Wits: the show, its prompts and its set. The quiz itself is quiz.py's.

Half an hour from a darts pub: Clive Ashdown (mag_b) welcomes the two pubs, asks four rounds of questions and a
darts round (oche.py: every dart in code, shown in a window as Clive calls it), and reads
the final score. Each round is one interview item whose brief carries the round as booked ("{r2}"), so the
writer sets the banter around results already decided. If items come in short, the order wraps to a chat
with one team or the other (no questions, no score) until the result is read at the close.

The set stands in: the darts pub backdrop (assets/backdrops/pub.png) with Clive at the left and the two
teams across the floor, until a quiz set of its own is drawn and approved.
"""
from __future__ import annotations

from newsroom.models import SegmentType as T
from newsroom.schedule import Item as I, Show
from newsroom.writers import _COMMON_RULES, _MIDDLE

from . import quiz

SET = "pub"
DONE = ("all seven rounds are over and only the result is to come (no round is next), so no quiz questions "
        "and no score: ")
# Clive standing at the left; the home pair, then the away pair, facing him across the floor.
MARKS = {"host": (52, 152, 2, 1), "guest": (128, 150, 2, -1),
         "panel_1": (128, 150, 2, -1), "panel_2": (178, 150, 2, -1),
         "panel_3": (238, 154, 2, -1), "panel_4": (288, 154, 2, -1)}

SHOW = Show(
    quiz.SHOW, "WEXLEY WITS", "QUIZ", (196, 140, 40),
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Clive opens Wexley Wits: a cheery good evening from the pub, {open}; he "
                                 "introduces both teams by name, and how the scoring works", target_s=50.0),
        I(T.interview, brief="{r1}", target_s=240.0),
        T.ad_break,
        I(T.interview, brief="{r2}", target_s=240.0),
        I(T.interview, brief="{r3}", target_s=200.0),            # the darts round
        T.ad_break,
        I(T.interview, brief="{r4}", target_s=240.0),
        I(T.interview, brief="{r5}", target_s=200.0),            # who said that
        T.ad_break,
        I(T.interview, brief="{r6}", target_s=240.0),
        I(T.interview, brief="{r7}", target_s=200.0),            # darts doubles
        # Wraps to here until the close: chats, no questions and no score, a different angle each lap.
        I(T.interview, brief=tuple(DONE + b for b in (
            "Clive chats with {chat1} about their pub, their darts season and who is the brains of the pair",
            "Clive chats with {chat2} about their pub, the regulars and how they prepared for tonight",
            "Clive asks both captains for the best and the worst answer they have ever given at a quiz",
            "Clive asks {chat1} which question tonight they will be kicking themselves about all week",
            "Clive asks {chat2} about the oddest thing that has happened on a darts night at their pub",
            "Clive asks both pairs what the winners should do with tonight's prize, a tin of biscuits and the "
            "pub's cup")), target_s=120.0),
    ),
    loop_from=12,
    closing=(I(T.interview, "close", brief="the RESULT, {close}; a word from each captain, a good loser and a "
                                           "happy winner, and Clive's goodnight", target_s=110.0),),
    target_s={T.bumper: 8.0, T.links: 50.0, T.interview: 240.0, T.ad_break: 60.0},
    cast=("mag_b",), lead="mag_b",
    cast_by_type={T.links: ("mag_b",), T.interview: ("mag_b", "guest")},
    station="Wexley Wits, the pub quiz on Port Wexley's second channel, with Clive Ashdown asking",
    tone="warm, quick and a bit cheeky: pub banter, regulars ribbing each other, Clive's gentle jokes",
    light=True,
    repeats_overnight=False,     # tonight's quiz, tonight
)

_RULES = """
This is part of WEXLEY WITS, a pub quiz, as THE QUIZ gives it. Clive Ashdown ("mag_b") is the
quizmaster; every contestant is speaker "guest" with guest_name their exact name from THE TEAMS. The
questions, who answers, right or wrong, and the scores are FIXED: Clive asks each question word for
word, the named contestant answers, and it goes exactly as THIS ITEM says. Never add a question, change
an answer, or change a score. The general knowledge questions are real-world facts, given to you: read
them as given (the rule that everything is invented is for the town). No news stories of your own: the
quiz is the item. Teammates may confer for a line before the answer; a wrong answer is a plausible one,
said with conviction. thread_id is null.
"""

SYSTEMS = {
    T.links: _COMMON_RULES + _RULES + """
These are Clive's words TO CAMERA ("mag_b" alone), as THIS ITEM and the PLACE IN THE SHOW say. No
contestant speaks. headline = the point in under 12 words. lower_third = "Wexley Wits" plus a short tag.
""",
    T.interview: _COMMON_RULES + _RULES + """
This is Clive with the teams, as THIS ITEM says. When it is a ROUND: Clive names the round in a line,
then asks its questions in order, with a quick word now and then for whoever answered; each goes as given (right; or wrong and over to the other team for
the bonus; or nobody, and Clive gives the answer); a quick word between questions, never a long one;
at the end Clive reads out THE SCORE exactly. When it is THE DARTS ROUND, it goes dart by dart as
THIS ITEM gives it. At most 36 lines: Clive's verdict and his next question
share a line. Every contestant speaks at least once. When it is a chat,
there are no questions and no score. When it is the RESULT, it goes exactly as given. Every "guest" line
names its speaker in guest_name. headline = the round or the chat and how it went, under 12 words.
lower_third = "Wexley Wits" plus the round, short.
""",
}

PLACE = {
    (quiz.SHOW, T.links): {
        "open": "PLACE IN THE SHOW: this OPENS Wexley Wits: the first words of the programme.",
        "": _MIDDLE.format(title="Wexley Wits", extra=""),
    },
    (quiz.SHOW, T.interview): {"": _MIDDLE.format(title="Wexley Wits", extra="")},
}

IDENT = "It's Wexley Wits! The pub quiz, live from Port Wexley."
