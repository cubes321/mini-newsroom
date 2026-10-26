"""Port Wexley's tides and the Saltby foot ferry, worked out rather than written by the model.

The model used to invent the morning tide, and a different one each time. Here it is
arithmetic: a semi-diurnal tide (high water every 12 h 25 min, so about 50 minutes later
each day) whose heights swell and shrink over the 14.8-day spring-neap cycle, from a
fixed first high water. Fictional, but consistent: every segment on a given day agrees,
and tomorrow follows on from today.

The foot ferry crosses the Grey estuary to Saltby every half hour from 07:00, the last
one at 23:15 (the late show's namesake). The Saltby landing dries out, so there are no
crossings within LOW_GAP_MIN of low water, and none at all in a storm or fog.

    python -m newsroom.tides [YYYY-MM-DD]
"""
from __future__ import annotations

import math
from datetime import date, datetime, timedelta

EPOCH_HW = datetime(2026, 1, 1, 4, 52)    # a high water at Port Wexley
SPRING_EPOCH = datetime(2026, 1, 2, 12, 0)  # the middle of a spring tide
M2 = timedelta(hours=12.4206)              # high water to high water
SPRING_NEAP_DAYS = 14.765
HW_MEAN, HW_SWING = 4.6, 0.8               # metres above chart datum
LW_MEAN, LW_SWING = 1.0, 0.5

FERRY = "the Saltby foot ferry"
FERRY_FIRST, FERRY_EVERY_MIN, FERRY_HALF_HOURLY_UNTIL = (7, 0), 30, (22, 30)
LAST_FERRY = (23, 15)
LOW_GAP_MIN = 50
NO_FERRY_WEATHER = ("storm", "fog")


def _spring(t: datetime) -> float:
    """1 at springs, -1 at neaps."""
    days = (t - SPRING_EPOCH).total_seconds() / 86400
    return math.cos(2 * math.pi * days / SPRING_NEAP_DAYS)


def tides(day: date) -> list[tuple[datetime, str, float]]:
    """The day's high and low waters: (time to the minute, "high" | "low", height in metres)."""
    start = datetime.combine(day, datetime.min.time())
    n = math.floor((start - EPOCH_HW) / M2) - 1
    out = []
    for i in range(n, n + 4):
        for kind, t in (("high", EPOCH_HW + i * M2), ("low", EPOCH_HW + i * M2 + M2 / 2)):
            t = (t + timedelta(seconds=30)).replace(second=0, microsecond=0)
            if t.date() == day:
                s = _spring(t)
                h = HW_MEAN + HW_SWING * s if kind == "high" else LW_MEAN - LW_SWING * s
                out.append((t, kind, round(h, 1)))
    return sorted(out)


def ferry(day: date, map_state: str | None = None) -> dict:
    """The day's sailings: every one that runs, the gaps for low water, or why it's off."""
    if map_state in NO_FERRY_WEATHER:
        return {"suspended": f"no crossings today ({map_state})", "sailings": [], "gaps": []}
    lows = [t for t, kind, _ in tides(day) if kind == "low"]
    t = datetime.combine(day, datetime.min.time()).replace(hour=FERRY_FIRST[0], minute=FERRY_FIRST[1])
    until = t.replace(hour=FERRY_HALF_HOURLY_UNTIL[0], minute=FERRY_HALF_HOURLY_UNTIL[1])
    times = []
    while t <= until:
        times.append(t)
        t += timedelta(minutes=FERRY_EVERY_MIN)
    times.append(t.replace(hour=LAST_FERRY[0], minute=LAST_FERRY[1]))
    gap = timedelta(minutes=LOW_GAP_MIN)
    sailings = [s for s in times if all(abs(s - lw) > gap for lw in lows)]
    # a gap only matters between the day's first and last sailings ("from 08:00" covers an early one)
    gaps = [(lw - gap, lw + gap) for lw in lows if sailings and sailings[0] < lw < sailings[-1]]
    return {"suspended": "", "sailings": sailings, "gaps": gaps}


def for_prompt(day: date, map_state: str | None = None) -> str:
    """The facts a script may use, in words."""
    tt = tides(day)
    springs = _spring(datetime.combine(day, datetime.min.time()).replace(hour=12))

    def times(kind: str) -> str:
        return " and ".join(f"{t:%H:%M} ({h:.1f} m)" for t, k, h in tt if k == kind) or "none today"
    lines = [f"TIDES AT PORT WEXLEY TODAY: high water {times('high')}; low water {times('low')}"
             + ("; spring tides, so big ones" if springs > 0.6 else "; neap tides, so small ones" if springs < -0.6 else "")
             + "."]
    f = ferry(day, map_state)
    if f["suspended"]:
        lines.append(f"FERRY: {FERRY} across the Grey estuary is off: {f['suspended']}.")
    else:
        gaps = "; ".join(f"none {a:%H:%M}-{b:%H:%M} around low water" for a, b in f["gaps"])
        lines.append(f"FERRY: {FERRY} across the Grey estuary runs every half hour from "
                     f"{f['sailings'][0]:%H:%M}" + (f" ({gaps})" if gaps else "")
                     + f"; the last ferry leaves at {f['sailings'][-1]:%H:%M}.")
    lines.append("Use these exact times if the tide or the ferry comes up; don't invent others.")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    for t, kind, h in tides(d):
        print(f"{t:%a %d %b %H:%M}  {kind:<4}  {h:.1f} m")
    print()
    print(for_prompt(d))
