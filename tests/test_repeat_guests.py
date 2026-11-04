"""A guest is on a show once a day: on 2026-11-03 Coastwide interviewed the mayor three times in an hour, every
19 slots, because the writers' list of the last eight guests had forgotten her each time. The model is
stubbed: no network."""
from __future__ import annotations

from newsroom import llm, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def test_guests_today_are_this_shows_and_todays():
    w = world_mod.seed()
    w.record_aired("interview", "Mayor on frost", None, "...", show="magazine", guest="Helen Strand", aired=False)
    w.record_aired("interview", "Mayor again", None, "...", show="magazine", guest="helen strand")
    w.record_aired("interview", "Mayor at breakfast", None, "...", show="breakfast", guest="Jasper Fowle")
    w.record_aired("vox_pop", "Chips", None, "...", show="magazine")
    w.archive.append({"date": "2020-01-01", "type": "interview", "show": "magazine", "guest": "Ruth Ellery"})
    assert w.guests_today("magazine") == ["Helen Strand"]


def test_a_guest_already_on_the_show_today_is_not_booked_again(monkeypatch):
    w = world_mod.seed()
    w.record_aired("interview", "Mayor Helen Strand, off duty, on frost", None, "...", show="magazine",
                   guest="Helen Strand", aired=False)
    monkeypatch.setattr(writers, "_recent_guests", writers.deque(maxlen=8))    # she has dropped off it
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        name = "Helen Strand" if len(asked) == 1 else "Ellie Marr"
        return schema.model_validate({
            "headline": "Frost on the quay", "lower_third": "Coastwide", "guest_name": name,
            "guest_role": "a guest", "guest_gender": "f",
            "lines": [{"speaker": "mag_a", "text": "Cold one?"}, {"speaker": "guest", "text": "Freezing."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=91, type=T.interview, show="magazine", target_s=90)
    writers.script_segment(seg, w)
    assert "RECENT GUESTS (book someone else): Helen Strand" in asked[0]
    assert len(asked) == 2 and "NOT Helen Strand" in asked[1]
    assert w.guests_today("magazine") == ["Helen Strand", "Ellie Marr"]
