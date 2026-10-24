"""Persistent state of the fictional town.

The world is the newsroom's memory. Every LLM call is stateless; the only
continuity comes from `summary_for_prompt()`, which is capped so a small
local model never drifts on a long context. After each segment is written
the writers call `record_headline` / `update_thread` so tomorrow's bulletin
can say "as we reported yesterday".
"""
from __future__ import annotations

import json
import logging
import random
import threading
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path

from .config import CONFIG

log = logging.getLogger(__name__)

MAX_THREADS_IN_PROMPT = 5
MAX_HEADLINES_IN_PROMPT = 10


@dataclass
class Character:
    id: str
    name: str
    role: str
    voice: str
    traits: list[str]


@dataclass
class Thread:
    id: str
    title: str
    status: str
    opened: str          # ISO date
    updated: str         # ISO date
    mentions: int = 0


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

    # ------------------------------------------------------------ prompt view

    def summary_for_prompt(self) -> str:
        chars = "\n".join(
            f"  - {c.id}: {c.name}, {c.role}; {', '.join(c.traits)}" for c in self.characters
        )
        threads = "\n".join(
            f"  - [{t.id}] {t.title} — {t.status} (covered {t.mentions}x)"
            for t in self.open_threads()[:MAX_THREADS_IN_PROMPT]
        ) or "  (none yet)"
        heads = "\n".join(f"  - {h}" for h in self.headlines[-MAX_HEADLINES_IN_PROMPT:]) or "  (none yet)"
        wx = self.last_weather
        wx_line = (
            f"{wx.get('map_state', 'unknown')}, {wx.get('temp_c', '?')}°C ({wx.get('headline', '')})"
            if wx else "no report yet"
        )
        return (
            f"Town: {self.town}, {self.region}. Population about {self.population:,}. "
            f"Founded {self.founded}. Landmarks: {', '.join(self.landmarks)}.\n"
            f"Today: {self.last_date}, broadcast day {self.broadcast_day}.\n"
            f"Characters (use ONLY these ids as speakers):\n{chars}\n"
            f"Last weather: {wx_line}\n"
            f"Open story threads (may be followed up by id):\n{threads}\n"
            f"Recent headlines (do NOT repeat these):\n{heads}"
        )

    def open_threads(self) -> list[Thread]:
        return sorted(self.threads, key=lambda t: t.updated, reverse=True)

    def voice_for(self, speaker: str) -> str:
        for c in self.characters:
            if c.id == speaker:
                return c.voice
        return CONFIG.tts.voices.get(speaker, "af_heart")

    # --------------------------------------------------------------- updates

    def record_headline(self, headline: str) -> None:
        headline = headline.strip()
        if headline and headline not in self.headlines:
            self.headlines.append(headline)
            self.headlines = self.headlines[-50:]

    def record_weather(self, map_state: str, temp_c: int, headline: str) -> None:
        self.last_weather = {"map_state": map_state, "temp_c": temp_c, "headline": headline}

    def update_thread(self, thread_id: str | None, title: str, status: str | None) -> str:
        """Follow up an existing thread or open a new one. Returns the thread id."""
        today = date.today().isoformat()
        if thread_id:
            for t in self.threads:
                if t.id == thread_id:
                    t.status = status or t.status
                    t.updated = today
                    t.mentions += 1
                    return t.id
        new_id = f"t{len(self.threads) + 1:03d}"
        self.threads.append(Thread(new_id, title[:80], status or "developing", today, today, 1))
        self.threads = self.threads[-20:]
        return new_id

    def roll_day_if_needed(self) -> None:
        today = date.today().isoformat()
        if today != self.last_date:
            self.last_date = today
            self.broadcast_day += 1


# ------------------------------------------------------------------- storage

_LOCK = threading.Lock()
_WORLD: World | None = None


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
        characters=[
            Character("anchor", "Dana Ferris", "evening news anchor", CONFIG.tts.voices.get("anchor", "af_heart"),
                      ["dry", "unflappable", "fond of the town"]),
            Character("weather", "Gordon Pell", "weather presenter", CONFIG.tts.voices.get("weather", "bm_george"),
                      ["cheerful", "over-explains fronts", "sailing enthusiast"]),
            Character("reporter", "Miles Okafor", "field reporter", CONFIG.tts.voices.get("reporter", "am_michael"),
                      ["earnest", "always slightly out of breath", "talks to everyone"]),
        ],
    )


def _to_dict(w: World) -> dict:
    return asdict(w)


def _from_dict(d: dict) -> World:
    d = dict(d)
    d["characters"] = [Character(**c) for c in d.get("characters", [])]
    d["threads"] = [Thread(**t) for t in d.get("threads", [])]
    return World(**d)


def load(path: Path | None = None) -> World:
    """Load the world (seeding it on first run). Cached process-wide."""
    global _WORLD
    with _LOCK:
        if _WORLD is None:
            path = path or CONFIG.paths.world
            if path.exists():
                _WORLD = _from_dict(json.loads(path.read_text(encoding="utf-8")))
                log.info("world loaded from %s (day %d, %d threads, %d headlines)",
                         path.name, _WORLD.broadcast_day, len(_WORLD.threads), len(_WORLD.headlines))
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
    logging.basicConfig(level=logging.INFO, format="%(levelname)-5s %(name)s: %(message)s")
    w = load()
    text = w.summary_for_prompt()
    print(text)
    print(f"\n--- {len(text)} chars, ~{len(text) // 4} tokens; saved {datetime.now():%H:%M:%S}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
