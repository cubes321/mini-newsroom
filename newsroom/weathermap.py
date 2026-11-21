"""The weather map: Gordon's wall screen drawn from the town's map (geography.py), not a made-up coast.

The coast from Greymouth to Pellow Harbour with the Grey running up to Polgrey, the same shore the locator and
The Coast Road use, and four spots with a temperature each. The script still gives one temperature, Port
Wexley's; the others are worked out here from it and the sky (`spots`), so the model writes nothing new and
the four always agree with each other. Drawn at the canvas's size, in the pixels, like the rest of the set.
"""
from __future__ import annotations

import math

from . import geography as g

# The window on the map, in miles east and north of the Quay Steps: 24 miles of coast across the screen. The
# lower third hides the screen's bottom 12 rows, so the coast sits above them and the sea runs under.
X0, X1, Y1 = -12.5, 11.5, 7.2

LAND, LAND_HIGH, SEA, SEA_DEEP = (112, 150, 84), (100, 138, 78), (58, 104, 150), (50, 92, 138)
SHORE_LINE, TOWN = (206, 198, 150), (196, 186, 170)
PLATE, NAME, TEMP = (20, 22, 34), (240, 240, 240), (255, 222, 110)
DIM = {"storm": 0.62, "rain": 0.8, "fog": 0.88, "snow": 0.94, "cloudy": 0.9}     # the map under a dark sky

# The spots: (place, the name on the map, where its label goes from the dot: dx, dy, and "l" to end there).
SPOTS = (("greymouth", "Greymouth", 5, -14, ""),
         ("polgrey", "Polgrey", 6, -5, ""),
         ("harbour", "Port Wexley", 7, -4, ""),
         ("pellow_harbour", "Pellow Harbour", 4, -15, "l"))


def spots(temp_c: int, state: str | None) -> dict[str, int]:
    """Each spot's temperature from Port Wexley's: Polgrey, five miles up the estuary, is a degree colder (two
    in frost, fog or snow); Greymouth, out on the open coast, a degree down in wind and rain; Pellow Harbour,
    tucked in under Carrow Point, a degree up in the sun."""
    return {"harbour": temp_c,
            "polgrey": temp_c - (2 if state in ("snow", "fog") or temp_c <= 3 else 1),
            "greymouth": temp_c - (1 if state in ("wind", "storm", "rain") else 0),
            "pellow_harbour": temp_c + (1 if state == "sunny" else 0)}


def for_prompt() -> str:
    """The spots, for Gordon, in words that can't disagree with the map behind him. Given the rules and asked for
    figures, Haiku named a spot in all six forecasts of a trial and got one wrong (Greymouth "a degree colder, at
    ten" on a sunny day, with eleven on the map: 2026-11-21). So no figure but Port Wexley's, and one place at most."""
    return ("THE WEATHER MAP behind Gordon shows Port Wexley's temperature (temp_c) and three more worked out from "
            "it: Polgrey, up the estuary; Greymouth, on the open coast to the west; Pellow Harbour, along the coast "
            "to the east. Now and then, not in every forecast, Gordon may point to ONE of them, in these words and "
            "no figure: Polgrey is \"a degree or two colder\" than the town, always; Greymouth is \"a degree down\" "
            "only in wind, rain or a storm; Pellow Harbour is \"a degree up\" only when it is sunny. Otherwise he "
            "leaves them to the map. The only temperature he gives in figures is Port Wexley's.")


WINDOW = (X0, X1, Y1)                  # the weather's window; the travel board and the route map have their own


def _at(xy: tuple[float, float], w: int, win: tuple[float, float, float] = WINDOW) -> tuple[int, int]:
    x0, x1, y1 = win
    k = w / (x1 - x0)
    return round((xy[0] - x0) * k), round((y1 - xy[1]) * k)


_base: dict = {}


def base(size: tuple[int, int], win: tuple[float, float, float] = WINDOW):
    """The map with no weather on it: land, the sea and the estuary, the river and the town. `win` is the
    window on it (miles: west edge, east edge, north edge); each is drawn once and kept. Copy it to draw on."""
    import pygame

    if (size, win) not in _base:
        w, h = size
        at = lambda p: _at(p, w, win)  # noqa: E731
        s = pygame.Surface(size)
        s.fill(LAND)
        for i in range(0, w, 3):                                    # the moor, a shade darker up the top
            for j in range(0, h // 3, 3):
                if (i * 7 + j * 13) % 5 == 0:
                    s.set_at((i, j), LAND_HIGH)
        sea = [at(p) for p in g.SHORE] + [at((g.SHORE[-1][0], -40)), at((g.SHORE[0][0], -40))]
        pygame.draw.polygon(s, SEA, sea)
        deep = at((0, -6.2))[1]                                     # open water, a shade darker off the coast
        for j in range(max(0, deep), h):
            for i in range(w):
                if s.get_at((i, j))[:3] == SEA and (i + j * 2) % 4:
                    s.set_at((i, j), SEA_DEEP)
        pygame.draw.lines(s, SHORE_LINE, False, [at(p) for p in g.SHORE], 1)
        pygame.draw.lines(s, SEA, False, [at(p) for p in g.RIVER], 1)
        pygame.draw.circle(s, TOWN, at(g.BY_ID["main_street"].xy), max(3, round(0.42 * w / (win[1] - win[0]))))
        _base[size, win] = s
    return _base[size, win]


def _cloud(s, x: int, y: int, c) -> None:
    import pygame
    pygame.draw.ellipse(s, c, (x, y + 2, 11, 5))
    pygame.draw.ellipse(s, c, (x + 2, y, 6, 5))


def icon(s, state: str | None, x: int, y: int, t: float) -> None:
    """The sky at one spot, 11 by 10 with its top left at (x, y)."""
    import pygame

    beat = int(t * 3)
    if state is None:                          # before the day's first forecast: the places, and no sky yet
        return
    if state == "sunny":
        pygame.draw.circle(s, (255, 226, 110), (x + 5, y + 5), 3)
        for i in range(8):
            a = i * math.pi / 4 + (0.4 if beat % 2 else 0.0)
            s.set_at((x + 5 + round(math.cos(a) * 5), y + 5 + round(math.sin(a) * 5)), (255, 240, 170))
    elif state == "fog":
        for j, (dx, n) in enumerate(((1, 8), (0, 10), (2, 8), (0, 9))):
            pygame.draw.line(s, (226, 228, 232), (x + dx, y + 1 + j * 2), (x + dx + n, y + 1 + j * 2))
    elif state == "wind":
        for j, n in enumerate((7, 10, 6)):
            ox = (beat + j) % 3
            pygame.draw.line(s, (238, 242, 248), (x + ox, y + 2 + j * 3), (x + ox + n - 3, y + 2 + j * 3))
            s.set_at((x + ox + n - 2, y + 1 + j * 3), (238, 242, 248))
    else:
        dark = state in ("storm", "rain")
        _cloud(s, x, y, (120, 126, 140) if state == "storm" else (188, 194, 204) if dark else (236, 238, 242))
        if state == "rain":
            for i in range(3):
                dy = (beat + i) % 3
                pygame.draw.line(s, (170, 205, 245), (x + 2 + i * 3, y + 7 + dy), (x + 2 + i * 3, y + 8 + dy))
        elif state == "snow":
            for i in range(3):
                s.set_at((x + 2 + i * 3 + (beat + i) % 2, y + 8 + (beat + i) % 2), (255, 255, 255))
        elif state == "storm":
            for px in ((5, 6), (4, 7), (5, 8), (4, 9)) if beat % 4 else ((5, 6), (4, 7), (6, 7), (5, 8), (4, 9), (3, 10)):
                s.set_at((x + px[0], y + px[1]), (255, 232, 90))


def _sky(s, state: str | None, t: float) -> None:
    """What moves over the whole map: rain and snow falling, cloud and fog drifting, the wind's streaks."""
    import pygame

    w, h = s.get_size()
    if state in ("rain", "storm"):
        for i in range(22 if state == "storm" else 14):
            x = (i * 37 + int(t * 60)) % w
            y = (i * 53 + int(t * 150)) % h
            pygame.draw.line(s, (200, 214, 238), (x, y), (x - 1, y + 3))
    elif state == "snow":
        for i in range(26):
            x = (i * 29 + int(math.sin(t * 0.8 + i) * 3)) % w
            y = (i * 47 + int(t * 14)) % h
            s.set_at((x, y), (250, 250, 255))
    elif state == "wind":
        for i in range(7):
            x = (i * 61 + int(t * 90)) % (w + 30) - 30
            y = 8 + (i * 31) % (h - 30)
            pygame.draw.line(s, (232, 238, 246), (x, y), (x + 12 + i % 3 * 4, y))
    if state in ("cloudy", "fog", "storm"):
        veil = pygame.Surface((w, h), pygame.SRCALPHA)
        c = (60, 64, 80, 70) if state == "storm" else (230, 232, 236, 80 if state == "fog" else 60)
        for i in range(5 if state == "fog" else 3):
            x = (i * 67 + int(t * (3 if state == "fog" else 6))) % (w + 60) - 60
            pygame.draw.ellipse(veil, c, (x, 6 + i * (h // 6), 70 if state == "fog" else 54, 12 if state == "fog" else 16))
        s.blit(veil, (0, 0))


def draw(canvas, rect, state: str | None, temp_c: int | None, t: float, text, measure) -> None:
    """The map on the wall's screen at `rect` (x, y, w, h on the canvas), with the sky over it and each spot's
    name and temperature. `text(canvas, s, x, y, size, colour)` and `measure(s, size)` are scenes.py's."""
    import pygame

    x0, y0, w, h = rect
    s = base((w, h)).copy()
    if state in DIM:
        shade = pygame.Surface((w, h))
        shade.fill(tuple(round(255 * DIM[state]) for _ in range(3)))
        s.blit(shade, (0, 0), special_flags=pygame.BLEND_MULT)
    _sky(s, state, t)
    temps = spots(temp_c, state) if temp_c is not None else {}
    labels = []
    for pid, name, dx, dy, end in SPOTS:
        px, py = _at(g.BY_ID["main_street" if pid == "harbour" else pid].xy, w)
        said = f"{name} {temps[pid]}°" if pid in temps else name
        tw, th = measure(said, 8)
        lx = px + dx - (tw + 15 if end else 0)
        ly = py + dy
        pygame.draw.rect(s, PLATE, (lx - 2, ly - 1, tw + 16, max(th, 10) + 2))
        icon(s, state, lx + tw + 2, ly, t)
        pygame.draw.rect(s, PLATE, (px - 2, py - 2, 5, 5))
        pygame.draw.rect(s, NAME, (px - 1, py - 1, 3, 3))
        labels.append((said, name, x0 + lx, y0 + ly))
    canvas.blit(s, (x0, y0))
    for said, name, lx, ly in labels:
        r = text(canvas, name, lx, ly, 8, NAME)
        if said != name:
            text(canvas, said[len(name):], r.right, ly, 8, TEMP)
