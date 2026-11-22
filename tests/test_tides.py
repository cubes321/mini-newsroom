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


def test_a_reworded_tide_or_ferry_time_is_caught():
    """The facts were right and Haiku still reworded a time now and then (the replays of 2026-11-22)."""
    from datetime import datetime

    now = datetime(2026, 11, 21, 21, 35)                # Saturday: 04:10, 10:22, 16:35, 22:48; Sunday: 05:00, 11:13, 17:25
    slips = lambda *lines: tides.clock_slips(list(lines), now, "sunny")  # noqa: E731
    assert slips("High water was twenty-five to five this afternoon, five point two metres.") == []
    assert slips("High water was twenty-five past four this afternoon.") == ["twenty-five past four"]
    assert slips("Low water comes just before ten to eleven tonight.", "Low water is just before eleven tonight.") == []
    assert slips("The low at twenty past eleven tomorrow is the one to watch.") == ["twenty past eleven"]   # 11:13
    # a slip that happens to be another of the times given gets by: "twenty to eleven" is tomorrow's last ferry
    assert slips("The low at twenty to eleven tonight is the last one.") == []
    assert slips("High water tomorrow is at five o'clock in the morning and again at twenty-five past five.") == []
    assert slips("The evening high tide is at twenty-five to six.") == ["twenty-five to six"]
    assert slips("The last ferry leaves at twenty to twelve tonight.", "The last crossing is at twenty to midnight.") == []
    assert slips("There is no ferry from two minutes to two.") == ["two minutes to two"]
    assert slips("The ferry stops from just before ten until twenty to twelve.") == []
    assert slips("Tomorrow the ferry runs from seven, with none from twenty-five past ten until five to twelve.") == ["five to twelve"]
    assert slips("High water at sixteen thirty-five was a big one.") == ["sixteen thirty-five"]       # never a 24-hour clock
    assert slips("High water was at 16:35, five point two metres.") == []
    # only where the tide or the ferry is the subject, and never the Tides
    assert slips("The Tides kicked off at three and won three-one.", "Dougal has been up the ladder since six.") == []
    assert slips("It is twenty-five to ten and the ferry is still running.") == []                    # the hour itself
    assert slips("The tide is at five point two metres, and it is four degrees.") == []


def test_the_writer_is_asked_again_for_a_time_that_is_none_of_those_given(monkeypatch):
    from datetime import datetime

    from newsroom import llm, schedule, world as world_mod, writers
    from newsroom.models import Segment, SegmentType as T

    w = world_mod.seed()
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        again = "WRONG TIMES" in user
        return schema.model_validate({
            "headline": "Clear and cold, with big tides", "map_state": "sunny", "temp_c": 4,
            "lines": [{"speaker": "weather", "text": "High water was " + ("twenty-five to five" if again else
                                                                           "twenty-five past four") + " this afternoon."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    monkeypatch.setattr(llm, "provider_for", lambda task: "claude_haiku")
    airs = datetime(2026, 11, 21, 21, 35).timestamp()
    seg = writers.script_segment(Segment(slot_id=5, type=T.weather, show="news", target_s=60.0, nominal_start_ts=airs), w)
    assert len(asked) == 2 and 'WRONG TIMES: the script said "twenty-five past four"' in asked[1]
    assert "twenty-five to five" in seg.lines[0].text and not seg.fallback


def test_a_tide_or_ferry_told_the_wrong_way_round_is_caught():
    """The sentences of the 2026-11-21 night, each a time given and each told as done when it was to come, or the
    reverse, or today's as tomorrow's: what `clock_slips` can't see."""
    from datetime import datetime

    sat = lambda h, m, *lines: tides.tense_slips(list(lines), datetime(2026, 11, 21, h, m), "sunny")  # noqa: E731
    sun = lambda h, m, *lines: tides.tense_slips(list(lines), datetime(2026, 11, 22, h, m), "sunny")  # noqa: E731
    # Saturday: 04:10, 10:22, 16:35, 22:48; ferry 07:00 to 23:40, none 09:32-11:12 and 21:58-23:38
    assert "is already gone" in sat(23, 38, "Low water came and went at twenty-two minutes past ten today, and the "
                                            "next one is at twelve minutes to eleven tonight.")[0]
    assert "is already gone" in sat(21, 41, "High water is at twenty-five past four this afternoon and again just "
                                            "after half past four.")[0]
    assert "has not finished" in sat(21, 11, "The foot ferry ran its last sailing for the night at twenty to midnight.")[0]
    assert "not running right now" in sat(22, 24, "Out here on the last ferry, with the lights going small behind us.")[0]
    assert "today's times" in sat(23, 50, "Low water came at ten to eleven and high water is due at ten past four "
                                          "in the morning.")[0]
    assert "none of the times given" in sat(19, 19, "High water near half past four tomorrow morning.")[0]
    # Sunday: 05:00, 11:13, 17:25; ferry from 07:00
    assert "is already gone" in sun(6, 0, "High water is at five this morning, so mind the quay.")[0]
    assert "not running right now" in sun(6, 40, "The first ferry is already rattling across the estuary.")[0]
    assert "not running right now" in sun(6, 20, "The Saltby foot ferry has been running since seven.")[0]
    # told as it is: nothing
    assert sat(21, 11, "The evening high water at twenty-five to five this afternoon was five point two metres.") == []
    assert sat(22, 58, "High water came in at twenty-five past four this morning and again at twenty-five to five "
                       "this afternoon.") == []
    assert sat(21, 47, "The last Saltby foot ferry leaves at twenty to twelve, so wrap up warm.") == []
    assert sun(6, 19, "The morning high water at five is five point three metres.") == []
    assert sun(6, 2, "The Saltby ferry is running every half hour from seven, so there's no excuse.") == []
    assert sat(22, 0, "It is ten o'clock on a Saturday, and the tide is doing its big spring thing.") == []
    assert sun(6, 33, "Is the Saltby foot ferry still running today?") == []
    assert sat(21, 53, "The afternoon high at thirty-five minutes past four tomorrow comes in at five point two.") == []


def test_the_writer_is_asked_again_for_a_tide_told_the_wrong_way_round(monkeypatch):
    from datetime import datetime

    from newsroom import llm, world as world_mod, writers
    from newsroom.models import Segment, SegmentType as T

    w = world_mod.seed()
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        again = "WRONG WAY ROUND" in user
        return schema.model_validate({
            "headline": "A sunny Sunday with big tides", "map_state": "sunny", "temp_c": 4,
            "lines": [{"speaker": "weather", "text": "High water " + ("was" if again else "is") + " at five this morning."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    monkeypatch.setattr(llm, "provider_for", lambda task: "claude_haiku")
    airs = datetime(2026, 11, 22, 6, 0).timestamp()
    seg = writers.script_segment(Segment(slot_id=5, type=T.weather, show="news", target_s=60.0, nominal_start_ts=airs), w)
    assert len(asked) == 2 and "WRONG WAY ROUND (it is 06:00" in asked[1] and '"at five" is already gone' in asked[1]
    assert seg.lines[0].text == "High water was at five this morning."


def test_a_span_of_the_ferry_is_not_a_tense():
    """The replay of 2026-11-22, 22:24 in the ferry's gap: told right, and caught as "already gone"."""
    from datetime import datetime

    now = datetime(2026, 11, 21, 22, 24)
    assert tides.tense_slips(["The Saltby landing has gone dry, and there is no boat from just before ten o'clock "
                              "tonight until just before twenty to twelve."], now, "sunny") == []
