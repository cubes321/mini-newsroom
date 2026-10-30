"""Out and About: Meg Trethewey at 15:00 on days out, culture and food (docs/SHOWS.md).

The show is out on location all the way through, with no studio. Its `review` item is a visit to a
place to eat or a show, ending in stars out of five, and the town remembers them (`World.reviews`):
Meg doesn't review a place again within a fortnight, may go back to an older one to see if it has
changed, and on Coastwide an owner may come on to answer back.
"""
from __future__ import annotations

from datetime import date, timedelta

from .models import ReviewScript
from .world import World

SHOW = "outabout"
REST_DAYS = 14                  # a place isn't reviewed again within this
SHOWN = 8                       # the reviews a writer is shown
ANSWER_BACK_DAYS = 7            # how recent a review an owner may answer back on Coastwide


def record(world: World, script: ReviewScript) -> dict:
    """Keep a review: the place, what it is, where, the stars and the verdict, and who spoke for it."""
    entry = {"date": world.last_date, "place": script.place.strip(), "kind": script.kind, "where": script.where,
             "stars": script.stars, "verdict": script.verdict, "owner": script.guest_name or ""}
    with world.lock:
        world.reviews = (world.reviews + [entry])[-200:]
    return entry


def _since(world: World, days: int) -> str:
    return (date.fromisoformat(world.last_date) - timedelta(days=days)).isoformat()


def _row(r: dict) -> str:
    owner = f"; {r['owner']} spoke for it" if r.get("owner") else ""
    return (f"  - {date.fromisoformat(r['date']):%a %d %b}: {r['place']} ({r['kind']}, {r['where']}): "
            f"{r['stars']} out of 5, \"{r['verdict']}\"{owner}")


def for_prompt(world: World) -> str:
    """The places Meg has reviewed, for every item in the show: a fortnight's rest, then a revisit."""
    rest = _since(world, REST_DAYS)
    with world.lock:
        recent = world.reviews[-SHOWN:]
        resting = sorted({r["place"] for r in world.reviews if r["date"] > rest})   # all of them, not just the shown
    if not recent:
        return "PLACES MEG HAS REVIEWED: none yet."
    return ("PLACES MEG HAS REVIEWED (nowhere reviewed in the last fortnight is reviewed again"
            + (f": not {', '.join(resting)}" if resting else "")
            + "; an older one may be revisited, to see if it has changed, keeping to what she said then):\n"
            + "\n".join(_row(r) for r in recent))


def answer_back(world: World) -> str:
    """Out and About's reviews of the last week, for Coastwide: an owner may come on to answer back."""
    since = _since(world, ANSWER_BACK_DAYS)
    with world.lock:
        recent = [r for r in world.reviews if r["date"] > since][-4:]
    if not recent:
        return ""
    return ("OUT AND ABOUT'S RECENT REVIEWS (if THIS ITEM suits, the guest may be the owner of one, answering "
            "back with good humour: the stars stand, they give their side):\n" + "\n".join(_row(r) for r in recent))
