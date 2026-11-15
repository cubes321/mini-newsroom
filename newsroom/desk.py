"""The story desk: makes threads develop instead of repeating.

Every `plan_every_s`, when the worker is idle and the live buffer is healthy,
the desk reads the open threads and returns a plan for a batch of them (those
something has changed for since they were last planned, the least recently
planned first, `[story] batch` per call): a phase for each
(emerging, developing, peak, resolving, closed), the concrete next
development the next follow-up should deliver, who is now involved, and
occasionally a new thread to seed (perhaps from a chat-show guest's loose end)
or two threads to merge as one story. Writers see the NEXT development in their
briefing, so a bulletin that follows up a thread moves it along. The senior
editor's latest memo on the whole board (senior.py) comes after the briefing.

A story waiting in the running-stories pool is off the rounds until its day, with one exception: when the
senior editor's memo names it, it is put within the desk's reach once (`reach`), so that it can be moved
to another day or closed. On the night of 2026-11-14 four memos running asked for four stories to come
off a Monday that had eight due, and nothing could move them: the desk never saw them, and the senior
editor only writes the memo.
"""
from __future__ import annotations

import logging
import re
import time
from datetime import date, datetime

from . import chamber, llm, meeting, promises, safety, schedule
from .config import CONFIG
from .models import NewThread, StoryPlan, ThreadUpdate
from .world import STALE_WARNING_S, THREAD_PEOPLE, Thread, World, due_date, fade_after_s, said_date

log = logging.getLogger(__name__)

_SYSTEM = """\
You run the story desk of a small-town TV newsroom in the FICTIONAL town in the briefing. Your job
is to make the town's stories develop plausibly over days, at small-town scale: council decisions,
harbour and market life, schools, weather damage, local characters, the odd mystery. For each open
thread decide its phase and write the concrete NEXT development the next bulletin should report,
tied to a day where relevant ("on Tuesday the part arrives and does not fit"). A story that meets a
day in the briefing's "Coming up" (a town event, a council meeting, a match) may be set for that day,
by its day and date ("on Thursday 5 November, Bonfire Night, the new barriers are tried out"); never
for an event that isn't listed. A long story whose next step is days away waits for that day in the
running-stories pool, off the bulletins (the board marks it WAITING); give it a dated NEXT rather than
holding it or closing it. Involve the named
public figures when natural; they have positions and reputations to keep. Close threads that have
run their course. If there is room, seed one or two new threads with a first status and a planned
next step. Prefer continuity and consequence over novelty. Everything is fiction; never reference
real people or events. Return ONLY JSON.
"""


def seed_room(world: World, open_n: int) -> int:
    """New stories the desk may seed this round: two while the board is thin, else one, within the
    day's allowance (shared with the senior editor)."""
    return min(2 if open_n < CONFIG.story.thin_board else 1, world.seeds_left())


def should_plan(world: World, now: float | None = None) -> bool:
    now = now or time.time()
    return now - world.last_story_plan_ts >= CONFIG.story.plan_every_s


_THREAD_ID = re.compile(r"\bt\d+\b")


def seen(world: World, t: Thread) -> str:
    """What the desk has in front of it for a story: the day, how often it has aired, when it last moved
    (on air, back from the pool, breaking), the senior editor's memo if it names the story, and whether
    it is going quiet. The desk plans a story again only when this has changed since it last did
    (`Thread.planned_seen`).

    Until 2026-11-15 a board no bigger than the batch was planned whole every half hour: on the night of
    2026-11-14 t484 and t513 were planned in 22 rounds of 24, eight rounds running overnight with nothing
    aired in between, and the senior editor wrote "the desk has replanned the same four threads for eight
    rounds; stop restating them". Compared for equality, never ordered: `moved_ts` is on the broadcast
    clock and `planned_ts` on the real one."""
    named = t.id in _THREAD_ID.findall(world.senior_memo or "")
    quiet = bool(t.moved_ts) and fade_after_s(t) - (schedule.now() - t.moved_ts) < STALE_WARNING_S
    return "|".join((world.last_date, str(t.mentions), f"{t.moved_ts:.0f}", world.senior_memo_at if named else "",
                     "going quiet" if quiet else ""))


def batch(world: World) -> list[Thread]:
    """The open threads to plan this call: those something has changed for (`seen`), the least recently
    planned first.

    Planning every open thread in one reply grew past max_tokens and the timeout
    as the town grew, so each call plans a few and the board rotates.
    """
    # Tonight's council motions wait for their votes (chamber.py): a NEXT rewritten after the booking
    # would leave a motion about a story that has moved on.
    agenda = chamber.on_agenda(world)
    # A story waiting in the running-stories pool is planned again on its day (world.pool_threads), or
    # sooner if the senior editor's memo names it (reach).
    open_ = [t for t in world.board_threads()                          # most recently updated first, kept for ties
             if t.id not in agenda and t.planned_seen != seen(world, t)]
    return sorted(open_, key=lambda t: t.planned_ts)[: CONFIG.story.batch]


def reach(world: World) -> list[Thread]:
    """The stories waiting in the pool that the senior editor's latest memo names, the soonest due first:
    within the desk's reach this round beside its batch, to be moved to another day or closed. Each is
    offered once a memo (the desk stamps it planned); if the memo still wants it moved, the next one says
    so and it is offered again. Not part of the batch: a round that rightly leaves them all alone is not
    an empty plan."""
    if not world.senior_memo:
        return []
    named = set(_THREAD_ID.findall(world.senior_memo))
    agenda = chamber.on_agenda(world)
    return [t for t in world.waiting_threads() if t.id in named and t.id not in agenda
            and t.planned_ts < world.last_senior_ts][: CONFIG.story.batch]


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
            f"desk's recent rounds; follow it where it touches the threads within reach this round:\n{world.senior_memo}\n\n")


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

    With nothing to do (no story changed since it was planned, none within reach from the pool, no room
    for a new one, no breaking news asked for) no call is made: an empty plan comes back, and the round
    leaves no note for the senior editor.

    `breaking` is "no", "may" (the desk may break a story itself, rarely) or "now" (asked to):
    the plan's `breaking` is left for the worker, which commissions it (`breaking.from_desk`)."""
    world.last_story_plan_ts = time.time()
    world.fade_threads()
    promises.lapse(world, date.fromisoformat(world.last_date))   # after the fade: a faded story's promise goes with it
    open_n = len(world.board_threads())           # the pool's waiting stories leave room for new ones
    room = seed_room(world, open_n)
    todo = batch(world)
    also = reach(world)
    if not todo and not also and not room and breaking == "no":
        # Before the prompt is built: the editors' meeting counts each showing of its offered story.
        log.info("story desk: nothing has changed for any story on the board since it was planned; no call")
        return StoryPlan(note="Nothing has changed since the last round: no call made.")
    faded = world.recently_faded()
    ids = ", ".join(t.id for t in todo) or "(none)"
    pool_ids = ", ".join(t.id for t in also)
    user = (
        f"BRIEFING\n{world.summary_for_editor()}\n\n" + _memo(world) + meeting.for_desk(world, offer=not dry) +
        f"{schedule.clock_line(schedule.now())} A NEXT development dated today must come after now; a "
        "thread whose event is over moves on to how it went, or closes.\n\n"
        f"There are {open_n} open threads. THIS ROUND, plan only these threads: {ids}. The rest get "
        f"their turn later; use them as context only. You may seed at most {room} new "
        f"{'story' if room == 1 else 'stories'}, only if something would really happen. "
        "Return phase and NEXT development for each of this round's threads you want to change, close any "
        "that are finished, and list the people now involved (exact names from the briefing where "
        "possible): at most four per thread, three for a new one. A thread GOING QUIET fades off the air "
        "unless it is covered again: give it a NEXT step worth covering, or close it."
        + (f" You may also revive one recently faded thread ({', '.join(t.id for t in faded)}) by giving it "
           "a phase and a NEXT development, but only if something new would really happen." if faded else "")
        # Action first: worded as "leave each as it is unless...", the desk left them all (rehearsal, 2026-11-15).
        + (f"\n\nALSO WITHIN REACH this round: {pool_ids}. They are WAITING in the running-stories pool and "
           "the senior editor's memo names them; this is the one round you can change them before the next "
           "memo. Where the memo asks for one to go to another day, move it now: return its phase and a NEXT "
           "that opens with the new day and date (\"On Monday 23 November ...\") and names no other date, and "
           "it waits in the pool for that day instead. Where the memo asks for one to be closed now, close "
           "it. Return no update for the others: they keep their day." if also else "")
    ) + _MERGES + _loose_ends(world) + promises.for_desk(world, date.fromisoformat(world.last_date), {
        t.id for t in todo}) + {"may": _BREAKING_RARE, "now": _BREAKING_NOW}.get(breaking, _BREAKING_NO)
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
    if bad := safety.check(safety.strings(p)):     # its titles reach teletext and notices unvoiced
        log.warning("story desk plan has %r in it; that batch comes round next time", bad)
        return None
    if not dry:
        with world.lock:                           # threads are changed in place
            apply(world, p, only={t.id for t in todo} | {t.id for t in faded}, reach={t.id for t in also})
            now = time.time()
            for t in todo + also:                  # a pooled story is offered once a memo (reach)
                t.planned_ts = now
                t.planned_seen = seen(world, t)    # after the plan is applied: a revival restarts its fade clock
            world.desk_notes = (world.desk_notes + [{
                "at": f"{world.last_date} {datetime.fromtimestamp(schedule.now()):%H:%M}", "planned": [t.id for t in todo],
                "pool": [t.id for t in also],
                "new": len(p.new_threads), "merges": len(p.merges), "note": p.note}])[-12:]
        meeting.offer_seeded(world, p.new_threads)     # a story the editors' meeting offered, if the desk took it
    if breaking == "no":
        p.breaking = None
    log.info("story desk: %d updates, %d new threads (planned %s%s)%s — %s", len(p.updates), len(p.new_threads),
             ids, f"; from the pool {pool_ids}" if also else "",
             f", BREAKING {p.breaking.tip!r}" if p.breaking else "", p.note)
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


def apply(world: World, p: StoryPlan, only: set[str] | None = None, reach: set[str] | None = None) -> None:
    """`only` is the round's threads (and the faded ones it may revive); `reach` the pooled stories the
    memo put within reach, which may be re-dated or closed but settle no promises."""
    with world.lock:                               # changes the threads it is handed in place
        _apply(world, p, only, reach or set())


def _redate(world: World, t: Thread, u: ThreadUpdate) -> ThreadUpdate | None:
    """A waiting story's new day, from the NEXT the desk gave it: the update to apply, or None to leave
    the story as it is. `world.pool_threads` leaves a story already in the pool alone, so the date is
    moved here.

    A NEXT that names no day, or one gone by, is refused: it would put a long story back on every
    bulletin with nothing new, which is what the pool is for. A story closed with its ending still to
    come ("close t462 at the fender sign-off", and the desk closed it two days early in the rehearsal of
    2026-11-15) is not closed: it waits for that day as resolving, so the ending is reported first."""
    today = date.fromisoformat(world.last_date)
    due = due_date(u.next_development, today)
    if u.phase == "closed":
        if due is None or due <= today:
            t.waits_until = ""
            return u
        log.info("thread %s is to close on %s, not before: resolving, and it waits for that day", t.id, said_date(due))
        u = u.model_copy(update={"phase": "resolving"})
    if due is None or due < today:
        log.info("story desk gave waiting thread %s a NEXT with no day to come; left in the pool until %s",
                 t.id, said_date(t.waits_until))
        return None
    if due == today:
        log.info("thread %s brought out of the pool today (was %s)", t.id, said_date(t.waits_until))
        t.waits_until, t.moved_ts = "", schedule.now()          # a fresh start on the fade timer
    elif due.isoformat() != t.waits_until:
        log.info("thread %s moved in the pool: %s -> %s", t.id, said_date(t.waits_until), said_date(due))
        t.waits_until = due.isoformat()
    return u


def _apply(world: World, p: StoryPlan, only: set[str] | None, reach: set[str]) -> None:
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
        if only is not None and t.id not in only and t.id not in reach:
            log.info("story desk planned %s out of turn; skipping", t.id)
            continue
        if world.waiting(t) and (u := _redate(world, t, u)) is None:
            continue
        if t.phase == "faded" and u.phase != "closed":
            t.moved_ts = schedule.now()             # revived: a full window before it can fade again
            log.info("story desk revived faded thread %s", t.id)
        t.phase = u.phase
        t.next_development = u.next_development.strip()
        t.updated = world.last_date if u.phase == "closed" else t.updated
        # The desk's list replaces the old one: appended to, "at most four" could never shrink a list, and
        # t220 kept 22 names through eight senior editor memos asking for three (2026-10-31).
        named = list(dict.fromkeys(_resolve_people(world, u.people)))
        if named:
            t.people = named[:THREAD_PEOPLE]
        log.info("thread %s -> %s; next: %s", t.id, t.phase, t.next_development[:80])
    for v in p.promises:                           # a verdict needs its story planned this round to match
        mine = next((pr for pr in promises.open_(world) if pr["id"] == v.id), None)
        if mine is None or (only is not None and mine["thread_id"] not in only):
            log.info("story desk settled promise %r, not an open one on this round's threads; skipping", v.id)
        else:
            promises.settle(world, v.id, v.state, v.note)
    for nt in p.new_threads[: seed_room(world, len(world.board_threads()))]:
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
