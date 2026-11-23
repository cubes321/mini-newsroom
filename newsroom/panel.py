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
import re
from datetime import datetime, timedelta

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
    return (tonight(world) is None and _at(CONFIG.panel.commission_from, now) <= now < _at(CONFIG.panel.airs_at, now)
            and schedule.show_at(_at(CONFIG.panel.airs_at, now)).id == SHOW)     # not on a council night


def _not_tonight(world: World) -> tuple[set[str], set[str]]:
    """The Inquiry's story and guest: they've had their half hour."""
    i = inquiry.tonight(world) or {}
    return {i.get("thread_id")} - {None}, {i.get("guest")} - {None, ""}


def _stories(world: World):
    skip, _ = _not_tonight(world)
    return sorted((t for t in world.open_threads() if t.id not in skip), key=lambda t: -t.mentions)[:STORIES]


def _people(world: World):
    _, guest = _not_tonight(world)
    guest = set(guest) | {p.name for p, _ in world.rested_names()}     # nobody on a lot today
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


def _booked(world: World) -> dict:
    return tonight(world) or _record(world, None)    # nothing chosen by 20:30: the stand-in, recorded once, no call


def brief_for(world: World, brief: str) -> str:
    """An item's brief with tonight's questions in their own words: "{q2}" is the second. Told "the SECOND
    of TONIGHT'S QUESTIONS", the vox pop took another question on three runs in a row (2026-10-30 to 31)."""
    booked = _booked(world)
    qs = booked["questions"]

    def question(m: re.Match) -> str:
        n = int(m.group(1)) - 1
        return f"\"{qs[n]['question'].strip()}\"" if n < len(qs) else "one of TONIGHT'S QUESTIONS"
    if "{qback}" in brief and qs:
        n = _back_to(world, booked)
        brief = brief.replace("{qback}", f"\"{qs[n]['question'].strip()}\"") + (
            " Don't give the question a number (not \"our fourth question\" or \"the first question\").")
    return re.sub(r"\{q(\d)\}", question, brief)


def _back_to(world: World, booked: dict) -> int:
    """Which of tonight's questions a loop item goes back to: the one gone back to least, then the one with fewest
    items so far, then the earliest, and recorded on the booking. The opening and the first debate both have the
    first question, the vox pop and the second debate the second; on 2026-11-22 the email ("{q1}") and "the
    question that split them most" took the first again, and its engine question aired four times."""
    with world.lock:
        briefs = [e.get("brief") or "" for e in world.archive if e.get("date") == world.last_date
                  and e.get("show") == SHOW]
        back = booked.setdefault("went_back", [])
        n = min(range(len(booked["questions"])),
                key=lambda i: (back.count(i), sum(f"{{q{i + 1}}}" in b for b in briefs) + back.count(i), i))
        back.append(n)
    return n


def for_prompt(world: World) -> str:
    """Tonight's lineup for every item in the show, with what has been said so far."""
    s = _booked(world)
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
            "their stance, in their own voice. The next full council is a fact for the debate (where a question "
            "goes next), said once at most and in the panel's own words; never read out the briefing's line about "
            "it." + done)


def back_on(now: float | None = None) -> str:
    """When The Panel is next on, for its goodbye. On 2026-11-21 Dana signed off "Back on the third of December,
    live on The Chamber at eight", the council line from the briefing read out: The Panel is on every night but a
    council night, and the council's date is a fact for the debate, not a line to read."""
    # The schedule says, not the council's calendar: a council night gives The Chamber the hour, and a special day
    # (Christmas) has a grid of its own.
    today = datetime.fromtimestamp(now or schedule.now()).date()
    h, m = (int(x) for x in CONFIG.panel.airs_at.split(":"))
    for n in range(1, 8):
        day = today + timedelta(days=n)
        if schedule.show_at(datetime(day.year, day.month, day.day, h, m).timestamp()).id == SHOW:
            when = "tomorrow night" if n == 1 else f"on {day:%A}"
            return f"THE PANEL is back {when} at {schedule.said_clock(h, m)}: say so in the goodbye."
    return "The Panel's next night isn't set: say goodnight without naming one."
