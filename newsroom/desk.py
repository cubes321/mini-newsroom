"""The story desk: makes threads develop instead of repeating.

Every `plan_every_s`, when the worker is idle and the live buffer is healthy,
the desk reads the open threads and returns a plan for a batch of them (the
least recently planned, `[story] batch` per call): a phase for each
(emerging, developing, peak, resolving, closed), the concrete next
development the next follow-up should deliver, who is now involved, and
occasionally a new thread to seed (perhaps from a chat-show guest's loose end)
or two threads to merge as one story. Writers see the NEXT development in their
briefing, so a bulletin that follows up a thread moves it along. The senior
editor's latest memo on the whole board (senior.py) comes after the briefing.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from . import llm, schedule
from .config import CONFIG
from .models import NewThread, StoryPlan
from .world import Thread, World

log = logging.getLogger(__name__)

_SYSTEM = """\
You run the story desk of a small-town TV newsroom in the FICTIONAL town in the briefing. Your job
is to make the town's stories develop plausibly over days, at small-town scale: council decisions,
harbour and market life, schools, weather damage, local characters, the odd mystery. For each open
thread decide its phase and write the concrete NEXT development the next bulletin should report,
tied to a day where relevant ("on Tuesday the part arrives and does not fit"). Involve the named
public figures when natural; they have positions and reputations to keep. Close threads that have
run their course. If there is room, seed one or two new threads with a first status and a planned
next step. Prefer continuity and consequence over novelty. Everything is fiction; never reference
real people or events. Return ONLY JSON.
"""


def should_plan(world: World, now: float | None = None) -> bool:
    now = now or time.time()
    return now - world.last_story_plan_ts >= CONFIG.story.plan_every_s


def batch(world: World) -> list[Thread]:
    """The open threads to plan this call: the least recently planned first.

    Planning every open thread in one reply grew past max_tokens and the timeout
    as the town grew, so each call plans a few and the board rotates.
    """
    open_ = world.open_threads()                   # most recently updated first, kept for ties
    return sorted(open_, key=lambda t: t.planned_ts)[: CONFIG.story.batch]


def _in_turn(p: StoryPlan, todo: list[Thread]) -> int:
    ids = {t.id for t in todo}
    return sum(1 for u in p.updates if u.thread_id in ids)


_BREAKING_RARE = (
    "\n\nBREAKING NEWS is rare: most rounds leave breaking null. Only if something sudden would plausibly "
    "happen in town right now (a fire, a boat in trouble, a burst main, storm damage, a road shut, an animal "
    "loose), set breaking to it as it would first be phoned in. It is a NEW event, not the next step of a "
    "thread, and not also one of new_threads. Small-town scale; nobody badly hurt unless it is essential."
)
_BREAKING_NOW = ("\n\nThe producer has asked for BREAKING NEWS this round: set breaking to something sudden "
                 "that plausibly happens in town right now (not the next step of a thread, not also a new thread).")
_BREAKING_NO = "\n\nbreaking must be null this round."

# The writers often open a running story again under a new title; a title match catches the near
# copies (world.same_story), but on 2026-10-27 "Fire chief says one engine leaves harbour exposed"
# and "Harrow Street Residents Back Call for Second Fire Engine" were their own threads beside the
# fire station's, and the harbour wall ran as four. Telling them apart takes judgement.
_MERGES = (
    "\n\nDUPLICATES: when one story runs as several threads (open or recently faded) under different "
    "titles, merge EVERY duplicate into the one to keep (usually the one covered more): one merge per "
    "duplicate. Only the same story, not merely the same place or the same people."
)


def _memo(world: World) -> str:
    """The senior editor's latest memo on the whole board (senior.py), for the desk to act on."""
    if not world.senior_memo:
        return ""
    return (f"SENIOR EDITOR'S MEMO ({world.senior_memo_at}). The senior editor reviewed the whole board and the "
            f"desk's recent rounds; follow it where it touches this round's threads:\n{world.senior_memo}\n\n")


def _loose_ends(world: World) -> str:
    """The newest things chat-show guests left to ask them: the desk may make one news."""
    ends = world.fresh_loose_ends()
    if not ends:
        return ""
    rows = "\n".join(
        f"  - {p.name} ({p.role}), on {e['show']} on {e['date']}"
        + (f": said {p.memories[-1]['said']}" if p.memories else "") + f"; left to ask: {e['ask']}"
        for p, e in ends)
    return ("\n\nLOOSE ENDS guests left on the chat shows (not news; most never will be):\n" + rows +
            "\nIf one would really make news in a small town, you may seed it as one of the new threads, "
            "with from_guest set to the guest's exact name and the guest among its people.")


def plan(world: World, *, dry: bool = False, breaking: str = "no") -> StoryPlan | None:
    """Ask the desk and apply its plan. Returns None if the model was unavailable, or twice
    planned none of this round's threads (valid JSON, but an empty plan is a failed plan:
    local models did it in the bench). Either way the same batch comes round next time.

    `breaking` is "no", "may" (the desk may break a story itself, rarely) or "now" (asked to):
    the plan's `breaking` is left for the worker, which commissions it (`breaking.from_desk`)."""
    world.last_story_plan_ts = time.time()
    world.fade_threads()
    open_n = len(world.open_threads())
    room = max(0, CONFIG.story.max_open_threads - open_n)
    todo = batch(world)
    faded = world.recently_faded()
    ids = ", ".join(t.id for t in todo) or "(none)"
    user = (
        f"BRIEFING\n{world.summary_for_editor()}\n\n" + _memo(world) +
        f"There are {open_n} open threads. THIS ROUND, plan only these threads: {ids}. The rest get "
        f"their turn later; use them as context only. You may seed at most {min(room, 2)} new ones. "
        "Return phase and NEXT development for each of this round's threads you want to change, close any "
        "that are finished, and list the people now involved (exact names from the briefing where "
        "possible): at most four per thread, three for a new one. A thread GOING QUIET fades off the air "
        "unless it is covered again: give it a NEXT step worth covering, or close it."
        + (f" You may also revive one recently faded thread ({', '.join(t.id for t in faded)}) by giving it "
           "a phase and a NEXT development, but only if something new would really happen." if faded else "")
    ) + _MERGES + _loose_ends(world) + {"may": _BREAKING_RARE, "now": _BREAKING_NOW}.get(breaking, _BREAKING_NO)
    try:
        p = llm.complete_json("story_desk", StoryPlan, _SYSTEM, user)
        if todo and not _in_turn(p, todo):
            log.warning("story desk planned none of %s; asking once more", ids)
            merges = p.merges
            p = llm.complete_json("story_desk", StoryPlan, _SYSTEM, user + (
                f"\n\nYour last reply planned none of this round's threads. Return an update (phase and "
                f"NEXT development) for each of: {ids}."))
            p.merges = p.merges or merges           # the duplicates it found are still duplicates
    except llm.LLMError as e:
        log.warning("story desk unavailable: %s", e)
        return None                                # the same batch comes round again next time
    if todo and not _in_turn(p, todo):
        log.warning("story desk planned none of %s again; that batch comes round next time", ids)
        return None
    if not dry:
        with world.lock:                           # threads are changed in place
            apply(world, p, only={t.id for t in todo} | {t.id for t in faded})
            now = time.time()
            for t in todo:
                t.planned_ts = now
            world.desk_notes = (world.desk_notes + [{
                "at": f"{world.last_date} {datetime.fromtimestamp(schedule.now()):%H:%M}", "planned": [t.id for t in todo],
                "new": len(p.new_threads), "merges": len(p.merges), "note": p.note}])[-12:]
    if breaking == "no":
        p.breaking = None
    log.info("story desk: %d updates, %d new threads (planned %s)%s — %s", len(p.updates), len(p.new_threads),
             ids, f", BREAKING {p.breaking.tip!r}" if p.breaking else "", p.note)
    return p


def _looks_like_a_name(s: str) -> bool:
    """Two or more capitalised words: 'Bea Kowalczyk' yes, 'the council' no."""
    toks = [t for t in s.replace("-", " ").split() if t[:1].isalpha()]
    return sum(1 for t in toks if t[0].isupper()) >= 2


def _resolve_people(world: World, names: list[str]) -> list[str]:
    ids = []
    for name in names:
        person = world.person_by_name(name)
        if person is None:
            if not _looks_like_a_name(name):
                log.info("story desk named %r; not a person, skipping", name)
                continue
            person = world.ensure_person(name, None)
            if person is None:
                continue                            # a presenter: on air already, not one of the people
        ids.append(person.id)
    return ids


def apply(world: World, p: StoryPlan, only: set[str] | None = None) -> None:
    with world.lock:                               # changes the threads it is handed in place
        _apply(world, p, only)


def _apply(world: World, p: StoryPlan, only: set[str] | None) -> None:
    for m in p.merges:                             # first, so an update can't reopen a duplicate
        if world.merge_thread(m.duplicate, m.into):
            log.info("story desk merged thread %s into %s: %s", m.duplicate, m.into, world.thread(m.into).title[:60])
        else:
            log.info("story desk merge %s into %s skipped (not two live threads)", m.duplicate, m.into)
    for u in p.updates:
        t = world.thread(u.thread_id)
        if t is None:
            log.warning("story desk named unknown thread %r", u.thread_id)
            continue
        if t.merged_into:
            log.info("story desk planned %s, merged into %s; skipping", t.id, t.merged_into)
            continue
        if only is not None and t.id not in only:
            log.info("story desk planned %s out of turn; skipping", t.id)
            continue
        if t.phase == "faded" and u.phase != "closed":
            t.moved_ts = schedule.now()             # revived: a full window before it can fade again
            log.info("story desk revived faded thread %s", t.id)
        t.phase = u.phase
        t.next_development = u.next_development.strip()
        t.updated = world.last_date if u.phase == "closed" else t.updated
        for pid in _resolve_people(world, u.people):
            if pid not in t.people:
                t.people.append(pid)
        log.info("thread %s -> %s; next: %s", t.id, t.phase, t.next_development[:80])
    room = CONFIG.story.max_open_threads - len(world.open_threads())
    for nt in p.new_threads[: max(0, room)]:
        seed(world, nt)


def seed(world: World, nt: NewThread, who: str = "story desk") -> Thread:
    """Open a new thread from a plan, with its people, and spend the guest's loose end it grew from."""
    people = _resolve_people(world, nt.people)
    guest = world.loose_ends_taken(nt.from_guest) if nt.from_guest else None
    if nt.from_guest and guest is None:
        log.info("%s seeded from %r's loose end, but nobody has that name", who, nt.from_guest)
    if guest is not None and guest.id not in people:
        people.insert(0, guest.id)                 # their loose end is news now, not a chat to come
    t = world.seed_thread(nt.title, nt.status, nt.next_development, people)
    log.info("seeded thread %s: %s%s", t.id, t.title, f" (from {guest.name}'s loose end)" if guest else "")
    return t


def _cli(argv: list[str]) -> int:
    import argparse

    from . import world as world_mod

    ap = argparse.ArgumentParser(prog="python -m newsroom.desk")
    ap.add_argument("cmd", choices=["plan"])
    ap.add_argument("--dry", action="store_true", help="show the plan without applying it")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    w = world_mod.load()
    p = plan(w, dry=a.dry)
    if p is None:
        return 1
    print(p.model_dump_json(indent=2))
    if not a.dry:
        world_mod.save(w)
        print("\n--- applied; open threads now:")
        for t in w.open_threads():
            print(f"  [{t.id}] {t.phase:<10} {t.title}  NEXT: {t.next_development}")
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
