"""Coastwide remembers its evening: each item's writer sees tonight's items on the show and how the
last few of its own kind began, so the chip-shop vox pop doesn't come round five times an hour."""
from __future__ import annotations

from newsroom import schedule, writers, world as world_mod
from newsroom.models import SegmentType as T

MAG = schedule.get("magazine")


def _world() -> world_mod.World:
    w = world_mod.seed()                  # never load(): that's the real, process-cached world
    w.record_aired("vox_pop", "Port Wexley Votes on the Best Chips", None,
                   "We asked the harbour front one question: who fries the best chips in Port Wexley?", show="magazine")
    w.record_aired("feature", "Biscuit the Harbour Cat Comes Down From the Lifeboat Ladder", None,
                   "Biscuit has ruled the lifeboat station for six years.", show="magazine")
    w.record_aired("weather", "Cloud Rolls In Tonight", None, "Cloud tonight.", show="magazine")
    w.record_aired("vox_pop", "Harbour Loading Dock Divides the Quayside", None,
                   "Should the old loading dock become a cafe terrace?", show="magazine")
    w.record_aired("bulletin", "Harbour wall money confirmed", None, "The council confirmed...", show="news")
    w.record_aired("vox_pop", "Chips from yesterday", None, "Yesterday's chips.", show="magazine")
    w.archive[-1]["date"] = "2000-01-01"
    return w


def _prompt(w, seg_type, part="", show=MAG) -> str:
    return writers.build_prompt(seg_type, w, target_s=60.0, show=show, part=part)[1]


def test_a_vox_pop_sees_tonights_items_and_how_the_last_vox_pops_began():
    user = _prompt(_world(), T.vox_pop)
    memory = user.split("ON COASTWIDE ALREADY TONIGHT")[1]
    assert "vox pop: Port Wexley Votes on the Best Chips" in memory
    assert "feature: Biscuit the Harbour Cat" in memory
    assert "THE LAST VOX POPS, how they began. This vox pop is about none of these" in memory and "who fries the best chips" in memory
    assert "Cloud Rolls In" not in memory                      # the weather comes round as it should
    assert "Harbour wall money" not in memory                  # another show
    assert "Chips from yesterday" not in memory                # another day


def test_a_feature_sees_the_evening_but_only_features_as_its_kind():
    user = _prompt(_world(), T.feature)
    assert "Port Wexley Votes on the Best Chips" in user and "THE LAST FEATURES" in user
    assert "who fries the best chips" not in user.split("THE LAST FEATURES")[1]


def test_the_goodbye_gets_the_list_for_its_nod():
    user = _prompt(_world(), T.links, part="close")
    assert "ON COASTWIDE TONIGHT (for the nod to what was on)" in user and "Biscuit" in user
    assert "do NOT do any of these again" not in user


def test_the_first_item_and_other_shows_have_no_memory():
    assert "ON COASTWIDE" not in _prompt(world_mod.seed(), T.vox_pop)
    assert "ALREADY TONIGHT" not in _prompt(_world(), T.interview, show=schedule.get("late"))
