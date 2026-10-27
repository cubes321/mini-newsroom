"""Backdrops: the pixels behind every scene.

locations.py says which places exist; this module paints them. For each
backdrop id the picture comes from the first of:

1. assets/backdrops/<id>_<tod>.png   art made for that time of day
2. assets/backdrops/<id>.png         art, graded here for time of day
3. a programmatic placeholder painter below

Exteriors are also graded for the last weather report. Animated touches
(water shimmer, rain, snow, fog, wind, the lighthouse beam) are drawn on top
every frame. Graded pictures are cached per (id, tod, weather), so a scene
pays one blit plus its overlays.

Placeholders are painted onto a transparent layer over a separate sky, so
the sky can have its own dusk and night colours. Windows and lamps they
declare are lit after grading, so they glow instead of being darkened.

    python -m newsroom.backdrops --sheet out.png    contact sheet of everything
    python -m newsroom.backdrops --bake harbour     write a placeholder as a PNG template
"""
from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path

import numpy as np
import pygame

from . import locations
from .config import CONFIG
from .locations import MARKS, Location

W, H = 320, 180
HZ = 120                                   # default ground line
ART_DIR = CONFIG.paths.assets / "backdrops"
CACHE_SIZE = 24
TODS = ("day", "dusk", "night")

GLASS = (60, 75, 95)
LIT = (255, 214, 130)
WATER_C, WATER_HI = (55, 95, 135), (80, 125, 165)

# Where to look for water, for the shimmer overlay. The shimmer only touches the art's own
# water pixels inside these (`_water_mask`), so they can be generous; keep them below the sky,
# which is blue too.
WATER: dict[str, list[tuple[int, int, int, int]]] = {
    "harbour": [(140, 110, 180, 70)],
    "cannery": [(200, 124, 120, 56)],
    "slipway": [(100, 106, 220, 74)],
    "loading_dock": [(0, 100, W, 12)],
    "lighthouse": [(0, 100, 175, 16)],
    "lifeboat_station": [(0, 104, 190, 12), (270, 104, 50, 8)],
    "seafront": [(0, 84, W, 22)],
    "coast_road": [(190, 72, 130, 108)],
    "estuary": [(0, 106, W, 20), (170, 145, 150, 30)],
}
LIGHTHOUSE_LAMP = (251, 21)

# Where the sky meets land or sea in the art, for the dusk grade's sunset band.
DUSK_HZ = 105
HORIZON: dict[str, int] = {"seafront": 80, "estuary": 62, "farm": 86, "lighthouse": 92, "coast_road": 70}
# Dusk on art without its own <id>_dusk.png: (row fraction of the horizon, colour) stops,
# then how hard sky/water and everything else are pulled towards them.
DUSK_RAMP = ((0.0, (96, 72, 150)), (0.55, (220, 110, 150)), (1.0, (255, 150, 70)), (1.6, (190, 120, 95)))
DUSK_WATER = (95, 85, 150)                 # sea and river below the horizon: violet, not the ground's warm brown
DUSK_K_SKY, DUSK_K_REST, DUSK_DARKEN = 0.75, 0.22, 0.86

TOD_MULT = {"day": (1.0, 1.0, 1.0), "dusk": (1.0, 0.82, 0.72), "night": (0.38, 0.42, 0.62)}
TOD_K = {"day": 1.0, "dusk": 0.7, "night": 0.25}
# weather -> (multiply, desaturate 0..1, (mix colour, amount) or None)
WX_GRADE: dict[str, tuple[tuple[float, float, float], float, tuple | None]] = {
    "sunny": ((1.04, 1.0, 0.94), 0.0, None),
    "cloudy": ((0.92, 0.92, 0.95), 0.2, None),
    "rain": ((0.78, 0.80, 0.86), 0.35, None),
    "storm": ((0.60, 0.62, 0.70), 0.5, None),
    "snow": ((1.0, 1.0, 1.0), 0.25, ((235, 240, 250), 0.18)),
    "fog": ((1.0, 1.0, 1.0), 0.3, ((190, 190, 195), 0.45)),
}
SKY_TOD = {"dusk": ((70, 60, 120), (245, 160, 110)), "night": ((8, 10, 28), (28, 34, 70))}
SKY_WX = {"cloudy": ((165, 170, 180), 0.5), "rain": ((105, 110, 122), 0.75), "storm": ((60, 62, 76), 0.85),
          "snow": ((200, 205, 215), 0.6), "fog": ((190, 190, 195), 0.85)}


def _shade(c, k: float) -> tuple[int, int, int]:
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _mix(a, b, k: float) -> tuple[int, int, int]:
    return tuple(int(a[i] + (b[i] - a[i]) * k) for i in range(3))


# ------------------------------------------------------------- paint kit


class _Paint:
    """A transparent layer, plus the windows and lamps that light up after dark."""

    def __init__(self, loc: Location) -> None:
        self.loc = loc
        self.s = pygame.Surface((W, H), pygame.SRCALPHA)
        self.windows: list[pygame.Rect] = []
        self.lamps: list[tuple[int, int, tuple]] = []

    def rect(self, c, x, y, w, h) -> None:
        pygame.draw.rect(self.s, c, (x, y, w, h))

    def poly(self, c, pts) -> None:
        pygame.draw.polygon(self.s, c, pts)

    def circle(self, c, x, y, r) -> None:
        pygame.draw.circle(self.s, c, (x, y), r)

    def ellipse(self, c, x, y, w, h) -> None:
        pygame.draw.ellipse(self.s, c, (x, y, w, h))

    def line(self, c, a, b, width: int = 1) -> None:
        pygame.draw.line(self.s, c, a, b, width)

    def window(self, x, y, w=4, h=5) -> None:
        self.rect(GLASS, x, y, w, h)
        self.windows.append(pygame.Rect(x, y, w, h))

    def window_grid(self, x, y, cols, rows, dx=8, dy=9, w=4, h=5) -> None:
        for r in range(rows):
            for c in range(cols):
                self.window(x + c * dx, y + r * dy, w, h)

    def lamp(self, x, y, color=LIT, ground: int | None = None) -> None:
        """A light that glows after dark; with `ground`, a post down to it."""
        if ground is not None:
            self.rect((40, 40, 46), x, y, 1, ground - y)
        self.rect((70, 70, 76), x - 1, y - 1, 3, 2)
        self.lamps.append((x, y, color))


Painter = Callable[[_Paint], None]
PAINTERS: dict[str, Painter] = {}


def _painter(*ids: str):
    def reg(fn: Painter) -> Painter:
        for i in ids:
            PAINTERS[i] = fn
        return fn
    return reg


def _ground(p: _Paint, y: int = HZ, c=None) -> None:
    p.rect(c or p.loc.ground, 0, y, W, H - y)


def _water(p: _Paint, x, y, w, h) -> None:
    p.rect(WATER_C, x, y, w, h)
    p.rect(WATER_HI, x, y, w, 1)


def _hills(p: _Paint, y: int, c, amp: int = 8, seed: float = 0.0) -> None:
    pts = [(0, H)] + [(x, int(y - amp * (0.5 + 0.5 * math.sin(x * 0.013 + seed)) * (0.7 + 0.3 * math.sin(x * 0.05 + seed))))
                      for x in range(0, W + 8, 8)] + [(W, H)]
    p.poly(c, pts)


def _tree(p: _Paint, x: int, base: int, r: int = 10, c=(60, 110, 55)) -> None:
    p.rect((80, 60, 40), x - 1, base - r - 4, 3, r + 4)
    p.circle(c, x, base - r - 4, r)
    p.circle(_shade(c, 1.15), x - r // 3, base - r - 4 - r // 3, r // 2)


def _house(p: _Paint, x: int, w: int, h: int, wall, roof=(90, 70, 70), base: int = HZ, door=(60, 40, 40)) -> None:
    top = base - h
    p.poly(roof, [(x - 1, top), (x + w // 2, top - w // 3), (x + w + 1, top)])
    p.rect(_shade(wall, 0.7), x + w - 8, top - w // 3, 4, w // 3 - 2)       # chimney
    p.rect(wall, x, top, w, h)
    p.window(x + 3, top + 4, 5, 6)
    p.window(x + w - 9, top + 4, 5, 6)
    if h > 26:
        p.window(x + 3, base - 13, 6, 7)
    p.rect(door, x + w - 9, base - 11, 6, 11)


def _boat(p: _Paint, x: int, y: int, hull=(170, 60, 50)) -> None:
    p.poly(hull, [(x, y), (x + 26, y), (x + 22, y + 6), (x + 3, y + 6)])
    p.rect((230, 230, 225), x + 12, y - 6, 9, 6)
    p.window(x + 14, y - 5, 3, 2)
    p.rect((60, 50, 40), x + 8, y - 20, 1, 20)


# ------------------------------------------------------------- painters


@_painter("harbour")
def _harbour(p: _Paint) -> None:
    _hills(p, 104, (95, 120, 110), 10, 1.0)
    _water(p, 0, 106, W, H - 106)
    p.rect((120, 115, 105), 150, 102, W - 150, 6)                 # harbour wall
    p.rect((90, 86, 80), 150, 108, W - 150, 2)
    p.rect((200, 200, 195), 312, 92, 3, 10)
    p.lamp(313, 91, (120, 255, 140))
    for i, (w, h, c) in enumerate(((26, 34, (200, 190, 170)), (22, 40, (170, 185, 200)), (28, 30, (215, 200, 160)),
                                   (24, 38, (190, 160, 150)), (26, 32, (210, 210, 200)))):
        _house(p, 2 + i * 27, w, h, c, base=118)
    p.rect(p.loc.ground, 0, 118, 140, 62)                        # quay
    p.rect((110, 105, 98), 0, 118, 140, 3)
    for i in range(4):
        p.rect((40, 40, 45), 12 + i * 36, 113, 4, 5)
    p.lamp(132, 92, ground=118)
    _boat(p, 165, 114)
    _boat(p, 215, 120, (50, 90, 150))
    _boat(p, 262, 112, (230, 200, 70))


@_painter("main_street")
def _main_street(p: _Paint) -> None:
    _ground(p, HZ, (75, 75, 80))
    p.rect((150, 145, 135), 0, HZ, W, 8)
    x = 0
    walls = [(190, 170, 150), (150, 160, 175), (200, 185, 160), (170, 140, 130), (185, 185, 175), (160, 150, 120)]
    awnings = [(170, 50, 50), (50, 110, 80), (60, 80, 150), (200, 150, 40), (120, 60, 110), (60, 120, 140)]
    for i, (w, h) in enumerate(((52, 62), (46, 54), (58, 70), (50, 58), (60, 66), (54, 60))):
        top = HZ - h
        p.rect(walls[i], x, top, w, h)
        p.rect(_shade(walls[i], 0.75), x, top, w, 3)
        p.window_grid(x + 5, top + 7, (w - 6) // 9, max(1, (h - 32) // 12), dx=9, dy=12, w=5, h=7)
        p.rect(awnings[i], x + 2, HZ - 24, w - 4, 4)
        p.window(x + 4, HZ - 19, w - 18, 12)
        p.rect((50, 40, 35), x + w - 11, HZ - 19, 7, 19)
        x += w
    p.lamp(130, 88, ground=HZ + 4)
    p.lamp(250, 88, ground=HZ + 4)
    p.rect((50, 50, 55), 300, 96, 1, 28)                        # bus stop
    p.rect((200, 40, 40), 296, 94, 9, 6)


@_painter("town_hall")
def _town_hall(p: _Paint) -> None:
    _ground(p)
    p.rect((165, 160, 150), 0, HZ, W, 6)
    stone, dark = (200, 190, 170), (150, 140, 125)
    p.rect(stone, 140, 60, 170, 52)
    p.poly(dark, [(136, 60), (225, 42), (314, 60)])
    for i in range(5):
        p.window(160 + i * 28, 70, 8, 14)
    for i in range(6):
        p.rect((225, 218, 200), 148 + i * 28, 64, 6, 48)
    for i in range(3):
        p.rect(_shade(stone, 0.92 - i * 0.05), 140 - i * 4, 112 + i * 3, 170 + i * 8, 3)
    p.rect(stone, 210, 12, 30, 32)                              # clock tower
    p.poly(dark, [(207, 12), (225, 2), (243, 12)])
    p.circle((240, 236, 220), 225, 27, 10)
    p.line((30, 30, 30), (225, 27), (225, 20))
    p.line((30, 30, 30), (225, 27), (230, 29))
    p.lamps.append((225, 27, (255, 240, 200)))                  # the clock face is lit at night
    p.rect((60, 60, 60), 300, 22, 1, 38)
    p.rect((40, 70, 150), 301, 22, 10, 6)
    p.lamp(120, 90, ground=HZ + 3)


@_painter("park")
def _park(p: _Paint) -> None:
    _ground(p, 112)
    for i in range(12):
        p.circle((70, 120, 60), 10 + i * 28, 108, 12)
    p.poly((190, 175, 140), [(140, H), (190, H), (172, 112), (164, 112)])
    p.ellipse(WATER_C, 196, 120, 64, 14)
    p.ellipse(WATER_HI, 204, 122, 40, 3)
    p.rect((200, 195, 185), 234, 104, 46, 6)                    # bandstand
    for i in range(4):
        p.rect((230, 230, 225), 236 + i * 13, 86, 2, 18)
    p.poly((60, 110, 80), [(230, 86), (257, 72), (284, 86)])
    p.rect((230, 230, 225), 230, 86, 54, 2)
    p.rect((110, 80, 50), 150, 114, 16, 2)                      # bench
    p.lamp(222, 92, ground=114)
    _tree(p, 22, 122, 14)
    _tree(p, 128, 116, 10)
    _tree(p, 304, 124, 13, (55, 100, 50))


@_painter("factory")
def _factory(p: _Paint) -> None:
    _ground(p, HZ, (95, 92, 88))
    p.rect((140, 90, 70), 290, 22, 12, 98)                      # chimney
    p.rect((200, 200, 200), 290, 32, 12, 3)
    for x, w, h in ((130, 90, 46), (224, 96, 56)):
        top = HZ - h
        p.rect((150, 155, 160), x, top, w, h)
        for sx in range(x, x + w, 4):
            p.rect((130, 135, 142), sx, top, 1, h)
        p.poly((110, 115, 122), [(x - 2, top), (x + w // 2, top - 8), (x + w + 2, top)])
        p.rect((90, 95, 100), x + 10, HZ - 28, 28, 28)          # roller door
        for ry in range(HZ - 28, HZ, 3):
            p.rect((75, 80, 85), x + 10, ry, 28, 1)
        p.window_grid(x + 46, top + 6, 4, 1, dx=10, w=6, h=4)
        p.lamp(x + 24, HZ - 32)
    for x in range(0, 128, 6):                                   # fence
        p.rect((60, 70, 60), x, HZ - 14, 1, 14)
    p.rect((60, 70, 60), 0, HZ - 14, 128, 1)
    p.rect((60, 70, 60), 0, HZ - 7, 128, 1)


@_painter("farm")
def _farm(p: _Paint) -> None:
    _hills(p, 100, (120, 160, 90), 12, 2.0)
    for i, y in enumerate(range(106, H, 12)):
        p.rect((150, 140, 80) if i % 2 else (120, 150, 70), 0, y, W, 12)
        for x in range(i * 5 % 16, W, 16):
            p.rect(_shade((150, 140, 80) if i % 2 else (120, 150, 70), 0.85), x, y + 5, 10, 1)
    p.rect((50, 85, 45), 0, 104, W, 3)                          # hedges
    p.rect((50, 85, 45), 0, 117, 200, 3)
    p.rect((150, 50, 40), 215, 74, 60, 44)                      # barn
    p.poly((90, 40, 35), [(211, 74), (226, 58), (264, 58), (279, 74)])
    p.rect((90, 40, 35), 236, 92, 18, 26)
    p.rect((240, 240, 230), 236, 92, 18, 1)
    p.rect((170, 170, 175), 284, 62, 14, 56)                    # silo
    p.circle((170, 170, 175), 291, 62, 7)
    p.lamp(228, 80)
    for x in range(0, 60, 10):
        p.rect((110, 85, 55), x, 120, 2, 10)
    p.rect((110, 85, 55), 0, 123, 60, 1)


@_painter("stadium")
def _stadium(p: _Paint) -> None:
    _ground(p)
    for x in range(0, W, 40):
        p.rect((80, 150, 80), x, HZ, 20, H - HZ)
    p.rect((235, 235, 235), 0, HZ + 14, W, 1)
    p.rect((110, 110, 120), 120, 62, 200, 58)
    for r in range(6):
        p.rect((40, 90, 160) if r % 2 else (225, 225, 230), 124, 70 + r * 8, 196, 5)
    p.poly((80, 80, 90), [(116, 62), (W, 50), (W, 56), (120, 66)])
    for i, c in enumerate(((200, 60, 50), (40, 120, 190), (230, 190, 60), (60, 150, 90))):
        p.rect(c, i * 30, HZ - 8, 28, 8)                        # advert boards
    for x in (130, 296):
        p.rect((150, 150, 155), x, 28, 3, 36)
        p.rect((190, 190, 195), x - 6, 22, 15, 6)
        p.lamp(x + 1, 25, (255, 255, 230))


@_painter("school")
def _school(p: _Paint) -> None:
    _ground(p)
    p.rect((150, 145, 140), 0, HZ, W, 4)
    p.rect((150, 110, 90), 125, 50, 195, 70)
    p.rect((110, 80, 65), 125, 48, 195, 4)
    p.window_grid(132, 58, 20, 3, dx=9, dy=18, w=6, h=10)
    p.rect((120, 125, 130), 200, 94, 40, 4)                     # entrance canopy
    p.window(206, 98, 28, 22)
    p.rect((30, 40, 90), 250, 104, 40, 10)
    p.rect((230, 200, 60), 252, 112, 36, 1)
    for x in range(0, W, 4):                                     # railings with the gate gap
        if not 196 <= x <= 244:
            p.rect((40, 70, 50), x, 108, 1, 12)
    p.rect((40, 70, 50), 0, 108, 196, 1)
    p.rect((40, 70, 50), 245, 108, W - 245, 1)
    p.rect((40, 70, 50), 194, 102, 3, 18)
    p.rect((40, 70, 50), 244, 102, 3, 18)
    _tree(p, 30, 118, 14)
    p.lamp(190, 82, ground=HZ)


@_painter("council_chamber")
def _council_chamber(p: _Paint) -> None:
    p.rect((120, 85, 60), 0, 0, W, H)
    p.rect((90, 62, 44), 0, 0, W, 8)
    for x in range(0, W, 32):
        p.rect((105, 72, 50), x + 3, 30, 26, 68)
    p.rect((140, 105, 75), 0, 100, W, 3)
    for x in (16, 282):                                          # tall windows
        p.rect((170, 190, 210), x, 12, 22, 62)
        p.rect((90, 62, 44), x + 10, 12, 2, 62)
        p.rect((90, 62, 44), x, 40, 22, 2)
    p.circle((200, 170, 80), 160, 30, 14)                       # crest
    p.circle((150, 40, 40), 160, 30, 10)
    p.rect((120, 30, 40), 152, 54, 16, 42)                      # mayor's chair
    p.rect((70, 50, 40), 0, 126, W, H - 126)
    for x, y, w in ((0, 112, 120), (110, 96, 100), (200, 112, 120)):   # horseshoe of desks
        for c in range(x + 6, x + w - 6, 18):
            p.rect((40, 90, 60), c, y - 8, 10, 8)               # green leather chairs
        p.rect((90, 60, 40), x, y, w, 14)
        p.rect((130, 95, 65), x, y, w, 2)


@_painter("market")
def _market(p: _Paint) -> None:
    for i, c in enumerate(((180, 160, 140), (160, 150, 170), (190, 180, 150), (150, 140, 120), (175, 165, 160),
                           (165, 160, 140), (185, 170, 150))):
        _house(p, i * 46, 46, 48, c, base=100)
    _ground(p, 100, p.loc.ground)
    p.line((60, 60, 60), (0, 58), (W, 64))
    for i, x in enumerate(range(4, W, 12)):                      # bunting
        y = 58 + x * 6 // W
        p.poly(((200, 50, 50), (240, 200, 60), (50, 100, 180))[i % 3], [(x, y), (x + 8, y), (x + 4, y + 6)])
    for k, (x, col) in enumerate(((128, (180, 50, 50)), (192, (50, 130, 80)), (256, (50, 80, 160)))):
        for j in range(0, 60, 6):
            p.rect(col if (j // 6) % 2 else (240, 240, 235), x + j, 74, 6, 10)
        for j in range(0, 60, 6):
            p.poly(col, [(x + j, 84), (x + j + 6, 84), (x + j + 3, 87)])
        p.rect((80, 70, 60), x, 84, 2, 34)
        p.rect((80, 70, 60), x + 58, 84, 2, 34)
        p.rect((140, 100, 60), x, 104, 60, 6)
        for d in range(8):
            p.circle(((220, 60, 40), (240, 160, 40), (90, 160, 60), (230, 220, 120))[(d + k) % 4], x + 5 + d * 7, 101, 3)


@_painter("market_shed")
def _market_shed(p: _Paint) -> None:
    p.rect((80, 65, 50), 0, 0, W, H)
    for y in range(40, 112, 6):
        p.rect((95, 78, 60), 0, y, W, 5)
    for x in range(-30, W + 60, 60):                             # roof trusses
        p.line((55, 42, 32), (x, 0), (x + 30, 36), 3)
        p.line((55, 42, 32), (x + 60, 0), (x + 30, 36), 3)
    p.rect((55, 42, 32), 0, 36, W, 4)
    for x in range(0, W, 8):                                     # string lights, always on indoors
        y = 46 + int(5 * math.sin(x * 0.04))
        p.rect((255, 220, 140), x, y, 2, 2)
    p.rect((110, 105, 95), 0, 112, W, H - 112)
    for i, x in enumerate(range(120, W, 66)):
        cloth = ((160, 50, 50), (60, 110, 150), (190, 150, 60))[i % 3]
        p.rect(cloth, x, 96, 58, 16)
        p.rect((130, 100, 70), x, 94, 58, 3)
        for d in range(7):
            p.circle(((230, 200, 120), (200, 80, 50), (120, 170, 80))[(d + i) % 3], x + 6 + d * 8, 91, 3)


@_painter("cannery")
def _cannery(p: _Paint) -> None:
    brick, roof = (140, 75, 55), (90, 80, 78)
    p.rect(brick, 40, 30, 10, 92)                                # chimney
    p.rect(brick, 110, 52, 150, 70)
    for i in range(5):
        p.poly(roof, [(110 + i * 30, 52), (110 + i * 30, 40), (140 + i * 30, 52)])
    for i in range(12):
        x = 116 + i * 12
        if i % 4 == 1 or i % 5 == 3:
            p.rect((25, 25, 30), x, 74, 7, 10)                   # broken panes
        else:
            p.window(x, 74, 7, 10)
    p.rect((150, 90, 50), 130, 58, 90, 10)                       # the rusting sign
    for x in (138, 166, 197):
        p.rect((110, 60, 35), x, 60, 6, 6)
    p.rect(_shade(brick, 0.9), 262, 76, 58, 46)
    p.window_grid(268, 84, 5, 2, dx=10, dy=14, w=6, h=8)
    p.rect(p.loc.ground, 0, 122, 200, 58)
    p.rect((110, 105, 98), 0, 122, 200, 2)
    _water(p, 200, 124, 120, 56)
    p.lamp(100, 96, ground=122)


@_painter("slipway")
def _slipway(p: _Paint) -> None:
    _hills(p, 100, (100, 125, 115), 8, 3.0)
    _water(p, 0, 104, W, H - 104)
    p.rect((140, 75, 55), 0, 70, 96, 46)                         # cannery end wall
    p.poly((90, 80, 78), [(0, 70), (48, 58), (96, 70)])
    p.window_grid(8, 78, 4, 2, dx=22, dy=16, w=8, h=9)
    p.rect(p.loc.ground, 0, 116, 120, 64)
    p.poly((150, 140, 120), [(120, 116), (160, 116), (250, H), (170, H)])
    p.poly((110, 105, 92), [(140, 140), (186, 140), (250, H), (170, H)])
    _boat(p, 205, 112)
    p.poly((230, 230, 225), [(150, 128), (168, 128), (165, 133), (152, 133)])
    p.lamp(112, 92, ground=116)


@_painter("loading_dock")
def _loading_dock(p: _Paint) -> None:
    _hills(p, 98, (110, 125, 120), 6, 4.0)
    _water(p, 0, 100, W, 14)
    p.rect(p.loc.ground, 0, 112, W, H - 112)
    for x in range(0, W, 12):
        p.rect((220, 180, 40), x, 112, 6, 2)
    stacks = [(150, 96, (180, 60, 50)), (150, 80, (50, 100, 160)), (192, 96, (60, 130, 90)), (192, 80, (200, 150, 50)),
              (234, 96, (130, 60, 120)), (150, 64, (200, 110, 50))]
    for x, y, c in stacks:
        p.rect(c, x, y, 40, 16)
        for rx in range(x + 2, x + 40, 4):
            p.rect(_shade(c, 0.8), rx, y + 1, 1, 14)
    p.rect((230, 190, 40), 270, 30, 4, 82)                       # crane
    p.rect((230, 190, 40), 300, 30, 4, 82)
    p.rect((230, 190, 40), 200, 26, 120, 5)
    for x in range(204, 318, 8):
        p.line((180, 140, 30), (x, 26), (x + 4, 31))
    p.rect((40, 40, 40), 230, 31, 1, 26)
    p.rect((60, 60, 65), 222, 57, 18, 3)
    for x in (16, 34):
        p.rect((140, 100, 60), x, 116, 14, 5)
    p.lamp(130, 72, ground=112)


@_painter("lighthouse")
def _lighthouse(p: _Paint) -> None:
    _water(p, 0, 100, W, H - 100)
    p.poly((90, 90, 85), [(170, H), (186, 110), (226, 96), (290, 92), (W, 100), (W, H)])
    p.poly((120, 118, 110), [(196, 112), (226, 100), (250, 100), (232, 116)])
    p.poly(p.loc.ground, [(0, 116), (140, 120), (160, H), (0, H)])
    p.poly((240, 240, 235), [(240, 96), (262, 96), (258, 30), (244, 30)])
    for y in (46, 70):
        p.rect((190, 40, 40), 242, y, 18, 8)
    p.rect((40, 40, 45), 240, 26, 22, 4)
    p.rect((200, 220, 230), 245, 16, 12, 10)
    p.poly((190, 40, 40), [(243, 16), (251, 8), (259, 16)])
    p.lamps.append((*LIGHTHOUSE_LAMP, (255, 240, 180)))
    p.rect((230, 230, 225), 270, 84, 24, 12)                     # keeper's cottage
    p.poly((80, 80, 85), [(268, 84), (282, 76), (296, 84)])
    p.window(274, 88, 4, 4)
    p.window(286, 88, 4, 4)


@_painter("lifeboat_station")
def _lifeboat_station(p: _Paint) -> None:
    _hills(p, 96, (110, 130, 115), 8, 4.0)
    _water(p, 0, 104, W, H - 104)
    p.rect(p.loc.ground, 0, 116, 150, 64)
    p.rect((225, 220, 205), 160, 56, 110, 56)
    p.poly((70, 80, 100), [(156, 56), (215, 36), (274, 56)])
    p.rect((40, 60, 110), 190, 72, 50, 40)
    p.rect((230, 120, 40), 190, 72, 50, 3)
    p.window_grid(166, 66, 2, 2, dx=10, dy=14, w=6, h=8)
    p.window_grid(248, 66, 2, 2, dx=10, dy=14, w=6, h=8)
    p.poly((140, 135, 125), [(190, 112), (240, 112), (300, H), (230, H)])
    p.rect((60, 60, 60), 282, 26, 1, 30)
    p.rect((40, 60, 140), 283, 26, 10, 6)
    p.rect((240, 240, 240), 283, 28, 10, 2)
    p.lamp(150, 88, ground=116)


@_painter("seafront")
def _seafront(p: _Paint) -> None:
    _water(p, 0, 82, W, 30)
    p.rect((80, 80, 90), 226, 78, 18, 4)                         # a ship on the horizon
    p.rect((80, 80, 90), 232, 74, 6, 4)
    p.rect((215, 200, 155), 0, 108, W, 10)
    p.rect(p.loc.ground, 0, 118, W, H - 118)
    p.rect((130, 125, 120), 0, 118, W, 2)
    p.rect((40, 60, 70), 0, 106, W, 2)                           # railings
    for x in range(0, W, 10):
        p.rect((40, 60, 70), x, 106, 1, 12)
    for x in (40, 150, 260):
        p.lamp(x, 86, ground=118)
    for x in (172, 282):
        p.rect((110, 80, 50), x, 122, 18, 2)
        p.rect((110, 80, 50), x, 118, 18, 1)


@_painter("fire_station")
def _fire_station(p: _Paint) -> None:
    _ground(p, HZ, (100, 100, 98))
    p.rect((130, 130, 128), 0, HZ, W, 6)
    p.rect((170, 70, 50), 120, 56, 162, 64)
    p.rect((130, 50, 40), 120, 54, 162, 3)
    p.window_grid(128, 60, 9, 1, dx=16, w=8, h=8)
    p.rect((240, 240, 235), 126, 71, 150, 4)
    for x in (130, 180, 230):
        p.rect((200, 30, 30), x, 78, 42, 42)
        p.window(x + 3, 82, 36, 5)
        for ry in range(90, 120, 5):
            p.rect((170, 25, 25), x, ry, 42, 1)
    p.rect((150, 60, 45), 286, 18, 22, 102)                      # drill tower
    for i in range(5):
        p.window(294, 26 + i * 18, 6, 8)
    p.lamp(110, 86, ground=HZ)


@_painter("police_station")
def _police_station(p: _Paint) -> None:
    _ground(p)
    p.rect((150, 145, 140), 0, HZ, W, 4)
    p.rect((150, 150, 155), 125, 46, 170, 74)
    p.rect((120, 120, 128), 125, 44, 170, 4)
    p.window_grid(134, 54, 8, 3, dx=20, dy=18, w=8, h=11)
    p.rect((150, 150, 155), 196, 88, 30, 32)
    p.rect((70, 50, 40), 201, 94, 20, 26)
    for i in range(2):
        p.rect((170, 170, 175), 196 - i * 4, 114 + i * 3, 30 + i * 8, 3)
    p.rect((60, 90, 200), 205, 80, 12, 9)                        # the blue lamp
    p.rect((240, 240, 240), 205, 84, 12, 1)
    p.lamps.append((211, 84, (90, 140, 255)))
    for x in range(0, 120, 30):
        p.rect((50, 50, 55), x + 10, 114, 3, 6)
    p.lamp(110, 86, ground=HZ)


@_painter("residential_street")
def _residential_street(p: _Paint) -> None:
    _ground(p, HZ + 6, (70, 70, 74))
    p.rect((150, 145, 138), 0, HZ, W, 6)
    walls = [(200, 185, 165), (175, 160, 150), (210, 200, 180), (185, 170, 160), (205, 190, 170), (170, 165, 155), (195, 180, 160)]
    doors = [(60, 40, 40), (40, 70, 110), (50, 90, 60), (120, 40, 40), (60, 60, 70), (40, 70, 110), (110, 90, 40)]
    for i in range(7):
        _house(p, i * 46, 46, 50, walls[i], door=doors[i])
    for i in range(7):                                           # front walls with gates
        p.rect((150, 110, 90), i * 46, HZ - 5, 30, 5)
    for x, c in ((150, (170, 40, 40)), (236, (60, 90, 150))):
        p.rect(c, x, HZ + 10, 34, 8)
        p.rect(c, x + 7, HZ + 5, 20, 6)
        p.window(x + 9, HZ + 6, 7, 4)
        p.window(x + 18, HZ + 6, 7, 4)
        p.rect((25, 25, 25), x + 4, HZ + 17, 6, 3)
        p.rect((25, 25, 25), x + 24, HZ + 17, 6, 3)
    p.lamp(130, 84, ground=HZ)


@_painter("coast_road")
def _coast_road(p: _Paint) -> None:
    _water(p, 150, 72, W - 150, H - 72)
    p.poly((140, 160, 120), [(260, 72), (300, 66), (W, 68), (W, 74)])   # far headland
    p.poly(p.loc.ground, [(0, 90), (120, 92), (175, 104), (196, H), (0, H)])
    p.poly((140, 130, 115), [(175, 104), (190, 104), (214, H), (196, H)])  # cliff face
    p.poly((80, 80, 85), [(0, 142), (150, 110), (166, 110), (36, H), (0, H)])
    p.poly((235, 235, 225), [(52, 152), (54, 150), (60, 150), (58, 152)])
    for x in range(140, 172, 6):                                 # stone wall at the edge
        y = 104 + (x - 140) // 4
        p.rect((150, 145, 135), x, y - 5, 5, 5)


@_painter("woods")
def _woods(p: _Paint) -> None:
    p.rect((45, 70, 40), 0, 36, W, 80)
    for x in range(0, W + 20, 20):
        p.circle((45, 70, 40), x, 38, 14)
    for x in range(8, W, 23):
        p.rect((50, 40, 30), x, 60, 3, 50)
    _ground(p, 108, p.loc.ground)
    p.poly((150, 130, 90), [(144, 108), (166, 108), (230, H), (100, H)])
    for x, w in ((14, 12), (200, 10), (290, 14)):
        p.rect((80, 60, 40), x, 0, w, 124)
        p.circle((40, 80, 40), x + w // 2, 8, 26)
    for x in range(0, W, 14):
        p.poly((60, 120, 50), [(x, 122), (x + 6, 112), (x + 12, 122)])


@_painter("estuary")
def _estuary(p: _Paint) -> None:
    _hills(p, 96, (110, 130, 110), 6, 5.0)
    _ground(p, 100)
    p.poly(WATER_C, [(0, 108), (120, 106), (220, 114), (W, 108), (W, 120), (220, 126), (120, 118), (0, 122)])
    p.poly(WATER_C, [(180, 150), (W, 140), (W, 160), (210, 166)])
    for x in range(0, 64, 3):
        p.line((150, 140, 80), (x, 150), (x + 1, 124 - (x * 7) % 12))
    for bx, by in ((200, 40), (214, 46), (230, 38), (90, 30)):
        p.line((40, 40, 50), (bx - 3, by - 2), (bx, by))
        p.line((40, 40, 50), (bx, by), (bx + 3, by - 2))
    for x in (250, 266):                                         # wading birds
        p.rect((230, 230, 230), x, 102, 3, 3)
        p.rect((60, 60, 60), x + 1, 105, 1, 4)


@_painter("village")
def _village(p: _Paint) -> None:
    _hills(p, 96, (100, 140, 90), 8, 6.0)
    _ground(p, 112)
    p.rect((170, 165, 150), 210, 80, 52, 32)                     # church
    p.poly((90, 85, 80), [(208, 80), (236, 68), (264, 80)])
    p.rect((170, 165, 150), 262, 56, 16, 56)
    p.poly((90, 85, 80), [(260, 56), (270, 20), (280, 56)])
    p.window(232, 88, 6, 12)
    p.window(267, 70, 6, 8)
    p.rect((225, 220, 205), 130, 78, 60, 34)                     # pub
    p.poly((60, 55, 55), [(127, 78), (160, 64), (193, 78)])
    p.window_grid(136, 84, 4, 2, dx=13, dy=14, w=7, h=7)
    p.rect((60, 40, 30), 196, 80, 1, 32)
    p.rect((40, 90, 50), 192, 84, 9, 10)
    for i, c in enumerate(((220, 210, 190), (200, 190, 170))):
        _house(p, 4 + i * 34, 30, 28, c, base=112)
    p.poly((180, 165, 125), [(110, H), (140, H), (176, 112), (168, 112)])
    p.lamp(120, 90, ground=112)


@_painter("studio_wide")
def _studio_wide(p: _Paint) -> None:
    p.rect((28, 34, 60), 0, 0, W, H)
    for i in range(6):                                           # back-wall screens (scenes animate them)
        p.rect((40, 60, 110), 12 + i * 50, 30, 40, 50)
    p.rect((80, 60, 50), 0, 130, W, 50)                          # desk
    p.rect((120, 95, 80), 0, 130, W, 4)


@_painter("weather_wall")
def _weather_wall(p: _Paint) -> None:
    p.rect((36, 42, 70), 0, 0, W, H)
    for x in range(0, W, 40):
        p.rect((44, 52, 84), x, 0, 1, 150)
    p.rect((18, 18, 24), 36, 16, 188, 128)                       # map screen bezel
    p.rect((18, 18, 24), 230, 16, 84, 128)                       # side panel bezel
    p.rect((40, 40, 50), 0, 150, W, 30)


def _armchair(p: _Paint, x: int, base: int, c, w: int = 56) -> None:
    """An armchair whose sitter's mark is (x, base): back behind the shoulders, arms either side."""
    p.ellipse(c, x - w // 2, base - 56, w, 20)
    p.rect(c, x - w // 2, base - 46, w, 46)
    p.rect(_shade(c, 0.8), x - w // 2 - 6, base - 30, 10, 34)
    p.rect(_shade(c, 0.8), x + w // 2 - 4, base - 30, 10, 34)
    p.rect(_shade(c, 0.65), x - w // 2 - 6, base + 2, w + 12, 6)


@_painter("studio_interview")
def _studio_interview(p: _Paint) -> None:
    p.rect(p.loc.sky, 0, 0, W, H)
    for x in range(0, W, 32):
        p.rect((42, 50, 80), x, 0, 1, 128)
    for x in range(30, W, 60):                                   # ceiling spots
        p.rect((90, 90, 100), x, 0, 6, 4)
    p.rect(p.loc.ground, 0, 128, W, H - 128)
    p.rect((80, 68, 64), 0, 128, W, 2)
    p.rect((18, 18, 24), 124, 24, 72, 52)                        # screen between the chairs
    p.rect((40, 70, 130), 128, 28, 64, 44)
    p.circle((200, 40, 40), 160, 50, 12)                         # the channel 7 ident
    p.rect((240, 240, 240), 154, 43, 12, 3)
    p.poly((240, 240, 240), [(163, 46), (166, 46), (160, 58), (157, 58)])
    host, guest = (MARKS["studio_interview"][k] for k in ("host", "guest"))
    _armchair(p, host[0], host[1], (120, 40, 45))
    _armchair(p, guest[0], guest[1], (120, 40, 45))
    p.rect((90, 70, 55), 140, 140, 40, 4)                        # low table
    p.rect((70, 55, 45), 144, 144, 3, 12)
    p.rect((70, 55, 45), 173, 144, 3, 12)
    for x in (148, 166):
        p.rect((170, 200, 225), x, 134, 4, 6)
    p.rect((90, 70, 55), 14, 110, 14, 18)                        # plant
    for dx, dy in ((-6, -16), (0, -24), (6, -18), (-2, -10)):
        p.circle((60, 120, 60), 21 + dx, 110 + dy, 7)
    p.rect((50, 50, 55), 304, 60, 2, 68)                         # floor lamp
    p.poly((235, 200, 140), [(296, 60), (312, 60), (308, 48), (300, 48)])


@_painter("studio_sofa")
def _studio_sofa(p: _Paint) -> None:
    p.rect(p.loc.sky, 0, 0, W, H)
    p.rect(p.loc.ground, 0, 140, W, H - 140)
    for y in range(144, H, 6):
        p.rect(_shade(p.loc.ground, 0.85), 0, y, W, 1)
    p.rect((200, 185, 160), 0, 136, W, 4)                        # skirting
    p.rect((240, 238, 230), 58, 12, 204, 86)                     # window onto the harbour
    p.s.blit(picture("harbour", "day", None, (196, 78)), (62, 16))
    for x in (126, 194):
        p.rect((240, 238, 230), x, 16, 3, 78)
    p.rect((240, 238, 230), 62, 54, 196, 3)
    p.rect((150, 110, 80), 6, 30, 44, 4)                         # shelves
    p.rect((150, 110, 80), 6, 60, 44, 4)
    for i, c in enumerate(((180, 60, 50), (60, 100, 150), (200, 170, 70), (80, 130, 90))):
        p.rect(c, 10 + i * 9, 20 + (i % 2) * 2, 6, 10 - (i % 2) * 2)
        p.rect(c, 12 + i * 9, 50, 5, 10)
    teal = (60, 120, 130)
    a, b = MARKS["studio_sofa"]["host_a"], MARKS["studio_sofa"]["host_b"]
    p.rect(teal, a[0] - 40, a[1] - 42, b[0] - a[0] + 80, 36)     # sofa back, behind both hosts
    for x in (a[0] - 36, (a[0] + b[0]) // 2 - 2):
        p.rect(_shade(teal, 1.12), x, a[1] - 38, 34, 28)         # back cushions
    p.rect(_shade(teal, 0.8), a[0] - 50, a[1] - 26, 14, 34)       # arms
    p.rect(_shade(teal, 0.8), b[0] + 36, a[1] - 26, 14, 34)
    p.rect(_shade(teal, 0.7), a[0] - 50, a[1] + 2, b[0] - a[0] + 100, 8)
    g = MARKS["studio_sofa"]["guest"]
    _armchair(p, g[0], g[1], (200, 140, 70), w=48)
    p.rect((120, 85, 60), 132, 156, 50, 4)                       # coffee table
    for x, c in ((140, (230, 230, 225)), (152, (200, 60, 50)), (166, (230, 230, 225))):
        p.rect(c, x, 150, 5, 6)
    p.rect((120, 85, 60), 20, 118, 26, 4)                        # side table and lamp
    p.rect((120, 85, 60), 31, 122, 3, 16)
    p.rect((60, 60, 60), 32, 100, 1, 18)
    p.poly((245, 215, 150), [(24, 100), (42, 100), (38, 88), (28, 88)])


@_painter("studio_late")
def _studio_late(p: _Paint) -> None:
    """The Last Ferry: painted with the lights already down, the harbour at night behind."""
    p.rect(p.loc.sky, 0, 0, W, H)
    p.rect((14, 14, 20), 34, 10, 240, 94)                        # window onto the harbour at night
    p.s.blit(picture("harbour", "night", None, (232, 86)), (38, 14))
    for x in (114, 192):
        p.rect((14, 14, 20), x, 14, 3, 86)
    for x0 in (0, 274):                                          # velvet curtains either side
        p.rect((90, 22, 32), x0, 0, 46, 132)
        for x in range(x0 + 4, x0 + 46, 8):
            p.rect((62, 14, 24), x, 0, 2, 132)
    p.rect(p.loc.ground, 0, 128, W, H - 128)
    for y in range(134, H, 7):
        p.rect(_shade(p.loc.ground, 0.8), 0, y, W, 1)
    host, guest = MARKS["studio_late"]["host"], MARKS["studio_late"]["guest"]
    leather = (72, 34, 38)
    p.ellipse(leather, host[0] - 26, host[1] - 62, 52, 16)       # tall chair back behind the host
    p.rect(leather, host[0] - 26, host[1] - 54, 52, 50)
    top = host[1] - 4                                            # desk top just above the baseline, like studio_wide
    p.rect((112, 70, 44), 40, top, 112, 4)
    p.rect((76, 46, 32), 44, top + 4, 104, 26)
    p.rect((92, 58, 40), 52, top + 9, 88, 16)
    p.rect((200, 170, 120), 48, top - 14, 2, 14)                 # desk lamp and a mug, clear of the host
    p.poly((235, 190, 110), [(42, top - 14), (56, top - 14), (52, top - 22), (46, top - 22)])
    p.rect((220, 215, 205), 128, top - 7, 7, 7)
    green = (46, 84, 70)
    p.rect(green, guest[0] - 50, guest[1] - 42, 136, 36)         # couch back, behind the guest's shoulders
    for x in range(guest[0] - 46, guest[0] + 82, 42):
        p.rect(_shade(green, 1.15), x, guest[1] - 38, 38, 26)    # back cushions
    p.rect(_shade(green, 0.8), guest[0] - 60, guest[1] - 26, 14, 34)   # arms
    p.rect(_shade(green, 0.8), guest[0] + 84, guest[1] - 26, 10, 34)
    p.rect(_shade(green, 0.65), guest[0] - 60, guest[1] + 2, 154, 8)
    p.rect((76, 46, 32), 154, 128, 14, 3)                        # side table and lamp between desk and couch
    p.rect((76, 46, 32), 159, 131, 4, 20)
    p.rect((60, 60, 60), 160, 112, 2, 16)
    p.poly((245, 205, 130), [(153, 112), (169, 112), (165, 102), (157, 102)])


TIDES = ((40, 110, 190), (240, 240, 235))                       # Tidewater Town: sea blue and white


@_painter("studio_sports")
def _studio_sports(p: _Paint) -> None:
    """The sports corner of the main studio: the stadium on the big screen, a blank results board
    the scenes can fill, the trophy cabinet and the scarves."""
    p.rect(p.loc.sky, 0, 0, W, H)
    for x in range(0, W, 32):
        p.rect((42, 50, 80), x, 0, 1, 128)
    for x in range(30, W, 60):                                   # ceiling spots
        p.rect((90, 90, 100), x, 0, 6, 4)
    p.rect(p.loc.ground, 0, 128, W, H - 128)
    p.rect((80, 68, 64), 0, 128, W, 2)
    p.rect((18, 18, 24), 84, 12, 116, 60)                        # big screen: the stadium
    p.s.blit(picture("stadium", "day", None, (108, 52)), (88, 16))
    p.rect((18, 18, 24), 206, 12, 64, 60)                        # results board, rows left blank
    p.rect((24, 34, 70), 210, 16, 56, 52)
    for i in range(6):
        y = 19 + i * 8
        p.rect(TIDES[0] if i % 2 == 0 else (190, 40, 40), 213, y, 5, 5)
        p.rect((70, 84, 120), 220, y, 30, 5)
        p.rect((230, 230, 230), 253, y, 4, 5)
        p.rect((230, 230, 230), 259, y, 4, 5)
    wood = (110, 75, 50)                                         # trophy cabinet, clear of the presenter
    p.rect(wood, 8, 28, 50, 100)
    p.rect((50, 64, 90), 12, 32, 42, 92)
    for y in (54, 80, 106):
        p.rect((170, 200, 215), 12, y, 42, 2)
    gold, silver = (220, 180, 60), (200, 205, 215)
    for x, y, c in ((18, 54, gold), (36, 54, silver), (16, 80, silver), (34, 80, gold), (24, 106, gold), (42, 106, silver)):
        p.poly(c, [(x, y - 14), (x + 10, y - 14), (x + 7, y - 7), (x + 3, y - 7)])
        p.rect(c, x + 4, y - 7, 2, 4)
        p.rect(_shade(c, 0.7), x + 2, y - 3, 6, 3)
    p.rect((150, 150, 160), 276, 24, 40, 2)                      # scarves on a rail
    for i, (a, b) in enumerate((TIDES, ((190, 40, 40), (30, 30, 30)), (TIDES[0], (240, 200, 60)))):
        x = 279 + i * 12
        for y in range(26, 106, 6):
            p.rect(a if (y // 6) % 2 == 0 else b, x, y, 8, 6)
        for fx in range(x, x + 8, 2):
            p.rect(b, fx, 106, 1, 4)
    host, guest = MARKS["studio_sports"]["host"], MARKS["studio_sports"]["guest"]
    top = host[1] - 4                                            # desk top just above the baseline: they stand behind it
    p.rect((210, 210, 215), host[0] - 40, top, 80, 4)
    p.rect((40, 46, 70), host[0] - 36, top + 4, 72, 30)
    p.rect(TIDES[0], host[0] - 36, top + 10, 72, 3)
    p.rect((200, 40, 40), host[0] - 36, top + 14, 72, 2)
    blue = TIDES[0]                                              # the guest's swivel chair
    p.ellipse(_shade(blue, 0.8), guest[0] - 24, guest[1] - 52, 48, 14)
    p.rect(_shade(blue, 0.8), guest[0] - 24, guest[1] - 46, 48, 44)
    p.rect(blue, guest[0] - 30, guest[1] - 2, 60, 6)
    p.rect((150, 150, 160), guest[0] - 2, guest[1] + 4, 4, 14)
    p.ellipse((110, 110, 120), guest[0] - 16, guest[1] + 16, 32, 6)


def _generic(p: _Paint) -> None:
    """Any location without its own painter: the original blocks."""
    _ground(p)
    for i in range(5):
        bh = 40 + (i * 23) % 50
        p.rect(_shade(p.loc.ground, 0.7), 10 + i * 62, HZ - bh, 48, bh)


# ------------------------------------------------------------- building


def _sky(loc: Location, tod: str, wx: str | None) -> pygame.Surface:
    if tod == "day":
        top, bot = _shade(loc.sky, 0.8), _mix(loc.sky, (235, 240, 245), 0.45)
    else:
        top, bot = SKY_TOD[tod]
    if wx in SKY_WX:
        c, k = SKY_WX[wx]
        c = _shade(c, TOD_K[tod])
        top, bot = _mix(top, c, k), _mix(bot, c, k)
    s = pygame.Surface((W, H))
    for y in range(H):
        s.fill(_mix(top, bot, min(1.0, y / HZ)), (0, y, W, 1))
    clear = wx in (None, "sunny", "wind")
    if tod == "night" and clear:
        for i in range(40):
            s.fill((220, 220, 240), ((i * 97) % W, (i * 53) % 90, 1, 1))
        pygame.draw.circle(s, (235, 235, 220), (52, 36), 6)
        pygame.draw.circle(s, top, (55, 34), 5)
    elif tod == "day" and wx in (None, "sunny"):
        pygame.draw.circle(s, (255, 235, 150), (52, 40), 8)
    elif tod == "dusk" and clear:
        pygame.draw.circle(s, (255, 170, 90), (60, HZ - 14), 12)
    return s


def _grade(surf: pygame.Surface, tod: str, wx: str | None, *, tod_grade: bool = True) -> None:
    rgb = pygame.surfarray.pixels3d(surf)
    a = rgb.astype(np.float32)
    mult, desat, mix = WX_GRADE.get(wx, ((1.0, 1.0, 1.0), 0.0, None))
    if desat:
        a += (a.mean(axis=2, keepdims=True) - a) * desat
    a *= np.array(mult, np.float32) * (np.array(TOD_MULT[tod], np.float32) if tod_grade else 1.0)
    if mix:
        col, k = mix                                             # fog and snow light dim with the day, whatever the art
        a += (np.array(_shade(col, TOD_K[tod]), np.float32) - a) * k
    rgb[...] = np.clip(a, 0, 255).astype(np.uint8)
    del rgb                                                      # unlock the surface


PERSON_LIGHT_K = 0.5            # people on location are lit by the crew: half the backdrop's grade


def person_light(backdrop_id: str | None, tod: str, wx: str | None) -> tuple[float, float, float]:
    """A multiply for the people in front of an exterior, so they sit in its light: cool at
    night, warm at dusk, greyer in rain. Studio sets and interiors are lit as they are."""
    if not locations.get(backdrop_id).exterior:
        return (1.0, 1.0, 1.0)
    mult = WX_GRADE.get(wx, ((1.0, 1.0, 1.0), 0.0, None))[0]
    return tuple(1.0 + (m * t - 1.0) * PERSON_LIGHT_K for m, t in zip(mult, TOD_MULT.get(tod, TOD_MULT["day"])))


def _dusk_grade(surf: pygame.Surface, horizon: int) -> None:
    """Sunset for art made in daylight: a multiply can't turn blue sky orange, so tint instead.

    Each row gets a colour from DUSK_RAMP (purple overhead, pink, orange at the horizon, a warm
    dim on the ground), applied keeping each pixel's brightness. Sky, water and pale haze take
    most of it; buildings and grass a little, so they stay readable.
    """
    rgb = pygame.surfarray.pixels3d(surf)                       # indexed [x, y, channel]
    a = rgb.astype(np.float32)
    ys = np.arange(a.shape[1], dtype=np.float32) / max(1, horizon)
    stops = np.array([s for s, _ in DUSK_RAMP], np.float32)
    ramp = np.stack([np.interp(ys, stops, [c[i] for _, c in DUSK_RAMP]) for i in range(3)], axis=1)
    lum = a @ np.array([0.299, 0.587, 0.114], np.float32)
    blue = np.clip((a[..., 2] - np.maximum(a[..., 0], a[..., 1])) / 30.0, 0, 1)
    water = blue * np.clip((ys[None, :] - 1.0) * 10, 0, 1)    # blue below the horizon
    target = ramp[None, :, :] + (np.array(DUSK_WATER, np.float32) - ramp[None, :, :]) * water[..., None]
    target_lum = target @ np.array([0.299, 0.587, 0.114], np.float32)
    tint = target * (lum / target_lum)[..., None]
    haze = np.clip((lum - 185) / 45.0, 0, 1) * (ys[None, :] < 1.05)
    k = DUSK_K_REST + (DUSK_K_SKY - DUSK_K_REST) * np.maximum(blue, haze)
    a = a * DUSK_DARKEN
    a += (np.minimum(tint, 255) * DUSK_DARKEN - a) * k[..., None]
    rgb[...] = np.clip(a, 0, 255).astype(np.uint8)
    del rgb


_glows: dict[tuple, pygame.Surface] = {}


def _glow(c) -> pygame.Surface:
    g = _glows.get(c)
    if g is None:
        g = _glows[c] = pygame.Surface((13, 13), pygame.SRCALPHA)
        pygame.draw.circle(g, (*c, 50), (6, 6), 6)
        pygame.draw.circle(g, (*c, 90), (6, 6), 3)
    return g


def _light_up(surf: pygame.Surface, p: _Paint, tod: str) -> None:
    if tod == "day":
        return
    share = 65 if tod == "night" else 30
    for r in p.windows:
        if (r.x * 7 + r.y * 13) % 100 < share:
            surf.fill(LIT, r)
    for x, y, c in p.lamps:
        surf.blit(_glow(c), (x - 6, y - 6))
        surf.fill(c, (x - 1, y - 1, 3, 2))


def _paint(loc: Location) -> _Paint:
    p = _Paint(loc)
    PAINTERS.get(loc.id, _generic)(p)
    return p


def _finish(s: pygame.Surface) -> pygame.Surface:
    return s.convert() if pygame.display.get_surface() is not None else s


def _load(path: Path) -> pygame.Surface:
    img = pygame.image.load(str(path))
    if img.get_size() != (W, H):
        img = pygame.transform.scale(img, (W, H))
    out = pygame.Surface((W, H), 0, 32)                          # 32-bit so it can be graded
    out.blit(img, (0, 0))
    return out


def _build(loc: Location, tod: str, wx: str | None) -> pygame.Surface:
    for name, own_tod in ((f"{loc.id}_{tod}.png", True), (f"{loc.id}.png", False)):
        path = ART_DIR / name
        if path.exists():
            img = _load(path)
            if loc.exterior:
                dusk = tod == "dusk" and not own_tod
                if dusk:                                         # sunset first, so the weather sits on top of it
                    _dusk_grade(img, HORIZON.get(loc.id, DUSK_HZ))
                _grade(img, tod, wx, tod_grade=not own_tod and not dusk)
            return _finish(img)
    p = _paint(loc)
    if not loc.exterior:
        out = pygame.Surface((W, H))
        out.blit(p.s, (0, 0))
        return _finish(out)
    _grade(p.s, tod, wx)
    out = _sky(loc, tod, wx)
    out.blit(p.s, (0, 0))
    _light_up(out, p, tod)
    return _finish(out)


_cache: OrderedDict[tuple, pygame.Surface] = OrderedDict()
_art: dict[str, bool] = {}


def surface(backdrop_id: str | None, tod: str = "day", wx: str | None = None) -> pygame.Surface:
    """The graded still for a backdrop. Built on first use, then cached."""
    loc = locations.get(backdrop_id)
    if not loc.exterior:
        tod, wx = "day", None
    key = (loc.id, tod, wx)
    s = _cache.get(key)
    if s is None:
        s = _cache[key] = _build(loc, tod, wx)
        if len(_cache) > CACHE_SIZE:
            _cache.popitem(last=False)
    else:
        _cache.move_to_end(key)
    return s


_pictures: OrderedDict[tuple, pygame.Surface] = OrderedDict()


def picture(backdrop_id: str | None, tod: str, wx: str | None, size: tuple[int, int]) -> pygame.Surface:
    """A backdrop as a picture on a studio screen: centre-cropped to the screen's
    shape and smooth-scaled, which reads as a monitor rather than the set."""
    key = (locations.get(backdrop_id).id, tod, wx, size)
    pic = _pictures.get(key)
    if pic is None:
        src = surface(backdrop_id, tod, wx)
        w, h = size
        cw = min(W, H * w // h)
        ch = min(H, cw * h // w)
        crop = src.subsurface(((W - cw) // 2, (H - ch) // 2, cw, ch))
        pic = _pictures[key] = pygame.transform.smoothscale(crop, size)
        if len(_pictures) > 8:
            _pictures.popitem(last=False)
    return pic


def has_art(backdrop_id: str) -> bool:
    """True when real art exists, so scenes can skip placeholder-only touches."""
    if backdrop_id not in _art:
        _art[backdrop_id] = any((ART_DIR / f"{backdrop_id}{sfx}.png").exists() for sfx in ("", "_day", "_dusk", "_night"))
    return _art[backdrop_id]


# ------------------------------------------------------------- per frame


_washes: dict[tuple, pygame.Surface] = {}
_scratch: pygame.Surface | None = None
_fog: pygame.Surface | None = None


def _wash(rgba: tuple) -> pygame.Surface:
    s = _washes.get(rgba)
    if s is None:
        s = _washes[rgba] = pygame.Surface((W, H), pygame.SRCALPHA)
        s.fill(rgba)
    return s


def _fog_layer() -> pygame.Surface:
    global _fog
    if _fog is None:
        _fog = pygame.Surface((W, H), pygame.SRCALPHA)
        for i in range(9):
            pygame.draw.ellipse(_fog, (215, 215, 220, 45), ((i * 71) % W - 40, 50 + (i * 29) % 90, 140, 22))
    return _fog


_water_masks: dict[str, pygame.Surface] = {}
_shimmer_buf: pygame.Surface | None = None


def _water_mask(loc_id: str) -> pygame.Surface:
    """Where the art itself shows water inside the WATER rects, as an alpha mask: the shimmer
    keeps off the quays, ramps, boats and containers the art draws there. Taken once from the
    day picture; the night art lines up with it."""
    m = _water_masks.get(loc_id)
    if m is None:
        rgb = pygame.surfarray.array3d(surface(loc_id, "day", None)).astype(np.int16)
        water = (rgb[..., 2] > rgb[..., 0] + 25) & (rgb[..., 2] >= rgb[..., 1])
        inside = np.zeros((W, H), bool)
        for x0, y0, w, h in WATER[loc_id]:
            inside[x0:x0 + w, y0:y0 + h] = True
        m = pygame.Surface((W, H), pygame.SRCALPHA)
        m.fill((255, 255, 255, 255))
        pygame.surfarray.pixels_alpha(m)[:] = np.where(water & inside, 255, 0).astype(np.uint8)
        _water_masks[loc_id] = m
    return m


def _shimmer(canvas: pygame.Surface, loc_id: str, tod: str, t: float) -> None:
    global _shimmer_buf
    if _shimmer_buf is None:
        _shimmer_buf = pygame.Surface((W, H), pygame.SRCALPHA)
    c = {"day": (160, 195, 225), "dusk": (230, 170, 140), "night": (70, 85, 125)}[tod]
    buf = _shimmer_buf
    buf.fill((0, 0, 0, 0))
    for x0, y0, w, h in WATER[loc_id]:
        buf.set_clip(pygame.Rect(x0, y0, w, h))
        for i in range(max(3, w * h // 700)):
            x = x0 + (i * 41 + int(t * 10)) % (w + 24) - 24
            y = y0 + 2 + (i * 17) % max(1, h - 3)
            buf.fill(c, (x, y, 8 + (i % 3) * 5, 1))
    buf.set_clip(None)
    buf.blit(_water_mask(loc_id), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    canvas.blit(buf, (0, 0))


def _beam(canvas: pygame.Surface, t: float) -> None:
    global _scratch
    if _scratch is None:
        _scratch = pygame.Surface((W, H), pygame.SRCALPHA)
    a = math.sin(t * 0.9)
    if abs(a) < 0.15:
        return
    lx, ly = LIGHTHOUSE_LAMP
    reach = int(170 * a)
    _scratch.fill((0, 0, 0, 0))
    pygame.draw.polygon(_scratch, (255, 240, 180, int(70 * abs(a))), [(lx, ly), (lx + reach, ly - 12), (lx + reach, ly + 10)])
    canvas.blit(_scratch, (0, 0))


def _weather_fx(canvas: pygame.Surface, wx: str | None, tod: str, t: float) -> None:
    if wx in ("rain", "storm"):
        n, slant = (45, 1) if wx == "rain" else (80, 3)
        c = (190, 200, 220) if tod == "day" else (110, 120, 150)
        for i in range(n):
            x = (i * 37 - int(t * 30 * slant)) % (W + 20) - 10
            y = (i * 53 + int(t * 260)) % H
            pygame.draw.line(canvas, c, (x, y), (x - slant, y + 4))
        if wx == "storm" and t % 9.0 < 0.12:
            canvas.blit(_wash((255, 255, 255, 110)), (0, 0))
    elif wx == "snow":
        for i in range(50):
            y = (i * 29 + int(t * (14 + i % 5 * 3))) % H
            x = int(i * 61 + math.sin(t * 0.8 + i) * 6) % W
            canvas.fill((245, 245, 250), (x, y, 1 + i % 2, 1 + i % 2))
    elif wx == "fog":
        off = int(t * 6) % W
        canvas.blit(_fog_layer(), (-off, 0))
        canvas.blit(_fog_layer(), (W - off, 0))
    elif wx == "wind":
        for i in range(12):
            x = (i * 53 + int(t * (120 + i % 4 * 30))) % (W + 10) - 5
            y = 40 + (i * 23) % 110 + int(math.sin(t * 3 + i) * 3)
            canvas.fill((200, 190, 150), (x, y, 2, 1))


def draw(canvas: pygame.Surface, backdrop_id: str | None, tod: str = "day", wx: str | None = None, t: float = 0.0) -> None:
    """Paint the full canvas: the graded still, then the animated touches."""
    loc = locations.get(backdrop_id)
    canvas.blit(surface(loc.id, tod, wx), (0, 0))
    if not loc.exterior:
        return
    if loc.id in WATER:
        _shimmer(canvas, loc.id, tod, t)
    if loc.id == "lighthouse" and tod != "day":
        _beam(canvas, t)
    _weather_fx(canvas, wx, tod, t)


# ------------------------------------------------------------------- CLI


def contact_sheet(path: Path, ids: list[str] | None = None, *, per_row: int = 2) -> None:
    """Every location at day/dusk/night, then a weather row on the harbour."""
    pygame.font.init()
    f = pygame.font.SysFont("consolas,couriernew,monospace", 10, bold=True)
    ids = ids or [loc.id for loc in locations.LOCATIONS]
    pad, label = 4, 12
    cell_w, cell_h = W + pad, H + label + pad
    weathers = ("cloudy", "rain", "storm", "snow", "fog", "wind")
    rows = math.ceil(len(ids) / per_row) + 1
    sheet = pygame.Surface((max(per_row * len(TODS), len(weathers)) * cell_w, rows * cell_h))
    sheet.fill((20, 20, 24))
    frame = pygame.Surface((W, H))

    def cell(col: int, row: int, bid: str, tod: str, wx: str | None, name: str) -> None:
        draw(frame, bid, tod, wx, t=1.0)
        x, y = col * cell_w, row * cell_h
        sheet.blit(f.render(name, False, (230, 230, 230)), (x + 2, y))
        sheet.blit(frame, (x, y + label))

    for n, bid in enumerate(ids):
        for k, tod in enumerate(TODS):
            cell((n % per_row) * len(TODS) + k, n // per_row, bid, tod, None, f"{bid} / {tod}")
    for k, wx in enumerate(weathers):
        cell(k, rows - 1, "harbour", "day", wx, f"harbour / {wx}")
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(sheet, str(path))


def bake(ids: list[str], *, force: bool = False) -> list[Path]:
    """Write placeholders (daytime, ungraded) as PNG templates for real art."""
    out = []
    ART_DIR.mkdir(parents=True, exist_ok=True)
    for bid in ids:
        if bid not in locations.BY_ID:
            raise SystemExit(f"unknown backdrop id {bid!r}")
        loc = locations.BY_ID[bid]
        path = ART_DIR / f"{bid}.png"
        if path.exists() and not force:
            print(f"skip {path.name} (exists; --force to overwrite)")
            continue
        p = _paint(loc)
        s = _sky(loc, "day", None) if loc.exterior else pygame.Surface((W, H))
        s.blit(p.s, (0, 0))
        pygame.image.save(s, str(path))
        out.append(path)
        print(f"baked {path}")
    return out


def _cli(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m newsroom.backdrops")
    ap.add_argument("--sheet", type=Path, help="write a contact sheet PNG here")
    ap.add_argument("--ids", nargs="*", help="limit the sheet to these ids")
    ap.add_argument("--bake", nargs="*", metavar="ID", help="write placeholders to assets/backdrops (no ids = all)")
    ap.add_argument("--force", action="store_true", help="let --bake overwrite existing files")
    a = ap.parse_args(argv)
    if a.bake is not None:
        bake(a.bake or [loc.id for loc in locations.LOCATIONS], force=a.force)
    if a.sheet:
        contact_sheet(a.sheet, a.ids)
        print(f"sheet -> {a.sheet}")
    if a.bake is None and not a.sheet:
        ap.print_help()
    return 0


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
