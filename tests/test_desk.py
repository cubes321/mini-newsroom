"""The story desk asks again when a plan comes back empty, and leaves the batch for next time if it stays empty.

The model is stubbed: no network.
"""
from newsroom import desk, world as world_mod
from newsroom.models import StoryPlan, ThreadUpdate


def _world():
    w = world_mod.seed()
    for i in range(3):
        w.seed_thread(f"story {i}", "known so far", "", [])
    return w


def _stub(monkeypatch, replies):
    calls = []

    def complete_json(task, schema, system, user, **kw):
        calls.append(user)
        return replies[len(calls) - 1]
    monkeypatch.setattr(desk.llm, "complete_json", complete_json)
    return calls


def _full(w):
    return StoryPlan(updates=[ThreadUpdate(thread_id=t.id, phase="developing", next_development="It moves on.")
                              for t in desk.batch(w)])


def test_a_full_plan_is_one_call(monkeypatch):
    w = _world()
    calls = _stub(monkeypatch, [_full(w)])
    assert desk.plan(w) is not None and len(calls) == 1


def test_an_empty_plan_is_asked_again(monkeypatch):
    w = _world()
    todo = desk.batch(w)
    calls = _stub(monkeypatch, [StoryPlan(note="nothing to add"), _full(w)])
    assert desk.plan(w) is not None
    assert len(calls) == 2 and todo[0].id in calls[1].split("Your last reply")[1]
    assert all(t.planned_ts > 0 and t.next_development == "It moves on." for t in todo)


def test_the_desks_people_replace_a_threads_list_and_nothing_else_grows_it_past_four():
    """t220 kept 22 names through eight senior editor memos asking for three: the desk's list was added to
    the old one, and every aired item and merge added more (2026-10-31)."""
    w = _world()
    t, other = w.seed_thread("Harbour wall", "so far", "", []), w.seed_thread("The wall", "so far", "", [])
    people = w.people[:8]
    t.people = [p.id for p in people[:6]]
    update = ThreadUpdate(thread_id=t.id, phase="developing", next_development="On.",
                          people=[people[4].name, people[5].name, people[4].name])
    desk.apply(w, StoryPlan(updates=[update]))
    assert t.people == [people[4].id, people[5].id]
    desk.apply(w, StoryPlan(updates=[update.model_copy(update={"people": []})]))     # none named: kept
    assert t.people == [people[4].id, people[5].id]

    w.record_aired("bulletin", "The wall", t.id, " and ".join(p.name for p in people[:4]) + " spoke.")
    assert t.people == [people[4].id, people[5].id, people[0].id, people[1].id]   # filled to four, no more
    assert w.archive[-1]["people"] == [p.id for p in people[:4]]                  # still counted as on air
    other.people = [people[6].id, people[7].id]
    assert w.merge_thread(other.id, t.id) and len(t.people) == world_mod.THREAD_PEOPLE


def test_out_of_turn_updates_only_count_as_empty(monkeypatch):
    w = _world()
    stray = StoryPlan(updates=[ThreadUpdate(thread_id="t999", phase="peak", next_development="Elsewhere.")])
    calls = _stub(monkeypatch, [stray, stray])
    assert desk.plan(w) is None and len(calls) == 2


def test_still_empty_leaves_the_batch_for_next_time(monkeypatch):
    w = _world()
    todo = desk.batch(w)
    _stub(monkeypatch, [StoryPlan(), StoryPlan()])
    assert desk.plan(w) is None
    assert all(t.planned_ts == 0 for t in todo)
    assert [t.id for t in desk.batch(w)] == [t.id for t in todo]
