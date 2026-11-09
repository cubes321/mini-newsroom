"""The council's promises (promises.py): a carried motion's what-follows is kept, the story desk gives the
verdict, The Chamber and SEVENTEXT show them. The model is stubbed: no network."""
from __future__ import annotations

from datetime import date, datetime

from newsroom import chamber, council, desk, promises, teletext, world as world_mod
from newsroom.models import ChamberAgenda, CouncilVote, Motion, PromiseVerdict, StoryPlan, ThreadUpdate

NAMES = [name for name, *_ in council.COUNCILLORS]
MEETING = date(2026, 11, 5)                                     # a Thursday, full council


def _town():
    w = world_mod.seed()
    w.threads, w.last_date = [], MEETING.isoformat()
    for title in ("Harbour wall tender", "Second fire engine", "Christmas lights cherry-picker", "Market winter timetable"):
        w.thread(w.update_thread(None, title, "so far")).next_development = "Full council decides on Thursday"
    return w


def _motion(tid, ayes, then):
    votes = [CouncilVote(councillor=n, vote="for" if i < ayes else "against", why="because") for i, n in enumerate(NAMES)]
    return Motion(thread_id=tid, motion=f"That the council settles {tid}", mover=NAMES[0], votes=votes,
                  if_carried=then, if_lost="It goes back to committee.", public="")


def _meeting(w, monkeypatch):
    """Four motions booked, the first three carried, and every vote taken."""
    ids = [t.id for t in chamber.candidates(w)]
    agenda = ChamberAgenda(motions=[
        _motion(ids[0], 5, "The tender is awarded by Friday 13 November."),
        _motion(ids[1], 4, "The budget committee names a date by the 28th."),
        _motion(ids[2], 6, "Officers will look into hiring one."),
        _motion(ids[3], 1, "The later hours start on Monday.")])
    monkeypatch.setattr(chamber.llm, "complete_json", lambda *a, **k: agenda)
    chamber.commission(w)
    for i in range(4):
        chamber.settle(w, i)
    return ids


def test_a_promise_falls_due_on_the_day_its_own_words_give():
    for said, due in (("The tender is awarded by Friday 13 November.", date(2026, 11, 13)),
                      ("Officers report back to full council on Thursday 19 November.", date(2026, 11, 19)),
                      ("The committee names a date by the 28th.", date(2026, 11, 28)),
                      ("The barriers go up on the 3rd.", date(2026, 12, 3)),
                      ("The later hours start on Monday.", date(2026, 11, 9)),
                      ("Work begins on Thursday.", date(2026, 11, 12)),            # the next one, not today
                      ("It is settled on 4 January.", date(2027, 1, 4)),
                      ("Officers will look into hiring one.", date(2026, 11, 19)),  # undated: the next full council
                      ("It is done on 30 February.", date(2026, 11, 19))):
        assert promises.due_date(said, MEETING) == due, said


def test_a_carried_motion_leaves_a_promise_and_a_lost_one_doesnt(monkeypatch):
    w = _town()
    ids = _meeting(w, monkeypatch)
    ps = promises.open_(w)
    assert [(p["thread_id"], p["due"]) for p in ps] == [
        (ids[0], "2026-11-13"), (ids[2], "2026-11-19"), (ids[1], "2026-11-28")]         # the soonest due first
    assert ps[0]["text"] == "The tender is awarded by Friday 13 November." and ps[0]["made"] == "2026-11-05"
    assert promises.tally(w) == {"open": 3, "kept": 0, "broken": 0, "lapsed": 0}
    chamber.settle(w, 0)                                         # a vote is filed once
    assert len(promises.open_(w)) == 3
    back = world_mod._from_dict(world_mod._to_dict(w))           # and they are saved with the town
    assert [p["id"] for p in promises.open_(back)] == [p["id"] for p in ps]


def test_the_desk_sees_this_rounds_promises_and_gives_the_verdict(monkeypatch):
    w = _town()
    ids = _meeting(w, monkeypatch)
    w.last_date = "2026-11-15"                                   # two days past the tender's day
    todo = desk.batch(w)
    mine = {p["thread_id"]: p for p in promises.open_(w)}
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append(user)
        return StoryPlan(updates=[ThreadUpdate(thread_id=t.id, phase="developing", next_development="On.") for t in todo],
                         promises=[PromiseVerdict(id=mine[ids[0]]["id"], state="broken", note="No tender: the bids came in over."),
                                   PromiseVerdict(id="p999", state="kept")])
    monkeypatch.setattr(desk.llm, "complete_json", complete_json)
    assert desk.plan(w) is not None
    assert "COUNCIL PROMISES" in seen[0] and "OVERDUE by 2 days (was due Friday 13 November)" in seen[0]
    assert f"[{mine[ids[2]]['id']}]" in seen[0] and "due Thursday 19 November" in seen[0]
    # The fire engine's story waits in the running-stories pool for its day, the 28th: its promise comes
    # up with it, when the desk plans it again.
    assert f"[{mine[ids[1]]['id']}]" not in seen[0]
    done = next(p for p in w.promises if p["id"] == mine[ids[0]]["id"])
    assert (done["state"], done["settled"], done["note"]) == ("broken", "2026-11-15", "No tender: the bids came in over.")
    assert promises.tally(w) == {"open": 2, "kept": 0, "broken": 1, "lapsed": 0}


def test_a_verdict_on_a_story_not_planned_this_round_waits(monkeypatch):
    w = _town()
    ids = _meeting(w, monkeypatch)
    p = next(p for p in promises.open_(w) if p["thread_id"] == ids[0])
    plan = StoryPlan(promises=[PromiseVerdict(id=p["id"], state="kept", note="Awarded.")])
    desk.apply(w, plan, only={ids[1]})
    assert p["state"] == "open"
    assert "COUNCIL PROMISES" not in promises.for_desk(w, MEETING, only={"t-none"})
    desk.apply(w, plan, only={ids[0]})
    assert p["state"] == "kept" and p["note"] == "Awarded."


def test_a_promise_follows_a_merged_story_and_lapses_with_a_closed_one(monkeypatch):
    w = _town()
    ids = _meeting(w, monkeypatch)
    by = {p["thread_id"]: p for p in promises.open_(w)}
    assert w.merge_thread(ids[0], ids[1])                         # the tender's story folds into the fire engine's
    w.thread(ids[2]).phase = "closed"
    assert promises.lapse(w, date(2026, 11, 10)) == 1
    assert by[ids[0]]["thread_id"] == ids[1] and by[ids[0]]["state"] == "open"
    assert by[ids[2]]["state"] == "lapsed" and by[ids[2]]["note"] == "the story ended without it"
    assert promises.lapse(w, date(2026, 12, 30)) == 2             # a month past their days, and nobody asked
    assert promises.open_(w) == []


def test_the_chamber_is_told_what_it_still_owes(monkeypatch):
    w = _town()
    _meeting(w, monkeypatch)
    w.last_date = "2026-11-19"                                    # the next full council
    seen = []
    monkeypatch.setattr(chamber.llm, "complete_json",
                        lambda task, schema, system, user, **kw: seen.append(user) or (_ for _ in ()).throw(chamber.llm.LLMError("down")))
    chamber.commission(w)
    assert "PROMISES THE COUNCIL HAS MADE AND NOT YET KEPT" in seen[0] and "OVERDUE by 6 days" in seen[0]
    assert "due TODAY" in seen[0] and "PROMISES THE COUNCIL HAS MADE" in chamber.for_prompt(w)


def test_seventext_has_a_council_watch_page(monkeypatch):
    w = _town()
    ids = _meeting(w, monkeypatch)
    first = next(p for p in promises.open_(w) if p["thread_id"] == ids[0])
    promises.settle(w, next(p for p in promises.open_(w) if p["thread_id"] == ids[2])["id"], "kept", "Hired.")
    page = next(p for p in teletext.pages(w, datetime(2026, 11, 15, 2, 14)) if p["num"] == 175)
    said = [r.get("t", "") for r in page["rows"]]
    assert "Promised at full council: 1 kept," in said and "0 broken, 2 still to come." in said
    assert said.index("OVERDUE since Fri 13 Nov") < said.index("DUE Sat 28 Nov") < said.index("KEPT")
    assert first["text"][:30] in " ".join(said)
    assert teletext.height(page["rows"]) <= len(teletext.BODY)
    empty = next(p for p in teletext.pages(world_mod.seed(), datetime(2026, 11, 15, 2, 14)) if p["num"] == 175)
    assert any("Nothing promised yet" in r.get("t", "") for r in empty["rows"])
