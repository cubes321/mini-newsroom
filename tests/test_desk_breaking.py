"""The story desk can break a story itself (now and then, never overnight), and after any breaking
story Miles reports from the scene in the next field report, once.

Template scripts only (NEWSROOM_LLM=off, set in conftest): the model calls are stubbed.
"""
import time

import pytest

from newsroom import breaking, desk, schedule, tipline, writers, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import DeskBreaking, FieldReportScript, LiveLine, Segment, SegmentType as T, StoryPlan

TIP = "Smoke is pouring from the chandlery on the quay and the fire crew is on its way."


@pytest.fixture
def daytime(monkeypatch):
    """Ten in the morning on the broadcast clock, and no breaking story for an hour."""
    monkeypatch.setattr(schedule, "_offset_s", 0.0)
    schedule.set_clock("10:00")
    tipline.set_last_breaking(time.time() - 3600)
    yield
    schedule._offset_s = 0.0


def test_the_desk_may_break_a_story_in_the_day_but_not_overnight(daytime):
    w = world_mod.seed()
    assert breaking.desk_may_break(w)
    schedule.set_clock("03:00")
    assert not breaking.desk_may_break(w)


def test_once_a_day_and_never_inside_the_cooldown(daytime):
    w, buf = world_mod.seed(), Buffer()
    seg = breaking.from_desk(w, TIP, buf)
    assert seg.type is T.breaking and seg.work["source"] == breaking.FROM_DESK and seg.work["tip"] == TIP
    assert w.desk_breaking == [w.last_date]
    assert not breaking.desk_may_break(w)                    # the cooldown, and the day's one
    tipline.set_last_breaking(time.time() - 3600)
    assert not breaking.desk_may_break(w)                    # still the day's one
    w.desk_breaking = ["2020-01-01"]
    assert breaking.desk_may_break(w)


def _desk(monkeypatch, mode, reply):
    seen = {}

    def fake(task, schema, system, user):
        seen["user"] = user
        return reply
    monkeypatch.setattr(desk.llm, "complete_json", fake)
    w = world_mod.seed()
    monkeypatch.setattr(w, "seeds_left", lambda now=None: 1)      # at any hour: with nothing to do the desk makes no call
    return desk.plan(w, breaking=mode, dry=True), seen["user"]


def test_the_desk_is_told_when_it_may_break_a_story(monkeypatch):
    p, user = _desk(monkeypatch, "may", StoryPlan(breaking=DeskBreaking(tip=TIP)))
    assert "BREAKING NEWS is rare" in user and p.breaking.tip == TIP
    p, user = _desk(monkeypatch, "now", StoryPlan(breaking=DeskBreaking(tip=TIP)))
    assert "has asked for BREAKING NEWS" in user and p.breaking


def test_a_breaking_item_the_desk_was_not_allowed_is_dropped(monkeypatch):
    p, user = _desk(monkeypatch, "no", StoryPlan(breaking=DeskBreaking(tip=TIP)))
    assert "breaking must be null" in user and p.breaking is None


def _broke(w, ago_s):
    tid = w.update_thread(None, "Chandlery fire on the quay", "smoke reported, crews on the way")
    w.mark_breaking(tid, schedule.now() - ago_s)
    return tid


def test_miles_goes_to_the_scene_once_and_only_while_it_is_fresh():
    w = world_mod.seed()
    tid = _broke(w, 600)
    assert writers.scene_due(w, schedule.now()) == tid
    assert writers.scene_due(w, schedule.now() + 3600) is None          # past the window
    w.record_aired("field_report", "Miles at the chandlery", tid, "...", show="news")
    assert writers.scene_due(w, schedule.now()) is None                 # he has been


def test_the_scene_replaces_the_rota_angle_in_the_field_report_prompt():
    w = world_mod.seed()
    tid = _broke(w, 600)
    show = schedule.get("breakfast")
    _, user = writers.build_prompt(T.field_report, w, target_s=75.0, show=show,
                                   brief="the harbour at first light", work={"scene": tid})
    assert f"FROM THE SCENE: [{tid}]" in user and "broke 10 minutes ago" in user
    assert "THIS ITEM" not in user


def test_after_the_scene_report_the_other_field_reports_leave_the_story_to_the_bulletins():
    w = world_mod.seed()
    tid = _broke(w, 600)
    show = schedule.get("news")
    _, before = writers.build_prompt(T.field_report, w, target_s=90.0, show=show)
    assert "already reported from the scene" not in before
    w.record_aired("field_report", "Miles at the chandlery", tid, "...", show="news")
    _, after = writers.build_prompt(T.field_report, w, target_s=90.0, show=show)
    assert f"already reported from the scene of [{tid}]" in after
    _, later = writers.build_prompt(T.field_report, w, target_s=90.0, show=show, at_ts=schedule.now() + 3 * 3600)
    assert "already reported from the scene" not in later          # the story is no longer breaking


def test_a_field_report_sees_the_last_ones_and_goes_elsewhere():
    w = world_mod.seed()
    show = schedule.get("news")
    _, first = writers.build_prompt(T.field_report, w, target_s=90.0, show=show)
    assert "MILES'S LAST REPORTS" not in first
    tid = w.update_thread(None, "One engine for the whole harbour", "the chief wants a second")
    w.record_aired("field_report", "Fire crew times the far berths", tid, "...", show="news")
    w.record_aired("field_report", "Breakfast at the slipway", None, "...", show="breakfast")   # another show's
    _, user = writers.build_prompt(T.field_report, w, target_s=90.0, show=show)
    block = user.split("MILES'S LAST REPORTS")[1].split("\n\n")[0]
    assert f"Fire crew times the far berths [{tid}]" in block and "slipway" not in block


def test_the_scene_report_is_not_told_to_go_elsewhere():
    w = world_mod.seed()
    tid = _broke(w, 300)
    w.record_aired("field_report", "Fire crew times the far berths", None, "...", show="news")
    _, user = writers.build_prompt(T.field_report, w, target_s=90.0, show=schedule.get("news"), work={"scene": tid})
    assert "FROM THE SCENE" in user and "MILES'S LAST REPORTS" not in user


def test_the_scene_report_is_filed_on_the_breaking_thread(monkeypatch):
    w = world_mod.seed()
    tid = _broke(w, 300)
    reply = FieldReportScript(
        lines=[LiveLine(speaker="anchor", text="Miles is at the quay."),
               LiveLine(speaker="reporter", text="The fire is out; nobody was hurt.")],
        headline="Chandlery fire out, nobody hurt", location="the quay by the chandlery",
        backdrop="harbour", lower_third="Miles Okafor at the quay", thread_id=None,
        thread_status="fire out, cause not known")
    monkeypatch.setattr(writers.llm, "complete_json", lambda *a, **k: reply)
    seg = Segment(slot_id=40, type=T.field_report, show="news", target_s=90.0, nominal_start_ts=schedule.now())
    writers.script_segment(seg, w)
    assert seg.work["scene"] == tid and seg.thread_id == tid
    assert w.thread(tid).status == "fire out, cause not known"
    assert writers.scene_due(w, schedule.now()) is None


def test_a_field_report_that_tells_the_last_one_again_is_sent_to_a_story_the_code_names(monkeypatch):
    """On the 2026-11-21 night "Hake Glut Keeps Fish Quay Busy Into the Night" was written fourteen times running,
    with the same headline three times in MILES'S LAST REPORTS: one item a cycle never makes two of the news's last
    four, so nothing asked again."""
    from newsroom import llm

    w = world_mod.seed()
    hake = w.update_thread(None, "Hake Glut Softens the Quay Price", "boxes stacked on the quay")
    quiet = [w.update_thread(None, title, "so far") for title in (
        "Reading torch comes back cracked", "Dry suits go in for taking in", "Grit bin down to the scraping",
        "A second grey glove on the bollard", "Brass band needs a tuba", "Allotment squash turns orange",
        "Library tin gives up four shillings", "Chess club sets up its boards")]
    for tid in quiet:
        w.thread(tid).next_development = "On Wednesday the next thing happens."
    w.record_aired("field_report", "Hake Glut Keeps Fish Quay Busy Into the Night", hake, "...", show="news")
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        again = "Miles has only just reported that" not in user
        return schema.model_validate({
            "headline": "Hake Glut Keeps Fish Quay Busy Into the Night" if again else "The torch's cracked lens",
            "lower_third": "Fish quay" if again else "Harrow Street", "backdrop": "fish_quay" if again else "market",
            "location": "the fish quay" if again else "Harrow Street", "thread_id": None if again else quiet[0],
            "lines": [{"speaker": "anchor", "text": "Over to Miles."}, {"speaker": "reporter", "text": "Thanks, Dana."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    monkeypatch.setattr(llm, "provider_for", lambda task: "claude_haiku")
    seg = writers.script_segment(Segment(slot_id=9, type=T.field_report, show="news", target_s=90.0), w)
    assert len(asked) == 2 and seg.headline == "The torch's cracked lens" and not seg.fallback
    sent = asked[1].split("NOT ")[-1]
    assert sent.startswith('"Hake Glut Keeps Fish Quay Busy Into the Night": Miles has only just reported that')
    named = [tid for tid in quiet if f"This report is on [{tid}]" in sent]
    assert len(named) == 1 and f'Set thread_id to "{named[0]}"' in sent and hake not in sent.split("This report")[1]
    # a report on a story he hasn't just done is taken as it comes
    asked.clear()
    w2 = world_mod.seed()
    w2.record_aired("field_report", "Fire crew times the far berths", None, "...", show="news")
    writers.script_segment(Segment(slot_id=10, type=T.field_report, show="news", target_s=90.0), w2)
    assert len(asked) == 1
