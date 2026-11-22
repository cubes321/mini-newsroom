"""The shows whose running order wraps (The Last Ferry, Full Time, The Panel, The Inquiry): a brief that comes round
again is told what it made before, a middle item knows the programme isn't over, and The Inquiry's guest leaves.
From the close read of the 2026-11-21 night's scripts. The model is never called."""
from __future__ import annotations

import time

from newsroom import schedule, world as world_mod, writers
from newsroom.models import SegmentType as T


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


def _item(show: str, kind: T, brief: str):
    return next(i for i in map(schedule.as_item, schedule.SHOWS[show].pattern) if i.type is kind and brief in (i.brief or ""))


def test_a_brief_that_comes_round_again_is_told_what_it_made_before():
    """The Last Ferry read the same viewer's letter five times and the same papers four."""
    w = world_mod.seed()
    show = schedule.get("late")
    letter = _item("late", T.links, "a letter from a viewer").brief
    papers = _item("late", T.links, "tomorrow's papers").brief
    first = writers.build_prompt(T.links, w, target_s=40.0, show=show, brief=letter, at_ts=_at(22, 10))[1]
    assert "come round before" not in first
    w.record_aired("links", "Who keeps the small hours? A viewer asks", None, "...", show="late", brief=letter)
    w.record_aired("links", "Thin papers and a crossword", None, "...", show="late", brief=papers)
    w.record_aired("links", "A letter read on another show", None, "...", show="magazine", brief=letter)
    again = writers.build_prompt(T.links, w, target_s=40.0, show=show, brief=letter, at_ts=_at(22, 25))[1]
    item = again.split("THIS ITEM: ")[1].split("\n\n")[0]
    assert 'come round before on today\'s programme, as "Who keeps the small hours? A viewer asks": do NOT write that again' in item
    assert "Thin papers" not in item and "another show" not in item        # its own brief, its own show
    # Coastwide has a memory of its own for an item on the same brief: no second note
    mag = writers.build_prompt(T.links, w, target_s=45.0, show=schedule.get("magazine"), brief=letter, at_ts=_at(19, 20))[1]
    assert "come round before on today's programme" not in mag


def test_a_middle_item_is_told_the_programme_isnt_over():
    """The Panel said "our final round of the evening" at 20:38 and ran six more items."""
    w = world_mod.seed()
    show = schedule.get("panel")
    brief = schedule.SHOWS["panel"].briefs[T.interview][0]
    middle = writers.build_prompt(T.interview, w, target_s=330.0, show=show, brief=brief, at_ts=_at(20, 38))[1]
    assert "About 22 minutes of The Panel are still to come after this: it is not the last item" in middle
    late = writers.build_prompt(T.interview, w, target_s=330.0, show=show, brief=brief, at_ts=_at(20, 57))[1]
    assert "are still to come after this" not in late                       # three minutes left: it may well be last
    close = writers.build_prompt(T.links, w, target_s=40.0, show=show, part="close", brief="Dana thanks the panel",
                                 at_ts=_at(20, 58))[1]
    assert "are still to come after this" not in close


def test_the_inquirys_guest_has_left_once_both_parts_are_written():
    """Gerald Thorne finished at 20:07 and was trailed four more times ("he's back with us now")."""
    w = world_mod.seed()
    show = schedule.get("inquiry")
    other = schedule.SHOWS["inquiry"].briefs[T.interview][0]
    before = writers.build_prompt(T.interview, w, target_s=210.0, show=show, part="other", brief=other, at_ts=_at(20, 5))[1]
    assert "has LEFT the studio" not in before
    part_two = next(i for i in map(schedule.as_item, schedule.SHOWS["inquiry"].pattern) if i.part == "cont").brief
    w.record_aired("interview", "Thorne on the two panels, part two", None, "...", show="inquiry", brief=part_two)
    after = writers.build_prompt(T.interview, w, target_s=210.0, show=show, part="other", brief=other, at_ts=_at(20, 10))[1]
    assert "THE GUEST has given both parts of their interview and has LEFT the studio" in after


def test_the_talk_shows_second_half_isnt_its_first_half_again():
    """Two of The Last Ferry's second halves reran the first nearly line for line, one under the same headline."""
    w = world_mod.seed()
    late, panel = schedule.get("late"), schedule.get("panel")
    w.record_aired("interview", "Imogen Fairlie wants the cannery plaque ordered", None, "...", show="late", brief="x")
    assert writers._repeated("Imogen Fairlie wants the cannery plaque ordered now", w, late, T.interview, "") is not None
    assert writers._repeated("A nurse counts forty-one lamp posts on her way home", w, late, T.interview, "") is None
    # The Panel is one subject all night: its items are alike by nature, and the net leaves them alone
    w.record_aired("interview", "Panel splits on the lifeboat fund", None, "...", show="panel", brief="q")
    assert writers._repeated("Panel splits again on the lifeboat fund", w, panel, T.interview, "r") is None
    email = schedule.SHOWS["panel"].briefs[T.interview][1]
    assert "already debated" in email and "not \"the first question tonight\"" in email


def test_a_title_doesnt_let_the_guest_back_in():
    """The replay of 2026-11-22: The Inquiry's guest, Raymond Doyle, was booked again for its last film as "Chief
    Inspector Raymond Doyle"."""
    assert writers.same_person("Chief Inspector Raymond Doyle", "Raymond Doyle")
    assert writers.same_person("Councillor Gerald Thorne", "Gerald Thorne") and writers.same_person("gerald thorne", "Gerald Thorne")
    assert not writers.same_person("Imogen Strand", "Helen Strand") and not writers.same_person("Raymond Doyle", "Hannah Doyle-Mercer")
    assert not writers.same_person("", "Raymond Doyle") and not writers.same_person(None, None)
