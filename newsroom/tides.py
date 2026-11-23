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


TURN_MIN = 30                      # this near a high or low water, the tide is on the turn: either way is fair


def _either_side(now: datetime) -> tuple[tuple[datetime, str, float], tuple[datetime, str, float]]:
    """The high or low water just gone and the next one to come, from yesterday's, today's and tomorrow's tables."""
    tt = [e for d in (-1, 0, 1) for e in tides(now.date() + timedelta(days=d))]
    return max((e for e in tt if e[0] <= now), key=lambda e: e[0]), min((e for e in tt if e[0] > now), key=lambda e: e[0])


def tide_way(now: datetime) -> str:
    """"rising", "falling", or "turning" within TURN_MIN of a high or low water."""
    (was, _, _), (nxt, kind, _) = _either_side(now)
    if min(now - was, nxt - now) <= timedelta(minutes=TURN_MIN):
        return "turning"
    return "rising" if kind == "high" else "falling"


def tide_now(now: datetime) -> str:
    """The tide as it is at `now`, for the prompt: on 2026-11-22 The Last Ferry had it "still making" and "very high
    against the steps" in six items while it ebbed to the 23:38 low, given only the times."""
    (_, was_kind, _), (nxt, kind, _) = _either_side(now)
    way = tide_way(now)
    if way == "turning":
        near = was_kind if now - _either_side(now)[0][0] <= timedelta(minutes=TURN_MIN) else kind
        return f"the tide is on the turn, at about {near} water"
    words = ("rising (the flood: coming in, making)" if way == "rising"
             else "falling (the ebb: going out, dropping)")
    return f"the tide is {words}, towards {kind} water {said(nxt, now)}"


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
    # The example is today's own first time: a fixed "twenty-five to five this afternoon" (Saturday's 16:35) was in
    # every prompt, and on Sunday 22 November The Last Ferry gave it as that afternoon's high water (17:25).
    example = re.sub(r" \(\d\d:\d\d\)$", "", said(tt[0][0], now)).removeprefix("at ") if tt else "five o'clock"
    lines = [f"TIDES AT PORT WEXLEY. It is {now:%H:%M} on {now:%A} {now.day} {now:%B}{size}.",
             "  TODAY, ALREADY GONE (say \"was\"): " + ("; ".join(gone) or "nothing yet") + ".",
             "  TODAY, STILL TO COME: " + ("; ".join(ahead) or "nothing more today") + ".",
             f"  TOMORROW, {nxt:%A} {nxt.day} {nxt:%B}: " + "; ".join(water(*e) for e in tides(nxt)) + ".",
             f"  RIGHT NOW {tide_now(now)}.",
             f"FERRY ({FERRY} across the Grey estuary). RIGHT NOW it is {ferry_now(now, map_state)}.",
             f"  TOMORROW: {ferry_then(nxt, now)}.",
             "Use these exact times if the tide or the ferry comes up; don't invent others, and don't work one out. "
             "Each time is given in the words to say, then its figures in brackets: say the words as they are given "
             f"(\"{example}\"), never the figures in brackets, and never "
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
_PAST_TO = re.compile(rf"(?<![-\w])({_MINS}|\d{{1,2}})(?: minutes?)? (past|to) ({_H12}|midnight|midday|noon)\b", re.I)
_OCLOCK = re.compile(rf"\b({_H12}) o'clock\b", re.I)
_DIGITS = re.compile(r"\b([01]?\d|2[0-3])[:.]([0-5]\d)\b")
_SPOKEN_24 = re.compile(rf"\b({_H24}) ({'|'.join(sorted(_TENS, key=len, reverse=True))})\b", re.I)
_BARE = re.compile(rf"\b(?:at|from|until|till|by|before|after)(?: just| about| around)? ({_H12}|midnight|midday|noon)\b"
                   r"(?! (?:point|degrees|metres|minutes|past|to|o'clock|and a|or|of|hundred|thousand|boats|people|years|miles)\b)"
                   r"(?!-)", re.I)
_CARRIES_ON = re.compile(r"\W*(?:it|it's|that|which|this|and it)\b", re.I)
SLACK_MIN = 5                      # "ten to eleven" for 22:48, "quarter past eleven" for 11:13
BARE_SLACK_MIN = 15                # "just before eleven" for 22:48, "from seven" for 07:00


def _hour(word: str) -> int:
    word = word.lower()
    return 0 if word in ("midnight", "midday", "noon", "twelve") else _NUM[word]


def clock_times(text: str) -> list[tuple[str, int, int]]:
    """The clock times a piece of text says, as (the words, minutes round a twelve-hour clock, how many minutes
    out it may be): "twenty-five to five" and "16:35" are both 275. A bare hour ("just before eleven") is looser.
    A 24-hour time read aloud ("sixteen thirty-five") has -1 for its minutes: it is never how anyone says it."""
    return [(w, mins, slack) for w, mins, slack, _ in _clock_spans(text)]


def _clock_spans(text: str) -> list[tuple[str, int, int, tuple[int, int]]]:
    """`clock_times`, each with where it is in the text."""
    found, taken = [], []

    def add(m, minutes, slack=SLACK_MIN):
        if not any(a < m.end() and m.start() < b for a, b in taken):
            taken.append(m.span())
            found.append((m.group(0), -1 if minutes is None else minutes % 720, slack, m.span()))
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
    return sorted(found, key=lambda f: f[3])


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
        after_water = False
        for sentence in re.split(r"(?<=[.!?])\s+", line or ""):
            # And the sentence after one about the tide: asked again over "twenty-five to five this afternoon",
            # The Last Ferry moved the tide into a sentence of its own ("The tide is making a fine show tonight. It
            # came up to five point four metres at twenty-five to five this afternoon", 2026-11-22).
            # Only one that carries it on ("It came up..."), not the next thing said ("...at two miles").
            about = bool(_WATER.search(sentence) or _WATER_LOWER.search(sentence))
            if not (about or (after_water and _CARRIES_ON.match(sentence))):
                continue
            after_water = about
            for words, minutes, slack in clock_times(sentence):
                if minutes < 0 or not any(min(abs(minutes - t), 720 - abs(minutes - t)) <= slack for t in ok):
                    slips.append(words)
    return list(dict.fromkeys(slips))


_PAST = re.compile(r"\b(was|were|came|went|reached|peaked|turned|left|made|ran|sailed|had|has been|have been|"
                   r"earlier|already|gone)\b", re.I)
_TO_COME = re.compile(r"\b(will|'ll|is due|are due|due|comes|coming|is at|are at|next|later|expected|leaves|sails|"
                      r"is|are|drops|rises)\b", re.I)
_RANGE = re.compile(r"\b(from|since|until|till|between|every)\s*(?:(?:about|around|just|roughly)\s+)?(?:before\s+|after\s+)?$",
                    re.I)                  # "no boat from just before ten o'clock until just before twenty to twelve"
_CLAUSE_CUT = re.compile(r",|;|:| and | so | but | with | then ")
_DAY_WORDS = re.compile(r"\b(tomorrow|today|tonight|this morning|this afternoon|this evening|in the morning)\b", re.I)
_PARTS = {"morning": (0, 12), "afternoon": (12, 18), "evening": (17, 24), "tonight": (17, 24)}   # 17:25 is either
_PART_SAID = re.compile(r"\b(?:this|tomorrow|in the|on \w+day) (morning|afternoon|evening)\b|\b(tonight)\b", re.I)
_GOES_ON = re.compile(r"^\W*(?:and\s+)?(?:again|then)\b", re.I)     # "and again at Y": the clause before's tense
_FERRY_DONE = re.compile(r"\b(stopped for the night|finished for the night|done for the night|made its last crossing|"
                         r"ran its last|last (?:ferry|crossing|sailing|boat) (?:has )?(?:gone|went|left|sailed)|"
                         r"no more (?:ferries|crossings|sailings) tonight)\b", re.I)
_FERRY_RUNNING = re.compile(r"\b(has been running|running since|been running|is already (?:rattling|crossing|running|"
                            r"out)|already (?:rattling|crossing) |is running|still running|out here on the (?:last )?"
                            r"(?:foot )?ferry|on board the ferry|aboard the ferry|catch the next one)\b", re.I)


def _near(minutes: int, t: datetime, slack: int) -> bool:
    d = abs(minutes - ((t.hour % 12) * 60 + t.minute))
    return min(d, 720 - d) <= slack


def _day_of(upto: str, now: datetime) -> str | None:
    """"tomorrow" or "today", from the last word for a day said up to here; "in the morning" said in the evening is
    tomorrow's."""
    days = _DAY_WORDS.findall(upto)
    if not days:
        return None
    last = days[-1].lower()
    if last == "tomorrow" or (last == "in the morning" and now.hour >= 17):
        return "tomorrow"
    return None if last == "in the morning" else "today"


def tense_slips(lines: list[str], now: datetime, map_state: str | None = None) -> list[str]:
    """What a script tells as done that is still to come, or as to come that is done, of the tide and the ferry: a
    note for each, to put to the writer. With the right times given, about one item in four still did it on the
    replays of 2026-11-22 ("the ferry has stopped for the night" at 21:41, an hour and a quarter early; "the first
    boat was seven o'clock this morning" at 06:31; "High water is at five this morning" at 06:00, an hour gone).

    Three kinds, none of which `clock_slips` sees, since each time is one of the times given:
    - the ferry finished for the night before its last boat, or running (or somebody on it) while it isn't;
    - a tide or ferry time told in the past ("came in at") while it is to come, or as to come ("is due", "comes",
      "is at") once it is gone, from the words in its own clause (a clause with none takes the one before's);
    - one of today's times given as tomorrow's ("High water tomorrow comes at twenty to five in the morning": today's).
    A time that could be either, the time of day itself, a question, and a time that opens or closes a span ("from
    seven", "until twenty past ten") are left."""
    f = ferry(now.date(), map_state)
    first, last = (f["sailings"][0], f["sailings"][-1]) if f["sailings"] else (None, None)
    in_gap = any(a <= now <= b for a, b in f["gaps"])
    running = bool(first) and first <= now <= last and not in_gap and not f["suspended"]
    times_given = given(now, map_state)[1:]
    notes = []
    for line in lines:
        for sentence in re.split(r"(?<=[.!?])\s+", line or ""):
            if not (_WATER.search(sentence) or _WATER_LOWER.search(sentence)) or sentence.rstrip().endswith("?"):
                continue
            if re.search(r"\b(ferry|ferries|crossing|sailing|boat)\b", sentence, re.I) and "tomorrow" not in sentence.lower():
                if last and now < last and not f["suspended"] and _FERRY_DONE.search(sentence):
                    notes.append(f"\"{sentence.strip()}\": the ferry has not finished, its last boat leaves "
                                 f"{said(last, now)}")
                elif not running and (m := _FERRY_RUNNING.search(sentence)) and not (
                        m.group(0).lower().startswith(("is running", "catch")) and first and now < first
                        and "now" not in sentence.lower()):
                    notes.append(f"\"{sentence.strip()}\": the ferry is not running right now ({ferry_now(now, map_state)})")
                elif first and now < first and re.search(r"\b(has been running|running since|first (?:ferry|boat) "
                                                         r"(?:was|went|left|sailed))\b", sentence, re.I):
                    notes.append(f"\"{sentence.strip()}\": no ferry has sailed yet today; the first is {said(first, now)}")
            spans = _clock_spans(sentence)
            tense = None                       # the clause before's: "came in at X, and again at Y"
            for i, (words, minutes, slack, (a, b)) in enumerate(spans):
                lo = spans[i - 1][3][1] if i else 0
                hi = spans[i + 1][3][0] if i + 1 < len(spans) else len(sentence)
                cuts = [m.end() for m in _CLAUSE_CUT.finditer(sentence, lo, a)]
                start = cuts[-1] if cuts else lo
                tail = _CLAUSE_CUT.split(sentence[b:hi], maxsplit=1)[0]
                clause = sentence[start:b] + tail
                # The past may come after the time ("at twenty-five to five was five point two metres"), the future
                # only before it: "The morning high water at five is five point three metres" is its height.
                past, to_come = _PAST.search(clause), _TO_COME.search(sentence[start:a])
                if past and not to_come:
                    tense = "past"
                elif to_come and not past:
                    tense = "to come"
                elif past or not _GOES_ON.search(sentence[start:a]):
                    tense = None
                if minutes < 0 or _RANGE.search(sentence[start:a]) or _near(minutes, now, slack):
                    continue
                near = [t for t in times_given if _near(minutes, t, slack)]
                day = _day_of(sentence[:b] + tail, now)
                # "this afternoon", "tomorrow morning", "tonight": not "the evening high water at twenty-five to five"
                for part in {(m.group(1) or m.group(2)).lower() for m in _PART_SAID.finditer(clause)}:
                    h0, h1 = _PARTS[part]
                    if near:
                        theirs = [t for t in near if h0 <= t.hour < h1]
                        if not theirs:     # "high water near half past four tomorrow morning": 16:35's figures
                            notes.append(f"\"{words}\" in the {part} is none of the times given (the nearest is "
                                         f"{near[0]:%H:%M}): use a time from TIDES or FERRY as it is given")
                        near = theirs
                if day == "tomorrow":
                    theirs = [t for t in near if t.date() > now.date()]
                    if near and not theirs:
                        notes.append(f"\"{words}\" is one of today's times ({near[0]:%H:%M}), not tomorrow's: TOMORROW's "
                                     "are given on their own line")
                        continue
                    near = theirs
                elif day == "today":
                    near = [t for t in near if t.date() == now.date()]
                if not near or len({t <= now for t in near}) > 1 or tense is None:
                    continue
                gone = near[0] <= now
                if gone and tense == "to come":
                    notes.append(f"\"{words}\" is already gone at {now:%H:%M}: say it as past (\"was\", \"came\")")
                elif not gone and tense == "past":
                    notes.append(f"\"{words}\" is still to come at {now:%H:%M}: say it as to come")
    return list(dict.fromkeys(notes))


_RISING = re.compile(r"\b(?:(?:tide|water)(?:'s| is)? (?:still |now |just )?(?:making|rising|coming in|coming up|creeping up|"
                     r"flooding|on the flood|on its way (?:in|up))|(?<!\ba )(?:rising|incoming|flood) tide|tide coming in|"
                     r"(?:on|with) the flood)\b", re.I)
_FALLING = re.compile(r"\b(?:(?:tide|water)(?:'s| is)? (?:still |now |just )?(?:ebbing|dropping|falling|going out|draining|"
                      r"receding|running out|on its way out|on the ebb)|(?<!\ba )(?:falling|outgoing|ebb) tide|"
                      r"(?:on|with) the ebb|tide going out)\b", re.I)
_HIGH_NOW = re.compile(r"\b(?:tide|water)(?:'s| is| still)?(?: runs| sits| stands| stays)? (?:very |right |still |now |good and |nice and )?(?:high|up)\b"
                       r"(?! (?:water|tide|at|tomorrow|this|again)\b)", re.I)
_LOW_NOW = re.compile(r"\b(?:tide|water)(?:'s| is| still)?(?: runs| sits| stands| stays)? (?:very |right |still |now |well )?(?:low|out)\b"
                      r"(?! (?:water|tide|at|tomorrow|this|again)\b)", re.I)
_NOT_NOW = re.compile(r"\b(?:tomorrow|was|were|had|earlier|this morning|this afternoon|in the morning|yesterday|will|'ll|when|if|by the "
                      r"time|until|once)\b", re.I)
HIGH_LOW_NEAR = timedelta(hours=2)   # this near low water the tide isn't "high", and the reverse


def state_slips(lines: list[str], now: datetime) -> list[str]:
    """What a script says of the tide's state at this minute that the table says it isn't: rising while it falls, or
    falling while it rises; high near low water, or low near high water. A note for each, to put to the writer. On
    2026-11-22 The Last Ferry had "the tide's still making" at 22:27, "very high against the steps" at 22:55 and "still
    runs high" at 22:57, while it ebbed to the 23:38 low (high water 17:25). Nothing is judged on the turn, in a
    question, or in a sentence about another time ("tomorrow", "was", "will", "when")."""
    way = tide_way(now)
    (was, was_kind, _), (nxt, kind, _) = _either_side(now)
    near_low = (was_kind == "low" and now - was <= HIGH_LOW_NEAR) or (kind == "low" and nxt - now <= HIGH_LOW_NEAR)
    near_high = (was_kind == "high" and now - was <= HIGH_LOW_NEAR) or (kind == "high" and nxt - now <= HIGH_LOW_NEAR)
    notes = []
    for line in lines:
        for sentence in re.split(r"(?<=[.!?])\s+", line or ""):
            if sentence.rstrip().endswith("?") or _NOT_NOW.search(sentence):
                continue
            s = sentence.strip()
            if way == "falling" and (m := _RISING.search(sentence)):
                notes.append(f"\"{s}\": \"{m.group(0)}\", but the tide is falling right now (towards {kind} water "
                             f"{said(nxt, now)})")
            elif way == "rising" and (m := _FALLING.search(sentence)):
                notes.append(f"\"{s}\": \"{m.group(0)}\", but the tide is rising right now (towards {kind} water "
                             f"{said(nxt, now)})")
            elif near_low and (m := _HIGH_NOW.search(sentence)):
                notes.append(f"\"{s}\": \"{m.group(0)}\", but it is near low water right now")
            elif near_high and (m := _LOW_NOW.search(sentence)):
                notes.append(f"\"{s}\": \"{m.group(0)}\", but it is near high water right now")
    return list(dict.fromkeys(notes))


if __name__ == "__main__":
    import sys

    d = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else date.today()
    for t, kind, h in tides(d):
        print(f"{t:%a %d %b %H:%M}  {kind:<4}  {h:.1f} m")
    print()
    print(for_prompt(d))
