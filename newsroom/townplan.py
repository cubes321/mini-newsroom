"""The town in streets and blocks: Port Wexley close up, for the map's sheet and the locator in town.

The streets are the gazetteer's: the named ones (geography.STREETS) and the side streets that join them up
(BACK_STREETS), each with the buildings along it: small roofs either side, none on water or on a green. The harbour wall, the quay's edge, the greens (the park, the bowling green,
the two grounds) and the Salting are drawn too. Everything is placed by `at`, the caller's own window on the map,
so one drawing serves any scale: a street is a pixel wide on the locator and a proper road on the sheet.
"""
from __future__ import annotations

from . import geography as g

ROAD, ROAD_EDGE, LANE = (226, 214, 176), (150, 140, 112), (206, 194, 160)
ROOFS = ((172, 84, 64), (150, 96, 70), (126, 132, 142), (160, 120, 84), (188, 104, 72), (112, 118, 128))
WALLS = (210, 200, 182)
GREEN, PITCH, MARSH, STONE, QUAY = (96, 150, 78), (86, 160, 82), (122, 138, 92), (150, 150, 156), (170, 166, 150)

# How far a house stands from the middle of its street, and its size, in miles (a terrace's house is ~25 feet).
SETBACK, HOUSE, STEP = 0.022, (0.03, 0.022), 0.036


def _on_land(s, px: tuple[int, int], water: tuple) -> bool:
    """Is there ground to build on here: on the surface, not water, and not a green, a pitch or the marsh."""
    w, h = s.get_size()
    return 0 <= px[0] < w and 0 <= px[1] < h and tuple(s.get_at(px))[:3] not in (*water, GREEN, PITCH, MARSH)


def _blocks(s, at, ppm: float, water: tuple) -> None:
    """The buildings: a roof either side of every built-up street, a step apart, where there is land."""
    import pygame

    bw, bh = max(2, round(HOUSE[0] * ppm)), max(2, round(HOUSE[1] * ppm))
    streets = [(name, g.STREETS[name]) for name in g.BUILT_UP] + [(f"back {i}", line)
                                                                  for i, line in enumerate(g.BACK_STREETS)]
    for name, line in streets:
        n = 0
        for (x0, y0), (x1, y1) in zip(line, line[1:]):
            length = ((x1 - x0) ** 2 + (y1 - y0) ** 2) ** 0.5
            ux, uy = (x1 - x0) / length, (y1 - y0) / length
            d = STEP / 2
            while d < length:
                cx, cy = x0 + ux * d, y0 + uy * d
                for side in ((1, -1, 2.4, -2.4) if name in g.DENSE else (1, -1)):   # a back row in the middle
                    px, py = at((cx - uy * SETBACK * side, cy + ux * SETBACK * side))
                    if _on_land(s, (px, py), water):
                        k = (len(name) * 5 + n * 7 + round(side * 2)) % len(ROOFS)
                        pygame.draw.rect(s, WALLS, (px - bw // 2, py - bh // 2, bw, bh))
                        pygame.draw.rect(s, ROOFS[k], (px - bw // 2, py - bh // 2, bw, max(1, bh - 1)))
                n += 1
                d += STEP


def draw(s, at, ppm: float, water: tuple) -> None:
    """Draw the town on `s`, already filled with land and water. `at((miles east, miles north))` gives a pixel,
    `ppm` is pixels to the mile, `water` the colours that are water on `s`."""
    import pygame

    for kind, xy, (w, h) in g.GREENS:                              # the greens and grounds, under everything
        px, py = at(xy)
        pw, ph = max(2, round(w * ppm)), max(2, round(h * ppm))
        colour = {"park": GREEN, "pitch": PITCH, "marsh": MARSH}[kind]
        if kind == "pitch":
            pygame.draw.rect(s, colour, (px - pw // 2, py - ph // 2, pw, ph))
            if pw > 8:
                pygame.draw.rect(s, (220, 232, 214), (px - pw // 2, py - ph // 2, pw, ph), 1)
        else:
            pygame.draw.ellipse(s, colour, (px - pw // 2, py - ph // 2, pw, ph))
    _blocks(s, at, ppm, water)
    wide = max(1, round(0.012 * ppm))
    for line in g.BACK_STREETS:                                    # the side streets, under the named ones
        pygame.draw.lines(s, LANE, False, [at(p) for p in line], max(1, wide - 1))
    for name, line in g.STREETS.items():
        pts = [at(p) for p in line]
        lane = name.endswith("Lane") or name.endswith("Row")
        if wide >= 3:
            pygame.draw.lines(s, ROAD_EDGE, False, pts, wide + 2)
        pygame.draw.lines(s, LANE if lane else ROAD, False, pts, max(1, wide - (1 if lane and wide > 1 else 0)))
    pygame.draw.lines(s, STONE, False, [at(p) for p in g.HARBOUR_WALL], max(2, round(0.014 * ppm)))
    pygame.draw.lines(s, STONE, False, [at(p) for p in g.QUAY_STEPS], max(2, round(0.016 * ppm)))
    pygame.draw.lines(s, QUAY, False, [at(p) for p in g.QUAYSIDE], max(1, round(0.008 * ppm)))
