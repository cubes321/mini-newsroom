"""The last of the 2026-11-22 night's review, fixed on 2026-11-23 and tested on the night's own lines: the tide's state
and the prompt's example, a weekday's note, the weekend briefs, the letter and the theme, a guest's part one, The
Panel's go-back question, the over-used resting, the history once, earlier programmes, Morning Tide's same story, new
guests' worn first names, a known person's job, a loose end's weekday, the "twelve-oh-three" clock and Who Said That.
No network."""
from __future__ import annotations

import time
from datetime import date, datetime
from types import SimpleNamespace as NS

from newsroom import panel, rundown, schedule, special, tides, world as world_mod, writers
from newsroom.buffer import Buffer
from newsroom.models import Segment, SegmentType as T
from newsroom.producer import Producer, _WEEKEND

SUN = date(2026, 11, 22)


def test_the_tide_prompt_has_todays_example_and_which_way_it_is_going():
    """The fixed example "twenty-five to five this afternoon" was Saturday's 16:35; Sunday's high was 17:25."""
    p = tides.for_prompt(SUN, now=datetime(2026, 11, 22, 21, 50))
    assert "twenty-five to five" not in p and "(\"five o'clock this morning\")" in p
    assert "RIGHT NOW the tide is falling" in p and "(23:38)" in p.split("RIGHT NOW the tide")[1]
    assert "rising" in tides.tide_now(datetime(2026, 11, 22, 13, 0))
    assert "on the turn" in tides.tide_now(datetime(2026, 11, 22, 17, 40))


def test_the_tide_said_the_wrong_way_round():
    """The Last Ferry, while it ebbed to the 23:38 low (2026-11-22)."""
    late = datetime(2026, 11, 22, 22, 55)
    assert tides.state_slips(["It's twenty-five past ten and the tide's still making, so the water's pushing up."],
                             datetime(2026, 11, 22, 22, 27))
    assert tides.state_slips(["It's gone eleven on the quay, and the tide is very high against the steps."], late)
    assert tides.state_slips(["The tide still runs high against the wall."], late)
    for fine in ("The tide is going out now.", "High water was at twenty-five past five.",
                 "You learn to tell a rising tide from a rising wind by ear.", "Is the tide coming in?",
                 "Tomorrow the tide is high at ten to six."):
        assert not tides.state_slips([fine], late), fine
    assert not tides.state_slips(["The tide is making nicely."], datetime(2026, 11, 22, 13, 0))   # it is


def test_a_time_in_the_sentence_after_the_tide_is_checked_too():
    """The second ask moved the tide into a sentence of its own and kept the wrong time."""
    at = datetime(2026, 11, 22, 22, 0)
    assert tides.clock_slips(["The tide is making a fine show tonight. It came up to five point four metres at "
                              "twenty-five to five this afternoon."], at) == ["twenty-five to five"]
    assert not tides.clock_slips(["Ned, you've no sense of the tide. I spotted the blue at two miles, Sheila, at "
                                  "four in the afternoon."], at)


def test_every_day_has_its_note():
    ts = lambda d, h=6: time.mktime((2026, 11, d, h, 7, 0, 0, 0, -1))        # noqa: E731
    assert "weekend is over" in schedule.day_note(ts(23))
    assert "weekend starts tomorrow" in schedule.day_note(ts(27))
    assert "about ten in the morning" in schedule.day_note(ts(22, 23))       # not "open until ten tonight"


def test_the_weekend_briefs_wait_for_the_end_of_the_week():
    """Monday's Morning Tide was given "the weekend ahead" and said "the weekend is nearly here"."""
    assert _WEEKEND.search("the weekend ahead: walks, the tide, the sport")
    assert not _WEEKEND.search("the school run on a weekday (at the weekend: who is about)")

    def sofa_briefs(day: int) -> list[str]:
        p = Producer(Buffer(), 600, start_ts=time.mktime((2026, 11, day, 6, 0, 30, 0, 0, -1)))
        out = []
        while len(out) < 60:
            seg = p.plan_one()
            if seg.show != "breakfast":
                break
            out.append(seg.brief or "")
        return out
    assert not any("weekend ahead" in b for b in sofa_briefs(23))            # Monday
    assert any("weekend ahead" in b for b in sofa_briefs(27)) or not any(   # Friday, if the hour reaches it
        "the weekend ahead" in b for b in schedule.SHOWS["breakfast"].briefs.get(T.sofa, ()))


def test_the_day_and_greeting_are_when_it_airs(monkeypatch):
    """An item written at 23:56 to air at 00:04 is Monday's."""
    w = world_mod.seed()
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 22, 23, 56).timestamp())
    user = writers.build_prompt(T.bulletin, w, target_s=40.0, show=schedule.get("overnight"),
                                at_ts=datetime(2026, 11, 23, 0, 4).timestamp())[1]
    assert "Today is Monday 23 November" in user


def test_a_letter_is_off_the_theme_and_sees_what_the_letters_asked():
    w = world_mod.seed()
    show = schedule.get("late")
    letter = "a letter from a viewer, read out and answered"
    w.rundowns = [{"date": w.last_date, "show": "late", "title": show.title, "theme": "The town after dark",
                   "slots": {}, "taken": []}]
    assert "TONIGHT'S THEME" not in rundown.for_prompt(w, show, T.links, None, letter)
    assert "TONIGHT'S THEME" in rundown.for_prompt(w, show, T.links, None, "the papers")
    w.record_aired("links", "The Hands That Keep the Lights On", None,
                   "A letter from a viewer has come in, and it asks why the town's lights go on without anybody "
                   "switching them.", show="late", brief=letter)
    said = writers._came_round(w, show, T.links, letter)
    assert "asks why the town's lights go on" in said and "nor ask or answer the same thing" in said


def test_a_guests_first_part_knows_they_are_back_after_the_break():
    lt = time.localtime()
    p = Producer(Buffer(), 600, start_ts=time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 22, 0, 30, 0, 0, -1)))
    segs = []
    while not segs or segs[-1].show == "late":
        segs.append(p.plan_one())
    firsts = [s for s in segs if s.type is T.interview and s.part not in ("cont", "couch")]
    assert firsts and all(s.work.get("continues") for s in firsts[:1])
    w = world_mod.seed()
    user = writers.build_prompt(T.interview, w, target_s=300.0, show=schedule.get("late"),
                                at_ts=time.time(), work={"continues": True})[1]
    assert "THIS IS PART ONE" in user and "no thanks for coming in" in user


def test_the_panel_goes_back_to_a_question_not_yet_gone_back_to():
    w = world_mod.seed()
    w.panels = [{"date": w.last_date, "questions": [{"question": f"Question {i}?"} for i in range(1, 5)],
                 "panellists": [{"name": "A", "stance": "a"}]}]
    for brief in ("the first question, {q1}", "the FIRST question, {q1}", "Miles asks the SECOND question, {q2}",
                  "the SECOND question, {q2}", "the THIRD question, {q3}", "the FOURTH question, {q4}"):
        w.record_aired("interview", brief, None, "...", show="panel", brief=brief)
    email = schedule.SHOWS["panel"].briefs[T.interview][1]
    first = panel.brief_for(w, email)
    again = panel.brief_for(w, schedule.SHOWS["panel"].briefs[T.interview][2])
    assert "\"Question 3?\"" in first and "\"Question 4?\"" in again and "Question 1" not in first + again
    assert "Don't give the question a number" in first


def test_the_most_seen_are_not_offered_for_booking():
    """Marjorie Pell was offered to The Last Ferry's running order while its prompt rested her (10 items);
    Ivy Marchetti, the Harbourmaster, was in 26 news items and never rested."""
    w = world_mod.seed()
    marjorie = w.ensure_person("Marjorie Pell", "retired midwife", kind="worthy")
    ivy = w.ensure_person("Ivy Marchetti", "Harbourmaster", kind="official")
    for i in range(7):
        w.record_aired("bulletin", f"M {i}", None, f"Marjorie Pell spoke ({i}).", show="news")
    assert [p.name for p, _ in w.rested_names()] == ["Marjorie Pell"]       # an official only from 12
    for i in range(12):
        w.record_aired("bulletin", f"I {i}", None, f"Ivy Marchetti said ({i}).", show="news")
    assert ivy.name in [p.name for p, _ in w.rested_names()]
    assert marjorie.name not in [p.name for p in rundown._people(w, "late")]
    assert marjorie.name not in [p.name for p in panel._people(w)]


def test_the_history_gives_each_fact_once():
    w = world_mod.seed()
    w.documentaries = [{"date": f"2026-11-{d}", "title": f"Doc {d}", "timeline": [
        {"date": "1871", "event": f"Background: Port Wexley is founded on the Greymouth coast; the harbour and the "
                                  f"{'old ' if d > 20 else ''}cannery grow up with the town."}]} for d in (18, 21, 22)]
    lines = w._history(full=False)
    assert lines.count("1871") == 1 and "Background:" not in lines


def test_a_documentary_sees_earlier_programmes_on_other_threads():
    w = world_mod.seed()
    a = w.update_thread(None, "Lifeboat crew suits fund", "so far")
    b = w.update_thread(None, "Lifeboat fund: suits now or the boat", "so far")
    w.record_aired("special", "Suits for the lifeboat crew", a, "Every one of the lifeboat crew's suits paid for and "
                   "fitted, says the coxswain.")
    w.confirm_aired = getattr(w, "confirm_aired", None)
    for e in w.archive:
        e.pop("aired", None)
    seg = Segment(slot_id=1, type=T.documentary, show="news", target_s=600, thread_id=b,
                  headline="Lifeboat fund: suits now or the boat")
    out = special.earlier_programmes(seg, w)
    assert "EARLIER PROGRAMMES" in out and "paid for and fitted" in out


def test_morning_tide_tells_a_story_once():
    """Miles reported the fire station at 06:09 and the bulletin told it again at 06:27."""
    w = world_mod.seed()
    show = schedule.get("breakfast")
    fire = w.update_thread(None, "Fire Station Makes Its Case for a Second Engine", "so far")
    w.record_aired("field_report", "Fire Station Makes Its Case for a Second Engine", fire, "...", show="breakfast")
    assert writers._same_story_again(fire, w, show, T.bulletin, time.time(),
                                     "Fire Station Pins Its Second Engine Case Inside Bay Door") == fire
    w.record_aired("field_report", "Lifeboat Crew Suits All Fitted; Call-Out Drill Under Eleven Minutes", None, "...",
                   show="breakfast")
    assert writers._same_story_again(None, w, show, T.bulletin, time.time(),
                                     "Lifeboat Crew Suits All Fitted, Drill Under Eleven Minutes") is not None
    assert writers._same_story_again(None, w, show, T.bulletin, time.time(), "Frost on the Harrow Street Stalls") is None
    news = schedule.get("news")                                       # the news still lets a story have two
    w.record_aired("field_report", "Fire Station Makes Its Case for a Second Engine", fire, "...", show="news")
    assert writers._same_story_again(fire, w, news, T.bulletin, time.time(), "Fire Station Pins Its Case") is None


def test_a_new_guest_with_a_worn_first_name():
    w = world_mod.seed()
    for last in ("Penhale", "Hollis", "Carrow"):
        w.ensure_person(f"Ruth {last}", "resident")
        w.record_aired("vox_pop", "View", None, f"Ruth {last} told us.", show="magazine")
    assert w.first_names_worn() == {"Ruth": 3}
    assert writers.worn_names(NS(guest_name="Ruth Adair", lines=[]), w) == [("Ruth Adair", 3)]
    assert writers.worn_names(NS(guest_name="Ruth Hollis", lines=[]), w) == []       # known: keeps her name
    assert writers.worn_names(NS(guest_name="Wenna Treloar", lines=[]), w) == []


def test_a_known_person_given_another_job():
    """Tam Buchanan, a lifeboat coxswain, as "Foot ferry skipper" on Coastwide."""
    w = world_mod.seed()
    w.ensure_person("Tam Buchanan", "Lifeboat coxswain")
    w.ensure_person("Imogen Starling", "author of The Tallow Season")
    assert writers.role_drift(NS(guest_name="Tam Buchanan", guest_role="Foot ferry skipper"), w) == (
        "Tam Buchanan", "Foot ferry skipper", "Lifeboat coxswain")
    for role in ("lifeboat coxswain and knitter", "a guest", "", None):
        assert writers.role_drift(NS(guest_name="Tam Buchanan", guest_role=role), w) is None, role
    assert writers.role_drift(NS(guest_name="Imogen Starling", guest_role="novelist"), w) is None
    assert writers.role_drift(NS(guest_name="Nobody New", guest_role="skipper"), w) is None


def test_given_another_job_twice_the_caption_is_the_towns(monkeypatch):
    """2026-11-25 slot 187: Lorna Pascoe, a sea-swimming club member on record, kept "retired schoolteacher and
    amateur timekeeper" after the second ask, and the lower third showed it at 22:31 and in the 00:16 repeat."""
    from newsroom import llm
    from newsroom.models import GuestLine, InterviewScript

    w = world_mod.seed()
    w.ensure_person("Lorna Pascoe", "sea-swimming club member", gender="f")
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return InterviewScript(
            lines=[GuestLine(speaker="late_host", text="Lorna, you timed the quay wall."),
                   GuestLine(speaker="guest", text="End to end, in the dark, with a stopwatch."),
                   GuestLine(speaker="late_host", text="Lorna Pascoe, thank you.")],
            headline="Lorna Pascoe times the quay wall", lower_third="Stopwatch", guest_name="Lorna Pascoe",
            guest_role="retired schoolteacher and amateur timekeeper", guest_gender="f")
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=187, type=T.interview, show="late", target_s=60)
    writers.script_segment(seg, w)
    assert any("NOT A RETIRED SCHOOLTEACHER" in u for u in asked)
    assert [l.guest_role for l in seg.lines if l.speaker == "guest"] == ["sea-swimming club member"]


def test_a_loose_end_on_a_day_that_hasnt_come():
    """Dev Ramachandran was asked on Saturday whether the rye "sold out on a Monday", and answered on Sunday."""
    ask = "Whether the orange-peel rye finally sold out on a Monday"
    assert writers._day_not_come(ask, "2026-11-21", "2026-11-22") == "Monday"
    assert writers._day_not_come(ask, "2026-11-21", "2026-11-23") is None
    w = world_mod.seed()
    w.last_date = "2026-11-22"
    assert "no Monday has come since" in writers._not_settled(ask, w, "2026-11-21")


def test_twelve_oh_three_is_said_as_people_say_it():
    assert writers.clock_read_out("round the low at twelve-oh-three.") == "round the low at three minutes past twelve."
    for left in ("ring oh one six three two, nine six oh, seven oh seven.", "my eleven-forty is full"):
        assert writers.clock_read_out(left) == left


def test_who_said_that_reaches_back_before_the_bank():
    from entertainment import quiz

    w = world_mod.seed()
    w.last_date = "2026-11-23"
    for i, first in enumerate(("Agnes", "Bernard", "Cyril", "Dora", "Edna", "Fred")):
        p = w.ensure_person(f"{first} Tester", "resident")
        p.memories = [{"date": "2026-11-12" if i > 2 else "2026-11-21", "show": "Coastwide",
                       "said": f"The quay was busy and the tea was strong, number {i}."}]
    booking = NS(general=[], news=[], potluck=[])
    qs = quiz._quotes(w, [{"members": []}, {"members": []}], booking)
    assert sum(q.question.startswith("Who said this") for q in qs) == quiz.PER_ROUND
    assert any("Thursday 12 November" in q.question for q in qs)
