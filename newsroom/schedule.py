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
from datetime import date

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


# Rock Pool's recurring items, each with its own place in the order (writers._ROCKPOOL has the rules).
_MAKE = ("THE MAKE: Poppy makes one thing from things found at home (an egg box, a paper plate, a sock, a "
         "loo-roll tube), step by step so children can make it too, with a grown-up for the scissors; Gully helps, "
         "badly")
_VISITOR = ("an ANIMAL VISITOR: someone brings an animal into the studio (the lifeboat station's cat, a farm's "
            "lambs, a rescued hedgehog, a sheepdog, the school's tortoise): what it eats, how to look after it, one "
            "amazing fact; Gully is jealous")
_LETTERS = ("LETTERS AND DRAWINGS: Gully reads out two or three letters from viewers and Poppy describes the "
            "drawings they sent (a first name and an age only, never a surname or an address)")
_STORY = ("STORY TIME: Hugh Tremayne (\"historian\") reads a legend of the town or the coast for children (a "
          "mermaid, a smuggler's dog, a giant who built the harbour wall), gentle and a little funny, nothing "
          "frightening; Poppy introduces it in a line, and she and Gully ask one question at the end")
_POEM = ("GULLY'S POEM: Gully recites a short silly poem he has written (four to eight rhyming lines) about "
         "something on the beach; Poppy is kind about it")

SHOWS: dict[str, Show] = {s.id: s for s in (
    Show(
        "news", "PORT WEXLEY NEWS", "NEWS", (200, 30, 30),
        # One loop in three swaps the field report for a studio interview. The weather comes
        # once a loop, about every ten minutes (at every bumper it was a quarter of the airtime).
        # The sport comes once in three loops, about every half hour.
        pattern=(T.bumper, T.weather, T.bulletin, T.field_report,
                 T.bumper, T.bulletin, T.field_report,
                 T.bumper, T.bulletin, T.interview,
                 T.bumper, T.weather, T.bulletin, T.field_report,
                 T.bumper, T.bulletin, T.sport,
                 T.bumper, T.bulletin, T.interview,
                 T.bumper, T.weather, T.bulletin, T.field_report,
                 T.bumper, T.bulletin, T.field_report,
                 T.bumper, T.bulletin, T.interview),
        target_s={T.bumper: 8.0, T.weather: 60.0, T.bulletin: 75.0, T.field_report: 90.0, T.interview: 90.0,
                  T.sport: 60.0},
        cast=("anchor", "weather", "reporter"), lead="anchor",
        cast_by_type={T.interview: ("anchor", "guest"), T.breaking: ("anchor", "reporter"),
                      T.bulletin: ("anchor", "reporter"),   # Gordon has no place at the desk
                      T.sport: ("sport",)},
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
        "sport", "FULL TIME", "SPORT", (40, 150, 90),
        # Fifteen minutes of local sport before Coastwide, from the sports corner: the Tides, the
        # Wreckers' rugby and the pub darts (sport.py, rugby.py, darts.py, so the scores are the same
        # everywhere), Tamsin Jago at the stadium and in a darts pub and asking the Wreckers' supporters
        # at the Quarry Field, a guest on the sports desk, and the games coming up. Tamsin took the
        # outside work from Miles on 2026-10-30, so he isn't on three shows an evening.
        # The rugby and the darts come before the wrap: fifteen minutes rarely gets past it.
        pattern=(
            T.bumper,
            I(T.sport, "open", brief="the headlines: the Tides' latest result or news, the Wreckers' rugby, the darts"),
            I(T.field_report, brief="Tamsin live at Tidewater Stadium or the training ground: the Tides this week"),
            I(T.sport, brief="the rugby: the Wreckers' last result, who scored the tries, the table, the next game"),
            I(T.interview, brief="a guest from the Tides, the Wreckers or the darts league, about the last game "
                                 "or match night and the next"),
            I(T.field_report, brief="Tamsin live from a darts pub: the last match night's results, the 180s and the "
                                    "best checkout, the table, who plays next, and the regulars at the bar"),
            # the order wraps back to here
            I(T.sport, brief="the rest of the football league: the other results from the last round and the table"),
            I(T.vox_pop, brief="Tamsin asks Wreckers supporters at the Quarry Field one question"),
            I(T.sport, brief="the smaller clubs: bowls, rowing, the sea swimmers or the Gulls' Sunday side"),
            I(T.interview, brief="someone from one of the smaller clubs, or a young player coming through"),
        ),
        loop_from=6,
        closing=(I(T.sport, "close", brief="the games coming up, and over to Coastwide"),),
        target_s={T.bumper: 8.0, T.sport: 60.0, T.field_report: 100.0, T.interview: 180.0, T.vox_pop: 60.0},
        cast=("sport", "sport_reporter"), lead="sport",
        cast_by_type={T.sport: ("sport",), T.interview: ("sport", "guest"),
                      T.vox_pop: ("sport", "sport_reporter", "guest"), T.field_report: ("sport", "sport_reporter")},
        station="Full Time, the sport from Port Wexley and the Greymouth coast on channel 7",
        tone="quick, keen and local; proud of the clubs, honest about a bad result, never cruel",
        light=True,                  # no news threads from the sports desk: the scores come from sport.py
        repeats_overnight=False,     # tonight's results aren't tomorrow's
    ),
    Show(
        "quayside", "QUAYSIDE", "QUAYSIDE", (40, 104, 124),
        # Half an hour of the town's money at lunchtime with Howard Lanyon: the morning's fish auction
        # (quay.py, so the figures agree everywhere), local firms, jobs and prices (docs/SHOWS.md).
        pattern=(
            T.bumper,
            I(T.links, "open", brief="Howard opens Quayside: the morning's auction in a few figures, and what's "
                                     "coming up"),
            I(T.field_report, brief="Miles on the fish quay: this morning's auction, the boats that went out "
                                    "and those that stayed in, a skipper or a buyer"),
            I(T.interview, brief="a local business in the armchair: a firm, a shop opening or closing, a trader "
                                 "with a problem"),
            I(T.links, brief="the jobs board: three or four vacancies in town and along the coast, and who to ask",
              target_s=50.0),
            I(T.consumer, brief="prices: the high street, the pumps, a bill or a charge that has changed"),
            T.ad_break,
            I(T.feature, brief="a local firm at work: what it makes or does, who it employs, how trade is"),
            I(T.vox_pop, brief="Miles asks shoppers or traders one question about money"),
            # the order wraps back to here
            I(T.interview, brief="the harbour trade: the harbourmaster, the merchant on the quay, or someone "
                                 "who buys at the auction", target_s=150.0),
            I(T.feature, brief="a shop or business that is new, closing or changing hands"),
        ),
        loop_from=9,
        closing=(I(T.links, "close", brief="Howard's closing figures, and what to watch this week"),),
        target_s={T.bumper: 8.0, T.links: 60.0, T.field_report: 100.0, T.interview: 180.0, T.consumer: 75.0,
                  T.feature: 120.0, T.vox_pop: 60.0, T.ad_break: 60.0},
        cast=("business", "reporter"), lead="business",
        cast_by_type={T.links: ("business",), T.field_report: ("business", "reporter"),
                      T.interview: ("business", "guest"), T.consumer: ("business", "guest"),
                      T.feature: ("business", "reporter", "guest"), T.vox_pop: ("business", "reporter", "guest")},
        station="Quayside, the business half hour on channel 7, with Howard Lanyon",
        tone="dry, clear and local: the figures first, then what they mean for people in town",
        repeats_overnight=False,     # this morning's prices, this lunchtime
    ),
    Show(
        "phonein", "HAVE YOUR SAY", "YOUR SAY", (50, 110, 190),
        # An hour's news phone-in with Jonah Pike after breakfast: one question from the day's news, a
        # studio guest at the heart of it, and viewers ringing in (phonein.py books all three); Dana
        # reads the headlines from the news desk, and Jonah does the travel.
        pattern=(
            T.bumper,
            I(T.links, "open", brief="Jonah opens Have Your Say: today's question, the studio guest by name and "
                                     "role, and the number to ring", target_s=45.0),
            I(T.interview, brief="THE STUDIO GUEST first: Jonah puts today's question to them and gets where they "
                                 "stand, so the callers have something to answer", target_s=120.0),
            T.call,
            T.call,
            # the order wraps back to here, the headlines at the top of it: ten to fifteen minutes, by how
            # long the calls run
            I(T.bulletin, brief="the headlines, from Dana at the news desk in the middle of the phone-in"),
            T.call,
            T.call,
            I(T.links, brief="the travel: the roads, the buses, the ferries and the tide, then back to the phones",
              target_s=40.0),
            T.call,
            T.call,
            T.ad_break,
            I(T.interview, brief="back to THE STUDIO GUEST: Jonah puts the callers' strongest points to them, and "
                                 "presses where they dodged", target_s=100.0),
            T.call,
            T.call,
        ),
        loop_from=5,
        closing=(I(T.links, "close", brief="Jonah sums up what the callers said and where the studio guest moved, "
                                           "thanks them, and gives the number for next time", target_s=40.0),),
        # Haiku wrote calls of about 55 s to a 100 s budget in the first run (2026-10-30): 130 for about 70.
        target_s={T.bumper: 8.0, T.links: 45.0, T.interview: 120.0, T.call: 130.0, T.bulletin: 60.0,
                  T.ad_break: 60.0},
        cast=("host_b", "anchor"), lead="host_b",
        cast_by_type={T.links: ("host_b",), T.interview: ("host_b", "guest"), T.call: ("host_b", "guest"),
                      T.bulletin: ("anchor",)},
        station="Have Your Say, channel 7's news phone-in, with Jonah Pike",
        tone="warm, quick and fair: every caller gets a hearing, nobody gets a speech",
        repeats_overnight=False,     # this morning's question, this morning
    ),
    Show(
        "outabout", "OUT AND ABOUT", "OUT & ABOUT", (70, 140, 80),
        # Forty-five minutes of days out, culture and food with Meg Trethewey, all of it on location: her
        # pieces to camera are field reports with no studio to hand back to, and a review gives a place
        # stars that the town remembers (outabout.py). The briefs below send each lap somewhere new.
        pattern=(
            T.bumper,
            I(T.field_report, "open", brief="Meg opens Out and About to camera from where today starts: a good "
                                            "afternoon, where she is, and what's coming up", target_s=45.0),
            T.feature,
            T.review,
            T.feature,
            T.vox_pop,
            T.ad_break,
            # the order wraps back to here: one review a lap (two a lap made about nine places an afternoon in
            # the first run, 2026-10-30, every one of them kept)
            T.feature,
            T.field_report,
            T.feature,
            T.vox_pop,
            T.ad_break,
            T.feature,
            T.review,
            T.feature,
            T.field_report,
        ),
        loop_from=7,
        closing=(I(T.field_report, "close", brief="Meg signs off from where the day ended: the best of what she "
                                                  "found, and the walk for the weekend", target_s=40.0),),
        briefs={
            T.feature: (
                "a day out along the Greymouth coast: a walk, a cove or a viewpoint, with someone who knows it",
                # the amateur dramatics are the reviews' (a rehearsal, then its review, on 2026-10-30)
                "the town's culture: a gallery opening, or a painter in their studio",
                "food: what's in season on the market, and a recipe cooked with a local cook",
                "a music night, a choir or a band rehearsing, or a talk at the library",
                "somewhere to take the family: the estuary birds, the lighthouse, a farm open day",
                "a maker: a potter, a weaver, a boatbuilder or a baker, and what they make",
            ),
            T.review: (
                "a cafe or a tea room at the end of a walk",
                "a show: the amateur dramatics, a concert or an exhibition",
                "a pub lunch or a fish-and-chip shop",
                "a restaurant or a bakery in town or in Saltby",
            ),
            T.field_report: (
                "Meg's walk for the weekend: the route, the tide times, where to park and where to eat",
                "what's on this week: three or four things to do in town and along the coast",
            ),
            T.vox_pop: (
                "people out walking: the best walk, cafe or view on the coast",
                "people in town: the best thing on this week, or the best chips",
            ),
        },
        # Haiku wrote reviews of about 50 s to a 120 s budget in the first run: 150 for about a minute and a quarter.
        target_s={T.bumper: 8.0, T.field_report: 60.0, T.feature: 150.0, T.review: 150.0, T.vox_pop: 60.0,
                  T.ad_break: 60.0},
        cast=("travel",), lead="travel",
        cast_by_type={T.feature: ("travel", "guest"), T.review: ("travel", "guest"), T.vox_pop: ("travel", "guest")},
        station="Out and About, channel 7's afternoon of days out, culture and food, with Meg Trethewey",
        tone="warm, outdoorsy and honest: practical tips, real prices, no gushing",
        light=True,
        repeats_overnight=False,     # this afternoon's weekend walk and what's on
    ),
    Show(
        "rockpool", "ROCK POOL", "ROCK POOL", (232, 120, 64),
        # Forty-five minutes of children's television with Poppy Tregenza and Gully, the herring-gull puppet
        # on her arm: a make, an animal visitor, letters and drawings, Gully's poem, a guest with a job
        # children love, and story time with Hugh Tremayne. All in the studio, no ad breaks (the advert
        # pool is pubs and garages), and no news. The loop is long so story time comes round about three times.
        pattern=(
            T.bumper,
            I(T.links, "open", brief="Poppy and Gully say hello: what's on today, and Gully's opinion of it",
              target_s=45.0),
            I(T.links, brief=_MAKE, target_s=180.0),
            I(T.interview, brief=_VISITOR),
            I(T.links, brief=_LETTERS, target_s=90.0),
            # the order wraps back to here
            I(T.links, brief=_STORY, target_s=240.0),
            I(T.interview, brief="a GUEST with a job children love (a lifeboat volunteer, the lighthouse keeper, a "
                                 "baker, a vet, the bus driver, a fisherman): what they do all day, the best bit, and "
                                 "one question from Gully"),
            I(T.links, brief=_POEM, target_s=60.0),
            I(T.links, brief=_MAKE, target_s=180.0),
            I(T.interview, brief=_VISITOR),
            I(T.links, brief=_LETTERS, target_s=90.0),
        ),
        loop_from=5,
        closing=(I(T.links, "close", brief="Poppy and Gully say goodbye until tomorrow; Gully gets the last word",
                   target_s=35.0),),
        target_s={T.bumper: 8.0, T.links: 90.0, T.interview: 180.0},
        cast=("kids", "gully"), lead="kids",
        cast_by_type={T.links: ("kids", "gully", "historian"), T.interview: ("kids", "gully", "guest")},
        station="Rock Pool, channel 7's children's programme, with Poppy Tregenza and Gully",
        tone="kind, bright and silly: short sentences, nothing frightening",
        light=True,
        repeats_overnight=False,     # "see you tomorrow!" doesn't belong at three in the morning
    ),
    Show(
        "panel", "THE PANEL", "THE PANEL", (110, 70, 150),
        # Half an hour of debate: Dana Ferris chairs three panellists on three questions from the week's
        # news, booked earlier in the evening (panel.py); a question from the public on the second.
        pattern=(
            T.bumper,
            I(T.links, "open", brief="Dana opens The Panel: welcome, the three panellists by name and role, and "
                                     "the first question", target_s=45.0),
            I(T.interview, brief="the FIRST of TONIGHT'S QUESTIONS: Dana puts it, each panellist answers in turn, "
                                 "then they take each other on; Dana keeps it moving and fair"),
            I(T.vox_pop, brief="Miles asks people in town the SECOND of TONIGHT'S QUESTIONS; the last of them "
                               "puts it to the panel in their own words"),
            I(T.interview, brief="the SECOND of TONIGHT'S QUESTIONS, picking up the member of the public's words: "
                                 "each answers, then they argue it out"),
            T.ad_break,
            I(T.interview, brief="the THIRD of TONIGHT'S QUESTIONS: each answers, then the sharpest disagreement "
                                 "of the night; Dana presses whoever dodges"),
            # the order wraps back to here
            I(T.interview, brief="the quick-fire round: Dana's short questions on the week's smaller stories, a "
                                 "line or two from each panellist", target_s=120.0),
        ),
        loop_from=7,
        closing=(I(T.links, "close", brief="Dana thanks the panel and sums up where they agreed and where they "
                                           "didn't, in a few lines", target_s=40.0),),
        target_s={T.bumper: 8.0, T.links: 45.0, T.interview: 330.0, T.vox_pop: 60.0, T.ad_break: 60.0},
        cast=("anchor", "reporter"), lead="anchor",
        cast_by_type={T.links: ("anchor",), T.interview: ("anchor", "guest"),
                      T.vox_pop: ("anchor", "reporter", "guest")},
        station="The Panel, channel 7's debate, chaired by Dana Ferris",
        tone="lively but civil: real disagreement, real reasons, nobody shouted down",
        repeats_overnight=False,     # tonight's questions, tonight
    ),
    Show(
        "inquiry", "THE INQUIRY", "INQUIRY", (150, 46, 46),
        # Half an hour on one running story, chosen earlier in the evening with Pat's questions and the
        # guest who has to answer them (inquiry.py). The only serious show of the evening.
        pattern=(
            T.bumper,
            I(T.links, "open", brief="Pat opens The Inquiry to camera: tonight's story in a few lines, and the "
                                     "questions she will put"),
            I(T.feature, brief="Miles's film: how the story began and how it got here, from the record, with "
                               "someone it has affected (not THE GUEST: they are saved for the studio)"),
            I(T.interview, brief="THE GUEST in the studio, part one: Pat puts only the first one or two of THE "
                                 "QUESTIONS, and does not let a vague answer go; the rest come after the break"),
            T.ad_break,
            I(T.feature, brief="the paper trail: what the minutes, letters, plans and the archive show, and what "
                               "they leave out", target_s=120.0),
            I(T.vox_pop, brief="Miles asks the people most affected one question about it"),
            I(T.interview, "cont", brief="THE GUEST, part two: the questions not yet put; Pat holds them to what "
                                         "they said in part one and what the film and the papers showed"),
            I(T.interview, brief="the other side: a resident, a campaigner or an expert who sees it differently "
                                 "from THE GUEST", target_s=120.0),
            # the order wraps back to here
            I(T.feature, brief="Miles back on the ground tonight: what it looks like now, and who is waiting",
              target_s=90.0),
        ),
        loop_from=9,
        closing=(I(T.links, "close", brief="Pat to camera: what we found, what is still not answered, and who "
                                           "has to answer it next"),),
        target_s={T.bumper: 8.0, T.links: 60.0, T.feature: 150.0, T.interview: 210.0, T.vox_pop: 60.0,
                  T.ad_break: 60.0},
        cast=("mag_a", "reporter"), lead="mag_a",
        cast_by_type={T.links: ("mag_a",), T.feature: ("mag_a", "reporter", "guest"),
                      T.interview: ("mag_a", "guest"), T.vox_pop: ("mag_a", "reporter", "guest")},
        station="The Inquiry, channel 7's investigation, with Pat Holloway",
        tone="probing, fair and precise; plain words, no sensation; the record first, then the questions",
        repeats_overnight=False,     # tonight's questions, tonight
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

# A normal day, without breaking news: (start, show id), in order; the last entry at or
# before the time wins. A start is a whole hour, or "HH:MM" for a show that starts on the
# quarter. A show that isn't built yet airs its stand-in.
SCHEDULE: tuple[tuple[int | str, str], ...] = (
    (0, "overnight"),       # test card and repeats; the editor and story desk keep working, specials air
    (6, "breakfast"),       # Morning Tide on the sofa: lighter, chattier
    (9, "news"),            # the news loop through the day and the early evening
    (10, "phonein"),        # Have Your Say: Jonah Pike's news phone-in
    (11, "news"),
    (13, "quayside"),      # Quayside: the business half hour, with the fish auction's prices
    ("13:30", "news"),
    (15, "outabout"),       # Out and About: Meg Trethewey on days out, culture and food
    ("15:45", "news"),
    (16, "rockpool"),       # Rock Pool: Poppy Tregenza and Gully, children's television
    ("16:45", "news"),
    ("18:45", "sport"),     # Full Time: fifteen minutes of local sport
    (19, "magazine"),       # Coastwide: features, a studio guest, vox pops, the consumer slot
    (20, "inquiry"),        # The Inquiry: Pat Holloway on one story in depth
    ("20:30", "panel"),     # The Panel: Dana Ferris chairs three panellists on the week's news
    (21, "news"),           # the documentary airs at its first bumper
    (22, "late"),           # The Last Ferry: a monologue and long guest chats
    (23, "news"),           # the late news
)
STAND_INS: dict[str, str] = {}          # schedule slots whose show isn't built yet -> what airs instead


def hour_min(start: int | str) -> tuple[int, int]:
    """A schedule start as (hour, minute)."""
    if isinstance(start, str):
        h, m = start.split(":")
        return int(h), int(m)
    return start, 0


def start_label(start: int | str) -> str:
    return "%02d:%02d" % hour_min(start)


def slot_at(ts: float) -> str:
    """The schedule entry at `ts`, which may be a show that isn't built yet."""
    lt = time.localtime(ts)
    at = (lt.tm_hour, lt.tm_min)
    current = SCHEDULE[0][1]
    for start, show_id in SCHEDULE:
        if at >= hour_min(start):
            current = show_id
    return current


def starts(ts: float, days: int = 2) -> list[tuple[float, str]]:
    """Every schedule entry's start from the day of `ts` on, for `days` days, in order:
    (timestamp, slot). DST-safe: each is built from the calendar day."""
    day = date.fromtimestamp(ts)
    out = []
    for k in range(days):
        d = date.fromordinal(day.toordinal() + k)
        for start, slot in SCHEDULE:
            h, m = hour_min(start)
            out.append((time.mktime((d.year, d.month, d.day, h, m, 0, 0, 0, -1)), slot))
    return out


def show_at(ts: float) -> Show:
    slot = slot_at(ts)
    return SHOWS[STAND_INS.get(slot, slot)]


def show_end(ts: float) -> float:
    """When the show on air at `ts` hands over to a different one: the start of that entry."""
    now_id = show_at(ts).id
    return next((t for t, _ in starts(ts) if t > ts and show_at(t).id != now_id), ts + 24 * 3600)


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
    i = next(i for i, (_, s) in enumerate(SCHEDULE) if s == show_id)
    return start_label(SCHEDULE[(i + 1) % len(SCHEDULE)][0])


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
        print(f"{start_label(start)}  {name:<10} {s.title:<18}{' light' if s.light else ''}  cast={','.join(s.cast) or '-'}  "
              f"{shape}: {order}")
    lt = time.localtime()
    at = [time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, 1, 0, 0, 0, -1)) for h in range(24)]   # DST-safe
    print("by hour: " + " ".join(f"{h:02d}={show_at(ts).id[0]}" for h, ts in enumerate(at)))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
