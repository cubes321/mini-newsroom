"""The running-stories pool: a long story whose next step is days away waits for that day, off the writers'
board, instead of being reported with nothing new until it is closed as stalled and reborn under a new id
(the harbour wall: t220, covered 117 times, then t372). No network."""
from __future__ import annotations

import dataclasses
import itertools
import time
from datetime import date

import pytest

from newsroom import desk, inquiry, senior, world as world_mod
from newsroom.config import CONFIG
from newsroom.models import StoryPlan, ThreadUpdate
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


def _memo_round(monkeypatch, w, memo, updates):
    """One desk round with the senior editor's memo just left and the model's reply stubbed."""
    w.senior_memo, w.senior_memo_at, w.last_senior_ts = memo, "2026-11-04 20:00", time.time()
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append(user)
        return StoryPlan(updates=[ThreadUpdate(thread_id=i, phase=ph, next_development=nxt) for i, ph, nxt in updates])
    monkeypatch.setattr(desk.llm, "complete_json", complete_json)
    assert desk.plan(w) is not None
    return seen


def _pooled(monkeypatch):
    ticks = itertools.count(1_800_000_000)                  # a clock of its own: Windows' ticks every 15 ms
    monkeypatch.setattr(time, "time", lambda: float(next(ticks)))
    w, story = _town(monkeypatch)
    tray = story("Boxing Day tray order goes in early", "2026-10-31", 33, "On Thursday 12 November Dolores walks it down")
    wreath = story("Lifeboat crew ready the wreath", "2026-11-03", 28, "On Sunday 8 November the crew lay it")
    fresh = story("Boiler fails at the Academy", "2026-11-04", 3, "The engineer comes")
    fresh.moved_ts = 1_800_000_000.0
    w.fade_threads()
    assert w.waiting(tray) and w.waiting(wreath) and fresh in w.board_threads()
    return w, tray, wreath, fresh


def test_a_waiting_story_the_memo_names_is_within_the_desks_reach_once_and_moves(monkeypatch):
    """On the night of 2026-11-14 four memos asked for t454, t492, t474 and t476 to come off Monday 16, which
    had eight stories due; the desk plans only the board, so they stayed."""
    w, tray, wreath, fresh = _pooled(monkeypatch)
    assert desk.reach(w) == []                                           # no memo: nothing from the pool
    seen = _memo_round(monkeypatch, w, f"Thursday 12 is too full: move {tray.id} to Monday 16 November.", [
        (fresh.id, "developing", "The engineer fits the valve"),
        (tray.id, "developing", "On Monday 16 November Dolores walks the tray sheet down"),
        (wreath.id, "developing", "On Monday 16 November the crew lay it")])
    reach = seen[0].split("ALSO WITHIN REACH")[1].split("DUPLICATES")[0]
    assert tray.id in reach and wreath.id not in reach and len(seen) == 1
    assert "threads within reach this round" in seen[0]
    assert tray.waits_until == "2026-11-16" and w.waiting(tray) and tray.next_development.startswith("On Monday 16")
    assert tray.id not in {t.id for t in desk.batch(w)}                  # moved, and still off the rounds
    assert wreath.waits_until == "2026-11-08" and "Sunday 8" in wreath.next_development   # not named: out of turn
    assert w.desk_notes[-1]["planned"] == [fresh.id] and w.desk_notes[-1]["pool"] == [tray.id]
    assert f"offered from the pool {tray.id}" in senior._rounds(w)
    assert desk.reach(w) == []                                           # once a memo
    w.last_senior_ts = time.time() + 1                                   # the next memo still names it
    assert desk.reach(w) == [tray]


def test_a_round_that_leaves_the_pooled_stories_alone_is_not_an_empty_plan(monkeypatch):
    w, tray, wreath, fresh = _pooled(monkeypatch)
    seen = _memo_round(monkeypatch, w, f"Keep {tray.id} and {wreath.id} where they are.",
                       [(fresh.id, "developing", "The engineer fits the valve")])
    assert len(seen) == 1 and "ALSO WITHIN REACH" in seen[0]
    assert (tray.waits_until, wreath.waits_until) == ("2026-11-12", "2026-11-08")


def test_a_pooled_story_is_moved_only_to_a_day_to_come_or_closed(monkeypatch):
    w, tray, wreath, fresh = _pooled(monkeypatch)
    _memo_round(monkeypatch, w, f"Move {tray.id}. Close {wreath.id}: the service is over.", [
        (fresh.id, "developing", "The engineer fits the valve"),
        (tray.id, "developing", "Dolores thinks again about the tray"),          # no day: back on every bulletin
        (wreath.id, "closed", "Laid, and done")])
    assert tray.waits_until == "2026-11-12" and tray.next_development.startswith("On Thursday 12 November")
    assert wreath.phase == "closed" and not wreath.waits_until
    # "Close it at the hand-over" is not "close it now": the ending is reported on its day first.
    _memo_round(monkeypatch, w, f"Close {tray.id} at the hand-over.", [
        (fresh.id, "developing", "The engineer fits the valve"),
        (tray.id, "closed", "On Friday 13 November Dolores hands the tray sheet over, and the story ends there")])
    assert tray.phase == "resolving" and tray.waits_until == "2026-11-13" and w.waiting(tray)
    _memo_round(monkeypatch, w, f"Bring {tray.id} forward to today.", [
        (fresh.id, "developing", "The engineer fits the valve"),
        (tray.id, "developing", "On Wednesday 4 November Dolores walks the tray sheet down")])
    assert not tray.waits_until and tray in w.board_threads() and tray.moved_ts == 1_800_000_000.0


def test_a_story_on_tonights_council_agenda_is_not_offered_from_the_pool(monkeypatch):
    w, tray, wreath, fresh = _pooled(monkeypatch)
    w.senior_memo, w.last_senior_ts = f"Move {tray.id} and {wreath.id}.", time.time()
    monkeypatch.setattr(desk.chamber, "on_agenda", lambda world: {tray.id})
    assert desk.reach(w) == [wreath]


def test_waiting_stories_leave_room_for_new_ones(monkeypatch):
    w, story = _town(monkeypatch)
    for i in range(CONFIG.story.thin_board):
        story(f"Long story number {i}", "2026-10-30", 12, "On Monday 9 November it moves").moved_ts = 1_800_000_000.0
    story("A fresh one", "2026-11-04", 1, "").moved_ts = 1_800_000_000.0
    w.fade_threads()
    assert len(w.open_threads()) == CONFIG.story.thin_board + 1 and len(w.board_threads()) == 1
    monkeypatch.setattr(w, "seeds_left", lambda: 5)
    assert desk.seed_room(w, len(w.board_threads())) == 2                               # a thin board again


def _close(w, t, nxt):
    desk.apply(w, StoryPlan(updates=[ThreadUpdate(thread_id=t.id, phase="closed", next_development=nxt)]))


def test_a_story_closed_with_its_ending_still_to_come_waits_for_it(monkeypatch):
    """On the night of 2026-11-14 the desk closed t515 on the Sunday with Monday's ending ("... passes the crane
    invoice for payment ... the story ends there"). It was a day old and on the board, so nothing held it, and
    the ending had no writer left to report it."""
    w, story = _town(monkeypatch)
    crane = story("Harbourmaster says crane invoice still under checks", "2026-11-03", 9, "The office checks it")
    crane.moved_ts = 1_800_000_000.0
    _close(w, crane, "On Thursday 5 November the harbour office passes the crane invoice, and the story ends there")
    assert crane.phase == "resolving" and crane.waits_until == "2026-11-05"      # a short story waits too
    assert w.waiting(crane) and crane not in w.board_threads()
    assert crane.next_development.startswith("On Thursday 5 November")           # the ending is its NEXT

    # Its day: back on the board and planned at once, before any piece is written, as t349 and t469 were.
    w.last_date = "2026-11-05"
    w.fade_threads(now=1_800_000_000.0 + 86400)
    assert crane in w.board_threads()
    _close(w, crane, "Today, Thursday 5 November, the harbour office passes the crane invoice")
    assert crane.phase == "resolving" and crane in w.board_threads()
    w.update_thread(crane.id, "Crane invoice passed for payment", "paid")
    _close(w, crane, "On Thursday 5 November the harbour office passed the crane invoice: settled")
    assert crane.phase == "closed"


def test_a_story_closed_with_todays_ending_is_reported_first(monkeypatch):
    w, story = _town(monkeypatch)
    sail = story("Bernard Moss airs the red spinnaker", "2026-11-02", 3, "On Wednesday 4 November he lays it flat")
    sail.updated, sail.moved_ts = "2026-11-02", 1_800_000_000.0 - 3600          # back from the pool, not covered today
    _close(w, sail, "Later on Wednesday 4 November Bernard lays the spinnaker flat and the surname goes to the file")
    assert sail.phase == "resolving" and not sail.waits_until
    assert sail.moved_ts == 1_800_000_000.0                                     # a full window to be reported in
    w.update_thread(sail.id, "The red spinnaker is laid flat", "done")
    _close(w, sail, "Wednesday 4 November: the spinnaker was laid flat and the surname went to the file")
    assert sail.phase == "closed"

    # Covered today, but before the desk wrote the ending: it has not gone out either.
    salt = story("Frost sells the salt off Harrow Street", "2026-11-03", 27, "The frost holds")
    salt.moved_ts = 1_800_000_000.0
    desk.apply(w, StoryPlan(updates=[ThreadUpdate(
        thread_id=salt.id, phase="resolving", next_development="By this evening, Wednesday 4 November, the last sack goes")]))
    _close(w, salt, "By the evening of Wednesday 4 November the last sack goes, and the frost story closes")
    assert salt.phase == "resolving"
    w.update_thread(salt.id, "The last of the rock salt goes", "sold out")
    _close(w, salt, "By the evening of Wednesday 4 November the last sack goes, and the frost story closes")
    assert salt.phase == "closed"


def test_a_story_that_is_over_closes(monkeypatch):
    w, story = _town(monkeypatch, pool=False)

    def fresh(title, nxt):
        t = story(title, "2026-11-03", 4, nxt)
        t.moved_ts = 1_800_000_000.0
        return t
    cups, rye, fence, one_off, quiet, later = (
        fresh("Thirteen numbered cups", "The count goes on"), fresh("Rye on Harrow Street", "The rye sells"),
        fresh("The allotment fence", "The fence waits"), fresh("Calm morning on the slipway", ""),
        fresh("Gulls on the bins", "Someone does something"), fresh("Pontoon fenders", "The fender waits"))
    _close(w, cups, "On Monday 2 November the thirteen cups went nine to four")          # a day gone by
    _close(w, rye, "The rye settles into a standing Wednesday bake")                     # no day named
    _close(w, fence, "The fence went up on the 3rd, and that is that")                   # not 3 December
    _close(w, one_off, "Wednesday 4 November's calm morning piece ran, and is done")     # covered today, never planned
    assert [t.phase for t in (cups, rye, fence, one_off)] == ["closed"] * 4
    quiet.phase = "faded"
    _close(w, quiet, "On Friday 6 November the bins are emptied")                        # a faded story stays down
    assert quiet.phase == "closed"
    _close(w, later, "On Friday 6 November the third fender goes on and the job is signed off")
    assert later.phase == "resolving" and not later.waits_until                          # the pool is switched off


def test_a_held_close_keeps_its_day_when_closed_again_without_one(monkeypatch):
    """On the night of 2026-11-19, t513, t558 and t560 were held at 19:22 to close on the Friday, the Sunday and the
    Tuesday; at 21:22 a memo said "close them on the board now", the desk closed all three with notes naming no day,
    the closes stood, and two were never covered again."""
    w, story = _town(monkeypatch)
    crane = story("Harbourmaster says crane invoice still under checks", "2026-11-03", 9, "The office checks it")
    crane.moved_ts = 1_800_000_000.0
    ending = "On Thursday 5 November the harbour office passes the crane invoice, and the story ends there"
    _close(w, crane, ending)
    assert crane.phase == "resolving" and crane.waits_until == crane.closes_on == "2026-11-05"
    _close(w, crane, "Close it: the checks are a formality and there is nothing more to report")    # no day
    assert crane.phase == "resolving" and crane.waits_until == "2026-11-05" and w.waiting(crane)
    assert crane.next_development == ending                                       # the ending, still to report
    _close(w, crane, "Close it after Tuesday 3 November's checks")                # a day gone by: the same
    assert crane.phase == "resolving" and crane.next_development == ending

    # Its day: once the ending has gone out, a close with no day stands, and the hold is spent.
    w.last_date = "2026-11-05"
    w.fade_threads(now=1_800_000_000.0 + 86400)
    _close(w, crane, "Close it now")
    assert crane.phase == "resolving"                                             # not reported yet today
    w.update_thread(crane.id, "Crane invoice passed for payment", "paid")
    _close(w, crane, "Close it now: paid")
    assert crane.phase == "closed" and crane.closes_on == ""


def test_a_held_close_moved_to_a_later_day_takes_that_day(monkeypatch):
    w, story = _town(monkeypatch)
    sign = story("The fender sign-off", "2026-11-03", 6, "The engineer inspects")
    sign.moved_ts = 1_800_000_000.0
    _close(w, sign, "On Thursday 5 November the fender is signed off, and the story ends there")
    _close(w, sign, "On Monday 9 November the fender is signed off after a second look, and that is the end")
    assert sign.phase == "resolving" and sign.waits_until == sign.closes_on == "2026-11-09"
    assert sign.next_development.startswith("On Monday 9 November")
