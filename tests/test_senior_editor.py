"""The senior editor reads the desk's recent rounds, merges duplicates, may open one story past the
desk's cap, and leaves a memo the desk reads on its next rounds.

The model is stubbed: no network.
"""
import time

from newsroom import desk, schedule, senior, world as world_mod
from newsroom.config import CONFIG
from newsroom.models import NewThread, SeniorMemo, StoryPlan, ThreadMerge, ThreadUpdate


def _world(n=3):
    w = world_mod.seed()
    for i in range(n):
        w.seed_thread(f"story {i}", "known so far", "", [])
    w.seeded = []                          # the board as found: none of it seeded today
    return w


def _stub(monkeypatch, module, replies):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, user))
        return replies[len(seen) - 1]
    monkeypatch.setattr(module.llm, "complete_json", complete_json)
    return seen


def test_the_desk_records_its_rounds_and_reads_the_memo(monkeypatch):
    w = _world()
    todo = desk.batch(w)
    plan = StoryPlan(updates=[ThreadUpdate(thread_id=t.id, phase="developing", next_development="On.")
                              for t in todo], note="Everything converges on Monday's council")
    seen = _stub(monkeypatch, desk, [plan, plan])
    desk.plan(w)
    assert "SENIOR EDITOR'S MEMO" not in seen[0][1]
    assert w.desk_notes[-1]["planned"] == [t.id for t in todo]
    assert w.desk_notes[-1]["note"] == "Everything converges on Monday's council"
    w.senior_memo, w.senior_memo_at = f"Take {todo[0].id} away from the council.", "2026-10-30 20:00"
    desk.plan(w)
    assert f"SENIOR EDITOR'S MEMO (2026-10-30 20:00)" in seen[1][1] and f"Take {todo[0].id} away" in seen[1][1]


def test_desk_notes_keep_the_last_dozen(monkeypatch):
    w = _world()
    plan = StoryPlan(updates=[ThreadUpdate(thread_id=t.id, phase="developing", next_development="On.")
                              for t in desk.batch(w)])
    _stub(monkeypatch, desk, [plan] * 15)
    for _ in range(15):
        desk.plan(w)
    assert len(w.desk_notes) == 12


def test_a_review_merges_seeds_past_the_cap_and_leaves_the_memo(monkeypatch):
    monkeypatch.setattr(schedule, "now", lambda: _at(12))
    w = _world(CONFIG.story.thin_board + 2)                    # a full board
    a, b = w.open_threads()[:2]
    w.desk_notes = [{"at": "2026-10-30 19:30", "planned": [a.id], "new": 0, "merges": 0,
                     "note": "Everything converges on Monday's council"}]
    memo = SeniorMemo(memo=f"{a.id}: move it on through the divers, not the money.",
                      merges=[ThreadMerge(duplicate=b.id, into=a.id)],
                      new_thread=NewThread(title="Gull steals the regatta trophy", status="It flew off with it.",
                                           next_development="On Saturday the harbourmaster gives chase."))
    seen = _stub(monkeypatch, senior, [memo])
    before = len(w.threads)
    assert senior.review(w) is memo
    task, user = seen[0]
    assert task == "senior_editor" and "Everything converges on Monday's council" in user
    assert w.thread(b.id).merged_into == a.id
    assert len(w.threads) == before + 1 and w.threads[-1].title == "Gull steals the regatta trophy"
    assert w.senior_memo.startswith(a.id) and w.senior_memo_at.startswith(w.last_date)
    assert not senior.should_review(w)


def test_a_dry_review_changes_nothing(monkeypatch):
    w = _world()
    _stub(monkeypatch, senior, [SeniorMemo(memo="Close t001.",
                                           new_thread=NewThread(title="x", status="y", next_development="z"))])
    before = len(w.threads)
    senior.review(w, dry=True)
    assert len(w.threads) == before and w.senior_memo == ""


def test_a_failed_review_keeps_the_last_memo(monkeypatch):
    w = _world()
    w.senior_memo = "Keep this."

    def down(*a, **kw):
        raise senior.llm.LLMUnavailable("down")
    monkeypatch.setattr(senior.llm, "complete_json", down)
    assert senior.review(w) is None and w.senior_memo == "Keep this."


def test_the_senior_editor_is_routed_to_sonnet():
    assert CONFIG.llm.provider_name_for("senior_editor") == "claude_sonnet"
    assert CONFIG.story.review_every_s == 7200


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


def test_no_new_stories_overnight_then_the_days_come_a_few_at_a_time(monkeypatch):
    """All eight of 2026-11-01's new stories went between midnight and half past three, into the
    overnight repeats, and the day's shows had none."""
    w = _world()
    assert w.seeds_left(_at(0, 5)) == 0 and w.seeds_left(_at(5, 59)) == 0
    assert w.seeds_left(_at(6)) == 1 and w.seeds_left(_at(12)) == 4 and w.seeds_left(_at(23, 59)) == 10
    w.seeded = [w.last_date] * 3
    assert w.seeds_left(_at(12)) == 1 and w.seeds_left(_at(9)) == 0
    monkeypatch.setattr(schedule, "now", lambda: _at(3, 30))
    assert desk.seed_room(w, 3) == 0


def test_the_desk_may_seed_one_a_round_two_on_a_thin_board_within_the_days_allowance(monkeypatch):
    monkeypatch.setattr(schedule, "now", lambda: _at(12))           # four of the day's released by noon
    w = _world(CONFIG.story.thin_board + 4)                    # the board the writers keep: 11 to 17 open
    assert desk.seed_room(w, len(w.open_threads())) == 1       # was 0 all night on 2026-10-29
    assert desk.seed_room(w, CONFIG.story.thin_board - 1) == 2
    for i in range(CONFIG.story.seeds_per_day):
        desk.seed(w, NewThread(title=f"Story {i}", status="s", next_development="n"))
    assert w.seeds_left() == 0 and desk.seed_room(w, 3) == 0


def test_the_senior_editor_seeds_nothing_once_the_day_is_used_up(monkeypatch):
    w = _world()
    w.seeded = [w.last_date] * CONFIG.story.seeds_per_day
    seen = _stub(monkeypatch, senior, [SeniorMemo(memo="Fine.", new_thread=NewThread(
        title="Gull steals the regatta trophy", status="s", next_development="n"))])
    before = len(w.threads)
    senior.review(w)
    assert "new_thread must be null" in seen[0][1] and len(w.threads) == before
