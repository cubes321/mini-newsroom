"""Port Wexley's tides and the Saltby foot ferry, worked out rather than written by the model.

The model used to invent the morning tide, and a different one each time. Here it is
arithmetic: a semi-diurnal tide (high water every 12 h 25 min, so about 50 minutes later
each day) whose heights swell and shrink over the 14.8-day spring-neap cycle, from a
fixed first high water. Fictional, but consistent: every segment on a given day agrees,
and tomorrow follows on from today.

The foot ferry crosses the Grey estuary to Saltby every half hour from 07:00, the last
one at 23:15 (the late show's namesake). The Saltby landing dries out, so there are no
crossings within LOW_GAP_MIN of low water, and none at all in a storm or fog. The last ferry
always sails after The Last Ferry starts at 22:00: when low water covers 23:15 it waits for the
tide, or goes as the landing dries if waiting would take it past midnight (on 2026-11-06 low water
at 22:36 made it 21:30, and the show kept saying so).

    python -m newsroom.tides [YYYY-MM-DD]
"""
from __future__ import annotations

import math
import re
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


def last_ferry(at: datetime, lows: list[datetime]) -> datetime:
    """The last sailing: at `at`, or, with low water too near, just after the landing floods again
    (rounded up to five minutes), or just before it dries if that would be past midnight."""
    gap = timedelta(minutes=LOW_GAP_MIN)
    lw = next((lw for lw in lows if abs(at - lw) <= gap), None)
    if lw is None:
        return at
    after = lw + gap + timedelta(minutes=1)
    after += timedelta(minutes=-after.minute % 5)
    if after.date() == at.date() and after.hour * 60 + after.minute <= 23 * 60 + 55:
        return after
    before = lw - gap - timedelta(minutes=1)
    return before - timedelta(minutes=before.minute % 5)


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
    gap = timedelta(minutes=LOW_GAP_MIN)
    sailings = [s for s in times if all(abs(s - lw) > gap for lw in lows)]
    last = last_ferry(t.replace(hour=LAST_FERRY[0], minute=LAST_FERRY[1]), lows)
    sailings = [s for s in sailings if s <= last - timedelta(minutes=FERRY_EVERY_MIN)] + [last]   # it replaces one just before
    # a gap only matters between the day's first and last sailings ("from 08:00" covers an early one)
    gaps = [(lw - gap, lw + gap) for lw in lows if sailings and sailings[0] < lw < sailings[-1]]
    return {"suspended": "", "sailings": sailings, "gaps": gaps}


def _water(tt: list, kind: str) -> str:
    return " and ".join(f"{t:%H:%M} ({h:.1f} m)" for t, k, h in tt if k == kind) or "none"


def _ferry_day(f: dict) -> str:
    """A day's ferry in a clause: when it runs, its gaps, its last boat; or why it is off."""
    if f["suspended"]:
        return f"off: {f['suspended']}"
    gaps = "; ".join(f"none {a:%H:%M}-{b:%H:%M} around low water" for a, b in f["gaps"])
    return (f"every half hour from {f['sailings'][0]:%H:%M}" + (f" ({gaps})" if gaps else "")
            + f"; the last ferry leaves at {f['sailings'][-1]:%H:%M}")


def said(t: datetime, now: datetime) -> str:
    """A time as it is said at `now`, with the figures after it: "at twenty-five to five this afternoon (16:35)",
    "just before ten to eleven tonight (22:48)", "at five o'clock tomorrow morning (05:00)". Told "16:35" alone, Haiku said "twenty-five past four", and "five past
    five" for 05:00 (the replay of 2026-11-22): the words are worked out here, as the clock's are (schedule.py)."""
    from .schedule import spoken_time

    part = ("morning" if t.hour < 12 else "afternoon" if t.hour < 17 else "evening" if t.hour < 21 else "night")
    days = (t.date() - now.date()).days
    when = ("tonight" if part == "night" else f"this {part}") if days == 0 else (
        f"tomorrow {part}" if days == 1 else f"yesterday {part}" if days == -1 else f"on {t:%A} {part}")
    words = spoken_time(t.timestamp())
    words = words.replace("coming up to ", "just before ") if words.startswith(("coming up to ", "just after ")) else f"at {words}"
    return f"{words} {when} ({t:%H:%M})"


def _gap(a: datetime, b: datetime, now: datetime) -> str:
    return f"no ferry from {said(a, now).removeprefix('at ')} until {said(b, now).removeprefix('at ')}, round low water"


def ferry_now(now: datetime, map_state: str | None = None) -> str:
    """The ferry at this minute, in words: off, not yet running, in its low-water gap, running, or finished."""
    f = ferry(now.date(), map_state)
    if f["suspended"]:
        return f"not running at all today: {f['suspended']}"
    first, last = f["sailings"][0], f["sailings"][-1]
    if now < first:                       # with the rest of its day, or tomorrow's gap is taken for today's
        gaps = "".join(f"; then {_gap(a, b, now)}" for a, b in f["gaps"])
        return (f"NOT running yet, and none has sailed today: the first ferry is {said(first, now)}{gaps}; the last "
                f"ferry leaves {said(last, now)}")
    if now > last:
        return f"finished for the night: the last ferry left {said(last, now)}"
    for a, b in f["gaps"]:
        if a <= now <= b:
            back = next((x for x in f["sailings"] if x >= b), last)
            return (f"NOT running: the Saltby landing is dry, {_gap(a, b, now)}; the next one is {said(back, now)}"
                    + (f", and the last {said(last, now)}" if back != last else ", which is the last ferry"))
    ahead = next(((a, b) for a, b in f["gaps"] if a > now), None)
    return ("running, every half hour" + (f"; then {_gap(*ahead, now)}" if ahead else "")
            + f"; the last ferry leaves {said(last, now)}")


def ferry_then(day: date, now: datetime) -> str:
    """Another day's ferry, in the words to say: its first boat, its gaps, its last."""
    f = ferry(day)
    if f["suspended"]:
        return f"off: {f['suspended']}"
    gaps = "".join(f"; {_gap(a, b, now)}" for a, b in f["gaps"])
    return (f"every half hour, the first {said(f['sailings'][0], now)}{gaps}; the last ferry leaves "
            f"{said(f['sailings'][-1], now)}")


def for_prompt(day: date, map_state: str | None = None, now: datetime | None = None) -> str:
    """The facts a script may use, in words. With `now` (when the item airs), today's waters are split into those
    gone and those to come, the ferry is given as it is at that minute, and tomorrow's table comes too.

    Given today's table alone, the forecasts of the 2026-11-21 night read it out as tomorrow's ("High water tomorrow
    comes at twenty to five in the morning, five point one metres": Sunday's was 05:00, 5.3 m), told the afternoon's
    high water as still to come at seven in the evening, and had Miles "out here on the last ferry" at 22:24, in the
    low-water gap: 13 of the evening's 14 weathers had a tide or the ferry wrong."""
    tt = tides(day)
    springs = _spring(datetime.combine(day, datetime.min.time()).replace(hour=12))
    size = ("; spring tides, so big ones" if springs > 0.6 else "; neap tides, so small ones" if springs < -0.6 else "")
    f = ferry(day, map_state)
    if now is None:
        lines = [f"TIDES AT PORT WEXLEY TODAY: high water {_water(tt, 'high')}; low water {_water(tt, 'low')}{size}."
                 .replace("none;", "none today;").replace("water none.", "water none today.")]
        if f["suspended"]:
            lines.append(f"FERRY: {FERRY} across the Grey estuary is off: {f['suspended']}.")
        else:
            lines.append(f"FERRY: {FERRY} across the Grey estuary runs {_ferry_day(f)}.")
        lines.append("Use these exact times if the tide or the ferry comes up; don't invent others.")
        return "\n".join(lines)
    nxt = day + timedelta(days=1)
    water = lambda t, k, h: f"{k} water {said(t, now)}, {h:.1f} m"  # noqa: E731
    gone = [water(*e) for e in tt if e[0] <= now]
    ahead = [water(*e) for e in tt if e[0] > now]
    lines = [f"TIDES AT PORT WEXLEY. It is {now:%H:%M} on {now:%A} {now.day} {now:%B}{size}.",
             "  TODAY, ALREADY GONE (say \"was\"): " + ("; ".join(gone) or "nothing yet") + ".",
             "  TODAY, STILL TO COME: " + ("; ".join(ahead) or "nothing more today") + ".",
             f"  TOMORROW, {nxt:%A} {nxt.day} {nxt:%B}: " + "; ".join(water(*e) for e in tides(nxt)) + ".",
             f"FERRY ({FERRY} across the Grey estuary). RIGHT NOW it is {ferry_now(now, map_state)}.",
             f"  TOMORROW: {ferry_then(nxt, now)}.",
             "Use these exact times if the tide or the ferry comes up; don't invent others, and don't work one out. "
             "Each time is given in the words to say, then its figures in brackets: say the words as they are given "
             "(\"twenty-five to five this afternoon\"), never the figures (not \"sixteen thirty-five\"), and never "
             "change them. A time already gone is told as past, one to come as to come, and TOMORROW's are only ever "
             "tomorrow's: today's are never given as tomorrow's. Nobody is on the ferry, or just off it, while it is "
             "not running."]
    return "\n".join(lines)


# ------------------------------------------------------------------ what a script said

_NUM = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen "
    "eighteen nineteen twenty".split())}
_NUM.update({"twenty-one": 21, "twenty-two": 22, "twenty-three": 23, "twenty-four": 24, "twenty-five": 25,
             "twenty-six": 26, "twenty-seven": 27, "twenty-eight": 28, "twenty-nine": 29, "quarter": 15, "a quarter": 15,
             "half": 30})
_TENS = {"oh five": 5, "ten": 10, "fifteen": 15, "twenty": 20, "twenty-five": 25, "thirty": 30, "thirty-five": 35,
         "forty": 40, "forty-five": 45, "fifty": 50, "fifty-five": 55, "forty-eight": 48, "thirty-eight": 38,
         "twenty-two": 22, "thirteen": 13}
_H12 = "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve"
_H24 = _H12 + "|thirteen|fourteen|fifteen|sixteen|seventeen|eighteen|nineteen|twenty-one|twenty-two|twenty-three|twenty"
_MINS = "|".join(sorted((k for k in _NUM if k not in ("zero",)), key=len, reverse=True))
_WATER = re.compile(r"\b(high water|low water|high tide|low tide|ferry|ferries|crossing|crossings|sailing|sailings)\b", re.I)
_WATER_LOWER = re.compile(r"\b(tides?|[Tt]he low|[Tt]he high|landing)\b")       # lower case only: not "the Tides"
_PAST_TO = re.compile(rf"\b({_MINS}|\d{{1,2}})(?: minutes?)? (past|to) ({_H12}|midnight|midday|noon)\b", re.I)
_OCLOCK = re.compile(rf"\b({_H12}) o'clock\b", re.I)
_DIGITS = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
_SPOKEN_24 = re.compile(rf"\b({_H24}) ({'|'.join(sorted(_TENS, key=len, reverse=True))})\b", re.I)
_BARE = re.compile(rf"\b(?:at|from|until|till|by|before|after)(?: just| about| around)? ({_H12}|midnight|midday|noon)\b"
                   r"(?! (?:point|degrees|metres|minutes|past|to|o'clock|and a|or|of|hundred|thousand|boats|people|years)\b)"
                   r"(?!-)", re.I)
SLACK_MIN = 5                      # "ten to eleven" for 22:48, "quarter past eleven" for 11:13
BARE_SLACK_MIN = 15                # "just before eleven" for 22:48, "from seven" for 07:00


def _hour(word: str) -> int:
    word = word.lower()
    return 0 if word in ("midnight", "midday", "noon", "twelve") else _NUM[word]


def clock_times(text: str) -> list[tuple[str, int, int]]:
    """The clock times a piece of text says, as (the words, minutes round a twelve-hour clock, how many minutes
    out it may be): "twenty-five to five" and "16:35" are both 275. A bare hour ("just before eleven") is looser.
    A 24-hour time read aloud ("sixteen thirty-five") has -1 for its minutes: it is never how anyone says it."""
    found, taken = [], []

    def add(m, minutes, slack=SLACK_MIN):
        if not any(a < m.end() and m.start() < b for a, b in taken):
            taken.append(m.span())
            found.append((m.group(0), -1 if minutes is None else minutes % 720, slack))
    for m in _PAST_TO.finditer(text):
        n = int(m.group(1)) if m.group(1).isdigit() else _NUM[m.group(1).lower()]
        h = _hour(m.group(3))
        add(m, h * 60 + n if m.group(2).lower() == "past" else h * 60 - n)
    for m in _SPOKEN_24.finditer(text):
        h = _NUM[m.group(1).lower()]
        add(m, None if h > 12 else h * 60 + _TENS[m.group(2).lower()])
    for m in _DIGITS.finditer(text):
        add(m, int(m.group(1)) * 60 + int(m.group(2)))
    for m in _OCLOCK.finditer(text):
        add(m, _hour(m.group(1)) * 60)
    for m in _BARE.finditer(text):
        add(m, _hour(m.group(1)) * 60, BARE_SLACK_MIN)
    return found


def given(now: datetime, map_state: str | None = None) -> list[datetime]:
    """Every time `for_prompt` gives the writer at `now`: today's and tomorrow's waters, each day's first and last
    ferry and the edges of its gaps, and the hour itself."""
    out = [now]
    for day in (now.date(), now.date() + timedelta(days=1)):
        out += [t for t, _, _ in tides(day)]
        f = ferry(day, map_state if day == now.date() else None)
        if f["sailings"]:
            out += [f["sailings"][0], f["sailings"][-1]] + [x for gap in f["gaps"] for x in gap]
    return out


def clock_slips(lines: list[str], now: datetime, map_state: str | None = None) -> list[str]:
    """The clock times said in a sentence about the tide or the ferry that are none of the times given, within
    SLACK_MIN minutes: the words, as said. The facts were right and Haiku still reworded one now and then: "twenty
    to eleven" for 22:48, "five to twelve" for 12:03, a 21:58 gap as "two minutes to two" (the replays of
    2026-11-22)."""
    ok = [(t.hour % 12) * 60 + t.minute for t in given(now, map_state)]
    slips = []
    for line in lines:
        for sentence in re.split(r"(?<=[.!?])\s+", line or ""):
            if not (_WATER.search(sentence) or _WATER_LOWER.search(sentence)):
                continue
            for words, minutes, slack in clock_times(sentence):
                if minutes < 0 or not any(min(abs(minutes - t), 720 - abs(minutes - t)) <= slack for t in ok):
                    slips.append(words)
    return list(dict.fromkeys(slips))


if __name__ == "__main__":
    import sys

    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    for t, kind, h in tides(d):
        print(f"{t:%a %d %b %H:%M}  {kind:<4}  {h:.1f} m")
    print()
    print(for_prompt(d))
