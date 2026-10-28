"""A canned script written while the model was unreachable is neither replayed from the cache
nor repeated overnight: on 2026-10-28 one from a six-minute outage aired seven times. With
NEWSROOM_LLM=off the template is the content, and caches as before.
"""
from __future__ import annotations

import dataclasses

import pytest

from newsroom import llm, workers, writers
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
