"""Model-planned running orders (rundown.py): Coastwide and The Last Ferry get a theme and a subject per item,
booked before the show, kept to the slots and the people offered, taken once each, and only for the ordinary
version of the show. The model is stubbed: no network."""
from __future__ import annotations

import time

import pytest

from newsroom import rundown, schedule, world as world_mod, writers
from newsroom.buffer import Buffer
from newsroom.models import PlannedSlot, RunningOrder, SegmentType as T
from newsroom.producer import Producer


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


@pytest.fixture
def evening(monkeypatch):
    monkeypatch.setattr(schedule, "_offset_s", 0.0)
    monkeypatch.setenv("NEWSROOM_SPECIAL_NIGHT", "0")
    monkeypatch.setenv("NEWSROOM_RUNDOWN", "1")
    monkeypatch.setenv("NEWSROOM_SPECIAL_DAY", "0")
    monkeypatch.setattr(schedule.council, "council_night", lambda d: False)
    yield


def _town():
    w = world_mod.seed()
    for name, role in (("Bernard Moss", "sailmaker, Harbour Row"), ("Ivy Marchetti", "Harbourmaster")):
        w.ensure_person(name, role)
    return w


def _stub(monkeypatch, reply):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, system, user))
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(rundown.llm, "complete_json", complete_json)
    return seen


def test_the_slots_are_the_planned_types_with_their_angles():
    mag = rundown.slots(schedule.SHOWS["magazine"], 3600)
    assert {s["type"] for s in mag} == {"interview", "feature", "consumer", "vox_pop"}
    assert mag[0]["angle"] and all(s["part"] in ("", "couch") for s in mag)
    vox = [s["angle"] for s in mag if s["type"] == "vox_pop"]
    assert vox[0] == schedule.SHOWS["magazine"].briefs[T.vox_pop][0] and vox[1] != vox[0]   # in turn, as the producer
    late = rundown.slots(schedule.SHOWS["late"], 3600)
    assert any(s["part"] == "couch" for s in late) and not any(s["part"] == "cont" for s in late)


def test_due_before_the_show_once_and_never_on_its_special_night(evening, monkeypatch):
    w = _town()
    assert rundown.due(w, _at(17, 45)) == "magazine"          # 75 minutes before Coastwide
    assert rundown.due(w, _at(17, 0)) is None                 # too early
    assert rundown.due(w, _at(21, 0)) == "late"
    w.rundowns = [{"date": w.last_date, "show": "magazine", "title": "COASTWIDE", "theme": "", "slots": {}, "taken": []}]
    assert rundown.due(w, _at(17, 45)) is None                # planned already today
    w.rundowns = []
    monkeypatch.setenv("NEWSROOM_SPECIAL_NIGHT", "1")        # Coastwide at the Bonfire: its own order
    assert rundown.due(w, _at(17, 45)) is None


def test_a_plan_keeps_to_the_slots_and_the_people_offered(evening, monkeypatch):
    w = _town()
    first = rundown.slots(schedule.SHOWS["magazine"], 3600)
    iv = [s["pos"] for s in first if s["type"] == "interview"]
    feat = next(s["pos"] for s in first if s["type"] == "feature")
    seen = _stub(monkeypatch, RunningOrder(theme="the first frost", slots=[
        PlannedSlot(slot=iv[0], subject="Bernard Moss on fifty years of sails", guest="bernard moss"),
        PlannedSlot(slot=iv[1], subject="the harbourmaster's log", guest="Bernard Moss"),     # nobody twice
        PlannedSlot(slot=iv[2], subject="a stranger", guest="Nobody Known"),                  # not offered
        PlannedSlot(slot=feat, subject="the choir's rehearsal", guest="Ivy Marchetti"),        # a feature: no guest
        PlannedSlot(slot=999, subject="a slot that isn't there"),
    ]))
    e = rundown.commission(w, "magazine", _at(17, 45))
    task, system, user = seen[0]
    assert task == "rundown" and "Coastwide" in system and "SLOTS" in user and "Bernard Moss, sailmaker" in user
    assert e["theme"] == "the first frost" and set(e["slots"]) == {str(iv[0]), str(iv[1]), str(iv[2]), str(feat)}
    assert e["slots"][str(iv[0])]["guest"] == "Bernard Moss"                  # the exact name, whatever the case
    assert [e["slots"][str(p)]["guest"] for p in (iv[1], iv[2], feat)] == ["", "", ""]
    assert rundown.booked(w, "magazine") is e


def test_a_failed_plan_is_recorded_empty_and_the_fixed_order_runs(evening, monkeypatch):
    w = _town()
    _stub(monkeypatch, rundown.llm.LLMError("down"))
    e = rundown.commission(w, "magazine", _at(17, 45))
    assert e["slots"] == {} and e["theme"] == "" and rundown.due(w, _at(17, 50)) is None   # not asked again
    show = schedule.SHOWS["magazine"]
    assert rundown.take(w, show, 3) is None and rundown.for_prompt(w, show, T.links, None) == ""


def _planned(w):
    w.rundowns = [{"date": w.last_date, "show": "magazine", "title": schedule.SHOWS["magazine"].title,
                   "theme": "the first frost", "taken": [],
                   "slots": {"3": {"type": "interview", "subject": "Bernard Moss on fifty years of sails",
                                   "guest": "Bernard Moss"}}}]


def test_a_slot_is_taken_once_and_only_for_the_ordinary_show(evening):
    w = _town()
    _planned(w)
    show = schedule.SHOWS["magazine"]
    assert rundown.take(w, show, 3)["guest"] == "Bernard Moss"
    assert rundown.take(w, show, 3) is None                   # written already (a restart starts the order again)
    assert rundown.take(w, show, 4) is None and rundown.take(w, show, None) is None
    _planned(w)
    assert rundown.take(w, schedule.BONFIRE, 3) is None and rundown.theme(w, schedule.BONFIRE) == ""


def test_the_writer_is_told_the_subject_the_guest_and_the_theme(evening):
    w = _town()
    _planned(w)
    show = schedule.SHOWS["magazine"]
    slot = rundown.take(w, show, 3)
    _, user = writers.build_prompt(T.interview, w, target_s=120, show=show, brief="a resident with a hobby",
                                   work={"planned": slot}, at_ts=_at(19, 10))
    assert "TONIGHT'S RUNNING ORDER has this item as: Bernard Moss on fifty years of sails." in user
    assert "THE GUEST, booked for it: Bernard Moss, sailmaker, Harbour Row. Use exactly this name" in user
    assert "TONIGHT'S THEME" not in user                      # the links carry the theme, not the guests
    _, links = writers.build_prompt(T.links, w, target_s=45, show=show, work={}, at_ts=_at(19, 10))
    assert "TONIGHT'S THEME, for the links to come back to now and then (lightly, not every line): the first frost" in links
    _, news = writers.build_prompt(T.bulletin, w, target_s=60, show=schedule.SHOWS["news"], work={}, at_ts=_at(19, 10))
    assert "TONIGHT'S" not in news


def test_the_producer_tags_each_item_with_its_place_in_the_order(evening):
    p = Producer(Buffer(), 600, start_ts=_at(19, 0))
    segs = [p.plan_one() for _ in range(6)]
    assert [s.show for s in segs] == ["magazine"] * 6
    assert [s.work.get("order_pos") for s in segs] == list(range(6))
