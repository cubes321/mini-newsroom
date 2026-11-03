"""Presenters greet for the hour they air: Dana's morning field reports had opened "Good evening"
(26 times over two mornings) because her card called her the evening news anchor.

Template scripts only (NEWSROOM_LLM=off, set in conftest).
"""
import time

from newsroom import schedule, writers, world as world_mod
from newsroom.models import SegmentType as T


def _at(hour: int) -> float:
    t = time.localtime()
    return time.mktime((t.tm_year, t.tm_mon, t.tm_mday, hour, 20, 0, 0, 0, -1))


def test_the_brief_names_the_greeting_for_the_hour(monkeypatch):
    w = world_mod.seed()
    news = schedule.get("news")
    for hour, word in ((10, "morning"), (14, "afternoon"), (19, "evening"), (0, "evening")):
        monkeypatch.setattr(schedule, "now", lambda h=hour: _at(h))
        _, user = writers.build_prompt(T.field_report, w, target_s=75.0, show=news)
        assert f'any greeting is "good {word}"' in user


def test_the_anchors_card_no_longer_says_evening_and_a_saved_world_takes_the_new_one():
    w = world_mod.seed()
    assert "evening" not in w.character("anchor").role
    saved = world_mod._to_dict(w)
    for c in saved["characters"]:
        if c["id"] == "anchor":
            c["role"] = "evening news anchor"
    assert "evening" not in world_mod._from_dict(saved).character("anchor").role
