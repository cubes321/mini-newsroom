"""A looped show doesn't run the same item again: on 2026-11-03 Coastwide's 19-slot loop came round three
times, each lap with the same briefs, and Haiku wrote the same redshank count, roof-survey scam and parking
rise every time, though the prompt listed them as done. The model is stubbed: no network."""
from __future__ import annotations

from newsroom import llm, schedule, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def test_each_lap_of_coastwide_has_its_own_briefs():
    show = schedule.get("magazine")
    n, lap = len(show.pattern), len(show.pattern) - show.loop_from
    for pos in range(show.loop_from, n):
        laps = [show.item(pos + k * lap).brief for k in range(3)]
        if schedule.as_item(show.pattern[pos]).brief:
            assert len(set(laps)) == 3, laps
        assert all(isinstance(b, str) for b in laps)
    vox = [show.item(p) for p in range(n * 3)]
    assert all(isinstance(i.brief, str) for i in vox)


def test_a_plain_brief_is_the_same_every_lap():
    show = schedule.get("late")
    pos = next(p for p in range(show.loop_from, len(show.pattern)) if schedule.as_item(show.pattern[p]).brief)
    lap = len(show.pattern) - show.loop_from
    assert show.item(pos).brief == show.item(pos + lap).brief


def test_a_headline_already_on_the_show_today_is_asked_for_again(monkeypatch):
    w = world_mod.seed()
    show = schedule.get("magazine")
    w.record_aired("feature", "Counting redshank on the estuary, one cold morning at a time", None, "...",
                   show="magazine", aired=False)
    w.record_aired("feature", "Counting redshank on the estuary", None, "...", show="news")   # another show's
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        head = ("Counting redshank on the estuary, one cold morning at a time" if len(asked) == 1
                else "The coast path above Saltby, with the warden")
        return schema.model_validate({
            "headline": head, "lower_third": "Coastwide", "location": "the coast path", "backdrop": "coast_road",
            "lines": [{"speaker": "mag_a", "text": "Off we go."}, {"speaker": "reporter", "text": "Windy up here."},
                      {"speaker": "mag_b", "text": "Hold on to your hat."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=31, type=T.feature, show="magazine", target_s=100, brief="a walk")
    writers.script_segment(seg, w)
    assert len(asked) == 2 and 'NOT "Counting redshank on the estuary, one cold morning at a time"' in asked[1]
    assert seg.headline == "The coast path above Saltby, with the warden"


def test_what_counts_as_a_repeat():
    w = world_mod.seed()
    show = schedule.get("magazine")
    w.record_aired("consumer", "Beware the doorstep roof survey pushing for a deposit", None, "...", show="magazine")
    w.record_aired("weather", "Clear, cold and frosty for the bonfire week", None, "...", show="magazine")
    assert writers._repeated("Beware the doorstep roof survey asking for a deposit", w, show, T.consumer)
    assert not writers._repeated("Roofers on Harbour Row after the gales", w, show, T.feature)
    assert not writers._repeated("Clear, cold and dry for the bonfire week", w, show, T.feature)   # weather aside
    assert not writers._repeated("Beware the doorstep roof survey asking for a deposit", w,
                                 schedule.get("news"), T.interview)                         # a show without the memory
