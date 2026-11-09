"""The council's promises: what full council voted would happen, by when, and whether it did.

Every motion The Chamber carries comes with what follows ("the tender is awarded by Friday 13
November"). Until 2026-11-09 that became the story's next step and was then forgotten: the story
moved on, and nobody on the station ever said "the council promised this a fortnight ago". Now a
carried motion's what-follows is kept as a promise, with the day it falls due (read from its own
words, or else the next full council).

- The story desk sees the open ones every round, the overdue ones marked, and gives the verdict when
  a story's next step delivers one or shows it broken (`StoryPlan.promises`): the desk decides what
  happens in the town, so it decides this too, and the writers report it as the story's next step.
- The Chamber's booking and its hour see them, so a motion can deliver or renew one, and a councillor
  or the public gallery can hold the council to one.
- SEVENTEXT has them on page 175, COUNCIL WATCH: open, overdue, kept, broken.

A promise whose story has closed or faded without a verdict lapses; one a month overdue with no
verdict lapses too. The last KEPT are held in the world.

    python -m newsroom.promises            # the list as it stands
"""
from __future__ import annotations

import logging
import re
from datetime import date, timedelta

from . import council

log = logging.getLogger(__name__)

KEPT = 40                          # promises held in the world, the newest
LAPSE_DAYS = 28                    # overdue this long with no verdict: nobody is counting any more
SHOWN = 6                          # in a prompt
OPEN, DONE, BROKEN, LAPSED = "open", "kept", "broken", "lapsed"

_MONTHS = ("january", "february", "march", "april", "may", "june", "july", "august", "september", "october",
           "november", "december")
_DAYS = ("monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday")
_DAY_MONTH = re.compile(r"\b(\d{1,2})(?:st|nd|rd|th)?\s+(?:of\s+)?(" + "|".join(_MONTHS) + r")\b", re.I)
_THE_NTH = re.compile(r"\bthe\s+(\d{1,2})(?:st|nd|rd|th)\b", re.I)
_WEEKDAY = re.compile(r"\b(" + "|".join(_DAYS) + r")\b", re.I)


def due_date(text: str, made: date) -> date:
    """The day a promise falls due, from its own words: "Friday 13 November", "by the 28th", "on
    Monday". Anything undated ("officers will look into it") is due at the next full council, where
    it would be asked about."""
    try:
        if m := _DAY_MONTH.search(text):
            d = date(made.year, _MONTHS.index(m.group(2).lower()) + 1, int(m.group(1)))
            return d if d >= made else d.replace(year=made.year + 1)
        if m := _THE_NTH.search(text):
            for k in range(0, 62):
                d = made + timedelta(days=k)
                if d.day == int(m.group(1)):
                    return d
        if m := _WEEKDAY.search(text):
            gap = (_DAYS.index(m.group(1).lower()) - made.weekday()) % 7
            return made + timedelta(days=gap or 7)
    except ValueError:                 # "30 February"
        pass
    return council.next_meetings(made + timedelta(days=1), 1)[0]


def record(world, made: date, thread, text: str) -> dict | None:
    """Keep a carried motion's what-follows as a promise. None if there is nothing to keep, or the
    same promise on the same story is already open."""
    text = " ".join((text or "").split())
    if len(text) < 8 or thread is None:
        return None
    with world.lock:
        if any(p["state"] == OPEN and p["thread_id"] == thread.id and p["text"] == text[:200] for p in world.promises):
            return None
        n = max((int(p["id"][1:]) for p in world.promises), default=0) + 1
        p = {"id": f"p{n:03d}", "made": made.isoformat(), "thread_id": thread.id, "title": thread.title,
             "text": text[:200], "due": due_date(text, made).isoformat(), "state": OPEN, "settled": "", "note": ""}
        world.promises = (world.promises + [p])[-KEPT:]
    log.info("council promise %s on %s, due %s: %s", p["id"], thread.id, p["due"], p["text"][:80])
    return p


def open_(world) -> list[dict]:
    """The promises still to be kept, the soonest due first."""
    with world.lock:
        return sorted((p for p in world.promises if p["state"] == OPEN), key=lambda p: (p["due"], p["id"]))


def overdue(p: dict, today: date) -> int:
    """Days past its day, for an open promise; 0 if it isn't."""
    return max(0, (today - date.fromisoformat(p["due"])).days) if p["state"] == OPEN else 0


def settle(world, pid: str, state: str, note: str = "") -> bool:
    """The desk's verdict on an open promise. False if there is no such open promise."""
    with world.lock:
        p = next((p for p in world.promises if p["id"] == pid and p["state"] == OPEN), None)
        if p is None or state not in (DONE, BROKEN):
            return False
        p.update(state=state, settled=world.last_date, note=" ".join(note.split())[:160])
    log.info("council promise %s %s: %s", pid, state, p["note"] or p["text"][:80])
    return True


def lapse(world, today: date) -> int:
    """Open promises nobody can settle any more: the story closed, faded or was merged away, or the day
    passed a month ago. Returns how many lapsed."""
    n = 0
    with world.lock:
        for p in world.promises:
            if p["state"] != OPEN:
                continue
            t = world.thread(p["thread_id"])
            for _ in range(5):             # merged into another story: the promise goes with it
                if t is None or not t.merged_into:
                    break
                t = world.thread(t.merged_into)
                if t is not None:
                    p.update(thread_id=t.id, title=t.title)
            gone = t is None or t.phase in ("closed", "faded")
            if gone or overdue(p, today) > LAPSE_DAYS:
                p.update(state=LAPSED, settled=today.isoformat(),
                         note="the story ended without it" if gone else "a month past its day, and nobody asked")
                n += 1
    return n


def _when(p: dict, today: date) -> str:
    due = date.fromisoformat(p["due"])
    late = overdue(p, today)
    said = f"{due:%A} {due.day} {due:%B}"
    if late:
        return f"OVERDUE by {late} day{'s' if late != 1 else ''} (was due {said})"
    gap = (due - today).days
    return f"due {'TODAY' if gap == 0 else 'tomorrow' if gap == 1 else said}"


def _rows(world, today: date, limit: int = SHOWN, only: set[str] | None = None) -> list[str]:
    # The overdue first (the oldest debt), then the soonest due.
    ps = [p for p in open_(world) if only is None or p["thread_id"] in only]
    ps = sorted(ps, key=lambda p: (not overdue(p, today), p["due"]))[:limit]
    return [f"  - [{p['id']}] on [{p['thread_id']}] {p['title']}, voted {date.fromisoformat(p['made']):%a %d %b}: "
            f"\"{p['text']}\" {_when(p, today)}" for p in ps]


def for_desk(world, today: date, only: set[str] | None = None) -> str:
    """The open promises on this round's threads (`only`) for the story desk, with how it gives a
    verdict: a verdict needs the story's next step written to match, so only those. Empty if none."""
    rows = _rows(world, today, only=only)
    if not rows:
        return ""
    return ("\n\nCOUNCIL PROMISES (what full council voted would happen; the town is counting):\n" + "\n".join(rows)
            + "\nWhen a thread's NEXT development this round delivers one of these, or shows it will not happen, "
              "give the verdict in `promises` (its id, kept or broken, a line on how) and write that NEXT "
              "development to match. An OVERDUE promise is a story in itself: somebody in the town asks where it "
              "is. Leave `promises` empty when nothing settles one.")


def for_chamber(world, today: date) -> str:
    """The open promises for The Chamber: its booking, and every item of its hour."""
    rows = _rows(world, today, limit=4)
    if not rows:
        return ""
    return ("\nPROMISES THE COUNCIL HAS MADE AND NOT YET KEPT (a motion may deliver or renew one; a councillor or "
            "the public gallery may hold the council to one, by its date):\n" + "\n".join(rows))


def tally(world) -> dict[str, int]:
    with world.lock:
        return {s: sum(1 for p in world.promises if p["state"] == s) for s in (OPEN, DONE, BROKEN, LAPSED)}


def board(world, today: date, limit: int = 5) -> list[tuple[str, str, dict]]:
    """For the teletext page: (label, colour, promise), the open ones first (overdue at the top), then
    the latest verdicts."""
    with world.lock:
        ps = list(world.promises)
    live = sorted((p for p in ps if p["state"] == OPEN), key=lambda p: (not overdue(p, today), p["due"]))
    done = sorted((p for p in ps if p["state"] in (DONE, BROKEN)), key=lambda p: p["settled"], reverse=True)
    out = []
    for p in (live + done)[:limit]:
        due = date.fromisoformat(p["due"])
        if p["state"] == DONE:
            out.append(("KEPT", "green", p))
        elif p["state"] == BROKEN:
            out.append(("BROKEN", "red", p))
        elif overdue(p, today):
            out.append((f"OVERDUE since {due:%a} {due.day} {due:%b}", "red", p))
        else:
            out.append((f"DUE {due:%a} {due.day} {due:%b}", "yellow", p))
    return out


def main() -> None:
    from . import world as world_mod

    w = world_mod.load()
    today = date.fromisoformat(w.last_date)
    print(", ".join(f"{n} {s}" for s, n in tally(w).items()))
    for label, _, p in board(w, today, limit=KEPT):
        print(f"{p['id']}  {label:<24} [{p['thread_id']}] {p['title'][:40]}: {p['text']}"
              + (f"  ({p['note']})" if p["note"] else ""))


if __name__ == "__main__":
    main()
