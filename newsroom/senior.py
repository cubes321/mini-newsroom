"""The senior editor: a periodic look at the story desk's whole board.

The desk plans eight threads a round, every half hour, and each model has a habit there: on
2026-10-29 DeepSeek Flash steered 11 of 24 rounds onto the same council meeting, and on 2026-10-28
Sonnet held the same eight threads with "hold Friday's beats" all night. Every `[story]
review_every_s` (two hours), when the worker is idle, the senior editor reads the whole board and
the desk's recent rounds and leaves the desk a short memo it reads on every round until the next
one. It merges duplicates itself, and may open one fresh story even when the board is past the
desk's `max_open_threads` (the desk was told it could seed none all night on 2026-10-29).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime

from . import desk, llm, schedule
from .config import CONFIG
from .models import SeniorMemo
from .world import World

log = logging.getLogger(__name__)

_SYSTEM = """\
You are the senior editor of a small-town TV newsroom in the FICTIONAL town in the briefing. A story
desk plans the town's running stories, a batch of threads every half hour, giving each a phase and
the NEXT development the bulletins will report. Every two hours you read the whole board and the
desk's recent rounds, and leave the desk a short memo it will follow until your next one. You don't
plan threads yourself; you correct the board's shape. Look for:
- CONVERGENCE: too many threads steered onto the same meeting, day, decision or pot of money, so
  every bulletin becomes one story. Name the threads to take elsewhere: a different day, place,
  person or kind of consequence.
- STALLING: threads held round after round ("hold the beats", the same next step restated). Ask for
  real movement, or closure.
- CLOSURES: threads that have run their course. Closing them makes room for new stories.
- DUPLICATES: one story under several threads. Merge them yourself (merges), into the one covered more.
- FRESHNESS and BALANCE: the board needs stories from all of town life (harbour, schools, shops,
  sport, clubs, weather, oddities), not only the council and its money, and some light ones. You may
  open ONE new story yourself (new_thread), perhaps from a guest's LOOSE END; leave it null if the
  board is already varied.
Write the memo as at most five short directives naming threads by id ("t058 and t220 both lean on
the reserves line: move t220 on through the divers, not the money"). Small-town scale; everything is
fiction, never real people or events. Return ONLY JSON.
"""


def should_review(world: World, now: float | None = None) -> bool:
    every = CONFIG.story.review_every_s
    return every > 0 and (now or time.time()) - world.last_senior_ts >= every


def _rounds(world: World) -> str:
    rows = "\n".join(f"  - {n['at']}: planned {', '.join(n['planned']) or '(none)'}; {n['new']} new, "
                     f"{n['merges']} merged — {n['note']}" for n in world.desk_notes)
    return rows or "  (none yet)"


def review(world: World, *, dry: bool = False) -> SeniorMemo | None:
    """Ask the senior editor and apply its memo, merges and new thread. None if the model failed."""
    world.last_senior_ts = time.time()
    open_n = len(world.open_threads())
    user = (
        f"BRIEFING\n{world.summary_for_editor()}\n\n"
        f"There are {open_n} open threads (the desk opens new ones only while fewer than "
        f"{CONFIG.story.max_open_threads} are open).\n\n"
        f"THE DESK'S RECENT ROUNDS, oldest first:\n{_rounds(world)}\n\n"
        + (f"YOUR LAST MEMO ({world.senior_memo_at}):\n{world.senior_memo}\n\n" if world.senior_memo else "")
        + "Write the memo for the desk's next rounds."
    ) + desk._loose_ends(world)
    try:
        m = llm.complete_json("senior_editor", SeniorMemo, _SYSTEM, user)
    except llm.LLMError as e:
        log.warning("senior editor unavailable: %s", e)
        return None
    if not dry:
        with world.lock:
            for mg in m.merges:
                if world.merge_thread(mg.duplicate, mg.into):
                    log.info("senior editor merged thread %s into %s: %s", mg.duplicate, mg.into,
                             world.thread(mg.into).title[:60])
                else:
                    log.info("senior editor merge %s into %s skipped (not two live threads)", mg.duplicate, mg.into)
            if m.new_thread:
                desk.seed(world, m.new_thread, who="senior editor")
            world.senior_memo = m.memo.strip()
            world.senior_memo_at = f"{world.last_date} {datetime.fromtimestamp(schedule.now()):%H:%M}"
    log.info("senior editor: %d merges, %s — %s", len(m.merges),
             f"new thread {m.new_thread.title!r}" if m.new_thread else "no new thread", m.memo.replace("\n", " / "))
    return m


def _cli(argv: list[str]) -> int:
    import argparse

    from . import world as world_mod

    ap = argparse.ArgumentParser(prog="python -m newsroom.senior")
    ap.add_argument("cmd", choices=["review"])
    ap.add_argument("--dry", action="store_true", help="show the memo without applying or saving it")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "openai", "urllib3", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    w = world_mod.load()
    m = review(w, dry=a.dry)
    if m is None:
        return 1
    print(m.model_dump_json(indent=2))
    if not a.dry:
        world_mod.save(w)
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
