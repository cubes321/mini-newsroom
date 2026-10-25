"""The viewer tip-line: a text file anyone can add a line to.

    python -m newsroom.tipline "Lifeboat called out to a yacht off the point"
    python -m newsroom.tipline "BREAKING: Smoke over the old cannery"
    python -m newsroom.tipline --list

The worker thread polls the file before each job (`poll()` only re-reads it
when its size or modification time changes) and takes new complete lines from
a saved byte offset, so a half-written line waits and a restart doesn't re-read
old tips. breaking.py decides what each line becomes. Plain tips wait in a
pending list until a bulletin uses one or they expire.

State is data/tipline.state.json: {offset, pending: [{text, ts}], last_breaking_ts}.
Only the worker thread touches it; the CLI only appends to the text file.
"""
from __future__ import annotations

import json
import logging
import time
from pathlib import Path

from .config import CONFIG

log = logging.getLogger(__name__)

_state: dict | None = None
_seen: tuple[int, float] | None = None       # (size, mtime) at the last read


def _state_path() -> Path:
    return CONFIG.paths.tipline.with_suffix(".state.json")


def _load() -> dict:
    global _state
    if _state is None:
        try:
            _state = json.loads(_state_path().read_text(encoding="utf-8"))
        except (OSError, ValueError):
            _state = {}
        _state.setdefault("offset", 0)
        _state.setdefault("pending", [])
        _state.setdefault("last_breaking_ts", 0.0)
    return _state


def _save() -> None:
    p = _state_path()
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(_load(), indent=1), encoding="utf-8")
    tmp.replace(p)


def poll() -> tuple[list[str], float]:
    """New complete lines since the last call, and how old the file was when read (seconds)."""
    global _seen
    path = CONFIG.paths.tipline
    try:
        st = path.stat()
    except OSError:
        return [], 0.0
    if _seen == (st.st_size, st.st_mtime):
        return [], 0.0
    _seen = (st.st_size, st.st_mtime)
    state = _load()
    if state["offset"] > st.st_size:              # the file was emptied or replaced
        state["offset"] = 0
    with path.open("rb") as f:
        f.seek(state["offset"])
        chunk = f.read()
    end = chunk.rfind(b"\n") + 1                  # stop at the last complete line
    if not end:
        return [], 0.0
    state["offset"] += end
    _save()
    lines = [ln.strip() for ln in chunk[:end].decode("utf-8", errors="replace").splitlines()]
    return [ln for ln in lines if ln and not ln.startswith("#")], time.time() - st.st_mtime


def add_tip(text: str) -> None:
    _load()["pending"].append({"text": text, "ts": time.time()})
    _save()
    log.info("tip-line: tip for the next bulletin: %r", text[:80])


def offer(n: int | None = None) -> list[str]:
    """The oldest pending tips that haven't expired, for a bulletin's briefing."""
    state = _load()
    cutoff = time.time() - CONFIG.breaking.tip_ttl_s
    fresh = [t for t in state["pending"] if t["ts"] >= cutoff]
    if len(fresh) != len(state["pending"]):
        state["pending"] = fresh
        _save()
    return [t["text"] for t in fresh[: n or CONFIG.breaking.max_tips]]


def consume(text: str) -> None:
    state = _load()
    state["pending"] = [t for t in state["pending"] if t["text"] != text]
    _save()
    log.info("tip-line: tip used: %r", text[:80])


def last_breaking_ts() -> float:
    return float(_load()["last_breaking_ts"])


def set_last_breaking(ts: float) -> None:
    _load()["last_breaking_ts"] = ts
    _save()


def _cli(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m newsroom.tipline")
    ap.add_argument("tip", nargs="?", help='the tip; start it with "BREAKING:" to interrupt the programme')
    ap.add_argument("--list", action="store_true", help="show the pending tips and the file position")
    a = ap.parse_args(argv)
    if a.tip:
        path = CONFIG.paths.tipline
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(a.tip.replace("\n", " ").strip() + "\n")
        print(f"added to {path}")
    if a.list:
        state = _load()
        print(f"offset {state['offset']}, last breaking {time.ctime(state['last_breaking_ts']) if state['last_breaking_ts'] else 'never'}")
        for t in state["pending"]:
            print(f"  {time.strftime('%H:%M', time.localtime(t['ts']))}  {t['text']}")
    if not a.tip and not a.list:
        ap.print_help()
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
