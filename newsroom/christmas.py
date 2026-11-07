"""Christmas on channel 7: Christmas Eve, Christmas Day and Boxing Day, each a day of its own (2026-11-07).

A special day has its own grid, like schedule.SCHEDULE, and its own versions of the regular shows: chosen by
the calendar's event for the day (schedule.special_day), as Bonfire Night's Coastwide is for its slot. A
version keeps its show's id, so the show's machinery (Coastwide's links, Rock Pool's chatter, The Last
Ferry's couch) comes with it; the new programmes have ids of their own and bring their prompts here.

- **Christmas Eve** (a working day until the evening): Coastwide live from the carols on the quay at seven,
  Hugh's Christmas Tales at eight, The Last Ferry's Christmas Eve at ten, and Midnight on the Quay from half
  past eleven, for the bells.
- **Christmas Day**: a late start; Morning Tide's Christmas morning at seven, the Christmas Morning Service at
  ten, the Christmas Day Swim at eleven, Rock Pool's Christmas at a quarter past twelve, Out and About at
  Christmas at one, the Mayor's Christmas Message at three, Christmases Past after it, Coastwide's
  Christmas night at seven and The Last Ferry's at ten. The news is short in between.
- **Boxing Day** (a Saturday in 2026): the Boxing Day Dip at eleven, Quayside on the sales, and Full Time
  out at the stadium from two, with the Tides and the Wreckers both at home.

Sets: the on-location ones use the town's own (the harbour at night, the seafront, the village hall for
the church, which has no art of its own yet); Hugh's tales are on The Last Ferry's set, the Mayor in the
council chamber. New programmes' bumpers borrow a show's music (assets.IDENT_MUSIC).
"""
from __future__ import annotations

from dataclasses import replace

from .models import SegmentType as T
from .schedule import SCHEDULE, SHOWS, SPECIAL_DAYS, I, Show

EVE, DAY, BOXING = "Christmas Eve", "Christmas Day", "Boxing Day"

# ------------------------------------------------------------------ new programmes

TALES = Show(
    "tales", "HUGH'S CHRISTMAS TALES", "TALES", (150, 40, 50),
    # An hour of winter stories of the coast, read by Hugh Tremayne by the fire, one tale an item.
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Hugh welcomes viewers by the fire on Christmas Eve: the night's tales, and why "
                                 "winter is the time for them", target_s=45.0),
        I(T.links, brief=(
            "THE SMUGGLERS' CHRISTMAS: how the free traders of Port Wexley landed brandy under the noses of the "
            "excise men on a Christmas Eve long ago",
            "THE MARINER'S GALE of 9 December 1910: the night the lifeboat saved twenty-two from the barque Ellen, "
            "and the Christmas the town gave its crew",
            "THE GHOST SHIP OF THE GREYMOUTH LIGHT: the lit ship seen off the headland every Christmas Eve that "
            "never comes in",
            "THE GULL WHO STOLE CHRISTMAS DINNER: an old harbour comic tale, told for the children still up",
            "THE CANNERY'S LAST CHRISTMAS: the women of the packing line and the party they threw before it shut",
            "THE BELLS UNDER THE SEA: the drowned chapel off the Salting whose bells ring at midnight on Christmas "
            "Eve, if you listen"), target_s=300.0),
        # Two tales to a break: one each made a minute of adverts for every two of story (scratch run, 2026-11-07).
        I(T.links, brief=(
            "THE LANTERN ON THE SALTING: the light a widow kept in her window every Christmas for a boat that came "
            "home at last",
            "THE WREN HUNT: the old Boxing Day custom of the coast, and the year the wren won",
            "THE DROWNED ORGANIST: why the harbour church's organ plays one note by itself on Christmas night"),
          target_s=300.0),
        T.ad_break,
    ),
    loop_from=2,
    closing=(I(T.links, "close", brief="Hugh's goodnight: a last word by the fire, and The Last Ferry later",
               target_s=35.0),),
    target_s={T.bumper: 8.0, T.links: 300.0, T.ad_break: 60.0},
    cast=("historian",), lead="historian",
    station="Hugh's Christmas Tales, a Christmas Eve hour of winter stories on channel 7, with Hugh Tremayne",
    tone="warm, unhurried and a little spooky in the right places; a storyteller by the fire, never frightening",
    light=True, repeats_overnight=False,
)

MIDNIGHT = Show(
    "midnight", "MIDNIGHT ON THE QUAY", "MIDNIGHT", (40, 50, 110),
    # Christmas Eve into Christmas Day: Dana on the quay as midnight comes, the lifeboat on call, the bells.
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Dana on the quay with half an hour to midnight: the lights on the boats, the "
                                 "people coming down for the bells, the cold", target_s=45.0),
        I(T.interview, brief="a lifeboat volunteer on call over Christmas: who is on the pager tonight and what "
                             "Christmas is like for the crew"),
        I(T.vox_pop, brief="Miles among the people on the quay: who they came with, and what they hope for "
                           "next year"),
        I(T.interview, brief="the tower captain of the bell ringers: the peal they ring at midnight and how long "
                             "it takes"),
        # the order wraps back to here
        I(T.links, brief=("Dana: the clock, the bells and the town's Christmas wishes read out",
                          "Dana: midnight has come: happy Christmas from the quay",
                          "Dana: the quay emptying as people head home, and Christmas Day ahead on channel 7")),
        I(T.vox_pop, brief=("Miles: one question: the best Christmas you remember",
                            "Miles: one question: who are you thinking of tonight",
                            "Miles: one question: what is on the table tomorrow")),
    ),
    loop_from=5,
    closing=(I(T.links, "close", brief="Dana's goodnight and happy Christmas from the quay", target_s=30.0),),
    target_s={T.bumper: 8.0, T.links: 45.0, T.interview: 150.0, T.vox_pop: 60.0},
    cast=("anchor", "reporter"), lead="anchor",
    cast_by_type={T.links: ("anchor",), T.interview: ("anchor", "guest"),
                  T.vox_pop: ("anchor", "reporter", "guest")},
    station="Midnight on the Quay, channel 7 live from Port Wexley harbour as Christmas Eve turns to Christmas Day",
    tone="quiet, warm and a little moved; a town gathered in the cold, gently funny where people are",
    light=True, repeats_overnight=False, location="harbour", tod="night",
)

CAROLS = Show(
    "carols", "THE CHRISTMAS MORNING SERVICE", "SERVICE", (120, 30, 50),
    # An hour from the harbour church on Christmas morning: carols, a reading, the vicar, the congregation.
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Dana at the back of the harbour church as people come in from the cold: who is "
                                 "here, the decorations, and the carols to come", target_s=45.0),
        I(T.feature, brief="the Salting Harmony choir before the first carol: who sings, what they have chosen "
                           "and why"),
        I(T.interview, brief="the vicar on Christmas morning in a fishing town: the service, the empty chairs "
                             "kept for those at sea, and the year"),
        I(T.vox_pop, brief="Miles at the church door: one question: what Christmas morning means to you"),
        I(T.feature, brief="the reading: a child from the Sunday school reads the Christmas story, and how they "
                           "practised"),
        # the order wraps back to here
        I(T.links, brief=("Dana: the next carol, and a word about it", "Dana: the collection and where it goes",
                          "Dana: the service ending and the bells")),
        I(T.interview, brief=("the organist, forty Christmases at the keys", "the volunteers who decorated the "
                              "church", "someone who comes back to Port Wexley every Christmas")),
    ),
    loop_from=6,
    closing=(I(T.links, "close", brief="Dana's happy Christmas from the church, and the swim at eleven",
               target_s=30.0),),
    target_s={T.bumper: 8.0, T.links: 45.0, T.feature: 120.0, T.interview: 150.0, T.vox_pop: 60.0},
    cast=("anchor", "reporter"), lead="anchor",
    cast_by_type={T.links: ("anchor",), T.interview: ("anchor", "guest"),
                  T.feature: ("anchor", "reporter", "guest"), T.vox_pop: ("anchor", "reporter", "guest")},
    station="The Christmas Morning Service, channel 7 at the harbour church in Port Wexley",
    tone="gentle, reverent but warm; a community at its best, never preachy",
    light=True, repeats_overnight=False, location="village_hall",
)

SWIM = Show(
    "swim", "THE CHRISTMAS DAY SWIM", "THE SWIM", (40, 120, 170),
    # The town's sea swim on the seafront: costumes, the plunge, the lifeboat standing by, the money raised.
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Miles on the seafront: the crowd, the costumes, the sea temperature and how long "
                             "until the plunge", target_s=45.0),
        I(T.vox_pop, brief="swimmers in costume before the plunge: who they are dressed as and why they do it"),
        I(T.interview, brief="the organiser: how many are in this year, the charity, and the safety talk"),
        I(T.feature, brief="THE PLUNGE: the countdown, the run into the sea, the shrieks and who stayed in "
                           "longest"),
        # the order wraps back to here
        I(T.interview, brief=("a lifeboat volunteer standing by in the water", "a swimmer straight out of the sea, "
                              "still shaking", "the oldest swimmer in the line", "a first-timer who said they "
                              "never would")),
        I(T.vox_pop, brief=("the people watching from the promenade: one question: would you go in",
                            "the swimmers in towels: one question: how cold was it",
                            "families with flasks: one question: what comes next today")),
        I(T.links, brief=("Miles: how much has been raised so far", "Miles: the hot drinks queue and the "
                          "warm-up", "Miles: the best costume of the morning")),
    ),
    loop_from=5,
    closing=(I(T.links, "close", brief="Miles signs off from the seafront: the swim, the money, and what's on next",
               target_s=30.0),),
    target_s={T.bumper: 8.0, T.links: 45.0, T.interview: 120.0, T.feature: 120.0, T.vox_pop: 60.0},
    cast=("reporter",), lead="reporter",
    cast_by_type={T.links: ("reporter",), T.interview: ("reporter", "guest"),
                  T.feature: ("reporter", "guest"), T.vox_pop: ("reporter", "guest")},
    station="The Christmas Day Swim, channel 7 live from the seafront in Port Wexley, with Miles Okafor",
    tone="cheerful, cold and silly; brave people in daft costumes, warmly cheered",
    light=True, repeats_overnight=False, location="seafront", tod="day",
)

MAYOR = Show(
    "mayor", "THE MAYOR'S CHRISTMAS MESSAGE", "MESSAGE", (110, 30, 40),
    # Ten minutes at three o'clock: the town's own Christmas message, from Helen Strand in the council chamber.
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Dana introduces the Mayor's Christmas message, in a line or two", target_s=20.0),
        I(T.interview, brief="HELEN STRAND's Christmas message to the town, to camera", target_s=330.0),
    ),
    closing=(I(T.links, "close", brief="Dana: that was the Mayor's message; Christmases Past follows",
               target_s=20.0),),
    target_s={T.bumper: 8.0, T.links: 20.0, T.interview: 330.0},
    cast=("anchor",), lead="anchor",
    cast_by_type={T.links: ("anchor",), T.interview: ("guest",)},
    station="The Mayor's Christmas Message, on channel 7",
    tone="warm, measured and local; a mayor speaking to her town, not a politician",
    light=True, repeats_overnight=False,
)

PAST = Show(
    "past", "CHRISTMASES PAST", "PAST", (120, 90, 50),
    # Hugh on the town's Christmases: old photographs, memories, the year the harbour froze.
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Hugh introduces an afternoon of Port Wexley Christmases past", target_s=40.0),
        I(T.feature, brief=("the cannery Christmas parties, from the photographs and the people who were there",
                            "the Christmas the harbour froze, and the boats that couldn't go out",
                            "Christmas at the lighthouse when it still had a keeper",
                            "the old Harrow Street Christmas market and its lights")),
        I(T.interview, brief=("a resident who remembers the town's Christmases sixty years ago",
                              "someone whose family has kept the same Christmas tradition for generations")),
        T.ad_break,
    ),
    loop_from=2,
    closing=(I(T.links, "close", brief="Hugh's last word on Christmases past", target_s=30.0),),
    target_s={T.bumper: 8.0, T.links: 40.0, T.feature: 150.0, T.interview: 150.0, T.ad_break: 60.0},
    cast=("historian",), lead="historian",
    cast_by_type={T.links: ("historian",), T.feature: ("historian", "guest"), T.interview: ("historian", "guest")},
    station="Christmases Past, Port Wexley's Christmases remembered on channel 7, with Hugh Tremayne",
    tone="warm, nostalgic and gently funny; true to the town's past as the record has it",
    light=True, repeats_overnight=False,
)

NEW_SHOWS = (TALES, MIDNIGHT, CAROLS, SWIM, MAYOR, PAST)

# ------------------------------------------------------------------ versions of the regular shows

_COASTWIDE_EVE = replace(
    SHOWS["magazine"], title="COASTWIDE ON CHRISTMAS EVE",
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Pat and Clive on the quay for the carols: the lanterns, the brass band tuning up, "
                                 "the crowd and the mince pies"),
        I(T.vox_pop, brief="the crowd at the carols: what makes Christmas Eve in Port Wexley"),
        I(T.feature, brief="the Salting Harmony choir and the brass band: who plays, who sings, and the carol they "
                           "love most"),
        I(T.interview, brief="the lifeboat crew's coxswain on the quay: the boat lit up for Christmas, and who is "
                             "on call"),
        T.ad_break,
        # the order wraps back to here
        T.links,
        I(T.feature, brief=("the mince pies and the mulled wine: who baked, who stirred, and the queue",
                            "the lantern makers: the children's lanterns and the one that caught fire last year",
                            "the boats strung with lights in the harbour, and the skippers who do it",
                            "the collection for the lifeboat: the tins and the total so far")),
        I(T.interview, brief=("someone home for Christmas after a long time away",
                              "a shopkeeper who has just shut up shop for Christmas",
                              "someone working tonight: a nurse, a ferry hand, a bus driver")),
        I(T.vox_pop, brief=("one question: your favourite carol", "one question: what you still have to wrap",
                            "one question: the best present you ever got")),
        T.ad_break,
    ),
    loop_from=6,
    closing=(I(T.links, "close", brief="happy Christmas Eve from the quay, and Hugh's Christmas Tales next"),),
    briefs={T.links: ("Pat and Clive by the brass band: the next carol and who is singing it",
                      "Pat and Clive: the lifeboat collection so far, and a cracker joke",
                      "Pat and Clive: the crowd thinning, and what's left to do before tomorrow")},
    station="Coastwide on Christmas Eve, live from the carols on the quay in Port Wexley, on channel 7",
    tone="warm, festive and gently funny; the town together on a cold Christmas Eve",
    location="harbour", tod="night",
)

_COASTWIDE_DAY = replace(
    SHOWS["magazine"], title="COASTWIDE ON CHRISTMAS NIGHT",
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Pat and Clive in paper hats: how the town's Christmas Day went, and the night ahead"),
        I(T.feature, brief="Christmas dinner around the town: a family table, a cafe feeding those on their own, "
                           "and the lifeboat crew's"),
        I(T.interview, brief="a guest for Christmas night: someone who had a remarkable year in Port Wexley"),
        T.vox_pop,
        T.ad_break,
        # the order wraps back to here
        T.links,
        I(T.feature, brief=("the swim this morning, and how the swimmers' afternoon went",
                            "the presents: the best and the worst the town got today",
                            "Christmas on duty: the hospital ward, the ferry, the police station",
                            "the leftovers: what the town does with them")),
        I(T.interview, brief=("someone who spent Christmas helping others", "a grandparent with stories of "
                              "Christmases long ago", "someone who had their first Christmas in Port Wexley")),
        I(T.vox_pop, brief=("one question: the best bit of today", "one question: the cracker joke of the year",
                            "one question: what you are watching tonight")),
        T.ad_break,
    ),
    loop_from=5,
    closing=(I(T.links, "close", brief="Pat and Clive's happy Christmas, and the news, then The Last Ferry"),),
    briefs={T.links: ("Pat and Clive: what viewers have sent in today", "Pat and Clive pull a cracker and read "
                      "the joke", "Pat and Clive: the Christmas telly they will fall asleep to"),
            T.vox_pop: ("one question: the best present you gave today", "one question: who did the washing up",
                        "one question: what you will do on Boxing Day")},
    station="Coastwide on Christmas Night, channel 7's Christmas evening magazine",
    tone="festive, full and sleepy; paper hats, gentle jokes, the town's Christmas told warmly",
)

_LATE_EVE = replace(
    SHOWS["late"], title="THE LAST FERRY: CHRISTMAS EVE",
    pattern=(
        T.bumper, I(T.monologue, "open", brief="Vincent's Christmas Eve monologue: the town's last-minute shopping, "
                                               "the carols on the quay, and Christmas in Port Wexley"),
        I(T.interview, brief="a public figure's Christmas Eve: their traditions and their year"), T.ad_break,
        I(T.interview, "cont"),
        I(T.interview, "couch", brief="a short second guest: someone with a Christmas story everyone in town knows"),
        I(T.vox_pop, brief="night owls on Christmas Eve: Miles asks people out late what they are waiting for"),
        # the order wraps back to here
        I(T.links, brief="Vincent reads a viewer's Christmas card, and answers it"),
        I(T.interview, brief="someone working on Christmas Eve night: a nurse, a ferry hand, a baker"), T.ad_break,
        I(T.interview, "cont"),
    ),
    loop_from=6,
    closing=(I(T.links, "close", brief="Vincent's happy Christmas, and Midnight on the Quay at half past eleven"),),
    station="The Last Ferry on Christmas Eve, Port Wexley's late-night talk show on channel 7",
)

_LATE_DAY = replace(
    SHOWS["late"], title="THE LAST FERRY: CHRISTMAS NIGHT",
    pattern=(
        T.bumper, I(T.monologue, "open", brief="Vincent's Christmas night monologue: the day the town had, and what "
                                               "everyone is too full to do"),
        I(T.interview, brief="a guest's Christmas Day, told well"), T.ad_break, I(T.interview, "cont"),
        I(T.interview, "couch", brief="a short second guest with the funniest Christmas Day in town"),
        # the order wraps back to here
        I(T.links, brief="Vincent's Christmas night letters from viewers"),
        I(T.interview, brief="someone who worked today so others could have Christmas"), T.ad_break,
        I(T.interview, "cont"),
    ),
    loop_from=5,
    closing=(I(T.links, "close", brief="Vincent's goodnight on Christmas night, and Boxing Day tomorrow"),),
    station="The Last Ferry on Christmas Night, Port Wexley's late-night talk show on channel 7",
)

_BREAKFAST_DAY = replace(
    SHOWS["breakfast"], title="MORNING TIDE: CHRISTMAS MORNING",
    pattern=(T.bumper, I(T.bulletin, "open"), T.sofa, T.weather, T.field_report, T.sofa, T.ad_break,
             T.sofa, T.sofa, T.field_report, T.interview, T.sofa, T.ad_break),
    loop_from=7,
    briefs={
        T.sofa: ("the presents the hosts opened this morning", "viewers' Christmas morning messages, read out",
                 "Christmas dinner: who's cooking what, and the timings", "the cracker jokes, tested on each other",
                 "Christmas traditions in the town: the swim, the bells, the walk", "will it snow: the hosts decide"),
        T.field_report: ("the first walkers on the beach on Christmas morning", "the hospital ward's Christmas "
                         "morning", "the lifeboat station: the crew on call over Christmas",
                         "the swim's volunteers setting up on the seafront"),
        T.interview: ("someone who has been Father Christmas in the town for years",
                      "a chef cooking Christmas dinner for people on their own"),
    },
    closing=(I(T.sofa, "close", brief="happy Christmas from the sofa, and the Christmas Morning Service at ten"),),
    station="Morning Tide on Christmas morning, Port Wexley's breakfast show on channel 7",
    tone="excited, cosy and silly; Christmas morning on the sofa, warm to everyone watching",
)

_ROCKPOOL_DAY = replace(
    SHOWS["rockpool"], title="ROCK POOL'S CHRISTMAS",
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Poppy and Gully in Christmas jumpers: happy Christmas, and what Gully got",
          target_s=45.0),
        I(T.links, brief="THE CHRISTMAS MAKE: Poppy makes a paper chain or a cracker from things at home, step by "
                         "step; Gully helps badly", target_s=180.0),
        I(T.interview, brief="A CHRISTMAS VISITOR: Hector the donkey with his owner, in tinsel"),
        I(T.links, brief="CHRISTMAS STORY TIME: Hugh Tremayne (\"historian\") reads a gentle winter legend of the "
                         "coast for children", target_s=240.0),
        I(T.links, brief="GULLY'S CHRISTMAS POEM: four to eight rhyming lines about his Christmas dinner",
          target_s=60.0),
        I(T.links, brief="CHRISTMAS LETTERS AND DRAWINGS: Gully reads out children's Christmas letters and Poppy "
                         "describes their drawings", target_s=90.0),
    ),
    loop_from=2,
    closing=(I(T.links, "close", brief="Poppy and Gully's happy Christmas; Gully gets the last word", target_s=35.0),),
    station="Rock Pool's Christmas, channel 7's children's programme on Christmas Day",
)

_OUTABOUT_DAY = replace(
    SHOWS["outabout"], title="OUT AND ABOUT AT CHRISTMAS",
    pattern=(
        T.bumper,
        I(T.field_report, "open", brief="Meg on the coast path on Christmas Day: where she is going this afternoon",
          target_s=45.0),
        I(T.feature, brief="the lifeboat crew's Christmas lunch at the station, between call-outs"),
        T.vox_pop,
        I(T.feature, brief="the hospital ward's Christmas: the nurses, the patients and the paper hats"),
        T.ad_break,
        # the order wraps back to here
        I(T.feature, brief=("the lighthouse on Christmas Day", "a Christmas walk on the estuary with the birds",
                            "the cafe that opens on Christmas Day for anyone on their own")),
        T.vox_pop,
    ),
    loop_from=6,
    closing=(I(T.field_report, "close", brief="Meg signs off from the coast as the light goes", target_s=40.0),),
    briefs={T.vox_pop: ("Christmas walkers: the best Christmas walk on the coast",
                        "people out walking off dinner: one question: how much did you eat")},
    station="Out and About at Christmas, channel 7's Christmas afternoon on the coast, with Meg Trethewey",
)

_SWIM_BOXING = replace(
    SWIM, title="THE BOXING DAY DIP", ticker="THE DIP",
    station="The Boxing Day Dip, channel 7 live from the seafront in Port Wexley, with Miles Okafor",
)

_QUAYSIDE_BOXING = replace(
    SHOWS["quayside"], title="QUAYSIDE: THE BOXING DAY SALES",
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Howard on the Boxing Day sales: the queues on Harrow Street and what the shops "
                                 "hope for", target_s=50.0),
        I(T.field_report, brief="Miles on Harrow Street: the first queue, the doors opening, the bargains"),
        I(T.interview, brief="a shopkeeper on Christmas trade: a good one or a bad one, honestly"),
        I(T.consumer, brief="the sales: real bargains and false ones, and returning presents"),
        T.ad_break,
        I(T.vox_pop, brief="Miles asks shoppers one question: the best buy of the morning"),
    ),
    loop_from=1,
    closing=(I(T.links, "close", brief="Howard's verdict on the town's Christmas trade"),),
    station="Quayside on Boxing Day, channel 7's business half hour, with Howard Lanyon",
)

_SPORT_BOXING = replace(
    SHOWS["sport"], title="FULL TIME: BOXING DAY",
    pattern=(
        T.bumper,
        I(T.sport, "open", brief="Fran on Boxing Day's sport: the Tides and the Wreckers both at home, and the "
                                 "latest as the briefing has it"),
        I(T.field_report, brief="Tamsin at Tidewater Stadium: before kick-off the crowd and the teams; after the "
                                "final whistle the result and the reaction"),
        I(T.vox_pop, brief="Tamsin among the Boxing Day crowd: one question: your Boxing Day tradition"),
        I(T.sport, brief="the Wreckers at the Quarry Field: before kick-off the build-up; after it, the result"),
        I(T.interview, brief="a guest from the Tides or the Wreckers on playing at home on Boxing Day"),
    ),
    loop_from=1,
    closing=(I(T.sport, "close", brief="the Boxing Day results, as they stand, and back to the studio"),),
    station="Full Time on Boxing Day, the sport from Port Wexley on channel 7",
    location="stadium",
)

# ------------------------------------------------------------------ the days

_REGULAR = dict(SCHEDULE)


def _grid(changes: dict, drop: tuple = ()) -> tuple:
    """The regular day with these slots changed or added, and those dropped, in time order."""
    from .schedule import hour_min

    rows = {k: v for k, v in _REGULAR.items() if k not in drop}
    rows.update(changes)
    return tuple(sorted(rows.items(), key=lambda kv: hour_min(kv[0])))


DAYS: dict[str, tuple[tuple, dict[str, Show]]] = {
    EVE: (_grid({20: "tales", "23:30": "midnight"}, drop=("20:30",)),
          {"magazine": _COASTWIDE_EVE, "late": _LATE_EVE}),
    DAY: ((
        (0, "midnight"), ("00:30", "overnight"), (7, "breakfast"), (10, "carols"), (11, "swim"), (12, "news"),
        ("12:15", "rockpool"), (13, "outabout"), (14, "news"), (15, "mayor"), ("15:10", "past"), (16, "news"),
        (19, "magazine"), (21, "news"), (22, "late"), (23, "news"),
    ), {"breakfast": _BREAKFAST_DAY, "rockpool": _ROCKPOOL_DAY, "outabout": _OUTABOUT_DAY,
        "magazine": _COASTWIDE_DAY, "late": _LATE_DAY}),
    BOXING: (_grid({11: "swim", 12: "news", 14: "sport"}),
             {"swim": _SWIM_BOXING, "quayside": _QUAYSIDE_BOXING, "sport": _SPORT_BOXING}),
}

# ------------------------------------------------------------------ the writers' prompts for the new programmes


def systems(common: str, guest_rules: str) -> dict[str, dict[T, str]]:
    """Each new programme's prompts, per item type (writers.SHOW_SYSTEMS)."""
    to_camera = ("These are {who}'s words TO CAMERA (\"{id}\" alone), as THIS ITEM and the PLACE IN THE SHOW say. "
                 "Nobody else speaks. Do not open a news story; thread_id is null.\nheadline = the point in under "
                 "12 words. lower_third = \"{title}\" plus a short tag.\n")
    vox = ("This is a VOX POP: {lead} hands over in a line; Miles (\"reporter\") asks THIS ITEM's question; three "
           "or four people answer in a line or two each, each speaker \"guest\" with their own guest_name (first "
           "name and surname), guest_gender and guest_age. question = the question as a caption. Backdrop: where "
           "the programme is (ON LOCATION gives it); location is the place in words. thread_id is null.\n")
    guest = (guest_rules + "This is {lead} with ONE GUEST, as THIS ITEM says: their own words, specific and warm, "
             "a story or two; short questions. Do not open a news story; thread_id is null.\nheadline = what the "
             "guest said, under 12 words. lower_third = a short caption.\n")
    feature = (guest_rules + "This is a FILMED PIECE, as THIS ITEM says: the presenter or Miles (\"reporter\") "
               "on the spot, one person who is part of it (speaker \"guest\"), real detail. Backdrop: where the "
               "programme is (ON LOCATION gives it), else a fitting one from LOCATIONS; location is the place in "
               "words. thread_id is null.\nheadline = the piece in under 12 words. lower_third = a short caption.\n")
    return {
        "tales": {T.links: common + to_camera.format(who="Hugh Tremayne", id="historian", title="Christmas Tales")
                  + "When THIS ITEM is a TALE, tell it whole, as a storyteller by the fire: a beginning, a turn and "
                    "an end, in the town's places, kept to the word budget, in six to ten lines of two to four "
                    "sentences each (a line is a breath, never the whole tale: one line of a thousand characters "
                    "failed twice). A legend is a legend: never claim it happened, and say where the story comes "
                    "from. No welcome: the programme is under way.\n"},
        "midnight": {T.links: common + to_camera.format(who="Dana", id="anchor", title="Midnight on the Quay"),
                     T.interview: common + guest.format(lead="Dana (\"anchor\")"),
                     T.vox_pop: common + vox.format(lead="Dana (\"anchor\")")},
        "carols": {T.links: common + to_camera.format(who="Dana", id="anchor", title="Christmas Morning Service")
                   + "Speak quietly, as in a church; nobody sings in the script, but say what is being sung.\n",
                   T.interview: common + guest.format(lead="Dana (\"anchor\")"),
                   T.feature: common + feature,
                   T.vox_pop: common + vox.format(lead="Dana (\"anchor\")")},
        "swim": {T.links: common + to_camera.format(who="Miles", id="reporter", title="The Swim"),
                 T.interview: common + guest.format(lead="Miles (\"reporter\")"),
                 T.feature: common + feature,
                 T.vox_pop: common + vox.format(lead="Miles (\"reporter\")").replace(
                     "{lead} hands over in a line; ", "")},
        "mayor": {T.links: common + to_camera.format(who="Dana", id="anchor", title="The Mayor's Christmas Message"),
                  T.interview: common + "This is HELEN STRAND, the Mayor, speaking her Christmas message TO CAMERA: "
                  "every line is speaker \"guest\" with guest_name \"Helen Strand\", guest_role \"Mayor of Port "
                  "Wexley\". Nobody else speaks. A real message: the town's year as the briefing has it (its good "
                  "news and its hard times, by name where the record has them), thanks to those who kept it going, "
                  "a thought for those at sea and those on their own, and a wish for the year ahead. No party "
                  "politics, no promises. thread_id is null.\nheadline = the message in under 12 words. "
                  "lower_third = \"The Mayor's Christmas Message\".\n"},
        "past": {T.links: common + to_camera.format(who="Hugh Tremayne", id="historian", title="Christmases Past"),
                 T.feature: common + feature.replace("Miles (\"reporter\")", "Hugh (\"historian\")"),
                 T.interview: common + guest.format(lead="Hugh (\"historian\")")},
    }


# Each new programme's spoken ident, and the show whose music it borrows (assets.IDENTS, IDENT_MUSIC).
IDENTS = {
    "tales": ("Hugh's Christmas Tales, on channel seven.", "late"),
    "midnight": ("Midnight on the Quay, on channel seven.", "news"),
    "carols": ("The Christmas Morning Service, on channel seven.", "chamber"),
    "swim": ("Live from the seafront, on channel seven.", "outabout"),
    "mayor": ("The Mayor's Christmas Message, on channel seven.", "chamber"),
    "past": ("Christmases Past, on channel seven.", "inquiry"),
}
# Its set, when it has no location of its own (scenes.SHOW_SETS).
SETS = {"tales": "studio_late", "mayor": "council_chamber", "past": "studio_interview"}

def places(middle: str) -> dict:
    """Where an item is in its programme (writers._PLACE): the middle of it, unless THIS ITEM opens or closes it.
    Without one, Hugh opened a tale in the middle of the hour with "Good evening, and welcome"."""
    from . import writers

    return {(s.id, t): {"": middle.format(title=writers._title(s), extra="")}
            for s in NEW_SHOWS for t in {e if isinstance(e, T) else e.type for e in s.pattern}
            if t not in (T.bumper, T.ad_break)}


# On the air: the new programmes join the shows, and the days the special days (schedule.special_day).
SHOWS.update({s.id: s for s in NEW_SHOWS})
SPECIAL_DAYS.update(DAYS)


def template(show_id: str, seg_type, world, rng, part: str, work: dict, brief: str):
    """A stand-in when the model is down: the Mayor's own short message, and otherwise the stock one with any
    presenter who isn't in the programme spoken by its lead (Miles has no place in Christmases Past)."""
    from . import writers
    from .models import GuestLine, InterviewScript
    from .schedule import SHOWS

    show = SHOWS[show_id]
    if show_id == "mayor" and seg_type is T.interview:
        said = ["Good afternoon, and happy Christmas from the council chamber.",
                f"It has been a full year in {world.town}, and I want to thank everyone who kept the town going "
                "through it: the lifeboat crew, the nurses, the shops that stayed open late, and every neighbour "
                "who knocked on a door.",
                "Today I am thinking of those at sea, and of anyone spending Christmas on their own. If that is "
                "you, the cafe on the quay has a seat for you.",
                "I wish you all a happy Christmas, and a kind new year."]
        return InterviewScript(lines=[GuestLine(speaker="guest", text=t) for t in said],
                               headline="The Mayor's Christmas message", lower_third="The Mayor's Christmas Message",
                               guest_name="Helen Strand", guest_role="Mayor of Port Wexley", guest_gender="f")
    script = writers._template(seg_type, world, rng, show, part, work)
    cast = set(show.cast_for(seg_type)) | {"guest"}
    for line in script.lines:
        if line.speaker not in cast:
            line.speaker = show.lead
    return script
