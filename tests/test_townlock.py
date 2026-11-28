"""One station to a town (townlock.py): a second station on the same world refuses to start, naming the
holder; a killed holder leaves no stale lock; another world is unaffected. The holders here are real
processes, each handed its own temp world: no station runs and the real town is never named."""
from __future__ import annotations

import logging
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from newsroom import townlock

REPO = Path(__file__).resolve().parent.parent
HOLD = ("import sys, time; sys.path.insert(0, sys.argv[1]); from newsroom import townlock; "
        "townlock.claim(sys.argv[2], 'Channel 7', wait_s=0); print('held', flush=True); time.sleep(120)")


def _holder(world: Path) -> subprocess.Popen:
    p = subprocess.Popen([sys.executable, "-c", HOLD, str(REPO), str(world)], stdout=subprocess.PIPE, text=True)
    assert p.stdout.readline().strip() == "held"
    return p


# Windows lets a killed process's lock go "in due course" (townlock.release), not the moment the process is reaped:
# on a busy machine a claim straight after the kill found it still held, and these tests failed one run in three or
# so (2026-11-28, the full suite taking four minutes). A station waits WAIT_S for this; the tests wait up to FREED_S.
FREED_S = 10.0


def _claim_after_kill(world: Path, who: str, monkeypatch) -> Path:
    monkeypatch.setattr(townlock, "POLL_S", 0.05)
    return townlock.claim(world, who, wait_s=FREED_S)


def test_a_second_station_is_refused_and_a_killed_one_leaves_no_lock(tmp_path, monkeypatch):
    world = tmp_path / "world.json"
    p = _holder(world)
    try:
        with pytest.raises(townlock.TownTaken, match=r"Channel 7, pid \d+, since .*--scratch"):
            townlock.claim(world, "Channel 8", wait_s=0)
        assert townlock.claim(tmp_path / "copy.json", "Channel 8", wait_s=0)    # another file: its own lock
    finally:
        p.kill()                                     # not a clean exit: the lock must go with the process
        p.wait()
    try:
        _claim_after_kill(world, "Channel 8", monkeypatch)
        assert townlock.holder(world).startswith("Channel 8, pid ")
        assert townlock.claim(world, "Channel 8", wait_s=0)                    # its own town again: no-op
    finally:
        townlock.release(world)
        townlock.release(tmp_path / "copy.json")


def test_a_save_beside_a_station_is_refused(tmp_path, monkeypatch):
    from newsroom import world as world_mod

    path = tmp_path / "world.json"
    p = _holder(path)
    try:
        with pytest.raises(townlock.TownTaken, match="Channel 7"):     # a module's CLI saving the town on air
            world_mod.save(world_mod.seed(), path)
        assert not path.exists()
    finally:
        p.kill()
        p.wait()
    _claim_after_kill(path, "a save from pytest", monkeypatch)       # then the save's own claim is a no-op
    world_mod.save(world_mod.seed(), path)
    assert path.exists()
    townlock.release(path)


def test_a_station_closing_is_waited_for(tmp_path, monkeypatch):
    world = tmp_path / "world.json"
    p = _holder(world)
    monkeypatch.setattr(townlock, "POLL_S", 0.1)
    threading.Timer(0.5, p.kill).start()             # the old station's exit save finishing
    try:
        townlock.claim(world, "Channel 7", wait_s=30)
    finally:
        p.wait()
        townlock.release(world)


def test_the_station_refuses_before_it_touches_anything(tmp_path, monkeypatch):
    from newsroom import __main__ as station
    from newsroom.config import CONFIG

    world = CONFIG.paths.world                       # the tests' own temp town (conftest)
    before = world.stat().st_mtime_ns if world.exists() else None
    townlock.release(world)                          # this process's own saves of it claimed it earlier
    p = _holder(world)
    monkeypatch.setenv("NEWSROOM_LOGS", str(tmp_path / "logs"))
    monkeypatch.setattr(townlock, "WAIT_S", 0)
    monkeypatch.setattr(station, "run_headless", lambda *a: pytest.fail("the station started"))
    hooks, root = (sys.excepthook, threading.excepthook), logging.getLogger()
    handlers = list(root.handlers)
    try:
        assert station.main(["--no-window"]) == 3
        assert (world.stat().st_mtime_ns if world.exists() else None) == before   # not seeded, rolled or saved
    finally:
        p.kill()
        p.wait()
        sys.excepthook, threading.excepthook = hooks
        logging.captureWarnings(False)
        for h in root.handlers[:]:
            if h not in handlers:
                root.removeHandler(h)
                h.close()
