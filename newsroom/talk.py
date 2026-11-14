"""Town talk: what Port Wexley is talking about that Channel 7 didn't report itself.

The other channel shares the town (entertainment/), and what happens on it is known in the town the
next morning, as last night's television always was. So far that is the pub quiz, Wexley Wits: for
two days after one has aired, the writers' briefing has a line with who won, the score and how, to
drop into the sofa's chat, a caller's aside or a vox pop. It is talk, not news: the line says so,
and the story desk never sees it, so no thread grows from it.

Its soap, Marina Row, is talked about too: an aired episode's cliffhanger, the question and never the
answer (soap below). So is its wildlife series, Tideline: what Rowan Polglase showed, and the number he gave
(wildlife below). That one is canon: the seal pups in the coves really are there.

Read from the world alone (`world.quizzes`, `world.soaps`, the archive): this module knows nothing of
the other channel's code, and a station that never runs it has no talk.
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


def soap(world, today: date) -> list[str]:
    """Each Channel 8 drama's latest cliffhanger that aired in the last TALK_DAYS, as a sentence: the question the
    episode left, never what happens next (the arc stays in entertainment/soap.py). An episode counts as aired once
    its last scene went out (`last_brief`, its closing item's brief); one planned but never shown is nobody's talk.
    Read from the world alone (world.soaps): this module knows nothing of the other channel's code."""
    out = []
    for series in world.soaps.values():
        for ep in reversed(series.get("episodes", [])):
            try:
                day = date.fromisoformat(ep["date"])
                gap = (today - day).days
                if gap < 1:                    # tonight's: not shown yet, as far as the town knows
                    continue
                if gap > TALK_DAYS:
                    break
                if not any(e.get("show") == series["show"] and e.get("date") == ep["date"]
                           and e.get("brief") == ep["last_brief"] for e in world.aired_archive()):
                    continue
                out.append(f"{series['title']}, the soap on Channel 8, {day:%A} night: everyone is asking "
                           f"\"{ep['cliffhanger']}\" (nobody knows the answer yet).")
                break
            except (KeyError, TypeError, ValueError):
                continue                       # an entry saved in an older shape: no talk from it
    return out


def wildlife(world, today: date) -> str | None:
    """Channel 8's latest Tideline that aired in the last TALK_DAYS, as a sentence: the sight and its number. An
    episode is stamped aired by the item that gives them (entertainment/wildlife.py); one booked but never shown is
    nobody's talk. Read from the world alone (world.wildlife)."""
    for ep in reversed((getattr(world, "wildlife", None) or {}).get("episodes", [])):
        try:
            day = date.fromisoformat(ep["date"])
            gap = (today - day).days
            if gap < 1:
                continue
            if gap > TALK_DAYS:
                return None
            if not ep.get("aired"):
                continue
            n = f", {ep['count']} {ep['counted']} by his count" if ep.get("count") is not None else ""
            return f"Tideline, the wildlife programme on Channel 8, {day:%A} night: Rowan Polglase showed {ep['what']}{n}."
        except (KeyError, TypeError, ValueError):
            continue
    return None


def line(world, today: date) -> str:
    """The briefing's town-talk line, with its newline, or nothing."""
    said = [s for s in (quiz(world, today), *soap(world, today), wildlife(world, today)) if s]
    return f"{LABEL}{' '.join(said)}\n" if said else ""
