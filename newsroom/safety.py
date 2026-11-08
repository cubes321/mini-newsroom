"""The last look at words before they go out on a public stream.

The models are asked for a cosy, pre-watershed local station and nearly always give one, but a
public channel can't take "nearly": one bad line is a strike. This is a plain word list, not a
judge of taste. A term in assets/safety/blocklist.txt (or [safety] extra_terms in config.toml)
matches as a whole word, any case; a term ending in "*" also matches the words it starts.

The writers check a script before they keep it (writers.py asks again once, then the template
stands in), the back office checks adverts, notices and specials, and tts.synthesize checks
every line it voices, so nothing that slips past a writer is ever spoken.
"""
from __future__ import annotations

import functools
import logging
import re
from collections.abc import Iterable
from pathlib import Path

from .config import CONFIG

log = logging.getLogger(__name__)

BLOCKLIST = CONFIG.paths.assets / "safety" / "blocklist.txt"


class Unsafe(RuntimeError):
    """Text that mustn't go on air."""


def _terms(path: Path) -> list[str]:
    if not path.exists():
        return []
    return [t for raw in path.read_text(encoding="utf-8").splitlines()
            if (t := raw.split("#", 1)[0].strip().lower())]


@functools.cache
def _pattern() -> re.Pattern | None:
    terms = _terms(BLOCKLIST) + [t.strip().lower() for t in CONFIG.safety.extra_terms if t.strip()]
    parts = sorted({re.escape(t[:-1]) + r"\w*" if t.endswith("*") else re.escape(t) for t in terms},
                   key=len, reverse=True)
    if not parts:
        return None
    return re.compile(r"(?<!\w)(?:" + "|".join(parts) + r")(?!\w)", re.IGNORECASE)


def _plain(text: str) -> str:
    # Curly quotes and dashes the models like, so "x’s" still reads as a word and its 's.
    return text.replace("’", "'").replace("‘", "'")


def check(texts: str | Iterable[str]) -> str | None:
    """The first blocked term in `texts`, or None if they may go on air."""
    if not CONFIG.safety.enabled or (pat := _pattern()) is None:
        return None
    for t in [texts] if isinstance(texts, str) else texts:
        if t and (m := pat.search(_plain(t))):
            return m.group(0)
    return None


def strings(obj) -> list[str]:
    """Every string in a script: a pydantic model, a dict, a list, or a mix."""
    if hasattr(obj, "model_dump"):
        obj = obj.model_dump()
    if isinstance(obj, str):
        return [obj]
    if isinstance(obj, dict):
        return [s for v in obj.values() for s in strings(v)]
    if isinstance(obj, (list, tuple)):
        return [s for v in obj for s in strings(v)]
    return []


def require(obj, what: str) -> None:
    """Raise Unsafe if anything in `obj` is blocked; `what` names it in the log."""
    if bad := check(strings(obj)):
        log.warning("content check: %r in %s; kept off air", bad, what)
        raise Unsafe(f"{what} failed the content check ({bad!r})")
