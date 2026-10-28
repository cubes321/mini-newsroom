"""The story desk merges threads that are one story under different titles (the title match in
test_same_story.py only catches near copies): the duplicate's coverage joins the kept thread, its
archive entries point there, and a later follow-up of it lands there too.

The model is stubbed: no network.
"""
from newsroom import desk, world as world_mod
from newsroom.models import StoryPlan, ThreadMerge, ThreadUpdate

T0 = 1_790_000_000.0


def _town():
    w = world_mod.seed()
    w.threads, w.archive = [], []
    station = w.update_thread(None, "Port Wexley fire station pushes for a second engine", "costing due", now=T0)
    w.update_thread(station, "Costing due Thursday", "costing due Thursday", now=T0 + 60)
    chief = w.update_thread(None, "Fire chief says one engine leaves harbour exposed", "chief speaks", now=T0 + 120)
    w.record_aired("bulletin", "Fire chief says one engine leaves harbour exposed", chief, "The chief spoke.")
    return w, station, chief


def _plan(monkeypatch, w, p):
    monkeypatch.setattr(desk.llm, "complete_json", lambda *a, **k: p)
    return desk.plan(w)


def test_the_desk_merges_a_duplicate_into_the_thread_it_repeats(monkeypatch):
    w, station, chief = _town()
    _plan(monkeypatch, w, StoryPlan(merges=[ThreadMerge(duplicate=chief, into=station)],
                                    updates=[ThreadUpdate(thread_id=chief, phase="peak", next_development="x")]))
    keep, dup = w.thread(station), w.thread(chief)
    assert dup.phase == "closed" and dup.merged_into == station          # the update didn't reopen it
    assert keep.mentions == 3 and len(keep.beats) == 3 and keep.status == "chief speaks"
    assert w.archive[-1]["thread_id"] == station
    assert w.update_thread(chief, "Fire chief shows the logbook", "logbook shown") == station
    assert w.thread(station).mentions == 4


def test_a_merge_that_names_a_closed_unknown_or_the_same_thread_does_nothing():
    w, station, chief = _town()
    assert not w.merge_thread(chief, chief) and not w.merge_thread(chief, "t999")
    w.thread(station).phase = "closed"
    assert not w.merge_thread(chief, station) and w.thread(chief).phase != "closed"


def test_a_live_duplicate_brings_a_faded_thread_back():
    w, station, chief = _town()
    w.thread(station).phase = "faded"
    assert w.merge_thread(chief, station)
    assert w.thread(station).phase == "developing"


def test_merged_into_survives_a_save():
    w, station, chief = _town()
    w.merge_thread(chief, station)
    w2 = world_mod._from_dict(world_mod._to_dict(w))
    assert w2.thread(chief).merged_into == station
