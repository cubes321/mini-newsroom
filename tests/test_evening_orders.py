"""The Inquiry and The Panel fill their half hours: on 2026-10-30 items came in near half their targets,
both reached a one-item loop ten minutes in, and The Inquiry booked its guest again for "the other side"
and wrote the guest's part two as a fresh interview. The model is stubbed: no network."""
from __future__ import annotations

import time
from collections import Counter

from newsroom import llm, schedule, world as world_mod, writers
from newsroom.buffer import Buffer
from newsroom.models import Segment, SegmentType as T
from newsroom.producer import Producer


def _half_hour(show: str, hh: int, mm: int, run_s: float = 90.0) -> list[Segment]:
    """The show's slots as planned when every item runs `run_s`, as they did on air."""
    lt = time.localtime()
    p = Producer(Buffer(), 600, start_ts=time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 30, 0, 0, -1)))
    out: list[Segment] = []
    while not out or out[-1].show == show:
        seg = p.plan_one()
        if seg.type is not T.bumper:
            p.cursor_ts += run_s - seg.target_s
        out.append(seg)
    return out[:-1]


def test_the_inquiry_guests_part_two_carries_on_part_one_across_the_film_and_vox_pop():
    slots = _half_hour("inquiry", 20, 0)
    one = next(s for s in slots if s.type is T.interview and s.brief.startswith("THE GUEST in the studio"))
    two = next(s for s in slots if s.part == "cont")
    assert [s.type for s in slots if one.slot_id < s.slot_id < two.slot_id] == [T.ad_break, T.feature, T.vox_pop]
    assert two.work["first_part"] == one.slot_id


def test_the_last_ferrys_second_parts_still_follow_their_own_guest():
    lt = time.localtime()
    p = Producer(Buffer(), 600, start_ts=time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 22, 0, 30, 0, 0, -1)))
    hour = [p.plan_one() for _ in range(16)]
    for two in (s for s in hour if s.part == "cont"):
        first = next(s for s in hour if s.slot_id == two.work["first_part"])
        assert first.type is T.interview and first.part == "" and two.slot_id - first.slot_id == 2


def test_a_half_hour_of_short_items_keeps_finding_new_angles():
    for show, hh, mm in (("inquiry", 20, 0), ("panel", 20, 30)):
        slots = _half_hour(show, hh, mm)
        assert slots[-1].part == "close" and len(slots) >= 18, (show, len(slots))
        items = [(s.type, s.brief) for s in slots if s.type not in (T.bumper, T.ad_break)]
        assert all(a != b for a, b in zip(items, items[1:])), show
        assert max(Counter(items).values()) <= 2, (show, Counter(items).most_common(2))


def test_the_inquirys_other_voices_are_never_its_guest(monkeypatch):
    w = world_mod.seed()
    tid = w.update_thread(None, "Harbour wall report due Friday", "so far")
    w.inquiries = [{"date": w.last_date, "thread_id": tid, "title": "Who Pays for the Wall?", "angle": "a",
                    "questions": ["q1", "q2"], "guest": "Ivy Marchetti"}]
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        name = "Ivy Marchetti" if len(asked) == 1 else "Ruth Abney"
        return schema.model_validate({
            "headline": "Who pays for the wall", "lower_third": "The Inquiry", "guest_name": name,
            "guest_role": "crabber", "guest_gender": "f",
            "lines": [{"speaker": "mag_a", "text": "Who pays?"}, {"speaker": "guest", "text": "Not the crabbers."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=40, type=T.interview, show="inquiry", part="other", target_s=210,
                  brief="the other side: a resident or a campaigner who sees it differently from THE GUEST")
    writers.script_segment(seg, w)
    assert len(asked) == 2 and "NOT Ivy Marchetti: they are THE GUEST" in asked[1]
    assert "NOT Ivy Marchetti in this item" in asked[0]                  # told before the first attempt too
    assert writers._last_interview["inquiry"]["name"] == "Ruth Abney"
    assert schedule.get("inquiry").briefs[T.interview][0].startswith("the other side")

    # THE GUEST's own part one is theirs, however recently they were on elsewhere (2026-10-31's scratch run).
    asked.clear()
    monkeypatch.setattr(writers, "_recent_guests", writers.deque(["Ivy Marchetti"], maxlen=8))
    one = Segment(slot_id=41, type=T.interview, show="inquiry", target_s=210,
                  brief="THE GUEST in the studio, part one")
    writers.script_segment(one, w)
    assert len(asked) == 1 and writers._last_interview["inquiry"]["name"] == "Ivy Marchetti"
