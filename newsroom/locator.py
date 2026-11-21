"""The news locator: a small inset of the town's map marking where a Channel 7 news item is.

The way real local news does it, from the map the user approved (newsroom/geography.py, drawn by
tools/town_map.py). It goes up on the big-picture wall while the anchor hands over, and in the corner of
Miles's report or vox pop for its first few seconds out on location; then it goes.

Where: the place the report says it is first (the script's own `location`, the first place it names), then
the item's other words (its headline, the running order's brief, its thread's title and status), then the
backdrop it is filmed on when that shows one place. Over the 118 reports of 2026-11-20 and 21 the location
placed 117 and the headline 79, and where they differed the headline was wrong every time: it named the
story's subject ("Wreckers Hold Their Shape Ahead of Saltby Trip", filmed at the Quarry Field). A name the map doesn't know, names on both
sides of the Grey, or words and backdrop on opposite sides: nothing goes up. It never guesses.

Channel 7's news only: Miles ("reporter"), never Meg's Out and About or anything on Channel 8.
"""
from __future__ import annotations

from . import channel, geography as g, townplan
from .models import Segment, SegmentType

SHOW_S = 6.0                        # on location, up for this long from the first line out there
KINDS = (SegmentType.field_report, SegmentType.feature, SegmentType.vox_pop)
REPORTER = "reporter"               # Miles
NOT_SHOWS = ("outabout",)           # Meg's reviews and days out have their own places, and no locator

# On the canvas (320x180). Clear of the clock (276,4,40,12), the lower third (y 128-154), the ticker (y 166-180)
# and the reporter on a field shot (x 64-116): top right under the clock. On the wall, in the big screen's
# corner (scenes.WALL_SCREEN is 40,20,180,120), clear of the anchor at the side panel.
FIELD_RECT = (240, 20, 72, 52)
WALL_RECT = (44, 24, 72, 52)
CAPTION_H = 11                      # the place's name under the map

TOWN_MILES, AREA_MILES = 2.4, 10.0  # how wide the map is round a place in the town, and round anywhere else
STREET_MILES = 1.0                  # and round a place in the streets by the harbour: Harbour Row is not the fish quay
CENTRE, CENTRE_REACH = (0.35, -0.05), 0.85      # the middle of the old town, and how far its streets go

LAND, SEA, RIVER_C = (112, 150, 84), (58, 104, 150), (58, 104, 150)
TOWN, FRAME, CAPTION = (196, 186, 170), (20, 22, 34), (20, 22, 34)
MARK, MARK_RING = (230, 40, 40), (250, 250, 250)


def place_of(seg: Segment, thread_text: str = "", backdrop: str | None = None) -> str | None:
    """The gazetteer id of where this news item is, or None when its words and backdrop don't say for sure."""
    words = " ".join(x for x in (seg.headline or "", seg.brief or "", thread_text) if x)
    said = g.place_at(seg.work.get("said_at") or "") or (g.place_for(words) if words else None)
    shown = g.BACKDROP_PLACE.get(backdrop or "")
    if said and shown and {g.side(said), g.side(shown)} == {g.EAST, g.WEST}:
        return None                                   # filmed on one side, about the other: say nothing
    return said or shown


def wanted(seg: Segment, reporter: str) -> bool:
    """Is this an item the locator is for: Channel 7's news on location, with Miles."""
    return (channel.CURRENT.number == "7" and seg.type in KINDS and seg.show not in NOT_SHOWS
            and reporter == REPORTER and not seg.repeat)


def box(pid: str, aspect: float) -> tuple[float, float, float, float]:
    """The map's window round a place, in miles (x0, x1, y0, y1): the town close up, anywhere else wider."""
    p = g.BY_ID[pid]
    streets = p.side == g.EAST and ((p.xy[0] - CENTRE[0]) ** 2 + (p.xy[1] - CENTRE[1]) ** 2) ** 0.5 < CENTRE_REACH
    w = STREET_MILES if streets else TOWN_MILES if g.miles_between(pid, "harbour") < 1.8 else AREA_MILES
    h = w * aspect
    return p.xy[0] - w / 2, p.xy[0] + w / 2, p.xy[1] - h / 2, p.xy[1] + h / 2


def picture(pid: str, size: tuple[int, int], k: int, lit: bool):
    """The locator, `size` canvas pixels drawn at `k` window pixels a canvas pixel: the map (land, water, the town,
    the spot) over a dark strip for the place's name, which scenes.py writes on it."""
    import pygame

    full = pygame.Surface((size[0] * k, size[1] * k))
    full.fill(CAPTION)
    w, h = size[0] * k, (size[1] - CAPTION_H) * k
    x0, x1, y0, y1 = box(pid, (size[1] - CAPTION_H) / size[0])
    sx = w / (x1 - x0)

    def at(xy):
        return round((xy[0] - x0) * sx), round((y1 - xy[1]) * sx)

    s = pygame.Surface((w, h))
    s.fill(LAND)
    pygame.draw.polygon(s, SEA, [at(p) for p in g.SHORE] + [at((g.SHORE[-1][0], -40)), at((g.SHORE[0][0], -40))])
    pygame.draw.lines(s, RIVER_C, False, [at(p) for p in g.RIVER], max(2, k))
    if x1 - x0 <= TOWN_MILES:             # close enough for the streets and their roofs (townplan.py)
        townplan.draw(s, at, sx, (SEA,))
    else:
        for town, r in (((0.6, 0.3), 0.45), (g.BY_ID["saltby"].xy, 0.22)):   # the town and the village, as grey
            cx, cy = at(town)
            rr = max(k, round(r * sx))
            pygame.draw.ellipse(s, TOWN, (cx - rr, cy - rr * 2 // 3, rr * 2, rr * 4 // 3))
    x, y = at(g.BY_ID[pid].xy)
    if lit:
        pygame.draw.circle(s, MARK_RING, (x, y), 6 * k, max(1, k))
    pygame.draw.circle(s, MARK_RING, (x, y), 3 * k)
    pygame.draw.circle(s, MARK, (x, y), 2 * k)
    full.blit(s, (0, 0))
    pygame.draw.rect(full, FRAME, full.get_rect(), max(1, k))
    return full


def caption(pid: str) -> str:
    name = g.BY_ID[pid].name
    return name[:1].upper() + name[1:]
