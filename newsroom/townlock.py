"""One station to a town: a lock file beside the world, held for as long as the station runs (TODO, 2026-11-26).

`world.save()` writes the whole town from one process's memory, so two stations on one world.json overwrite
each other's threads, people and bookings, without a word. A station now claims `<world>.lock` before it
touches anything (the backup, the load, OBS, the window); a second station on the same file waits a moment
(the first may be making its exit save) and then refuses to start, naming the holder. A scratch or copied
world is another file with its own lock, so a test run beside a night is unaffected.

The lock is the operating system's (msvcrt on Windows, flock elsewhere), not a pid in a file: it goes with
the process however that ends, a crash or a kill included, so there is never a stale one to clear by hand.
Windows locks are mandatory, so the byte locked lies past the note of who holds it (pid, channel, start),
which a refused station reads for its message.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from pathlib import Path

log = logging.getLogger("newsroom.townlock")

FAR = 1 << 20                     # the byte locked: past the note, which stays readable on Windows
WAIT_S = 90.0                     # a restart's new station waits this long for the old one's exit save
POLL_S = 2.0

_HELD: dict[Path, int] = {}       # lock path -> the fd holding it, for the life of the process


class TownTaken(RuntimeError):
    """Another station holds this town."""


def path_for(world: Path) -> Path:
    return world.with_name(world.name + ".lock")


def _try(fd: int) -> bool:
    os.lseek(fd, FAR, os.SEEK_SET)
    try:
        if sys.platform == "win32":
            import msvcrt

            msvcrt.locking(fd, msvcrt.LK_NBLCK, 1)      # not LK_LOCK, which retries for ten seconds itself
        else:
            import fcntl

            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        return False
    return True


def holder(world: Path) -> str:
    """The holder's note, as it wrote it ("" if there is none or it can't be read)."""
    try:
        return path_for(Path(world).resolve()).read_text(encoding="utf-8").strip()
    except OSError:
        return ""


def claim(world: Path, who: str, wait_s: float | None = None) -> Path:
    """Hold `world`'s lock until this process ends, or raise TownTaken. Claiming a town this process
    already holds is a no-op (Windows locks are per handle: a second claim would refuse its own)."""
    lock = path_for(Path(world).resolve())
    if lock in _HELD:
        return lock
    wait_s = WAIT_S if wait_s is None else wait_s
    lock.parent.mkdir(parents=True, exist_ok=True)
    # Opened without truncating: a station that is about to be refused mustn't wipe the holder's note.
    fd = os.open(lock, os.O_RDWR | os.O_CREAT | getattr(os, "O_BINARY", 0), 0o644)
    deadline = time.monotonic() + wait_s
    waited = False
    while not _try(fd):
        if time.monotonic() >= deadline:
            os.close(fd)
            raise TownTaken(
                f"{world} is already on air: {holder(world) or 'another station'} holds {lock.name}. Two stations "
                f"on one town overwrite each other's saves. Stop that one first, or run this one with --scratch "
                f"or --world <a copy>.")
        if not waited:
            log.warning("%s is held by %s; waiting up to %.0f s for it (a station closing makes its last save)",
                        lock.name, holder(world) or "another station", wait_s)
            waited = True
        time.sleep(POLL_S)
    note = f"{who}, pid {os.getpid()}, since {time.strftime('%Y-%m-%d %H:%M')}\n".encode()
    os.lseek(fd, 0, os.SEEK_SET)
    os.ftruncate(fd, 0)
    os.write(fd, note)
    os.fsync(fd)
    _HELD[lock] = fd                  # never closed: the lock lasts until the process ends, past the exit save
    log.info("town claimed: %s (%s)", lock, who)
    return lock


def release(world: Path) -> None:
    """Let go of `world`'s lock early (the tests; a station never does, the process's end does it)."""
    fd = _HELD.pop(path_for(Path(world).resolve()), None)
    if fd is None:
        return
    if sys.platform == "win32":       # unlocked first: Windows frees a closed handle's locks only in due course
        import msvcrt

        os.lseek(fd, FAR, os.SEEK_SET)
        msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
    os.close(fd)
