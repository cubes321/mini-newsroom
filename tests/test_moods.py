"""Moods: a script line says how it is said, and the face shows it (sprites.MOODS, chosen on a contact
sheet 2026-11-01). The model is stubbed and nothing is voiced."""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from newsroom import llm, scenes, sprites, world as world_mod, writers  # noqa: E402
from newsroom.buffer import Buffer  # noqa: E402
from newsroom.models import MOOD_NAMES, GuestLine, Line, Segment, SegmentType as T  # noqa: E402
from newsroom.player import Player  # noqa: E402
from newsroom.producer import Producer  # noqa: E402


def test_the_scripts_moods_are_the_faces_moods():
    assert sprites.MOODS == ("",) + MOOD_NAMES
    assert set(sprites.REACT) <= set(MOOD_NAMES) and set(sprites.REACT.values()) <= set(MOOD_NAMES)


def test_a_mood_in_the_models_own_words_is_mapped_or_dropped():
    def mood(m):
        return GuestLine.model_validate({"speaker": "guest", "text": "Well.", "mood": m}).mood
    assert mood("LAUGHING") == "laughing"
    assert mood("amused") == "happy" and mood("indignant") == "cross" and mood("sheepish") == "embarrassed"
    assert mood("neutral") is None and mood("") is None and mood(None) is None


def test_the_mood_goes_from_the_script_to_the_line_on_air(monkeypatch):
    w = world_mod.seed()

    def write(task, schema, system, user):
        assert "mood is drawn in the speaker's face" in system
        return schema.model_validate({
            "headline": "A gull rode the ferry", "lower_third": "The Last Ferry", "guest_name": "Megan Tolley",
            "guest_role": "ferry hand", "guest_gender": "f",
            "lines": [{"speaker": "late_host", "text": "Any crossing that stays with you?"},
                      {"speaker": "guest", "text": "A gull rode the whole way over.", "mood": "amused"},
                      {"speaker": "late_host", "text": "That is the most Port Wexley thing I have heard.",
                       "mood": "laughing"}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = writers.script_segment(Segment(slot_id=7, type=T.interview, show="late", target_s=120), w)
    assert [l.mood for l in seg.lines] == [None, "happy", "laughing"]


def test_the_view_carries_the_lines_mood_and_the_listeners_react():
    buf = Buffer()
    pl = Player(buf, world_mod.seed(), Producer(buf, 600), audio=False)
    seg = Segment(slot_id=0, type=T.interview, show="late", lines=[
        Line(speaker="late_host", text="Hello.", duration_s=1.0),
        Line(speaker="guest", text="Ha!", guest_name="Megan Tolley", duration_s=1.0, mood="laughing")])
    pl.current, pl.line_idx, pl.seg_start, pl.line_start = seg, 1, 0.0, 0.0
    v = pl.view(0.5)
    assert v.mood == "laughing"
    assert scenes._mood(v, True) == "laughing" and scenes._mood(v, False) == "happy"
    v.mood = "cross"
    assert scenes._mood(v, False) == ""                      # a cross word leaves the others as they are
    pygame.init()
    for m in sprites.MOODS:                                  # every face draws, talking and shut, at every size
        c = pygame.Surface((320, 180))
        for scale in (1, 2, 4):
            sprites.draw_character(c, 160, 170, "anchor", 0.0, 0.5, scale=scale, mood=m)
            sprites.draw_character(c, 160, 170, "late_host", 0.6, 0.5, scale=scale, mood=m)
