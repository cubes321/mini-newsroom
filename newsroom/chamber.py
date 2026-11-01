"""The Chamber: full council, live, from 20:00 to 21:00 on council nights (docs/SHOWS.md, council.py).

From `[chamber] commission_from`, in idle time, the back office books tonight's agenda: four motions
from the stories due at council, who moves each, and how every councillor votes and why, by their
leanings. The result is counted here (a tie goes to the mayor's casting vote, against the motion by
convention), so a debate is written towards a vote already cast and never contradicts the councillors'
positions. When a motion's debate is written its thread takes the result: the vote as its latest
status, what happens next as its NEXT development, and resolving if carried. Until then the desk
leaves the agenda's threads alone, so a motion still matches its story when it comes up.

Helen Strand chairs; the councillors are council.py's. Dana is in the press seats and Miles in the
public gallery. If nothing was booked by 20:00, a stand-in agenda notes the four most-covered stories
and asks for a report back, so the hour always has business.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime

from . import council, llm, schedule
from .config import CONFIG
from .models import ChamberAgenda, SegmentType
from .world import Thread, World

log = logging.getLogger(__name__)

SHOW = "chamber"
MOTIONS = 4
CANDIDATES = 8
SO_FAR_CHARS = 220
_DUE = re.compile(r"council|committee|councillor|vote|mayor|planning|budget|tender|consultation|by-?law", re.I)
_SLOT = re.compile(r"\{m(\d)\}")

_SYSTEM = """\
You book THE CHAMBER: full council, live, on a small-town TV station in the FICTIONAL town in the
briefing. Helen Strand, the mayor, chairs; the six councillors in THE COUNCIL vote. Choose FOUR motions
from the STORIES, the ones the council would really decide on tonight (money, a contract, a closure, a
by-law, a date fixed, a report accepted), each written as the clerk reads it ("That the council ...").
For each, the councillor who moves it, and EVERY councillor's vote (for, against or abstain) with a
one-line reason, true to their ward and leaning: they don't all agree, and a motion may be lost. Then
what happens next if it is carried and if it is lost, each a dated step, and a member of the public who
would speak on it. Small-town scale; nobody accused of anything the record doesn't show. Everything is
fiction. Return ONLY JSON.
"""


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def tonight(world: World) -> dict | None:
    return next((c for c in reversed(world.chambers) if c.get("date") == world.last_date), None)


def should_commission(world: World, now: float | None = None) -> bool:
    now = now or schedule.now()
    return (council.council_night(date.fromtimestamp(now)) and tonight(world) is None
            and _at(CONFIG.chamber.commission_from, now) <= now < _at(CONFIG.chamber.airs_at, now))


def candidates(world: World) -> list[Thread]:
    """Open stories, those heading for the council first (their NEXT or status says so), then by coverage."""
    def due(t: Thread) -> bool:
        return bool(_DUE.search(f"{t.next_development} {t.status} {t.title}"))
    return sorted(world.open_threads(), key=lambda t: (not due(t), -t.mentions))[:CANDIDATES]


def on_agenda(world: World) -> set[str]:
    """Tonight's motions' threads whose votes haven't been taken: the desk leaves them be until then."""
    c = tonight(world)
    return {m["thread_id"] for m in c["motions"] if not m.get("applied")} if c else set()


def _row(world: World, t: Thread) -> str:
    people = ", ".join(p.name for pid in t.people if (p := world.person(pid))) or "nobody named yet"
    return (f"  - [{t.id}] {t.title} ({t.phase}, covered {t.mentions}x): {t.status}"
            + (f" Planned next: {t.next_development}" if t.next_development else "") + f" People: {people}.")


def _council_rows(world: World) -> str:
    rows = [f"  - {p.name}, {p.role}: {p.notes}" for p in council.who(world)]
    return f"  - {council.CHAIR}, Mayor, in the chair (the casting vote on a tie)\n" + "\n".join(rows)


def commission(world: World) -> dict:
    """Book tonight's agenda and votes (the model, or the stand-in if it fails) and record them."""
    pool = candidates(world)
    if not pool:
        return _record(world, None)
    user = (f"BRIEFING\n{world.summary_for_editor()}\n\nTHE COUNCIL:\n{_council_rows(world)}\n\nSTORIES:\n"
            + "\n".join(_row(world, t) for t in pool))
    try:
        agenda = llm.complete_json("chamber", ChamberAgenda, _SYSTEM, user)
    except llm.LLMError as e:
        log.warning("chamber: no agenda (%s); the stand-in takes tonight", e)
        return _record(world, None)
    ids = [m.thread_id for m in agenda.motions]
    if len(set(ids)) < len(ids) or not set(ids) <= {t.id for t in pool}:
        log.warning("chamber: agenda named %s, not four different stories from the list; the stand-in takes tonight", ids)
        return _record(world, None)
    return _record(world, agenda)


def count(votes: list[dict]) -> dict:
    """The result: carried on more for than against; a tie goes to the chair's casting vote, against."""
    n = {k: sum(1 for v in votes if v["vote"] == k) for k in ("for", "against", "abstain")}
    return {**n, "carried": n["for"] > n["against"], "casting": n["for"] == n["against"]}


def _votes(world: World, cast: list) -> list[dict]:
    """One vote per councillor, in council order: a name the model got wrong is dropped, a councillor
    it left out abstains."""
    by = {}
    for v in cast:
        p = world.person_by_name(v.councillor)
        if p and p.name not in by:
            by[p.name] = {"councillor": p.name, "vote": v.vote, "why": v.why}
    return [by.get(name, {"councillor": name, "vote": "abstain", "why": "did not speak to it"})
            for name, *_ in council.COUNCILLORS]


def _record(world: World, agenda: ChamberAgenda | None) -> dict:
    names = [name for name, *_ in council.COUNCILLORS]
    if agenda is None:
        pool = candidates(world) or sorted(world.open_threads(), key=lambda t: -t.mentions)
        nxt = council.next_meetings(date.fromisoformat(world.last_date), 2)[-1]
        motions = [{"thread_id": t.id, "motion": f"That the council notes the latest on {t.title.rstrip('.')} "
                                                 "and asks officers to report back to the next meeting",
                    "mover": names[i % len(names)],
                    "votes": [{"councillor": n, "vote": "abstain" if j == (i + 1) % len(names) else "for",
                               "why": "wants the full report first" if j == (i + 1) % len(names) else "it needs a report"}
                              for j, n in enumerate(names)],
                    "if_carried": f"Officers report back to full council on {nxt:%A} {nxt.day} {nxt:%B}.",
                    "if_lost": "It goes back to committee.", "public": ""}
                   for i, t in enumerate(pool[:MOTIONS])]
        entry = {"date": world.last_date, "stand_in": True, "motions": motions}
    else:
        motions = []
        for m in agenda.motions:
            mover = world.person_by_name(m.mover)
            motions.append({"thread_id": m.thread_id, "motion": m.motion,
                            "mover": mover.name if mover and mover.name in names else names[0],
                            "votes": _votes(world, m.votes), "if_carried": m.if_carried, "if_lost": m.if_lost,
                            "public": m.public})
        entry = {"date": world.last_date, "motions": motions}
    for m in entry["motions"]:
        t = world.thread(m["thread_id"])
        m["title"] = t.title if t else ""
        m.update(count(m["votes"]))
        m["applied"] = False
    with world.lock:
        world.chambers = (world.chambers + [entry])[-30:]
    log.info("chamber: tonight %s%s", " | ".join(
        f"{m['thread_id']} {m['for']}-{m['against']}-{m['abstain']} {'carried' if m['carried'] else 'lost'}"
        for m in entry["motions"]), " (stand-in)" if entry.get("stand_in") else "")
    return entry


def _booked(world: World) -> dict:
    return tonight(world) or _record(world, None)    # nothing booked by 20:00: the stand-in, recorded once, no call


def motion_in(brief: str) -> int | None:
    """Which motion an item's brief is about: "{m2}" is the second (its index, from 0)."""
    m = _SLOT.search(brief or "")
    return int(m.group(1)) - 1 if m else None


def _result(m: dict) -> str:
    names = {k: [v["councillor"] for v in m["votes"] if v["vote"] == k] for k in ("for", "against", "abstain")}
    tally = "; ".join(f"{len(names[k])} {k if k != 'abstain' else 'abstaining'}"
                      + (f" ({', '.join(names[k])})" if names[k] else "") for k in ("for", "against", "abstain"))
    how = (" — a tie: Helen Strand's casting vote goes against, by convention, so it is LOST" if m["casting"]
           else ": CARRIED" if m["carried"] else ": LOST")
    return tally + how


def brief_for(world: World, brief: str) -> str:
    """An item's brief with its motion in full: "{m2}" becomes the second motion, who moves it, how every
    councillor votes and why, the result Helen Strand reads out, and the member of the public."""
    motions = _booked(world)["motions"]

    def motion(mt: re.Match) -> str:
        i = int(mt.group(1)) - 1
        if i >= len(motions):
            return "any other business (no vote is taken)"
        m = motions[i]
        whys = "; ".join(f"{v['councillor']}: {v['vote']}, {v['why']}" for v in m["votes"])
        return (f"\"{m['motion']}\" on [{m['thread_id']}] {m['title']}, moved by {m['mover']}. HOW THEY VOTE: {whys}. "
                f"THE RESULT, which Helen Strand reads out exactly: {_result(m)}. What follows: "
                f"{(m['if_carried'] if m['carried'] else m['if_lost']).rstrip('.')}"
                + (f". From the public: {m['public'].rstrip('.')}" if m.get("public") else ""))
    return _SLOT.sub(motion, brief)


def for_prompt(world: World) -> str:
    """The council in session for every item in the show: the members, the agenda, what has happened so far."""
    c = _booked(world)
    agenda = "\n".join(f"  {i + 1}. \"{m['motion']}\" (moved by {m['mover']})" for i, m in enumerate(c["motions"]))
    with world.lock:
        aired = [e for e in world.archive if e["date"] == world.last_date and e.get("show") == SHOW
                 and e["type"] != SegmentType.ad_break.value]
    done = ("\nSO FAR TONIGHT (don't repeat it; build on it):\n" + "\n".join(
        f"  - {e['type'].replace('_', ' ')}: {e['headline']}: {e['text'][:SO_FAR_CHARS]}" for e in aired)) if aired else ""
    return (f"FULL COUNCIL IN SESSION, live from the council chamber.\nTHE COUNCIL (speak as speaker \"guest\" with "
            f"guest_name their exact name):\n{_council_rows(world)}\nTONIGHT'S AGENDA, in this order:\n{agenda}{done}")


def settle(world: World, i: int) -> str | None:
    """Motion `i`'s vote goes to its story, once: what follows is its NEXT development, and a carried
    motion starts it resolving (the caller files the beat, with `status_of`). Returns the thread id, or
    None if there is nothing to settle."""
    c = tonight(world)
    if not c or i >= len(c["motions"]) or c["motions"][i].get("applied"):
        return None
    m = c["motions"][i]
    t = world.thread(m["thread_id"])
    if t is None:
        return None
    with world.lock:
        t.next_development = (m["if_carried"] if m["carried"] else m["if_lost"])[:200]
        if m["carried"] and t.phase in ("emerging", "developing", "peak"):
            t.phase = "resolving"
        m["applied"] = True
    log.info("chamber: motion %d on %s %s %d-%d; next: %s", i + 1, t.id, "carried" if m["carried"] else "lost",
             m["for"], m["against"], t.next_development[:80])
    return t.id


def status_of(world: World, i: int) -> str:
    """The thread's status line for motion `i`'s vote, before it is settled."""
    m = (tonight(world) or {}).get("motions", [])[i]
    return (f"Full council voted {m['for']}-{m['against']}, motion {'carried' if m['carried'] else 'lost'}: "
            f"{m['motion']}")[:160]
