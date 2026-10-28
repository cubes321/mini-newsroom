"""Guest memory follow-ups: the story desk sees the newest loose ends guests left and may make one
news (the guest's loose end is then spoken for), and a writer who books a remembered guest of
their own accord is asked again with what that guest said before.

The model is stubbed: no network.
"""
from newsroom import desk, writers
from newsroom.models import NewThread, Segment, SegmentType, StoryPlan
from test_guest_memory import _chat, _file, _town


def _stub(monkeypatch, module, replies):
    calls = []

    def complete_json(task, schema, system, user, **kw):
        calls.append(user)
        return replies[min(len(calls), len(replies)) - 1]
    monkeypatch.setattr(module.llm, "complete_json", complete_json)
    return calls


def _remembered_town():
    w = _town()
    _file(w, Segment(slot_id=1, type=SegmentType.interview, show="late"), _chat())
    writers._recent_guests.clear()
    return w


def test_the_desk_sees_loose_ends_and_may_make_one_news(monkeypatch):
    w = _remembered_town()
    seeded = NewThread(title="Stadium gig sells out for Saturday", status="Tickets gone in a day.",
                       next_development="Saturday: the gig.", from_guest="Hollis Byrne")
    calls = _stub(monkeypatch, desk, [StoryPlan(new_threads=[seeded])])
    desk.plan(w)
    assert "LOOSE ENDS" in calls[0] and "how Saturday's stadium gig went" in calls[0]
    hollis = w.person_by_name("Hollis Byrne")
    t = next(t for t in w.threads if t.title.startswith("Stadium gig"))
    assert t.people[0] == hollis.id and hollis.loose_ends == []        # news now, not a chat to come


def test_no_loose_ends_no_section(monkeypatch):
    w = _town()
    calls = _stub(monkeypatch, desk, [StoryPlan()])
    desk.plan(w)
    assert "LOOSE ENDS" not in calls[0] and "DUPLICATES" in calls[0]


def test_a_remembered_guest_booked_unasked_is_written_again_with_what_they_said(monkeypatch):
    w = _remembered_town()
    calls = _stub(monkeypatch, writers, [_chat(memory="the gig went well", ask=None)])
    seg = writers.script_segment(Segment(slot_id=5, type=SegmentType.interview, show="magazine"), w)
    assert len(calls) == 2 and "Hollis Byrne has been on before" in calls[1]
    assert "a goose calmer than its owner" in calls[1] and "how Saturday's stadium gig went" in calls[1]
    hollis = w.person_by_name("Hollis Byrne")
    assert hollis.loose_ends == [] and "magazine" not in w.guest_returns    # asked; the daily offer is untouched
    assert seg.headline == "Hollis Byrne on a goose"


def test_a_new_guest_is_one_call(monkeypatch):
    w = _remembered_town()
    calls = _stub(monkeypatch, writers, [_chat(name="Sadie Quill")])
    writers.script_segment(Segment(slot_id=5, type=SegmentType.interview, show="magazine"), w)
    assert len(calls) == 1 and w.person_by_name("Hollis Byrne").loose_ends
