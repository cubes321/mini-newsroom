"""Threads fade off the air when they stop moving, and past [story] max_live_threads the stalest
fade: on 2026-10-28 every guest chat and field report had opened a thread and nothing retired
them (108 open). A faded thread comes back on a follow-up or from the story desk.

Explicit `now` values throughout: no clock offset to restore.
"""
from newsroom import desk, world as world_mod
from newsroom.config import CONFIG
from newsroom.models import StoryPlan, ThreadUpdate

H = 3600
T0 = 1_790_000_000.0            # in the past: a revival stamps the real clock


def _town():
    w = world_mod.seed()
    w.threads = []
    return w


def test_a_one_off_fades_after_its_window_and_a_follow_up_keeps_it_on():
    w = _town()
    a = w.update_thread(None, "Seal on the slipway", "spotted at dawn", now=T0)
    b = w.update_thread(None, "Harbour wall cracks", "engineers called", now=T0)
    for _ in range(3):
        w.update_thread(b, "Harbour wall: more cracks", "worse", now=T0)
    assert w.fade_threads(T0 + 7 * H) == []
    assert [t.id for t in w.fade_threads(T0 + CONFIG.story.fade_oneoff_h * H)] == [a]
    assert w.thread(a).phase == "faded" and a not in {t.id for t in w.open_threads()}
    w.update_thread(b, "Harbour wall: council meets", "Thursday", now=T0 + 20 * H)
    assert w.fade_threads(T0 + 40 * H) == []                 # moved at 20h: 24h from then
    assert [t.id for t in w.fade_threads(T0 + 44 * H)] == [b]


def test_a_follow_up_brings_a_faded_thread_back():
    w = _town()
    a = w.update_thread(None, "Seal on the slipway", "spotted at dawn", now=T0)
    w.fade_threads(T0 + 9 * H)
    w.update_thread(a, "The seal is back", "a second visit", now=T0 + 10 * H)
    t = w.thread(a)
    assert t.phase == "developing" and t.moved_ts == T0 + 10 * H
    assert a in {t.id for t in w.open_threads()}


def test_past_the_cap_the_stalest_fade_but_never_a_peak():
    w = _town()
    cap = CONFIG.story.max_live_threads
    ids = [w.update_thread(None, f"Story {i}", "x", now=T0 + i) for i in range(cap + 3)]
    for i in ids:                                           # covered enough not to be one-offs
        w.thread(i).mentions = 3
    w.thread(ids[0]).phase = "peak"                        # the oldest, but at its peak
    faded = {t.id for t in w.fade_threads(T0 + cap + 10)}
    assert faded == set(ids[1:4])
    assert len(w.open_threads()) == cap


def test_the_desk_hears_a_thread_is_going_quiet_and_can_revive_a_faded_one():
    w = _town()
    a = w.update_thread(None, "Seal on the slipway", "spotted", now=T0)
    b = w.update_thread(None, "Bakery petition", "300 names", now=world_mod.schedule.now() - 20 * H)
    w.thread(b).mentions = 3
    assert "GOING QUIET" in w.summary_for_editor()          # 4h left of b's 24
    w.fade_threads(T0 + 9 * H)                             # a fades
    assert a in {t.id for t in w.recently_faded(T0 + 10 * H)}
    plan = StoryPlan(updates=[ThreadUpdate(thread_id=a, phase="developing", next_development="It returns.")])
    desk.apply(w, plan, only={a})
    t = w.thread(a)
    assert t.phase == "developing" and t.moved_ts > T0 + 9 * H


def test_a_world_saved_before_fading_gets_a_full_window_not_an_instant_fade():
    w = _town()
    w.update_thread(None, "Harbour wall cracks", "engineers called", now=T0)
    d = world_mod._to_dict(w)
    for t in d["threads"]:
        del t["moved_ts"], t["faded_ts"]
    w2 = world_mod._from_dict(d)
    assert w2.fade_threads() == []
    assert w2.threads[0].moved_ts > T0


def test_closed_then_faded_threads_leave_the_list_first():
    w = _town()
    for i in range(world_mod.MAX_THREADS):
        w.update_thread(None, f"Story {i}", "x", now=T0 + i)
    w.threads[0].phase = "faded"
    w.threads[0].faded_ts = T0
    w.threads[1].phase = "closed"
    w.update_thread(None, "One more", "x", now=T0 + 500)
    w.update_thread(None, "And another", "x", now=T0 + 501)
    names = {t.title for t in w.threads}
    assert "Story 0" not in names and "Story 1" not in names and len(w.threads) == world_mod.MAX_THREADS
