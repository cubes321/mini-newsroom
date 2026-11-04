"""The running-stories pool: a long story whose next step is days away waits for that day, off the writers'
board, instead of being reported with nothing new until it is closed as stalled and reborn under a new id
(the harbour wall: t220, covered 117 times, then t372). No network."""
from __future__ import annotations

import dataclasses
from datetime import date

import pytest

from newsroom import desk, inquiry, world as world_mod
from newsroom.config import CONFIG
from newsroom.world import due_date

TODAY = date(2026, 11, 4)


@pytest.mark.parametrize("text, due", [
    ("On Thursday 12 November Dolores Finch walks the tray sheet down", date(2026, 11, 12)),
    ("on Sunday 8 November, Remembrance Sunday, the lifeboat goes out", date(2026, 11, 8)),
    ("On Wednesday 4 November the shed checklist arrives", TODAY),
    ("close it after the 11th", date(2026, 11, 11)),
    ("on the 3rd the fence goes up", date(2026, 12, 3)),
    ("On 2 January the dip", date(2027, 1, 2)),
    ("Nothing dated, just more of the same", None),
    ("On 31 November", None),
])
def test_the_day_a_next_step_names(text, due):
    assert due_date(text, TODAY) == due


def _town(monkeypatch, pool=True):
    monkeypatch.setattr(world_mod.schedule, "now", lambda: 1_800_000_000.0)
    object.__setattr__(CONFIG, "story", dataclasses.replace(CONFIG.story, pool=pool))
    w = world_mod.seed()
    w.last_date = TODAY.isoformat()
    for t in w.threads:
        t.phase = "closed"

    def story(title, opened, mentions, nxt, phase="developing"):
        tid = w.update_thread(None, title, "under way")
        t = w.thread(tid)
        t.opened, t.mentions, t.next_development, t.phase = opened, mentions, nxt, phase
        t.moved_ts = 1_800_000_000.0 - 30 * 3600                # quiet for longer than any fade window
        return t
    return w, story


@pytest.fixture(autouse=True)
def _story_config():
    old = CONFIG.story
    yield
    object.__setattr__(CONFIG, "story", old)


def test_a_long_story_waits_for_its_day_off_the_board(monkeypatch):
    w, story = _town(monkeypatch)
    tray = story("Boxing Day tray order goes in early", "2026-10-31", 33, "On Thursday 12 November Dolores walks it down")
    wreath = story("Lifeboat crew ready the wreath", "2026-11-03", 28, "On Sunday 8 November the crew lay it")
    young = story("Boiler fails at the Academy", "2026-11-04", 3, "On Friday 6 November the engineer comes")
    undated = story("Gulls on the bins", "2026-10-30", 20, "Someone does something about the gulls")
    today = story("Shed checklist arrives", "2026-10-30", 26, "On Wednesday 4 November it reaches Kelly")
    peak = story("Bonfire stack on the Salting", "2026-10-30", 28, "On Thursday 5 November the gates open", "peak")
    peak.moved_ts = 1_800_000_000.0

    faded = w.fade_threads()
    assert {t.id for t in w.waiting_threads()} == {tray.id, wreath.id}
    assert tray.waits_until == "2026-11-12" and wreath.waits_until == "2026-11-08"
    assert tray not in faded and wreath not in faded and tray.phase == "developing"   # never faded for quiet
    assert young in faded and undated in faded and today in faded                     # the usual rules still
    board = {t.id for t in w.board_threads()}
    assert tray.id not in board and peak.id in board
    briefing = w.summary_for_prompt()
    assert "Running stories waiting for their day" in briefing
    assert f"[{tray.id}] Boxing Day tray order goes in early: next on Thursday 12 November" in briefing
    assert "WAITING in the running-stories pool until Sunday 8 November" in w.summary_for_editor()
    assert tray.id not in {t.id for t in desk.batch(w)}                                 # not planned till then
    assert tray in w.open_threads() and tray.id in {t.id for t in inquiry.candidates(w)}   # the deep-dive shows


def test_on_its_day_the_story_is_back_with_its_history(monkeypatch):
    w, story = _town(monkeypatch)
    wreath = story("Lifeboat crew ready the wreath", "2026-11-03", 28, "On Sunday 8 November the crew lay it")
    w.fade_threads()
    assert w.waiting(wreath)
    w.last_date = "2026-11-08"
    w.fade_threads(now=1_800_000_000.0 + 4 * 86400)
    assert not wreath.waits_until and wreath.phase == "developing" and wreath.mentions == 28
    assert wreath in w.board_threads() and wreath.moved_ts == 1_800_000_000.0 + 4 * 86400


def test_the_pool_can_be_switched_off(monkeypatch):
    w, story = _town(monkeypatch, pool=False)
    tray = story("Boxing Day tray order goes in early", "2026-10-31", 33, "On Thursday 12 November Dolores walks it down")
    w.fade_threads()
    assert not w.waiting_threads() and tray.phase == "faded"


def test_waiting_stories_leave_room_for_new_ones(monkeypatch):
    w, story = _town(monkeypatch)
    for i in range(CONFIG.story.thin_board):
        story(f"Long story number {i}", "2026-10-30", 12, "On Monday 9 November it moves").moved_ts = 1_800_000_000.0
    story("A fresh one", "2026-11-04", 1, "").moved_ts = 1_800_000_000.0
    w.fade_threads()
    assert len(w.open_threads()) == CONFIG.story.thin_board + 1 and len(w.board_threads()) == 1
    monkeypatch.setattr(w, "seeds_left", lambda: 5)
    assert desk.seed_room(w, len(w.board_threads())) == 2                               # a thin board again
