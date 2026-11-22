"""The same few people and tics: who has been on a lot lately is rested, and so is a trait said aloud too often."""
from __future__ import annotations

from newsroom import world as world_mod


def test_the_most_named_lately_are_rested_and_said_after_the_cache_break():
    """2026-11-21: Dolores Finch in about 28 of the evening news's items, seven Coastwide guests called Ruth, Miles
    "out of breath" 22 times."""
    w = world_mod.seed()
    dolores = w.ensure_person("Dolores Finch", "owner, Gull's Rest", kind="resident")
    for i in range(7):
        w.record_aired("bulletin", f"Chips {i}", None, f"Dolores Finch says the queue reached the van ({i}).", show="news")
    for first, last in (("Ruth", "Okonedo"), ("Ruth", "Keddie"), ("Ruth", "Carrow")):
        w.ensure_person(f"{first} {last}", "resident", kind="resident")
        w.record_aired("vox_pop", "Ruth's view", None, f"{first} {last} told us.", show="magazine")
    for i in range(3):
        w.record_aired("field_report", "Quay", None, "Miles Okafor is on the quay, out of breath as ever.", show="news")
    line = w.rested_line()
    assert f"{dolores.name} (7 items)" in line and "unless the item is about them" in line
    assert "Ruth (3)" in line
    assert "Miles out of breath (3 times)" in line
    summary = w.summary_for_prompt()
    from newsroom.llm import CACHE_BREAK
    assert summary.index("ON A LOT LATELY") > summary.index(CACHE_BREAK)


def test_nobody_is_rested_on_a_quiet_day_or_from_another_day():
    w = world_mod.seed()
    w.ensure_person("Dolores Finch", "owner, Gull's Rest", kind="resident")
    for i in range(7):
        w.record_aired("bulletin", f"Chips {i}", None, "Dolores Finch fried.", show="news")
        w.archive[-1]["date"] = "2000-01-01"
    w.record_aired("bulletin", "Chips", None, "Dolores Finch fried.", show="news")
    assert w.rested_line() == ""


def test_nobody_booked_for_the_item_is_told_to_rest():
    """The Panel names its three panellists every round: by the third its prompt would have rested them."""
    from newsroom import schedule, writers
    from newsroom.models import SegmentType as T

    w = world_mod.seed()
    w.ensure_person("Marjorie Pell", "Chair, Wexley Historical Society", kind="worthy")
    for i in range(7):
        w.record_aired("interview", f"Round {i}", None, f"Marjorie Pell said her piece ({i}).", show="panel")
    assert "Marjorie Pell (7 items)" in w.rested_line()
    w.panels = [{"date": w.last_date, "panellists": [{"name": "Marjorie Pell", "stance": "for the plaque"}],
                 "questions": [{"question": "The plaque?", "thread_id": None}]}]
    user = writers.build_prompt(T.interview, w, target_s=330.0, show=schedule.get("panel"), brief="a quick-fire round")[1]
    assert "Marjorie Pell (7 items)" not in user
    news = writers.build_prompt(T.bulletin, w, target_s=60.0, show=schedule.get("news"))[1]
    assert "Marjorie Pell (7 items)" in news
    planned = writers.build_prompt(T.interview, w, target_s=150.0, show=schedule.get("magazine"),
                                   work={"planned": {"subject": "Marjorie on the plaque", "guest": "Marjorie Pell"}})[1]
    assert "Marjorie Pell (7 items)" not in planned
