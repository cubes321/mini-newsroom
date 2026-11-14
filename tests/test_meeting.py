"""The editors' daily meeting (newsroom/meeting.py): Channel 7's senior editor and Channel 8's creative editor, each
on their own model, two rounds and then the minutes; the minutes' actions reach the story desk and Channel 8's
planners. The model is stubbed: no network."""
from __future__ import annotations

import json
import time
from datetime import date, timedelta

import pytest

import entertainment
from entertainment import creative, kettle, soap
from newsroom import desk, llm, meeting, schedule, senior, world as world_mod
from newsroom.models import NewThread, SeniorMemo, StoryPlan, ThreadUpdate
from test_soap import M, _arc, _episode


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


@pytest.fixture
def table(monkeypatch):
    """Both editors at the table with models to ask (the tests run with them off), at ten past four."""
    undo = entertainment.attend()
    monkeypatch.setattr(meeting, "_on", lambda task: True)
    monkeypatch.setattr(schedule, "now", lambda: _at(16, 10))
    yield
    undo()


def _minutes(**kw):
    return meeting.Minutes.model_validate({
        "verdict": "Channel 7 led on the ferry; Channel 8's Tideline went well. Tonight the council vote matters.",
        "actions": [{"to": "news", "about": "t001", "what": "Keep the ferry story off Thursday: Wits is at the Anchor."},
                    {"to": "channel8", "about": "The Kettle's On", "what": "Not Ivy Marchetti on the sofa this week."},
                    {"to": "channel8", "about": "", "what": "No jokes about the ferry while the inquiry is on."},
                    {"to": "channel8", "about": "Marina Row", "what": "Keep the titles under ten seconds."},
                    {"to": "nobody", "about": "", "what": "An action for a seat that isn't there."}],
        "canon": ["The Salting hide is at the north end of the reserve."],
        "offer": {"what": "The Anchor beat the Mermaid on the last dart of Wexley Wits, in front of a full pub.",
                  "people": ["Shirley Vosper"]}, **kw})


def _stub(monkeypatch, minutes=None, fail=()):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, schema, system, user, kw))
        if len(seen) in fail:
            raise llm.LLMError("down")
        if schema is meeting.Turn:
            return meeting.Turn(says=f"Point {len(seen)} from the {task} side.")
        if schema is meeting.Minutes:
            return minutes or _minutes()
        raise AssertionError(f"unexpected call for {schema}")
    monkeypatch.setattr(llm, "complete_json", complete_json)
    return seen


def _hold(w, monkeypatch, **kw):
    seen = _stub(monkeypatch, **kw)
    while meeting.due(w):
        meeting.step(w)
    return seen


# ------------------------------------------------------------------ who is at the table, and when

def test_one_editor_or_a_model_off_is_no_meeting(monkeypatch):
    w = world_mod.seed()
    monkeypatch.setattr(schedule, "now", lambda: _at(16, 10))
    assert set(meeting.SEATS) == {"news"} and not meeting.due(w)             # the models are off, and one seat
    monkeypatch.setattr(meeting, "_on", lambda task: True)
    assert not meeting.due(w)                                                # one editor is not a meeting
    undo = entertainment.attend()
    assert set(meeting.SEATS) == {"news", "channel8"} and meeting.due(w)
    monkeypatch.setattr(meeting, "_on", lambda task: task != creative.TASK)
    assert not meeting.due(w)                                                # the creative editor's model is off
    undo()
    assert set(meeting.SEATS) == {"news"}


def test_the_channel_brings_its_editor_and_takes_them_away():
    undo = entertainment.use()
    assert "channel8" in meeting.SEATS and meeting.SEATS["channel8"].task == creative.TASK
    undo()
    assert set(meeting.SEATS) == {"news"}


def test_it_is_held_from_four_one_call_at_a_time_each_editor_on_their_own_model(table, monkeypatch):
    w = world_mod.seed()
    assert not meeting.due(w, _at(15, 59)) and meeting.due(w, _at(16, 0))
    seen = _stub(monkeypatch)
    for n in range(1, 5):
        assert meeting.step(w) and len(seen) == n and not meeting.today(w)["done"]      # one call a tick
    assert [s[0] for s in seen] == ["senior_editor", creative.TASK, "senior_editor", creative.TASK]
    assert "you open it" in seen[0][3] and "SENIOR EDITOR OF CHANNEL 7: Point 1" in seen[1][3]
    assert "your last word today" not in seen[1][3] and "your last word today" in seen[2][3]
    assert "senior editor of Channel 7" in seen[0][2] and "creative editor of Channel 8" in seen[1][2]
    assert meeting.step(w) and seen[4][0] == meeting.TASK and seen[4][1] is meeting.Minutes
    assert "Point 4 from" in seen[4][3] and "channel8: the creative editor of Channel 8" in seen[4][3]
    m = meeting.today(w)
    assert m["done"] and len(m["turns"]) == 4 and not meeting.due(w)
    assert [a["to"] for a in m["minutes"]["actions"]] == ["news", "channel8", "channel8", "channel8"]   # no stranger
    back = world_mod._from_dict(json.loads(json.dumps(world_mod._to_dict(w))))
    assert back.meetings[-1]["minutes"]["canon"] == ["The Salting hide is at the north end of the reserve."]
    assert "MINUTES" in meeting.show(m) and "to news [t001]" in meeting.show(m)


def test_a_turn_that_fails_is_tried_once_more_later_and_then_the_day_has_no_meeting(table, monkeypatch):
    w = world_mod.seed()
    seen = _stub(monkeypatch, fail=(2, 3))
    assert meeting.step(w) and not meeting.step(w)                           # the creative editor's turn failed
    assert not meeting.due(w)                                                # not at once
    meeting.today(w)["ts"] -= meeting.TRY_GAP_S + 1
    assert meeting.due(w) and not meeting.step(w)                            # and again
    m = meeting.today(w)
    assert m["done"] and m["minutes"] is None and len(m["turns"]) == 1 and not meeting.due(w) and len(seen) == 3
    assert meeting.for_desk(w) == "" and creative.for_planner(w, "kettle") == ""        # and nothing changes
    assert "no minutes" in meeting.show(m)


def test_the_worker_holds_it_after_any_booking_that_is_due(table, monkeypatch):
    from newsroom import adverts, annals, continuity, prune, workers
    from newsroom.buffer import Buffer

    w = world_mod.seed()
    pool = workers.WorkerPool(Buffer(), w)
    for mod, name in ((annals, "tick"), (adverts, "seed_one"), (continuity, "bake_one")):
        monkeypatch.setattr(mod, name, lambda w: False)
    monkeypatch.setattr(prune, "due", lambda: False)
    monkeypatch.setattr(pool, "_buffer_healthy", lambda: True)
    monkeypatch.setattr(desk, "should_plan", lambda w: False)
    monkeypatch.setattr(senior, "should_review", lambda w: False)
    monkeypatch.setattr(workers.world_mod, "save", lambda *a, **k: None)
    seen = _stub(monkeypatch)
    booked = []
    monkeypatch.setattr(workers, "IDLE_JOBS", [(lambda w: not booked, lambda w: booked.append("kettle"))])
    pool._idle_work()
    assert booked == ["kettle"] and not seen                                 # the booking first
    pool._idle_work()
    assert len(seen) == 1 and len(meeting.today(w)["turns"]) == 1            # then the meeting, a turn a tick


# ------------------------------------------------------------------ where the minutes go

def test_the_desk_and_the_senior_editor_read_what_the_news_side_agreed(table, monkeypatch):
    w = world_mod.seed()
    for i in range(3):
        w.seed_thread(f"story {i}", "known so far", "", [])
    _hold(w, monkeypatch)
    todo = desk.batch(w)
    plan = StoryPlan(updates=[ThreadUpdate(thread_id=t.id, phase="developing", next_development="On.") for t in todo])
    seen = []
    monkeypatch.setattr(llm, "complete_json", lambda task, schema, system, user, **kw: (
        seen.append((task, user)), plan if schema is StoryPlan else SeniorMemo(memo="Fine."))[1])
    desk.plan(w)
    user = seen[0][1]
    assert "FROM THE EDITORS' MEETING" in user and "[t001] Keep the ferry story off Thursday" in user
    assert "Not Ivy Marchetti" not in user and "An action for a seat" not in user       # the other side's are theirs
    assert "SETTLED BETWEEN THE CHANNELS" in user and "north end of the reserve" in user
    assert "OFFERED BY CHANNEL 8" in user and "on the last dart" in user and "Shirley Vosper" in user
    senior.review(w)
    assert "Keep the ferry story off Thursday" in seen[1][1] and "OFFERED BY CHANNEL 8" not in seen[1][1]


def test_an_offered_story_goes_once_the_desk_takes_it_or_has_seen_it_enough_or_the_day_ends(table, monkeypatch):
    w = world_mod.seed()
    _hold(w, monkeypatch)
    for _ in range(meeting.OFFER_ROUNDS):
        assert "OFFERED BY CHANNEL 8" in meeting.for_desk(w)
    assert "OFFERED BY CHANNEL 8" not in meeting.for_desk(w) and "FROM THE EDITORS' MEETING" in meeting.for_desk(w)
    m = meeting.today(w)
    m["shown"] = 0
    assert "OFFERED" not in meeting.for_desk(w, offer=False) and m["shown"] == 0        # a dry round, the senior editor
    meeting.offer_seeded(w, [NewThread(title="Harbour dues to rise", status="s", next_development="n")])
    assert not m["taken"]
    meeting.offer_seeded(w, [NewThread(title="Last-dart win packs the Anchor", status="The Anchor beat the Mermaid "
                                       "on the last dart.", next_development="n", people=["Shirley Vosper"])])
    assert m["taken"] and "OFFERED BY CHANNEL 8" not in meeting.for_desk(w)
    m["taken"] = False
    w.last_date = (date.fromisoformat(w.last_date) + timedelta(days=1)).isoformat()
    assert "FROM THE EDITORS' MEETING" in meeting.for_desk(w) and "OFFERED" not in meeting.for_desk(w)   # yesterday's
    w.last_date = (date.fromisoformat(w.last_date) + timedelta(days=1)).isoformat()
    assert meeting.for_desk(w) == ""                                         # two days on, the minutes have lapsed


def test_channel_eights_planners_read_theirs_and_the_drama_only_what_names_it(table, monkeypatch):
    undo = entertainment.use()
    try:
        w = world_mod.seed()
        _hold(w, monkeypatch)
        k = creative.for_planner(w, "kettle")
        assert "FROM THE EDITORS' MEETING" in k and "Not Ivy Marchetti on the sofa" in k
        assert "No jokes about the ferry" in k and "Keep the titles" not in k and "Keep the ferry story" not in k
        assert "north end of the reserve" in k                               # the town's facts, for a show in the town
        t = creative.for_planner(w, "tideline")
        assert "No jokes about the ferry" in t and "Not Ivy Marchetti" not in t
        s = creative.for_planner(w, "marina")
        assert "Keep the titles under ten seconds" in s
        assert "ferry" not in s and "Ivy Marchetti" not in s and "Salting" not in s      # the town is not its business
        seen = []

        def booking(task, schema, system, user, **kw):
            seen.append(user)
            raise llm.LLMError("only the prompt is wanted")
        monkeypatch.setattr(llm, "complete_json", booking)
        kettle.commission(w)
        assert "Not Ivy Marchetti on the sofa this week." in seen[0]
        w.last_date = (date.fromisoformat(w.last_date) + timedelta(days=1)).isoformat()
        assert "Not Ivy Marchetti" in creative.for_planner(w, "kettle")      # a Channel 7 night's meeting, next night
    finally:
        undo()


# ------------------------------------------------------------------ what each editor brings

def test_the_sheet_names_a_resident_on_both_channels(table, monkeypatch):
    w = world_mod.seed()
    ivy = w.person_by_name("Ivy Marchetti")
    w.seed_thread("Harbour dues to rise", "known so far", "", [ivy.id])
    w.kettles.append({"date": w.last_date, "dish": {"cook": "Morwenna Pascoe"}, "sofa": {"name": "Ivy Marchetti"},
                      "expert": {"name": "Sam Lander"}})
    seen = _stub(monkeypatch)
    meeting.step(w)
    sheet = seen[0][3]
    assert "ON BOTH CHANNELS" in sheet and "Ivy Marchetti: in the news (" in sheet
    assert "on The Kettle's On's sofa, tonight" in sheet and "Morwenna Pascoe:" not in sheet.split("ON BOTH CHANNELS")[1]


def test_nothing_of_the_dramas_story_reaches_the_table_or_the_desk(table, monkeypatch):
    undo = entertainment.use()
    try:
        w = world_mod.seed()
        monkeypatch.setattr(creative, "_on", lambda: False)
        monkeypatch.setattr(llm, "complete_json", lambda task, schema, *a, **k: _arc() if schema is soap.Arc else _episode())
        today = w.last_date
        w.last_date = (date.fromisoformat(today) - timedelta(days=2)).isoformat()
        ep = soap.commission(w, M)
        ep["aired"] = True
        creative._apply(w, creative.SHOWS["marina"], w.last_date, creative.Review.model_validate(
            {"mark": "fair", "verdict": "Kerra's secret stood still.", "established": ["Davey's moorings are south"],
             "planted": ["Queenie saw Kerra at The Loft"], "notes": ["Move the secret on."]}), True)
        w.last_date = today
        soap.commission(w, M)                                                # tonight's: planned, not shown
        seen = _hold(w, monkeypatch)
        desk_sees = meeting.for_desk(w)
        said = "\n".join(s[2] + s[3] for s in seen) + desk_sees
        for secret in ("pontoon beat", "secret beat", "beat of scene", "Queenie finds the letter", "Not one word",
                       "Kerra's secret stood still", "Queenie saw Kerra", "Davey's moorings", "Move the secret on"):
            assert secret not in said, secret
        brief = creative.meeting_brief(w)
        assert "Marina Row" in brief and "the town is asking \"Will Queenie tell Davey?\"" in brief    # as town talk has it
        assert brief.count("Will Queenie tell Davey?") == 1                  # the aired one; tonight's is not shown yet
    finally:
        undo()


def test_the_creative_editor_brings_what_its_town_programmes_did_from_the_world_alone(table):
    w = world_mod.seed()
    day = (date.fromisoformat(w.last_date) - timedelta(days=1)).isoformat()
    w.creative = {"log": [{"date": day, "show": "tideline", "title": "Tideline", "kind": "factual", "mark": "good",
                           "verdict": "The roost was worth the wait."}],
                  "ledger": {"tideline": {"facts": [{"date": day, "what": "The starlings roost in the Salting reeds"}]}}}
    w.wildlife = {"episodes": [{"date": day, "aired": True, "meets": [{"name": "Gwen Tarrant"}]}]}
    assert creative.SHOWS == {}                                              # a Channel 7 night: nothing is enrolled
    brief = creative.meeting_brief(w)
    assert "Tideline (" in brief and "good. The roost was worth the wait." in brief
    assert "The starlings roost in the Salting reeds" in brief and "Gwen Tarrant: met on Tideline" in brief
