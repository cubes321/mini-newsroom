"""The story desk asks again when a plan comes back empty, and leaves the batch for next time if it stays empty.

The model is stubbed: no network.
"""
from datetime import date, datetime, timedelta

from newsroom import desk, schedule, world as world_mod
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
    assert all(t.planned_ts == 0 and not t.planned_seen for t in todo)
    assert [t.id for t in desk.batch(w)] == [t.id for t in todo]


# ------------------------------------------------------------------ only what has changed is planned again

THREE_AM = datetime(2026, 11, 16, 3, 0).timestamp()         # no new stories before six: a round has nothing else to do


def _quiet_night(monkeypatch):
    """A board the desk has planned from end to end, in the small hours, and the calls it has made since."""
    monkeypatch.setattr(schedule, "now", lambda: THREE_AM)
    w = _world()
    calls = []

    def complete_json(task, schema, system, user, **kw):
        calls.append(user)
        return _full(w)
    monkeypatch.setattr(desk.llm, "complete_json", complete_json)
    while desk.batch(w):
        assert desk.plan(w) is not None
    del calls[:]
    return w, calls


def test_a_board_nothing_has_changed_on_is_not_planned_again(monkeypatch):
    """On the night of 2026-11-14 the desk planned t484, t513, t517 and t519 eight rounds running with nothing
    aired in between (22 rounds of 24 for two of them), and the senior editor asked it to stop restating them."""
    w, calls = _quiet_night(monkeypatch)
    notes = len(w.desk_notes)
    for _ in range(3):
        p = desk.plan(w)
        assert p is not None and not p.updates and "no call" in p.note
    assert calls == [] and len(w.desk_notes) == notes                   # no call, and no round for the senior editor to read

    a, b, c = w.board_threads()[:3]
    w.update_thread(a.id, "It aired again", "something new")            # covered on air: its turn again
    assert desk.batch(w) == [a]
    desk.plan(w)
    assert len(calls) == 1 and f"plan only these threads: {a.id}." in calls[0] and desk.batch(w) == []

    w.senior_memo, w.senior_memo_at = f"Take {b.id} away from the council.", "2026-11-16 02:08"
    assert desk.batch(w) == [b]                                         # the memo names it
    desk.plan(w)
    assert len(calls) == 2 and desk.batch(w) == []                      # once a memo
    w.senior_memo_at = "2026-11-16 04:08"                               # the next memo still names it
    assert desk.batch(w) == [b]
    desk.plan(w)

    assert desk.batch(w) == [] and "GOING QUIET" not in w.summary_for_editor()
    monkeypatch.setattr(schedule, "now", lambda: THREE_AM + 2.5 * 3600)  # half past five: the one-offs are going quiet
    assert "GOING QUIET" in w.summary_for_editor() and c.id in {t.id for t in desk.batch(w)}
    while desk.batch(w):
        desk.plan(w)
    n = len(calls)
    desk.plan(w)
    assert len(calls) == n                                              # told once, not every round while it lasts

    w.last_date = (date.fromisoformat(w.last_date) + timedelta(days=1)).isoformat()
    assert {a.id, b.id, c.id} <= {t.id for t in desk.batch(w)}          # a new day: the dates have all moved


def test_a_quiet_board_is_still_asked_when_a_round_has_something_else_to_do(monkeypatch):
    w, calls = _quiet_night(monkeypatch)
    desk.plan(w, breaking="now")                                        # the producer asked for breaking news
    assert len(calls) == 1 and "plan only these threads: (none)." in calls[0]
    monkeypatch.setattr(w, "seeds_left", lambda now=None: 1)            # by day: a new story may be seeded
    desk.plan(w)
    assert len(calls) == 2


def test_a_story_from_before_the_desk_kept_what_it_saw_is_planned_once_more(monkeypatch):
    w, _calls = _quiet_night(monkeypatch)
    d = world_mod._to_dict(w)
    for t in d["threads"]:
        t.pop("planned_seen")
    old = world_mod._from_dict(d)
    assert {t.id for t in desk.batch(old)} == {t.id for t in old.board_threads()[: len(desk.batch(old))]} and desk.batch(old)


def test_the_desk_cant_script_a_game_before_it_is_played(monkeypatch):
    """The Tides' match of 2026-11-21: the desk's NEXT had the score before kick-off, against the sports desk's."""
    from datetime import datetime

    from newsroom import desk, schedule, world as world_mod
    from newsroom.models import NewThread, StoryPlan, ThreadUpdate

    w = world_mod.seed()
    w.last_date = "2026-11-21"
    tid = w.update_thread(None, "Tides Host Saltby Saturday", "Kick-off at three today")
    t = w.thread(tid)
    t.next_development = "On Saturday 21 November the Tides kick off at three."
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 21, 9, 0).timestamp())
    scripted = ("On Saturday 21 November the Tides kick off at three on a frosty pitch, Hal Anand in the stand; "
                "Saltby lead at the break and it ends one apiece.")
    desk.apply(w, StoryPlan(updates=[ThreadUpdate(thread_id=tid, phase="peak", next_development=scripted)]), only={tid})
    assert t.next_development == "On Saturday 21 November the Tides kick off at three on a frosty pitch, Hal Anand in the stand."
    # a new story's plan too
    new = desk.seed(w, NewThread(title="Wreckers away at Saltby", status="The coach is booked.",
                                 next_development="On Saturday 28 November the Wreckers go to Saltby: they win 20-12.", people=[]))
    assert new.next_development == "On Saturday 28 November the Wreckers go to Saltby."
    # once the afternoon's games are over, the result is the sports desk's and the desk may carry it
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 21, 18, 30).timestamp())
    after = "On Saturday 21 November the Tides beat Saltby three-one, and the crowd stays for the pies."
    desk.apply(w, StoryPlan(updates=[ThreadUpdate(thread_id=tid, phase="peak", next_development=after)]), only={tid})
    assert t.next_development == after
    assert "an editor NEVER writes a score" in w.summary_for_editor() and "Tidewater Town FC (the Tides)" in w.summary_for_editor()
