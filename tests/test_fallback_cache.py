"""A canned script written while the model was unreachable is neither replayed from the cache
nor repeated overnight: on 2026-10-28 one from a six-minute outage aired seven times. With
NEWSROOM_LLM=off the template is the content, and caches as before.
"""
from __future__ import annotations

import dataclasses
import os
import time
from datetime import datetime, timedelta

import pytest

from newsroom import llm, schedule, workers, writers
from newsroom import world as world_mod
from newsroom.config import CONFIG
from newsroom.models import Line, Segment, SegmentState, SegmentType


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    old = CONFIG.paths
    object.__setattr__(CONFIG, "paths", dataclasses.replace(old, cache=tmp_path, world=tmp_path / "world.json"))
    monkeypatch.setattr(world_mod, "save", lambda *a, **k: None)
    yield tmp_path
    object.__setattr__(CONFIG, "paths", old)


def _down(*a, **k):
    raise llm.LLMUnavailable("Connection error.")


def _script(monkeypatch, override: str | None) -> Segment:
    if override:
        monkeypatch.setenv("NEWSROOM_LLM", override)
    else:
        monkeypatch.delenv("NEWSROOM_LLM", raising=False)
    monkeypatch.setattr(llm, "complete_json", _down)
    seg = Segment(slot_id=7, type=SegmentType.bulletin, show="news")
    return writers.script_segment(seg, world_mod.seed())


def test_an_outage_template_is_marked_and_an_llm_off_one_is_not(monkeypatch):
    assert _script(monkeypatch, None).fallback
    assert not _script(monkeypatch, "off").fallback


def _cached(tmp_path, *, fallback: bool) -> str:
    wav = tmp_path / "x_00.wav"
    wav.write_bytes(b"")
    seg = Segment(slot_id=7, type=SegmentType.interview, show="news", state=SegmentState.ready, fallback=fallback,
                  headline="Dev Ramachandran on the week in town", lines=[Line(speaker="anchor", text="Hi.", wav_path=wav)])
    workers._save_cached(seg, "h7")
    return "h7"


def test_a_fallback_is_asked_for_again_and_never_repeated(tmp_cache):
    slot = Segment(slot_id=7, type=SegmentType.interview, show="news")
    assert workers._load_cached(slot, _cached(tmp_cache, fallback=True)) is None
    rep = workers.repeat_segment(Segment(slot_id=9, type=SegmentType.repeat, show="overnight"))
    assert rep.type is SegmentType.testcard                      # nothing else to repeat


def test_a_real_script_still_replays_and_repeats(tmp_cache):
    slot = Segment(slot_id=7, type=SegmentType.interview, show="news")
    assert workers._load_cached(slot, _cached(tmp_cache, fallback=False)) is not None
    rep = workers.repeat_segment(Segment(slot_id=9, type=SegmentType.repeat, show="overnight"))
    assert rep.repeat and rep.headline == "Dev Ramachandran on the week in town"


def test_the_overnight_repeats_come_from_the_day_that_began_at_six(tmp_cache, monkeypatch):
    """On 2026-11-06 a 48-hour window replayed the 4th's auction and its "harbour clears for Bonfire
    Night" at three in the morning, the day after the bonfire."""
    monkeypatch.setattr(schedule, "_offset_s", 0.0)
    schedule.set_clock("03:00")                                     # the 6th, say, at three in the morning
    now = schedule.now()
    shift = now - time.time()                    # the broadcast clock is ahead of the files' real clock by this
    day = datetime.fromtimestamp(now).date()
    since = datetime(day.year, day.month, day.day, 6) - timedelta(days=1)
    assert datetime.fromtimestamp(workers.repeat_since(now)) == since          # six in the morning on the 5th
    for key, headline, hours_ago in (("old", "Quay auction dips as harbour clears", 30), ("new", "Gorse fire out", 6)):
        wav = tmp_cache / f"{key}_00.wav"
        wav.write_bytes(b"")
        workers._save_cached(Segment(slot_id=1, type=SegmentType.bulletin, show="news", state=SegmentState.ready,
                                     headline=headline, lines=[Line(speaker="anchor", text="Hi.", wav_path=wav)]), key)
        t = now - shift - hours_ago * 3600
        os.utime(tmp_cache / f"{key}.json", (t, t))
    for _ in range(5):
        rep = workers.repeat_segment(Segment(slot_id=9, type=SegmentType.repeat, show="overnight"))
        assert rep.headline == "Gorse fire out"                    # last evening's, never the day before's


def test_a_script_that_has_aired_is_written_afresh_after_a_restart(tmp_cache):
    """Slot numbers start at 0 on every run and are in the cache key: a station restarted the same day
    read its earlier news again, word for word. What was made and never aired is still picked up; the
    overnight repeats still have the aired one."""
    from newsroom import adverts
    from newsroom.buffer import Buffer
    from newsroom.player import Player
    from newsroom.producer import Producer

    wav = tmp_cache / "x_00.wav"
    wav.write_bytes(b"")

    def made(slot, h):
        seg = Segment(slot_id=slot, type=SegmentType.bulletin, show="news", state=SegmentState.ready, content_hash=h,
                      headline=f"Story {slot}", lines=[Line(speaker="anchor", text="Hi.", wav_path=wav, duration_s=4.0)])
        workers._save_cached(seg, h)
        return seg

    buf = Buffer()
    pl = Player(buf, world_mod.seed(), Producer(buf, 600), audio=False, ads=adverts.AdPool(tmp_cache / "ads"))
    first, second, third = made(0, "h0"), made(1, "h1"), made(2, "h2")
    for seg in (first, second, third):
        buf.submit(seg)
        buf.mark(seg, SegmentState.ready)
    now = 1_000_000.0
    pl.update(now)
    pl.update(now + 5)                                   # the first has aired; the second is on
    assert pl.current is second
    pl.drop(now + 6, "a fault")                          # taken off part-way: not to be read out again either

    slot = lambda n: Segment(slot_id=n, type=SegmentType.bulletin, show="news")       # the next run's plan
    assert workers._load_cached(slot(0), "h0") is None and workers._load_cached(slot(1), "h1") is None
    assert workers._load_cached(slot(2), "h2") is not None                             # made, never aired
    heads = {workers.repeat_segment(Segment(slot_id=9, type=SegmentType.repeat, show="overnight")).headline
             for _ in range(30)}
    assert "Story 0" in heads                            # the repeats take no notice of the marker

    made(0, "h0")                                        # the restart writes slot 0 again under its old key
    assert workers._load_cached(slot(0), "h0") is not None                             # new, and not aired yet
