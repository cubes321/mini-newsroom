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
    monkeypatch.setattr(prune, "_scanned", -prune.SCAN_EVERY_S)
    return tmp_path


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


def test_on_the_station_it_scans_once_a_day_and_clears_a_batch_a_tick(cache, monkeypatch):
    w = _town(cache)
    for i in range(5):
        _entry(cache, f"{i:x}" * 8 + "a" * 8, 30)
    monkeypatch.setattr(prune, "BATCH", 4)
    assert prune.due(now=0.0)
    assert prune.tick(w, now=0.0) == 4 and prune.due(now=1.0)   # more to do: due again at the next idle tick
    assert prune.tick(w, now=1.0) == 2 and not prune.due(now=2.0)
    assert OLD not in _keys(cache) and {IN_ARCHIVE, DOC, NEW, AIRED} <= set(_keys(cache))
    _entry(cache, "b" * 16, 30)
    assert not prune.due(now=3600.0)                            # not until tomorrow's scan
    assert prune.due(now=prune.SCAN_EVERY_S + 1.0) and prune.tick(w, now=prune.SCAN_EVERY_S + 1.0) == 1


def test_it_is_off_until_keep_days_is_set(cache, monkeypatch):
    assert CONFIG.cache.keep_days == 0                          # config.toml as it ships: nothing is deleted
    monkeypatch.setattr(prune, "CONFIG", dataclasses.replace(prune.CONFIG, cache=dataclasses.replace(CONFIG.cache, keep_days=0)))
    assert not prune.due(now=0.0)
