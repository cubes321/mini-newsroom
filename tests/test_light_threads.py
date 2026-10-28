"""The light shows follow stories up but never open one: on 2026-10-27 every Last Ferry and
Coastwide guest chat opened a news thread (44 of 108 open). The news still opens them, and
breaking news does whatever is on.

`_apply_to_world` with built scripts: the template path never opens threads, so it can't show this.
"""
from newsroom import world as world_mod, writers
from newsroom.models import BulletinScript, GuestLine, InterviewScript, LiveLine, Segment, SegmentType


def _chat(thread_id=None):
    return InterviewScript(lines=[GuestLine(speaker="late_host", text="Welcome."),
                                  GuestLine(speaker="guest", text="Thank you, Vincent.")],
                           headline="Priya Anand on a cat and a bookshop", lower_third="Night nurse",
                           guest_name="Priya Anand", guest_role="night nurse", guest_gender="f",
                           thread_id=thread_id, thread_status="still going" if thread_id else None)


def _town():
    w = world_mod.seed()
    w.threads = []
    return w


def test_a_late_show_guest_opens_no_thread_but_may_follow_one_up():
    w = _town()
    seg = Segment(slot_id=1, type=SegmentType.interview, show="late")
    writers._apply_to_world(seg, _chat(), w)
    assert seg.thread_id is None and w.threads == []
    tid = w.update_thread(None, "Second fire engine", "costing due")
    seg = Segment(slot_id=2, type=SegmentType.interview, show="late")
    writers._apply_to_world(seg, _chat(tid), w)
    assert seg.thread_id == tid and w.thread(tid).mentions == 2


def test_the_news_still_opens_threads_and_breaking_news_does_on_any_show():
    w = _town()
    seg = Segment(slot_id=1, type=SegmentType.interview, show="news")
    writers._apply_to_world(seg, _chat(), w)
    assert seg.thread_id is not None
    tip = BulletinScript(lines=[LiveLine(speaker="anchor", text="A fire on the quay.")],
                         headline="Fire on the quay", lower_third="Breaking")
    seg = Segment(slot_id=2, type=SegmentType.breaking, show="late")
    writers._apply_to_world(seg, tip, w)
    assert seg.thread_id is not None and len(w.threads) == 2
