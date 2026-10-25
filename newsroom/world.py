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
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from .config import CONFIG

log = logging.getLogger(__name__)

MAX_THREADS_IN_PROMPT = 5
MAX_HEADLINES_IN_PROMPT = 10
MAX_ARCHIVE = 1000

PHASES = ("emerging", "developing", "peak", "resolving", "closed")

# Voices for residents who are not seeded officials; chosen by name so a
# guest sounds the same if they come back. Officials have explicit voices.
GUEST_VOICES_F = ["af_bella", "af_nicole", "bf_emma", "af_kore", "bf_isabella", "af_aoede"]
GUEST_VOICES_M = ["am_puck", "bm_daniel", "am_fenrir", "bm_lewis", "bm_fable"]
GUEST_VOICES = GUEST_VOICES_F + GUEST_VOICES_M


@dataclass
class Character:
    id: str
    name: str
    role: str
    voice: str
    traits: list[str]


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

    # ------------------------------------------------------------ prompt views

    def _people_lines(self, kinds: tuple[str, ...], limit: int) -> str:
        rows = [p for p in self.people if p.kind in kinds]
        rows.sort(key=lambda p: (-p.appearances, p.name))
        return "\n".join(f"  - {p.name}, {p.role}" + (f"; {p.notes}" if p.notes else "") for p in rows[:limit]) or "  (none yet)"

    def _thread_line(self, t: Thread, *, full: bool = False) -> str:
        last = t.beats[-1] if t.beats else None
        last_s = f"; last covered {last['date']}: {last['headline']}" if last else ""
        people = ", ".join(self.person(pid).name for pid in t.people if self.person(pid)) or "nobody named yet"
        nxt = f"; NEXT: {t.next_development}" if t.next_development else ""
        extra = f" (opened {t.opened}, covered {t.mentions}x)" if full else f" (opened {t.opened})"
        return f"  - [{t.id}] {t.title} — {t.phase}{extra}{last_s}; people: {people}{nxt}"

    def summary_for_prompt(self, cast: tuple[str, ...] | None = None) -> str:
        """The town briefing. `cast` limits the presenters to one show's (see schedule.py)."""
        chars = "\n".join(
            f"  - {c.id}: {c.name}, {c.role}; {', '.join(c.traits)}"
            for c in self.characters if cast is None or c.id in cast
        )
        threads = "\n".join(self._thread_line(t) for t in self.open_threads()[:MAX_THREADS_IN_PROMPT]) or "  (none yet)"
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
            f"{self._people_lines(('official', 'worthy'), 10)}\n"
            f"Residents we have met before:\n{self._people_lines(('resident',), 6)}\n"
            f"Last weather: {wx_line}\n"
            f"Open story threads (follow up by id; a follow-up must deliver the NEXT development or a step towards it):\n{threads}\n"
            f"Recent headlines (do NOT repeat these):\n{heads}"
        )

    def summary_for_editor(self) -> str:
        """Fuller view for the editor and story desk."""
        threads = "\n".join(self._thread_line(t, full=True) for t in self.open_threads()) or "  (none)"
        done = "\n".join(f"  - {s['date']}: {s['title']} (thread {s['thread_id']})" for s in self.specials[-10:]) or "  (none)"
        heads = "\n".join(f"  - {h}" for h in self.headlines[-20:]) or "  (none)"
        return (
            f"Town: {self.town}, {self.region}. TODAY IS {self.last_date}, broadcast day {self.broadcast_day}.\n"
            f"Public figures:\n{self._people_lines(('official', 'worthy'), 20)}\n"
            f"Residents met so far:\n{self._people_lines(('resident',), 12)}\n"
            f"Open threads:\n{threads}\n"
            f"Specials already made (do not repeat these subjects):\n{done}\n"
            f"Recent headlines:\n{heads}"
        )

    # ---------------------------------------------------------------- lookups

    def open_threads(self) -> list[Thread]:
        return sorted((t for t in self.threads if t.phase != "closed"), key=lambda t: t.updated, reverse=True)

    def thread(self, thread_id: str | None) -> Thread | None:
        return next((t for t in self.threads if t.id == thread_id), None)

    def person(self, person_id: str | None) -> Person | None:
        return next((p for p in self.people if p.id == person_id), None)

    def person_by_name(self, name: str | None) -> Person | None:
        if not name:
            return None
        key = name.strip().lower()
        for p in self.people:
            pk = p.name.lower()
            if pk == key or pk.split()[-1] == key.split()[-1] and key.split()[0] in pk:
                return p
        return None

    def character(self, speaker: str) -> Character | None:
        return next((c for c in self.characters if c.id == speaker), None)

    def presenter_named(self, name: str | None) -> Character | None:
        """A presenter booked as a guest (Gordon on his ghost tours) is still themselves."""
        key = (name or "").strip().lower()
        return next((c for c in self.characters if c.name.lower() == key), None) if key else None

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

    def speed_for(self, speaker: str, guest_name: str | None = None) -> float:
        if speaker == "guest":
            if self.presenter_named(guest_name):
                return 1.0
            p = self.person_by_name(guest_name)
            if p:
                return p.speed
            return [0.92, 0.97, 1.0, 1.04, 1.08][_name_hash(guest_name) % 5]
        return 1.0

    # ---------------------------------------------------------------- updates

    def record_headline(self, headline: str) -> None:
        headline = headline.strip()
        if headline and headline not in self.headlines:
            self.headlines.append(headline)
            self.headlines = self.headlines[-50:]

    def record_weather(self, map_state: str, temp_c: int, headline: str) -> None:
        self.last_weather = {"map_state": map_state, "temp_c": temp_c, "headline": headline}

    def record_aired(self, seg_type: str, headline: str | None, thread_id: str | None, text: str) -> None:
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
        })
        self.archive = self.archive[-MAX_ARCHIVE:]

    def update_thread(self, thread_id: str | None, title: str, status: str | None) -> str:
        """Follow up an existing thread or open a new one. Returns the thread id."""
        today = self.last_date
        if thread_id:
            for t in self.threads:
                if t.id == thread_id:
                    t.status = status or t.status
                    t.updated = today
                    t.mentions += 1
                    t.beats.append({"date": today, "day": self.broadcast_day, "headline": title[:90], "status": t.status})
                    t.beats = t.beats[-12:]
                    if t.phase == "emerging":
                        t.phase = "developing"
                    return t.id
        new_id = f"t{len(self.threads) + 1:03d}"
        self.threads.append(Thread(new_id, title[:80], status or "developing", today, today, 1,
                                   beats=[{"date": today, "day": self.broadcast_day, "headline": title[:90], "status": status or ""}]))
        self.threads = self.threads[-40:]
        return new_id

    def mark_breaking(self, thread_id: str | None) -> None:
        t = self.thread(thread_id)
        if t is not None:
            t.phase, t.breaking = "peak", self.last_date

    def seed_thread(self, title: str, status: str, next_development: str, people: list[str]) -> Thread:
        """A story the desk wants to exist before anyone has covered it."""
        t = Thread(f"t{len(self.threads) + 1:03d}", title[:80], status[:160], self.last_date, self.last_date, 0,
                   phase="emerging", next_development=next_development[:200], people=people)
        self.threads.append(t)
        self.threads = self.threads[-40:]
        return t

    def ensure_person(self, name: str, role: str | None, kind: str = "resident", gender: str | None = None) -> Person:
        """Return the known person, or promote a new guest to the recurring cast."""
        p = self.person_by_name(name)
        if p:
            if role and not p.role:
                p.role = role
            return p
        h = _name_hash(name)
        pool = {"f": GUEST_VOICES_F, "m": GUEST_VOICES_M}.get(gender or "", GUEST_VOICES)
        p = Person(
            id=f"p{len(self.people) + 1:03d}", name=name.strip()[:40], role=(role or "resident")[:50], kind=kind,
            voice=pool[h % len(pool)], speed=[0.92, 0.97, 1.0, 1.04, 1.08][h % 5],
            first_seen=self.last_date,
        )
        self.people.append(p)
        log.info("new %s in the cast: %s, %s", kind, p.name, p.role)
        return p

    def record_special(self, title: str, thread_id: str | None) -> None:
        self.specials.append({"title": title, "thread_id": thread_id, "date": self.last_date})
        self.specials = self.specials[-30:]
        self.last_special_ts = time.time()

    def roll_day_if_needed(self) -> None:
        today = date.today().isoformat()
        if today != self.last_date:
            self.last_date = today
            self.broadcast_day += 1

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


def _name_hash(name: str | None) -> int:
    return sum(map(ord, (name or "guest").strip().lower()))


# ------------------------------------------------------------------- storage

_LOCK = threading.Lock()
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
    ]


def _to_dict(w: World) -> dict:
    return asdict(w)


def _from_dict(d: dict) -> World:
    d = dict(d)
    d["characters"] = [Character(**c) for c in d.get("characters", [])]
    d["threads"] = [Thread(**t) for t in d.get("threads", [])]
    d["people"] = [Person(**p) for p in d.get("people", [])]
    w = World(**d)
    if not w.people:                       # migrate a world saved before the cast existed
        w.people = seed_people()
        log.info("world migrated: seeded %d public figures", len(w.people))
    have = {c.id for c in w.characters}
    for c in seed_characters():            # presenters added since the world was saved
        if c.id not in have:
            w.characters.append(c)
            log.info("world migrated: new presenter %s (%s)", c.name, c.id)
    return w


def load(path: Path | None = None) -> World:
    """Load the world (seeding it on first run). Cached process-wide."""
    global _WORLD
    with _LOCK:
        if _WORLD is None:
            path = path or CONFIG.paths.world
            if path.exists():
                _WORLD = _from_dict(json.loads(path.read_text(encoding="utf-8")))
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
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(_to_dict(w), indent=2, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


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
    else:
        text = w.summary_for_prompt()
    print(text)
    print(f"\n--- {len(text)} chars, ~{len(text) // 4} tokens")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
