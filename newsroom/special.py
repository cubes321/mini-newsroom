"""Special reports: the first step towards documentaries.

Two jobs live here, both run on the worker thread, never the main thread:

1. The editor. Every `check_every_s`, when the worker is idle, it reads the
   open threads and asks the model whether one of them has earned a deeper
   piece. Most of the time the answer should be no.

2. The writer. A commissioned special is written in stages so each model call
   stays small and recoverable: an outline (title, standfirst, anchor intro
   and outro, 3-6 sections with an optional invented interviewee), then one
   call per section. Lines are voiced like any other segment; cues (chapter
   cards, backdrops, guest lower thirds) are placed by real audio timing.

A ready special sits in the buffer's side pocket and the player airs it at
the next bumper boundary, so it never pre-empts a live slot mid-sentence.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from datetime import date

from . import llm
from .config import CONFIG
from .models import (
    EditorDecision,
    Line,
    ScriptLine,
    Segment,
    SegmentState,
    SegmentType,
    SpecialOutline,
    SpecialSection,
    VisualCue,
)
from .world import World

log = logging.getLogger(__name__)

SPECIAL_SLOT_BASE = 1_000_000      # specials live outside the rundown's slot numbering
_special_counter = 0

_EDITOR_SYSTEM = """\
You are the editor of a small-town TV newsroom in the FICTIONAL town described in the briefing.
You decide whether any open story thread has earned a SPECIAL REPORT: a five-minute piece with a
presenter on location and invented local residents interviewed. Commission one only when a thread
has real texture: history, people with a stake, a question worth five minutes. A thread covered
once with nothing new is not enough. If nothing qualifies, say so; that is the usual answer.
Everything is fiction; never reference real people or events. Return ONLY JSON.
"""

_OUTLINE_SYSTEM = """\
You are the producer of a five-minute SPECIAL REPORT for a small-town TV newsroom in the FICTIONAL
town in the briefing. The presenter is the field reporter (speaker id "reporter"); the anchor
(speaker id "anchor") introduces and closes the piece from the studio. Plan 3 to 6 sections. Each
section has a heading, the beats it establishes, a backdrop from the allowed list, and optionally one
invented resident to hear from, with a role. Vary the guests; give them specific, believable names.
Make it warm, local, specific, a little dry. Everything is fiction. Return ONLY JSON.
"""

_SECTION_SYSTEM = """\
You write one section of a five-minute SPECIAL REPORT for a small-town TV newsroom in the FICTIONAL
town in the briefing. Speakers allowed in this section: "reporter" (the presenter, narrating on
location) and, if a guest is named, "guest" with guest_name set to that exact name. Spoken lines
only: no stage directions, brackets, markdown or emojis. Numbers as words when short. Keep to the
word budget. Let the guest talk like a real person: a detail, an opinion, a short story. Do not
re-introduce the piece or sign off; this is one section in the middle. Return ONLY JSON.
"""


# ------------------------------------------------------------------ editor


_force: bool | None = None


def take_force() -> bool:
    """One-shot per process: NEWSROOM_SPECIAL_NOW asks for an editor check right away,
    ignoring cooldown and coverage minimums. Consumed on first call."""
    global _force
    if _force is None:
        _force = bool(os.environ.get("NEWSROOM_SPECIAL_NOW"))
    if _force:
        _force = False
        return True
    return False


def should_check(world: World, now: float | None = None) -> bool:
    now = now or time.time()
    sc = CONFIG.special
    if now - world.last_special_ts < sc.cooldown_s:
        return False
    return now - world.last_editor_check_ts >= sc.check_every_s


def decide(world: World, *, force: bool = False) -> EditorDecision:
    """Ask the editor model. Returns a non-commissioning decision on any failure."""
    world.last_editor_check_ts = time.time()
    eligible = [t for t in world.threads if t.mentions >= CONFIG.special.min_mentions]
    if not eligible and not force:
        return EditorDecision(commission=False, reason="no thread has enough coverage yet")
    user = (
        f"BRIEFING\n{world.summary_for_editor()}\n\n"
        f"Threads with at least {CONFIG.special.min_mentions} pieces of coverage are eligible. "
        "Should we commission a special report now? If yes, name the thread id, a working title "
        "and the angle (the question the piece answers)."
    )
    if force:
        user += "\nThe producer has asked for a special in this edition if at all defensible."
    try:
        d = llm.complete_json("editor", EditorDecision, _EDITOR_SYSTEM, user)
    except llm.LLMError as e:
        log.warning("editor unavailable: %s", e)
        return EditorDecision(commission=False, reason=f"editor unavailable: {e}")
    if d.commission and d.thread_id and world.thread(d.thread_id) is None:
        log.warning("editor named unknown thread %r; treating as a fresh subject", d.thread_id)
        d.thread_id = None
    log.info("editor: %s — %s", "COMMISSION " + d.working_title if d.commission else "pass", d.reason)
    return d


def commission(world: World, decision: EditorDecision) -> Segment:
    global _special_counter
    _special_counter += 1
    seg = Segment(
        slot_id=SPECIAL_SLOT_BASE + _special_counter,
        type=SegmentType.documentary,
        priority=9,
        nominal_start_ts=time.time() + 6 * 3600,   # far deadline: live slots always win
        target_s=CONFIG.special.target_s,
        headline=decision.working_title or None,
        thread_id=decision.thread_id,
    )
    seg.cues = [VisualCue(kind="chapter", payload={"angle": decision.angle})]   # placeholder; replaced on generate
    return seg


# ------------------------------------------------------------------ writer


def _hash(seg: Segment, world: World) -> str:
    key = f"special|{date.today().isoformat()}|{seg.thread_id}|{seg.headline}|{world.town}|{llm.provider_for('special_outline')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _word_budget(seconds: float) -> int:
    return int(seconds / 60 * CONFIG.broadcast.words_per_minute)


def write_outline(seg: Segment, world: World) -> SpecialOutline:
    angle = next((c.payload.get("angle") for c in seg.cues if c.kind == "chapter"), "") or ""
    thread = world.thread(seg.thread_id)
    subject = (f"Thread [{thread.id}] {thread.title} — {thread.status} (covered {thread.mentions}x)"
               if thread else f"Subject: {seg.headline}")
    user = (
        f"TOWN BRIEFING\n{world.summary_for_prompt()}\n\n"
        f"SPECIAL REPORT COMMISSION\nWorking title: {seg.headline}\n{subject}\nAngle: {angle}\n"
        f"Total length about {_word_budget(seg.target_s)} words of speech across all sections, "
        f"plus a short anchor intro and outro. Today is {date.today():%A %d %B}."
    )
    return llm.complete_json("special_outline", SpecialOutline, _OUTLINE_SYSTEM, user)


def write_section(seg: Segment, world: World, outline: SpecialOutline, i: int, words: int) -> SpecialSection:
    sec = outline.sections[i]
    guest = (f"Guest for this section: {sec.guest_name}, {sec.guest_role}. Use speaker 'guest' with "
             f"guest_name '{sec.guest_name}' for their lines.") if sec.guest_name else "No guest in this section."
    prev = outline.sections[i - 1].heading if i > 0 else "(this is the first section)"
    user = (
        f"TOWN BRIEFING\n{world.summary_for_prompt()}\n\n"
        f"SPECIAL REPORT: {outline.title}\n{outline.standfirst}\n"
        f"Section {i + 1} of {len(outline.sections)}: {sec.heading}\n"
        f"Beats to cover:\n" + "\n".join(f"  - {b}" for b in sec.beats) + "\n"
        f"Location/backdrop: {sec.backdrop}. Previous section was: {prev}.\n{guest}\n"
        f"Word budget for this section: about {words} words."
    )
    return llm.complete_json("special_section", SpecialSection, _SECTION_SYSTEM, user)


def script_special(seg: Segment, world: World, on_progress=None) -> tuple[Segment, SpecialOutline, list[int]]:
    """Fill seg.lines from outline + sections. Returns section start line indices too."""
    outline = write_outline(seg, world)
    seg.headline = outline.title
    n = len(outline.sections)
    per_section = _word_budget(seg.target_s) // n
    lines: list[Line] = [Line(speaker="anchor", text=outline.intro.strip())]
    starts: list[int] = []
    for i in range(n):
        starts.append(len(lines))
        sec = write_section(seg, world, outline, i, per_section)
        for l in sec.lines:
            if not l.text.strip():
                continue
            name = l.guest_name or outline.sections[i].guest_name if l.speaker == "guest" else None
            lines.append(Line(speaker=l.speaker, text=l.text.strip(), guest_name=name))
        if on_progress:
            on_progress(i + 1, n)
        log.info("special %r section %d/%d scripted (%d lines)", outline.title, i + 1, n, len(sec.lines))
    lines.append(Line(speaker="anchor", text=outline.outro.strip()))
    seg.lines = lines
    seg.state = SegmentState.scripted
    return seg, outline, starts


def build_cues(seg: Segment, outline: SpecialOutline, starts: list[int]) -> list[VisualCue]:
    """Place cues by real line timing (call after voicing)."""
    t = 0.0
    line_start: list[float] = []
    for l in seg.lines:
        line_start.append(t)
        t += l.duration_s or 0.0
    cues: list[VisualCue] = [VisualCue(at_s=0, kind="ticker", payload={"text": f"SPECIAL REPORT: {outline.title}"})]
    n = len(outline.sections)
    for i, start_idx in enumerate(starts):
        at = line_start[start_idx]
        sec = outline.sections[i]
        cues.append(VisualCue(at_s=at, kind="chapter", payload={
            "number": i + 1, "total": n, "heading": sec.heading,
            "title": outline.title, "standfirst": outline.standfirst}))
        cues.append(VisualCue(at_s=at, kind="backdrop", payload={"backdrop": sec.backdrop}))
        cues.append(VisualCue(at_s=at, kind="lower_third", payload={}))
        end_idx = starts[i + 1] if i + 1 < n else len(seg.lines) - 1
        for j in range(start_idx, end_idx):
            l = seg.lines[j]
            if l.speaker == "guest":
                cues.append(VisualCue(at_s=line_start[j], kind="lower_third",
                                      payload={"title": l.guest_name or "Resident", "subtitle": sec.guest_role or "Port Wexley"}))
            elif j > start_idx and seg.lines[j - 1].speaker == "guest":
                cues.append(VisualCue(at_s=line_start[j], kind="lower_third", payload={}))
    # Anchor outro: back in the studio with the title as caption.
    cues.append(VisualCue(at_s=line_start[-1], kind="lower_third", payload={"title": outline.title, "subtitle": "Special report"}))
    return cues


def generate_special(seg: Segment, world: World, buffer=None) -> Segment:
    """Outline -> sections -> voice -> cues. Cached like any other segment."""
    from . import workers, world as world_mod

    t0 = time.perf_counter()
    h = _hash(seg, world)
    seg.content_hash = h
    cached = workers._load_cached(seg, h)
    if cached is not None:
        cached.state = SegmentState.ready
        log.info("special: cache hit %s (%r)", h, cached.headline)
        if buffer:
            buffer.mark(cached, SegmentState.ready)
        return cached

    seg, outline, starts = script_special(seg, world)
    if buffer:
        buffer.mark(seg, SegmentState.scripted)
    workers.voice_segment(seg, world, h)
    if buffer:
        buffer.mark(seg, SegmentState.voiced)
    seg.cues = build_cues(seg, outline, starts)
    seg.state = SegmentState.ready
    workers._save_cached(seg, h)
    world.record_special(outline.title, seg.thread_id)
    world.record_headline(f"Special report: {outline.title}")
    world_mod.save(world)
    if buffer:
        buffer.mark(seg, SegmentState.ready)
    log.info("special %r ready: %d lines, %.0fs of audio, %d sections, in %.0fs wall",
             outline.title, len(seg.lines), seg.duration_s, len(starts), time.perf_counter() - t0)
    return seg


# --------------------------------------------------------------------- CLI


def _cli(argv: list[str]) -> int:
    import argparse
    import json

    from . import world as world_mod

    p = argparse.ArgumentParser(prog="python -m newsroom.special")
    p.add_argument("cmd", choices=["decide", "make"])
    p.add_argument("--thread", help="thread id to cover (make)")
    p.add_argument("--title", help="working title (make, when no thread)")
    p.add_argument("--angle", default="", help="the question the piece answers")
    p.add_argument("--target", type=float, default=None, help="seconds (default from config)")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "openai", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    w = world_mod.load()
    if a.cmd == "decide":
        print(decide(w, force=True).model_dump_json(indent=2))
        return 0

    thread = w.thread(a.thread) if a.thread else None
    if a.thread and thread is None:
        print(f"unknown thread {a.thread}; known: {[t.id for t in w.threads]}")
        return 2
    title = a.title or (thread.title if thread else None)
    if not title:
        print("need --thread or --title")
        return 2
    seg = commission(w, EditorDecision(commission=True, thread_id=a.thread, working_title=title, angle=a.angle))
    if a.target:
        seg.target_s = a.target
    out = generate_special(seg, w)
    print(json.dumps({
        "title": out.headline, "hash": out.content_hash, "duration_s": round(out.duration_s, 1),
        "lines": len(out.lines), "guests": sorted({l.guest_name for l in out.lines if l.guest_name}),
        "chapters": [c.payload["heading"] for c in out.cues if c.kind == "chapter"],
    }, indent=1))
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
