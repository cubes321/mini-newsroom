"""Tides and the foot ferry are arithmetic: consistent through a day and from one day to the next."""
from datetime import date, timedelta

from newsroom import schedule, tides, world as world_mod, writers
from newsroom.models import SegmentType as T

DAYS = [date(2026, 10, 26) + timedelta(days=i) for i in range(30)]


def test_same_day_same_answer():
    assert tides.tides(DAYS[0]) == tides.tides(DAYS[0])


def test_highs_and_lows_alternate_about_six_hours_apart():
    events = [e for d in DAYS for e in tides.tides(d)]
    for (t1, k1, h1), (t2, k2, h2) in zip(events, events[1:]):
        assert k1 != k2
        assert 6 * 60 + 10 <= (t2 - t1).total_seconds() / 60 <= 6 * 60 + 15
        assert (h1 > h2) == (k1 == "high")


def test_high_water_is_about_fifty_minutes_later_each_day():
    first_high = [next(t for t, k, _ in tides.tides(d) if k == "high") for d in DAYS[:3]]
    shift = (first_high[1] - first_high[0]).total_seconds() / 60 - 24 * 60
    assert 45 <= shift <= 55


def test_springs_are_bigger_than_neaps():
    ranges = [max(h for _, k, h in tides.tides(d) if k == "high") - min(h for _, k, h in tides.tides(d) if k == "low")
              for d in DAYS[:15]]
    assert max(ranges) - min(ranges) > 2.0


def test_no_ferry_near_low_water_and_none_in_a_storm():
    for d in DAYS:
        lows = [t for t, k, _ in tides.tides(d) if k == "low"]
        f = tides.ferry(d)
        assert f["sailings"] and all(abs(s - lw) > timedelta(minutes=tides.LOW_GAP_MIN) for s in f["sailings"] for lw in lows)
        assert all(f["sailings"][0] < a + (b - a) / 2 < f["sailings"][-1] for a, b in f["gaps"])
    assert tides.ferry(DAYS[0], "storm")["sailings"] == []
    assert "off" in tides.for_prompt(DAYS[0], "fog")


def test_weather_breakfast_and_late_scripts_get_the_facts():
    w = world_mod.seed()
    has = {(st, show): "TIDES AT PORT WEXLEY" in writers.build_prompt(st, w, target_s=60, show=schedule.get(show))[1]
           for st, show in ((T.weather, "news"), (T.sofa, "breakfast"), (T.interview, "late"), (T.bulletin, "news"))}
    assert has == {(T.weather, "news"): True, (T.sofa, "breakfast"): True, (T.interview, "late"): True,
                   (T.bulletin, "news"): False}


def test_the_last_ferry_always_sails_after_the_last_ferry_starts():
    """2026-11-06: low water at 22:36 cancelled every sailing after 21:30, and The Last Ferry (22:00) kept
    saying the last ferry had gone at half past nine. Now it waits for the tide, or leaves as the landing
    dries when waiting would take it past midnight, and takes the place of a sailing just before it."""
    tonight = [s.strftime("%H:%M") for s in tides.ferry(date(2026, 11, 6))["sailings"]]
    assert tonight[-2:] == ["21:30", "23:30"]                      # waited for the 22:36 low water
    early = [s.strftime("%H:%M") for s in tides.ferry(date(2026, 11, 7))["sailings"]]
    assert early[-2:] == ["22:00", "22:35"]                        # low at 23:26: goes before it dries
    assert "the last ferry leaves at 23:30" in tides.for_prompt(date(2026, 11, 6))
    for i in range(400):
        day = date(2026, 1, 1) + timedelta(days=i)
        s = tides.ferry(day)["sailings"]
        assert s[-1].date() == day and s[-1].hour >= 22 and s[-1] - s[-2] >= timedelta(minutes=30), day


def test_the_writer_is_told_what_has_gone_what_is_to_come_and_tomorrow():
    """On the 2026-11-21 night 13 of the evening's 14 forecasts had a tide or the ferry wrong: given today's table
    alone they read it out as tomorrow's ("High water tomorrow comes at twenty to five in the morning, five point
    one metres"; Sunday's was 05:00, 5.3 m) and told the afternoon's high water as still to come at seven."""
    from datetime import datetime

    said = tides.for_prompt(date(2026, 11, 21), "sunny", now=datetime(2026, 11, 21, 21, 35))
    gone, ahead, tomorrow = (next(l for l in said.splitlines() if l.strip().startswith(k))
                             for k in ("TODAY, ALREADY GONE", "TODAY, STILL TO COME", "TOMORROW, Sunday 22 November"))
    assert "high water at twenty-five to five this afternoon (16:35), 5.2 m" in gone and "04:10" in gone
    assert "22:48" not in gone
    assert ahead.strip() == "TODAY, STILL TO COME: low water just before ten to eleven tonight (22:48), 0.6 m."
    assert "high water at five o'clock tomorrow morning (05:00), 5.3 m" in tomorrow and "04:10" not in tomorrow
    assert "high water at twenty-five past five tomorrow evening (17:25), 5.4 m" in tomorrow
    assert ("TOMORROW: every half hour, the first at seven o'clock tomorrow morning (07:00); no ferry from just before "
            "twenty-five past ten tomorrow morning (10:23) until just before five past twelve tomorrow afternoon (12:03), round low "
            "water; the last ferry leaves at quarter to eleven tomorrow night (22:45).") in said
    assert "today's are never given as tomorrow's" in said and "say the words as they are given" in said
    late = tides.for_prompt(date(2026, 11, 21), "sunny", now=datetime(2026, 11, 21, 23, 50))
    assert "TODAY, STILL TO COME: nothing more today." in late
    early = tides.for_prompt(date(2026, 11, 22), "sunny", now=datetime(2026, 11, 22, 0, 30))
    assert 'ALREADY GONE (say "was"): nothing yet.' in early and "TOMORROW, Monday 23 November" in early


def test_the_ferry_is_given_as_it_is_at_that_minute():
    """Miles was "out here on the last ferry" at 22:24 that night, in the low-water gap (none 21:58 to 23:38), and
    Morning Tide had it "running since seven" at 06:20."""
    from datetime import datetime

    at = lambda d, h, m: tides.ferry_now(datetime(2026, 11, d, h, m), "sunny")  # noqa: E731
    assert at(21, 21, 35) == ("running, every half hour; then no ferry from just before ten o'clock tonight (21:58) until "
                              "just before twenty to twelve tonight (23:38), round low water; the last ferry leaves at "
                              "twenty to twelve tonight (23:40)")
    assert at(21, 22, 24) == ("NOT running: the Saltby landing is dry, no ferry from just before ten o'clock tonight (21:58) "
                              "until just before twenty to twelve tonight (23:38), round low water; the next one is at "
                              "twenty to twelve tonight (23:40), which is the last ferry")
    assert at(21, 23, 50) == "finished for the night: the last ferry left at twenty to twelve tonight (23:40)"
    assert at(22, 6, 20) == ("NOT running yet, and none has sailed today: the first ferry is at seven o'clock this morning "
                             "(07:00); then no ferry from just before twenty-five past ten this morning (10:23) until just "
                             "before five past twelve this afternoon (12:03), round low water; the last ferry leaves at "
                             "quarter to eleven tonight (22:45)")
    assert at(22, 14, 0) == "running, every half hour; the last ferry leaves at quarter to eleven tonight (22:45)"
    assert tides.ferry_now(datetime(2026, 11, 22, 14, 0), "fog").startswith("not running at all today")
    said = tides.for_prompt(date(2026, 11, 21), "sunny", now=datetime(2026, 11, 21, 22, 24))
    assert "RIGHT NOW it is NOT running" in said and "Nobody is on the ferry, or just off it, while it is not running" in said


def test_the_weather_writer_gets_the_tides_as_they_are_when_the_item_airs():
    from datetime import datetime

    from newsroom import schedule, world as world_mod, writers
    from newsroom.models import SegmentType as T

    w = world_mod.seed()
    airs = datetime(2026, 11, 21, 19, 6).timestamp()
    user = writers.build_prompt(T.weather, w, target_s=60, show=schedule.get("news"), at_ts=airs)[1]
    assert "It is 19:06 on Saturday 21 November" in user and "TOMORROW, Sunday 22 November" in user
    assert "high water at twenty-five to five this afternoon (16:35), 5.2 m" in user.split("ALREADY GONE")[1].split("STILL TO COME")[0]


def test_a_time_is_given_in_the_words_to_say():
    """Told "16:35", Haiku said "twenty-five past four"; told "05:00", "five past five" (the replay of 2026-11-22)."""
    from datetime import datetime

    now = datetime(2026, 11, 21, 21, 35)
    for t, words in ((datetime(2026, 11, 21, 4, 10), "at ten past four this morning (04:10)"),
                     (datetime(2026, 11, 21, 16, 35), "at twenty-five to five this afternoon (16:35)"),
                     (datetime(2026, 11, 21, 22, 48), "just before ten to eleven tonight (22:48)"),
                     (datetime(2026, 11, 22, 5, 0), "at five o'clock tomorrow morning (05:00)"),
                     (datetime(2026, 11, 22, 11, 13), "just before quarter past eleven tomorrow morning (11:13)"),
                     (datetime(2026, 11, 22, 17, 25), "at twenty-five past five tomorrow evening (17:25)"),
                     (datetime(2026, 11, 22, 23, 38), "just before twenty to twelve tomorrow night (23:38)")):
        assert tides.said(t, now) == words
