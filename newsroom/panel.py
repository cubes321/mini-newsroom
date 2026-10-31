"""The Panel: Dana Ferris chairs three panellists on four questions from the week's news at 20:30
(docs/SHOWS.md).

From `[panel] commission_from`, in idle time, the back office picks the questions from the stories with
the most coverage (not tonight's Inquiry, which has had its half hour) and three panellists who will
differ: an official, a worthy or a business, and a resident with a view, never tonight's Inquiry
guest. Every item then gets the lineup, where each panellist stands, and what has been said so far.
If nothing was chosen in time, a stand-in lineup is made in code from the same stories and people.
"""
from __future__ import annotations

import logging
from datetime import datetime

from . import inquiry, llm, schedule
from .config import CONFIG
from .models import PanelLineup, SegmentType
from .world import World

log = logging.getLogger(__name__)

SHOW = "panel"
STORIES = 6                     # the most-covered stories offered for questions
QUESTIONS = 4                   # one debate each; three left the half hour a third empty (2026-10-30)
RESIDENTS = 8                   # the most-seen residents offered as panellists
SO_FAR_CHARS = 260

_SYSTEM = """\
You book THE PANEL, a half-hour debate on a small-town TV station in the FICTIONAL town in the
briefing. Dana Ferris chairs three panellists on four questions from the week's news. Choose four
questions from the STORIES that people in town genuinely disagree about (money, priorities, who
decides, what the town should keep), phrased as Dana would put them. Choose three panellists from
the PEOPLE who will DIFFER: one official, one worthy or business owner, one resident with a view; say
where each stands, one sentence each, consistent with their positions in the briefing. Not a
panellist named under "not tonight". Everything is fiction. Return ONLY JSON.
"""


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def tonight(world: World) -> dict | None:
    return next((p for p in reversed(world.panels) if p.get("date") == world.last_date), None)


def should_commission(world: World, now: float | None = None) -> bool:
    now = now or schedule.now()
    return tonight(world) is None and _at(CONFIG.panel.commission_from, now) <= now < _at(CONFIG.panel.airs_at, now)


def _not_tonight(world: World) -> tuple[set[str], set[str]]:
    """The Inquiry's story and guest: they've had their half hour."""
    i = inquiry.tonight(world) or {}
    return {i.get("thread_id")} - {None}, {i.get("guest")} - {None, ""}


def _stories(world: World):
    skip, _ = _not_tonight(world)
    return sorted((t for t in world.open_threads() if t.id not in skip), key=lambda t: -t.mentions)[:STORIES]


def _people(world: World):
    _, guest = _not_tonight(world)
    official = [p for p in world.people if p.kind in ("official", "worthy") and p.name not in guest]
    residents = sorted((p for p in world.people if p.kind == "resident" and p.name not in guest),
                       key=lambda p: -p.appearances)[:RESIDENTS]
    return official + residents


def commission(world: World) -> dict:
    """Choose tonight's questions and panellists (the model, or the stand-in if it fails) and record them."""
    stories, people = _stories(world), _people(world)
    names = {p.name for p in people}
    _, guest = _not_tonight(world)
    user = (f"BRIEFING\n{world.summary_for_editor()}\n\nSTORIES:\n"
            + "\n".join(f"  - [{t.id}] {t.title} ({t.phase}, covered {t.mentions}x): {t.status}" for t in stories)
            + "\n\nPEOPLE:\n" + "\n".join(f"  - {p.name}, {p.role} ({p.kind})" for p in people)
            + (f"\n\nNot tonight: {', '.join(sorted(guest))} (on The Inquiry at eight)." if guest else ""))
    try:
        lineup = llm.complete_json("panel", PanelLineup, _SYSTEM, user)
    except llm.LLMError as e:
        log.warning("panel: no lineup (%s); the stand-in takes tonight", e)
        return _record(world, None)
    chosen = [p.name for p in lineup.panellists]
    if len(set(chosen)) < 3 or not set(chosen) <= names:
        log.warning("panel: lineup named %s, not three from the list; the stand-in takes tonight", chosen)
        return _record(world, None)
    return _record(world, lineup)


def _record(world: World, lineup: PanelLineup | None) -> dict:
    if lineup is None:
        stories, people = _stories(world)[:QUESTIONS], _people(world)
        pick = ([p for p in people if p.kind == "official"][:1] + [p for p in people if p.kind == "worthy"][:1]
                + [p for p in people if p.kind == "resident"][:1])
        pick += [p for p in people if p not in pick][:3 - len(pick)]
        entry = {"date": world.last_date, "stand_in": True,
                 "questions": [{"question": f"What should happen next with {t.title.rstrip('.')}?", "thread_id": t.id}
                               for t in stories],
                 "panellists": [{"name": p.name, "stance": f"speaks as {p.role}"} for p in pick]}
    else:
        entry = {"date": world.last_date, **lineup.model_dump()}
    with world.lock:
        world.panels = (world.panels + [entry])[-30:]
    log.info("panel: tonight %s on %s%s", ", ".join(p["name"] for p in entry["panellists"]),
             " | ".join(q["question"][:50] for q in entry["questions"]), " (stand-in)" if entry.get("stand_in") else "")
    return entry


def for_prompt(world: World) -> str:
    """Tonight's lineup for every item in the show, with what has been said so far."""
    s = tonight(world) or _record(world, None)       # nothing chosen by 20:30: the stand-in, recorded once, no call
    who = "\n".join(f"  - {p['name']}" + (f", {person.role}" if (person := world.person_by_name(p["name"])) else "")
                    + f": {p['stance']}" for p in s["panellists"])
    qs = "\n".join(f"  {i + 1}. {q['question']}" + (f" [thread {q['thread_id']}]" if q.get("thread_id") else "")
                   for i, q in enumerate(s["questions"]))
    with world.lock:
        aired = [e for e in world.archive if e["date"] == world.last_date and e.get("show") == SHOW
                 and e["type"] != SegmentType.ad_break.value]
    done = ("\nSAID SO FAR TONIGHT (don't repeat it; take it on):\n" + "\n".join(
        f"  - {e['type'].replace('_', ' ')}: {e['headline']}: {e['text'][:SO_FAR_CHARS]}" for e in aired)) if aired else ""
    return (f"TONIGHT'S PANEL, chaired by Dana Ferris (\"anchor\"):\n{who}\nTONIGHT'S QUESTIONS (one debate "
            f"each, in this order):\n{qs}\n"
            "Panellists speak as speaker \"guest\" with guest_name set to their exact name above; keep each to "
            "their stance, in their own voice." + done)
