"""The Panel: Dana Ferris chairs three panellists on four questions, booked in the evening (never
tonight's Inquiry guest), and seated at one long desk. The model is stubbed: no network."""
from __future__ import annotations

import time

from newsroom import panel, schedule, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Line, PanelLineup, PanelQuestion, Panellist, Segment, SegmentType as T
from newsroom.player import Player, View
from newsroom.scenes import _interview_marks


def _town():
    w = world_mod.seed()
    w.threads = []
    for title, n in (("Harbour wall report due Friday", 9), ("Fire station pushes for a second engine", 7),
                     ("Coast road closed to lorries", 5), ("Coffee stall wants a pitch", 4)):
        w.thread(w.update_thread(None, title, "so far")).mentions = n
    w.ensure_person("Bernard Moss", "sailmaker")
    return w


def _stub(monkeypatch, reply):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, user))
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(panel.llm, "complete_json", complete_json)
    return seen


def _lineup(*names):
    return PanelLineup(questions=[PanelQuestion(question=f"Question {i}?") for i in range(4)],
                       panellists=[Panellist(name=n, stance="has a view") for n in names])


def test_a_lineup_is_booked_without_tonights_inquiry_guest(monkeypatch):
    w = _town()
    w.inquiries = [{"date": w.last_date, "thread_id": w.threads[0].id, "guest": "Helen Strand"}]
    seen = _stub(monkeypatch, _lineup("Ivy Marchetti", "Marjorie Pell", "Bernard Moss"))
    entry = panel.commission(w)
    user = seen[0][1]
    assert seen[0][0] == "panel" and "Not tonight: Helen Strand" in user
    assert "  - Helen Strand," not in user.split("PEOPLE:")[1]                # not offered
    assert w.threads[0].title not in user.split("STORIES:")[1].split("PEOPLE:")[0]   # the Inquiry's story isn't
    assert panel.tonight(w) == entry and [p["name"] for p in entry["panellists"]][2] == "Bernard Moss"
    brief = panel.for_prompt(w)
    assert "TONIGHT'S PANEL, chaired by Dana Ferris" in brief and "Ivy Marchetti, Harbourmaster: has a view" in brief
    assert "  1. Question 0?" in brief


def test_a_failed_or_wrong_lineup_gets_a_stand_in(monkeypatch):
    w = _town()
    _stub(monkeypatch, panel.llm.LLMError("down"))
    entry = panel.commission(w)
    kinds = [w.person_by_name(p["name"]).kind for p in entry["panellists"]]
    assert entry["stand_in"] and kinds == ["official", "worthy", "resident"] and len(entry["questions"]) == panel.QUESTIONS
    w.panels = []
    _stub(monkeypatch, _lineup("Ivy Marchetti", "Ivy Marchetti", "Nobody Known"))
    assert panel.commission(w)["stand_in"]


def test_nobody_booked_by_half_eight_the_show_takes_the_stand_in_without_a_call(monkeypatch):
    w = _town()
    seen = _stub(monkeypatch, panel.llm.LLMError("should not be called"))
    assert "TONIGHT'S PANEL" in panel.for_prompt(w) and not seen
    panel.for_prompt(w)
    assert len(w.panels) == 1


def test_it_is_booked_between_half_six_and_half_eight():
    w = _town()
    lt = time.localtime()

    def at(h, m):
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
    assert not panel.should_commission(w, at(18, 0)) and panel.should_commission(w, at(19, 30))
    assert not panel.should_commission(w, at(20, 35))
    assert schedule.show_at(at(20, 40)).id == "panel" and schedule.show_end(at(20, 40)) == at(21, 0)


def test_the_four_sit_at_the_long_desk():
    w = _town()
    pl = Player(Buffer(), w, producer=None, audio=False)
    seg = Segment(slot_id=1, type=T.interview, show="panel", target_s=300, lines=[
        Line(speaker="anchor", text="Ivy?"), Line(speaker="guest", text="Yes.", guest_name="Ivy Marchetti"),
        Line(speaker="guest", text="No.", guest_name="Marjorie Pell"),
        Line(speaker="guest", text="Maybe.", guest_name="Bernard Moss")])
    people = pl._people(seg)
    assert people == [("anchor", None), ("guest", "Ivy Marchetti"), ("guest", "Marjorie Pell"),
                      ("guest", "Bernard Moss")]
    marks = [m for _, _, m in _interview_marks(View(show="panel", set="interview", people=people))]
    assert len(set(marks)) == 4 and marks[0][3] == 1 and all(m[3] == -1 for m in marks[1:])


def test_a_debate_keeps_three_panellists_apart_to_air(monkeypatch):
    import pytest
    from pydantic import ValidationError

    from newsroom import writers
    from newsroom.models import script_schema

    w = _town()
    show = schedule.get("panel")
    schema = script_schema(T.interview, show.cast_for(T.interview), panel=True)
    with pytest.raises(ValidationError):           # a panellist's line must say who is speaking
        schema.model_validate({"headline": "Commit the money now?", "lower_third": "The wall", "lines": [
            {"speaker": "anchor", "text": "Ivy?"}, {"speaker": "guest", "text": "Yes.", "guest_name": "Ivy Marchetti"},
            {"speaker": "guest", "text": "No."}, {"speaker": "anchor", "text": "Thank you."}]})
    script = schema.model_validate({"headline": "Commit the money now?", "lower_third": "The wall", "lines": [
        {"speaker": "anchor", "text": "Ivy?"}, {"speaker": "guest", "text": "Yes.", "guest_name": "Ivy Marchetti"},
        {"speaker": "guest", "text": "No.", "guest_name": "Marjorie Pell"},
        {"speaker": "guest", "text": "Both.", "guest_name": "Bernard Moss"}]})
    monkeypatch.setattr(writers.llm, "complete_json", lambda *a, **k: script)
    seg = Segment(slot_id=3, type=T.interview, show="panel", target_s=300)
    writers.script_segment(seg, w)
    guests = [(l.guest_name, l.guest_role) for l in seg.lines if l.speaker == "guest"]
    assert guests == [("Ivy Marchetti", "Harbourmaster"), ("Marjorie Pell", w.person_by_name("Marjorie Pell").role),
                      ("Bernard Moss", "sailmaker")]
