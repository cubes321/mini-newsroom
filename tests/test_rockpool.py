"""Rock Pool: Poppy Tregenza and Gully, the herring-gull puppet on her arm, at 16:00. Gully's voice is a
puppet's (Fable raised a third), drawn in code with a beak that opens. The model is stubbed: no network."""
from __future__ import annotations

import time
from pathlib import Path

import numpy as np
import pygame

from newsroom import schedule, tts, world as world_mod, writers
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentType as T
from newsroom.player import Player, View


def test_poppy_and_gully_are_cast_and_nobody_loses_a_voice():
    w = world_mod.seed()
    poppy, gully = w.character("kids"), w.character("gully")
    assert poppy.name == "Poppy Tregenza" and poppy.voice == "af_bella" and "af_bella" not in world_mod.GUEST_VOICES
    assert gully.voice == "bm_fable@puppet" and "bm_fable" in world_mod.GUEST_VOICES   # Fable stays a guest's too
    fable = [p for p in w.people if p.voice == "bm_fable"]
    world_mod._recast_presenter_voices(w)
    assert fable and all(p.voice == "bm_fable" for p in fable)                         # not recast for the puppet


def test_a_puppet_voice_is_spoken_slower_and_raised_a_third(monkeypatch, tmp_path):
    sr, seen = tts.CONFIG.tts.sample_rate, {}

    class Result:
        audio = np.sin(2 * np.pi * 200 * np.arange(sr) / sr).astype(np.float32)    # a second at 200 Hz

    def pipe(text, voice, speed):
        seen.update(voice=voice, speed=speed)
        return [Result()]
    monkeypatch.setattr(tts, "_pipeline", lambda lang: pipe)
    res = tts.synthesize("Snacks are mine.", "bm_fable@puppet", Path(tmp_path) / "g.wav")
    assert seen["voice"] == "bm_fable" and abs(seen["speed"] - 1 / tts.PUPPET) < 1e-6
    assert abs(res.duration_s - 1 / tts.PUPPET) < 0.01
    a, _ = tts.sf.read(res.wav_path, dtype="float32")
    peak = np.argmax(np.abs(np.fft.rfft(a))) * sr / len(a)
    assert abs(peak - 200 * tts.PUPPET) < 5


def test_it_airs_from_four_to_quarter_to_five_with_no_breaks():
    lt = time.localtime()
    at = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 16, 20, 0, 0, 0, -1))
    show = schedule.show_at(at)
    assert show.id == "rockpool" and time.localtime(schedule.show_end(at))[3:5] == (16, 45)
    assert T.ad_break not in {schedule.as_item(e).type for e in show.pattern}


def _seated(lines):
    pl = Player(Buffer(), world_mod.seed(), producer=None, audio=False)
    return pl._people(Segment(slot_id=1, type=T.links, show="rockpool", lines=lines))


def test_gully_is_always_on_poppys_arm_and_hugh_or_a_visitor_takes_the_third_seat():
    assert _seated([Line(speaker="kids", text="Hello!")]) == [("kids", None), ("gully", None)]
    assert _seated([Line(speaker="kids", text="Story time."), Line(speaker="historian", text="Once...")]) == [
        ("kids", None), ("gully", None), ("historian", None)]
    assert _seated([Line(speaker="gully", text="Cat!"), Line(speaker="guest", text="Purr.", guest_name="Jo Bray")]) == [
        ("kids", None), ("gully", None), ("guest", "Jo Bray")]


def test_the_childrens_ticker_carries_no_news():
    pl = Player(Buffer(), world_mod.seed(), producer=None, audio=False)
    pl.ticker.extend([("news", "Harbour wall report due Friday"), ("rockpool", "Make a paper plate owl")])
    pl.current, pl.line_idx = Segment(slot_id=1, type=T.links, show="rockpool",
                                      lines=[Line(speaker="kids", text="Hello!", duration_s=1.0)]), 0
    pl.seg_start = pl.line_start = schedule.now()
    assert pl.view().ticker == ["Make a paper plate owl"]
    pl.current = Segment(slot_id=2, type=T.bulletin, show="news", lines=[Line(speaker="anchor", text="Good evening.")])
    assert pl.view().ticker == ["Harbour wall report due Friday", "Make a paper plate owl"]


def test_gully_is_drawn_with_a_beak_that_opens():
    from newsroom import locations, scenes

    pygame.font.init()
    people = [("kids", None), ("gully", None), ("historian", None)]
    marks = [m for _, _, m in scenes._interview_marks(View(show="rockpool", set="interview", people=people))]
    assert marks == [locations.MARKS["studio_kids"][k] for k in ("host", "gully", "guest")]
    frames = []
    for mouth in (0.0, 1.0):
        c = pygame.Surface(scenes.CANVAS)
        scenes.render(c, View(mode="studio", show="rockpool", set="interview", people=people, speaker="gully",
                              mouth=mouth), 0.05)
        frames.append(pygame.surfarray.array3d(c))
    x, y = locations.MARKS["studio_kids"]["gully"][:2]
    diff = np.argwhere((frames[0] != frames[1]).any(axis=2))
    assert len(diff) and (diff[:, 0] < x).all() and (diff[:, 1] < y).all()      # only his beak moved, by Poppy


def test_rock_pool_is_kept_from_the_news_and_from_grown_up_guests(monkeypatch):
    w = world_mod.seed()
    t = w.thread(w.update_thread(None, "Harbour wall report due Friday", "so far"))
    t.phase, t.mentions = "peak", 9                                    # a big running story elsewhere
    system, user = writers.build_prompt(T.links, w, target_s=90, show=schedule.get("rockpool"), brief="THE MAKE")
    assert "BIG RUNNING STORY" not in user and "NOTHING frightening" in system and "Poppy Tregenza" in user
    p = w.ensure_person("Helen Strand", "Mayor")
    p.loose_ends = [{"ts": schedule.now() - 3 * 24 * 3600, "date": w.last_date, "show": "Coastwide", "ask": "the wall"}]
    monkeypatch.setattr(writers.llm, "complete_json",
                        lambda *a, **k: (_ for _ in ()).throw(writers.llm.LLMError("stub")))
    seg = Segment(slot_id=4, type=T.interview, show="rockpool", target_s=180)
    writers.script_segment(seg, w)
    assert "return_guest" not in seg.work
    for part in ("", "close"):                    # the canned pieces are Poppy and Gully's, never Coastwide's
        seg = Segment(slot_id=5, type=T.links, show="rockpool", target_s=90, part=part)
        writers.script_segment(seg, w)
        assert {l.speaker for l in seg.lines} == {"kids", "gully"} and "Coastwide" not in seg.headline


def test_a_long_make_fits():
    from newsroom.models import script_schema

    schema = script_schema(T.links, schedule.get("rockpool").cast_for(T.links), chatter=True)
    lines = [{"speaker": ("kids", "gully")[k % 2], "text": "Fold it."} for k in range(18)]
    assert len(schema.model_validate({"headline": "A paper plate owl", "lower_third": "Rock Pool",
                                      "lines": lines}).lines) == 18
    visitor = script_schema(T.interview, schedule.get("rockpool").cast_for(T.interview), chatter=True)
    lines = [{"speaker": ("kids", "gully", "guest")[k % 3], "text": "Purr."} for k in range(18)]
    assert len(visitor.model_validate({"headline": "Biscuit the cat visits", "lower_third": "Rock Pool",
                                       "guest_name": "Tam Buchanan", "lines": lines}).lines) == 18
