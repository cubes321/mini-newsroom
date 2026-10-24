"""The story desk: makes threads develop instead of repeating.

Every `plan_every_s`, when the worker is idle and the live buffer is healthy,
the desk reads the open threads and returns a plan: a phase for each
(emerging, developing, peak, resolving, closed), the concrete next
development the next follow-up should deliver, who is now involved, and
occasionally a new thread to seed. Writers see the NEXT development in their
briefing, so a bulletin that follows up a thread moves it along.
"""
from __future__ import annotations

import logging
import time

from . import llm
from .config import CONFIG
from .models import StoryPlan
from .world import World

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


def plan(world: World, *, dry: bool = False) -> StoryPlan | None:
    """Ask the desk and apply its plan. Returns None if the model was unavailable."""
    world.last_story_plan_ts = time.time()
    open_n = len(world.open_threads())
    room = max(0, CONFIG.story.max_open_threads - open_n)
    user = (
        f"BRIEFING\n{world.summary_for_editor()}\n\n"
        f"There are {open_n} open threads; you may seed at most {min(room, 2)} new ones. "
        "Return phase and NEXT development for every open thread you want to change, close any that "
        "are finished, and list people (exact names from the briefing where possible) now involved."
    )
    try:
        p = llm.complete_json("story_desk", StoryPlan, _SYSTEM, user)
    except llm.LLMError as e:
        log.warning("story desk unavailable: %s", e)
        return None
    if not dry:
        apply(world, p)
    log.info("story desk: %d updates, %d new threads — %s", len(p.updates), len(p.new_threads), p.note)
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
        ids.append(person.id)
    return ids


def apply(world: World, p: StoryPlan) -> None:
    for u in p.updates:
        t = world.thread(u.thread_id)
        if t is None:
            log.warning("story desk named unknown thread %r", u.thread_id)
            continue
        t.phase = u.phase
        t.next_development = u.next_development.strip()
        t.updated = world.last_date if u.phase == "closed" else t.updated
        for pid in _resolve_people(world, u.people):
            if pid not in t.people:
                t.people.append(pid)
        log.info("thread %s -> %s; next: %s", t.id, t.phase, t.next_development[:80])
    room = CONFIG.story.max_open_threads - len(world.open_threads())
    for nt in p.new_threads[: max(0, room)]:
        t = world.seed_thread(nt.title, nt.status, nt.next_development, _resolve_people(world, nt.people))
        log.info("seeded thread %s: %s", t.id, t.title)


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
