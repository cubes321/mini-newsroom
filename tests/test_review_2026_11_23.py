"""The rest of the 2026-11-22 night's review, fixed on 2026-11-23, tested on the night's own lines: the overnight
documentaries' hour, the repeat's label, the Chamber trail in guests' mouths, panellists and presenters' names, the
sport's facts, "Good evening" midway, Coastwide's weathers, and steps told before their day by a title or a loose
end. No network."""
from __future__ import annotations

from datetime import datetime

from newsroom import documentary, schedule, special, sport, world as world_mod, writers
from newsroom.models import BulletinScript, InterviewScript, Line, Segment, SegmentType as T

SUN = datetime(2026, 11, 22, 21, 30)


def test_an_overnight_documentary_is_told_it_airs_now(monkeypatch):
    seg = Segment(slot_id=1000008, type=T.documentary, show="news", target_s=300, work={"format": "documentary"})
    night = datetime(2026, 11, 23, 2, 43).timestamp()
    monkeypatch.setattr(special.schedule, "now", lambda: night)
    assert "02:43" in special.airs_at(seg) and "21:00" not in special.airs_at(seg)
    evening = datetime(2026, 11, 22, 18, 47).timestamp()
    monkeypatch.setattr(special.schedule, "now", lambda: evening)
    assert "21:00" in special.airs_at(seg)                       # the week's review, made at 18:47, airs at nine


def test_the_repeat_says_which_day_it_is_from():
    sun9 = datetime(2026, 11, 22, 21, 1).timestamp()
    assert documentary.repeat_label(sun9, datetime(2026, 11, 23, 2, 2).timestamp()) == "REPEAT FROM SUNDAY"
    assert documentary.repeat_label(sun9, datetime(2026, 11, 22, 23, 50).timestamp()) == "REPEAT"


def test_a_guest_never_says_the_chamber_trail():
    lines = [Line(speaker="guest", guest_name="Helen Strand",
                  text="Full council meets on Thursday the third of December, live on The Chamber at eight, and that "
                       "is where decisions get taken."),
             Line(speaker="guest", guest_name="Gerald Thorne",
                  text="Yes. Full council, Thursday the third of December, live on The Chamber at eight. Nothing gets "
                       "decided in a corridor."),
             Line(speaker="anchor", text="Full council meets on the third, live on The Chamber at eight.")]
    assert writers.no_chamber_trail_from_guests(lines) == 2
    assert lines[0].text == ("Full council meets on Thursday the third of December, and that is where decisions get "
                             "taken.")
    assert lines[1].text.startswith("Yes. Full council, Thursday the third of December. Nothing")
    assert "live on The Chamber" in lines[2].text                # a presenter may trail it


def test_a_panellist_speaking_of_themselves_and_a_guest_with_a_presenters_name():
    script = InterviewScript.model_validate({"headline": "The panels", "lower_third": "The Panel", "lines": [
        {"speaker": "anchor", "text": "Gerald?"},
        {"speaker": "guest", "guest_name": "Gerald Thorne",
         "text": "Gerald has been waiting for the numbers for months, and the numbers are still not on the table."},
        {"speaker": "guest", "guest_name": "Dolores Finch", "text": "Costings first, then."}]})
    assert len(writers.own_name_lines(script)) == 1
    w = world_mod.seed()
    assert writers.presenter_named("Gordon Pell", w) == "Gordon Pell"
    assert writers.presenter_named("Gordon Ashdown", w) == "Gordon Pell"
    assert writers.presenter_named("Imogen Vale", w) is None


def test_the_sport_against_the_sports_desks_facts():
    eve = datetime(2026, 11, 22, 23, 10)
    said = ["Port Wexley Tides beat Saltby Rovers three-one at home this afternoon, with goals from Shore, Kemp and "
            "Price.",
            "Ruth, the Wreckers beat Lowmoor thirty-eight to twenty-two a fortnight back.",
            "Tonight's bulletin, and the Tides are still on top of the Greymouth and District League after Saturday's "
            "three-one."]
    notes = sport.slips(said, eve)
    assert any("was yesterday" in n and "not today" in n for n in notes)
    assert any("8 days ago" in n and "not a fortnight" in n for n in notes)
    assert any("not top" in n for n in notes)
    right = ["The Tides beat Saltby Rovers three-one at home yesterday, with goals from Shore, Kemp and Price.",
             "Also tonight, the Wreckers face Saltby away on Saturday, after their thirty-eight to twenty-two win over "
             "Lowmoor.",
             "They beat Saltby Rovers three-one yesterday, and next go away to Polgrey Rangers.",
             f"The Tides stay {sport._PLACES[[r['club'] for r in sport.table(eve)].index(sport.CLUB)]} in the league."]
    assert sport.slips(right, eve) == []
    r = next(x for x in reversed(sport.played(eve)) if sport.CLUB not in (x.fixture.home, x.fixture.away))
    a, b = r.fixture.home, r.fixture.away
    wrong = f"{b} beat {a} {max(r.home_goals, r.away_goals) + 2}-0 on Saturday."
    assert any(f"the result was {a}" in n for n in sport.slips([wrong], eve))


def test_good_evening_only_where_a_programme_begins():
    news, mag = schedule.get("news"), schedule.get("magazine")
    at = datetime(2026, 11, 22, 21, 22).timestamp()
    lines = [Line(speaker="weather", text="Good evening, Port Wexley. Gordon Pell with your weather, and a calm one.")]
    assert writers.no_hello_midway(lines, news, T.weather, "", at) == 1 and lines[0].text.startswith("Gordon Pell with")
    lines = [Line(speaker="anchor", text="Good evening. Miles Okafor is at the quay."),
             Line(speaker="reporter", text="Good evening, I'm Miles Okafor on Harrow Street.")]
    assert writers.no_hello_midway(lines, news, T.field_report, "", at) == 2
    assert lines[1].text == "I'm Miles Okafor on Harrow Street."
    top = datetime(2026, 11, 22, 22, 1).timestamp()                 # the news on the hour may greet
    lines = [Line(speaker="anchor", text="Good evening. The Tides won.")]
    assert writers.no_hello_midway(lines, news, T.bulletin, "", top) == 0
    lines = [Line(speaker="mag_a", text="Good evening, and welcome back to the middle of Coastwide. Clive, what have you found?")]
    assert writers.no_hello_midway(lines, mag, T.links, "", at) == 1 and lines[0].text == "Clive, what have you found?"
    lines = [Line(speaker="mag_a", text="Good evening, and welcome to Coastwide.")]
    assert writers.no_hello_midway(lines, mag, T.links, "open", at) == 0
    lines = [Line(speaker="mag_a", text="Good evening, Bea.")]
    assert writers.no_hello_midway(lines, mag, T.interview, "", at) == 0      # a hello to the guest by name stays


def test_coastwide_has_two_weathers(monkeypatch):
    """Each keeps to the station's forecast since 2026-11-27 (tests/test_forecast.py), not to the one before."""
    mag = schedule.get("magazine")
    items = [schedule.as_item(e).type for e in (*mag.pattern, *mag.closing)]
    assert items.count(T.weather) == 2


def test_a_title_or_a_loose_end_that_names_a_step_not_due(monkeypatch):
    monkeypatch.setattr(world_mod.schedule, "now", lambda: SUN.timestamp())
    w = world_mod.seed()
    w.last_date = "2026-11-22"
    chess = w.thread(w.update_thread(None, "Year 9 Chess Club Sets Up Boards in the Academy Hall at Lunch", "so far"))
    chess.next_development = ("At Friday 27 November lunchtime Priya Nair sets out six borrowed boards in the Academy "
                              "hall for the staff-room challenger.")
    assert "its title names that planned step, which has NOT happened yet" in w._thread_line(chess)
    assert "title names" not in w._thread_line(chess, full=True)
    rope = w.thread(w.update_thread(None, "Harbour Mooring Rope Wears Through", "so far"))
    rope.next_development = "On Monday 23 November Dougal Crane fits the new mooring rope on the quay before the big tide."
    note = writers._not_settled("whether the new mooring rope went on before the big tide", w)
    assert f"[{rope.id}]" in note and "due tomorrow, Monday 23 November" in note and "hasn't happened yet" in note
    assert writers._not_settled("what her favourite biscuit is", w) == ""
