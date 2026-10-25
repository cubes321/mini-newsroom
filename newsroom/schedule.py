"""The schedule: which show is on air at a given time.

Pure data plus a clock, no pygame, like locations.py. The producer asks
`show_at(ts)` for each slot it plans (by the slot's nominal start, which runs
up to the planning horizon ahead), so a show change lands at a segment
boundary near the hour rather than cutting anything off.

`time_of_day()` in locations.py is a different thing: it grades the art.

The broadcast clock is `now()`, which is `time.time()` plus an offset that
`set_clock("HH:MM")` sets, so any show can be tested at any hour.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .models import SegmentType as T

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Show:
    id: str
    title: str                       # on the bumper and the filler card
    ticker: str                      # the ticker's label box
    colour: RGB                      # bumper and ticker accent
    pattern: tuple[T, ...]
    target_s: dict[T, float] = field(hash=False)
    cast: tuple[str, ...] = ()       # speaker ids allowed in live segments
    lead: str = "anchor"             # who fronts the show and hands over
    station: str = ""                # how writers are told who they write for
    tone: str = ""
    airs_specials: bool = False      # a ready special may air after this show's bumpers
    light: bool = False              # lighter stories unless a big running story is on (writers.py)
    cast_by_type: dict[T, tuple[str, ...]] = field(default_factory=dict, hash=False)   # narrower casts

    def cast_for(self, seg_type: T) -> tuple[str, ...]:
        return self.cast_by_type.get(seg_type, self.cast)


SHOWS: dict[str, Show] = {s.id: s for s in (
    Show(
        "news", "PORT WEXLEY NEWS", "NEWS", (200, 30, 30),
        # One loop in three swaps the field report for a studio interview.
        pattern=(T.bumper, T.weather, T.bulletin, T.field_report,
                 T.bumper, T.weather, T.bulletin, T.field_report,
                 T.bumper, T.weather, T.bulletin, T.interview),
        target_s={T.bumper: 8.0, T.weather: 60.0, T.bulletin: 75.0, T.field_report: 90.0, T.interview: 90.0},
        cast=("anchor", "weather", "reporter"), lead="anchor",
        cast_by_type={T.interview: ("anchor", "guest")},
        station="Port Wexley News on channel 7",
        tone="warm, dry, local",
        airs_specials=True,
    ),
    Show(
        "breakfast", "MORNING TIDE", "MORNING", (230, 140, 40),
        pattern=(T.bumper, T.bulletin, T.sofa, T.weather, T.field_report, T.sofa),
        target_s={T.bumper: 8.0, T.bulletin: 60.0, T.sofa: 75.0, T.weather: 45.0, T.field_report: 75.0},
        cast=("host_a", "host_b", "weather", "reporter"), lead="host_a",
        station="Morning Tide, Port Wexley's breakfast show on channel 7",
        tone="light, warm and chatty, early-morning company; still local and specific",
        cast_by_type={T.sofa: ("host_a", "host_b")},
        light=True,
    ),
    Show(
        "magazine", "COASTWIDE", "COASTWIDE", (40, 140, 150),
        pattern=(T.bumper, T.links, T.feature, T.interview, T.vox_pop, T.consumer, T.weather),
        target_s={T.bumper: 8.0, T.links: 45.0, T.feature: 90.0, T.interview: 110.0, T.vox_pop: 60.0,
                  T.consumer: 75.0, T.weather: 40.0},
        cast=("mag_a", "mag_b", "weather", "reporter"), lead="mag_a",
        station="Coastwide, Port Wexley's early-evening magazine on channel 7",
        tone="warm, curious and gently funny, in the spirit of an old-fashioned regional magazine show",
        light=True,
        cast_by_type={
            T.links: ("mag_a", "mag_b"),
            T.interview: ("mag_a", "guest"),
            T.consumer: ("mag_b", "guest"),
            T.feature: ("mag_a", "mag_b", "reporter", "guest"),
            T.vox_pop: ("mag_a", "mag_b", "reporter", "guest"),
            T.weather: ("mag_a", "mag_b", "weather"),
        },
    ),
    Show(
        "late", "THE LAST FERRY", "LATE", (90, 50, 130),
        pattern=(T.bumper, T.monologue, T.interview, T.interview),
        target_s={T.bumper: 8.0, T.monologue: 60.0, T.interview: 150.0},
        cast=("late_host", "guest"), lead="late_host",
        station="The Last Ferry, Port Wexley's late-night talk show on channel 7",
        tone="late-night, wry and unhurried; affectionate about the town, never cruel",
        light=True,
        cast_by_type={T.monologue: ("late_host",)},
    ),
    Show(
        "overnight", "PORT WEXLEY NEWS", "OVERNIGHT", (90, 90, 140),
        pattern=(T.testcard, T.repeat),
        target_s={T.testcard: 60.0, T.repeat: 75.0},
    ),
)}

# A normal day, without breaking news: (start hour, show id), in order; the last
# entry at or before the hour wins. A show that isn't built yet airs its stand-in.
SCHEDULE: tuple[tuple[int, str], ...] = (
    (0, "overnight"),       # test card and repeats; the editor and story desk keep working
    (6, "breakfast"),       # Morning Tide on the sofa: lighter, chattier
    (9, "news"),            # the news loop through the day and the early evening
    (19, "magazine"),       # Coastwide: features, a studio guest, vox pops, the consumer slot
    (20, "news"),
    (22, "late"),           # The Last Ferry: a monologue and long guest chats
    (23, "news"),           # the late news
)
STAND_INS: dict[str, str] = {}          # schedule slots whose show isn't built yet -> what airs instead


def slot_at(ts: float) -> str:
    """The schedule entry at `ts`, which may be a show that isn't built yet."""
    hour = time.localtime(ts).tm_hour
    current = SCHEDULE[0][1]
    for start, show_id in SCHEDULE:
        if hour >= start:
            current = show_id
    return current


def show_at(ts: float) -> Show:
    slot = slot_at(ts)
    return SHOWS[STAND_INS.get(slot, slot)]


def part_of_day(ts: float) -> str:
    """The word presenters use for the time: 'morning', 'afternoon', 'evening' or 'night'."""
    hour = time.localtime(ts).tm_hour
    if 5 <= hour < 12:
        return "morning"
    if 12 <= hour < 17:
        return "afternoon"
    if 17 <= hour < 23:
        return "evening"
    return "night"


def get(show_id: str | None) -> Show:
    return SHOWS.get(show_id or "", SHOWS["news"])


def next_start(show_id: str) -> str:
    """When `show_id`'s first block ends, as HH:MM: for "programmes resume at" captions."""
    hours = [h for h, _ in SCHEDULE]
    i = next(i for i, (_, s) in enumerate(SCHEDULE) if s == show_id)
    return f"{hours[(i + 1) % len(hours)]:02d}:00"


# ------------------------------------------------------------------- clock

_offset_s = 0.0


def now() -> float:
    return time.time() + _offset_s


def set_clock(hhmm: str) -> None:
    """Pretend the local time is `hhmm` today; the clock then runs normally from there."""
    global _offset_s
    h, m = (int(x) for x in hhmm.split(":"))
    lt = time.localtime()
    target = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
    _offset_s = target - time.time()


def _cli() -> int:
    for start, slot in SCHEDULE:
        s = SHOWS[STAND_INS.get(slot, slot)]
        loop = sum(s.target_s.get(t, 0.0) for t in s.pattern)
        name = slot if slot == s.id else f"{slot} (not built; {s.id} stands in)"
        print(f"{start:02d}:00  {name:<10} {s.title:<18}{' light' if s.light else ''}  cast={','.join(s.cast) or '-'}  "
              f"loop ~{loop / 60:.1f} min: {' '.join(t.value for t in s.pattern)}")
    lt = time.localtime()
    at = [time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, 1, 0, 0, 0, -1)) for h in range(24)]   # DST-safe
    print("by hour: " + " ".join(f"{h:02d}={show_at(ts).id[0]}" for h, ts in enumerate(at)))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
