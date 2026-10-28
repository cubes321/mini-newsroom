"""Guests remember: what a chat-show guest said goes on their person, with anything to ask them
next time, and a chat show may book them back for it once that has waited a while. A guest chat
is no longer a news thread (test_light_threads.py); this is where it goes instead.
"""
from newsroom import schedule, world as world_mod, writers
from newsroom.models import GuestLine, InterviewScript, Line, Segment, SegmentType

H = 3600
T0 = 1_790_000_000.0


def _chat(name="Hollis Byrne", memory="a goose calmer than its owner", ask="how Saturday's stadium gig went"):
    return InterviewScript(lines=[GuestLine(speaker="late_host", text="Welcome."),
                                  GuestLine(speaker="guest", text="Thanks, Vincent.")],
                           headline=f"{name} on a goose", lower_third="Comedian", guest_name=name,
                           guest_role="comedian", guest_gender="m", guest_memory=memory, ask_next_time=ask)


def _file(w, seg, script):
    """What script_segment does before it files a script: the segment gets its lines."""
    seg.lines = [Line(speaker=l.speaker, text=l.text) for l in script.lines]
    writers._apply_to_world(seg, script, w)


def _town():
    w = world_mod.seed()
    w.threads = []
    writers._recent_guests.clear()
    return w


def test_a_loose_end_ripens_then_is_forgotten():
    w = _town()
    w.ensure_person("Hollis Byrne", "comedian")
    w.remember_guest("Hollis Byrne", "The Last Ferry", "a goose calmer than its owner", "Saturday's gig", now=T0)
    p = w.person_by_name("Hollis Byrne")
    assert p.memories[-1]["said"] == "a goose calmer than its owner"
    assert w.return_guests(T0 + H) == []
    assert w.return_guests(T0 + 13 * H) == [p]
    assert w.return_guests(T0 + 13 * H, exclude={"Hollis Byrne"}) == []
    assert w.return_guests(T0 + 8 * 86400) == []


def test_a_late_show_chat_is_remembered_on_the_guest():
    w = _town()
    seg = Segment(slot_id=1, type=SegmentType.interview, show="late")
    _file(w, seg, _chat())
    p = w.person_by_name("Hollis Byrne")
    assert p.memories == [{"date": w.last_date, "show": "The Last Ferry", "said": "a goose calmer than its owner"}]
    assert p.loose_ends[0]["ask"] == "how Saturday's stadium gig went"


def test_the_offer_reaches_the_prompt_and_booking_them_uses_up_the_loose_end():
    w = _town()
    _file(w, Segment(slot_id=1, type=SegmentType.interview, show="late"), _chat())
    p = w.person_by_name("Hollis Byrne")
    p.loose_ends[0]["ts"] -= 13 * H                      # it has waited long enough
    writers._recent_guests.clear()
    user = writers.build_prompt(SegmentType.interview, w, target_s=120, show=schedule.get("magazine"),
                                work={"return_guest": "Hollis Byrne"})[1]
    assert "A RETURN VISIT" in user and "Saturday's stadium gig" in user and "a goose calmer" in user
    seg = Segment(slot_id=2, type=SegmentType.interview, show="magazine", work={"return_guest": "Hollis Byrne"})
    _file(w, seg, _chat(memory="the gig went well; the goose came too", ask=None))
    assert p.loose_ends == [] and w.guest_returns["magazine"] == w.last_date
    assert p.memories[-1]["show"] == "Coastwide" and len(p.memories) == 2


def test_someone_else_booked_leaves_the_loose_end_waiting():
    w = _town()
    _file(w, Segment(slot_id=1, type=SegmentType.interview, show="late"), _chat())
    seg = Segment(slot_id=2, type=SegmentType.interview, show="late", work={"return_guest": "Hollis Byrne"})
    _file(w, seg, _chat(name="Sadie Quill", ask=None))
    assert w.person_by_name("Hollis Byrne").loose_ends and "late" not in w.guest_returns
