"""The kill switch: take the station off air to the test card, and put it back.

A one-word file, data/control.txt (NEWSROOM_CONTROL overrides it): "testcard" holds the station on
the test card, anything else (or no file) is on air. The player looks at it twice a second. On
"testcard" it cuts whatever is playing at once, never to resume it, clears the ticker, and shows
the card with the music bed until the file says "air" again; the producer and the writers carry on
behind it, so the station comes back with the next slot.

    python -m newsroom.control testcard     # off air now
    python -m newsroom.control air          # back on
    python -m newsroom.control              # which it is

Anything that can write the file works from afar (a remote session, a synced folder); F12 in the
station's window toggles it too.
"""
from __future__ import annotations

import sys
import time
from pathlib import Path

from .config import CONFIG

HOLD = "testcard"
AIR = "air"
LOOK_EVERY_S = 0.5

_last = {"at": -1e9, "held": False}


def path() -> Path:
    return CONFIG.paths.control


def _read() -> bool:
    try:
        words = path().read_text(encoding="utf-8").split()
    except OSError:
        return False
    return bool(words) and words[0].lower() == HOLD


def held(now: float | None = None) -> bool:
    """Is the station held on the test card? Reads the file at most every LOOK_EVERY_S."""
    now = time.monotonic() if now is None else now
    if now - _last["at"] >= LOOK_EVERY_S:
        _last["at"], _last["held"] = now, _read()
    return _last["held"]


def set_state(state: str) -> None:
    if state not in (HOLD, AIR):
        raise ValueError(f"{state!r}: say {HOLD!r} or {AIR!r}")
    p = path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(state + "\n", encoding="utf-8")
    _last["at"], _last["held"] = time.monotonic(), state == HOLD


def toggle() -> str:
    state = AIR if _read() else HOLD
    set_state(state)
    return state


def main(argv: list[str]) -> int:
    if argv:
        set_state(argv[0].lower())
    print(f"{HOLD if _read() else AIR} ({path()})")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
