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
    memory = user.split("ON COASTWIDE ALREADY TODAY")[1]
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
    assert "ON COASTWIDE TODAY (for the nod to what was on)" in user and "Biscuit" in user
    assert "do NOT do any of these again" not in user


def test_the_first_item_and_other_shows_have_no_memory():
    assert "ON COASTWIDE" not in _prompt(world_mod.seed(), T.vox_pop)
    assert "ALREADY TODAY" not in _prompt(_world(), T.interview, show=schedule.get("late"))


def test_quaysides_loop_remembers_its_lunchtime():
    w = world_mod.seed()
    shop = "a shop or business that is new, closing or changing hands"
    w.record_aired("feature", "New owners take on the old Harrow Street haberdashery", None,
                   "The haberdashery on Harrow Street has new owners.", show="quayside", brief=shop)
    user = writers.build_prompt(T.feature, w, target_s=120.0, show=schedule.get("quayside"), brief=shop)[1]
    assert "ON QUAYSIDE ALREADY TODAY" in user and "The haberdashery on Harrow Street has new owners" in user
    assert "MIDDLE of Quayside" in user                        # no good afternoon on every item


def test_an_item_sees_the_last_on_its_own_brief_however_far_back():
    w = world_mod.seed()                  # Out and About's painter, six features before her angle came round
    art = "the town's culture: a gallery opening, or a painter in their studio"
    w.record_aired("feature", "Harbour painter opens her cannery studio", None, "Nell Harrower paints the boats.",
                   show="outabout", brief=art)
    for n in range(5):
        w.record_aired("feature", f"Feature {n}", None, f"Another angle {n}.", show="outabout", brief=f"angle {n}")
    show = schedule.get("outabout")
    user = writers.build_prompt(T.feature, w, target_s=120.0, show=show, brief=art)[1]
    assert "Nell Harrower paints the boats" in user.split("THE LAST FEATURES")[1]
    other = writers.build_prompt(T.feature, w, target_s=120.0, show=show, brief="angle 9")[1]
    assert "Nell Harrower paints the boats" not in other.split("THE LAST FEATURES")[1]


def test_a_middle_link_with_no_brief_is_caught_repeating_another():
    """Coastwide's middle links have no brief: nine aired as "The town settles into winter, one story at a time"."""
    w = world_mod.seed()
    w.record_aired("links", "The town settles into winter, one story at a time", None, "Clive...", show="magazine")
    assert writers._repeated("The town settles into winter, one story at a time", w, MAG, T.links, "") is not None
    assert writers._repeated("Clive counts the town hall clock's steps", w, MAG, T.links, "") is None
    # a show that doesn't remember its own items still leaves its unbriefed links alone
    w.record_aired("links", "Four votes carried tonight", None, "...", show="chamber")
    assert writers._repeated("Four votes carried tonight", w, schedule.get("chamber"), T.links, "") is None


def test_the_links_headline_is_the_links_own_not_the_theme():
    system = writers.build_prompt(T.links, world_mod.seed(), target_s=60.0, show=MAG)[0]
    assert "not the evening's theme" in system and "the evening's theme in under 12 words" not in system


def test_a_link_trails_only_what_comes_next(monkeypatch):
    """18:56 on 2026-11-21: "Coming up after the break, we have Dougal Crane on the roof of the old cannery, and a
    studio guest from the harbour who has very firm views on the hake": neither came."""
    from newsroom import rundown

    w = world_mod.seed()
    pos = next(i for i, e in enumerate(MAG.pattern) if schedule.as_item(e).type is T.links and not schedule.as_item(e).part
               and isinstance(schedule.as_item(e).brief, tuple))                     # the first middle link, before the interview
    after = [MAG.item(p) for p in range(pos + 1, pos + 3)]
    plan = {str(pos + 1): {"subject": "Bea Kowalczyk on her allotment", "guest": "Bea Kowalczyk"}}
    monkeypatch.setattr(rundown, "peek", lambda world, show, p: plan.get(str(p)))
    from datetime import datetime

    at = datetime(2026, 11, 21, 19, 0).timestamp()          # the trail is only what fits before the close
    user = writers.build_prompt(T.links, w, target_s=60.0, show=MAG, work={"order_pos": pos}, at_ts=at)[1]
    coming = user.split("WHAT COMES NEXT")[1]
    assert "a guest in the studio: Bea Kowalczyk on her allotment (with Bea Kowalczyk)" in coming
    assert f"a filmed report: {after[1].brief}" in coming
    assert "no other guest, film, place or subject is coming" in coming
    # the close trails nothing, and a show without a running order of its own gets nothing
    assert "WHAT COMES NEXT" not in writers.build_prompt(T.links, w, target_s=60.0, show=MAG, part="close",
                                                         work={"order_pos": pos})[1]
    assert "WHAT COMES NEXT" not in writers.build_prompt(T.links, w, target_s=60.0, show=schedule.get("chamber"),
                                                         work={"order_pos": 3})[1]


def test_the_close_says_no_hello():
    """All five closes of 2026-11-21 opened "Good evening"; Coastwide's "Good evening, and welcome to Coastwide"."""
    user = _prompt(world_mod.seed(), T.links, part="close")
    assert "No hello or welcome" in user


def test_the_last_link_trails_nothing_the_hour_wont_reach():
    from datetime import datetime

    w = world_mod.seed()
    pos = next(i for i, e in enumerate(MAG.pattern) if schedule.as_item(e).type is T.links and not schedule.as_item(e).part
               and isinstance(schedule.as_item(e).brief, tuple))
    early = writers._coming_up(w, MAG, pos, datetime(2026, 11, 21, 19, 0).timestamp())
    late = writers._coming_up(w, MAG, pos, datetime(2026, 11, 21, 19, 56).timestamp())
    assert "WHAT COMES NEXT, in this order" in early
    assert "nothing more of this programme but its goodbye" in late and "The Inquiry" in late


def test_the_opening_written_before_the_hour_trails_its_own_show():
    """The scratch evening of 2026-11-22: Coastwide's opening, timed at 18:59 as Full Time ended, was told nothing
    more of the programme was coming."""
    from datetime import datetime

    w = world_mod.seed()
    pos = next(i for i, e in enumerate(MAG.pattern) if schedule.as_item(e).part == "open")
    trail = writers._coming_up(w, MAG, pos, datetime(2026, 11, 22, 18, 59, 50).timestamp())
    assert "WHAT COMES NEXT, in this order" in trail
