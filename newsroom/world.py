"""Persistent state of the fictional town: the story bible.

The world is the newsroom's memory and its cast list. Every LLM call is
stateless; continuity comes from the briefings built here:

- `summary_for_prompt()`: what a segment writer needs (capped, ~600 tokens).
- `summary_for_editor()`: the fuller view the editor and story desk use.

What lives here:
- Characters: the station's presenters (fixed voices).
- People: public figures seeded with the town (mayor, police, fire, MP,
  harbourmaster...) and residents promoted from special-report guests, each
  with a stable voice, speaking speed and look so they can come back.
- Threads: story lines with a phase, the beats aired so far, the people
  involved and a planned next development that follow-ups should deliver.
- Archive: every segment aired, for "as we reported" callbacks and, later,
  for documentary research over the town's own history.

Threads: the workers write the world and the player reads it every frame (and
writes it when a special airs), so every World method that reads or changes
shared state holds `World.lock`, an RLock, and `save()` holds it to take its
snapshot. Code outside this module that changes a Thread or Person it was
handed (the story desk) takes the lock itself. Model calls and TTS never run
under it, so the player waits milliseconds at most.
"""
from __future__ import annotations

import json
import logging
import random
import re
import functools
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from . import quay, schedule, sport
from .config import CONFIG
from .llm import CACHE_BREAK

log = logging.getLogger(__name__)

MAX_THREADS_IN_PROMPT = 5
MAX_HEADLINES_IN_PROMPT = 10
MAX_ARCHIVE = 1000
MAX_THREADS = 120               # closed, then faded, threads beyond this are dropped; open ones never are
# A story that broke is kept on the board this long whatever the cap (writers.BREAKING_LEAD_S).
_BREAKING_KEEP_S = 2 * 3600
STALE_WARNING_S = 6 * 3600      # the desk is told a thread is going quiet this long before it fades
HISTORY_DOCS = 5                # the documentaries the desk and editors are shown in full,
HISTORY_PER_DOC = 4             # with this many background facts each;
HISTORY_FACTS = 6               # the writers, this many of the newest background facts
GUEST_MEMORIES = 4              # what a guest said on air, the last few appearances
RETURN_RIPE_S = 12 * 3600       # a loose end waits this long (air time) before the guest is offered back
RETURN_EXPIRE_S = 7 * 86400     # and is forgotten after this

# "faded" is the code's, not the desk's: a thread that stopped moving on air (fade_threads).
PHASES = ("emerging", "developing", "peak", "resolving", "closed", "faded")
# A new story's headline joins an open or faded thread whose title shares this many words, and
# this share of the shorter title's words, beyond the common ones. Tried on the 160 threads of
# 2026-10-27: 38 joined, near enough all the same story (twelve threads were the fire engine).
SAME_STORY_WORDS = 3
SAME_STORY_SHARE = 0.6
SAME_STORY_SHARE_FADED = 0.75   # fire, station, engine of four came back; boat, crew, wait of five didn't
_STORY_STOP = frozenset("""a an the and or but of to in on at by for with from as is are was were be been it its his
her their this that these those after before over under up down out into off again still now new old more than
about says say said gets get got make makes made back takes take set sets keeps keep could would will may might
tonight today tomorrow morning evening night week weekend first last one two second here there what who
port wexley town harbour harbor local""".split())

# Voices for residents who are not seeded officials; chosen by name so a
# guest sounds the same if they come back. Officials have explicit voices.
# bf_isabella is the continuity announcer's alone, af_jessica Fran's, am_santa Hugh's, af_sarah Tamsin's, am_echo Howard's.
GUEST_VOICES_F = ["af_bella", "af_nicole", "bf_emma", "af_kore", "af_aoede", "af_nova", "af_sky",
                  "af_river", "af_alloy"]
GUEST_VOICES_M = ["am_puck", "bm_daniel", "am_fenrir", "bm_lewis", "bm_fable", "am_adam"]
GUEST_VOICES = GUEST_VOICES_F + GUEST_VOICES_M
OLD_VOICES_M: list[str] = []    # extra voices for old men only (am_santa was one, until Hugh took it)
# A guest's speaking speed: the old a little slower, the young a little quicker.
SPEEDS = {"young": [1.0, 1.04, 1.08], "middle": [0.95, 0.98, 1.0, 1.03], "old": [0.88, 0.92, 0.95],
          "": [0.92, 0.97, 1.0, 1.04, 1.08]}


@dataclass
class Character:
    id: str
    name: str
    role: str
    voice: str
    traits: list[str]
    speed: float = 1.0              # speaking speed: Hugh, in his sixties, takes his time
    lang: str = ""                  # Kokoro's pronunciation: "b" British; "" the station's own


@dataclass
class Person:
    """Someone who can be quoted or interviewed. kind: official | worthy | resident."""
    id: str
    name: str
    role: str
    kind: str
    voice: str
    speed: float = 1.0
    traits: list[str] = field(default_factory=list)
    notes: str = ""                 # current stance / what they are known for
    first_seen: str = ""
    appearances: int = 0
    age: str = ""                   # young | middle | old, from the script that booked them (their look)
    accent: str = ""                # british | american: british may voice them with British pronunciation
    # What they said on air, the last few ({date, show, said}), and anything left to ask them next
    # time ({ts, date, show, ask}, broadcast clock): a chat show may book them back for it.
    memories: list[dict] = field(default_factory=list)
    loose_ends: list[dict] = field(default_factory=list)


@dataclass
class Thread:
    id: str
    title: str
    status: str
    opened: str          # ISO date
    updated: str         # ISO date
    mentions: int = 0
    phase: str = "emerging"
    next_development: str = ""      # what should happen next (the story desk plans this)
    people: list[str] = field(default_factory=list)      # person ids
    beats: list[dict] = field(default_factory=list)      # {date, day, headline, status}
    breaking: str = ""              # ISO date it broke as breaking news (the light shows lead with it)
    breaking_ts: float = 0.0        # when it broke, on the broadcast clock (bulletins lead with it for a while)
    planned_ts: float = 0.0         # when the story desk last planned it (it plans a batch per call)
    moved_ts: float = 0.0           # when it last moved on air, on the broadcast clock (it fades when quiet)
    faded_ts: float = 0.0           # when it faded, on the broadcast clock
    merged_into: str = ""           # closed as a duplicate: a follow-up of it goes to this thread


def _locked(method):
    """Run a World method under the world's lock (an RLock: methods call each other)."""
    @functools.wraps(method)
    def run(self, *a, **k):
        with self.lock:
            return method(self, *a, **k)
    return run


@dataclass
class World:
    town: str
    region: str
    population: int
    founded: int
    characters: list[Character]
    threads: list[Thread] = field(default_factory=list)
    headlines: list[str] = field(default_factory=list)
    last_weather: dict = field(default_factory=dict)
    broadcast_day: int = 1
    last_date: str = field(default_factory=lambda: date.today().isoformat())
    landmarks: list[str] = field(default_factory=list)
    specials: list[dict] = field(default_factory=list)     # {title, thread_id, date}
    last_special_ts: float = 0.0
    last_editor_check_ts: float = 0.0
    people: list[Person] = field(default_factory=list)
    archive: list[dict] = field(default_factory=list)      # {date, day, type, headline, thread_id, people, text}
    last_story_plan_ts: float = 0.0
    desk_breaking: list[str] = field(default_factory=list)   # dates the story desk broke a story itself
    # What the story desk did each round ({at, planned, new, merges, note}, the last dozen), for the
    # senior editor, whose latest memo the desk then reads (senior.py).
    desk_notes: list[dict] = field(default_factory=list)
    senior_memo: str = ""
    senior_memo_at: str = ""                 # broadcast date and clock it was written
    last_senior_ts: float = 0.0
    seeded: list[str] = field(default_factory=list)   # the date of each story the desk or senior editor seeded
    inquiries: list[dict] = field(default_factory=list)   # The Inquiry's subjects: {date, thread_id, title, angle, questions, guest}
    # The nightly documentary: what each one established (its research timeline and sections), so the
    # canon it invents outlives the 400 characters the archive keeps; and the day markers.
    documentaries: list[dict] = field(default_factory=list)
    last_documentary_date: str = ""          # the broadcast day one was last commissioned
    last_documentary_aired: str = ""         # the day one last aired
    last_documentary_hash: str = ""          # the last one to air (its cache key), for the overnight repeat,
    last_documentary_aired_ts: float = 0.0   # when it aired (broadcast clock),
    last_documentary_repeated: str = ""      # and the last one repeated
    guest_returns: dict[str, str] = field(default_factory=dict)   # show id -> the day a guest last came back to it

    def __post_init__(self) -> None:
        self.lock = threading.RLock()        # not a field: asdict() and the JSON leave it out

    # ------------------------------------------------------------ prompt views

    def _people_lines(self, kinds: tuple[str, ...], limit: int) -> str:
        rows = [p for p in self.people if p.kind in kinds]
        rows.sort(key=lambda p: (-p.appearances, p.name))
        # The most seen make the list, in a fixed order: re-sorting by appearances after every segment
        # would change the cached head of the briefing (see llm.CACHE_BREAK).
        rows = sorted(rows[:limit], key=lambda p: p.name)
        return "\n".join(f"  - {p.name}, {p.role}" + (f"; {p.notes}" if p.notes else "") for p in rows) or "  (none yet)"

    def _history(self, *, full: bool) -> str:
        """What the documentaries established, so later pieces keep to it: the invented background
        especially (the town's founding in 1871), which nothing else on record holds. In full for
        the desk and the editors: each recent documentary's standfirst and its background. In brief
        for the writers: the newest few background facts. Empty before the first documentary.
        It changes once a day, so it sits in the cached head of the briefing."""
        docs = self.documentaries[-HISTORY_DOCS:]
        if not docs:
            return ""
        if full:
            rows = []
            for d in docs:
                rows.append(f"  - {d['date']}: {d['title']}: {d.get('standfirst', '')}")
                rows += [f"      established: {e.get('date', '')}: {e['event'][:160]}"
                         for e in d.get("timeline", []) if not e.get("on_record")][:HISTORY_PER_DOC]
            return ("Documentaries made (their history is canon: plan nothing that contradicts it):\n"
                    + "\n".join(rows) + "\n")
        facts = [f"  - {e.get('date', '')}: {e['event'][:140]}" for d in reversed(docs)
                 for e in d.get("timeline", []) if not e.get("on_record") and _before(e.get("date", ""), d["date"])
                 ][:HISTORY_FACTS]
        return ("Town history our documentaries have told (keep to it; never contradict it):\n"
                + "\n".join(facts) + "\n") if facts else ""

    def _thread_line(self, t: Thread, *, full: bool = False) -> str:
        last = t.beats[-1] if t.beats else None
        last_s = f"; last covered {last['date']}: {last['headline']}" if last else ""
        people = ", ".join(self.person(pid).name for pid in t.people if self.person(pid)) or "nobody named yet"
        nxt = f"; NEXT: {t.next_development}" if t.next_development else ""
        extra = f" (opened {t.opened}, covered {t.mentions}x)" if full else f" (opened {t.opened})"
        if full and t.moved_ts and t.phase != "faded":
            left = fade_after_s(t) - (schedule.now() - t.moved_ts)
            if left < STALE_WARNING_S:
                nxt += f"; GOING QUIET: fades off the air in about {max(1, round(left / 3600))}h unless it moves"
        return f"  - [{t.id}] {t.title} — {t.phase}{extra}{last_s}; people: {people}{nxt}"

    @_locked
    def summary_for_prompt(self, cast: tuple[str, ...] | None = None) -> str:
        """The town briefing. `cast` limits the presenters to one show's (see schedule.py)."""
        chars = "\n".join(
            f"  - {c.id}: {c.name}, {c.role}; {', '.join(c.traits)}"
            for c in self.characters if cast is None or c.id in cast
        )
        threads = "\n".join(self._thread_line(t) for t in self.briefing_threads()) or "  (none yet)"
        heads = "\n".join(f"  - {h}" for h in self.headlines[-MAX_HEADLINES_IN_PROMPT:]) or "  (none yet)"
        wx = self.last_weather
        wx_line = (
            f"{wx.get('map_state', 'unknown')}, {wx.get('temp_c', '?')}°C ({wx.get('headline', '')})"
            if wx else "no report yet"
        )
        return (
            f"Town: {self.town}, {self.region}. Population about {self.population:,}. "
            f"Founded {self.founded}. Landmarks: {', '.join(self.landmarks)}.\n"
            f"TODAY IS {self.last_date} ({datetime.fromisoformat(self.last_date):%A}), broadcast day {self.broadcast_day}. "
            f"Use these dates; do not invent how much time has passed.\n"
            f"Presenters (the ONLY allowed speaker ids in live segments):\n{chars}\n"
            f"Public figures who may be quoted or interviewed (by name, in the text):\n"
            f"{self._people_lines(('official', 'worthy'), 10)}\n{self._history(full=False)}{CACHE_BREAK}"
            f"Residents we have met before:\n{self._people_lines(('resident',), 6)}\n"
            f"Last weather: {wx_line}\n"
            f"Sport: {sport.briefing(datetime.fromtimestamp(schedule.now()))}\n"
            + (f"Quay: {q}\n" if (q := quay.summary(datetime.fromtimestamp(schedule.now()))) else "") +
            f"Open story threads (follow up by id; a follow-up must deliver the NEXT development or a step towards it):\n{threads}\n"
            f"Recent headlines (do NOT repeat these):\n{heads}"
        )

    @_locked
    def briefing_threads(self) -> list[Thread]:
        """The open threads the writers' briefing lists. Threads updated the same day tie on the
        date; the one followed up least often today goes first, so each follow-up moves a story
        down a place instead of keeping it on top."""
        live = sorted(self.open_threads(), reverse=True,
                      key=lambda t: (t.updated, -sum(b.get("date") == self.last_date for b in t.beats)))
        return live[:MAX_THREADS_IN_PROMPT]

    @_locked
    def summary_for_editor(self) -> str:
        """Fuller view for the editor and story desk."""
        threads = "\n".join(self._thread_line(t, full=True) for t in self.open_threads()) or "  (none)"
        faded = "\n".join(self._thread_line(t, full=True) for t in self.recently_faded()) or "  (none)"
        done = "\n".join(f"  - {s['date']}: {s['title']} (thread {s['thread_id']})" for s in self.specials[-10:]) or "  (none)"
        heads = "\n".join(f"  - {h}" for h in self.headlines[-20:]) or "  (none)"
        return (
            f"Town: {self.town}, {self.region}. TODAY IS {self.last_date}, broadcast day {self.broadcast_day}.\n"
            f"Public figures:\n{self._people_lines(('official', 'worthy'), 20)}\n{CACHE_BREAK}"
            f"Residents met so far:\n{self._people_lines(('resident',), 12)}\n"
            f"Open threads:\n{threads}\n"
            f"Recently faded off the air (revive one only if something new would really happen):\n{faded}\n"
            f"Specials already made (do not repeat these subjects):\n{done}\n"
            f"{self._history(full=True)}"
            f"Recent headlines:\n{heads}"
        )

    # ---------------------------------------------------------------- lookups

    @_locked
    def open_threads(self) -> list[Thread]:
        return sorted((t for t in self.threads if t.phase not in ("closed", "faded")), key=lambda t: t.updated,
                      reverse=True)

    @_locked
    def recently_faded(self, now: float | None = None, limit: int = 5) -> list[Thread]:
        """Threads that faded in the last three days, the most recent first: the desk may revive one."""
        now = now or schedule.now()
        faded = [t for t in self.threads if t.phase == "faded" and 0 <= now - t.faded_ts < 3 * 86400]
        return sorted(faded, key=lambda t: -t.faded_ts)[:limit]

    @_locked
    def thread(self, thread_id: str | None) -> Thread | None:
        return next((t for t in self.threads if t.id == thread_id), None)

    @_locked
    def same_story(self, headline: str) -> tuple[Thread, set[str]] | None:
        """The open or faded thread a new story's headline already is, by its title's words, and the
        words they share. The writers often leave thread_id empty for a story already running.
        Titles only: a thread's people and beats gather whatever its follow-ups mentioned.

        A faded thread, quiet for a day or more, comes back only on three-quarters of the shorter title
        (an open one on SAME_STORY_SHARE), and an open thread wins a tie: on 2026-10-28 "Lifeboat crew asks small boats to wait for
        daylight" revived "Harbour Boats Lashed Down as Crews Wait on Divers" on boat, crew and wait
        (the desk then merged it into the harbour wall), and a fire-crew piece went to a faded
        duplicate instead of the live second-engine thread."""
        new = _story_words(headline)
        best = None
        for t in self.threads:
            if t.phase == "closed":
                continue
            old = _story_words(t.title)
            shared = new & old
            share = SAME_STORY_SHARE_FADED if t.phase == "faded" else SAME_STORY_SHARE
            if len(shared) >= SAME_STORY_WORDS and len(shared) >= share * min(len(new), len(old)):
                rank = (len(shared), t.phase != "faded", t.moved_ts)
                if best is None or rank > best[2]:
                    best = (t, shared, rank)
        return best[:2] if best else None

    @_locked
    def person(self, person_id: str | None) -> Person | None:
        return next((p for p in self.people if p.id == person_id), None)

    @_locked
    def person_by_name(self, name: str | None) -> Person | None:
        if not name:
            return None
        key = name.strip().lower()
        for p in self.people:
            pk = p.name.lower()
            if pk == key or pk.split()[-1] == key.split()[-1] and key.split()[0] in pk:
                return p
        return None

    @_locked
    def character(self, speaker: str) -> Character | None:
        return next((c for c in self.characters if c.id == speaker), None)

    @_locked
    def presenter_named(self, name: str | None) -> Character | None:
        """A presenter booked as a guest (Gordon on his ghost tours) is still themselves."""
        key = (name or "").strip().lower()
        return next((c for c in self.characters if c.name.lower() == key), None) if key else None

    @_locked
    def voice_for(self, speaker: str, guest_name: str | None = None) -> str:
        if speaker == "guest":
            c = self.presenter_named(guest_name)
            if c:
                return c.voice
            p = self.person_by_name(guest_name)
            if p:
                return p.voice
            return GUEST_VOICES[_name_hash(guest_name) % len(GUEST_VOICES)]
        for c in self.characters:
            if c.id == speaker:
                return c.voice
        return CONFIG.tts.voices.get(speaker, "af_heart")

    @_locked
    def speed_for(self, speaker: str, guest_name: str | None = None) -> float:
        if speaker == "guest":
            if self.presenter_named(guest_name):
                return 1.0
            p = self.person_by_name(guest_name)
            if p:
                return p.speed
            return [0.92, 0.97, 1.0, 1.04, 1.08][_name_hash(guest_name) % 5]
        c = self.character(speaker)
        return c.speed if c else 1.0

    @_locked
    def lang_for(self, speaker: str, guest_name: str | None = None) -> str | None:
        """Kokoro's pronunciation for a line: British for a guest cast with a British accent when
        [tts] british_guests is on, or a presenter cast that way (Hugh); otherwise None, the station's own."""
        if speaker != "guest":
            c = self.character(speaker)
            return (c.lang or None) if c else None
        if CONFIG.tts.british_guests and not self.presenter_named(guest_name):
            p = self.person_by_name(guest_name)
            if p and p.accent == "british":
                return "b"
        return None

    # ---------------------------------------------------------------- updates

    @_locked
    def record_headline(self, headline: str) -> None:
        headline = headline.strip()
        if headline and headline not in self.headlines:
            self.headlines.append(headline)
            self.headlines = self.headlines[-50:]

    @_locked
    def record_weather(self, map_state: str, temp_c: int, headline: str) -> None:
        self.last_weather = {"map_state": map_state, "temp_c": temp_c, "headline": headline}

    @_locked
    def record_aired(self, seg_type: str, headline: str | None, thread_id: str | None, text: str,
                     show: str = "", brief: str = "", content_hash: str = "") -> None:
        """Archive entry for a scripted segment; also counts appearances of named people."""
        named = [p.id for p in self.people if p.name.split()[-1] in text and p.name.split()[0] in text]
        for pid in named:
            p = self.person(pid)
            p.appearances += 1
            if not p.first_seen:
                p.first_seen = self.last_date
        t = self.thread(thread_id)
        if t:
            for pid in named:
                if pid not in t.people:
                    t.people.append(pid)
        self.archive.append({
            "date": self.last_date, "day": self.broadcast_day, "type": seg_type,
            "headline": headline or "", "thread_id": thread_id, "people": named, "text": text[:400],
            "show": show, "brief": brief, "hash": content_hash,   # its cache entry: the documentary's footage
        })
        self.archive = self.archive[-MAX_ARCHIVE:]

    @_locked
    def aired_today(self, seg_type: str, show: str) -> list[dict]:
        """Today's archive entries of one type on one show, oldest first (entries from before
        the show was recorded don't count)."""
        return [e for e in self.archive
                if e["date"] == self.last_date and e["type"] == seg_type and e.get("show") == show]

    @_locked
    def update_thread(self, thread_id: str | None, title: str, status: str | None, now: float | None = None) -> str:
        """Follow up an existing thread or open a new one. Returns the thread id. A follow-up of a
        faded thread brings it back; one of a merged duplicate goes to the thread it joined."""
        today = self.last_date
        now = now or schedule.now()
        for _ in range(4):
            dup = self.thread(thread_id)
            if dup is None or not dup.merged_into:
                break
            thread_id = dup.merged_into
        if thread_id:
            for t in self.threads:
                if t.id == thread_id:
                    if t.phase == "faded":
                        t.phase = "developing"
                        log.info("thread %s back from faded: %s", t.id, title[:60])
                    t.status = status or t.status
                    t.updated = today
                    t.moved_ts = now
                    t.mentions += 1
                    t.beats.append({"date": today, "day": self.broadcast_day, "headline": title[:90], "status": t.status})
                    t.beats = t.beats[-12:]
                    if t.phase == "emerging":
                        t.phase = "developing"
                    return t.id
        new_id = self._new_thread_id()
        self.threads.append(Thread(new_id, title[:80], status or "developing", today, today, 1, moved_ts=now,
                                   beats=[{"date": today, "day": self.broadcast_day, "headline": title[:90], "status": status or ""}]))
        self._cap_threads()
        return new_id

    @_locked
    def merge_thread(self, dup_id: str, keep_id: str) -> bool:
        """Fold a duplicate into the thread that is the same story: its beats, coverage and people
        join it, its archive entries and specials point at it, and it closes, redirecting any later
        follow-up. False (nothing done) unless both are live threads and different."""
        dup, keep = self.thread(dup_id), self.thread(keep_id)
        if (dup is None or keep is None or dup is keep or "closed" in (dup.phase, keep.phase)
                or dup.merged_into or keep.merged_into):
            return False
        keep.beats = sorted(keep.beats + dup.beats, key=lambda b: b.get("day", 0))[-12:]
        keep.mentions += dup.mentions
        keep.people += [pid for pid in dup.people if pid not in keep.people]
        keep.next_development = keep.next_development or dup.next_development
        if dup.moved_ts > keep.moved_ts:              # the latest word on it
            keep.status = dup.status or keep.status
        if keep.phase == "faded" and dup.phase != "faded":
            keep.phase = dup.phase                      # a live duplicate brings the story back
        if keep.phase == "emerging":
            keep.phase = "developing"                   # covered under two titles, it has moved
        keep.updated, keep.moved_ts = max(keep.updated, dup.updated), max(keep.moved_ts, dup.moved_ts)
        if dup.breaking_ts > keep.breaking_ts:
            keep.breaking, keep.breaking_ts = dup.breaking, dup.breaking_ts
        for e in self.archive + self.specials:
            if e.get("thread_id") == dup.id:
                e["thread_id"] = keep.id
        dup.phase, dup.merged_into, dup.updated = "closed", keep.id, self.last_date
        return True

    def _cap_threads(self) -> None:
        """Keep at most MAX_THREADS: drop closed threads first, the least recently updated
        first, then faded ones, the longest faded first. Never drop an open thread (a plain
        [-40:] once evicted live stories); if every thread is open the list grows past the cap.
        fade_threads keeps the open ones in check."""
        excess = len(self.threads) - MAX_THREADS
        if excess <= 0:
            return
        gone = (sorted((t for t in self.threads if t.phase == "closed"), key=lambda t: t.updated)
                + sorted((t for t in self.threads if t.phase == "faded"), key=lambda t: t.faded_ts))
        drop = {t.id for t in gone[:excess]}
        self.threads = [t for t in self.threads if t.id not in drop]
        if len(self.threads) > MAX_THREADS:
            log.warning("%d threads, all open; keeping them all past the cap of %d",
                        len(self.threads), MAX_THREADS)

    @_locked
    def fade_threads(self, now: float | None = None) -> list[Thread]:
        """Threads that haven't moved on air for their window fade (`fade_after_s`): off the
        writers' and the desk's boards, kept for the desk to revive and for the documentary.
        Then, past `[story] max_live_threads` open, the stalest fade too, never a story at its
        peak or one that broke in the last two hours. On 2026-10-28 every guest chat and field
        report had opened a thread and nothing retired them: 108 open, the cap ignored."""
        now = now or schedule.now()
        live = self.open_threads()
        quiet = [t for t in live if t.moved_ts and now - t.moved_ts >= fade_after_s(t)]
        live = [t for t in live if t not in quiet]
        excess = len(live) - CONFIG.story.max_live_threads
        capped = []
        if excess > 0:
            spare = [t for t in live if t.phase != "peak"
                     and not (t.breaking_ts and 0 <= now - t.breaking_ts < _BREAKING_KEEP_S)]
            capped = sorted(spare, key=lambda t: (t.moved_ts, t.mentions))[:excess]
        # "over the cap" in the log is how a night shows whether max_live_threads is too low:
        # quiet fades are stories that stopped; cap fades are live ones squeezed out.
        for t, why in [(t, "quiet") for t in quiet] + [(t, "over the cap") for t in capped]:
            log.info("thread %s faded, %s (%s, %.0fh since it moved, covered %dx): %s", t.id, why, t.phase,
                     (now - t.moved_ts) / 3600, t.mentions, t.title[:60])
            t.phase, t.updated, t.faded_ts = "faded", self.last_date, now
        return quiet + capped

    def _new_thread_id(self) -> str:
        """One past the highest id ever used. Not the list's length: the list is capped at 40,
        so once full every new thread got the same id, and follow-ups landed on the wrong story."""
        used = [t.id for t in self.threads] + [a.get("thread_id") or "" for a in self.archive]
        return f"t{max((int(i[1:]) for i in used if i[1:].isdigit()), default=0) + 1:03d}"

    def _new_person_id(self) -> str:
        """One past the highest id used, as for threads: people can be removed (drop_presenter_people)."""
        return f"p{max((int(p.id[1:]) for p in self.people if p.id[1:].isdigit()), default=0) + 1:03d}"

    @_locked
    def drop_presenter_people(self) -> None:
        """Remove person entries that duplicate a presenter, and their ids in threads and the archive."""
        dupes = {p.id for p in self.people if self.presenter_named(p.name)}
        if not dupes:
            return
        log.warning("removing people who are presenters: %s", ", ".join(
            f"{p.id} {p.name}" for p in self.people if p.id in dupes))
        self.people = [p for p in self.people if p.id not in dupes]
        for t in self.threads:
            t.people = [pid for pid in t.people if pid not in dupes]
        for e in self.archive:
            e["people"] = [pid for pid in e.get("people", []) if pid not in dupes]

    @_locked
    def remember_guest(self, name: str, show: str, said: str | None, ask: str | None,
                       now: float | None = None) -> None:
        """Keep what a guest said on air and anything to ask them next time. A guest chat is not
        news: this is where it goes instead of a thread."""
        p = self.person_by_name(name)
        if p is None:
            return
        now = now or schedule.now()
        if said and said.strip():
            p.memories = (p.memories + [{"date": self.last_date, "show": show, "said": said.strip()}])[-GUEST_MEMORIES:]
        if ask and ask.strip():
            keep = [e for e in p.loose_ends if now - e["ts"] < RETURN_EXPIRE_S][-1:]
            p.loose_ends = keep + [{"ts": now, "date": self.last_date, "show": show, "ask": ask.strip()}]

    @_locked
    def return_guests(self, now: float | None = None, exclude: set[str] = frozenset(),
                      limit: int = 1) -> list[Person]:
        """Guests with something to be asked: a loose end at least RETURN_RIPE_S old and not yet
        forgotten. The longest waiting first; nobody in `exclude` (names, the recent guests)."""
        now = now or schedule.now()
        skip = {n.lower() for n in exclude}
        ripe = []
        for p in self.people:
            waiting = [e["ts"] for e in p.loose_ends if RETURN_RIPE_S <= now - e["ts"] < RETURN_EXPIRE_S]
            if waiting and p.name.lower() not in skip and not self.presenter_named(p.name):
                ripe.append((min(waiting), p))
        return [p for _, p in sorted(ripe, key=lambda r: r[0])][:limit]

    @_locked
    def asked_back(self, name: str, show_id: str) -> None:
        """A guest came back for their loose ends: they've been asked, and the show has had its
        return visit today."""
        self.loose_ends_taken(name)
        self.guest_returns[show_id] = self.last_date

    @_locked
    def loose_ends_taken(self, name: str) -> Person | None:
        """A guest's loose ends are spoken for (asked on air, or become a news story)."""
        p = self.person_by_name(name)
        if p is not None:
            p.loose_ends = []
        return p

    @_locked
    def fresh_loose_ends(self, now: float | None = None, limit: int = 5) -> list[tuple[Person, dict]]:
        """The newest loose ends guests have left, one per guest, for the story desk: a few may be news."""
        now = now or schedule.now()
        ends = [(p, p.loose_ends[-1]) for p in self.people
                if p.loose_ends and 0 <= now - p.loose_ends[-1]["ts"] < RETURN_EXPIRE_S]
        return sorted(ends, key=lambda pe: -pe[1]["ts"])[:limit]

    @_locked
    def mark_breaking(self, thread_id: str | None, ts: float) -> None:
        t = self.thread(thread_id)
        if t is not None:
            t.phase, t.breaking, t.breaking_ts, t.moved_ts = "peak", self.last_date, ts, ts

    @_locked
    def seed_thread(self, title: str, status: str, next_development: str, people: list[str]) -> Thread:
        """A story the desk wants to exist before anyone has covered it."""
        t = Thread(self._new_thread_id(), title[:80], status[:160], self.last_date, self.last_date, 0,
                   phase="emerging", next_development=next_development[:200], people=people,
                   moved_ts=schedule.now())
        self.threads.append(t)
        self.seeded = (self.seeded + [self.last_date])[-50:]
        self._cap_threads()
        return t

    @_locked
    def seeds_left(self) -> int:
        """How many more stories the desk and the senior editor may seed today."""
        return max(0, CONFIG.story.seeds_per_day - self.seeded.count(self.last_date))

    @_locked
    def ensure_person(self, name: str, role: str | None, kind: str = "resident", gender: str | None = None,
                      age: str | None = None, accent: str | None = None) -> Person | None:
        """Return the known person, or promote a new guest to the recurring cast. None for a
        presenter: they are cast already, and a second Gordon Pell as a resident took the credit
        for every mention of the weatherman. The script's hints cast them: gender and age pick
        the voice and its speed, the accent its pronunciation (`lang_for`). Someone already
        cast keeps their voice; a missing age is filled in, for their look."""
        if self.presenter_named(name):
            return None
        p = self.person_by_name(name)
        if p:
            if role and role != "resident" and p.role in ("", "resident"):
                p.role = role                       # met in a vox pop, now we know what they do
            if age and not p.age:
                p.age = age
            return p
        h = _name_hash(name)
        pool = {"f": GUEST_VOICES_F, "m": GUEST_VOICES_M}.get(gender or "", GUEST_VOICES)
        if gender == "m" and age == "old":
            pool = pool + OLD_VOICES_M
        speeds = SPEEDS.get(age or "", SPEEDS[""])
        p = Person(
            id=self._new_person_id(), name=name.strip()[:40], role=(role or "resident")[:50], kind=kind,
            voice=pool[h % len(pool)], speed=speeds[(h >> 8) % len(speeds)],
            first_seen=self.last_date, age=age or "", accent=accent or "",
        )
        self.people.append(p)
        log.info("new %s in the cast: %s, %s", kind, p.name, p.role)
        return p

    @_locked
    def record_special(self, title: str, thread_id: str | None, *, cooldown: bool = True) -> None:
        """A finished special or documentary: neither repeats the other's subject. Only a special
        starts the editor's cooldown; the documentary has its own slot."""
        self.specials.append({"title": title, "thread_id": thread_id, "date": self.last_date})
        self.specials = self.specials[-30:]
        if cooldown:
            self.last_special_ts = time.time()

    @_locked
    def record_documentary(self, entry: dict) -> None:
        self.documentaries.append(entry)
        self.documentaries = self.documentaries[-30:]

    @_locked
    def roll_day_if_needed(self) -> None:
        today = date.fromtimestamp(schedule.now()).isoformat()     # the broadcast clock's day (--clock)
        if today != self.last_date:
            self.last_date = today
            self.broadcast_day += 1

    @_locked
    def search_archive(self, query: str, limit: int = 12) -> list[dict]:
        """Keyword search over past coverage (for documentary research)."""
        words = [w for w in query.lower().split() if len(w) > 3]
        scored = []
        for e in self.archive:
            blob = f"{e['headline']} {e['text']}".lower()
            score = sum(blob.count(w) for w in words)
            if score:
                scored.append((score, e))
        scored.sort(key=lambda s: -s[0])
        return [e for _, e in scored[:limit]]


def _story_words(title: str) -> set[str]:
    """A headline's telling words: lower case, plural s off, the common and the town's own words out."""
    words = re.findall(r"[a-z]+", title.lower().replace("'s", ""))
    return {w[:-1] if w.endswith("s") and not w.endswith("ss") and len(w) > 4 else w
            for w in words if w not in _STORY_STOP and len(w) > 2}


def _before(when: str, day: str) -> bool:
    """Is a timeline date ("1871", "March 1953", "Thursday 2026-10-29") history by `day` (ISO)? A
    documentary's background also holds what it expected to happen ("Scheduled: ... on Thursday"),
    which would go stale in every writer's briefing. Undated entries aren't history either."""
    if m := re.search(r"\d{4}-\d{2}-\d{2}", when):
        return m.group() < day
    if m := re.search(r"\b(1[0-9]{3}|20[0-9]{2})\b", when):
        return int(m.group()) < int(day[:4])
    return False


def fade_after_s(t: Thread) -> float:
    """How long a thread may go without moving on air before it fades: a story at its peak
    longest, a one-off (covered once or twice) soonest, one that is resolving soon after."""
    s = CONFIG.story
    h = (s.fade_peak_h if t.phase == "peak" else s.fade_resolving_h if t.phase == "resolving"
         else s.fade_oneoff_h if t.mentions <= 2 else s.fade_quiet_h)
    return h * 3600


def _name_hash(name: str | None) -> int:
    return sum(map(ord, (name or "guest").strip().lower()))


# ------------------------------------------------------------------- storage

_LOCK = threading.Lock()
_SAVE_LOCK = threading.Lock()
_WORLD: World | None = None


def seed_people() -> list[Person]:
    """Port Wexley's public figures and local worthies. Specific on purpose."""
    today = date.today().isoformat()
    rows = [
        ("Helen Strand", "Mayor of Port Wexley", "official", "bf_isabella", 1.0,
         ["brisk", "never misses a ribbon-cutting"], "running for a third term next spring"),
        ("Raymond Doyle", "Chief Inspector, Port Wexley police", "official", "bm_daniel", 0.95,
         ["weary", "precise"], "dislikes being asked about the cannery"),
        ("Bea Kowalczyk", "Station Officer, Port Wexley fire station", "official", "af_kore", 1.02,
         ["practical", "dry"], "campaigning for a second engine"),
        ("Oliver Fenwick-Hale", "Member of Parliament for Greymouth Coast", "official", "bm_fable", 0.98,
         ["rarely in town", "fond of a photo opportunity"], "promised money for the harbour wall"),
        ("Ivy Marchetti", "Harbourmaster", "official", "bf_emma", 1.0,
         ["territorial about the harbour", "knows every boat"], ""),
        ("Samuel Achebe", "Head teacher, Greymouth Academy", "worthy", "am_fenrir", 0.97,
         ["earnest", "quotes poetry"], ""),
        ("Tam Buchanan", "Lifeboat coxswain", "worthy", "bm_lewis", 0.93,
         ["laconic", "a local hero who hates the word"], ""),
        ("Marjorie Pell", "Chair, Wexley Historical Society; Gordon Pell's aunt", "worthy", "af_aoede", 0.95,
         ["formidable", "corrects dates"], "writing a history of the cannery"),
        ("Dev Ramachandran", "Baker, Harrow Street market", "resident", "am_puck", 1.05,
         ["cheerful", "renames his bakes after the news"], ""),
    ]
    return [Person(f"p{i + 1:03d}", n, r, k, v, s, tr, notes, today, 0) for i, (n, r, k, v, s, tr, notes) in enumerate(rows)]


def seed() -> World:
    """A fresh town. Deliberately specific so the model has hooks to riff on."""
    rng = random.Random(42)
    return World(
        town="Port Wexley",
        region="on the Greymouth coast",
        population=rng.randint(18_000, 24_000),
        founded=1871,
        landmarks=[
            "the old cannery on the harbour", "Wexley Town Hall clock",
            "the Greymouth lighthouse", "Harrow Street market", "the Tidewater Stadium",
        ],
        characters=seed_characters(),
        people=seed_people(),
    )


def seed_characters() -> list[Character]:
    """The station's presenters. Each show's cast is a subset of them (schedule.py)."""
    return [
        Character("anchor", "Dana Ferris", "evening news anchor", CONFIG.tts.voices.get("anchor", "af_heart"),
                  ["dry", "unflappable", "fond of the town"]),
        Character("weather", "Gordon Pell", "weather presenter", CONFIG.tts.voices.get("weather", "bm_george"),
                  ["cheerful", "over-explains fronts", "sailing enthusiast"]),
        Character("reporter", "Miles Okafor", "field reporter", CONFIG.tts.voices.get("reporter", "am_michael"),
                  ["earnest", "always slightly out of breath", "talks to everyone"]),
        Character("host_a", "Rosie Treloar", "breakfast presenter, Morning Tide",
                  CONFIG.tts.voices.get("host_a", "bf_lily"),
                  ["bright", "up since four and proud of it", "keeps the diary of what's on"]),
        Character("host_b", "Jonah Pike", "breakfast co-presenter, Morning Tide",
                  CONFIG.tts.voices.get("host_b", "am_eric"),
                  ["laid-back", "a weakness for puns", "a former local-radio DJ"]),
        Character("mag_a", "Pat Holloway", "presenter, Coastwide (the early-evening magazine)",
                  CONFIG.tts.voices.get("mag_a", "bf_alice"),
                  ["warm", "a former consumer champion", "never lets a vague answer go"]),
        Character("mag_b", "Clive Ashdown", "presenter, Coastwide (the early-evening magazine)",
                  CONFIG.tts.voices.get("mag_b", "am_liam"),
                  ["excitable about local oddities", "collects facts nobody asked for", "Pat's foil"]),
        Character("late_host", "Vincent Marr", "host, The Last Ferry (late-night talk show)",
                  CONFIG.tts.voices.get("late_host", "am_onyx"),
                  ["raconteur", "a former foreign correspondent who came home", "lets guests talk"]),
        Character("sport", "Fran Kellaway", "sports presenter (the news, and Full Time at 18:45)",
                  CONFIG.tts.voices.get("sport", "af_jessica"),
                  ["quick and keen", "played for the county until her knee went", "knows everyone at the club"]),
        # Full Time's reporter at the grounds and the pubs, so Miles isn't on three shows an evening.
        Character("sport_reporter", "Tamsin Jago", "sports reporter (Full Time: the grounds, the clubs and the pubs)",
                  CONFIG.tts.voices.get("sport_reporter", "af_sarah"),
                  ["twenty-five and Port Wexley born", "played for the Tides' women's side",
                   "knows everyone at the Quarry Field and every darts pub", "a bit cheeky with Fran"], lang="b"),
        # Quayside's presenter at 13:00: the town's money, the quay's prices, its firms and jobs.
        Character("business", "Howard Lanyon", "business presenter (Quayside at 13:00)",
                  CONFIG.tts.voices.get("business", "am_echo"),
                  ["ran the Harrow Street bank branch for thirty years", "knows who owes whom",
                   "dry wit", "reads the figures like tea leaves"], speed=0.95, lang="b"),
        # Shared with the entertainment channel planned in E:\programming\mini-TVChannel (same town).
        Character("historian", "Hugh Tremayne", "local-history presenter (the history documentaries)",
                  CONFIG.tts.voices.get("historian", "am_santa"),
                  ["a former history teacher at Greymouth Academy", "knows a story about every street",
                   "tells it with a twinkle"], speed=0.92, lang="b"),
    ]


def _to_dict(w: World) -> dict:
    return asdict(w)


def _from_dict(d: dict) -> World:
    d = dict(d)
    d["characters"] = [Character(**c) for c in d.get("characters", [])]
    d["threads"] = [Thread(**t) for t in d.get("threads", [])]
    d["people"] = [Person(**p) for p in d.get("people", [])]
    w = World(**d)
    now = schedule.now()
    for t in w.threads:                    # saved before threads faded: a full window from now
        if not t.moved_ts and t.phase not in ("closed", "faded"):
            t.moved_ts = now
    if not w.people:                       # migrate a world saved before the cast existed
        w.people = seed_people()
        log.info("world migrated: seeded %d public figures", len(w.people))
    have = {c.id for c in w.characters}
    for c in seed_characters():            # presenters added since the world was saved
        if c.id not in have:
            w.characters.append(c)
            log.info("world migrated: new presenter %s (%s)", c.name, c.id)
    _recast_presenter_voices(w)
    return w


def _recast_presenter_voices(w: World) -> None:
    """Nobody in the town shares a presenter's voice: a guest cast before a presenter joined
    (Maureen Tapp, before Fran took af_jessica) gets another from their pool, by name as ever."""
    taken = {c.voice for c in w.characters}
    for p in w.people:
        if p.voice in taken:
            pool = GUEST_VOICES_F if p.voice[1:2] == "f" else GUEST_VOICES_M
            old, p.voice = p.voice, pool[_name_hash(p.name) % len(pool)]
            log.info("world migrated: %s shared %s with a presenter; now %s", p.name, old, p.voice)


def load(path: Path | None = None) -> World:
    """Load the world (seeding it on first run). Cached process-wide."""
    global _WORLD
    with _LOCK:
        if _WORLD is None:
            path = path or CONFIG.paths.world
            if path.exists():
                _WORLD = _from_dict(json.loads(path.read_text(encoding="utf-8")))
                _WORLD.drop_presenter_people()
                log.info("world loaded from %s (day %d, %d threads, %d people, %d archived)",
                         path.name, _WORLD.broadcast_day, len(_WORLD.threads), len(_WORLD.people), len(_WORLD.archive))
            else:
                _WORLD = seed()
                save(_WORLD, path)
                log.info("world seeded: %s", _WORLD.town)
            _WORLD.roll_day_if_needed()
        return _WORLD


def save(w: World | None = None, path: Path | None = None) -> None:
    w = w or _WORLD
    if w is None:
        return
    path = path or CONFIG.paths.world
    with w.lock:                              # a consistent snapshot; the disk write is outside it
        text = json.dumps(_to_dict(w), indent=2, ensure_ascii=False)
    with _SAVE_LOCK:                          # two workers saving at once would share the .tmp file
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(text, encoding="utf-8")
        tmp.replace(path)


def _fade_backlog(w: World, *, dry: bool) -> int:
    """`python -m newsroom.world fade [--dry]`: retire a world saved before threads faded. Never
    while the station is running: it saves the world too. Threads without `moved_ts` get one from
    their last day (noon, at most now); threads a light show opened fade, as they'd no longer open;
    then the normal fade pass and the cap."""
    raw = json.loads(CONFIG.paths.world.read_text(encoding="utf-8"))
    undated = {t["id"] for t in raw.get("threads", []) if not t.get("moved_ts")}
    now = schedule.now()
    with w.lock:
        before = len(w.open_threads())
        for t in w.open_threads():
            if t.id in undated:
                noon = datetime.fromisoformat(t.updated).replace(hour=12).timestamp()
                t.moved_ts = min(noon, now)
        first = {}
        for e in w.archive:
            if e.get("thread_id"):
                first.setdefault(e["thread_id"], e)
        light = [t for t in w.open_threads() if (e := first.get(t.id)) and e.get("type") != "breaking"
                 and e.get("show") in schedule.SHOWS and schedule.SHOWS[e["show"]].light]
        for t in light:
            log.info("thread %s opened by %s (%s): fades: %s", t.id, first[t.id]["show"], first[t.id]["type"],
                     t.title[:60])
            t.phase, t.updated, t.faded_ts = "faded", w.last_date, now
        faded = w.fade_threads(now)
        print(f"{before} open before; {len(light)} opened by light shows and {len(faded)} more faded; "
              f"{len(w.open_threads())} open now:")
        for t in w.open_threads():
            print(f"  [{t.id}] {t.phase:<10} {t.mentions:>2}x  {t.title}")
    if dry:
        print("(dry run: nothing saved)")
    else:
        save(w)
    return 0


def _cli() -> int:
    import sys

    logging.basicConfig(level=logging.INFO, format="%(levelname)-5s %(name)s: %(message)s")
    w = load()
    if len(sys.argv) > 1 and sys.argv[1] == "editor":
        text = w.summary_for_editor()
    elif len(sys.argv) > 1 and sys.argv[1] == "archive":
        for e in w.archive[-20:]:
            print(f"{e['date']} d{e['day']} {e['type']:<13} {e['headline']}  [{e['thread_id']}]")
        return 0
    elif len(sys.argv) > 1 and sys.argv[1] == "fade":
        return _fade_backlog(w, dry="--dry" in sys.argv)
    else:
        text = w.summary_for_prompt()
    text = text.replace(CACHE_BREAK, "")
    print(text)
    print(f"\n--- {len(text)} chars, ~{len(text) // 4} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
