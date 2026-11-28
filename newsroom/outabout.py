"""Out and About: Meg Trethewey at 15:00 on days out, culture and food (docs/SHOWS.md).

The show is out on location all the way through, with no studio. Its `review` item is a visit to a
place to eat or a show, ending in stars out of five, and the town remembers them (`World.reviews`):
Meg doesn't review a place again within a fortnight, may go back to an older one to see if it has
changed, and on Coastwide an owner may come on to answer back.
"""
from __future__ import annotations

import random
import re
from datetime import date, timedelta

from .models import ReviewScript
from .world import World

SHOW = "outabout"
REST_DAYS = 14                  # a place isn't reviewed again within this
SHOWN = 8                       # the reviews a writer is shown
ANSWER_BACK_DAYS = 7            # how recent a review an owner may answer back on Coastwide

# Where a review is set, by what the place is (ReviewScript.kind): Meg reviews indoors. The darts pub
# isn't one of them: its oche and scoreboard say darts night, not supper.
INTERIORS: tuple[tuple[re.Pattern, str], ...] = (
    # A chip shop's counter and little tables are nearer the tea room's than the pub's inglenook: The Gull's Rest
    # ("fish and chip shop") was reviewed out on the fish quay (2026-11-28). A takeaway is still eaten outside.
    (re.compile(r"caf[eé]|tea ?(room|shop)|coffee|bakery|patisserie|cake|\bchip ?shop|chippy|fish bar", re.I),
     "tea_room"),
    (re.compile(r"\bpubs?\b|\binn\b|restaurant|bistro|brasserie|dining|tavern|carvery|supper", re.I), "dining_room"),
    (re.compile(r"\bplays?\b|theat|drama|panto|concert|music|\bgig|choir|comedy|musical|recital|ceilidh|opera|"
                r"\bshows?\b", re.I), "village_hall"),
)


def backdrop_for(kind: str, picked: str) -> str:
    """The interior that fits the place: a café's tea room, a pub's dining room, a show's village hall.
    Anything else (a takeaway, a gallery, a farm shop) keeps the writer's pick."""
    return next((bid for pattern, bid in INTERIORS if pattern.search(kind or "")), picked)


def record(world: World, script: ReviewScript) -> dict:
    """Keep a review: the place, what it is, where, the stars and the verdict, and who spoke for it."""
    entry = {"date": world.last_date, "place": script.place.strip(), "kind": script.kind, "where": script.where,
             "stars": script.stars, "verdict": script.verdict, "owner": script.guest_name or ""}
    with world.lock:
        world.reviews = (world.reviews + [entry])[-200:]
    return entry


def _since(world: World, days: int) -> str:
    return (date.fromisoformat(world.last_date) - timedelta(days=days)).isoformat()


def _name_words(place: str) -> frozenset[str]:
    return frozenset(w for w in re.findall(r"[a-z0-9]+", (place or "").lower().replace("'s", "")) if w != "the")


def resting(world: World, place: str) -> dict | None:
    """The review of this place in the last REST_DAYS, or None. The prompt names them, and on 2026-11-28 Meg
    reviewed all three of the day before's again: The Bay Window, Saltby Players and The Gull's Rest, two of them
    with the same verdict word for word. A name inside the other's is the same place ("Bay Window Tea Room")."""
    new = _name_words(place)
    if not new:
        return None
    rest = _since(world, REST_DAYS)
    with world.lock:
        recent = [r for r in world.reviews if r["date"] > rest]
    return next((r for r in reversed(recent)
                 if (old := _name_words(r["place"])) and (old <= new or new <= old)), None)


# The stars, drawn in code: told "most places get three or four", every review on one afternoon came out at three
# (2026-10-30); told "a good place is four", all six on 2026-11-27 and 11-28 came out at four.
STARS = (2, 3, 3, 3, 4, 4, 4, 5)
_STAR_VISIT = {
    1: "a bad visit: say plainly and fairly what went wrong",
    2: "a disappointing visit: one thing worth having, and what let it down",
    3: "a mixed visit: something good and something not, and who would still enjoy it",
    4: "a good visit with one small quibble",
    5: "a rare great one: say what makes it the best of its kind on the coast",
}


def stars_due(world: World) -> int:
    """The stars for the next review today: drawn from STARS by the date and how many came before, never the
    same as the one before it."""
    with world.lock:
        today = [r["stars"] for r in world.reviews if r["date"] == world.last_date]
    rng = random.Random(f"{world.last_date}/{len(today)}")
    choices = [s for s in STARS if not today or s != today[-1]]
    return rng.choice(choices)


def stars_for_prompt(world: World) -> str:
    n = stars_due(world)
    return (f"THIS VISIT: {n} star{'s' if n != 1 else ''} out of five, {_STAR_VISIT[n]}. Set stars to {n} and "
            "write the visit that earns them.")


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
