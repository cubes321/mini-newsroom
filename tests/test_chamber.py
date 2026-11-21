"""The Chamber: full council live every other Thursday (council.py), with four motions booked in the evening
and every councillor's vote (chamber.py). Each vote goes to its story when the debate is written, and the
desk leaves the agenda's stories alone until then. The model is stubbed: no network."""
from __future__ import annotations

import time
from collections import Counter
from datetime import date, datetime

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


def test_channel_8_on_a_council_night_books_no_sitting_and_no_phone_in(monkeypatch):
    """2026-11-19: a Channel 8 evening on a council night booked The Chamber's agenda and votes at 18:30 for an
    hour it doesn't have; Have Your Say's booking had the same hole for a Channel 8 morning."""
    import entertainment
    from newsroom import phonein
    w = _town()
    monkeypatch.setenv("NEWSROOM_COUNCIL_NIGHT", "1")
    assert chamber.should_commission(w, _at(19)) and phonein.should_commission(w, _at(9))     # Channel 7 books both
    undo = entertainment.use()
    try:
        assert not chamber.should_commission(w, _at(19)) and not phonein.should_commission(w, _at(9))
    finally:
        undo()
    assert chamber.should_commission(w, _at(19))


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
    t = w.thread(tid)
    t.planned_seen = desk.seen(w, t)                 # the desk had planned it as it stood before the booking
    writers._apply_to_world(seg, script, w)
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
    assert script.guest_name == "Helen Strand" and {l.speaker for l in script.lines} == {"guest"}   # not Dana
    assert "2 for, 4 against, 0 abstaining. The motion is lost" in script.lines[-1].text
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
    assert [m["thread_id"] for m in entry["motions"]] == [t.id for t in chamber.candidates(w)[:chamber.MOTIONS]]


def _wider_town():
    """_town, and more open stories than there are candidates, so one is left off the STORIES list."""
    w = _town()
    for i in range(chamber.CANDIDATES):
        w.thread(w.update_thread(None, f"Council report number {i}", "so far")).next_development = "Full council on Thursday"
    w.thread(w.update_thread(None, "Harbourmaster books the wall survey", "so far")).mentions = 26
    return w


def test_any_open_story_can_take_a_motion_not_only_the_listed_ones(monkeypatch):
    """2026-11-19: the agenda's fourth motion took the harbour wall survey, an open story covered 26 times that the
    briefing showed but the eight candidates didn't, and all four motions went to the stand-in."""
    w = _wider_town()
    pool = [t.id for t in chamber.candidates(w)]
    survey = next(t.id for t in w.open_threads() if t.title.startswith("Harbourmaster"))
    assert survey not in pool
    _stub(monkeypatch, ChamberAgenda(motions=[_motion(pool[0], 4), _motion(pool[1], 5), _motion(pool[2], 2),
                                              _motion(survey, 6)]))
    entry = chamber.commission(w)
    assert not entry.get("stand_in") and not any(m.get("stand_in") for m in entry["motions"])
    assert [m["thread_id"] for m in entry["motions"]] == [*pool[:3], survey]
    assert survey in chamber.on_agenda(w)                                     # the desk waits for its vote too


def test_a_motion_that_cant_stand_gives_way_alone(monkeypatch):
    """A made-up story, a finished one and a story twice each lose only their own motion, in its place on the
    agenda, to a stand-in motion on a candidate the agenda doesn't already have."""
    w = _town()
    pool = [t.id for t in chamber.candidates(w)]
    done = w.thread(pool[3])
    done.phase = "closed"
    _stub(monkeypatch, ChamberAgenda(motions=[_motion(pool[0], 4), _motion("t999", 5), _motion(pool[0], 2),
                                              _motion(done.id, 6)]))
    entry = chamber.commission(w)
    m = entry["motions"]
    assert not entry.get("stand_in") and len(m) == chamber.MOTIONS
    assert (m[0]["thread_id"], m[0]["for"], m[0].get("stand_in")) == (pool[0], 4, None)    # the model's, kept
    assert all(x.get("stand_in") and x["motion"].startswith("That the council notes") for x in m[1:])
    spares = [t.id for t in chamber.candidates(w) if t.id != pool[0]]
    assert [x["thread_id"] for x in m[1:]] == spares[:3] and done.id not in [x["thread_id"] for x in m]
    assert len({x["thread_id"] for x in m}) == chamber.MOTIONS


def test_an_agenda_with_nothing_that_stands_is_the_stand_in(monkeypatch):
    w = _town()
    _stub(monkeypatch, ChamberAgenda(motions=[_motion(f"t99{i}", 4) for i in range(4)]))
    entry = chamber.commission(w)
    assert entry["stand_in"] and len(entry["motions"]) == chamber.MOTIONS


def test_the_hour_fills_and_keeps_finding_new_business(monkeypatch):
    monkeypatch.setenv("NEWSROOM_COUNCIL_NIGHT", "1")
    slots = _half_hour("chamber", 20, 0)
    assert slots[-1].part == "close" and len(slots) >= 36, len(slots)
    debates = [s.brief for s in slots if s.type is T.interview and "{m" in s.brief]
    assert [chamber.motion_in(b) for b in debates] == [0, 1, 2, 3]
    items = [(s.type, s.brief) for s in slots if s.type not in (T.bumper, T.ad_break)]
    assert all(a != b for a, b in zip(items, items[1:]))
    assert max(Counter(items).values()) <= 3, Counter(items).most_common(2)


def _on_air(seg, idx):
    from newsroom.buffer import Buffer
    from newsroom.player import Player
    pl = Player(Buffer(), _town(), producer=None, audio=False)
    pl.current, pl.line_idx = seg, idx
    pl.seg_start = pl.line_start = schedule.now() - 0.5
    return pl.view()


def _drawn(monkeypatch, v):
    import pygame
    from newsroom import backdrops, scenes
    drawn, people = [], []
    monkeypatch.setattr(backdrops, "draw", lambda canvas, bid, *a, **k: drawn.append(bid))
    monkeypatch.setattr(scenes, "draw_character", lambda c, x, y, who, *a, **k: people.append((who, x, y)))
    pygame.font.init()
    scenes.render(pygame.Surface(scenes.CANVAS), v, 0.5)
    return drawn, people


def test_dana_talks_from_the_press_seats_and_the_council_debates_in_the_chamber(monkeypatch):
    from newsroom.locations import MARKS
    from newsroom.models import Line
    say = lambda who, name=None: Line(speaker=who, guest_name=name, text="...", duration_s=2.0, mouth_env=[0.5] * 40)
    x, y = MARKS["chamber_press"]["host"][:2]
    link = Segment(slot_id=3, type=T.links, show="chamber", target_s=45, lines=[say("anchor"), say("anchor")])
    for idx in (0, 1):                                            # wide, then the close shot
        drawn, people = _drawn(monkeypatch, _on_air(link, idx))
        assert drawn == ["chamber_press"]
        if idx == 0:
            assert people == [("anchor", x, y)]                  # at the bench, not in the horseshoe
    debate = Segment(slot_id=4, type=T.interview, show="chamber", target_s=330,
                     lines=[say("guest", council.CHAIR), say("guest", NAMES[0])])
    drawn, people = _drawn(monkeypatch, _on_air(debate, 0))
    assert drawn == ["council_chamber"] and ("guest", *MARKS["council_chamber"]["host"][:2]) in people
    from newsroom.player import View
    for odd in ([], [("anchor", None), ("mag_a", None)]):               # nobody, or two presenters: the chamber
        drawn, _ = _drawn(monkeypatch, View(mode="studio", show="chamber", set="interview", people=odd))
        assert drawn == ["council_chamber"], odd


def test_dana_hands_to_miles_from_the_press_seats_not_the_studio_wall(monkeypatch):
    from newsroom.models import Line, VisualCue
    say = lambda who, name=None: Line(speaker=who, guest_name=name, text="...", duration_s=2.0, mouth_env=[0.5] * 40)
    vox = Segment(slot_id=5, type=T.vox_pop, show="chamber", target_s=60,
                  cues=[VisualCue(at_s=0.0, kind="backdrop", payload={"backdrop": "council_chamber"})],
                  lines=[say("anchor"), say("reporter"), say("guest", "Jean Hocking")])
    v = _on_air(vox, 0)
    assert v.mode == "studio" and v.shot != "wall" and v.people == [("anchor", None)]
    assert _drawn(monkeypatch, v)[0] == ["chamber_press"]
    assert _on_air(vox, 1).mode == "field"                       # then Miles in the gallery


def test_a_motions_vote_is_on_screen_only_once_it_has_been_taken(monkeypatch):
    """2026-11-19, the first council night with The Chamber live: "Pool Petition Motion Carried, Officers Report in
    December" was a debate's headline, so it was on the ticker as Helen called the motion. (The banner names whoever is
    speaking, and in the chamber that's always a councillor.) The ticker has the vote once the debate is over."""
    from newsroom.buffer import Buffer
    from newsroom.models import Line
    from newsroom.player import Player

    w = world_mod.seed()
    monkeypatch.setattr(schedule, "now", lambda: _at(20, 1))
    pl = Player(Buffer(), w, producer=None, audio=False)
    lines = [{"speaker": "guest", "guest_name": council.CHAIR, "text": f"Line {i}: the pool petition."} for i in range(4)]
    script = PanelScript(headline="Pool Petition Motion Carried, Officers Report in December",
                         lower_third="Full council: the pool petition", lines=lines)
    seg = Segment(slot_id=88, type=T.interview, show=chamber.SHOW, target_s=150, headline=script.headline,
                  lines=[Line(speaker="guest", guest_name=council.CHAIR, text="Item one.", duration_s=2.0,
                              mouth_env=[0.5] * 40)],
                  cues=writers._cues_for(Segment(slot_id=88, type=T.interview, show=chamber.SHOW), script))
    pl._start(seg, _at(20, 1))
    v = pl.view(_at(20, 1) + 1)
    assert "Carried" not in " ".join(x for x in (v.lower_third or ()) if x)
    assert all(h != seg.headline for _, h in pl.ticker)
    pl._finish(_at(20, 4))
    assert (chamber.SHOW, seg.headline) in pl.ticker


def _met(applied=(True, True)):
    """The 19th's record, as chamber.py keeps it: one motion carried, one lost."""
    return {"date": "2026-11-19", "motions": [
        {"thread_id": "t484", "motion": "That the pool petition goes to officers", "carried": True, "for": 5,
         "against": 1, "applied": applied[0]},
        {"thread_id": "t447", "motion": "That the bowling green is sold", "carried": False, "for": 2, "against": 4,
         "applied": applied[1]}]}


def test_from_eight_on_a_council_night_the_meeting_is_over_and_only_its_votes_are_given():
    """On 2026-11-19 the briefing said "(tonight)" all day: bulletins written up to 23:45 had the council still
    to sit, and one made a result up ("Ferry Rail Costings Sent Back Again", never on the agenda)."""
    day = date(2026, 11, 19)
    at = lambda h, m=0: datetime(2026, 11, 19, h, m).timestamp()  # noqa: E731
    before = council.calendar_line(day, at(19, 30), _met())
    assert before == council.calendar_line(day) and "Thursday 19 November (tonight)" in before
    news = council.calendar_line(day, at(20, 50), _met())            # written in The Chamber's hour, aired after it
    assert "(tonight)" not in news and "MET tonight (Thursday 19 November)" in news and "is OVER" in news
    assert '[t484] "That the pool petition goes to officers" CARRIED 5-1' in news
    assert '[t447] "That the bowling green is sold" LOST 2-4' in news and "nothing else" in news
    assert "It next meets on Thursday 3 December" in news
    late = council.calendar_line(day, at(23, 45), _met(applied=(True, False)))
    assert "t484" in late and "t447" not in late                      # the hour never reached it: not voted on
    unknown = council.calendar_line(day, at(21, 30), None)             # no record: Channel 8's night, a late start
    assert "is OVER" in unknown and "not known here: report no council vote" in unknown
    short = council.calendar_line(day, at(22), _met(), short=True)
    assert short == ("Council: full council met tonight. It next meets on Thursday 3 December, live on The "
                     "Chamber at eight.")
    assert "(tonight)" not in council.calendar_line(date(2026, 11, 20), at(23) + 86400, _met())   # the day after
    assert "meets on Thursday 3 December and" in council.calendar_line(date(2026, 11, 20), at(23) + 86400)


def test_the_briefings_say_the_meeting_is_over_except_to_the_chamber_itself(monkeypatch):
    w = _town()
    w.last_date = "2026-11-19"
    w.chambers = [_met()]
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 19, 20, 50).timestamp())
    for text in (w.summary_for_prompt(), w.summary_for_editor()):
        assert "the meeting is OVER" in text and "CARRIED 5-1" in text and "(tonight)" not in text
    sitting = w.summary_for_prompt(sitting=True)                       # The Chamber's own items: still in session
    assert "Thursday 19 November (tonight)" in sitting and "OVER" not in sitting
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 19, 19, 59).timestamp())
    assert "Thursday 19 November (tonight)" in w.summary_for_prompt()


def _filed(w, brief, headline, kind="interview", people=()):
    """An item of tonight's Chamber as the writer files it."""
    w.archive.append({"date": w.last_date, "type": kind, "headline": headline, "text": "…", "show": "chamber",
                      "brief": brief, "people": list(people)})


def test_the_loops_briefs_take_turns_so_no_item_is_written_twice():
    """On 2026-11-19 the six angles came round with the same words and got the same items: Lucy Hammond's
    Cannery shed question twice, the harbour office accounts twice, the pool petition three times."""
    w = _town()
    w.chambers = [{"date": w.last_date, "motions": [
        {"thread_id": "t1", "title": "Harbour wall tender", "motion": "That the tender is let", "mover": NAMES[0],
         "carried": True, "for": 4, "against": 2, "applied": True, "votes": [], "casting": False},
        {"thread_id": "t2", "title": "Second fire engine", "motion": "That the engine is bought", "mover": NAMES[1],
         "carried": False, "for": 2, "against": 4, "applied": True, "votes": [], "casting": False}]}]
    show = schedule.SHOWS["chamber"]
    vote, ward, aob, story, report, petition = show.briefs[T.interview]
    asked = []
    for brief in (ward, aob, ward, aob, ward, aob, ward):                 # round the table, then round again
        said = chamber.brief_for(w, brief)
        assert "{" not in said
        asked.append(next(n for n in NAMES if n in said))
        _filed(w, brief, f"Question {len(asked)}")
    assert asked == NAMES + NAMES[:1]
    first = chamber.brief_for(w, vote)
    assert "tonight's first vote, on [t1] Harbour wall tender (carried 4-2" in first and "come round before" not in first
    _filed(w, vote, "Tender question")
    second = chamber.brief_for(w, vote)
    assert "tonight's second vote, on [t2] Second fire engine (lost 2-4" in second
    assert 'come round before tonight, as "Tender question": do NOT write that again' in second
    reports = []
    for _ in range(4):
        reports.append(chamber.brief_for(w, report).split(",")[0])
        _filed(w, report, f"Report {len(reports)}")
    assert len(set(reports[:3])) == 3 and reports[3] == reports[0]
    jean = w.ensure_person("Jean Corran", "Resident, Harbour Row")
    agenda_free = sorted(t.id for t in w.briefing_threads() if t.id not in ("t1", "t2"))
    told = []
    for _ in range(2):                                                    # a new story and a new ward each time
        q, pet = chamber.brief_for(w, story), chamber.brief_for(w, petition)
        assert "{" not in q + pet
        told.append((next(i for i in agenda_free if f"[{i}]" in q), pet.split("from ")[1].split(",")[0]))
        _filed(w, story, f"Story {len(told)}", people=[jean.id])
        _filed(w, petition, f"Petition {len(told)}")
    assert told[0][0] != told[1][0] and [t[1] for t in told] == ["Saltby ward", "Cannery ward"]
    assert "a resident who has not been at the lectern tonight (NOT Jean Corran, who have spoken)" in pet


def test_the_agenda_says_which_motions_are_voted_and_who_has_spoken(monkeypatch):
    """On 2026-11-19 the links said "three votes settled, bowling green left" after the fourth was carried, and
    Jean Corran of Harbour Row came to the lectern three times."""
    w = _town()
    motion = lambda tid, applied: {"thread_id": tid, "title": tid, "motion": f"That {tid} goes ahead",  # noqa: E731
                                   "mover": NAMES[0], "carried": True, "for": 5, "against": 1, "applied": applied,
                                   "votes": []}
    w.chambers = [{"date": w.last_date, "motions": [motion("t1", True), motion("t2", False)]}]
    said = chamber.for_prompt(w)
    assert '1. "That t1 goes ahead" (moved by Gerald Thorne) — VOTED: CARRIED 5-1' in said
    assert '2. "That t2 goes ahead" (moved by Gerald Thorne) — not yet voted on' in said
    assert "1 of 2 voted on so far" in said and "FROM THE PUBLIC" not in said
    w.chambers[0]["motions"][1]["applied"] = True
    jean = w.ensure_person("Jean Corran", "Resident, Harbour Row")
    _filed(w, "public question time", "Pool question", people=[jean.id, w.person_by_name(NAMES[0]).id])
    said = chamber.for_prompt(w)
    assert "ALL of the agenda has been voted on: no motion is left to come" in said
    assert "FROM THE PUBLIC ALREADY TONIGHT" in said and "street): Jean Corran\n" in said


def test_a_loop_item_the_chamber_has_had_is_asked_for_again_but_never_a_motion():
    w = _town()
    show = schedule.SHOWS["chamber"]
    _filed(w, "x", "Cannery Shed Sign-Off Stands, Plaque Quote Requested")
    _filed(w, "y", "Who Won and Lost Tonight in the Port Wexley Chamber", kind="links")
    again = "Cannery Plaque Quote Requested as Shed Sign-Off Stands"
    assert writers._repeated(again, w, show, T.interview, "a question to the mayor from {who}") is not None
    assert writers._repeated(again, w, show, T.interview, "the THIRD motion, {m3}") is None
    assert writers._repeated(again, w, show, T.interview, "a question about {vote}") is None
    assert writers._repeated("Who Won and Lost Tonight in the Port Wexley Chamber", w, show, T.links, "y") is not None
    assert writers._repeated("Who Won and Lost Tonight in the Port Wexley Chamber", w, show, T.links, "z") is None
    _filed(w, "p", "Splash pool petition of 418 names goes to budget committee")
    assert writers._repeated("Splash Pool Petition of 418 Names Heads to Costing", w, show, T.interview, "p")


def test_an_item_written_ahead_already_counts_for_the_turns():
    """The Chamber is written about six items ahead of the air: the turn after a "{who}" item comes from the
    entry filed as it is written, not when it airs."""
    w = _town()
    _, ward, aob, *_ = schedule.SHOWS["chamber"].briefs[T.interview]
    assert NAMES[0] in chamber.brief_for(w, ward)
    seg = Segment(slot_id=40, type=T.interview, show="chamber", brief=ward, target_s=330.0)
    writers.script_segment(seg, w)                                        # written; the player hasn't said it aired
    filed = w.archive[-1]
    assert filed["show"] == "chamber" and filed["brief"] == ward and filed.get("aired") is False
    assert NAMES[1] in chamber.brief_for(w, aob) and NAMES[0] not in chamber.brief_for(w, aob)
