"""The Chamber: full council live every other Thursday (council.py), with four motions booked in the evening
and every councillor's vote (chamber.py). Each vote goes to its story when the debate is written, and the
desk leaves the agenda's stories alone until then. The model is stubbed: no network."""
from __future__ import annotations

import time
from collections import Counter
from datetime import date

from newsroom import chamber, council, desk, inquiry, panel, schedule, world as world_mod, writers
from newsroom.models import ChamberAgenda, CouncilVote, Motion, PanelScript, Segment, SegmentType as T
from test_evening_orders import _half_hour

NAMES = [name for name, *_ in council.COUNCILLORS]


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


def _town():
    w = world_mod.seed()
    w.threads = []
    for title, nxt, n in (("Harbour wall tender", "Full council decides the tender on Thursday", 9),
                          ("Second fire engine", "The budget committee tables a date", 7),
                          ("Christmas lights cherry-picker", "Council hires one by the 28th", 5),
                          ("Market winter timetable", "Traders ask the council for later hours", 4),
                          ("Gull steals a pasty", "", 6)):
        t = w.thread(w.update_thread(None, title, "so far"))
        t.mentions, t.next_development = n, nxt
    return w


def _stub(monkeypatch, reply):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, user))
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(chamber.llm, "complete_json", complete_json)
    return seen


def _motion(tid, ayes, wrong=False):
    votes = [CouncilVote(councillor=n, vote="for" if i < ayes else "against", why="because") for i, n in enumerate(NAMES)]
    if wrong:
        votes[-1] = CouncilVote(councillor="Nobody Known", vote="for", why="?")
    return Motion(thread_id=tid, motion=f"That the council settles {tid}", mover=NAMES[0], votes=votes,
                  if_carried=f"{tid} goes ahead on Monday 9 November.", if_lost=f"{tid} waits for spring.",
                  public="a trader who wants it settled")


def test_full_council_meets_every_other_thursday():
    assert council.meets_on(date(2026, 11, 5)) and council.meets_on(date(2026, 11, 19))
    assert not council.meets_on(date(2026, 11, 12)) and not council.meets_on(date(2026, 10, 22))   # not before the first
    assert council.next_meetings(date(2026, 11, 1)) == [date(2026, 11, 5), date(2026, 11, 19)]
    line = council.calendar_line(date(2026, 11, 5))
    assert "Thursday 5 November (tonight) and Thursday 19 November" in line


def test_on_a_council_night_the_chamber_has_eight_till_nine(monkeypatch):
    w = _town()
    assert schedule.show_at(_at(20, 10)).id == "inquiry"                  # the tests' default: no council night
    monkeypatch.setenv("NEWSROOM_COUNCIL_NIGHT", "1")
    assert schedule.show_at(_at(20, 10)).id == schedule.show_at(_at(20, 40)).id == "chamber"
    assert schedule.show_at(_at(21, 5)).id == "news" and schedule.show_end(_at(20, 10)) == _at(21)
    assert not inquiry.should_commission(w, _at(19, 30)) and not panel.should_commission(w, _at(19, 30))
    assert chamber.should_commission(w, _at(19)) and not chamber.should_commission(w, _at(20, 5))


def test_the_council_is_seated_in_a_town_saved_before_it():
    w = world_mod.seed()
    w.people = [p for p in w.people if p.name not in NAMES]
    w.ensure_person("Gerald Thorne", "Councillor, chair of the council budget committee")   # the desk's resident
    back = world_mod._from_dict(world_mod._to_dict(w))
    seats = council.who(back)
    assert [p.name for p in seats] == NAMES and {p.kind for p in seats} == {"official"}
    assert back.person_by_name("Gerald Thorne").role.startswith("Councillor, Harbour ward")
    head = back.summary_for_prompt()
    assert "Town council: Helen Strand (the mayor) chairs" in head and "Lucy Hammond (Cannery ward)" in head


def test_the_agenda_is_booked_with_every_vote_and_the_result_counted(monkeypatch):
    w = _town()
    ids = [t.id for t in chamber.candidates(w)]
    assert w.thread(ids[-1]).title == "Gull steals a pasty"               # nothing due at council comes last
    seen = _stub(monkeypatch, ChamberAgenda(motions=[_motion(ids[0], 4), _motion(ids[1], 3), _motion(ids[2], 1),
                                                     _motion(ids[3], 6, wrong=True)]))
    entry = chamber.commission(w)
    assert seen[0][0] == "chamber" and "Lucy Hammond, Councillor, Cannery ward" in seen[0][1]
    m = entry["motions"]
    assert (m[0]["for"], m[0]["against"], m[0]["carried"]) == (4, 2, True)
    assert (m[1]["for"], m[1]["against"], m[1]["carried"], m[1]["casting"]) == (3, 3, False, True)   # the chair's vote
    assert m[2]["carried"] is False
    assert [v["councillor"] for v in m[3]["votes"]] == NAMES and m[3]["votes"][-1]["vote"] == "abstain"
    short = _motion(ids[0], 4)
    short.votes = short.votes[:4]                                             # two left out: they abstain
    assert [v["vote"] for v in chamber._votes(w, short.votes)] == ["for"] * 4 + ["abstain"] * 2
    brief = chamber.brief_for(w, "the SECOND motion, {m2}")
    assert f"[{ids[1]}]" in brief and "casting vote goes against" in brief and "LOST" in brief
    assert "From the public: a trader" in brief
    assert chamber.brief_for(w, "{m5}") == "any other business (no vote is taken)"
    assert not {t.id for t in desk.batch(w)} & set(ids[:4])                  # the desk waits for the votes


def test_a_debate_files_its_vote_with_the_story_once(monkeypatch):
    w = _town()
    tid = chamber.candidates(w)[0].id
    _stub(monkeypatch, ChamberAgenda(motions=[_motion(t.id, 5) for t in chamber.candidates(w)[:4]]))
    chamber.commission(w)
    script = PanelScript.model_validate({
        "headline": "Wall tender approved", "lower_third": "Full council", "thread_id": None, "lines": [
            {"speaker": "guest", "text": "Those in favour?", "guest_name": "Helen Strand"},
            {"speaker": "guest", "text": "Aye.", "guest_name": "Gerald Thorne"},
            {"speaker": "guest", "text": "No.", "guest_name": "Lucy Hammond"},
            {"speaker": "guest", "text": "Carried.", "guest_name": "Helen Strand"}]})
    seg = Segment(slot_id=5, type=T.interview, show="chamber", target_s=330, brief="the FIRST motion, {m1}")
    seg.work["motion"] = 0
    writers._apply_to_world(seg, script, w)
    t = w.thread(tid)
    assert seg.thread_id == tid and t.status.startswith("Full council voted 5-1, motion carried")
    assert t.next_development == f"{tid} goes ahead on Monday 9 November." and t.phase == "resolving"
    assert tid in {x.id for x in desk.batch(w)}                               # back on the desk's board
    mentions = t.mentions
    writers._apply_to_world(seg, script, w)                                   # filed again: no second vote
    assert t.mentions == mentions + 1 and t.phase == "resolving"


def test_a_debate_on_the_stock_script_still_files_its_vote(monkeypatch):
    w = _town()
    _stub(monkeypatch, ChamberAgenda(motions=[_motion(t.id, 2) for t in chamber.candidates(w)[:4]]))
    chamber.commission(w)
    tid = chamber.tonight(w)["motions"][1]["thread_id"]
    seg = Segment(slot_id=7, type=T.interview, show="chamber", target_s=330, brief="the SECOND motion, {m2}")
    seg.work["motion"] = 1
    script = writers._template(T.interview, w, writers.random.Random(1), schedule.get("chamber"), "", seg.work)
    writers._apply_to_world(seg, script, w, template=True)
    t = w.thread(tid)
    assert seg.thread_id == tid and t.status.startswith("Full council voted 2-4, motion lost")
    assert t.next_development == f"{tid} waits for spring." and tid not in chamber.on_agenda(w)


def test_a_failed_booking_still_gives_the_hour_its_business(monkeypatch):
    w = _town()
    _stub(monkeypatch, chamber.llm.LLMError("down"))
    entry = chamber.commission(w)
    assert entry["stand_in"] and len(entry["motions"]) == chamber.MOTIONS
    assert all(m["carried"] and m["motion"].startswith("That the council notes") for m in entry["motions"])


def test_the_hour_fills_and_keeps_finding_new_business(monkeypatch):
    monkeypatch.setenv("NEWSROOM_COUNCIL_NIGHT", "1")
    slots = _half_hour("chamber", 20, 0)
    assert slots[-1].part == "close" and len(slots) >= 36, len(slots)
    debates = [s.brief for s in slots if s.type is T.interview and "{m" in s.brief]
    assert [chamber.motion_in(b) for b in debates] == [0, 1, 2, 3]
    items = [(s.type, s.brief) for s in slots if s.type not in (T.bumper, T.ad_break)]
    assert all(a != b for a, b in zip(items, items[1:]))
    assert max(Counter(items).values()) <= 3, Counter(items).most_common(2)
