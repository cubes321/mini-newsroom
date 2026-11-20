"""Draw the map of Port Wexley and the Greymouth coast from newsroom/geography.py, for a contact sheet.

    uv run python tools/town_map.py [out.png]

The area on top, the town below it with the key and the coast in order. Pixel art on a small canvas scaled
up square, the names in the station's own face at full size. A white marker is a place the town's stories
already have; a yellow one was chosen with the map. Reads nothing of the town.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pygame  # noqa: E402

from newsroom import geography as g  # noqa: E402

FACE = "bahnschrift,segoeui,dejavusans,arial"           # scenes.TEXT_FACE
SEA, SEA_DEEP, SHIMMER = (58, 104, 150), (44, 84, 128), (96, 146, 190)
LAND, LAND_DARK, HILL = (112, 150, 84), (92, 128, 70), (140, 168, 98)
SAND, CLIFF, MARSH, REED = (214, 196, 140), (128, 104, 80), (122, 138, 92), (164, 160, 100)
WOOD, WOOD_DARK = (60, 100, 56), (44, 80, 44)
ROAD, PATH, BUS, FERRY = (226, 214, 176), (196, 176, 130), (238, 200, 64), (250, 250, 250)
ROOF, ROOF2, WALL = (172, 84, 64), (150, 150, 156), (210, 200, 182)
INK, PAPER, CANON, CHOSEN = (20, 22, 34), (236, 230, 214), (250, 250, 250), (255, 214, 64)

SHORE, RIVER = g.SHORE, g.RIVER                         # the approved shore (geography.py)
CLIFFS = [[(-4.25, -3.15), (-3.7, -2.5), (-2.95, -1.95), (-2.25, -1.35)],
          [(-0.15, -2.3), (-0.45, -2.85), (-0.75, -3.45), (-0.95, -3.9), (-0.45, -4.15)],
          [(5.0, -4.5), (5.9, -4.9), (6.4, -4.7)]]
BEACHES = [[(-1.85, -0.9), (-1.6, -0.35)], [(0.28, -1.0), (0.22, -1.35)], [(2.2, -4.15), (2.6, -4.3), (3.0, -4.2)]]

# The town's streets (the inset): the ones the stories have, laid out with the map.
STREETS = {
    "Harbour Row": [(0.07, 0.25), (0.1, 0.0), (0.2, -0.3)],
    "Harrow Street": [(0.1, 0.05), (0.45, 0.12), (0.8, 0.45)],
    "Main Street": [(0.5, 0.6), (0.8, 0.45), (1.05, 0.3), (1.2, 0.2)],
    "Quay Lane": [(0.12, 0.15), (0.25, 0.45)],
    "Gull Lane": [(0.25, 0.45), (0.45, 0.5)],
    "Tallow Lane": [(0.35, -0.5), (0.6, -0.55)],
    "Cannery Lane": [(0.27, -0.6), (0.5, -0.3), (0.45, 0.12)],
    "Greenhill Road": [(1.2, 0.2), (1.35, 0.05), (1.7, -0.1), (2.2, -0.25)],
    "Mill Lane": [(1.0, 0.65), (1.3, 0.9)],
    "Tidewater Road": [(0.8, 0.45), (1.0, 0.65), (1.3, 0.9), (1.6, 1.35)],
    "the Polgrey road": [(0.5, 0.6), (0.75, 1.0), (0.95, 1.15), (1.35, 1.6), (1.8, 1.95)],
    "the Kessick road": [(1.2, 0.2), (1.6, -0.8), (2.2, -2.0)],
    "Lantern Row": [(0.45, -0.85), (0.75, -0.95)],
    "the promenade": [(0.32, -0.95), (0.32, -1.3), (0.24, -1.75)],
    "the coast road": [(0.24, -1.75), (0.05, -2.15)],
    "Cliff Road": [(-1.6, -0.2), (-1.45, 0.05), (-1.25, 0.4)],
    "Saltby Road": [(-1.15, 0.75), (-0.75, 1.3), (-0.3, 1.9)],
}
STREET_LABELS = {"Harbour Row": ((0.2, -0.13), "left"), "Tallow Lane": ((0.4, -0.68), "left"),
                 "Cannery Lane": ((0.54, -0.25), "left"), "Mill Lane": ((1.15, 0.72), "left"),
                 "the Polgrey road": ((1.62, 1.68), "right"), "the Kessick road": ((1.95, -1.4), "left"),
                 "the promenade": ((0.38, -1.15), "left"), "Saltby Road": ((-0.7, 1.4), "left"),
                 "Gull Lane": ((0.42, 0.56), "left")}
# Roads that bend round the water or over the hill, drawn through these (miles) rather than straight.
BENDS = {
    ("greymouth", "greymouth_point"): [(-8.5, -2.8), (-6.2, -3.15)],
    ("greymouth", "saltby"): [(-7.5, -1.6), (-4.5, -0.3), (-2.4, 0.5)],
    ("saltby", "polgrey"): [(-0.6, 1.8), (0.6, 3.1), (1.8, 4.3)],
    ("polgrey", "main_street"): [(2.6, 3.3), (2.1, 2.2), (1.35, 1.6), (0.75, 1.0)],
    ("polgrey", "wexley_woods"): [(2.5, 3.6)],
    ("wexley_woods", "the_salting"): [(1.4, 1.9)],
    ("main_street", "kessick_bay"): [(1.6, -0.8), (2.2, -2.0), (2.6, -3.4)],
    ("wexley_point", "kessick_bay"): [(-0.2, -3.95), (1.4, -3.8)],
    ("east_cliffs", "wexley_point"): [(-0.6, -3.2)],
    ("lifeboat_station", "east_cliffs"): [(0.05, -2.15)],
    ("greymouth_point", "west_cliffs"): [(-3.6, -2.35)],
    ("the_salting", "harbour"): [(0.5, 0.6)],
    ("seafront", "harrow_hill"): [(1.0, -0.9)],
    ("cannery", "quarry_field"): [(0.6, -0.4), (1.2, -0.45)],
}

AREA = (-12.2, 10.6, -6.0, 6.2)        # x0, x1, y0, y1 in miles
AREA_PX, AREA_K = 32, 2                # pixels a mile on the small canvas; scaled up this many times
INSET = (-1.8, 2.75, -2.2, 1.95)
INSET_PX, INSET_K = 88, 2


def _font(px: int, bold: bool = False) -> pygame.font.Font:
    return pygame.font.SysFont(FACE, px, bold=bold)


class Frame:
    """A map at one scale: miles to pixels on the small canvas."""

    def __init__(self, box, px_mile: int):
        self.x0, self.x1, self.y0, self.y1 = box
        self.k = px_mile
        self.w, self.h = int((self.x1 - self.x0) * px_mile), int((self.y1 - self.y0) * px_mile)
        self.s = pygame.Surface((self.w, self.h))

    def at(self, xy) -> tuple[int, int]:
        return round((xy[0] - self.x0) * self.k), round((self.y1 - xy[1]) * self.k)


def _land_and_water(f: Frame) -> None:
    f.s.fill(LAND)
    for y in range(0, f.h, 3):                                     # a little texture on the land
        for x in range((y * 7) % 5, f.w, 5):
            if (x * 13 + y * 7) % 11 == 0:
                f.s.set_at((x, y), LAND_DARK)
    water = [f.at(p) for p in SHORE] + [f.at((SHORE[-1][0], -40)), f.at((SHORE[0][0], -40))]
    pygame.draw.polygon(f.s, SEA, water)
    deep = pygame.Surface((f.w, f.h), pygame.SRCALPHA)
    pygame.draw.rect(deep, SEA_DEEP + (255,), (0, f.at((0, -5.0))[1], f.w, f.h))
    mask = pygame.Surface((f.w, f.h), pygame.SRCALPHA)
    pygame.draw.polygon(mask, (255, 255, 255, 255), water)
    deep.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    f.s.blit(deep, (0, 0))
    for y in range(2, f.h, 4):                                     # the shimmer on the water
        for x in range((y * 5) % 9, f.w - 2, 9):
            if f.s.get_at((x, y))[:3] in (SEA, SEA_DEEP) and f.s.get_at((x + 2, y))[:3] in (SEA, SEA_DEEP):
                pygame.draw.line(f.s, SHIMMER, (x, y), (x + 1, y))
    pygame.draw.lines(f.s, SEA, False, [f.at(p) for p in RIVER], max(2, f.k // 16))


def _scenery(f: Frame) -> None:
    for line in CLIFFS:
        pygame.draw.lines(f.s, CLIFF, False, [f.at(p) for p in line], 3)
    for line in BEACHES:
        pygame.draw.lines(f.s, SAND, False, [f.at(p) for p in line], 3)
    sx, sy = f.at(g.BY_ID["the_salting"].xy)                       # the marsh: reeds
    r = max(4, int(0.4 * f.k))
    pygame.draw.ellipse(f.s, MARSH, (sx - r - r // 2, sy - r // 2, r * 2, r))
    for i in range(-r, r, 3):
        for j in range(-r // 2, r // 2, 4):
            if (i * 3 + j * 5) % 4 == 0:
                pygame.draw.line(f.s, REED, (sx + i - r // 3, sy + j), (sx + i - r // 3, sy + j - 2))
    wx, wy = f.at(g.BY_ID["wexley_woods"].xy)                      # the woods: round trees
    k = max(1, f.k // 22)
    for i, (dx, dy) in enumerate(((0, 0), (-5, 3), (5, 2), (-2, -4), (4, -4), (-7, -2), (8, -1), (1, 5),
                                  (-9, 4), (10, 4))):
        pygame.draw.circle(f.s, WOOD if i % 2 else WOOD_DARK, (wx + dx * k, wy + dy * k), 3 * k)
    hx, hy = f.at(g.BY_ID["harrow_hill"].xy)                       # the hill: contours
    for rr in (int(0.9 * f.k), int(0.6 * f.k), int(0.3 * f.k)):
        pygame.draw.ellipse(f.s, HILL, (hx - rr, hy - rr // 2, rr * 2, rr), 1)


def _links(f: Frame) -> None:
    for a, b, _miles, how in g.LINKS:
        bends = BENDS.get((a, b)) or list(reversed(BENDS.get((b, a), [])))
        pts = [f.at(p) for p in [g.BY_ID[a].xy, *bends, g.BY_ID[b].xy]]
        for pa, pb in zip(pts, pts[1:]):
            if how == "ferry":
                _dashed(f.s, FERRY, pa, pb, 3, 2)
            elif how == "path":
                _dashed(f.s, PATH, pa, pb, 3, 2, 2)
            else:
                on_bus = a in g.BUS_ROUTE and b in g.BUS_ROUTE
                pygame.draw.line(f.s, BUS if on_bus else ROAD, pa, pb, 3 if on_bus else 2)


def _dashed(s, colour, a, b, on: int, off: int, width: int = 1) -> None:
    (x1, y1), (x2, y2) = a, b
    n = max(1, int(max(abs(x2 - x1), abs(y2 - y1))))
    for i in range(0, n, on + off):
        t1, t2 = i / n, min(1.0, (i + on) / n)
        pygame.draw.line(s, colour, (x1 + (x2 - x1) * t1, y1 + (y2 - y1) * t1),
                         (x1 + (x2 - x1) * t2, y1 + (y2 - y1) * t2), width)


def _houses(f: Frame, xy, n: int, spread: float, seed: int) -> None:
    cx, cy = f.at(xy)
    k = max(1, f.k // 24)
    for i in range(n):
        dx = ((i * 37 + seed * 11) % 21 - 10) / 10 * spread * f.k
        dy = ((i * 53 + seed * 7) % 17 - 8) / 8 * spread * f.k * 0.6
        x, y = int(cx + dx), int(cy + dy)
        if f.s.get_at((max(0, min(f.w - 1, x)), max(0, min(f.h - 1, y))))[:3] in (SEA, SEA_DEEP, SHIMMER):
            continue
        pygame.draw.rect(f.s, WALL, (x, y + k, 3 * k, 2 * k))
        pygame.draw.rect(f.s, ROOF if i % 3 else ROOF2, (x, y, 3 * k, k + 1))


def _marker(f: Frame, p: g.Place) -> tuple[int, int]:
    x, y = f.at(p.xy)
    pygame.draw.rect(f.s, INK, (x - 2, y - 2, 5, 5))
    pygame.draw.rect(f.s, CANON if p.canon else CHOSEN, (x - 1, y - 1, 3, 3))
    return x, y


def _label(big: pygame.Surface, s: str, xy, px: int, colour=PAPER, anchor="left", bold=False) -> None:
    font = _font(px, bold)
    img, ink = font.render(s, True, colour), font.render(s, True, INK)
    x, y = xy
    if anchor == "right":
        x -= img.get_width()
    elif anchor == "center":
        x -= img.get_width() // 2
    y -= img.get_height() // 2
    for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1), (-1, -1), (1, 1), (1, -1), (-1, 1)):
        big.blit(ink, (x + dx, y + dy))
    big.blit(img, (x, y))


# Where each label goes from its marker, so the names don't sit on each other.
AREA_LABELS = {"greymouth": "below", "greymouth_point": "below", "west_cliffs": "left", "saltby_sands": "left",
               "cliff_road": "left", "saltby": "above", "saltby_slip": "right", "polgrey": "right",
               "wexley_woods": "right", "the_salting": "left", "harbour": "right", "fish_quay": "right",
               "cannery": "right", "seafront": "right", "lifeboat_station": "right", "east_cliffs": "left",
               "wexley_point": "below", "kessick_bay": "below", "carrow_point": "below", "pellow_harbour": "below",
               "harrow_hill": "right"}
INSET_LABELS = {"harbour": "left", "fish_quay": "left", "cannery": "left", "seafront": "left",
                "lifeboat_station": "left", "the_salting": "left", "saltby_slip": "left", "saltby": "above",
                "cliff_road": "below", "harrow_street": "right", "main_street": "above", "town_hall": "right",
                "harbour_church": "left", "park": "above", "lantern_row": "right", "greenhill_road": "below",
                "station": "right", "school": "right", "stadium": "right", "quarry_field": "below",
                "industrial_estate": "right", "fire_station": "right", "police_station": "above",
                "harrow_hill": "below", "east_cliffs": "left"}


def _place_label(big, p: g.Place, at, where: str, k: int, px: int, number: str = "") -> None:
    x, y = at[0] * k, at[1] * k
    gap = 6 + k
    name = (f"{number} " if number else "") + p.name
    if where == "left":
        _label(big, name, (x - gap, y), px, anchor="right")
    elif where == "above":
        _label(big, name, (x, y - gap - px // 3), px, anchor="center")
    elif where == "below":
        _label(big, name, (x, y + gap + px // 3), px, anchor="center")
    else:
        _label(big, name, (x + gap, y), px)


def _big(f: Frame, k: int, xy) -> tuple[int, int]:
    x, y = f.at(xy)
    return x * k, y * k


def draw_area() -> pygame.Surface:
    f = Frame(AREA, AREA_PX)
    _land_and_water(f)
    _scenery(f)
    _links(f)
    _houses(f, (0.6, 0.3), 30, 0.45, 1)                            # Port Wexley
    _houses(f, g.BY_ID["saltby"].xy, 9, 0.25, 2)
    for pid in ("polgrey", "kessick_bay", "carrow_point", "pellow_harbour", "greymouth"):
        _houses(f, g.BY_ID[pid].xy, 16 if pid == "greymouth" else 6, 0.4 if pid == "greymouth" else 0.2, len(pid))
    marks = {pid: _marker(f, g.BY_ID[pid]) for pid in AREA_LABELS}
    big = pygame.transform.scale(f.s, (f.w * AREA_K, f.h * AREA_K))
    for pid, where in AREA_LABELS.items():
        number = str(g.ORDER[pid] + 1) if pid in g.ORDER else ""
        _place_label(big, g.BY_ID[pid], marks[pid], where, AREA_K, 15, number)
    x, y = _big(f, AREA_K, (1.3, 1.0))
    _label(big, "PORT WEXLEY", (x, y), 24, bold=True)
    x, y = _big(f, AREA_K, (-1.6, 1.5))
    _label(big, "SALTBY", (x, y), 20, anchor="right", bold=True)
    for words, xy, px in (("the Grey", (0.9, 3.4), 16), ("the bay", (-2.2, -2.9), 20), ("the sea", (-1.0, -5.3), 22),
                          ("the Grey", (3.7, 6.0), 14)):
        x, y = _big(f, AREA_K, xy)
        _label(big, words, (x, y), px, SHIMMER, anchor="center")
    x, y = _big(f, AREA_K, (3.9, 5.6))
    _label(big, "to Lowmoor and the moor", (x + 16, y), 13, PATH)
    x, y = _big(f, AREA_K, (-11.0, -2.6))
    _label(big, "the coast bus from Greymouth", (x + 10, y - 50), 13, BUS)
    _compass_and_scale(big, f)
    return big


def _compass_and_scale(big: pygame.Surface, f: Frame) -> None:
    x, y = big.get_width() - 60, 56
    pygame.draw.polygon(big, PAPER, [(x, y - 30), (x - 9, y), (x + 9, y)])
    pygame.draw.polygon(big, INK, [(x, y - 30), (x - 9, y), (x + 9, y)], 2)
    _label(big, "N", (x, y + 14), 16, anchor="center", bold=True)
    x0, y0 = 30, big.get_height() - 30
    mile = f.k * AREA_K
    for i in range(5):
        pygame.draw.rect(big, PAPER if i % 2 == 0 else INK, (x0 + i * mile, y0, mile, 6))
    pygame.draw.rect(big, INK, (x0, y0, 5 * mile, 6), 1)
    _label(big, "0", (x0, y0 - 12), 12, anchor="center")
    _label(big, "5 miles", (x0 + 5 * mile, y0 - 12), 12, anchor="center")


def draw_inset() -> pygame.Surface:
    f = Frame(INSET, INSET_PX)
    _land_and_water(f)
    _scenery(f)
    for line in STREETS.values():
        pygame.draw.lines(f.s, ROAD, False, [f.at(p) for p in line], 3)
    _dashed(f.s, FERRY, f.at(g.BY_ID["harbour"].xy), f.at(g.BY_ID["saltby_slip"].xy), 4, 3, 2)
    for p in g.PLACES:
        if p.town or p.id in INSET_LABELS:
            x, y = f.at(p.xy)
            if 0 <= x < f.w and 0 <= y < f.h and p.id not in ("harrow_hill", "the_salting", "east_cliffs"):
                pygame.draw.rect(f.s, WALL, (x - 4, y - 1, 9, 5))
                pygame.draw.rect(f.s, ROOF if p.canon else ROOF2, (x - 5, y - 4, 11, 3))
    marks = {pid: _marker(f, g.BY_ID[pid]) for pid in INSET_LABELS}
    big = pygame.transform.scale(f.s, (f.w * INSET_K, f.h * INSET_K))
    for name, (xy, anchor) in STREET_LABELS.items():               # the streets' names, small
        x, y = _big(f, INSET_K, xy)
        _label(big, name, (x, y), 11, ROAD, anchor=anchor)
    for pid, where in INSET_LABELS.items():
        _place_label(big, g.BY_ID[pid], marks[pid], where, INSET_K, 13)
    _label(big, "THE TOWN", (14, 22), 18, bold=True)
    x, y = _big(f, INSET_K, (-0.75, -1.1))
    _label(big, "the Grey", (x, y), 18, SHIMMER, anchor="center")
    x, y = _big(f, INSET_K, (-0.45, 0.2))
    _label(big, "ferry, 8 min", (x, y), 12, FERRY, anchor="center")
    x, y = _big(f, INSET_K, (-1.2, 1.35))
    _label(big, "SALTBY", (x, y), 18, anchor="center", bold=True)
    pygame.draw.rect(big, INK, big.get_rect(), 3)
    return big


def draw_sheet() -> pygame.Surface:
    pygame.font.init()
    area, inset = draw_area(), draw_inset()
    pad, top = 16, 46
    w = max(area.get_width(), inset.get_width() + 580) + pad * 2
    h = top + area.get_height() + pad + inset.get_height() + pad
    sheet = pygame.Surface((w, h))
    sheet.fill((26, 28, 40))
    _label(sheet, "Port Wexley and the Greymouth coast: the gazetteer (newsroom/geography.py), drawn",
           (pad, 24), 20, bold=True)
    sheet.blit(area, (pad, top))
    pygame.draw.rect(sheet, INK, (pad, top, area.get_width(), area.get_height()), 3)
    iy = top + area.get_height() + pad
    sheet.blit(inset, (pad, iy))
    x, y = pad * 3 + inset.get_width(), iy + 14
    for colour, words, kind in ((CANON, "already in the town's stories", "mark"),
                                (CHOSEN, "chosen with this map", "mark"),
                                (BUS, "the coast bus, hourly", "line"), (ROAD, "road", "line"),
                                (PATH, "path (on foot, by bike)", "dash"), (FERRY, "the Saltby foot ferry", "dash")):
        if kind == "mark":
            pygame.draw.rect(sheet, INK, (x, y - 6, 13, 13))
            pygame.draw.rect(sheet, colour, (x + 3, y - 3, 7, 7))
        elif kind == "line":
            pygame.draw.line(sheet, colour, (x, y), (x + 22, y), 4)
        else:
            _dashed(sheet, colour, (x, y), (x + 22, y), 5, 3, 3)
        _label(sheet, words, (x + 32, y), 15)
        y += 26
    y += 18
    _label(sheet, "THE COAST IN ORDER", (x, y), 17, CHOSEN, bold=True)
    _label(sheet, "west to east, the long way round by Polgrey Bridge", (x, y + 22), 13)
    y += 50
    for i, c in enumerate(g.COAST, 1):
        p = g.BY_ID[c]
        col = x + (0 if i <= 10 else 280)
        _label(sheet, f"{i:>2}. {p.name}", (col, y + ((i - 1) % 10) * 22), 14, CANON if p.canon else CHOSEN)
    y += 10 * 22 + 20
    for line in ("The foot ferry: the Quay Steps to the Saltby slip, 8 minutes, half-hourly.",
                 "By road, Saltby is round by Polgrey Bridge: 5 miles each way.",
                 "On foot 3 mph, a bike 10, the coast bus about 24 between stops."):
        _label(sheet, line, (x, y), 13)
        y += 20
    return sheet


def main(argv: list[str]) -> None:
    out = Path(argv[1]) if len(argv) > 1 else Path("data/contact-sheets/2026-11-20-town-map.png")
    out.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(draw_sheet(), str(out))
    print(out)


if __name__ == "__main__":
    main(sys.argv)
