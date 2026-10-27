"""The schedule: which show is on air at a given time.

Pure data plus a clock, no pygame, like locations.py. The producer asks
`show_at(ts)` for each slot it plans (by the slot's nominal start, which runs
up to the planning horizon ahead), so a show change lands at a segment
boundary near the hour rather than cutting anything off.

`time_of_day()` in locations.py is a different thing: it grades the art.

The news and breakfast loop a short pattern. The magazine and the talk show
have a written-out order for the hour instead: an opening, a long middle the
order wraps back to if it runs out (never to the bumper), and a closing the
producer plans once as the hour runs out. Entries can be an `Item` with a
part ("open", "cont" for the same guest after the break, "close") and a brief,
so the third feature of the hour isn't the first one again. A show can also
list `briefs` per type, handed out in turn to entries without their own:
breakfast runs three hours on a short pattern, and its sofa chats and reports
still each get a different angle.

The light shows have ad breaks in their orders (`T.ad_break`, filled from the
advert pool by the worker): breakfast before each round of headlines, the
magazine between its blocks, and the talk show between a guest's two parts.

The broadcast clock is `now()`, which is `time.time()` plus an offset that
`set_clock("HH:MM")` sets, so any show can be tested at any hour.
"""
from __future__ import annotations

import time
from dataclasses import dataclass, field

from .models import SegmentType as T

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Item:
    """One entry in a running order when a bare segment type isn't enough."""
    type: T
    part: str = ""                   # "open" | "cont" | "couch" | "close" (writers.py)
    brief: str = ""                  # the angle for this item, given to the writer
    target_s: float = 0.0            # its own length; 0 = the show's target for the type


@dataclass(frozen=True)
class Show:
    id: str
    title: str                       # on the bumper and the filler card
    ticker: str                      # the ticker's label box
    colour: RGB                      # bumper and ticker accent
    pattern: tuple[T | Item, ...]
    target_s: dict[T, float] = field(hash=False)
    cast: tuple[str, ...] = ()       # speaker ids allowed in live segments
    lead: str = "anchor"             # who fronts the show and hands over
    station: str = ""                # how writers are told who they write for
    tone: str = ""
    airs_specials: bool = False      # a ready special may air after this show's bumpers
    light: bool = False              # lighter stories unless a big running story is on (writers.py)
    repeats_overnight: bool = True   # its segments may air again in the overnight repeats (workers.py)
    cast_by_type: dict[T, tuple[str, ...]] = field(default_factory=dict, hash=False)   # narrower casts
    loop_from: int = 0               # where the order wraps when it runs out
    closing: tuple[T | Item, ...] = ()   # planned once as the show's time runs out
    briefs: dict[T, tuple[str, ...]] = field(default_factory=dict, hash=False)   # angles, in turn, per type

    def cast_for(self, seg_type: T) -> tuple[str, ...]:
        return self.cast_by_type.get(seg_type, self.cast)

    def target_for(self, entry: T | Item) -> float:
        item = as_item(entry)
        return item.target_s or self.target_s[item.type]

    def item(self, pos: int) -> Item:
        """The pattern entry at `pos`, counting on past the end through the wrap."""
        n = len(self.pattern)
        if pos >= n:
            pos = self.loop_from + (pos - self.loop_from) % (n - self.loop_from)
        return as_item(self.pattern[pos])

    @property
    def opens(self) -> bool:
        """True when the order marks an opening item: the big running story is covered there only."""
        return any(as_item(e).part == "open" for e in self.pattern)

    @property
    def closing_s(self) -> float:
        return sum(self.target_for(e) for e in self.closing)


def as_item(entry: T | Item) -> Item:
    return entry if isinstance(entry, Item) else Item(entry)


I = Item

# The Last Ferry's shorter second guest: one part, no break, with the main guest still on the couch.
SHORT_GUEST_S = 100.0
_SHORT = ("a SHORTER SECOND GUEST, one part with no break: a quick hello, one good story and a laugh, "
          "then Vincent thanks them; ")


SHOWS: dict[str, Show] = {s.id: s for s in (
    Show(
        "news", "PORT WEXLEY NEWS", "NEWS", (200, 30, 30),
        # One loop in three swaps the field report for a studio interview. The weather comes
        # once a loop, about every ten minutes (at every bumper it was a quarter of the airtime).
        pattern=(T.bumper, T.weather, T.bulletin, T.field_report,
                 T.bumper, T.bulletin, T.field_report,
                 T.bumper, T.bulletin, T.interview),
        target_s={T.bumper: 8.0, T.weather: 60.0, T.bulletin: 75.0, T.field_report: 90.0, T.interview: 90.0},
        cast=("anchor", "weather", "reporter"), lead="anchor",
        cast_by_type={T.interview: ("anchor", "guest"), T.breaking: ("anchor", "reporter"),
                      T.bulletin: ("anchor", "reporter")},   # Gordon has no place at the desk
        station="Port Wexley News on channel 7",
        tone="warm, dry, local",
        airs_specials=True,
    ),
    Show(
        "breakfast", "MORNING TIDE", "MORNING", (230, 140, 40),
        # Headlines, sofa, weather and a report, round and round for three hours; the briefs
        # below give every sofa chat, report and guest its own angle. The loop is two laps,
        # with a guest in the armchair on the first: one about every seventeen minutes.
        pattern=(T.bumper, I(T.bulletin, "open"), T.sofa, T.weather, T.field_report, T.sofa, T.ad_break,
                 T.bulletin, T.sofa, T.weather, T.field_report, T.sofa, T.interview, T.ad_break,
                 T.bulletin, T.sofa, T.weather, T.field_report, T.sofa, T.sofa, T.ad_break),
        loop_from=7,
        closing=(I(T.sofa, "close"),),
        briefs={
            T.sofa: (
                "the morning papers: two or three local stories the hosts have opinions about",
                "something cheering from the town",
                "a viewer's question or a small local mystery",
                "a pet, a garden or an animal story",
                "on this day in the town's history",
                "what's on in town this week",
                "the hosts' own week: a hobby, a small disaster in the kitchen",
                "food: a recipe, a cafe or the market's best buy this week",
                "a birthday, an anniversary or a long-serving local worth a mention",
                "the weekend ahead: walks, the tide, the sport",
                "a quick quiz between the hosts about the town",
                "a bit of good news from a school or a club",
            ),
            T.field_report: (
                "somewhere waking up: the fish market, the first ferry, a bakery",
                "the morning commute: the buses, the quay, the school run",
                "a business opening up for the day",
                "volunteers or a club out early",
                "a follow-up on an open story, from where it is happening",
                "the harbour at first light",
            ),
            T.interview: (
                "an author with a new book out: what it's about, and a story from writing it",
                "someone with an inspiring story: a rescue, a comeback, an ambition finally achieved",
                "a funny guest: a comedian before a gig in town, or a resident with a gloriously silly hobby",
                "an actor promoting a new film or television series, ideally shot or set on this coast",
                "a charity challenge or a record attempt, and how viewers can back it",
                "a musician or a band before a gig in town, or the leader of a local choir",
                "a chef, a baker or a cookery writer with a dish for the season",
                "someone who has done something kind: a volunteer, a neighbour, a long career of helping",
                "a sportsperson after a win, or a coach whose team is on a run",
            ),
        },
        target_s={T.bumper: 8.0, T.bulletin: 60.0, T.sofa: 75.0, T.weather: 45.0, T.field_report: 75.0,
                  T.ad_break: 60.0, T.interview: 150.0},
        cast=("host_a", "host_b", "weather", "reporter"), lead="host_a",
        station="Morning Tide, Port Wexley's breakfast show on channel 7",
        tone="light, warm and chatty, early-morning company; still local and specific",
        cast_by_type={T.sofa: ("host_a", "host_b"), T.interview: ("host_a", "host_b", "guest")},
        light=True,
        repeats_overnight=False,     # "good morning" from the sofa doesn't belong at three a.m.
    ),
    Show(
        "magazine", "COASTWIDE", "COASTWIDE", (40, 140, 150),
        pattern=(
            # the top of the programme: about ten minutes
            T.bumper, I(T.links, "open"),
            I(T.feature, brief="a local tradition or a bit of the town's history"),
            I(T.interview, brief="a resident with a hobby or a collection to show"),
            T.vox_pop,
            I(T.consumer, brief="prices: the market, the shops or the pumps"),
            I(T.links, brief="what viewers have been saying, and Clive's odd fact"),
            I(T.feature, brief="someone with an unusual job in town"),
            T.weather,
            T.ad_break,
            # the middle, about twenty-five minutes with two breaks; the order wraps back to here
            T.links,
            I(T.interview, brief="a public figure off duty"),
            I(T.feature, brief="out in the countryside or on the water"),
            T.vox_pop,
            I(T.consumer, brief="a warning: a scam, a rogue trader or a small-print trap"),
            T.ad_break,
            T.links,
            I(T.feature, brief="a club, a team or a society"),
            I(T.interview, brief="someone who has lived here a very long time"),
            T.vox_pop,
            T.links,
            I(T.feature, brief="food: a cafe, a baker, a fishmonger or a recipe"),
            I(T.consumer, brief="a bill, a fare or a charge that has changed"),
            I(T.interview, brief="someone young doing something new in town"),
            T.weather,
            I(T.feature, brief="an animal story"),
            I(T.interview, brief="a shopkeeper or a publican"),
            T.vox_pop,
            T.ad_break,
        ),
        loop_from=10,
        closing=(T.weather, I(T.links, "close")),
        target_s={T.bumper: 8.0, T.links: 45.0, T.feature: 100.0, T.interview: 120.0, T.vox_pop: 60.0,
                  T.consumer: 75.0, T.weather: 40.0, T.ad_break: 60.0},
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
        # One monologue an hour. The main guest stays for two parts either side of a break; a
        # shorter second guest follows for one part, as on the talk shows it is modelled on.
        pattern=(
            T.bumper, I(T.monologue, "open"),
            I(T.interview, brief="a public figure, more candid than usual"), T.ad_break, I(T.interview, "cont"),
            I(T.interview, "couch", brief=_SHORT + "a local character with one story everyone in town has heard a version of",
              target_s=SHORT_GUEST_S),
            I(T.vox_pop, brief="night owls: Miles asks people out late (the taxi rank, the chip shop, the last ferry)"),
            # the order wraps back to here
            I(T.links, brief="a letter from a viewer, read out and answered"),
            I(T.interview, brief="someone who works nights: a nurse, a baker, a ferry hand"), T.ad_break,
            I(T.interview, "cont"),
            I(T.interview, "couch", brief=_SHORT + "a performer, a musician or a comedian on before a gig in town",
              target_s=SHORT_GUEST_S),
            I(T.vox_pop, brief="Miles at the harbour or on the last ferry, asking one late-night question"),
            I(T.links, brief="tomorrow's papers, or what's on in town tomorrow"),
            I(T.interview, brief="someone with a story from the town's past"), T.ad_break, I(T.interview, "cont"),
            I(T.interview, "couch", brief=_SHORT + "someone who has just done something: a win, a rescue, a first, a daft record",
              target_s=SHORT_GUEST_S),
        ),
        loop_from=7,
        closing=(I(T.links, "close"),),
        target_s={T.bumper: 8.0, T.monologue: 60.0, T.interview: 180.0, T.vox_pop: 60.0, T.links: 40.0,
                  T.ad_break: 60.0},
        cast=("late_host", "guest"), lead="late_host",
        station="The Last Ferry, Port Wexley's late-night talk show on channel 7",
        tone="late-night, wry and unhurried; affectionate about the town, never cruel",
        light=True,
        cast_by_type={T.monologue: ("late_host",), T.links: ("late_host",),
                      T.vox_pop: ("late_host", "reporter", "guest")},
    ),
    Show(
        "overnight", "PORT WEXLEY NEWS", "OVERNIGHT", (90, 90, 140),
        pattern=(T.testcard, T.repeat),
        target_s={T.testcard: 60.0, T.repeat: 75.0},
        # The editor keeps working overnight, so a special it commissions airs after a test
        # card rather than waiting for the 09:00 news (which a night's worth would flood).
        airs_specials=True,
    ),
)}

# A normal day, without breaking news: (start hour, show id), in order; the last
# entry at or before the hour wins. A show that isn't built yet airs its stand-in.
SCHEDULE: tuple[tuple[int, str], ...] = (
    (0, "overnight"),       # test card and repeats; the editor and story desk keep working, specials air
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


def show_end(ts: float) -> float:
    """When the show on air at `ts` hands over to a different one (the top of that hour)."""
    lt = time.localtime(ts)
    top = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, 0, 0, 0, 0, -1))
    now_id = show_at(ts).id
    for k in range(1, 25):
        t = top + k * 3600
        if show_at(t).id != now_id:
            return t
    return top + 24 * 3600


def special_slot(ts: float) -> float:
    """When a special finished at `ts` airs: after the first news bumper from the next top of the
    hour, so a trail can give the time. Overnight at once, after the test card: nobody to trail to."""
    if show_at(ts).id == "overnight":
        return ts
    lt = time.localtime(ts)
    top = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, lt.tm_hour, 0, 0, 0, 0, -1))
    return next((top + k * 3600 for k in range(1, 25) if show_at(top + k * 3600).airs_specials), ts)


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
        items = [as_item(e) for e in s.pattern]
        total = sum(s.target_for(i) for i in items)
        name = slot if slot == s.id else f"{slot} (not built; {s.id} stands in)"
        order = " ".join(i.type.value + (f"({i.part})" if i.part else "") for i in items)
        shape = (f"order ~{total / 60:.0f} min, wraps to item {s.loop_from}, closing ~{s.closing_s:.0f}s"
                 if s.loop_from or s.closing else f"loop ~{total / 60:.1f} min")
        print(f"{start:02d}:00  {name:<10} {s.title:<18}{' light' if s.light else ''}  cast={','.join(s.cast) or '-'}  "
              f"{shape}: {order}")
    lt = time.localtime()
    at = [time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, 1, 0, 0, 0, -1)) for h in range(24)]   # DST-safe
    print("by hour: " + " ".join(f"{h:02d}={show_at(ts).id[0]}" for h, ts in enumerate(at)))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
