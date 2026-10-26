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
