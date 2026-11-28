"""The station's forecast (forecast.py): a low, a high and a sky for each day, which every weather keeps to. On the
2026-11-25 evening the weather walked from 13 to -6, a degree a report; on the 26th, held to the first of three
hours, it stuck at -4 for 50 of 56 reports, through a sunny morning, while the reports disagreed about the afternoon
and the weekend. The model is stubbed: no network."""
from __future__ import annotations

from datetime import date, datetime, timedelta

from newsroom import forecast, llm, schedule, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T, WeatherScript

FRI = date(2026, 11, 27)
LAST = {"map_state": "sunny", "temp_c": -4, "headline": "Sunshine and Minus Four Hold for Friday",
        "ts": datetime(2026, 11, 27, 9, 47).timestamp()}


def _world(monkeypatch, at: datetime, last: dict | None = LAST):
    w = world_mod.seed()
    w.last_weather = dict(last or {})
    monkeypatch.setattr(world_mod.schedule, "now", lambda: at.timestamp())
    return w


def test_the_first_day_carries_on_from_the_last_weather_and_the_next_ease_back(monkeypatch):
    w = _world(monkeypatch, datetime(2026, 11, 27, 21, 0))
    fri = forecast.day(w, FRI)
    assert fri["low"] == -4 and fri["sky"] == "sunny" and 2 <= fri["high"] <= 6    # a morning's -4 is the day's low
    later = [forecast.day(w, FRI + timedelta(days=i)) for i in range(1, 8)]
    assert later[0]["low"] > fri["low"] and later[-1]["low"] >= 0              # the frost eases towards December's
    assert all(d["high"] > d["low"] for d in later)
    again = _world(monkeypatch, datetime(2026, 11, 27, 21, 0))
    assert [forecast.day(again, FRI + timedelta(days=i)) for i in range(8)] == [fri, *later]   # same town, same days
    assert (FRI - timedelta(days=1)).isoformat() not in w.forecasts          # no yesterday is made up


def test_an_evening_figure_is_the_next_mornings_low_and_an_old_one_is_not_used(monkeypatch):
    evening = {**LAST, "temp_c": 2, "ts": datetime(2026, 11, 26, 21, 30).timestamp()}
    w = _world(monkeypatch, datetime(2026, 11, 27, 6, 0), evening)
    assert forecast.day(w, FRI)["low"] == 2
    stale = {**LAST, "ts": datetime(2026, 11, 1, 9, 0).timestamp()}
    w = _world(monkeypatch, datetime(2026, 11, 27, 6, 0), stale)
    assert forecast.day(w, FRI)["sky"] == "cloudy"                            # weeks old: the month's normal


def test_a_station_off_for_days_carries_on_from_the_last_weather(monkeypatch):
    """Off from Friday morning to Sunday: Sunday is the day the forecast would have reached, not November's normal."""
    sun = FRI + timedelta(days=2)
    every_day = _world(monkeypatch, datetime(2026, 11, 27, 21, 0))
    want = [forecast.day(every_day, FRI + timedelta(days=i)) for i in range(3)]
    off = _world(monkeypatch, datetime(2026, 11, 29, 21, 0))
    assert forecast.day(off, sun) == want[2] and FRI.isoformat() not in off.forecasts


def test_the_briefing_and_gordon_have_the_weather_as_it_airs_not_as_it_is_written(monkeypatch):
    """A writer works about ten minutes ahead: written at 23:55 for 00:05, both lines are the 00:05 weather."""
    w = _world(monkeypatch, datetime(2026, 11, 27, 23, 55))
    airs = datetime(2026, 11, 28, 0, 5).timestamp()
    user = writers.build_prompt(T.weather, w, target_s=60, show=schedule.get("news"), at_ts=airs)[1]
    assert forecast.brief(w, airs) in user and forecast.brief(w) not in user
    assert "Now, at 00:05" in user and "Tonight, Saturday night" in user


def test_the_teletext_and_the_backdrop_have_the_forecasts_sky(monkeypatch):
    from newsroom import teletext
    night = datetime(2026, 11, 28, 2, 0)
    w = _world(monkeypatch, night)
    temp, sky = forecast.now(w, night.timestamp())
    page = next(p for p in teletext.pages(w, night) if p.get("title") == "WEATHER" or "WEATHER" in str(p)[:200])
    assert f"Clear, {temp}C" in str(page) and sky == "sunny"


def test_the_figure_follows_the_day_low_at_dawn_high_mid_afternoon(monkeypatch):
    w = _world(monkeypatch, datetime(2026, 11, 27, 21, 0))
    fri, sat = forecast.day(w, FRI), forecast.day(w, FRI + timedelta(days=1))
    def at(h, m=0, d=FRI):
        return forecast.temp_at(w, datetime.combine(d, datetime.min.time()) + timedelta(hours=h, minutes=m))
    low, high = forecast.low_at(FRI), forecast.high_at(FRI)
    assert 7.8 < low < 7.9 and 14.3 < high < 14.4                            # sunrise 07:51; warmest 14:23
    assert at(low) == fri["low"] and at(high) == fri["high"]
    assert at(forecast.low_at(FRI + timedelta(days=1)), 0, FRI + timedelta(days=1)) == sat["low"]
    day_ = [at(h) for h in range(8, 15)]
    assert day_ == sorted(day_)                                               # up through the morning
    assert at(7) < at(5) or at(7) == fri["low"]                              # still falling before a late sunrise
    evening = [at(h) for h in range(15, 24)]
    assert evening == sorted(evening, reverse=True) or sat["low"] >= fri["high"]
    assert fri["low"] <= at(3) <= fri["high"]                               # before dawn, no made-up yesterday


def test_gordon_is_given_the_figures_and_clear_for_sunny_after_dark(monkeypatch):
    night = datetime(2026, 11, 27, 21, 15)
    w = _world(monkeypatch, night)
    temp, sky = forecast.now(w, night.timestamp())
    note = forecast.for_prompt(w, night.timestamp())
    sat = forecast.day(w, FRI + timedelta(days=1))
    assert f"temp_c = {temp}" in note and f'map_state = "{sky}"' in note and f"say {temp} degrees" in note
    assert f"Tonight, Friday night: {sat['low']}°C by Saturday's dawn" in note
    assert f"Tomorrow, Saturday: sunny, a high of {sat['high']}°C" in note and "clear skies" in note
    assert "the sky is clear, never sunny" in note and "same as an earlier forecast" in note
    assert "map behind" not in note and "habit" not in note                   # no reason to tell the viewers
    morning = datetime(2026, 11, 28, 6, 20)
    monkeypatch.setattr(world_mod.schedule, "now", lambda: morning.timestamp())
    note = forecast.for_prompt(w, morning.timestamp())
    sun = forecast.day(w, FRI + timedelta(days=2))
    assert ("Before dawn this morning" in note) == (forecast.now(w, morning.timestamp())[0] > sat["low"])
    early = datetime(2026, 11, 28, 1, 0).timestamp()
    assert f"Before dawn this morning: down to {sat['low']}°C" in forecast.for_prompt(w, early)
    assert f"Today, Saturday: sunny, a high of {sat['high']}°C in the afternoon" in note
    assert f"Tonight, Saturday night: {sun['low']}°C by Sunday's dawn" in note    # tonight is the one to come
    assert "Yesterday, for comparison only: a low of -4°C" in note             # Friday, as it was forecast
    assert f"tonight {sun['low']}°C by dawn" in forecast.brief(w, morning.timestamp())
    noon = datetime(2026, 11, 28, 12, 0).timestamp()
    assert "never sunny" not in forecast.for_prompt(w, noon) and "Today, Saturday" in forecast.for_prompt(w, noon)


def test_every_writer_is_told_the_same_figures_after_the_cache_break(monkeypatch):
    w = _world(monkeypatch, datetime(2026, 11, 27, 21, 15))
    head, _, tail = w.summary_for_prompt().partition(llm.CACHE_BREAK)
    line = forecast.brief(w)
    assert line in tail and "Weather (the station's forecast" in tail and "Last weather" not in tail
    assert line.startswith(f"{forecast.temp_at(w, datetime(2026, 11, 27, 21, 15))}°C and clear now")
    monkeypatch.setattr(world_mod.schedule, "now", lambda: datetime(2026, 11, 27, 23, 40).timestamp())
    head2, _, tail2 = w.summary_for_prompt().partition(llm.CACHE_BREAK)
    assert head2 == head and forecast.brief(w) in tail2                       # the cached head doesn't move


def _wx(temp: int, sky: str = "sunny") -> WeatherScript:
    return WeatherScript.model_validate({"headline": "Clear and Cold", "map_state": sky, "temp_c": temp,
                                         "lines": [{"speaker": "weather", "text": f"It's {temp} degrees."}]})


def test_a_weather_off_the_forecast_is_asked_again(monkeypatch):
    night = datetime(2026, 11, 27, 21, 15)
    w = _world(monkeypatch, night)
    temp, sky = forecast.now(w, night.timestamp())
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return _wx(-4) if len(asked) == 1 else _wx(temp, sky)
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=11, type=T.weather, show="news", target_s=60, nominal_start_ts=night.timestamp())
    writers.script_segment(seg, w)
    assert len(asked) == 2 and "OFF THE FORECAST: you gave -4°C" in asked[1] and f"temp_c = {temp}" in asked[1]
    assert w.last_weather["temp_c"] == temp and "THE FORECAST (the station's own" in asked[0]
    asked.clear()
    monkeypatch.setattr(llm, "complete_json", lambda *a: (asked.append(a), _wx(temp + 1, sky))[1])
    writers.script_segment(Segment(slot_id=21, type=T.weather, show="news", target_s=60,
                                   nominal_start_ts=night.timestamp()), w)
    assert len(asked) == 1                                                    # a degree out is allowed
    monkeypatch.setattr(llm, "complete_json", lambda *a: (asked.append(a), _wx(temp, "rain"))[1])
    writers.script_segment(Segment(slot_id=31, type=T.weather, show="news", target_s=60,
                                   nominal_start_ts=night.timestamp()), w)
    assert len(asked) == 3                                                    # the wrong sky is asked again


def test_the_template_weather_gives_the_forecast(monkeypatch):
    night = datetime(2026, 11, 27, 21, 15)
    w = _world(monkeypatch, night)
    s = writers._template(T.weather, w, writers.random.Random(1), schedule.get("news"), at_ts=night.timestamp())
    assert (s.temp_c, s.map_state) == forecast.now(w, night.timestamp()) and "A clear" in s.lines[1].text


def test_the_forecasts_are_saved_and_old_days_let_go(monkeypatch):
    w = _world(monkeypatch, datetime(2026, 11, 27, 21, 0))
    forecast.day(w, FRI)
    back = world_mod._from_dict(world_mod._to_dict(w))
    assert back.forecasts == w.forecasts
    forecast.day(w, FRI + timedelta(days=forecast.KEEP_DAYS + 3))
    assert FRI.isoformat() not in w.forecasts and min(w.forecasts) >= (FRI + timedelta(days=3)).isoformat()


def test_a_clear_winters_day_is_colder_than_a_cloudy_one_and_snow_only_freezes():
    w = type("W", (), {"forecasts": {}, "last_weather": {}})()
    days = [forecast.day(w, date(2027, 1, 1) + timedelta(days=i)) for i in range(365)]
    winter = [d for i, d in enumerate(days) if (date(2027, 1, 1) + timedelta(days=i)).month in (12, 1, 2)]
    def mean(sky):
        lows = [d["low"] for d in winter if d["sky"] == sky]
        return sum(lows) / max(1, len(lows))
    assert mean("sunny") < mean("cloudy")
    assert all(d["low"] <= 0 for d in days if d["sky"] == "snow")
    july = [d for i, d in enumerate(days) if (date(2027, 1, 1) + timedelta(days=i)).month == 7]
    assert 10 <= min(d["low"] for d in july) and max(d["high"] for d in july) <= 30


def test_the_light_follows_the_sun_not_the_clock():
    """Until 2026-11-27 the art was day from 07:00 to 17:00 and dusk to 20:00 all year: a December sunset glow three
    and a half hours after the sun went (16:19), and night at 20:00 in June with the sun up until 21:33."""
    from newsroom import sun
    from newsroom.locations import time_of_day
    rise, noon, sett = sun.times(date(2026, 12, 21))
    assert (rise.strftime("%H:%M"), sett.strftime("%H:%M")) == ("08:16", "16:19")
    tod = lambda y, mo, d, h, mi=0: time_of_day(datetime(y, mo, d, h, mi))   # noqa: E731
    assert [tod(2026, 12, 21, h, m) for h, m in ((7, 0), (7, 50), (9, 0), (16, 0), (16, 45), (17, 30), (19, 30))] == \
        ["night", "dusk", "day", "dusk", "dusk", "night", "night"]
    assert [tod(2027, 6, 21, h, m) for h, m in ((4, 40), (6, 0), (17, 30), (20, 30), (21, 30), (22, 30))] == \
        ["dusk", "day", "day", "day", "dusk", "night"]
    assert time_of_day(datetime(2027, 6, 21, 21, 30).timestamp()) == "dusk"     # a timestamp, as the player gives
    assert sun.times(date(2027, 3, 29))[0].hour == 7 and sun.times(date(2027, 3, 27))[0].hour == 6   # summer time
    assert forecast.dark(datetime(2026, 12, 21, 16, 30)) and not forecast.dark(datetime(2027, 6, 21, 20, 30))


def test_the_hour_before_dusk_is_golden():
    """On 2026-11-28 Out and About's last scenes, half an hour before a 16:19 sunset, were as white as noon."""
    from newsroom import backdrops
    from newsroom.locations import GOLDEN_BEFORE, time_of_day
    from newsroom import sun
    sett = sun.times(date(2026, 11, 28))[2]
    tod = lambda m: time_of_day(sett - timedelta(minutes=m))                  # noqa: E731
    assert [tod(m) for m in (90, 61, 59, 35, 29, 0)] == ["day", "day", "golden", "golden", "dusk", "dusk"]
    assert GOLDEN_BEFORE == timedelta(minutes=60)
    assert "golden" in backdrops.TODS and "golden" in backdrops.LIT_BY_DAY      # no lamps, no beam
    warm = backdrops.person_light("harbour", "golden", None)
    assert warm[0] > 1.0 > warm[2] and backdrops.person_light("studio_wide", "golden", None) == (1.0, 1.0, 1.0)
