"""Sunrise, sunset and the middle of the day at Port Wexley, for the art's grade and the forecast's words.

Until 2026-11-27 the station had one fixed clock for the light all year (`locations.time_of_day`: day 07:00 to 17:00,
dusk to 20:00 and at six, night otherwise). In December that glowed with sunset until 20:00, three and a half hours
after the sun went (16:19), and showed full day before an 08:16 sunrise; in June it went dusk at 17:00 and night at
20:00 with the sun up until 21:33. Gordon's "clear tonight" (forecast.dark) read the same clock.

Port Wexley is made up, but its names are Cornish: it stands on the south Cornish coast, at Falmouth's latitude and
longitude. The times are the NOAA approximation (within a minute or two), turned to the machine's local time, so
British Summer Time comes from the clock, not from a table here.
"""
from __future__ import annotations

import functools
import math
from datetime import date, datetime, timedelta, timezone

LAT, LON = 50.15, -5.07           # degrees north, east: the south Cornish coast
HORIZON = 90.833                  # the sun's centre this far from overhead at sunrise: refraction and its radius


@functools.lru_cache(maxsize=64)
def _utc_minutes(d: date) -> tuple[float, float, float]:
    """Sunrise, solar noon and sunset on `d`, in minutes after midnight UTC."""
    g = 2 * math.pi / 365 * (d.timetuple().tm_yday - 1)
    eq = 229.18 * (0.000075 + 0.001868 * math.cos(g) - 0.032077 * math.sin(g) - 0.014615 * math.cos(2 * g)
                   - 0.040849 * math.sin(2 * g))
    decl = (0.006918 - 0.399912 * math.cos(g) + 0.070257 * math.sin(g) - 0.006758 * math.cos(2 * g)
            + 0.000907 * math.sin(2 * g) - 0.002697 * math.cos(3 * g) + 0.00148 * math.sin(3 * g))
    lat = math.radians(LAT)
    ha = math.degrees(math.acos(math.cos(math.radians(HORIZON)) / (math.cos(lat) * math.cos(decl))
                                - math.tan(lat) * math.tan(decl)))
    noon = 720 - 4 * LON - eq
    return noon - 4 * ha, noon, noon + 4 * ha


def _local(d: date, minutes: float) -> datetime:
    utc = datetime(d.year, d.month, d.day, tzinfo=timezone.utc) + timedelta(minutes=minutes)
    return utc.astimezone().replace(tzinfo=None)


@functools.lru_cache(maxsize=64)       # the player asks every frame
def times(d: date) -> tuple[datetime, datetime, datetime]:
    """Sunrise, solar noon and sunset on `d`, local time (naive, like the station's clock)."""
    rise, noon, sett = _utc_minutes(d)
    return _local(d, rise), _local(d, noon), _local(d, sett)


def hours(d: date) -> tuple[float, float, float]:
    """The same, as hours after local midnight (07:55 is 7.92)."""
    return tuple(t.hour + t.minute / 60 + t.second / 3600 for t in times(d))      # type: ignore[return-value]


def up(t: datetime) -> bool:
    """Is the sun above the horizon at `t`?"""
    rise, _, sett = times(t.date())
    return rise <= t < sett
