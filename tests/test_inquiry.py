"""The Inquiry: one story a night, chosen in the evening with Pat's questions and the guest, and the
brief every item in the half hour is written to. The model is stubbed: no network."""
from __future__ import annotations

import time

from newsroom import inquiry, schedule, world as world_mod, writers
from newsroom.models import InquiryCommission, SegmentType as T


def _town():
    w = world_mod.seed()
    w.threads = []
    ids = [w.update_thread(None, title, "so far") for title in (
        "Harbour wall report due Friday, tenders could follow", "Fire station pushes for a second engine",
        "Seafront benches creep closer to the railings", "A gull steals a pasty")]
    for tid, n in zip(ids, (9, 7, 4, 1)):
        w.thread(tid).mentions = n
    w.thread(ids[1]).phase = "peak"
    return w, ids


def _stub(monkeypatch, reply):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, user))
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(inquiry.llm, "complete_json", complete_json)
    return seen


def test_candidates_need_coverage_and_a_rest_and_the_peak_comes_first():
    w, (wall, engine, benches, gull) = _town()
    assert [t.id for t in inquiry.candidates(w)] == [engine, wall, benches]       # not the gull: covered once
    w.inquiries = [{"date": w.last_date, "thread_id": wall}]
    w.documentaries = [{"date": w.last_date, "thread_id": benches}]
    assert [t.id for t in inquiry.candidates(w)] == [engine]


def test_a_commission_is_recorded_and_tonights_brief_is_written_to_it(monkeypatch):
    w, (wall, *_) = _town()
    seen = _stub(monkeypatch, InquiryCommission(
        thread_id=wall, title="Who Pays for the Harbour Wall?", angle="The money has no number.",
        questions=["Where is the forty thousand coming from?", "Why was no sum in the letter?"],
        guest="Helen Strand"))
    entry = inquiry.commission(w)
    assert seen[0][0] == "inquiry" and f"[{wall}]" in seen[0][1]
    assert inquiry.tonight(w) == entry and entry["guest"] == "Helen Strand"
    brief = inquiry.for_prompt(w)
    assert "TONIGHT'S INQUIRY: \"Who Pays for the Harbour Wall?\"" in brief
    assert "1. Where is the forty thousand coming from?" in brief and "THE GUEST who has to answer them" in brief
    assert "THE STORY SO FAR" in brief and f'set thread_id to "{wall}"' in brief


def test_a_failed_or_wrong_commission_gets_the_stand_in(monkeypatch):
    w, (wall, engine, *_) = _town()
    _stub(monkeypatch, inquiry.llm.LLMError("down"))
    assert inquiry.commission(w)["thread_id"] == engine and inquiry.tonight(w)["stand_in"]
    w.inquiries = []
    _stub(monkeypatch, InquiryCommission(thread_id="t999", title="?", angle="?", questions=["a", "b"], guest="X"))
    assert inquiry.commission(w)["thread_id"] == engine


def test_nobody_chose_by_eight_the_show_takes_the_stand_in_without_a_call(monkeypatch):
    w, (wall, engine, *_) = _town()
    seen = _stub(monkeypatch, inquiry.llm.LLMError("should not be called"))
    assert f"[{engine}]" in inquiry.for_prompt(w) and not seen
    assert len(w.inquiries) == 1 and inquiry.for_prompt(w) and len(w.inquiries) == 1      # recorded once


def test_it_is_commissioned_once_between_half_six_and_eight():
    w, _ = _town()
    lt = time.localtime()

    def at(h, m):
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
    assert not inquiry.should_commission(w, at(18, 0)) and inquiry.should_commission(w, at(18, 45))
    assert not inquiry.should_commission(w, at(20, 5))
    w.inquiries = [{"date": w.last_date, "thread_id": None}]
    assert not inquiry.should_commission(w, at(19, 0))


def test_every_item_gets_the_brief_and_builds_on_what_came_before(monkeypatch):
    w, (wall, *_) = _town()
    w.inquiries = [{"date": w.last_date, "thread_id": wall, "title": "Who Pays for the Harbour Wall?",
                    "angle": "a", "questions": ["q1", "q2"], "guest": "Helen Strand"}]
    w.record_aired("feature", "How the wall began to slip", wall, "Miles on the harbour wall, where it began.",
                   show="inquiry")
    show = schedule.get("inquiry")
    user = writers.build_prompt(T.interview, w, target_s=200.0, show=show)[1]
    assert "TONIGHT'S INQUIRY" in user and "ALREADY ESTABLISHED TONIGHT" in user and "How the wall began" in user
    assert "RECENT GUESTS" not in user                     # its guest is the one the story needs
    assert show.cast_for(T.links) == ("mag_a",) and not show.light


def test_the_evening_schedule():
    lt = time.localtime()

    def at(h, m):
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
    assert schedule.show_at(at(20, 10)).id == "inquiry" and schedule.show_end(at(20, 10)) == at(20, 30)
    assert schedule.show_at(at(20, 40)).id == "panel" and schedule.show_at(at(21, 10)).id == "news"
    assert "not answered" in schedule.get("inquiry").closing[0].brief


def test_a_stand_in_title_is_cut_at_a_word():
    title = inquiry._what_next("Harbour wall report due Friday, tenders could follow next spring")
    assert title == "What Next for Harbour wall report due Friday, tenders could follow?" and len(title) <= 70
    assert inquiry._what_next("A gull steals a pasty.") == "What Next for A gull steals a pasty?"
