"""The places a picture can be set: Port Wexley, its countryside, the studio.

Pure data, no pygame, so models.py can build the `Backdrop` literal from it
and the prompts can describe each id to the model. backdrops.py owns the
pixels (PNG art, or a programmatic placeholder when there is none).

kind:
- "town" / "country": exteriors writers can pick; graded for time of day
  and the last weather report.
- "studio": interiors the scenes use directly; never offered to writers,
  never graded.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

Kind = Literal["town", "country", "studio"]
TimeOfDay = Literal["day", "dusk", "night"]
RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Location:
    id: str
    name: str
    blurb: str              # one line for the model: what you would see there
    kind: Kind
    sky: RGB                # daytime colours; placeholders and grading start from these
    ground: RGB
    water: bool = False     # animated shimmer along the bottom
    interior: bool = False  # no sky, no weather (council chamber, market shed)

    @property
    def exterior(self) -> bool:
        return self.kind != "studio" and not self.interior


# Order matters only for the prompt and the contact sheet. The first eight
# ids predate this module and keep their meaning: cached segments and special
# partials in data/cache store them as plain strings.
LOCATIONS: tuple[Location, ...] = (
    # ---- town
    Location("harbour", "Port Wexley harbour", "the harbour front: fishing boats, the harbour wall, gulls",
             "town", (110, 160, 205), (70, 75, 80), water=True),
    Location("main_street", "the high street", "the high street: shopfronts, the bus stop, the post office",
             "town", (150, 185, 220), (95, 90, 85)),
    Location("town_hall", "Wexley Town Hall", "outside Wexley Town Hall: the clock tower and the steps",
             "town", (140, 180, 225), (120, 115, 105)),
    Location("park", "Wexley Park", "Wexley Park: lawns, the bandstand, the duck pond",
             "town", (130, 185, 235), (90, 150, 70)),
    Location("factory", "the industrial estate", "the industrial estate on the edge of town: units, a chimney, a yard",
             "town", (160, 170, 180), (90, 85, 80)),
    Location("farm", "a farm outside town", "farmland outside town: fields, a barn, a tractor track",
             "country", (140, 190, 235), (150, 140, 80)),
    Location("stadium", "Tidewater Stadium", "Tidewater Stadium, home of the town's football club: stand, floodlights, pitch",
             "town", (135, 180, 230), (70, 140, 70)),
    Location("school", "Greymouth Academy", "Greymouth Academy, the secondary school: the main block, gates, playground",
             "town", (145, 185, 230), (110, 105, 100)),
    Location("council_chamber", "the council chamber", "inside the council chamber: the horseshoe of desks, the mayor's chair",
             "town", (120, 85, 60), (90, 60, 45), interior=True),
    Location("market", "Harrow Street market", "Harrow Street market: striped stalls along the street",
             "town", (150, 190, 230), (120, 110, 100)),
    Location("market_shed", "the winter market shed", "inside the market's winter shed: stalls under a long timber roof",
             "town", (95, 80, 65), (110, 95, 75), interior=True),
    Location("cannery", "the old cannery", "the old cannery on the harbour: brick sheds, a rusting sign, broken windows",
             "town", (125, 155, 185), (80, 75, 70), water=True),
    Location("slipway", "the cannery slipway", "the slipway by the cannery: a stone ramp into the water, small boats",
             "town", (125, 170, 210), (100, 95, 85), water=True),
    Location("loading_dock", "the loading dock", "the harbour loading dock: a crane, containers, pallets",
             "town", (130, 165, 200), (85, 85, 90), water=True),
    Location("lighthouse", "the Greymouth lighthouse", "the Greymouth lighthouse on the point: rocks, the tower",
             "town", (120, 170, 220), (95, 100, 90), water=True),
    Location("lifeboat_station", "the lifeboat station", "the lifeboat station: the boathouse, the launch ramp",
             "town", (125, 170, 215), (95, 95, 95), water=True),
    Location("seafront", "the seafront", "the seafront promenade: railings, benches, the beach and the sea",
             "town", (135, 185, 235), (170, 165, 155), water=True),
    Location("fire_station", "Port Wexley fire station", "the fire station: red engine-bay doors, the drill tower",
             "town", (145, 185, 225), (105, 100, 95)),
    Location("police_station", "Port Wexley police station", "the police station: the blue lamp, the front desk entrance",
             "town", (145, 180, 220), (100, 100, 105)),
    Location("residential_street", "a residential street", "a residential street: terraced houses, parked cars, front gardens",
             "town", (150, 190, 230), (100, 95, 90)),
    Location("quarry_field", "the Quarry Field", "the Quarry Field, home of Port Wexley RFC: rugby posts, the tin-roofed stand, quarry rock faces",
             "town", (140, 180, 225), (85, 140, 70)),
    Location("pub", "a darts pub", "inside a pub on darts night: the dartboard and the oche, the chalk scoreboard, the bar",
             "town", (110, 70, 45), (80, 55, 40), interior=True),
    # ---- country
    Location("coast_road", "the coast road", "the coast road along the cliffs: a stone wall, the sea far below",
             "country", (130, 180, 230), (110, 140, 80), water=True),
    Location("woods", "Wexley Woods", "Wexley Woods: a footpath under tall trees",
             "country", (150, 190, 220), (70, 100, 55)),
    Location("estuary", "the Grey estuary", "the estuary: mudflats, reeds, wading birds",
             "country", (155, 185, 215), (120, 115, 85), water=True),
    Location("village", "Saltby village", "Saltby, the neighbouring village: a green, the church spire, a pub",
             "country", (140, 185, 230), (95, 140, 75)),
    # ---- studio (scenes only)
    Location("studio_wide", "the studio", "the main news desk, wide shot", "studio", (28, 34, 60), (80, 60, 50)),
    Location("weather_wall", "the weather wall", "the weather presenter's wall", "studio", (36, 42, 70), (40, 40, 50)),
    Location("studio_interview", "the interview set", "two armchairs and a low table for a studio guest",
             "studio", (34, 40, 66), (60, 50, 48)),
    Location("studio_sofa", "the breakfast sofa", "the breakfast show's sofa by a window onto the harbour",
             "studio", (225, 210, 185), (150, 120, 95)),
    Location("studio_late", "The Last Ferry set", "the late-night show's desk and guest couch, the harbour at night behind",
             "studio", (22, 26, 48), (52, 40, 36)),
    Location("studio_sports", "the sports corner", "the sports desk: the stadium on the big screen, a results board, the trophy cabinet",
             "studio", (28, 34, 60), (60, 50, 48)),
)

# Where people go on the studio sets: (x, baseline y, sprite scale, facing).
# The art is drawn around these marks, so a scene that uses a set puts its
# characters exactly here. Both sets are built ahead of the shows that will
# use them (studio interviews, the breakfast and magazine shows).
Mark = tuple[int, int, int, int]
MARKS: dict[str, dict[str, Mark]] = {
    "studio_interview": {"host": (92, 150, 2, 1), "guest": (228, 150, 2, -1)},
    "studio_sofa": {"host_a": (122, 146, 2, 1), "host_b": (186, 146, 2, -1), "guest": (272, 150, 2, -1)},
    "studio_late": {"host": (92, 136, 2, 1), "guest": (228, 150, 2, -1),    # host just behind the desk top
                    # two on the couch: the new guest nearest the desk, the earlier one moved down
                    "guest_near": (204, 150, 2, -1), "guest_far": (268, 150, 2, -1)},
    "studio_sports": {"host": (92, 144, 2, 1), "guest": (228, 150, 2, -1)},   # host stands at the desk
}

BY_ID: dict[str, Location] = {loc.id: loc for loc in LOCATIONS}
BACKDROP_IDS: tuple[str, ...] = tuple(loc.id for loc in LOCATIONS if loc.kind != "studio")
DEFAULT_BACKDROP = "main_street"


def get(backdrop_id: str | None) -> Location:
    """Unknown or missing ids fall back to the high street, as they always have."""
    return BY_ID.get(backdrop_id or "", BY_ID[DEFAULT_BACKDROP])


def locations_for_prompt() -> str:
    return "\n".join(f"  - {loc.id}: {loc.blurb}" for loc in LOCATIONS if loc.kind != "studio")


def time_of_day(hour: int) -> TimeOfDay:
    if 7 <= hour < 17:
        return "day"
    if 17 <= hour < 20 or hour == 6:
        return "dusk"
    return "night"
