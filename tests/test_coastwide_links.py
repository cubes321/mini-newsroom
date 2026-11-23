"""Coastwide's links begin and are captioned each their own way: on 2026-11-22 seven began "Clive, you've gone
quiet again, which in your case means..." and four were captioned "The Harbour at First Light". The model is
stubbed: no network."""
from __future__ import annotations

from newsroom import llm, schedule, world as world_mod, writers
from newsroom.models import BulletinScript, Segment, SegmentType as T

QUIET = "Clive, you've gone quiet again, which in your case means you're sitting on something odd."


def _link(first, caption):
    return BulletinScript.model_validate({"headline": "Clive's gull count", "lower_third": caption,
                                          "lines": [{"speaker": "mag_a", "text": first},
                                                    {"speaker": "mag_b", "text": "I've been counting the gulls."}]})


def _aired(w, first, caption):
    w.record_aired("links", "Clive's fact and what's coming up", None, first + " I've been counting.",
                   show="magazine", caption=caption)


def test_an_opening_or_caption_said_before_is_caught():
    w = world_mod.seed()
    show = schedule.get("magazine")
    assert writers.link_echoes(_link(QUIET, "Coastwide: The Harbour at First Light"), w, show) == []
    _aired(w, QUIET, "Coastwide: The Harbour at First Light")
    echo = writers.link_echoes(_link(QUIET.replace("odd", "odder"), "Harbour at first light"), w, show)
    assert len(echo) == 2 and "begins as an earlier link" in echo[0] and "caption is an earlier link's" in echo[1]
    fresh = _link("Right, Pat, the lifeboat crew have a new kettle.", "Coastwide: Kettles and Lifeboats")
    assert writers.link_echoes(fresh, w, show) == []
    assert writers.link_echoes(_link(QUIET, "x y z"), w, show, part="close") == []      # the goodbye is its own
    assert writers.link_echoes(_link(QUIET, "x y z"), w, schedule.get("late")) == []    # Coastwide's only


def test_the_prompt_names_the_last_openings_and_captions_as_off_limits():
    w = world_mod.seed()
    _aired(w, QUIET, "Coastwide: The Harbour at First Light")
    user = writers.build_prompt(T.links, w, target_s=45, show=schedule.get("magazine"))[1]
    assert "begins with other words and another idea" in user and "(caption: Coastwide: The Harbour at First Light)" in user
    assert w.archive[-1]["caption"] == "Coastwide: The Harbour at First Light"


def test_asked_again_the_fresher_link_stands(monkeypatch):
    w = world_mod.seed()
    _aired(w, QUIET, "Coastwide: The Harbour at First Light")
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        if len(asked) == 1:
            return _link(QUIET, "Coastwide: Harbour at First Light")
        return _link("Pat, I've found out why the Town Hall clock runs fast.", "Coastwide: The Fast Clock")
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=60, type=T.links, show="magazine", target_s=45)
    writers.script_segment(seg, w)
    assert len(asked) == 2 and "NOT LIKE THE LAST LINKS" in asked[1]
    assert seg.lines[0].text.startswith("Pat, I've found out")


def test_each_lap_has_one_fact_from_clive_and_the_other_links_have_angles_of_their_own():
    show = schedule.get("magazine")
    n = len(show.pattern)
    middle = [p for p in range(show.loop_from, n) if schedule.as_item(show.pattern[p]).type is T.links]
    assert len(middle) == 3
    laps = n - show.loop_from
    for lap in range(3):
        briefs = [show.item(p + lap * laps if lap else p).brief for p in middle]
        assert sum("Clive's odd fact" in b for b in briefs) == 1, briefs
        assert len(set(briefs)) == 3
    every = {show.item(p + lap * laps if lap else p).brief for p in middle for lap in range(3)}
    assert len(every) == 7                                   # nine links an evening, seven angles: the fact three times


def test_no_two_of_clives_facts_come_one_after_the_other():
    """The replay of 2026-11-23: the last link of one lap and the first of the next were both his fact."""
    show = schedule.get("magazine")
    n, laps = len(show.pattern), len(show.pattern) - show.loop_from
    briefs = [show.item(p).brief or "" for p in range(n + 2 * laps) if show.item(p).type is T.links
              and show.item(p).part != "open"]
    facts = ["odd fact" in b for b in briefs]
    assert sum(facts) == 4 and not any(a and b for a, b in zip(facts, facts[1:])), briefs
