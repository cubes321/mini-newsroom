"""Clearing the segment cache (prune.py): an entry goes when it is old and the town no longer refers to it.

A temp folder and hand-made files: no station, no model.
"""
import dataclasses
import os
import time

import pytest

from newsroom import prune, world as world_mod
from newsroom.config import CONFIG


@pytest.fixture
def cache(tmp_path, monkeypatch):
    monkeypatch.setattr(prune, "CONFIG", dataclasses.replace(
        CONFIG, paths=dataclasses.replace(CONFIG.paths, cache=tmp_path),
        cache=dataclasses.replace(CONFIG.cache, keep_days=7.0)))
    monkeypatch.setattr(prune, "_todo", [])
    return tmp_path


def _every(monkeypatch, days, keep=7.0):
    monkeypatch.setattr(prune, "CONFIG", dataclasses.replace(
        prune.CONFIG, cache=dataclasses.replace(prune.CONFIG.cache, keep_days=keep, every_days=days)))


def _entry(folder, key, days_old, *names):
    at = time.time() - days_old * 86400
    for name in names or (".json", "_00.wav", "_01.wav"):
        f = folder / f"{key}{name}"
        f.write_bytes(b"x" * 100)
        os.utime(f, (at, at))


def _keys(folder):
    return sorted({f.name[:16] for f in folder.iterdir()})


OLD, IN_ARCHIVE, DOC, NEW, AIRED = "0" * 16, "1" * 16, "2" * 16, "3" * 16, "4" * 16


def _town(cache):
    w = world_mod.seed()
    w.archive.append({"date": "2026-10-20", "hash": IN_ARCHIVE, "type": "bulletin", "headline": "h", "text": "t"})
    w.documentaries.append({"title": "The harbour wall", "hash": DOC})
    _entry(cache, OLD, 20)
    _entry(cache, IN_ARCHIVE, 20)                               # a documentary may still quote its audio
    _entry(cache, DOC, 20, ".json", "_00.wav", "_clip0.wav", ".aired")
    _entry(cache, NEW, 2)
    _entry(cache, AIRED, 20, ".json", "_00.wav")
    _entry(cache, AIRED, 1, ".aired")                           # its newest file counts: marked yesterday
    for name in ("_silence_2.0s.wav", "_ident_news.wav", "tts_test.wav"):
        (cache / name).write_bytes(b"x")
        os.utime(cache / name, (0, 0))                          # not an entry's: never touched, however old
    return w


def test_only_what_is_old_and_out_of_the_archive_goes(cache):
    w = _town(cache)
    found = prune.plan(7, w)
    assert [(key, len(files), size) for key, files, size in found] == [(OLD, 3, 300)]
    assert prune.plan(7, None)[0][0] in (OLD, IN_ARCHIVE, DOC) and len(prune.plan(7, None)) == 3   # no town: age alone
    assert prune.plan(0.5, w) == found                          # never less than three days, whatever is asked
    for _, files, _ in found:
        prune.delete(files)
    left = {f.name for f in cache.iterdir()}
    assert not any(n.startswith(OLD) for n in left) and {"_ident_news.wav", "_silence_2.0s.wav", "tts_test.wav"} < left
    assert {n[:16] for n in left if n[0] in "01234"} == {IN_ARCHIVE, DOC, NEW, AIRED}


DAY = 86400.0


def test_on_the_station_it_clears_a_batch_a_tick_and_then_not_again_that_day(cache, monkeypatch):
    w = _town(cache)
    for i in range(5):
        _entry(cache, f"{i:x}" * 8 + "a" * 8, 30)
    monkeypatch.setattr(prune, "BATCH", 4)
    now = time.time()
    assert prune.last_run() == 0 and prune.due(now)             # never run: due at the first idle moment
    assert prune.tick(w, now) == 4 and prune.due(now + 1)       # more to do: due again at the next idle tick
    assert prune.last_run() == 0                                # and not marked done until it is
    assert prune.tick(w, now + 1) == 2 and not prune.due(now + 2)
    assert OLD not in _keys(cache) and {IN_ARCHIVE, DOC, NEW, AIRED} <= set(_keys(cache))
    assert (cache / prune.STAMP).exists() and abs(prune.last_run() - (now + 1)) < 1
    _entry(cache, "b" * 16, 30)
    assert not prune.due(now + 3600)                            # not until tomorrow
    assert prune.due(now + DAY + 2) and prune.tick(w, now + DAY + 2) == 1


def test_a_station_started_again_the_same_day_does_not_scan_again(cache, monkeypatch):
    """When it last ran is in the cache folder, not in the run's memory: five starts in a day are one scan."""
    w = _town(cache)
    now = time.time()
    assert prune.tick(w, now) == 1 and not prune.due(now + 60)
    monkeypatch.setattr(prune, "_todo", [])                     # a new run: nothing in memory
    scans = []
    monkeypatch.setattr(prune, "plan", lambda *a, **k: scans.append(1) or [])
    assert not prune.due(now + 3 * 3600) and prune.due(now + DAY + 60)
    assert prune.tick(w, now + DAY + 60) == 0 and scans == [1]  # nothing old: no idle tick spent, and done for the day
    assert not prune.due(now + DAY + 120)


def test_a_clear_out_stopped_part_way_starts_again_at_the_next_start(cache, monkeypatch):
    w = _town(cache)
    for i in range(5):
        _entry(cache, f"{i:x}" * 8 + "a" * 8, 30)
    monkeypatch.setattr(prune, "BATCH", 2)
    now = time.time()
    assert prune.tick(w, now) == 2
    monkeypatch.setattr(prune, "_todo", [])                     # the station stopped with four still to go
    assert prune.due(now + 60) and prune.tick(w, now + 60) == 2


def test_weekly_waits_a_week(cache, monkeypatch):
    w = _town(cache)
    _every(monkeypatch, 7)
    now = time.time()
    assert prune.due(now) and prune.tick(w, now) == 1
    assert not prune.due(now + 6 * DAY) and prune.due(now + 7 * DAY + 1)


def test_keep_days_nought_switches_it_off_and_the_station_says_which(cache, monkeypatch, caplog):
    import logging

    caplog.set_level(logging.INFO)
    assert CONFIG.cache.keep_days == 0 or CONFIG.cache.keep_days >= prune.MIN_DAYS     # config.toml as it ships
    prune.report()
    assert "older than 7 days and out of the archive are cleared every day in idle time (last: never)" in caplog.text
    _every(monkeypatch, 7, keep=0)
    assert not prune.due(time.time())
    prune.report()
    assert "nothing is cleared" in caplog.text


def test_the_worker_spends_no_idle_tick_when_nothing_is_old(cache, monkeypatch):
    """With the clear-out on by default, an idle tick that found nothing to delete must go on to the desk."""
    from newsroom import adverts, continuity, desk, workers
    from newsroom.buffer import Buffer

    w = world_mod.seed()
    pool = workers.WorkerPool(Buffer(), w)
    planned = []
    monkeypatch.setattr(adverts, "seed_one", lambda w: False)
    monkeypatch.setattr(continuity, "bake_one", lambda w: False)
    monkeypatch.setattr(pool, "_buffer_healthy", lambda: True)
    monkeypatch.setattr(desk, "should_plan", lambda w: True)
    monkeypatch.setattr(desk, "plan", lambda w, breaking="no": planned.append(1))
    monkeypatch.setattr(workers.world_mod, "save", lambda *a, **k: None)
    _entry(cache, NEW, 2)
    pool._idle_work()
    assert planned == [1] and prune.last_run() > 0              # the scan was done, and the desk still got its turn
    _entry(cache, OLD, 20)
    monkeypatch.setattr(prune, "last_run", lambda: 0.0)         # tomorrow
    pool._idle_work()
    assert planned == [1] and OLD not in _keys(cache)           # something to clear: that was this tick's work
