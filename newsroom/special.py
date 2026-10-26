"""Special reports: the first step towards documentaries.

Two jobs live here, both run on the worker thread, never the main thread:

1. The editor. When the worker is idle and the live buffer is healthy, it
   reads the open threads and asks the model whether one of them has earned
   a deeper piece. Most of the time the answer should be no.

2. The writer, as a RESUMABLE multi-stage job. A commissioned special goes
   through `advance()` one stage per turn on the worker: outline, then one
   section per stage, then voicing, then finish. After each stage the job is
   re-queued at low priority, so live slots are served in between and the
   longest uninterruptible unit is one model call. Progress is checkpointed
   to data/cache so a restart resumes rather than starting over.

A ready special sits in the buffer's side pocket and the player airs it at
the next break (a news bumper, or overnight the test card), so it never
pre-empts a live slot mid-sentence.

A special's cache key is its own `_hash()` (date, thread, title), never the
slot-keyed hash live segments use: special slot numbers restart every run.
"""
from __future__ import annotations

import hashlib
import logging
import os
import time
from pathlib import Path

from . import llm, schedule
from .config import CONFIG
from . import locations
from .locations import locations_for_prompt
from .models import (
    EditorDecision,
    Line,
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
presenter on location and local people interviewed. Commission one only when a thread has real
texture: history, people with a stake, a question worth five minutes. A thread covered once with
nothing new is not enough. If nothing qualifies, say so; that is the usual answer.
Everything is fiction; never reference real people or events. Return ONLY JSON.
"""

_OUTLINE_SYSTEM = """\
You are the producer of a five-minute SPECIAL REPORT for a small-town TV newsroom in the FICTIONAL
town in the briefing. The presenter is the field reporter (speaker id "reporter"); the anchor
(speaker id "anchor") introduces and closes the piece from the studio. Plan 3 to 6 sections. Each
section has a heading, the beats it establishes, a backdrop from the allowed list, and optionally one
person to hear from, with their role. Prefer the public figures and residents listed in the briefing
when they fit the story (use their exact names); invent a new resident only when nobody listed would
plausibly be involved. Respect the dates in the briefing. Make it warm, local, specific, a little dry.
Everything is fiction. Return ONLY JSON.
"""

_SECTION_SYSTEM = """\
You write one section of a five-minute SPECIAL REPORT for a small-town TV newsroom in the FICTIONAL
town in the briefing. Speakers allowed in this section: "reporter" (the presenter, narrating on
location) and, if a guest is named, "guest" with guest_name set to that exact name. Spoken lines
only: no stage directions, brackets, markdown or emojis. Numbers as words when short. Keep to the
word budget. Let the guest talk like a real person: a detail, an opinion, a short story. Respect the
dates in the briefing; do not invent how long things have been going on. Do not re-introduce the
piece or sign off; this is one section in the middle. Return ONLY JSON.
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
    eligible = [t for t in world.open_threads() if t.mentions >= CONFIG.special.min_mentions]
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
    return Segment(
        slot_id=SPECIAL_SLOT_BASE + _special_counter,
        type=SegmentType.documentary,
        priority=9,
        nominal_start_ts=schedule.now() + 6 * 3600,   # far deadline on the broadcast clock: live slots always win
        target_s=CONFIG.special.target_s,
        headline=decision.working_title or None,
        thread_id=decision.thread_id,
        stage="outline",
        work={"angle": decision.angle},
    )


# ------------------------------------------------------------------ writer


def _hash(seg: Segment, world: World) -> str:
    key = f"special|{world.last_date}|{seg.thread_id}|{seg.headline or seg.work.get('title')}|{world.town}|{llm.provider_for('special_outline')}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


def _word_budget(seconds: float) -> int:
    return int(seconds / 60 * CONFIG.broadcast.words_per_minute)


def _partial_path(h: str) -> Path:
    return CONFIG.paths.cache / f"{h}.partial.json"


def _save_partial(seg: Segment, h: str) -> None:
    p = _partial_path(h)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(seg.model_dump_json(), encoding="utf-8")
    tmp.replace(p)


def _load_partial(seg: Segment, h: str) -> bool:
    p = _partial_path(h)
    if not p.exists():
        return False
    try:
        saved = Segment.model_validate_json(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("special partial %s unreadable (%s); starting over", h, e)
        return False
    seg.lines, seg.work, seg.stage, seg.headline = saved.lines, saved.work, saved.stage, saved.headline
    log.info("special %r resumed at stage %s", seg.headline, seg.stage)
    return True


def write_outline(seg: Segment, world: World) -> SpecialOutline:
    angle = seg.work.get("angle", "")
    thread = world.thread(seg.thread_id)
    subject = (f"Thread [{thread.id}] {thread.title} — {thread.phase}; {thread.status} "
               f"(opened {thread.opened}, covered {thread.mentions}x)"
               if thread else f"Subject: {seg.headline}")
    if thread and thread.beats:
        subject += "\nCoverage so far:\n" + "\n".join(f"  - {b['date']}: {b['headline']}" for b in thread.beats[-6:])
    user = (
        f"TOWN BRIEFING\n{world.summary_for_prompt()}\n\n"
        f"SPECIAL REPORT COMMISSION\nWorking title: {seg.headline}\n{subject}\nAngle: {angle}\n"
        f"Total length about {_word_budget(seg.target_s)} words of speech across all sections, "
        f"plus a short anchor intro and outro.\n\n"
        f"LOCATIONS (backdrop ids):\n{locations_for_prompt()}"
    )
    return llm.complete_json("special_outline", SpecialOutline, _OUTLINE_SYSTEM, user)


def write_section(seg: Segment, world: World, outline: SpecialOutline, i: int, words: int) -> SpecialSection:
    sec = outline.sections[i]
    if sec.guest_name:
        known = world.person_by_name(sec.guest_name)
        who = f"{known.name}, {known.role}" + (f"; {known.notes}" if known and known.notes else "") if known else f"{sec.guest_name}, {sec.guest_role}"
        guest = f"Guest for this section: {who}. Use speaker 'guest' with guest_name '{sec.guest_name}' for their lines."
    else:
        guest = "No guest in this section."
    prev = outline.sections[i - 1].heading if i > 0 else "(this is the first section)"
    user = (
        f"TOWN BRIEFING\n{world.summary_for_prompt()}\n\n"
        f"SPECIAL REPORT: {outline.title}\n{outline.standfirst}\n"
        f"Section {i + 1} of {len(outline.sections)}: {sec.heading}\n"
        f"Beats to cover:\n" + "\n".join(f"  - {b}" for b in sec.beats) + "\n"
        f"Location: {locations.get(sec.backdrop).blurb}. Previous section was: {prev}.\n{guest}\n"
        f"Word budget for this section: about {words} words."
    )
    return llm.complete_json("special_section", SpecialSection, _SECTION_SYSTEM, user)


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
    cues.append(VisualCue(at_s=line_start[-1], kind="lower_third", payload={"title": outline.title, "subtitle": "Special report"}))
    return cues


# --------------------------------------------------------------- stages


def advance(seg: Segment, world: World, buffer=None) -> Segment:
    """Run ONE stage of a special. Re-queues itself if more stages remain.

    Stages: outline -> sections (one per call) -> voice -> finish.
    """
    from . import workers, world as world_mod

    # The hash is fixed at the first stage: the outline renames the segment, so
    # recomputing it later would scatter checkpoints under different keys.
    h = seg.content_hash or _hash(seg, world)
    seg.content_hash = h
    stage = seg.stage or "outline"

    if stage == "outline":
        cached = workers._load_cached(seg, h)
        if cached is not None:
            cached.state = SegmentState.ready
            log.info("special: cache hit %s (%r)", h, cached.headline)
            if buffer:
                buffer.mark(cached, SegmentState.ready)
            return cached
        if _load_partial(seg, h):
            return advance(seg, world, buffer)
        outline = write_outline(seg, world)
        # A new piece under the key of one that already aired (same title, thread and day):
        # its marker would stop a restart from resuming the new one. Only once the outline is
        # in hand, so a retried outline still sees the old piece as aired.
        _aired_path(h).unlink(missing_ok=True)
        seg.headline = outline.title
        seg.work.update({"outline": outline.model_dump(), "starts": [], "next_section": 0, "t0": time.time()})
        seg.lines = [Line(speaker="anchor", text=outline.intro.strip())]
        seg.stage = "sections"
        log.info("special %r outlined: %d sections", outline.title, len(outline.sections))

    elif stage == "sections":
        outline = SpecialOutline.model_validate(seg.work["outline"])
        i = seg.work["next_section"]
        n = len(outline.sections)
        words = _word_budget(seg.target_s) // n
        sec = write_section(seg, world, outline, i, words)
        seg.work["starts"].append(len(seg.lines))     # after the call: a retried stage mustn't add it twice
        plan = outline.sections[i]
        if plan.guest_name:
            world.ensure_person(plan.guest_name, plan.guest_role, gender=plan.guest_gender)
        for l in sec.lines:
            if not l.text.strip():
                continue
            name = (l.guest_name or plan.guest_name) if l.speaker == "guest" else None
            seg.lines.append(Line(speaker=l.speaker, text=l.text.strip(), guest_name=name))
        seg.work["next_section"] = i + 1
        log.info("special %r section %d/%d scripted (%d lines)", outline.title, i + 1, n, len(sec.lines))
        if i + 1 >= n:
            seg.lines.append(Line(speaker="anchor", text=outline.outro.strip()))
            seg.stage = "voice"
            seg.state = SegmentState.scripted
            if buffer:
                buffer.mark(seg, SegmentState.scripted)

    elif stage == "voice":
        workers.voice_segment(seg, world, h)
        seg.stage = "finish"
        if buffer:
            buffer.mark(seg, SegmentState.voiced)

    elif stage == "finish":
        outline = SpecialOutline.model_validate(seg.work["outline"])
        seg.cues = build_cues(seg, outline, seg.work["starts"])
        seg.state = SegmentState.ready
        workers._save_cached(seg, h)
        try:
            _partial_path(h).unlink()
        except OSError:
            pass
        world.record_special(outline.title, seg.thread_id)
        world.record_headline(f"Special report: {outline.title}")
        world.record_aired("special", outline.title, seg.thread_id, " ".join(l.text for l in seg.lines))
        world_mod.save(world)
        if buffer:
            buffer.mark(seg, SegmentState.ready)
        log.info("special %r ready: %d lines, %.0fs of audio, %d sections, %.0fs wall across stages",
                 outline.title, len(seg.lines), seg.duration_s, len(seg.work["starts"]),
                 time.time() - seg.work.get("t0", time.time()))
        return seg

    else:
        raise ValueError(f"unknown special stage {stage!r}")

    _save_partial(seg, h)
    world_mod.save(world)
    if buffer:
        buffer.requeue(seg)
    return seg


def resume_partials(buffer) -> int:
    """On startup, put any checkpointed special back on the queue. Returns how many."""
    global _special_counter
    n = 0
    for p in sorted(CONFIG.paths.cache.glob("*.partial.json")):
        try:
            seg = Segment.model_validate_json(p.read_text(encoding="utf-8"))
        except Exception as e:  # noqa: BLE001
            log.warning("ignoring unreadable checkpoint %s: %s", p.name, e)
            continue
        if seg.type is not SegmentType.documentary or not seg.stage:
            continue
        _special_counter = max(_special_counter, seg.slot_id - SPECIAL_SLOT_BASE)
        seg.state = SegmentState.planned
        # Re-stamp the far deadline: the saved one may be hours stale (or from a
        # run with --clock), and an old deadline would put it ahead of live slots.
        seg.nominal_start_ts = schedule.now() + 6 * 3600
        buffer.submit_special(seg)
        log.info("resuming special %r from stage %s", seg.headline, seg.stage)
        n += 1
    return n


def _aired_path(h: str) -> Path:
    return CONFIG.paths.cache / f"{h}.aired"


def mark_aired(seg: Segment) -> None:
    """Called by the player when a special finishes airing: an empty marker file next to its
    cache entry, so a restart doesn't air it again. No world write (this is the main thread)."""
    if seg.content_hash:
        try:
            _aired_path(seg.content_hash).touch()
        except OSError as e:
            log.warning("could not mark special %r aired: %s", seg.headline, e)


def resume_ready(buffer) -> int:
    """On startup, put finished specials that never aired back in the side pocket. Returns how many.

    A finished special waits in memory for a news bumper; without this a restart in between
    loses it. It goes straight to ready, not back on the queue: its stage is "finish", and
    running that again would record it in the world twice.
    """
    from .workers import REPEAT_WINDOW_S

    global _special_counter
    cutoff = time.time() - REPEAT_WINDOW_S
    n = 0
    for meta in sorted(CONFIG.paths.cache.glob("*.json")):
        if meta.name.endswith(".partial.json") or meta.stat().st_mtime < cutoff or _aired_path(meta.stem).exists():
            continue
        try:
            seg = Segment.model_validate_json(meta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if seg.type is not SegmentType.documentary or seg.state is not SegmentState.ready:
            continue
        if not seg.lines or not all(l.wav_path and Path(l.wav_path).exists() for l in seg.lines):
            continue
        _special_counter += 1                 # earlier runs reused the same slot ids
        seg.slot_id = SPECIAL_SLOT_BASE + _special_counter
        seg.content_hash = seg.content_hash or meta.stem
        buffer.mark(seg, SegmentState.ready)
        log.info("resuming finished special %r; it airs after the next news bumper", seg.headline)
        n += 1
    return n


def generate_special(seg: Segment, world: World, buffer=None) -> Segment:
    """Run all stages back to back (CLI / tests). The worker uses advance()."""
    while seg.state is not SegmentState.ready:
        seg = advance(seg, world, buffer)
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
