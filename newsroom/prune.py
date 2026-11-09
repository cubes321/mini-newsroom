"""Clearing out the segment cache: scripts and their audio that nothing will ask for again.

Every written segment leaves its script and a WAV a line in data/cache, for a restart to pick up, for
the overnight repeats (the day's pieces) and for a documentary's archive clips (pieces still in the
town's archive, the last thousand). Nothing ever took them away: by 2026-11-09 the cache was 20 GB in
51,000 files, most of it older than anything the station can reach.

An entry is a key's files together (`<key>.json`, `<key>_00.wav`, `<key>_clip0.wav`, `<key>.aired`).
One goes when its newest file is older than `keep_days` and the town doesn't refer to it: not in the
archive, not a documentary the world still lists. Files that aren't an entry's (the idents, the
silences) are left alone.

    python -m newsroom.prune                # what would go at [cache] keep_days (or 14), and how much
    python -m newsroom.prune --days 7       # the same, for another age
    python -m newsroom.prune --days 7 --delete

On the station it is off unless `[cache] keep_days` is set: then the worker scans once a day in idle
time and deletes a batch of entries per idle tick, so it never holds a live slot up.
"""
from __future__ import annotations

import argparse
import logging
import os
import re
import time
from pathlib import Path

from .config import CONFIG

log = logging.getLogger(__name__)

KEY = re.compile(r"[0-9a-f]{16}(?=[_.])")
MIN_DAYS = 3.0                  # never less: the overnight repeats and a finished special's wait (workers.py)
SCAN_EVERY_S = 86400.0
BATCH = 150                     # entries deleted per idle tick: a second or so of disk

_todo: list[list[Path]] = []
_scanned = -SCAN_EVERY_S


def referred(world) -> set[str]:
    """The entries the town still refers to: the archive's pieces (a documentary quotes their audio) and
    the documentaries the world lists (the last one repeats overnight)."""
    if world is None:
        return set()
    with world.lock:
        keys = {e.get("hash") for e in world.archive} | {d.get("hash") for d in world.documentaries}
        keys.add(world.last_documentary_hash)
    return {k for k in keys if k}


def plan(keep_days: float, world=None, now: float | None = None, folder: Path | None = None) -> list[tuple[str, list[Path], int]]:
    """(key, its files, their bytes) for every entry that may go, the oldest first."""
    folder = folder or CONFIG.paths.cache
    cutoff = (time.time() if now is None else now) - max(keep_days, MIN_DAYS) * 86400
    entries: dict[str, list] = {}
    if not folder.exists():
        return []
    with os.scandir(folder) as it:
        for e in it:
            m = KEY.match(e.name)
            if not m or not e.is_file():
                continue
            st = e.stat()
            ent = entries.setdefault(m.group(0), [0.0, [], 0])
            ent[0] = max(ent[0], st.st_mtime)
            ent[1].append(Path(e.path))
            ent[2] += st.st_size
    keep = referred(world)
    old = [(newest, key, files, size) for key, (newest, files, size) in entries.items()
           if newest < cutoff and key not in keep]
    return [(key, files, size) for _, key, files, size in sorted(old, key=lambda o: o[:2])]


def delete(files: list[Path]) -> int:
    """Delete one entry's files, the script first so nothing loads an entry with its audio half gone."""
    n = 0
    for f in sorted(files, key=lambda f: f.suffix != ".json"):
        try:
            f.unlink(missing_ok=True)
            n += 1
        except OSError as e:
            log.warning("cache: could not delete %s: %s", f.name, e)
    return n


# ------------------------------------------------------------- on the station, in idle time


def due(now: float | None = None) -> bool:
    now = time.monotonic() if now is None else now
    return CONFIG.cache.keep_days > 0 and (bool(_todo) or now - _scanned >= SCAN_EVERY_S)


def tick(world, now: float | None = None) -> int:
    """One idle tick's worth: scan if the day's scan is due, then delete a batch. Returns entries deleted."""
    global _todo, _scanned
    now = time.monotonic() if now is None else now
    if not _todo and now - _scanned >= SCAN_EVERY_S:
        _scanned = now
        found = plan(CONFIG.cache.keep_days, world)
        _todo = [files for _, files, _ in found]
        if found:
            log.info("cache: %d entries older than %g days and out of the archive (%.1f GB) to clear",
                     len(found), max(CONFIG.cache.keep_days, MIN_DAYS), sum(s for *_, s in found) / 1e9)
    batch, _todo = _todo[:BATCH], _todo[BATCH:]
    for files in batch:
        delete(files)
    if batch and not _todo:
        log.info("cache: cleared")
    return len(batch)


def main(argv: list[str] | None = None) -> int:
    from . import world as world_mod

    ap = argparse.ArgumentParser(prog="python -m newsroom.prune", description=__doc__.splitlines()[0])
    ap.add_argument("--days", type=float, default=CONFIG.cache.keep_days or 14.0,
                    help="clear entries older than this (never less than %g)" % MIN_DAYS)
    ap.add_argument("--delete", action="store_true", help="delete them; without it, only say what would go")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    found = plan(a.days, world_mod.load())
    files, size = sum(len(f) for _, f, _ in found), sum(s for *_, s in found)
    days = max(a.days, MIN_DAYS)
    if not found:
        print(f"nothing in {CONFIG.paths.cache} is older than {days:g} days and out of the archive")
        return 0
    print(f"{len(found)} entries ({files} files, {size / 1e9:.2f} GB) in {CONFIG.paths.cache} are older than "
          f"{days:g} days and out of the archive")
    if not a.delete:
        print("nothing deleted: add --delete to clear them")
        return 0
    gone = sum(delete(f) for _, f, _ in found)
    print(f"deleted {gone} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
