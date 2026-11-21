"""The travel board: the wall's screen while a presenter reads the travel (Have Your Say's travel link).

The estuary close up, from the town's map (geography.py, on weathermap.py's coast): the coast bus's road round
by Polgrey, the foot ferry's crossing, and the day's tides. Every word on it comes from code (tides.py for the
ferry and the water, geography.py for the bus), the same facts the script is given, so the board and the
presenter can't disagree and nothing on it is made up.
"""
from __future__ import annotations

from datetime import datetime

from . import geography as g, tides, weathermap as wm

WINDOW = (-6.5, 8.0, 4.9)             # miles: Saltby sands to Carrow Point, Polgrey at the top
BRIEF = "the travel"                  # a running order's item that starts so is the travel (schedule.py)

BUS, BUS_STOP, FERRY_C, OFF = (238, 200, 64), (255, 236, 150), (250, 250, 250), (232, 70, 60)
PLATE, WORD, FIGURE, GOOD = (20, 22, 34), (240, 240, 240), (255, 222, 110), (130, 220, 140)
NAMED = (("saltby", "Saltby", -34, -11), ("polgrey", "Polgrey", 6, 0), ("main_street", "Port Wexley", 6, -10))


def is_travel(brief: str | None) -> bool:
    return (brief or "").strip().lower().startswith(BRIEF)


def facts(now: datetime, map_state: str | None) -> dict:
    """What the board says, from tides.py: the ferry (running, its gaps, its last boat, or why it is off) and the
    next high and low water from `now` (the day's last of each once both have gone)."""
    f = tides.ferry(now.date(), map_state)
    tt = tides.tides(now.date())

    def water(kind: str):
        mine = [(t, h) for t, k, h in tt if k == kind]
        return next(((t, h) for t, h in mine if t >= now), mine[-1] if mine else None)
    left = [s for s in f["sailings"] if s >= now]
    gap = next(((a, b) for a, b in f["gaps"] if b >= now), None)
    return {"off": f["suspended"], "last": f["sailings"][-1] if f["sailings"] else None, "running": bool(left),
            "gap": gap, "high": water("high"), "low": water("low")}


def lines(now: datetime, map_state: str | None) -> list[tuple[str, str, tuple]]:
    """The board's three rows: (what, the words, the colour of the words)."""
    k = facts(now, map_state)
    if k["off"]:
        ferry = ("off: " + (map_state or "the weather"), OFF)
    elif not k["running"]:
        ferry = ("finished for today", OFF)
    elif k["gap"] and k["gap"][0] <= now:
        ferry = (f"none till {k['gap'][1]:%H:%M}, low water", OFF)
    elif k["gap"]:
        ferry = (f"none {k['gap'][0]:%H:%M}-{k['gap'][1]:%H:%M}, last {k['last']:%H:%M}", FIGURE)
    else:
        ferry = (f"every 30 min, last {k['last']:%H:%M}", GOOD)
    water = "  ".join(f"{name} {v[0]:%H:%M} {v[1]:.1f}m" for name, v in (("high", k["high"]), ("low", k["low"])) if v)
    return [("FERRY", *ferry), ("BUS", f"hourly, round by Polgrey", GOOD), ("TIDE", water or "no times today", FIGURE)]


def draw(canvas, rect, now: datetime, map_state: str | None, t: float, text, measure) -> None:
    """The board on the wall's screen at `rect`: the map, the bus's road, the ferry's crossing, and the three
    rows down the left. `text` and `measure` are scenes.py's."""
    import pygame

    x0, y0, w, h = rect
    s = wm.base((w, h), WINDOW).copy()
    at = lambda pid: wm._at(g.BY_ID[pid].xy, w, WINDOW)  # noqa: E731
    road = [at(pid) for pid in g.BUS_ROUTE]
    pygame.draw.lines(s, PLATE, False, road, 3)
    pygame.draw.lines(s, BUS, False, road, 1)
    for pid in g.BUS_ROUTE:
        px, py = at(pid)
        if 0 <= px < w and 0 <= py < h:
            pygame.draw.rect(s, PLATE, (px - 2, py - 2, 5, 5))
            pygame.draw.rect(s, BUS_STOP, (px - 1, py - 1, 3, 3))
    k = facts(now, map_state)
    a, b = at(g.FERRY[0]), at(g.FERRY[1])
    going = not k["off"] and k["running"] and not (k["gap"] and k["gap"][0] <= now)
    steps = max(abs(a[0] - b[0]), abs(a[1] - b[1]))
    for i in range(steps + 1):                                     # the crossing, dashed; the dashes run when it does
        if (i + (int(t * 4) if going else 0)) % 4 < 2:
            pygame.draw.rect(s, FERRY_C if going else OFF,
                             (round(a[0] + (b[0] - a[0]) * i / steps), round(a[1] + (b[1] - a[1]) * i / steps), 2, 2))
    labels = []
    for pid, name, dx, dy in NAMED:
        px, py = at(pid)
        tw, th = measure(name, 8)
        pygame.draw.rect(s, PLATE, (px + dx - 2, py + dy - 1, tw + 4, max(th, 10) + 1))
        labels.append((name, x0 + px + dx, y0 + py + dy, WORD))
    rows = lines(now, map_state)
    keyw = max(measure(what, 8)[0] for what, _, _ in rows)
    wide = max(measure(said, 8)[0] for _, said, _ in rows)
    bx, by = 3, h - 12 - len(rows) * 11 - 5            # bottom left, above the rows the lower third hides
    pygame.draw.rect(s, PLATE, (bx, by, keyw + wide + 11, len(rows) * 11 + 3))
    for i, (what, said, colour) in enumerate(rows):
        labels.append((what, x0 + bx + 3, y0 + by + 2 + i * 11, FIGURE if what != "FERRY" or going else OFF))
        labels.append((said, x0 + bx + keyw + 8, y0 + by + 2 + i * 11, colour))
    canvas.blit(s, (x0, y0))
    for said, lx, ly, colour in labels:
        text(canvas, said, lx, ly, 8, colour)
