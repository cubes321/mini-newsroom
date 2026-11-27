"""Port Wexley's forecast: a low, a high and a sky for each day, which every weather keeps to.

Until 2026-11-27 nothing held a forecast. Each weather was written fresh, told only the last one's figure, so held
loosely it walked down a degree a report (13 to -6 on the 2026-11-25 evening) and held tightly to the first of three
hours it stuck (-4 in 50 of the 26th's 56 weathers, through a sunny Morning Tide), while the reports disagreed about
the afternoon ("warms to about two" at 05:50, "minus four for the day" at 08:09) and the weekend.

So the station keeps one: `World.forecasts`, a day to {low, high, sky}, made in code, never by a model. A day
follows the one before (the sky mostly stays, the temperatures lean back towards the month's normal), drawn from a
generator seeded by the date, so the same town gives the same forecast. The first day comes from the last weather
on record, so the new forecast picks up where the town was left. The figure for any minute is on a curve: the low
at sunrise, the high mid-afternoon (sun.py), down again overnight to the next day's low. Gordon is given the hour's
figure, today's low and high, tonight's low and tomorrow; the drift check holds his temp_c to the hour's figure and
his map to the day's sky; once the sun is down a clear sky is "clear". Everyone else's briefing has the same figures in a line (World.summary_for_prompt).

Nothing here imports the world: it takes one (`forecasts`, `last_weather`), so world.py can import it.
"""
from __future__ import annotations

import math
import random
from contextlib import nullcontext
from datetime import date, datetime, timedelta

from . import schedule, sun

HIGH_AFTER_NOON = 2.25           # hours after the sun is highest that the day is warmest; the coldest is sunrise
KEEP_DAYS = 14                    # days kept before today: "colder than yesterday" needs yesterday
DRIFT = 1                         # degrees a weather's temp_c may be from the hour's figure
PULL = 0.35                       # how far a day's departure from the month's normal eases back by the next
STAY = 0.6                        # the chance tomorrow keeps today's sky

# The month's normal low and high on the coast (a south-west harbour town; the sea keeps the winters mild).
NORMALS = {1: (4, 9), 2: (4, 9), 3: (5, 11), 4: (6, 13), 5: (9, 16), 6: (11, 19), 7: (13, 21), 8: (13, 21),
           9: (12, 19), 10: (9, 15), 11: (7, 12), 12: (5, 10)}
# A day's range from low to high by its sky: clear skies swing furthest, cloud and rain hold the night's warmth.
RANGE = {"sunny": (6, 8), "cloudy": (2, 4), "rain": (2, 4), "wind": (3, 5), "fog": (2, 3), "storm": (2, 3),
         "snow": (1, 3)}
# And what the sky does to the day's middle, in winter: a clear winter's day is a cold one, cloud and rain mild.
# In summer a clear day is a warm one (SUMMER_SUN).
SKY_SHIFT = {"sunny": -2.0, "cloudy": 0.0, "rain": 0.5, "wind": 0.0, "fog": -1.0, "storm": 1.0, "snow": -4.0}
SUMMER_SUN = 2.0
WINTER = (10, 11, 12, 1, 2, 3)
WINTER_SKIES = {"sunny": 3, "cloudy": 4, "rain": 3, "wind": 2, "fog": 1, "storm": 0.5, "snow": 0.3}
SUMMER_SKIES = {"sunny": 6, "cloudy": 3, "rain": 1.5, "wind": 1, "fog": 0.5, "storm": 0.2}
WORDS = {"sunny": "sunny", "cloudy": "cloudy", "rain": "rain", "storm": "a storm", "snow": "snow", "fog": "fog",
         "wind": "windy"}
NIGHT_WORDS = {"sunny": "clear"}  # the map has no clear night: after dark "sunny" is said as clear


def _rng(day: date) -> random.Random:
    return random.Random(f"port-wexley-weather-{day.isoformat()}")


def _shift(sky: str, day: date) -> float:
    return SKY_SHIFT[sky] if day.month in WINTER or sky != "sunny" else SUMMER_SUN


def _normal(day: date) -> float:
    return sum(NORMALS[day.month]) / 2


def _departure(d: dict, day: date) -> float:
    """How far a day was from its month's normal, the sky's part taken out."""
    return (d["low"] + d["high"]) / 2 - _normal(day) - _shift(d["sky"], day)


def _made(day: date, sky: str, departure: float, rng: random.Random) -> dict:
    span = rng.randint(*RANGE[sky])
    low = round(_normal(day) + departure + _shift(sky, day) - span / 2)
    return {"low": low, "high": low + span, "sky": sky}


def _sky(rng: random.Random, day: date) -> str:
    skies = WINTER_SKIES if day.month in WINTER else SUMMER_SKIES
    return rng.choices(list(skies), weights=list(skies.values()))[0]


def following(prev: dict, day: date) -> dict:
    """The day after `prev`: its sky mostly kept, its departure from the month's normal easing back."""
    rng = _rng(day)
    departure = (1 - PULL) * _departure(prev, day - timedelta(days=1)) + rng.uniform(-1.5, 1.5)
    sky = prev["sky"] if rng.random() < STAY else _sky(rng, day)
    made = _made(day, sky, departure, rng)
    if sky == "snow" and (day.month not in (12, 1, 2) or made["low"] > 0):     # snow only on a freezing winter day
        made = _made(day, "cloudy", departure, rng)
    return made


def first(day: date, last_weather: dict | None) -> dict:
    """A first day, from the last weather on record, so the town's weather carries on: an evening's figure is near
    the next morning's low, a morning's near that day's low, an afternoon's near its high. The days after the one the
    figure belongs to follow from it, up to KEEP_DAYS (a station off over a weekend); otherwise (no figure, or an
    older one) the month's normal under cloud."""
    wx = last_weather or {}
    temp, sky, ts = wx.get("temp_c"), wx.get("map_state"), wx.get("ts")
    if temp is not None and sky in RANGE and ts:
        t = datetime.fromtimestamp(ts)
        of = t.date() + timedelta(days=1) if t.hour >= 18 else t.date()
        if timedelta(0) <= day - of <= timedelta(days=KEEP_DAYS):   # a station off for days carries on from it too
            rng = _rng(of)
            span = rng.randint(*RANGE[sky])
            low = int(temp) - span if 10 <= t.hour < 18 else int(temp)
            was = {"low": low, "high": low + span, "sky": sky}
            while of < day:
                of += timedelta(days=1)
                was = following(was, of)
            return was
    return _made(day, "cloudy", 0.0, _rng(day))


def day(world, d: date) -> dict:
    """The forecast for `d`, made and kept if it isn't yet: from the nearest day before it on record (each day
    between made in turn), or a first one. Days more than KEEP_DAYS before `d` are let go."""
    with getattr(world, "lock", nullcontext()):      # the workers write scripts side by side
        return _day_locked(world, d)


def _day_locked(world, d: date) -> dict:
    fc = world.forecasts
    key = d.isoformat()
    if key in fc:
        return fc[key]
    before = sorted(k for k in fc if k < key and date.fromisoformat(k) >= d - timedelta(days=KEEP_DAYS))
    if before:
        at, prev = date.fromisoformat(before[-1]), fc[before[-1]]
    else:
        at, prev = d, first(d, world.last_weather)
        fc[key] = prev
    while at < d:
        at += timedelta(days=1)
        prev = fc[at.isoformat()] = following(prev, at)
    for k in [k for k in fc if date.fromisoformat(k) < d - timedelta(days=KEEP_DAYS)]:
        del fc[k]
    return fc[key]


def _ease(a: float, b: float, x: float) -> float:
    return a + (b - a) * (1 - math.cos(math.pi * max(0.0, min(1.0, x)))) / 2


def low_at(d: date) -> float:
    """The hour the day is coldest: sunrise (sun.py), 08:16 at midwinter, 05:09 at midsummer."""
    return sun.hours(d)[0]


def high_at(d: date) -> float:
    """The hour the day is warmest: mid-afternoon, 14:33 at midwinter, 15:36 (summer time) at midsummer."""
    return sun.hours(d)[1] + HIGH_AFTER_NOON


def temp_at(world, t: datetime) -> int:
    """Port Wexley's temperature at `t`: up from the day's low at sunrise to its high mid-afternoon, then down to
    the next day's low at the next sunrise."""
    d, h = t.date(), t.hour + t.minute / 60
    today = day(world, d)
    low, high = low_at(d), high_at(d)
    if h < low:         # from yesterday's high, if the station had a yesterday (it doesn't make one: see `day`)
        before = world.forecasts.get((d - timedelta(days=1)).isoformat()) or today
        was = high_at(d - timedelta(days=1)) - 24
        return round(_ease(before["high"], today["low"], (h - was) / (low - was)))
    if h < high:
        return round(_ease(today["low"], today["high"], (h - low) / (high - low)))
    nxt = d + timedelta(days=1)
    return round(_ease(today["high"], day(world, nxt)["low"], (h - high) / (low_at(nxt) + 24 - high)))


def dark(t: datetime) -> bool:
    """Is the sun down at `t`? Then a clear sky is "clear", not sunny."""
    return not sun.up(t)


def sky_at(world, t: datetime) -> str:
    """The map's state at `t`: the day's sky (a change comes in at midnight)."""
    return day(world, t.date())["sky"]


def said(sky: str, at_night: bool) -> str:
    return (NIGHT_WORDS.get(sky) if at_night else None) or WORDS[sky]


def now(world, at: float | None = None) -> tuple[int, str]:
    """The hour's figure and the map's state, for the weather's temp_c and map_state."""
    t = datetime.fromtimestamp(at if at is not None else schedule.now())
    return temp_at(world, t), sky_at(world, t)


def brief(world, at: float | None = None) -> str:
    """One line for every writer's briefing: the figures anyone on air may give."""
    t = datetime.fromtimestamp(at if at is not None else schedule.now())
    today, tomorrow = day(world, t.date()), day(world, t.date() + timedelta(days=1))
    temp, sky = temp_at(world, t), sky_at(world, t)
    h = t.hour + t.minute / 60
    dawn = f"{today['low']}°C by dawn; " if h < low_at(t.date()) else ""
    later = f"today's high {today['high']}°C this afternoon; " if h < high_at(t.date()) else ""
    return (f"{temp}°C and {said(sky, dark(t))} now; {dawn}{later}tonight {tomorrow['low']}°C by dawn; "
            f"tomorrow {said(tomorrow['sky'], False)}, high {tomorrow['high']}°C")


def for_prompt(world, at: float | None = None) -> str:
    """The forecast for Gordon: the figures he gives, and how to give them. Each night is named by its day
    ("Saturday night"): before dawn, asked about "tonight" with only "the rest of the night" to go on, the 2026-11-27
    replay gave the night it was in, not the one to come. And the map's "sunny" is said as clear after dark without
    a reason given: given one, he told the viewers the map shows it as sunny "only out of habit"."""
    t = datetime.fromtimestamp(at if at is not None else schedule.now())
    d = t.date()
    nxt = d + timedelta(days=1)
    yesterday = world.forecasts.get((d - timedelta(days=1)).isoformat())
    today, tomorrow = day(world, d), day(world, nxt)
    after = day(world, d + timedelta(days=2))
    temp, sky = temp_at(world, t), sky_at(world, t)
    at_night = dark(t)
    h = t.hour + t.minute / 60
    skies = " skies" if at_night and sky == "sunny" else ""
    lines = [f"  - Now, at {t:%H:%M}: {temp}°C, {said(sky, at_night)}{skies}. "
             f"Put temp_c = {temp} and map_state = \"{sky}\", and say {temp} degrees."]
    if h < low_at(d) and today["low"] < temp:       # only while it has further to fall ("it dropped to zero around
        lines.append(f"  - Before dawn this morning: down to {today['low']}°C around sunrise.")  # seven" at 05:55)
    if h < high_at(d):
        lines.append(f"  - Today, {d:%A}: {said(today['sky'], False)}, a high of {today['high']}°C "
                     f"{'this afternoon' if h >= low_at(d) else 'in the afternoon'}.")
    change = f", {said(tomorrow['sky'], True)} coming in" if tomorrow["sky"] != today["sky"] else ""
    lines.append(f"  - Tonight, {d:%A} night: {tomorrow['low']}°C by {nxt:%A}'s dawn{change}.")
    lines.append(f"  - Tomorrow, {nxt:%A}: {said(tomorrow['sky'], False)}, a high of {tomorrow['high']}°C.")
    lines.append(f"  - The day after, {d + timedelta(days=2):%A}: {said(after['sky'], False)}, a high of "
                 f"{after['high']}°C.")
    if yesterday:
        lines.append(f"  - Yesterday, for comparison only: a low of {yesterday['low']}°C and a high of "
                     f"{yesterday['high']}°C, {said(yesterday['sky'], False)}.")
    night = " It is dark: the sky is clear, never sunny or sunshine." if at_night and sky == "sunny" else ""
    return ("\n\nTHE FORECAST (the station's own; every weather today gives these figures and no others):\n"
            + "\n".join(lines) + "\nGive the shape of the day from these: how cold tonight, how warm tomorrow, "
            "what the sky does. Don't call any figure the same as an earlier forecast, last time or yesterday; just "
            f"give it.{night}")


def drift(world, temp: int | None, state: str | None, at: float) -> tuple[int, str] | None:
    """The hour's figure and sky if a weather's temp_c is more than DRIFT from the one or its map not the other,
    else None."""
    want_t, want_s = now(world, at)
    if temp is None:
        return None
    return (want_t, want_s) if abs(temp - want_t) > DRIFT or (state and state != want_s) else None
