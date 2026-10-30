"""The senior editor reads the desk's recent rounds, merges duplicates, may open one story past the
desk's cap, and leaves a memo the desk reads on its next rounds.

The model is stubbed: no network.
"""
from newsroom import desk, senior, world as world_mod
from newsroom.config import CONFIG
from newsroom.models import NewThread, SeniorMemo, StoryPlan, ThreadMerge, ThreadUpdate


def _world(n=3):
    w = world_mod.seed()
    for i in range(n):
        w.seed_thread(f"story {i}", "known so far", "", [])
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
    w = _world(CONFIG.story.max_open_threads + 2)              # the board is past the desk's cap
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
