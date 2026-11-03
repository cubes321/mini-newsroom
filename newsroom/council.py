"""Port Wexley Town Council: when it meets, and who sits on it. Pure data and a calendar, like quay.py.

Full council meets every other Thursday (from `[chamber] first_meeting`, every `every_days`), and on
those nights The Chamber (chamber.py) takes 20:00 to 21:00 from The Inquiry and The Panel. The desk is
told the next meetings, so council business heads for nights that exist instead of Thursdays it makes
up. Helen Strand, the mayor, chairs, with the casting vote; six councillors sit with her, each for a
ward and with a leaning, so a vote splits the way the town would expect. Each has a voice of their own
(`VOICES`): a DramaBox design, chosen by ear on 2026-11-01 and cloned live by Pocket (assets/voices).

No meeting falls on New Year's Eve or on election day (the first Thursday in May, from 2027 every four
years): that one is cancelled, not moved, and the next is a fortnight on as usual (agreed 2026-11-03).

`NEWSROOM_COUNCIL_NIGHT=1` makes any night a council night (for a test run), `0` none (the tests).
"""
from __future__ import annotations

import os
from datetime import date, timedelta

from .config import CONFIG

CHAIR = "Helen Strand"

# (name, role, gender, age, leaning): the leaning is what the booking decides their votes from. A
# role is at most 50 characters, as a person's is (world.ensure_person).
COUNCILLORS: tuple[tuple[str, str, str, str, str], ...] = (
    ("Gerald Thorne", "Councillor, Harbour ward; budget committee chair", "m", "old",
     "careful with money: wants costings, phased spending and the reserves left alone"),
    ("Alan Penhaligon", "Councillor, the Salting ward", "m", "middle",
     "an independent for the residents: footpaths, lights, the bonfire, anything his ward can see"),
    ("Colin Tregarthen", "Councillor, Quay ward", "m", "old",
     "the fishing families' man: the harbour, the boats and the quay before anything in the town centre"),
    ("Sandra Okoye", "Councillor, Harrow Street ward", "f", "middle",
     "runs a shop: for the market, parking and trade, against anything that shuts a road for long"),
    ("Lucy Hammond", "Councillor, Cannery ward", "f", "young",
     "the youngest on the council: housing, the young, the estuary's wildlife; will vote to spend"),
    ("Tom Nancarrow", "Councillor, Saltby ward", "m", "old",
     "across the estuary and proud of it: keeps the old ways, the ferry, and a sharp eye on Port Wexley"),
)
# Their own voices, the chair's included: reference clips in assets/voices (voices.toml names each one's
# Kokoro stand-in). Named the Kokoro way, bf_/bm_, since a guest's look takes its gender from the voice.
VOICES = {CHAIR: "bf_strand", "Gerald Thorne": "bm_thorne", "Alan Penhaligon": "bm_penhaligon",
          "Colin Tregarthen": "bm_tregarthen", "Sandra Okoye": "bf_okoye", "Lucy Hammond": "bf_hammond",
          "Tom Nancarrow": "bm_nancarrow"}


def election_day(y: int) -> date | None:
    """The local elections: the first Thursday in May, in 2027 and every four years after."""
    if y < 2027 or (y - 2027) % 4:
        return None
    may = date(y, 5, 1)
    return may + timedelta(days=(3 - may.weekday()) % 7)


def cancelled(day: date) -> bool:
    """No meeting on New Year's Eve or on election day."""
    return (day.month, day.day) == (12, 31) or day == election_day(day.year)


def meets_on(day: date) -> bool:
    """The calendar: every `every_days` from `first_meeting`, never before it, and none on a cancelled day."""
    cfg = CONFIG.chamber
    gap = (day - date.fromisoformat(cfg.first_meeting)).days
    return gap >= 0 and gap % cfg.every_days == 0 and not cancelled(day)


def council_night(day: date) -> bool:
    """A night The Chamber is on: the calendar, unless NEWSROOM_COUNCIL_NIGHT says otherwise."""
    forced = os.environ.get("NEWSROOM_COUNCIL_NIGHT", "")
    return forced == "1" if forced in ("0", "1") else meets_on(day)


def next_meetings(day: date, n: int = 2) -> list[date]:
    """The next `n` meetings from `day` on (today included)."""
    out, d = [], day
    while len(out) < n:
        if meets_on(d):
            out.append(d)
        d += timedelta(days=1)
    return out


def calendar_line(day: date) -> str:
    """One line for the briefings: when full council meets, so council business heads there."""
    when = " and ".join(f"{d:%A} {d.day} {d:%B}" + (" (tonight)" if d == day else "") for d in next_meetings(day))
    return (f"Council: full council meets on {when}, live on The Chamber at eight. Council decisions (votes, "
            "budgets, planning) are taken at those meetings, not on other days.")


def who(world) -> list:
    """The councillors as the world has them (their roles, voices and what they've said)."""
    return [p for name, *_ in COUNCILLORS if (p := world.person_by_name(name))]
