"""Where Port Wexley's places are: the gazetteer, the coast in order, and a route check.

Nothing else in the code says where one place is from another, so every writer used to invent its own
lie of the land (2026-11-20: a Coast Road leg sailed for Saltby from the town quay, tied up at the fish
quay in town, and only then crossed). This module is the one map. Its drawing is tools/town_map.py.

The shape, from teletext.COAST: the Grey estuary runs up from the south-west, Port Wexley is on its
eastern shore, Saltby straight across on the western. Below the town the estuary widens into the bay,
between Greymouth Point (the lighthouse, on the Saltby side) and Wexley Point; above it, the Salting
and Wexley Woods, up to Polgrey Bridge at the head, the lowest bridge over the Grey.

- PLACES: each place, its side of the Grey, its district (a council ward, or the village), the backdrop
  that shows it, where it is (miles east and north of the Quay Steps), and `at`, the stop on the coast
  she passes it by. `canon` quotes what the town already says of it; empty means it was chosen here.
- COAST: the shore in order, west to east the long way round, by the head of the estuary. The foot
  ferry is the short cut across it; the coast bus goes round by the bridge.
- LINKS: neighbours, with the miles between them, for travel times on foot, by bike, by bus, by ferry.
- check_route(): a Coast Road leg's stops run one way along COAST, and cross the Grey only by the ferry
  (from its landing) or round by the bridge; a leg starts on the side of the water where the last ended.

Pure data and plain functions: nothing here reads the town, so the map tool and the tests import it alone.
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

EAST, WEST, HEAD = "east", "west", "head"          # Port Wexley's shore, Saltby's, and the bridge at the top
SIDE_NAMES = {EAST: "the Port Wexley side", WEST: "the Saltby side", HEAD: "the head of the estuary"}


@dataclass(frozen=True)
class Place:
    id: str
    name: str
    side: str
    district: str
    at: str                                    # the COAST stop she passes it by (itself, for a stop)
    xy: tuple[float, float]                    # miles east and north of the Quay Steps
    backdrop: str = ""                         # the locations.py id that shows it
    aliases: tuple[str, ...] = ()              # how a writer might name it (lower case, whole words)
    note: str = ""                             # a few words for the writers
    canon: str = ""                            # what the town already says; empty: chosen with the map
    town: bool = False                         # in the town inset of the map, not the area


def _p(id, name, side, district, at, xy, backdrop="", aliases=(), note="", canon="", town=False) -> Place:
    return Place(id, name, side, district, at or id, xy, backdrop, tuple(aliases), note, canon, town)


TOWN_WARDS = ("Harbour", "Quay", "Harrow Street", "Cannery", "the Salting", "Saltby")    # council.py

PLACES: tuple[Place, ...] = (
    # ------------------------------------------------ the Saltby side, from the west
    _p("greymouth", "Greymouth", WEST, "Greymouth", "", (-11.0, -2.6), "",
       ("greymouth town",),
       "the district's big town, round Greymouth Point: the pool, the cottage hospital, Greymouth Athletic",
       "\"went to Greymouth ... came back on the Saltby ferry\"; the pool and Greymouth Cottage Hospital"),
    _p("greymouth_point", "Greymouth Point", WEST, "Saltby", "", (-4.2, -3.0), "lighthouse",
       ("greymouth point", "lighthouse", "greymouth light", "lighthouse café", "lighthouse cafe"),
       "the lighthouse (112 steps) and the Lighthouse Café, at the mouth of the bay",
       "\"rowing eleven miles from the harbour wall to the Greymouth lighthouse and back\"; the café's view "
       "\"all the way to Saltby\""),
    _p("west_cliffs", "the west cliffs", WEST, "Saltby", "", (-2.9, -1.9), "coast_road",
       ("west cliffs", "saltby cliffs", "cliff path"),
       "the coast road along the cliffs from Saltby to the lighthouse"),
    _p("saltby_sands", "Saltby sands", WEST, "Saltby", "", (-1.75, -0.8), "seafront",
       ("saltby sands", "saltby beach", "beach at saltby", "saltby pier", "pier theatre"),
       "the beach at Saltby and the little pier, with its summer theatre",
       "\"the beach at Saltby\"; \"summers at the Saltby pier theatre\""),
    _p("cliff_road", "Cliff Road", WEST, "Saltby", "", (-1.45, 0.05), "residential_street",
       ("cliff road",), "Saltby's houses along the cliff top",
       "\"Cliff Road pupils take the Saltby ferry to school\""),
    _p("saltby", "Saltby", WEST, "Saltby", "", (-1.15, 0.75), "village",
       ("saltby", "saltby green", "saltby village", "saltby village hall", "village hall", "crown at saltby",
        "saltby church", "saltby yard", "saltby boatyard", "saltby road", "saltby lane"),
       "the village across the water: the green, the church spire and orchard, the Crown, the village hall, the "
       "boatyard",
       "the village set; the Crown at Saltby (darts.py); \"apprentice boatbuilder at the Saltby yard\""),
    _p("saltby_slip", "the Saltby slip", WEST, "Saltby", "", (-0.7, 0.5), "slipway",
       ("saltby slip", "saltby ferry slip", "ferry slip at saltby", "saltby landing"),
       "the foot ferry's landing on the Saltby side; it dries at low water",
       "tides.py: \"the Saltby landing dries out\""),
    # ------------------------------------------------ the head of the estuary
    _p("polgrey", "Polgrey", HEAD, "Polgrey", "", (2.7, 4.5), "village",
       ("polgrey", "polgrey bridge", "the bridge"),
       "the village at the head of the estuary, where Polgrey Bridge crosses the Grey",
       "Polgrey Rangers (sport.py)"),
    # ------------------------------------------------ the Port Wexley side, downstream from the head
    _p("wexley_woods", "Wexley Woods", EAST, "the Salting", "", (1.9, 2.5), "woods",
       ("wexley woods", "the woods", "estuary path"),
       "woods above the estuary, the footpath along the shore below them",
       "\"Honey from the hives above Wexley Woods\""),
    _p("the_salting", "the Salting", EAST, "the Salting", "", (0.85, 1.45), "estuary",
       ("the salting", "salting", "salting lane", "salting reserve", "salting chapel"),
       "the marsh reserve on the town's edge, upstream: mudflats, reeds and waders; the allotments, the chapel, "
       "the bonfire field",
       "the Salting ward; \"the town bonfire and fireworks on the Salting\"; the reserve's warden (wildlife.py)"),
    _p("harbour", "Port Wexley harbour", EAST, "Quay", "", (0.0, 0.0), "harbour",
       ("harbour", "quay steps", "harbour steps", "ferry steps", "town quay", "harbour wall", "harbour front",
        "harbour office", "ferry office", "loading dock", "harbour row", "gull's rest"),
       "the harbour: Harbour Row along it, the Quay Steps where the Saltby ferry goes from, the loading dock",
       "the ferry advert: \"Harbour steps, half-hourly from seven\"; \"Quay Steps to the Lighthouse\" swim"),
    _p("fish_quay", "the fish quay", EAST, "Quay", "", (0.15, -0.3), "fish_quay",
       ("fish quay", "auction", "fish market"), "the fish quay and the weekday auction, just below the steps"),
    _p("cannery", "the old cannery", EAST, "Cannery", "", (0.3, -0.6), "cannery",
       ("cannery", "cannery slipway", "cannery lane", "tallow lane", "old boatyard"),
       "the old cannery and its slipway, below the fish quay; Tallow Lane behind",
       "\"Tallow Lane, behind the old cannery\", \"just by the old boatyard\""),
    _p("seafront", "the seafront", EAST, "Harbour", "", (0.35, -1.25), "seafront",
       ("seafront", "promenade", "prom", "bandstand", "the beach"),
       "the promenade and the town beach, facing the bay"),
    _p("lifeboat_station", "the lifeboat station", EAST, "Harbour", "", (0.2, -1.75), "lifeboat_station",
       ("lifeboat station", "lifeboat slip", "boathouse"),
       "the boathouse and launch ramp at the end of the promenade"),
    _p("east_cliffs", "the coast road", EAST, "Harbour", "", (-0.35, -2.7), "coast_road",
       ("coast road", "east cliffs", "wexley cliffs"),
       "the coast road along the cliffs from the town to Wexley Point and on to Kessick Bay"),
    _p("wexley_point", "Wexley Point", EAST, "Harbour", "", (-0.9, -3.8), "coast_road",
       ("wexley point",), "the headland on the town's side of the bay's mouth",
       "\"lamp oil maker, Wexley Point\""),
    _p("kessick_bay", "Kessick Bay", EAST, "Kessick Bay", "", (2.6, -4.1), "harbour",
       ("kessick bay", "kessick", "kessick road"),
       "the next village east, round Wexley Point, in its own cove",
       "Kessick Bay (sport.py); \"did she reach Kessick Bay and back\""),
    _p("carrow_point", "Carrow Point", EAST, "Carrow Point", "", (5.9, -4.7), "lighthouse",
       ("carrow point",), "a fishing village on the next headland east", "Carrow Point (sport.py)"),
    _p("pellow_harbour", "Pellow Harbour", EAST, "Pellow Harbour", "", (9.6, -4.4), "harbour",
       ("pellow harbour", "pellow"), "the little harbour town at the east end of the bus route",
       "Pellow Harbour (sport.py)"),
    # ------------------------------------------------ the town itself (the map's inset)
    _p("harrow_street", "Harrow Street", EAST, "Harrow Street", "harbour", (0.45, 0.12), "market",
       ("harrow street", "harrow street market", "market"),
       "the shopping street up from the harbour, with the market",
       "Harrow Street market (a landmark); the Harrow Street ward", town=True),
    _p("main_street", "Main Street", EAST, "Harrow Street", "harbour", (0.8, 0.45), "main_street",
       ("main street", "high street", "post office", "bus stop"),
       "the old high street across the top of Harrow Street: the bus stop, the post office, the tailor",
       "\"Brenda Fisk, tailor of Main Street\"; \"saddler, Main Street\"", town=True),
    _p("town_hall", "Wexley Town Hall", EAST, "Harrow Street", "harbour", (1.05, 0.3), "town_hall",
       ("town hall", "council chamber", "clock tower"), "the town hall and its clock, at the top of Main Street",
       "the Wexley Town Hall clock (a landmark)", town=True),
    _p("harbour_church", "the harbour church", EAST, "Quay", "harbour", (0.25, 0.45), "church",
       ("harbour church", "gull lane", "chandlery", "quay lane"),
       "the harbour church above the steps; Gull Lane and the chandlery behind", town=True),
    _p("park", "Wexley Park", EAST, "Harbour", "seafront", (0.85, -0.5), "park",
       ("wexley park", "the park", "duck pond"), "the park between the town and the seafront", town=True),
    _p("lantern_row", "Lantern Row", EAST, "Harbour", "seafront", (0.6, -0.9), "residential_street",
       ("lantern row",), "terraced houses above the seafront", town=True),
    _p("greenhill_road", "Greenhill Road", EAST, "Harrow Street", "harbour", (1.35, 0.05), "residential_street",
       ("greenhill road", "bowling green"), "the road up Harrow Hill, with the bowling green",
       "the Greenhill Road bowling green", town=True),
    _p("station", "the station", EAST, "Harrow Street", "harbour", (1.3, 0.9), "main_street",
       ("railway station", "the station", "mill lane", "the railway"),
       "the railway station at the top of the town, the Railway pub and Mill Lane by it",
       "Okonkwo's Taxis: \"Saltby, the station, the lighthouse\"; \"Mill Lane, just up from the Railway\"",
       town=True),
    _p("school", "Greymouth Academy", EAST, "Harrow Street", "the_salting", (1.05, 1.15), "school",
       ("greymouth academy", "the academy", "the school"), "the secondary school, on the Salting side of the town",
       town=True),
    _p("stadium", "Tidewater Stadium", EAST, "the Salting", "the_salting", (1.6, 1.35), "stadium",
       ("tidewater stadium", "tidewater road", "the stadium"), "the Tides' ground, off Tidewater Road",
       "Tidewater Stadium (a landmark)", town=True),
    _p("quarry_field", "the Quarry Field", EAST, "Cannery", "cannery", (1.7, -0.45), "quarry_field",
       ("quarry field", "the quarry"), "Port Wexley RFC's ground, under the old quarry face on Harrow Hill",
       town=True),
    _p("industrial_estate", "the industrial estate", EAST, "the Salting", "the_salting", (1.95, 1.0), "factory",
       ("industrial estate",), "the units on the Polgrey road out of town", town=True),
    _p("fire_station", "the fire station", EAST, "Harrow Street", "harbour", (1.0, 0.65), "fire_station",
       ("fire station",), "the fire station on Main Street", town=True),
    _p("police_station", "the police station", EAST, "Harrow Street", "harbour", (0.55, 0.7), "police_station",
       ("police station",), "the police station off Main Street", town=True),
    # ------------------------------------------------ the country behind the town
    _p("harrow_hill", "Harrow Hill", EAST, "Harrow Street", "seafront", (2.1, -0.3), "farm",
       ("harrow hill", "hill farm"), "the hill behind the town: farms, the old quarry, the view of the bay",
       "\"a light frost creeping onto the top of Harrow Hill\""),
)

BY_ID: dict[str, Place] = {p.id: p for p in PLACES}

# The shore in order, west to east the long way round, by the head of the Grey (a Coast Road leg runs
# along it one way or the other).
COAST: tuple[str, ...] = ("greymouth", "greymouth_point", "west_cliffs", "saltby_sands", "cliff_road", "saltby",
                          "saltby_slip", "polgrey", "wexley_woods", "the_salting", "harbour", "fish_quay",
                          "cannery", "seafront", "lifeboat_station", "east_cliffs", "wexley_point", "kessick_bay",
                          "carrow_point", "pellow_harbour")
ORDER: dict[str, int] = {pid: i for i, pid in enumerate(COAST)}

# The foot ferry (tides.py): the Quay Steps on the harbour to the Saltby slip, eight minutes, half-hourly.
FERRY = ("harbour", "saltby_slip")
FERRY_MIN = 8
LANDING = {EAST: "harbour", WEST: "saltby_slip"}

# Neighbours: (a, b, miles, how). "road": on foot, by bike, by the coast bus if both ends are on it;
# "path": on foot or by bike only; "ferry": the foot ferry.
LINKS: tuple[tuple[str, str, float, str], ...] = (
    ("greymouth", "greymouth_point", 7.0, "road"),
    ("greymouth", "saltby", 9.5, "road"),
    ("greymouth_point", "west_cliffs", 1.8, "road"),
    ("west_cliffs", "saltby_sands", 1.5, "road"),
    ("saltby_sands", "cliff_road", 0.9, "road"),
    ("cliff_road", "saltby", 0.6, "road"),
    ("saltby", "saltby_slip", 0.3, "path"),
    ("saltby", "polgrey", 5.0, "road"),
    ("polgrey", "wexley_woods", 2.3, "path"),
    ("polgrey", "main_street", 5.0, "road"),
    ("wexley_woods", "the_salting", 1.5, "path"),
    ("the_salting", "harbour", 1.4, "road"),
    ("the_salting", "stadium", 0.6, "road"),
    ("harbour", "fish_quay", 0.3, "road"),
    ("harbour", "harrow_street", 0.3, "road"),
    ("harrow_street", "main_street", 0.3, "road"),
    ("main_street", "station", 0.4, "road"),
    ("fish_quay", "cannery", 0.3, "road"),
    ("cannery", "seafront", 0.7, "road"),
    ("cannery", "quarry_field", 1.2, "road"),
    ("seafront", "lifeboat_station", 0.5, "road"),
    ("seafront", "harrow_hill", 1.8, "path"),
    ("lifeboat_station", "east_cliffs", 1.1, "road"),
    ("east_cliffs", "wexley_point", 1.3, "road"),
    ("wexley_point", "kessick_bay", 3.6, "road"),
    ("main_street", "kessick_bay", 4.8, "road"),
    ("kessick_bay", "carrow_point", 3.4, "road"),
    ("carrow_point", "pellow_harbour", 3.8, "road"),
    ("harbour", "saltby_slip", 0.85, "ferry"),
)
# The coast bus, hourly, end to end: Greymouth, Saltby, round by Polgrey Bridge, Port Wexley's Main Street,
# over the hill by the Kessick road, Kessick Bay, Carrow Point, Pellow Harbour.
BUS_ROUTE: tuple[str, ...] = ("greymouth", "saltby", "polgrey", "main_street", "kessick_bay", "carrow_point",
                              "pellow_harbour")
BUS_EVERY_MIN = 60
MIN_PER_MILE = {"foot": 20.0, "bike": 6.0, "bus": 2.5}

# A backdrop on its own (no place named) says where only when it shows one place. The rest (the slipway,
# the coast road, a farm, a pub, a tea room) could be on either side of the water.
BACKDROP_PLACE: dict[str, str] = {
    "fish_quay": "fish_quay", "lighthouse": "greymouth_point", "lifeboat_station": "lifeboat_station",
    "seafront": "seafront", "village": "saltby", "village_hall": "saltby", "estuary": "the_salting",
    "woods": "wexley_woods", "harbour": "harbour", "cannery": "cannery", "market": "harrow_street",
    "main_street": "main_street", "town_hall": "town_hall", "quarry_field": "quarry_field", "stadium": "stadium",
    "school": "school", "park": "park", "church": "harbour_church", "fire_station": "fire_station",
    "police_station": "police_station", "factory": "industrial_estate", "loading_dock": "harbour",
}


def side(pid: str) -> str:
    return BY_ID[pid].side


def stop_of(pid: str) -> str:
    """The COAST stop a place is passed by."""
    return BY_ID[pid].at


# ------------------------------------------------------------------ naming a place

def _alias_table() -> list[tuple[re.Pattern, str, int]]:
    rows = []
    for p in PLACES:
        for a in {p.name.lower(), *p.aliases}:
            rows.append((re.compile(r"\b" + re.escape(a) + r"\b", re.I), p.id, len(a)))
    return sorted(rows, key=lambda r: -r[2])


_ALIASES = _alias_table()


def place_for(text: str = "", backdrop: str = "", where: str = "") -> str | None:
    """The gazetteer's id for a place a writer named: its own id if it gave one, else the longest name in
    `text` that the gazetteer knows, else what the backdrop alone shows; None when it can't tell."""
    if where in BY_ID:
        return where
    for pat, pid, _ in _ALIASES:
        if pat.search(text or ""):
            return pid
    return BACKDROP_PLACE.get(backdrop or "")


# ------------------------------------------------------------------ getting about

def _neighbours() -> dict[str, list[tuple[str, float, str]]]:
    """LINKS both ways; a place with none of its own (a street in town) is a road from its coast stop."""
    out: dict[str, list[tuple[str, float, str]]] = {p.id: [] for p in PLACES}
    links = list(LINKS)
    linked = {a for a, *_ in LINKS} | {b for _, b, *_ in LINKS}
    for p in PLACES:
        if p.id not in linked:
            links.append((p.at, p.id, round(max(0.1, miles_between(p.at, p.id) * 1.3), 1), "road"))
    for a, b, miles, how in links:
        out[a].append((b, miles, how))
        out[b].append((a, miles, how))
    return out



def _round5(minutes: float) -> int:
    return max(5, int(5 * round(minutes / 5)))


def times(a: str, b: str, miles: float, how: str) -> dict[str, int]:
    """Minutes from a to b by each way that goes: on foot, by bike, by bus (when both are on its route,
    without the wait), by ferry (the crossing, without the wait)."""
    if how == "ferry":
        return {"ferry": FERRY_MIN}
    out = {"foot": _round5(miles * MIN_PER_MILE["foot"]), "bike": _round5(miles * MIN_PER_MILE["bike"])}
    if how == "road" and a in BUS_ROUTE and b in BUS_ROUTE:
        out["bus"] = _round5(miles * MIN_PER_MILE["bus"])
    return out


def neighbours(pid: str) -> list[tuple[str, float, dict[str, int]]]:
    """A place's neighbours: (id, miles, minutes by each way)."""
    return [(n, miles, times(pid, n, miles, how)) for n, miles, how in NEIGHBOURS[pid]]


def miles_between(a: str, b: str) -> float:
    """As the crow flies: for the map and for a rough idea, not for a timetable."""
    (x1, y1), (x2, y2) = BY_ID[a].xy, BY_ID[b].xy
    return math.hypot(x2 - x1, y2 - y1)


NEIGHBOURS = _neighbours()


# ------------------------------------------------------------------ a leg of the Coast Road

_BY_WATER = re.compile(r"ferry|boat|crossing|row(ing|ed)? (over|across)|across the (water|grey|estuary)|"
                       r"\bsands\b", re.I)


@dataclass
class Placed:
    """A stop, placed: its gazetteer id (None when the writer's words don't say where)."""
    label: str
    pid: str | None = None


def _monotone(seq: list[int]) -> bool:
    return all(a <= b for a, b in zip(seq, seq[1:])) or all(a >= b for a, b in zip(seq, seq[1:]))


def _sides(stops: list[Placed]) -> list[str]:
    return [BY_ID[s.pid].side for s in stops]


def check_leg(stops: list[Placed], travel: str) -> str | None:
    """Why a leg's stops won't do as a journey, or None. Stops the gazetteer can't place are left out.
    - On one side of the Grey, the stops run one way along COAST, never back to where she has been.
    - She crosses the Grey once at most: by the ferry, from the Quay Steps or the Saltby slip, after the
      stops on the near side have brought her to it; or by road, round by Polgrey Bridge, which is
      the same as running one way along COAST."""
    placed = [s for s in stops if s.pid]
    if len(placed) < 2:
        return None
    sides = _sides(placed)
    order = [ORDER[stop_of(s.pid)] for s in placed]
    turns = [i for i in range(1, len(placed)) if HEAD not in (sides[i - 1], sides[i]) and sides[i] != sides[i - 1]]
    if len(turns) > 1:
        return "it crosses the Grey and back in one leg"
    if not turns or not _BY_WATER.search(travel or ""):
        if _monotone(order):
            return None
        back = next(i for i in range(2, len(order) + 1) if not _monotone(order[:i])) - 1
        return f"it goes back the way she came at {placed[back].label}"
    i = turns[0]
    near, far = placed[:i], placed[i:]
    land_near, land_far = LANDING[sides[i - 1]], LANDING[sides[i]]
    to_boat = [ORDER[stop_of(s.pid)] for s in near] + [ORDER[land_near]]
    from_boat = [ORDER[land_far]] + [ORDER[stop_of(s.pid)] for s in far]
    if not _monotone(to_boat):
        return (f"she takes the ferry after {near[-1].label}, but the ferry goes from "
                f"{'the Quay Steps' if land_near == 'harbour' else BY_ID[land_near].name}: the stops before the "
                f"crossing must lead to the landing, not on past it")
    if not _monotone(from_boat):
        return f"after the crossing it goes back on itself at {far[-1].label}"
    return None


def check_legs(legs: list[tuple[str, str, list[Placed]]]) -> list[str]:
    """Every leg's trouble, as "leg N (title): why". A leg also starts on the side of the water where the
    last one ended, unless it crosses first (its travel says ferry, boat or crossing)."""
    errors, last_side = [], None
    for n, (title, travel, stops) in enumerate(legs, 1):
        if why := check_leg(stops, travel):
            errors.append(f"leg {n} ({title}): {why}")
        placed = [s for s in stops if s.pid]
        if placed:
            first = BY_ID[placed[0].pid].side
            if last_side and HEAD not in (first, last_side) and first != last_side and not _BY_WATER.search(travel):
                errors.append(f"leg {n} ({title}): it starts on {SIDE_NAMES[first]} of the Grey, but the last leg "
                              f"ended on {SIDE_NAMES[last_side]}, and it doesn't cross by the ferry first")
            last_side = BY_ID[placed[-1].pid].side
    return errors


# ------------------------------------------------------------------ for the writers

def coast_text() -> str:
    """THE COAST for the Coast Road's planner: the shore in order, each stop's id, side and what's there."""
    lines = []
    for c in COAST:
        p = BY_ID[c]
        nearby = [q.name for q in PLACES if q.at == c and q.id != c]
        lines.append(f"  {p.id}: {p.name} ({SIDE_NAMES[p.side]}): {p.note}"
                     + (f". Nearby: {', '.join(nearby)}" if nearby else ""))
    return ("THE COAST, in order, west to east the long way round by the head of the Grey (the ids for `where`):\n"
            + "\n".join(lines)
            + f"\n  The foot ferry crosses between the Quay Steps (harbour) and the Saltby slip in {FERRY_MIN} minutes, "
              "half-hourly. By road the other side is round by Polgrey Bridge, five miles each way. The coast bus "
              "runs hourly: Greymouth, Saltby, Polgrey, Port Wexley, Kessick Bay, Carrow Point, Pellow Harbour.")


LIE_OF_THE_LAND = (
    "LIE OF THE LAND: Port Wexley is on the east shore of the Grey estuary. Saltby is straight across, eight "
    "minutes by the foot ferry from the Quay Steps to the Saltby slip, or five miles each way by road round "
    "Polgrey Bridge at the head of the estuary. Upstream of the town: the Salting (the marsh reserve and the "
    "allotments), Wexley Woods. Downstream, along the town's shore: the fish quay, the old cannery and its "
    "slipway, the seafront, the lifeboat station, then the coast road along the cliffs to Wexley Point and "
    "Kessick Bay. The Saltby side: Cliff Road, Saltby sands and the pier, the cliffs to the Greymouth lighthouse "
    "on Greymouth Point, and Greymouth beyond. Behind the town, Harrow Hill and its farms.")


def lie_of_the_land() -> str:
    """A short note for any writer who places things (about 120 words)."""
    return LIE_OF_THE_LAND
