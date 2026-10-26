"""The nightly documentary: fifteen minutes on one subject, researched from the archive.

A documentary is a longer special (special.py runs its stages and airs it the
same way), with three differences:

1. Commissioning. Once per broadcast day, in idle time from `commission_from`
   (18:00, so it covers the day), the documentary editor picks a subject: a
   long-running thread, or a piece of the town's history. It isn't commissioned
   while a special is in hand; the editor goes on commissioning specials while a
   documentary is made or waits for its slot (both are low-priority stage jobs
   that take turns).
2. Research. Before the outline, the researcher reads the archive (every piece
   on the thread, and a keyword search for the subject's names and places) and
   writes notes: a dated timeline, the people with a stake, telling details,
   background the piece may establish, open questions. The outline and every
   section are written from those notes, which keeps dates and facts straight
   over fifteen minutes. A timeline entry says whether it is on record (in the
   archive) or background; the town is only days old, so a history piece is
   mostly background, and the writers are told it may be told as history.
3. The slot. A ready documentary airs at the first news bumper from `airs_at`
   (21:00), and only within `window_s` of it, never at another break; one not
   ready in time waits for tomorrow. What it established goes into
   `world.documentaries`, so its canon outlives the archive's 400 characters.

    python -m newsroom.special make --documentary --thread t030   # make one now (uses the model)
"""
from __future__ import annotations

import logging
import os
import time
from datetime import datetime

from . import llm, schedule
from .config import CONFIG
from .models import DocumentaryCommission, DocumentaryResearch, Segment, SegmentType
from .world import World

log = logging.getLogger(__name__)

_COMMISSION_SYSTEM = """\
You are the documentary editor of a small-town TV station in the FICTIONAL town described in the
briefing. Tonight's fifteen-minute documentary goes out in the strand {strand}. Choose ONE subject:
either a long-running story thread with real texture (people with a stake, a history, a question
worth fifteen minutes) or a piece of the town's own history (its founding, a landmark, an industry,
a tradition). Prefer a thread with plenty of coverage; choose history when no thread can carry
fifteen minutes. Never repeat a subject already made. Give a working title, the question the piece
answers, and up to six search terms (names, places, things) for the archive. Everything is fiction;
never reference real people or events. Return ONLY JSON.
"""

_RESEARCH_SYSTEM = """\
You are the researcher for a fifteen-minute documentary on a small-town TV station in the FICTIONAL
town described in the briefing. From the archive extracts, write research notes for the producer and
writers: a dated timeline (on_record true ONLY for what the extracts report, with their dates), the
people with a stake and where they stand, telling details (a number, a quote, an object), background
the piece may establish about the town's past (marked as background, consistent with the briefing:
the founding year, the landmarks, the people), and the questions still open. Never move a date the
extracts give. Everything is fiction. Return ONLY JSON.
"""

OUTLINE_SYSTEM = """\
You are the producer of a fifteen-minute documentary in the strand {strand}, for a small-town TV
station in the FICTIONAL town in the briefing. The presenter is the field reporter (speaker id
"reporter"), on location; the anchor (speaker id "anchor") introduces and closes it from the studio.
Plan 6 to 10 sections with a shape: an opening that sets the question, the history or the build-up,
the people with a stake, the turning points, where things stand, and an ending that looks ahead. Each
section has a heading, the beats it establishes, a backdrop from the allowed list (vary them), and
optionally one person to hear from, with their role. Prefer the people in the research notes and the
briefing (exact names); a person may come back in a later section. Keep to the research notes: their
timeline is the record. Make it warm, local, specific, a little dry. Everything is fiction. Return
ONLY JSON.
"""

SECTION_SYSTEM = """\
You write one section of a fifteen-minute documentary in the strand {strand}, for a small-town TV
station in the FICTIONAL town in the briefing. Speakers allowed in this section: "reporter" (the
presenter, narrating on location) and, if a guest is named, "guest" with guest_name set to that exact
name. Spoken lines only: no stage directions, brackets, markdown or emojis. Numbers as words when
short. Keep to the word budget. Let the guest talk like a real person: a detail, an opinion, a short
story. The research notes are the record: keep their dates and facts; background items describe the
town's past and may be told as history. Do not re-introduce the documentary or sign off; this is one
section in the middle. Return ONLY JSON.
"""


def strand() -> str:
    return CONFIG.documentary.title


def _today_at(hhmm: str, now: float) -> float:
    lt = time.localtime(now)
    h, m = (int(x) for x in hhmm.split(":"))
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


# ------------------------------------------------------------- commissioning

_force: bool | None = None


def take_force() -> bool:
    """One-shot per process: NEWSROOM_DOCUMENTARY_NOW commissions one at the first idle turn,
    whatever the hour and whether or not one was made today. Consumed on first call."""
    global _force
    if _force is None:
        _force = bool(os.environ.get("NEWSROOM_DOCUMENTARY_NOW"))
    if _force:
        _force = False
        return True
    return False


def should_commission(world: World, buffer, now: float | None = None) -> bool:
    """Once per broadcast day, between commission_from and the slot, with no special or
    documentary already in hand."""
    now = now or schedule.now()
    if world.last_documentary_date == world.last_date or buffer.special_pending():
        return False
    return _today_at(CONFIG.documentary.commission_from, now) <= now < _today_at(CONFIG.documentary.airs_at, now)


def decide(world: World) -> DocumentaryCommission | None:
    """Ask the documentary editor for today's subject. None if the model is unavailable."""
    world.last_documentary_date = world.last_date      # one attempt a day, even if it fails
    threads = sorted(world.open_threads(), key=lambda t: -t.mentions)
    user = (
        f"BRIEFING\n{world.summary_for_editor()}\n\n"
        "Threads by coverage: " + (", ".join(f"[{t.id}] {t.mentions}x" for t in threads) or "none yet") + "\n"
        f"Documentaries already made: {', '.join(d['title'] for d in world.documentaries[-10:]) or 'none yet'}\n"
        "Choose tonight's subject."
    )
    try:
        d = llm.complete_json("documentary_commission", DocumentaryCommission,
                              _COMMISSION_SYSTEM.format(strand=strand()), user)
    except llm.LLMError as e:
        log.warning("documentary editor unavailable: %s", e)
        return None
    if d.subject == "thread" and world.thread(d.thread_id) is None:
        log.warning("documentary editor named unknown thread %r; a history piece instead", d.thread_id)
        d.subject, d.thread_id = "history", None
    log.info("documentary: %s %r — %s", d.subject, d.working_title, d.reason)
    return d


def commission(world: World, d: DocumentaryCommission) -> Segment:
    from . import special

    seg = special.commission(world, d)        # the special's slot numbering, priority and deadline
    seg.target_s = CONFIG.documentary.target_s
    seg.stage = "research"
    seg.work.update({"format": "documentary", "strand": strand(), "subject": d.subject,
                     "search_terms": list(d.search_terms)})
    return seg


# ------------------------------------------------------------------ research


def _extract(e: dict) -> str:
    return f"  - {e['date']} ({e['type']}): {e['headline']} | {e['text'][:300]}"


def research(seg: Segment, world: World) -> DocumentaryResearch:
    """The researcher's notes from the archive: every piece on the thread, then a keyword search."""
    thread = world.thread(seg.thread_id)
    on_thread = [e for e in world.archive if thread and e.get("thread_id") == thread.id][-30:]
    seen = {id(e) for e in on_thread}
    terms = " ".join(seg.work.get("search_terms", [])) or seg.headline or ""
    found = [e for e in world.search_archive(terms, limit=16) if id(e) not in seen]
    subject = (f"Thread [{thread.id}] {thread.title}: {thread.phase}; {thread.status}; opened {thread.opened}, "
               f"covered {thread.mentions}x; NEXT: {thread.next_development or 'nothing planned'}"
               if thread else "The town's history: " + (seg.headline or ""))
    if thread and thread.beats:
        subject += "\nBeats aired:\n" + "\n".join(f"  - {b['date']}: {b['headline']}" for b in thread.beats)
    past = [d for d in world.documentaries if d.get("thread_id") == seg.thread_id and thread] or []
    user = (
        f"TOWN BRIEFING\n{world.summary_for_prompt()}\n\n"
        f"DOCUMENTARY: {seg.headline}\nAngle: {seg.work.get('angle', '')}\n{subject}\n\n"
        "ARCHIVE: the pieces on this thread\n" + ("\n".join(map(_extract, on_thread)) or "  (none)") + "\n\n"
        f"ARCHIVE: a search for {terms!r}\n" + ("\n".join(map(_extract, found)) or "  (nothing found)")
    )
    if past:
        user += "\n\nEARLIER DOCUMENTARIES ON THIS SUBJECT (keep to what they established):\n" + "\n".join(
            f"  - {d['date']}: {d['title']}: " + "; ".join(t["event"] for t in d.get("timeline", [])[:6]) for d in past)
    notes = llm.complete_json("documentary_research", DocumentaryResearch, _RESEARCH_SYSTEM, user)
    log.info("documentary %r researched: %d archive pieces, %d timeline entries (%d on record)",
             seg.headline, len(on_thread) + len(found), len(notes.timeline),
             sum(1 for t in notes.timeline if t.on_record))
    return notes


def notes_for_prompt(seg: Segment) -> str:
    """The research notes as the outline and section writers see them."""
    r = DocumentaryResearch.model_validate(seg.work["research"])
    out = ["RESEARCH NOTES (the record: keep these dates and facts)", "Timeline:"]
    out += [f"  - {t.date}: {t.event}" + ("" if t.on_record else " [background]") for t in r.timeline]
    if r.people:
        out += ["People:"] + [f"  - {p.name}, {p.role}: {p.stance}" for p in r.people]
    if r.details:
        out += ["Details:"] + [f"  - {d}" for d in r.details]
    if r.background:
        out += ["Background the piece may establish:"] + [f"  - {b}" for b in r.background]
    if r.questions:
        out += ["Still open:"] + [f"  - {q}" for q in r.questions]
    return "\n".join(out)


def record(world: World, seg: Segment, outline) -> None:
    """What the finished documentary established, kept in the world for later pieces."""
    r = DocumentaryResearch.model_validate(seg.work["research"])
    world.record_special(outline.title, seg.thread_id, cooldown=False)
    world.record_documentary({
        "title": outline.title, "date": world.last_date, "thread_id": seg.thread_id,
        "subject": seg.work.get("subject", "thread"), "standfirst": outline.standfirst,
        "timeline": [t.model_dump() for t in r.timeline],
        "sections": [{"heading": s.heading, "beats": s.beats, "guest": s.guest_name} for s in outline.sections],
    })


# -------------------------------------------------------------------- the slot


def due(world: World, now: float) -> bool:
    """True from airs_at for window_s, on a day none has aired yet."""
    start = _today_at(CONFIG.documentary.airs_at, now)
    today = datetime.fromtimestamp(now).date().isoformat()
    return start <= now < start + CONFIG.documentary.window_s and world.last_documentary_aired != today


def is_documentary(seg: Segment) -> bool:
    return seg.type is SegmentType.documentary and seg.work.get("format") == "documentary"
