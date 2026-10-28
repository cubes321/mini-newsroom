"""A news field report is offered the open threads the briefing doesn't list, to pick up before
it invents a story: on 2026-10-27, told to leave Miles's last three alone with only the
briefing's five to choose from, field reports opened four "second fire engine" threads.
"""
from newsroom import schedule, world as world_mod, writers
from newsroom.models import SegmentType


def _town(n):
    w = world_mod.seed()
    w.threads = []
    ids = [w.update_thread(None, f"Story {i}", f"status {i}") for i in range(n)]
    return w, ids


def _prompt(w, show="news"):
    return writers.build_prompt(SegmentType.field_report, w, target_s=60, show=schedule.get(show))[1]


def test_threads_beyond_the_briefing_are_offered_planned_ones_first():
    w, ids = _town(9)
    listed = {t.id for t in w.briefing_threads()}
    beyond = [i for i in ids if i not in listed]
    w.thread(beyond[-1]).next_development = "On Friday the council votes."
    user = _prompt(w)
    block = user.split("QUIET STORIES")[1].split("\n\n")[0]
    offered = [line.split("]")[0].split("[")[1] for line in block.splitlines() if line.strip().startswith("- [")]
    assert offered[0] == beyond[-1] and not listed & set(offered)
    assert len(offered) == writers.QUIET_THREADS


def test_no_quiet_list_when_the_briefing_shows_everything_or_on_a_light_show():
    w, _ = _town(3)
    assert "QUIET STORIES" not in _prompt(w)
    w, _ = _town(9)
    assert "QUIET STORIES" not in _prompt(w, "breakfast")
