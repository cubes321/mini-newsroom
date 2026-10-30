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

Archive footage: the research stage also looks up the cached audio of the
pieces it read (by the archive entry's cache key, or for entries older than
that, by its text, an exact prefix of the segment's) and offers the outline up
to MAX_CLIPS clips: one line each, a guest's quote or else Miles in the field,
of a few seconds to three quarters of a minute. The outline may place up to three, one per
section; the section is written around it (its first line leads in, its second
picks up), the clip's WAV is copied into the documentary's own files, and it
airs captioned "Archive · <date>" in black and white.

    python -m newsroom.special make --documentary --thread t030   # make one now (uses the model)
"""
from __future__ import annotations

import logging
import os
import shutil
import time
from datetime import date, datetime
from pathlib import Path

from . import llm, schedule
from .config import CONFIG
from .models import DocumentaryCommission, DocumentaryResearch, Line, Segment, SegmentType
from .world import World

MAX_CLIPS = 8                        # offered to the outline
PLACED_CLIPS = 3                     # placed at most, one per section
CLIP_S = (3.0, 45.0)                 # a usable clip line's length (Miles's report lines run 30-48 s)

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
station in the FICTIONAL town in the briefing. The presenter is {presenter_is} (speaker id
"{presenter}"), on location; the anchor (speaker id "anchor") introduces and closes it from the studio.
Plan 6 to 10 sections with a shape: an opening that sets the question, the history or the build-up,
the people with a stake, the turning points, where things stand, and an ending that looks ahead. Each
section has a heading, the beats it establishes, a backdrop from the allowed list (vary them), and
optionally one person to hear from, with their role. Prefer the people in the research notes and the
briefing (exact names); a person may come back in a later section. Keep to the research notes: their
timeline is the record. If ARCHIVE CLIPS are listed, you may place up to three, one per section, by
their id in archive_clip: pick ones that move the story on, in the section they belong to. Make it
warm, local, specific, a little dry. Everything is fiction. Return ONLY JSON.
"""

# For any section of a special or documentary. Read 2026-10-30, Flash's first night on them: a planned
# NEXT step told as done ("on Saturday she called at Winifred's", on a Thursday) or foretold by a guest
# ("they'll get it right on the third throw"); the same facts restated in five sections of eight; the
# location's description read out ("the horseshoe of desks" in five specials, and still, when told not
# to, so a section now gets only the place's name). Sonnet repeated itself too.
SECTION_RULES = """
WHAT HAS NOT HAPPENED: a thread's NEXT development is the desk's plan, not news. Say what is expected
or due only as expected ("is due to", "says she will"); never report it as done, and nobody predicts
it as a certainty. ALREADY SAID: the earlier sections are given; do not restate their facts, figures,
dates or descriptions. Move the story on: new detail, a new voice, a consequence. The LOCATION is only
where we are (the picture shows it): describe it only where a detail serves the story."""

SECTION_SYSTEM = """\
You write one section of a fifteen-minute documentary in the strand {strand}, for a small-town TV
station in the FICTIONAL town in the briefing. Speakers allowed in this section: "{presenter}" (the
presenter, {presenter_is}, narrating on location) and, if a guest is named, "guest" with guest_name set to that exact
name. Spoken lines only: no stage directions, brackets, markdown or emojis. Numbers as words when
short. Keep to the word budget. Let the guest talk like a real person: a detail, an opinion, a short
story. The research notes are the record: keep their dates and facts; background items describe the
town's past and may be told as history. Do not re-introduce the documentary or sign off; this is one
section in the middle.""" + SECTION_RULES + """ Return ONLY JSON.
"""


def strand() -> str:
    return CONFIG.documentary.title


# Who presents: Miles a story the town is living through, Hugh a piece of its history.
PRESENTERS = {"reporter": "the field reporter, Miles Okafor",
              "historian": "Hugh Tremayne, the station's local-history presenter, a former history teacher"}


def presenter(seg: Segment) -> str:
    return "historian" if seg.work.get("subject") == "history" else "reporter"


def prompt_vars(seg: Segment) -> dict:
    """The presenter for the outline and section prompts."""
    who = presenter(seg)
    return {"presenter": who, "presenter_is": PRESENTERS[who]}


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
    # Faded threads too: a big story that went quiet is a "whatever happened to" subject.
    threads = sorted(world.open_threads() + world.recently_faded(), key=lambda t: -t.mentions)
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
               f"covered {thread.mentions}x; NEXT (planned, has not happened): {thread.next_development or 'nothing planned'}"
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
    seg.work["clips"] = find_clips(world, list(reversed(on_thread)) + found)   # the latest pieces first
    notes = llm.complete_json("documentary_research", DocumentaryResearch, _RESEARCH_SYSTEM, user)
    log.info("documentary %r researched: %d archive pieces, %d timeline entries (%d on record), %d clips",
             seg.headline, len(on_thread) + len(found), len(notes.timeline),
             sum(1 for t in notes.timeline if t.on_record), len(seg.work["clips"]))
    return notes


# ------------------------------------------------------------------ footage


def _joined(lines) -> str:
    return " ".join(l.text for l in lines if l.text)        # as record_aired joins them (a sting line is empty)


def _cached_segments() -> dict[str, Segment]:
    out: dict[str, Segment] = {}
    for meta in CONFIG.paths.cache.glob("*.json"):
        if meta.name.endswith(".partial.json"):
            continue
        try:
            out[meta.stem] = Segment.model_validate_json(meta.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
    return out


def _clip_line(seg: Segment) -> Line | None:
    """The line worth replaying: a guest's quote, or else the reporter in the field. Never an anchor
    reading the news, and never a clip of a clip."""
    usable = [l for l in seg.lines if l.speaker in ("guest", "reporter", "historian") and l.text and not l.archive
              and l.wav_path and Path(l.wav_path).exists() and CLIP_S[0] <= (l.duration_s or 0) <= CLIP_S[1]]
    # A guest first; then a report line that doesn't open with a handback ("Thanks, Dana."), which
    # sounds odd out of its bulletin.
    usable.sort(key=lambda l: (l.speaker != "guest", l.text.lower().startswith(("thanks", "thank you"))))
    return usable[0] if usable else None


def caption(iso: str) -> str:
    return f"Archive · {date.fromisoformat(iso):%A %d %B}".replace(" 0", " ")


def find_clips(world: World, entries: list[dict], cache: dict[str, Segment] | None = None) -> list[dict]:
    """Archive entries with replayable audio, as short-id clips for the outline (C1, C2...). An entry
    finds its segment by its cache key, or, written before entries had one, by its text."""
    cache = _cached_segments() if cache is None else cache
    by_text: dict[str, Segment] | None = None
    clips: list[dict] = []
    seen: set[str] = set()
    for e in entries:
        seg = cache.get(e.get("hash") or "")
        if seg is None and len(e.get("text", "")) >= 40:
            if by_text is None:
                by_text = {_joined(s.lines)[:400]: s for s in cache.values() if s.lines}
            seg = by_text.get(e["text"][:400])
        line = _clip_line(seg) if seg else None
        if line is None or str(line.wav_path) in seen:
            continue
        seen.add(str(line.wav_path))
        who = line.guest_name if line.speaker == "guest" else (c.name if (c := world.character(line.speaker)) else "")
        clips.append({"id": f"C{len(clips) + 1}", "date": e["date"], "type": e["type"], "headline": e["headline"],
                      "speaker": line.speaker, "who": who, "guest_name": line.guest_name,
                      "guest_role": line.guest_role, "text": line.text, "wav": str(line.wav_path),
                      "duration_s": line.duration_s, "mouth_env": line.mouth_env})
        if len(clips) >= MAX_CLIPS:
            break
    return clips


def clips_for_prompt(seg: Segment) -> str:
    clips = seg.work.get("clips") or []
    if not clips:
        return ""
    return "ARCHIVE CLIPS (footage of earlier coverage; place up to three by id):\n" + "\n".join(
        f"  {c['id']}: {caption(c['date'])[10:]}, from a {c['type'].replace('_', ' ')} \"{c['headline']}\": "
        f"{c['who']}" + (f" ({c['guest_role']})" if c.get("guest_role") else "") + f": \"{c['text'][:240]}\""
        for c in clips)


def clip(seg: Segment, clip_id: str | None) -> dict | None:
    return next((c for c in seg.work.get("clips") or [] if c["id"] == clip_id), None) if clip_id else None


def check_placed(seg: Segment, outline) -> None:
    """Drop clip ids the outline made up or used twice, and any past PLACED_CLIPS."""
    used: set[str] = set()
    for sec in outline.sections:
        if not sec.archive_clip:
            continue
        if clip(seg, sec.archive_clip) is None or sec.archive_clip in used or len(used) >= PLACED_CLIPS:
            log.info("documentary %r: dropping archive clip %r from %r", seg.headline, sec.archive_clip, sec.heading)
            sec.archive_clip = None
        else:
            used.add(sec.archive_clip)


def clip_brief(c: dict) -> str:
    """What the section writer is told about its clip."""
    return (f"ARCHIVE FOOTAGE in this section: after your FIRST line, a clip from {caption(c['date'])[10:]} plays: "
            f"{c['who']}: \"{c['text']}\". Your first line leads into it (say when it was said); your second line "
            "picks up after it. Do not repeat the quote.")


def clip_line(c: dict, h: str, n: int) -> Line | None:
    """The clip as a line of the documentary, with its own copy of the audio: the source segment's
    cache entry may not be kept as long as the documentary's."""
    src = Path(c["wav"])
    if not src.exists():
        log.warning("archive clip %s: its audio %s is gone; leaving it out", c["id"], src.name)
        return None
    dest = CONFIG.paths.cache / f"{h}_clip{n}.wav"
    if not dest.exists():
        shutil.copyfile(src, dest)
    return Line(speaker=c["speaker"], text=c["text"], guest_name=c.get("guest_name"), guest_role=c.get("guest_role"),
                wav_path=dest, duration_s=c["duration_s"], mouth_env=c.get("mouth_env") or [],
                archive=caption(c["date"]))


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


REPEAT_WITHIN_S = 12 * 3600          # only last night's: one that aired longer ago than this isn't repeated


def repeat_due(world: World, now: float) -> bool:
    """True overnight from repeat_at for window_s, when last night's documentary hasn't been
    repeated yet."""
    start = _today_at(CONFIG.documentary.repeat_at, now)
    return (bool(world.last_documentary_hash) and world.last_documentary_repeated != world.last_documentary_hash
            and start <= now < start + CONFIG.documentary.window_s
            and 0 < now - world.last_documentary_aired_ts < REPEAT_WITHIN_S
            and schedule.show_at(now).id == "overnight")


def load_repeat(world: World) -> Segment | None:
    """Last night's documentary from the cache, to air again: labelled a repeat, and not recorded
    as an airing (special.mark_aired). Marks it repeated even if it can't be loaded, so a missing
    file doesn't get looked for at every test card."""
    from .special import SPECIAL_SLOT_BASE

    h = world.last_documentary_hash
    world.last_documentary_repeated = h
    try:
        seg = Segment.model_validate_json((CONFIG.paths.cache / f"{h}.json").read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        log.warning("documentary repeat: %s can't be loaded (%s)", h, e)
        return None
    if not seg.lines or not all(l.wav_path and Path(l.wav_path).exists() for l in seg.lines):
        log.warning("documentary repeat: %s is missing audio", h)
        return None
    seg.slot_id, seg.repeat, seg.content_hash = SPECIAL_SLOT_BASE + 900_000, True, h
    seg.work["strand"] = f"{seg.work.get('strand') or strand()} · REPEAT"
    log.info("documentary repeat: %r", seg.headline)
    return seg


def is_documentary(seg: Segment) -> bool:
    return seg.type is SegmentType.documentary and seg.work.get("format") == "documentary"
