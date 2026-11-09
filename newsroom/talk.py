"""Town talk: what Port Wexley is talking about that Channel 7 didn't report itself.

The other channel shares the town (entertainment/), and what happens on it is known in the town the
next morning, as last night's television always was. So far that is the pub quiz, Wexley Wits: for
two days after one has aired, the writers' briefing has a line with who won, the score and how, to
drop into the sofa's chat, a caller's aside or a vox pop. It is talk, not news: the line says so,
and the story desk never sees it, so no thread grows from it.

Read from the world alone (`world.quizzes`, the archive): this module knows nothing of the other
channel's code, and a station that never runs it has no talk.
"""
from __future__ import annotations

from datetime import date

QUIZ = "Wexley Wits"
QUIZ_SHOW = "wits"                 # the show id its items are archived under (entertainment/quiz.py)
TALK_DAYS = 2                      # the morning after, and the day after that
LABEL = ("Town talk (what people are saying; a passing mention where it fits, never a headline or a story "
         "of its own): ")


def _aired(world, day: str) -> bool:
    """Was that night's quiz on air? It is booked, with its result, hours before: one whose programme
    never went out (the station was off) is nobody's talk."""
    return any(e.get("show") == QUIZ_SHOW and e.get("date") == day for e in world.aired_archive())


def quiz(world, today: date) -> str | None:
    """The latest quiz that aired in the last TALK_DAYS, as one sentence; None if there is none."""
    for q in reversed(world.quizzes):
        try:
            day = date.fromisoformat(q["date"])
            gap = (today - day).days
            if gap < 1:                    # tonight's: booked, not yet played as far as the town knows
                continue
            if gap > TALK_DAYS:
                return None
            if not _aired(world, q["date"]):
                continue
            w = q["winner"]
            won, lost = q["teams"][w], q["teams"][1 - w]
            final = q["final"]
            how = ""
            if q.get("tiebreak"):
                how = ", on the tiebreak"
            elif len(q.get("rounds", [])) >= 2:
                before = q["rounds"][-2]["scores_after"]
                if before[w] < before[1 - w]:
                    how = ", from behind going into the last round"
            return (f"{QUIZ}, the television pub quiz, {day:%A} night at {q['venue']}: {won['name']} "
                    f"({' and '.join(won['members'])}) beat {lost['name']} ({' and '.join(lost['members'])}) "
                    f"{final[w]}-{final[1 - w]}{how}.")
        except (KeyError, IndexError, TypeError, ValueError):
            continue                       # an entry saved in an older shape: no talk from it
    return None


def line(world, today: date) -> str:
    """The briefing's town-talk line, with its newline, or nothing."""
    said = quiz(world, today)
    return f"{LABEL}{said}\n" if said else ""
