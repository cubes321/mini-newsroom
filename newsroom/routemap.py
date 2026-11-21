"""A journey on the town's map: an inset with the whole route, tonight's leg picked out, and where she is going.

For The Coast Road (entertainment/travelogue.py): the route its planner wrote is already kept to the gazetteer
(geography.check_legs), so its stops have places, and the same coast the weather map uses (weathermap.py) shows
them. Nothing is guessed: a stop the gazetteer can't place is left off the line.
"""
from __future__ import annotations

from . import geography as g, weathermap as wm

MARGIN, MIN_MILES = 1.3, 10.0          # round the route's stops, and the least the map is across
RECT = (200, 18, 112, 78)              # on the canvas: top right, under the clock, clear of her and the lower third
CAPTION_H = 11

FRAME, CAPTION = (20, 22, 34), (20, 22, 34)
WHOLE, TONIGHT, DOT, NEXT_RING = (206, 198, 170), (255, 214, 70), (250, 250, 250), (250, 250, 250)


def legs_of(route_legs: list[dict]) -> list[list[str | None]]:
    """Each leg's stops as gazetteer ids, in order; None for one the map can't place (it keeps its number)."""
    return [[g.place_for(st.get("place", ""), st.get("backdrop", ""), st.get("where", "")) for st in leg["stops"]]
            for leg in route_legs]


def window_for(legs: list[list[str | None]], aspect: float) -> tuple[float, float, float]:
    """The window on the map that holds every stop with a margin, for a map `aspect` high for its width: the
    weather's whole coast when nothing is placed."""
    pts = [g.BY_ID[pid].xy for leg in legs for pid in leg if pid in g.BY_ID]
    if not pts:
        return wm.WINDOW
    xs, ys = [p[0] for p in pts], [p[1] for p in pts]
    wide = max(MIN_MILES, max(xs) - min(xs) + 2 * MARGIN, (max(ys) - min(ys) + 2 * MARGIN) / aspect)
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    return round(cx - wide / 2, 2), round(cx + wide / 2, 2), round(cy + wide * aspect / 2, 2)


def draw(canvas, rect, legs: list[list[str | None]], n: int, to: int | None, t: float, text, caption: str) -> None:
    """The inset at `rect`: every leg in a pale line, leg `n` (from 1) in yellow with a dot at each stop, and
    stop `to` (from 0) of it ringed and blinking when she is on her way there. `text` is scenes.py's."""
    import pygame

    x0, y0, w, h = rect
    mh = h - CAPTION_H
    s = pygame.Surface((w, h))
    s.fill(CAPTION)
    win = window_for(legs, mh / w)
    s.blit(wm.base((w, mh), win), (0, 0))
    at = lambda pid: wm._at(g.BY_ID[pid].xy, w, win) if pid in g.BY_ID else None  # noqa: E731
    whole = [p for leg in legs for pid in leg if (p := at(pid))]
    if len(whole) > 1:
        pygame.draw.lines(s, FRAME, False, whole, 3)
        pygame.draw.lines(s, WHOLE, False, whole, 1)
    mine = [at(pid) for pid in legs[n - 1]] if 0 < n <= len(legs) else []
    before = at(legs[n - 2][-1]) if n > 1 and legs[n - 2] else None
    line = [p for p in ([before] + mine) if p]          # tonight's leg starts where the last one ended
    if len(line) > 1:
        pygame.draw.lines(s, TONIGHT, False, line, 2)
    for i, p in enumerate(mine):
        if not p:
            continue
        px, py = p
        pygame.draw.rect(s, FRAME, (px - 2, py - 2, 5, 5))
        pygame.draw.rect(s, TONIGHT if i != to else DOT, (px - 1, py - 1, 3, 3))
    if to is not None and 0 <= to < len(mine) and mine[to] and int(t * 2) % 2 == 0:
        pygame.draw.circle(s, NEXT_RING, mine[to], 5, 1)
    pygame.draw.rect(s, FRAME, (0, 0, w, h), 1)
    canvas.blit(s, (x0, y0))
    text(canvas, caption, x0 + w // 2, y0 + h - CAPTION_H // 2 - 1, 8, (240, 240, 240), center=True, maxw=w - 4)
