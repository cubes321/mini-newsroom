"""The town's backups (world.backup): the file as it stood at each day's first save, and as a run began.

A temp folder: no station.
"""
import dataclasses
import json
import os
import time

import pytest

from newsroom import world as world_mod
from newsroom.config import CONFIG


@pytest.fixture
def town(tmp_path, monkeypatch):
    path = tmp_path / "world.json"
    monkeypatch.setattr(world_mod, "_backed_up", {})
    w = world_mod.seed()
    world_mod.save(w, path)                                # the first save ever: nothing to back up yet
    assert world_mod.backups(path) == []
    monkeypatch.setattr(world_mod, "_backed_up", {})       # as on the next day
    return w, path


def _days(monkeypatch, n):
    monkeypatch.setattr(world_mod, "CONFIG", dataclasses.replace(
        CONFIG, backups=dataclasses.replace(CONFIG.backups, keep=n)))


def test_the_days_first_save_keeps_the_town_as_it_stood(town):
    w, path = town
    before = path.read_text(encoding="utf-8")
    w.headlines.append("Harbour wall report due Friday")
    world_mod.save(w, path)
    (copy,) = world_mod.backups(path)
    assert copy.parent.name == "backups" and copy.read_text(encoding="utf-8") == before
    assert "Harbour wall report" in path.read_text(encoding="utf-8")
    w.headlines.append("Ferry back on")
    world_mod.save(w, path)                                # later the same day: no second copy
    assert world_mod.backups(path) == [copy] and copy.read_text(encoding="utf-8") == before


def test_old_days_go_and_the_last_three_starts_stay(town, monkeypatch):
    w, path = town
    _days(monkeypatch, 3)
    folder = world_mod.backup_dir(path)
    folder.mkdir()
    for i, name in enumerate(["world-2026-11-01.json", "world-2026-11-02.json", "world-2026-11-03.json",
                              "world-2026-11-04.json", "world-2026-11-01-0900-start.json",
                              "world-2026-11-02-0900-start.json", "world-2026-11-03-0900-start.json"]):
        (folder / name).write_text("{}")
        os.utime(folder / name, (time.time() - 1000 + i, time.time() - 1000 + i))
    made = world_mod.backup(path, start=True)
    assert made is not None and made.name.endswith("-start.json")
    world_mod.save(w, path)
    names = sorted(f.name for f in folder.iterdir())
    days = [n for n in names if "start" not in n]
    assert len(days) == 3 and "world-2026-11-01.json" not in days and "world-2026-11-02.json" not in days
    assert len([n for n in names if "start" in n]) == 3 and "world-2026-11-01-0900-start.json" not in names


def test_keep_nought_switches_them_off(town, monkeypatch):
    w, path = town
    _days(monkeypatch, 0)
    world_mod.save(w, path)
    assert world_mod.backup(path, start=True) is None and world_mod.backups(path) == []


def test_a_town_that_cant_be_read_says_where_the_last_good_one_is(town, monkeypatch):
    w, path = town
    world_mod.save(w, path)                                # leaves a backup
    path.write_text(path.read_text(encoding="utf-8")[:500], encoding="utf-8")       # cut short, as a crash mid-write would
    monkeypatch.setattr(world_mod, "_WORLD", None)
    with pytest.raises(RuntimeError, match="newest backup is .*backups"):
        world_mod.load(path)
    good = json.loads(world_mod.backups(path)[-1].read_text(encoding="utf-8"))
    assert good["town"] == w.town
