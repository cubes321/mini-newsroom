"""Port Wexley's year: the town's annual events, worked out from the date like the council and the sport.

Hand-written events (approved by the user on 2026-11-03), each with a rule that gives its days in a
year: a fixed date, the nth weekday of a month, an offset from Easter, or a council meeting
(council.meets_on). No model and nothing saved: the same day gives the same calendar everywhere.

Each writer gets at most RATION events, the nearest in the next AHEAD_DAYS that suit its show, and is
told to mention no event the calendar doesn't hold (`for_show`). The desk and the back office see
the whole fortnight, with the council, the fixtures and the auction gathered in (`for_editor`), so a
thread's NEXT development can be set for a real date (`due` reads the date back). SEVENTEXT has a
What's On page from the same view.

The charter (14 March 1871), the Mariner's Gale (9 December 1910), the cannery's last shift
(25 September 1981) and the market's day (since 1890) are canon from here on.

    python -m newsroom.calendar [YYYY-MM-DD]
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Callable

from . import council, darts, quay, rugby, sport

AHEAD_DAYS = 5                           # a writer hears of events this many days ahead
RATION = 2                               # and of at most this many, the nearest first
COMING_DAYS = 14                         # the desk's and SEVENTEXT's view ahead

Span = tuple[date, date]                 # the first and last day, inclusive


# ------------------------------------------------------------------- the rules

def nth(y: int, month: int, weekday: int, n: int) -> date:
    """The nth `weekday` (Monday 0) of the month."""
    d = date(y, month, 1)
    return d + timedelta(days=(weekday - d.weekday()) % 7, weeks=n - 1)


def last(y: int, month: int, weekday: int) -> date:
    """The last `weekday` of the month."""
    d = date(y + month // 12, month % 12 + 1, 1) - timedelta(days=1)
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def on_or_before(d: date, weekday: int) -> date:
    return d - timedelta(days=(d.weekday() - weekday) % 7)


def on_or_after(d: date, weekday: int) -> date:
    return d + timedelta(days=(weekday - d.weekday()) % 7)


def easter(y: int) -> date:
    """Easter Sunday (the Gregorian computus)."""
    a, (b, c) = y % 19, divmod(y, 100)
    d, e = divmod(b, 4)
    g = (b - (b + 8) // 25 + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l_ = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l_) // 451
    month, day = divmod(h + l_ - 7 * m + 114, 31)
    return date(y, month, day + 1)


def _day(f: Callable[[int], date | None]) -> Callable[[int], Span | None]:
    """A one-day event."""
    def span(y: int) -> Span | None:
        d = f(y)
        return (d, d) if d else None
    return span


def _week(f: Callable[[int], date]) -> Callable[[int], Span]:
    """Monday to Friday of the week `f` gives the Monday of: a half-term."""
    return lambda y: (f(y), f(y) + timedelta(days=4))


def _meeting(start: date, end: date) -> date | None:
    """The first council meeting in [start, end], or None (none yet: meets_on is False before the first)."""
    return next((d for d in (start + timedelta(days=k) for k in range((end - start).days + 1)) if council.meets_on(d)),
                None)


def _budget(y: int) -> date | None:
    """The last council meeting in February."""
    feb = [date(y, 2, 1) + timedelta(days=k) for k in range((date(y, 3, 1) - date(y, 2, 1)).days)]
    return next((d for d in reversed(feb) if council.meets_on(d)), None)


def _spring_term(y: int) -> date:
    return on_or_after(date(y, 1, 4), 0)


def _autumn_term(y: int) -> date:
    return nth(y, 9, 2, 1)


# ------------------------------------------------------------------- the events

@dataclass(frozen=True)
class Event:
    name: str
    span: Callable[[int], Span | None]   # its days in a year (starting that year), or None if not held
    about: str                           # one line for the writers and the page
    shows: tuple[str, ...]               # the show ids it suits (schedule.SHOWS)
    at: str = ""                         # its start on the day ("18:00"), if `about` names one: once that
                                         # has passed it is under way or over, not to come (for_prompt)


NEWS, BREAKFAST, PHONEIN, QUAYSIDE, OUTABOUT, ROCKPOOL = "news", "breakfast", "phonein", "quayside", "outabout", "rockpool"
SPORT, MAGAZINE, INQUIRY, PANEL, CHAMBER, LATE = "sport", "magazine", "inquiry", "panel", "chamber", "late"
SCHOOL = (BREAKFAST, ROCKPOOL, OUTABOUT)

EVENTS: tuple[Event, ...] = (
    # Winter
    Event("New Year's Day Dip", _day(lambda y: date(y, 1, 1)),
          "the Tidewater Swimming Club's sea swim off the harbour beach at eleven, in fancy dress, for the lifeboat",
          (NEWS, BREAKFAST, OUTABOUT, ROCKPOOL), at="11:00"),
    Event("spring term starts", _day(_spring_term),
          "Greymouth Academy and the primary schools go back", (BREAKFAST, ROCKPOOL)),
    Event("the Saltby Wassail", _day(lambda y: date(y, 1, 17)),
          "Old Twelfth Night: Saltby wassails the orchard by the church, toast in the branches, cider, and a lot "
          "of noise to wake the trees", (OUTABOUT, MAGAZINE, LATE)),
    Event("February half-term", _week(lambda y: nth(y, 2, 0, 3)), "the schools are out for the week", SCHOOL),
    Event("the Pancake Race", _day(lambda y: easter(y) - timedelta(days=47)),
          "Shrove Tuesday: down Harrow Street at noon, frying pans and all; Dev the baker supplies the batter",
          (NEWS, BREAKFAST, OUTABOUT, ROCKPOOL, MAGAZINE), at="12:00"),
    Event("budget night", _day(_budget),
          "full council sets the year's budget and the council tax, live on The Chamber",
          (NEWS, CHAMBER, QUAYSIDE, PANEL, PHONEIN)),
    Event("Charter Day", _day(lambda y: date(y, 3, 14)),
          "the town's birthday (the charter of 14 March 1871): the mayor reads the charter on the Town Hall "
          "steps, and the Town Hall clock is wound by hand, once a year", (NEWS, BREAKFAST, MAGAZINE, LATE)),
    # Spring
    Event("the Easter holidays", lambda y: (easter(y) - timedelta(days=6), easter(y) + timedelta(days=5)),
          "the schools are out for a fortnight; the Easter egg trail is on the Saltby green on Easter Saturday",
          SCHOOL),
    Event("the Blessing of the Fleet", _day(lambda y: nth(y, 5, 6, 1)),
          "the vicar and the harbourmaster bless the boats from the quay, the fleet dressed in bunting",
          (NEWS, QUAYSIDE, BREAKFAST, MAGAZINE)),
    Event("the local elections", _day(council.election_day),
          "the town votes for its council; Helen Strand is standing for a third term",
          (NEWS, PHONEIN, PANEL, INQUIRY, MAGAZINE)),
    Event("mayor-making", _day(lambda y: _meeting(date(y, 5, 10), date(y, 6, 7))),
          "council's annual meeting: the mayor is chosen and takes the chain", (NEWS, CHAMBER, MAGAZINE)),
    Event("May half-term", _week(lambda y: last(y, 5, 0)), "the schools are out for the week", SCHOOL),
    # Summer
    Event("the Ferry Oar", _day(lambda y: nth(y, 6, 5, 1)),
          "Wexley Rowing Club race Saltby's gig across the estuary and back for the Ferry Oar", (SPORT, NEWS, OUTABOUT)),
    Event("Lifeboat Day", _day(lambda y: nth(y, 6, 5, 3)),
          "open day at the lifeboat station: a launch at two, the boathouse open, the lifeboat tin on the bandstand",
          (NEWS, BREAKFAST, ROCKPOOL, OUTABOUT), at="14:00"),
    Event("Lighthouse Night", _day(lambda y: date(y, 6, 23)),
          "Midsummer Eve: the Greymouth lighthouse keeps its door open until midnight, the one night of the year",
          (OUTABOUT, MAGAZINE, LATE)),
    Event("Market Day", _day(lambda y: nth(y, 7, 5, 2)),
          "Harrow Street market's birthday (it began in 1890): the cheese wheel rolled down Harrow Street, stalls "
          "till dark", (NEWS, QUAYSIDE, OUTABOUT, MAGAZINE)),
    Event("the summer holidays",
          lambda y: (on_or_before(date(y, 7, 23), 4), _autumn_term(y) - timedelta(days=1)),
          "the schools are out for the summer", SCHOOL),
    Event("Regatta Week", lambda y: (nth(y, 8, 5, 2) - timedelta(days=5), nth(y, 8, 5, 2)),
          "racing in the harbour and the estuary all week; Regatta Saturday ends with fireworks off the harbour wall",
          (NEWS, SPORT, OUTABOUT, MAGAZINE, ROCKPOOL, BREAKFAST)),
    Event("the Crabbing Championship", _day(lambda y: last(y, 8, 0)),
          "the August bank holiday: lines off the quay wall, an hour to fill a bucket, and every crab goes back",
          (ROCKPOOL, OUTABOUT, BREAKFAST)),
    # Autumn
    Event("autumn term starts", _day(_autumn_term), "the schools go back", (BREAKFAST, ROCKPOOL)),
    Event("the Saltby Show", _day(lambda y: nth(y, 9, 5, 2)),
          "the village show on the green: sheep, marrows, the dog show and the tug-of-war against Port Wexley",
          (OUTABOUT, MAGAZINE, BREAKFAST)),
    Event("the cannery's last shift", _day(lambda y: date(y, 9, 25)),
          "the anniversary of the day the cannery closed, 25 September 1981; the old workers meet at the Cannery Tap",
          (MAGAZINE, LATE, NEWS)),
    Event("the Herring Supper", _day(lambda y: nth(y, 10, 4, 1)),
          "the fishing families' supper in the fish market hall: the first herring of the season",
          (QUAYSIDE, MAGAZINE, OUTABOUT)),
    Event("the Wexley Book Festival", lambda y: (nth(y, 10, 5, 2), nth(y, 10, 5, 2) + timedelta(days=1)),
          "authors at the library and the Town Hall, Saturday and Sunday", (OUTABOUT, MAGAZINE, LATE)),
    Event("October half-term", _week(lambda y: last(y, 10, 0)), "the schools are out for the week", SCHOOL),
    Event("the Halloween Cannery Walk", _day(lambda y: date(y, 10, 31)),
          "the ghost tour's one big night: Pell's Cannery Ghost Tours, with lanterns", (LATE, OUTABOUT, ROCKPOOL)),
    Event("Bonfire Night", _day(lambda y: date(y, 11, 5)),
          "the town bonfire and fireworks on the Salting, gates at six", (NEWS, BREAKFAST, ROCKPOOL, MAGAZINE, PHONEIN),
          at="18:00"),
    Event("Remembrance Sunday", _day(lambda y: nth(y, 11, 6, 2)),
          "the parade leaves the Town Hall at quarter to eleven for the war memorial: the two minutes' silence at "
          "eleven, the wreaths, then the lifeboat crew lay a wreath on the water off the harbour",
          (NEWS, BREAKFAST), at="10:45"),
    Event("the Christmas lights", _day(lambda y: last(y, 11, 4)),
          "Harrow Street's lights switched on at six by someone the children choose; carols on the bandstand",
          (NEWS, BREAKFAST, ROCKPOOL, OUTABOUT, MAGAZINE), at="18:00"),
    # December
    Event("the Mariner's Gale", _day(lambda y: date(y, 12, 9)),
          "the anniversary of the lifeboat's first great rescue, 9 December 1910: 22 saved from the barque Ellen "
          "Vance; the boathouse bell is rung at noon", (NEWS, MAGAZINE, LATE), at="12:00"),
    Event("the Christmas holidays",
          lambda y: (on_or_before(date(y, 12, 20), 4), _spring_term(y + 1) - timedelta(days=1)),
          "the schools are out for Christmas", (BREAKFAST, ROCKPOOL)),
    # Christmas Eve, Christmas Day and Boxing Day are days of their own on channel 7 (christmas.py).
    Event("Christmas Eve", _day(lambda y: date(y, 12, 24)),
          "carols on the quay at seven, and the bells at midnight", (MAGAZINE, LATE)),
    Event("Christmas Day", _day(lambda y: date(y, 12, 25)),
          "the Christmas Day swim on the seafront at eleven, and the Mayor's Christmas message at three",
          (BREAKFAST, MAGAZINE, LATE)),
    Event("Boxing Day", _day(lambda y: date(y, 12, 26)),
          "the Boxing Day dip on the seafront at eleven, and the sales on Harrow Street", (BREAKFAST, MAGAZINE)),
    Event("the Harbour of Lights", _day(lambda y: on_or_before(date(y, 12, 24), 5)),
          "the fishing boats, strung with lights, parade round the harbour after dark",
          (NEWS, QUAYSIDE, OUTABOUT, MAGAZINE, ROCKPOOL)),
)


@dataclass(frozen=True)
class On:
    """An event's days in one year."""
    event: Event
    first: date
    last: date

    def when(self, day: date) -> str:
        """'today', 'tomorrow', 'on Thursday 5 November', 'until Friday 30 October', 'from Monday 15 to
        Friday 19 February', as said on `day`."""
        if self.first <= day:
            if self.last == day:
                return "today"
            return f"{'from today ' if self.first == day else ''}until {_date(self.last)}"
        start = "tomorrow" if self.first == day + timedelta(days=1) else f"on {_date(self.first)}"
        return start if self.first == self.last else f"from {_date(self.first)} to {_date(self.last)}"

    def short(self, day: date) -> str:
        """'Regatta Week, to Sat 14 Aug: racing in the harbour and the estuary all week.'"""
        name = f"{self.event.name[0].upper()}{self.event.name[1:]}"
        end = f", to {self.last:%a} {self.last.day} {self.last:%b}" if self.last != max(self.first, day) else ""
        return f"{name}{end}: {self.event.about.split(';')[0]}."

    def line(self, day: date, *, dated: bool = True) -> str:
        """The event in a sentence; undated, for a list already under the day, only a span's end."""
        name = f"{self.event.name[0].upper()}{self.event.name[1:]}"
        if dated:
            return f"{name}, {self.when(day)}: {self.event.about}."
        return f"{name}{f' (until {_date(self.last)})' if self.last != max(self.first, day) else ''}: {self.event.about}."


def _date(d: date) -> str:
    return f"{d:%A} {d.day} {d:%B}"


def held(y: int) -> list[On]:
    """The events that start in year `y`, in the calendar's order."""
    return [On(e, *s) for e in EVENTS if (s := e.span(y))]


def events_on(day: date) -> list[On]:
    """What is on today (a holiday that started last year included)."""
    return [o for o in held(day.year - 1) + held(day.year) if o.first <= day <= o.last]


def upcoming(day: date, ahead: int = AHEAD_DAYS) -> list[On]:
    """Events on today or starting in the next `ahead` days, by start: those under way first."""
    end = day + timedelta(days=ahead)
    on = [o for y in (day.year - 1, day.year, day.year + 1) for o in held(y) if o.last >= day and o.first <= end]
    return sorted(on, key=lambda o: o.first)


def next_on(name: str, day: date) -> On | None:
    """The next time an event (by name, any case) is on, from `day` (today included): the Christmas holidays
    under way in January are last year's."""
    want = name.strip().lower()
    return next((o for y in (day.year - 1, day.year, day.year + 1) for o in held(y)
                 if o.event.name.lower() == want and o.last >= day), None)


def for_show(show_id: str, day: date) -> list[On]:
    """The writer's ration: up to RATION events in the next AHEAD_DAYS that suit the show. An event starting
    soon comes before one long under way (the summer holidays don't take a slot all August)."""
    mine = [o for o in upcoming(day) if show_id in o.event.shows]
    return sorted(mine, key=lambda o: (o.first < day, o.first))[:RATION]


def for_prompt(show_id: str, day: date | datetime) -> str:
    """The writers' lines: the show's ration, and never an event the calendar doesn't have. Given the
    time, an event today whose start has passed says so: on 2026-11-05 the news still had the
    bonfire's "gates at six" to come at eleven at night."""
    now = day if isinstance(day, datetime) else None
    day = now.date() if now else day
    mine = for_show(show_id, day)
    if not mine:
        return ("TOWN CALENDAR: nothing on in town for this programme in the next few days. Do not make up a "
                "festival, fair or town event, or a date for one.")
    return ("TOWN CALENDAR, today and coming up (mention one only where it fits this item, and in passing; "
            "these are the only town events you may mention: never invent another, or a date, time or place "
            "for one):\n" + "\n".join(f"  - {o.line(day)}{_started(o, now)}" for o in mine))


def _started(o: On, now: datetime | None) -> str:
    """For a one-day event today with a start time: ' It began at 18:00, ...' once it has passed, and
    ' It starts at 10:45, ...' before. On 2026-11-08 Remembrance Sunday had no time, and at 08:45 Morning
    Tide had the parade already "ends in clear, cold sunshine", two hours before it set off."""
    if not (now and o.event.at and o.first == o.last == now.date()):
        return ""
    if f"{now:%H:%M}" >= o.event.at:
        return (f" It began at {o.event.at}, so by now it is under way or over: tell it as happening or as "
                "done, never as still to come.")
    return (f" It starts at {o.event.at}, so it has not happened yet: tell it as still to come, never as "
            "under way or done.")


def due(text: str, day: date) -> date | None:
    """The date a NEXT development comes due, if it names an event in the calendar: its next first day."""
    low = text.lower()
    found = [o for o in upcoming(day, 366) if o.event.name.lower().removeprefix("the ") in low]
    return min((max(o.first, day) for o in found), default=None)


# ------------------------------------------------------------------- coming up

@dataclass(frozen=True)
class Coming:
    day: date
    text: str
    kind: str                            # "event", "council", "football", "rugby", "darts", "quay"
    short: str = ""                      # for a teletext page: the name and the gist

    @property
    def brief(self) -> str:
        return self.short or self.text


def _fixtures(mod, day: date, end: date, at: str = "kickoff") -> list:
    """The season's matches from `day` to `end` (the window can reach into the next season)."""
    seen = {f for d in (day, end) for f in mod.fixtures(d)}
    return sorted((f for f in seen if day <= getattr(f, at).date() <= end), key=lambda f: getattr(f, at))


def _match(f, club: str, nick: str) -> str:
    home = f.home == club
    return f"{nick} {'at home to' if home else 'away at'} {f.away if home else f.home}, {f.kickoff:%H:%M}"


def coming_up(day: date, days: int = COMING_DAYS) -> list[Coming]:
    """Everything dated in the next `days` (today included): the town's events, full council, the Tides',
    the rugby's and the darts league's matches, and the fish auction's return after a weekend."""
    end = day + timedelta(days=days - 1)
    out = [Coming(max(o.first, day), o.line(day, dated=False), "event", o.short(day)) for o in upcoming(day, days - 1)]
    out += [Coming(d, "Full council meets, live on The Chamber at eight.", "council", "Full council, live at eight.")
            for d in council.next_meetings(day, 3) if d <= end]
    out += [Coming(f.kickoff.date(), f"Football: {_match(f, sport.CLUB, sport.NICK)}.", "football")
            for f in _fixtures(sport, day, end) if sport.CLUB in (f.home, f.away)]
    out += [Coming(f.kickoff.date(), f"Rugby: {_match(f, rugby.CLUB, rugby.NICK)}.", "rugby")
            for f in _fixtures(rugby, day, end) if rugby.CLUB in (f.home, f.away)]
    nights: dict[date, int] = {}
    for f in _fixtures(darts, day, end, at="start"):
        nights[f.start.date()] = nights.get(f.start.date(), 0) + 1
    out += [Coming(d, f"Darts: {n} league {'match' if n == 1 else 'matches'} in the pubs from eight.", "darts",
                  "Darts league night, from eight.")
            for d, n in nights.items()]
    if quay.auction(day) is None:        # a weekend: say when the auction is back
        back = next(d for d in (day + timedelta(days=k) for k in range(1, 8)) if quay.auction(d))
        out.append(Coming(back, "The fish auction is back on the quay at half past six.", "quay",
                          "Fish auction, 06:30."))
    order = ("event", "council", "football", "rugby", "darts", "quay")
    return sorted(out, key=lambda c: (c.day, order.index(c.kind)))


def for_editor(day: date, days: int = COMING_DAYS) -> str:
    """The fortnight for the desk and the back office (world.summary_for_editor), a line a day."""
    by_day: dict[date, list[str]] = {}
    for c in coming_up(day, days):
        by_day.setdefault(c.day, []).append(c.text)
    rows = "\n".join(f"  - {_date(d)}{' (today)' if d == day else ''}: {' '.join(t)}" for d, t in by_day.items())
    return ("Coming up in the next fortnight (the town calendar, full council and the fixtures; the fish auction is "
            "weekdays only; these are the only town events: never invent another, or a date for one):\n" + rows)


if __name__ == "__main__":
    import sys

    at = date.fromisoformat(sys.argv[1]) if len(sys.argv) > 1 else datetime.now().date()
    for o in held(at.year):
        print(f"{o.first:%a %d %b}" + (f" - {o.last:%a %d %b}" if o.last != o.first else "") + f"  {o.event.name}")
    print()
    print(for_editor(at))
    for show in ("news", "breakfast", "rockpool", "late"):
        print(f"\n[{show}]\n{for_prompt(show, at)}")
