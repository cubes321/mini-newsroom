"""Have Your Say: Jonah Pike's news phone-in at 10:00 (docs/SHOWS.md).

From `[phonein] commission_from`, in idle time, the back office picks one question from the day's news,
the studio guest at the heart of it (an official, or someone in the story), where they stand, and the
kinds of caller who will ring, each with a different view. Every item then gets the booking, what has
been said so far, and people who have rung before (on earlier days) who may ring again. Each call takes
the next kind of caller in turn, so the hour isn't twelve people saying the same thing. If nothing was
booked in time, a stand-in is made in code from the most-covered story of the day.
"""
from __future__ import annotations

import logging
from datetime import datetime

from . import llm, schedule
from .config import CONFIG
from .models import PhoneInBooking, SegmentType
from .world import Person, Thread, World

log = logging.getLogger(__name__)

SHOW = "phonein"
CALLED = "Have Your Say, on the phone"   # how a caller's memory names the show (the studio guest's says "Have Your Say")
NUMBER = "oh one six three two, nine six oh, seven oh seven"   # the drama range: no real line
STORIES = 6
SO_FAR_CHARS = 220
RINGS_BACK = 3                  # earlier callers offered to ring again

STAND_IN_CALLERS = (
    "someone it affects directly, who is cross and wants to know who decides",
    "someone who thinks it is a fuss about nothing and says so",
    "an older resident who remembers the last time something like this happened",
    "a parent thinking about what it means for their children",
    "someone who runs a business and is counting the cost",
    "someone with a practical idea nobody seems to have tried",
)

_SYSTEM = """\
You book HAVE YOUR SAY, an hour-long news phone-in on a small-town TV station in the FICTIONAL town in
the briefing, presented by Jonah Pike. Choose ONE question from today's STORIES that people in town
genuinely answer differently (money, who decides, what the town should keep or change), phrased as
Jonah would put it to viewers; and the studio guest at the heart of that story who will answer callers,
by an exact name from PEOPLE (an official or someone in the story), with where they stand in one
sentence, consistent with the briefing. Then four to six kinds of caller who will ring, each with a
different view and a different stake (who they are and what they think, one line each), so the hour
hears the whole town and not one side. Everything is fiction. Return ONLY JSON.
"""


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def today(world: World) -> dict | None:
    return next((p for p in reversed(world.phone_ins) if p.get("date") == world.last_date), None)


def should_commission(world: World, now: float | None = None) -> bool:
    now = now or schedule.now()
    return today(world) is None and _at(CONFIG.phonein.commission_from, now) <= now < _at(CONFIG.phonein.airs_at, now)


def _stories(world: World) -> list[Thread]:
    """The day's news: stories that moved today first, then by coverage."""
    return sorted(world.open_threads(), key=lambda t: (t.updated != world.last_date, -t.mentions))[:STORIES]


def _people(world: World, stories: list[Thread]) -> list[Person]:
    """The public figures, and anyone named in the stories on offer."""
    named = {pid for t in stories for pid in t.people}
    return [p for p in world.people if p.kind in ("official", "worthy") or p.id in named]


def commission(world: World) -> dict:
    """Choose today's question, guest and callers (the model, or the stand-in if it fails) and record them."""
    stories = _stories(world)
    if not stories:
        return _record(world, None)
    people = _people(world, stories)
    user = (f"BRIEFING\n{world.summary_for_editor()}\n\nSTORIES:\n"
            + "\n".join(f"  - [{t.id}] {t.title} ({t.phase}, covered {t.mentions}x): {t.status}"
                        + (" People: " + ", ".join(p.name for pid in t.people if (p := world.person(pid))) + "."
                           if t.people else "") for t in stories)
            + "\n\nPEOPLE:\n" + "\n".join(f"  - {p.name}, {p.role} ({p.kind})" for p in people)
            + "\n\nRecent questions: " + (" | ".join(p["question"] for p in world.phone_ins[-5:]) or "none yet"))
    try:
        b = llm.complete_json("phonein", PhoneInBooking, _SYSTEM, user)
    except llm.LLMError as e:
        log.warning("phonein: no booking (%s); the stand-in takes today", e)
        return _record(world, None)
    if b.thread_id not in {t.id for t in stories} or not any(p.name == b.guest for p in people):
        log.warning("phonein: booking named %r and %r, not from the lists; the stand-in takes today",
                    b.thread_id, b.guest)
        return _record(world, None)
    return _record(world, b)


def _record(world: World, b: PhoneInBooking | None) -> dict:
    if b is None:
        stories = _stories(world)
        t = stories[0] if stories else None
        people = [p for pid in t.people if (p := world.person(pid))] if t else []
        guest = next((p for p in people if p.kind == "official"), None) or next(
            (p for p in world.people if p.kind == "official"), None)
        entry = {"date": world.last_date, "stand_in": True, "thread_id": t.id if t else None,
                 "question": (f"What do you make of {t.title.rstrip('.')}?" if t else
                              "What would you change about Port Wexley?")[:120],
                 "guest": guest.name if guest else "", "guest_stance": f"speaks as {guest.role}" if guest else "",
                 "callers": list(STAND_IN_CALLERS)}
    else:
        entry = {"date": world.last_date, **b.model_dump()}
    with world.lock:
        world.phone_ins = (world.phone_ins + [entry])[-30:]
    log.info("phonein: today %r on %s, guest %s%s", entry["question"][:70], entry["thread_id"],
             entry["guest"] or "none", " (stand-in)" if entry.get("stand_in") else "")
    return entry


def _rang_before(world: World) -> list[Person]:
    """People who rang on an earlier day, the most recent first, who haven't rung today."""
    out = []
    for p in world.people:
        rang = [m for m in p.memories if m.get("show") == CALLED]
        if rang and all(m["date"] != world.last_date for m in rang):
            out.append((rang[-1]["date"], p))
    return [p for _, p in sorted(out, key=lambda r: r[0], reverse=True)][:RINGS_BACK]


def for_prompt(world: World, seg_type: SegmentType | None = None) -> str:
    """Today's booking for every item in the show, with what has been said so far. A call also gets the
    next kind of caller in turn, and the people who have rung on earlier days."""
    s = today(world) or _record(world, None)          # nothing booked by 10:00: the stand-in, recorded once, no call
    guest = world.person_by_name(s["guest"])
    with world.lock:
        aired = [e for e in world.archive if e["date"] == world.last_date and e.get("show") == SHOW
                 and e["type"] != SegmentType.ad_break.value]
    calls = sum(e["type"] == SegmentType.call.value for e in aired)
    out = (f"TODAY'S QUESTION: \"{s['question']}\"" + (f" (thread [{s['thread_id']}])" if s["thread_id"] else "")
           + (f"\nTHE STUDIO GUEST, in the armchair all hour: {s['guest']}" + (f", {guest.role}" if guest else "")
              + f": {s['guest_stance']}" if s["guest"] else "\nNo studio guest today: Jonah answers callers himself.")
           + f"\nThe number to ring: {NUMBER}.")
    if aired:
        out += ("\nSAID SO FAR THIS MORNING (don't repeat it; a caller may answer an earlier one):\n" + "\n".join(
            f"  - {e['type'].replace('_', ' ')}: {e['headline']}: {e['text'][:SO_FAR_CHARS]}" for e in aired[-10:]))
    if seg_type is SegmentType.call:
        kinds = s["callers"]
        out += f"\nTHIS CALLER (call {calls + 1} of the morning): {kinds[calls % len(kinds)]}."
        if calls >= len(kinds):     # the second lap echoed the first (2026-10-30): someone new, a new point
            out += (" That kind of caller has rung already this morning: this is SOMEONE ELSE with that stake, "
                    "never the person named, with a point of their own that nobody in SAID SO FAR has made.")
        rang = [p.name for p in world.people if any(m.get("show") == CALLED and m["date"] == world.last_date
                                                    for m in p.memories)]
        if rang:                    # Tomas Reid at call six came back as Tomas Reilly at call twelve
            out += (f"\nRUNG ALREADY THIS MORNING: {', '.join(rang)}. A new caller has a name unlike all of "
                    "these, first name and surname.")
        back = _rang_before(world)
        if back:
            out += ("\nPEOPLE WHO HAVE RUNG BEFORE (at most one call in four is one of them, ringing again; keep "
                    "to what they said then):\n" + "\n".join(
                        f"  - {p.name}: {next(m['said'] for m in reversed(p.memories) if m.get('show') == CALLED)}"
                        for p in back))
    if s["thread_id"]:
        out += f"\nEverything is on today's question: set thread_id to \"{s['thread_id']}\"."
    return out
