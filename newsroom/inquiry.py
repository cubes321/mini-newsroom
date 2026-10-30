"""The Inquiry: Pat Holloway takes one running story in depth at 20:00 (docs/SHOWS.md).

From `[inquiry] commission_from`, in idle time, the back office picks tonight's story from those with
enough coverage that haven't been investigated lately (and aren't tonight's documentary), sets the
angle and the questions Pat puts, and names the guest who has to answer them. Every item in the show
then gets that brief, the story's record, and what the earlier items established. If nothing was
chosen by the time the show is written, the most-covered story at its peak stands in, so the half
hour always has a subject.
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timedelta

from . import llm, schedule
from .config import CONFIG
from .models import InquiryCommission, SegmentType
from .world import Thread, World

log = logging.getLogger(__name__)

SHOW = "inquiry"
CANDIDATES = 8
SO_FAR_CHARS = 220              # how much of each earlier item the next one is shown

_SYSTEM = """\
You are the editor of THE INQUIRY, a half-hour investigation on a small-town TV station in the
FICTIONAL town in the briefing. Each night Pat Holloway, a former consumer champion who never lets
a vague answer go, takes ONE running story in depth: how it began, what the record shows, who decides,
and what still isn't answered. Choose tonight's story from the CANDIDATES: one with real questions
for someone with power to answer (the council, the harbour office, a landlord, a firm, the MP), not
just a pleasant one. Give a title that is a question, an angle, two to four sharp questions Pat
puts, and the guest who has to answer them, by an exact name from the story's people or the public
figures. Fair and precise; small-town scale; nobody accused of a crime the record doesn't show.
Everything is fiction. Return ONLY JSON.
"""


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def tonight(world: World) -> dict | None:
    """Tonight's subject, if one has been chosen."""
    return next((i for i in reversed(world.inquiries) if i.get("date") == world.last_date), None)


def candidates(world: World) -> list[Thread]:
    """Open stories with enough coverage, not investigated in the last few days nor tonight's
    documentary, those at their peak first, then by coverage."""
    cfg = CONFIG.inquiry
    since = (date.fromisoformat(world.last_date) - timedelta(days=cfg.rest_days)).isoformat()
    recent = {i["thread_id"] for i in world.inquiries if i.get("date", "") > since}
    recent |= {d.get("thread_id") for d in world.documentaries if d.get("date") == world.last_date}
    ok = [t for t in world.open_threads() if t.mentions >= cfg.min_mentions and t.id not in recent]
    return sorted(ok, key=lambda t: (t.phase != "peak", -t.mentions))[:CANDIDATES]


def should_commission(world: World, now: float | None = None) -> bool:
    now = now or schedule.now()
    return tonight(world) is None and _at(CONFIG.inquiry.commission_from, now) <= now < _at(
        CONFIG.inquiry.airs_at, now)


def _row(world: World, t: Thread) -> str:
    people = ", ".join(p.name for pid in t.people if (p := world.person(pid))) or "nobody named yet"
    return (f"  - [{t.id}] {t.title} ({t.phase}, covered {t.mentions}x): {t.status}"
            + (f" Planned next: {t.next_development}" if t.next_development else "") + f" People: {people}.")


def commission(world: World) -> dict:
    """Choose tonight's subject (the model, or the stand-in if it fails) and record it."""
    pool = candidates(world)
    if not pool:
        return _record(world, None)
    user = (f"BRIEFING\n{world.summary_for_editor()}\n\nCANDIDATES:\n" + "\n".join(_row(world, t) for t in pool)
            + "\n\nRecent inquiries: " + (", ".join(i["title"] for i in world.inquiries[-5:]) or "none yet"))
    try:
        c = llm.complete_json("inquiry", InquiryCommission, _SYSTEM, user)
    except llm.LLMError as e:
        log.warning("inquiry: no commission (%s); the stand-in takes tonight", e)
        return _record(world, None)
    if not world.thread(c.thread_id) or c.thread_id not in {t.id for t in pool}:
        log.warning("inquiry: commission named %r, not a candidate; the stand-in takes tonight", c.thread_id)
        return _record(world, None)
    return _record(world, c)


def _record(world: World, c: InquiryCommission | None) -> dict:
    if c is None:
        pool = candidates(world) or sorted(world.open_threads(), key=lambda t: -t.mentions)
        t = pool[0] if pool else None
        guest = next((p.name for pid in t.people if (p := world.person(pid)) and p.kind == "official"), "") if t else ""
        entry = {"date": world.last_date, "thread_id": t.id if t else None,
                 "title": (f"What Next for {t.title}?" if t else "What Is Port Wexley Waiting For?")[:70],
                 "angle": "How the story began, what the record shows, who decides, and what still isn't answered.",
                 "questions": ["Who decides, and when?", "What has been promised, and what has been done?"],
                 "guest": guest, "stand_in": True}
    else:
        entry = {"date": world.last_date, **c.model_dump()}
    with world.lock:
        world.inquiries = (world.inquiries + [entry])[-30:]
    log.info("inquiry: tonight %r on %s, guest %s%s", entry["title"], entry["thread_id"], entry["guest"] or "none",
             " (stand-in)" if entry.get("stand_in") else "")
    return entry


def for_prompt(world: World) -> str:
    """Tonight's brief for every item in the show, with the record and what earlier items established."""
    from .special import story_so_far

    s = tonight(world) or _record(world, None)       # nothing chosen by 20:00: the stand-in, recorded once, no call
    qs = "\n".join(f"  {i + 1}. {q}" for i, q in enumerate(s["questions"]))
    record = story_so_far(world, s["thread_id"]) if s["thread_id"] else ""
    with world.lock:
        aired = [e for e in world.archive if e["date"] == world.last_date and e.get("show") == SHOW
                 and e["type"] != SegmentType.ad_break.value]
    done = ("\nALREADY ESTABLISHED TONIGHT (build on it; don't restate it):\n" + "\n".join(
        f"  - {e['type'].replace('_', ' ')}: {e['headline']}: {e['text'][:SO_FAR_CHARS]}" for e in aired)) if aired else ""
    return (f"TONIGHT'S INQUIRY: \"{s['title']}\"" + (f", on thread [{s['thread_id']}]" if s["thread_id"] else "")
            + f".\nTHE ANGLE: {s['angle']}\nTHE QUESTIONS PAT PUTS:\n{qs}\n"
            + (f"THE GUEST who has to answer them, in the studio: {s['guest']}.\n" if s["guest"] else "")
            + (f"\n{record}\n" if record else "") + done
            + (f"\nEvery item is about this story: set thread_id to \"{s['thread_id']}\"." if s["thread_id"] else ""))
