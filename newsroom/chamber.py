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
and asks for a report back, so the hour always has business. A booked motion that can't stand (a story
that isn't open, one twice, a blocked word) gives way to one such stand-in motion, and the rest are kept.
"""
from __future__ import annotations

import logging
import re
from datetime import date, datetime

from . import council, llm, promises, safety, schedule
from .config import CONFIG
from .models import ChamberAgenda, Motion, SegmentType
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
    """Only when The Chamber is what airs at eight on the channel that's on: Channel 8 runs on a council night
    too, and on 2026-11-19 it booked an agenda, votes and all, for a sitting it had no hour for."""
    now = now or schedule.now()
    return (council.council_night(date.fromtimestamp(now)) and tonight(world) is None
            and _at(CONFIG.chamber.commission_from, now) <= now < _at(CONFIG.chamber.airs_at, now)
            and schedule.show_at(_at(CONFIG.chamber.airs_at, now)).id == SHOW)


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
            + "\n".join(_row(world, t) for t in pool)
            + ("\n" + said if (said := promises.for_chamber(world, date.fromisoformat(world.last_date))) else ""))
    try:
        agenda = llm.complete_json("chamber", ChamberAgenda, _SYSTEM, user)
    except llm.LLMError as e:
        log.warning("chamber: no agenda (%s); the stand-in takes tonight", e)
        return _record(world, None)
    return _record(world, _checked(world, agenda))


def _checked(world: World, agenda: ChamberAgenda) -> list[Motion | None]:
    """The agenda's motions, each one that can't stand as None for a stand-in motion to take its place.

    Any open story will do, not only the STORIES list: the briefing shows the model every open story, and on
    2026-11-19 a good agenda was thrown away whole because one motion took the harbour wall survey, open and
    covered 26 times but not among the eight candidates. A made-up or finished story, a story twice, or a
    blocked word (a motion's wording becomes its story's status, read on teletext) loses just that motion."""
    live, taken, out = {t.id for t in world.open_threads()}, set(), []
    for i, m in enumerate(agenda.motions, 1):
        if m.thread_id not in live:
            why = "isn't an open story"
        elif m.thread_id in taken:
            why = "is on the agenda twice"
        elif bad := safety.check(safety.strings(m)):
            why = f"has {bad!r} in it"
        else:
            out.append(m)
            taken.add(m.thread_id)
            continue
        log.warning("chamber: motion %d's story %s %s; a stand-in motion takes its place", i, m.thread_id, why)
        out.append(None)
    return out


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


def _stand_in_motion(world: World, t: Thread, i: int, names: list[str]) -> dict:
    """A motion that notes the story and asks for a report back: business for the hour without a model."""
    nxt = council.next_meetings(date.fromisoformat(world.last_date), 2)[-1]
    return {"thread_id": t.id, "motion": f"That the council notes the latest on {t.title.rstrip('.')} "
                                         "and asks officers to report back to the next meeting",
            "mover": names[i % len(names)],
            "votes": [{"councillor": n, "vote": "abstain" if j == (i + 1) % len(names) else "for",
                       "why": "wants the full report first" if j == (i + 1) % len(names) else "it needs a report"}
                      for j, n in enumerate(names)],
            "if_carried": f"Officers report back to full council on {nxt:%A} {nxt.day} {nxt:%B}.",
            "if_lost": "It goes back to committee.", "public": "", "stand_in": True}


def _record(world: World, booked: list[Motion | None] | None) -> dict:
    """Tonight's sitting: the model's motions in its order, a stand-in motion wherever one is None (all four
    with no booking), from the candidates not already on the agenda."""
    names = [name for name, *_ in council.COUNCILLORS]
    booked = booked if booked is not None else [None] * MOTIONS
    pool = candidates(world) or sorted(world.open_threads(), key=lambda t: -t.mentions)
    spare = iter([t for t in pool if t.id not in {m.thread_id for m in booked if m}])
    motions = []
    for i, m in enumerate(booked):
        if m is None:
            if t := next(spare, None):
                motions.append(_stand_in_motion(world, t, i, names))
            continue
        mover = world.person_by_name(m.mover)
        motions.append({"thread_id": m.thread_id, "motion": m.motion,
                        "mover": mover.name if mover and mover.name in names else names[0],
                        "votes": _votes(world, m.votes), "if_carried": m.if_carried, "if_lost": m.if_lost,
                        "public": m.public})
    entry = {"date": world.last_date, "motions": motions}
    if all(m.get("stand_in") for m in motions):
        entry["stand_in"] = True
    for m in entry["motions"]:
        t = world.thread(m["thread_id"])
        m["title"] = t.title if t else ""
        m.update(count(m["votes"]))
        m["applied"] = False
    with world.lock:
        world.chambers = (world.chambers + [entry])[-30:]
    log.info("chamber: tonight %s%s", " | ".join(
        f"{m['thread_id']} {m['for']}-{m['against']}-{m['abstain']} {'carried' if m['carried'] else 'lost'}"
        + (" (stand-in)" if m.get("stand_in") and not entry.get("stand_in") else "")
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
    return _in_turn(world, brief, motions) if motion_in(brief) is None else _SLOT.sub(motion, brief)


# The officers' reports the council receives without a vote, one each time "{report}" comes round.
REPORTS = ("the harbour office's report on the quay, the moorings and its winter works",
           "the town clerk's report on the council's correspondence and its committees' dates",
           "the treasurer's report on the town's accounts for the quarter")
_ORDINALS = ("first", "second", "third", "fourth", "fifth", "sixth")


def _tonights(world: World) -> list[dict]:
    """What tonight's Chamber has written so far (filed as each item is written, aired or not yet)."""
    with world.lock:
        return [e for e in world.archive if e["date"] == world.last_date and e.get("show") == SHOW
                and e["type"] != SegmentType.ad_break.value]


def _ward(role: str) -> str:
    return role.removeprefix("Councillor, ").split(";")[0]


def _public(world: World, aired: list[dict]) -> list[str]:
    """Who has spoken from the public tonight: the people in tonight's items who don't sit on the council."""
    seats = {council.CHAIR, *(name for name, *_ in council.COUNCILLORS)}
    return list(dict.fromkeys(
        p.name for e in aired for pid in e.get("people", []) if (p := world.person(pid)) and p.name not in seats))


def _in_turn(world: World, brief: str, motions: list[dict]) -> str:
    """A brief from the loop after the agenda, with whose turn it is. The six angles come round two or three
    times in the hour, and word for word the same brief got the same item: on 2026-11-19 Lucy Hammond asked
    about the Cannery shed twice (and a resident a third time), the harbour office accounts were noted twice,
    Jean Corran brought the pool petition three times, and "do NOT do any of these again" stopped none of it.
    So the code takes the turns: "{who}" is the next councillor round the table, "{vote}" the next of
    tonight's motions, "{report}" the next officer's report, "{ward}" the next ward to bring a petition,
    "{story}" the next of the week's stories off the agenda, each counted from the items already written
    with that mark; "{resident}" is somebody who hasn't spoken; and a brief that has been round before is
    told what it made then."""
    aired = _tonights(world)
    turn = lambda mark: sum(1 for e in aired if mark in (e.get("brief") or ""))  # noqa: E731
    out = brief
    if "{who}" in out:
        name, role, *_ = council.COUNCILLORS[turn("{who}") % len(council.COUNCILLORS)]
        out = out.replace("{who}", f"{name} ({_ward(role)})")
    if "{vote}" in out:
        put = [(i, m) for i, m in enumerate(motions) if m.get("applied")]
        if put:
            i, m = put[turn("{vote}") % len(put)]
            out = out.replace("{vote}", f"tonight's {_ORDINALS[i]} vote, on [{m['thread_id']}] {m['title']} "
                                        f"({'carried' if m['carried'] else 'lost'} {m['for']}-{m['against']}, moved "
                                        f"by {m['mover']})")
        else:
            out = out.replace("{vote}", "one of tonight's motions")
    if "{report}" in out:
        out = out.replace("{report}", REPORTS[turn("{report}") % len(REPORTS)])
    if "{ward}" in out:                        # the petitions go round the table the other way from the questions
        wards = [_ward(role) for _, role, *_ in reversed(council.COUNCILLORS)]
        out = out.replace("{ward}", wards[turn("{ward}") % len(wards)])
    if "{story}" in out:                       # a story of the week's that the agenda doesn't have, a new one each time
        agenda = {m["thread_id"] for m in motions}
        pool = sorted((t for t in world.briefing_threads() if t.id not in agenda), key=lambda t: t.id)
        t = pool[turn("{story}") % len(pool)] if pool else None
        out = out.replace("{story}", f"[{t.id}] {t.title}" if t else "one of the week's stories")
    if "{resident}" in out:
        spoke = _public(world, aired)
        out = out.replace("{resident}", "a resident who has not been at the lectern tonight"
                          + (f" (NOT {', '.join(spoke)}, who have spoken)" if spoke else ""))
    before = [e["headline"] for e in aired if e.get("brief") == brief and e.get("headline")]
    if before:
        out += (". This kind of item has come round before tonight, as " + "; ".join(f"\"{h}\"" for h in before)
                + ": do NOT write that again. Something new this time: other people, another subject and its own "
                  "headline, or what has happened in the chamber since")
    return out


def for_prompt(world: World) -> str:
    """The council in session for every item in the show: the members, the agenda, what has happened so far."""
    c = _booked(world)
    # Each motion with where it stands: on 2026-11-19 the links said "three votes settled, bowling green left"
    # three times after the fourth was carried, from an agenda with no results on it and an earlier link to copy.
    voted = [m for m in c["motions"] if m.get("applied")]
    agenda = "\n".join(
        f"  {i + 1}. \"{m['motion']}\" (moved by {m['mover']}) — "
        + (f"VOTED: {'CARRIED' if m['carried'] else 'LOST'} {m['for']}-{m['against']}" if m.get("applied")
           else "not yet voted on")
        for i, m in enumerate(c["motions"]))
    if voted:
        agenda += ("\n  ALL of the agenda has been voted on: no motion is left to come, and nobody says one is."
                   if len(voted) == len(c["motions"]) else
                   f"\n  {len(voted)} of {len(c['motions'])} voted on so far.")
    aired = _tonights(world)
    public = _public(world, aired)
    spoke = ("\nFROM THE PUBLIC ALREADY TONIGHT (anyone new at the lectern or in the gallery is somebody else, from "
             f"another street): {', '.join(public)}" if public else "")
    # "Don't repeat it" wasn't enough: on 2026-11-01 the loop came round three times with the same
    # Gull's Rest debate, the same Christmas-lights petition and the same three vox pops.
    done = ("\nSO FAR TONIGHT (do NOT do any of these again, even when this kind of item comes round: no motion "
            "debated twice, and a different question, petition, report, speaker and subject; a callback is fine):\n"
            + "\n".join(
        f"  - {e['type'].replace('_', ' ')}: {e['headline']}: {e['text'][:SO_FAR_CHARS]}" for e in aired)) if aired else ""
    return (f"FULL COUNCIL IN SESSION, live from the council chamber.\nTHE COUNCIL (speak as speaker \"guest\" with "
            f"guest_name their exact name):\n{_council_rows(world)}\nTONIGHT'S AGENDA, in this order:\n{agenda}"
            f"{promises.for_chamber(world, date.fromisoformat(world.last_date))}{spoke}{done}")


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
    if m["carried"]:                           # what the council voted would follow is now a promise to keep
        promises.record(world, date.fromisoformat(c["date"]), t, m["if_carried"])
    log.info("chamber: motion %d on %s %s %d-%d; next: %s", i + 1, t.id, "carried" if m["carried"] else "lost",
             m["for"], m["against"], t.next_development[:80])
    return t.id


def status_of(world: World, i: int) -> str:
    """The thread's status line for motion `i`'s vote, before it is settled."""
    m = (tonight(world) or {}).get("motions", [])[i]
    return (f"Full council voted {m['for']}-{m['against']}, motion {'carried' if m['carried'] else 'lost'}: "
            f"{m['motion']}")[:160]
