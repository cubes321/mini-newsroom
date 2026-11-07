"""Wexley Wits' darts round: every dart thrown in code, on a real board's geometry, and shown in a window.

Each contestant throws three darts at treble twenty. Where a dart lands is a seeded draw around that
aim, wider for a weaker pub (darts.PUBS's strength; a captain a touch steadier), so a pub night's
scatter of twenties, ones and fives, the odd treble and the odd bounce off the wire. The board's
rings and segments then say what it scored, so every dart has a place and a score, and Clive's call
("Treble twenty!") is the board's, not the model's.

On air, the window at the top left of the set is the board, drawn once and kept, with the thrower's
darts going in as Clive calls them: each dart is tied to the line that calls it (`calls_in`), and a
script whose calls can't all be found in order is not used (the code's own round stands in).
"""
from __future__ import annotations

import math
import random
import re

import pygame

PER_PLAYER = 3
AIM = (0.0, 103.0)                   # treble twenty, in mm from the bull (y up)
SPREAD_MM = 30.0                     # a pub regular of strength 1.0
CAPTAIN = 1.05                       # the captain is a little steadier
POINTS = 3                           # the darts round to the higher team total; level, one each
ORDER = (20, 1, 18, 4, 13, 6, 10, 15, 2, 17, 3, 19, 7, 16, 8, 11, 14, 9, 12, 5)   # clockwise from the top
BULL, OUTER_BULL, TREBLE_IN, TREBLE_OUT, DOUBLE_IN, DOUBLE_OUT = 6.35, 15.9, 99.0, 107.0, 162.0, 170.0

_ONES = ("zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen "
         "sixteen seventeen eighteen nineteen").split()
_TENS = ("", "", "twenty", "thirty", "forty", "fifty", "sixty", "seventy", "eighty", "ninety")


def words(n: int) -> str:
    """0 to 999 as said: "sixty-six", "one hundred and twelve"."""
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + (f"-{_ONES[n % 10]}" if n % 10 else "")
    return f"{_ONES[n // 100]} hundred" + (f" and {words(n % 100)}" if n % 100 else "")


def score_at(x: float, y: float) -> tuple[int, str]:
    """(points, Clive's call) for a dart at (x, y) mm from the bull, y up."""
    r = math.hypot(x, y)
    if r <= BULL:
        return 50, "Bullseye!"
    if r <= OUTER_BULL:
        return 25, "Twenty-five."
    if r > DOUBLE_OUT:
        return 0, "Off the board!"
    angle = (math.degrees(math.atan2(x, y)) + 360) % 360          # 0 at the top, clockwise
    n = ORDER[int(((angle + 9) % 360) // 18)]
    if TREBLE_IN <= r <= TREBLE_OUT:
        return 3 * n, f"Treble {words(n)}!"
    if r >= DOUBLE_IN:
        return 2 * n, f"Double {words(n)}!"
    return n, f"{words(n).capitalize()}."


def mark(points: int, call: str) -> str:
    """The dart in darts shorthand, for the window: T20, D16, 20, 25, BULL, MISS."""
    if points == 0:
        return "MISS"
    if points == 50:
        return "BULL"
    if call.startswith("Treble"):
        return f"T{points // 3}"
    if call.startswith("Double"):
        return f"D{points // 2}"
    return str(points)


def play(rng: random.Random, teams: list[dict]) -> tuple[list[dict], list[int]]:
    """Every dart, captains first, the teams in turn: [{who, to, x, y, points, call}], and the team totals."""
    throws, totals = [], [0, 0]
    for k in range(2):
        for to, t in enumerate(teams):
            who = t["members"][k]
            spread = SPREAD_MM / (t["strength"] * (CAPTAIN if k == 0 else 1.0))
            for _ in range(PER_PLAYER):
                x, y = rng.gauss(AIM[0], spread), rng.gauss(AIM[1], spread)
                points, call = score_at(x, y)
                totals[to] += points
                throws.append({"who": who, "to": to, "x": round(x, 1), "y": round(y, 1), "points": points,
                               "call": call})
    return throws, totals


def brief(q: dict, r: dict, n: int, score: str) -> str:
    """Round n's brief: every dart in order with its call, the totals, and the score after."""
    rows = []
    for k in range(0, len(r["throws"]), PER_PLAYER):
        mine = r["throws"][k:k + PER_PLAYER]
        team = q["teams"][mine[0]["to"]]["name"].upper()
        rows.append(f"{mine[0]['who']} ({team}): " + ", ".join(f"\"{d['call']}\"" for d in mine)
                    + f" = {words(sum(d['points'] for d in mine))}")
    a, b = r["totals"]
    won = (f"so {q['teams'][0 if a > b else 1]['name']} take the darts round and {POINTS} points" if a != b
           else "level, so one point each")
    return (f"ROUND {n + 1}: THE DARTS ROUND, at the oche. Each contestant throws three darts at the board, the "
            f"throwers in this order or team by team. Clive names each thrower as they step up and calls EVERY dart in a line of his own that BEGINS with the call exactly as given (a word "
            f"after it is fine); before each player, a line to bring them up; a word from the thrower now and then. "
            f"At most 36 lines.\n" + "\n".join(rows)
            + f"\nTEAM TOTALS: {q['teams'][0]['name']} {words(a)}, {q['teams'][1]['name']} {words(b)}, {won}."
            + f"\nTHE SCORE AFTER ROUND {n + 1}, for Clive to read out: {score}.")


def _norm(s: str) -> list[str]:
    return re.sub(r"[^a-z ]", " ", s.lower().replace("-", " ")).split()


def calls_in(lines, throws: list[dict], caller: str = "mag_b") -> list[int] | None:
    """The line that calls each dart: Clive's line beginning with that dart's call ("Twenty." is not
    "Twenty-five."), for the thrower he last named, whose darts go in their order. The throwers may come in
    any order: on the scratch run (2026-11-07) Haiku took them team by team, not as booked. None if any
    dart's call is missing."""
    mine: dict[str, list[int]] = {}
    for k, t in enumerate(throws):
        mine.setdefault(t["who"], []).append(k)
    names = {who: (who.lower(), who.split()[0].lower()) for who in mine}
    done = {who: 0 for who in mine}
    found: list[int | None] = [None] * len(throws)
    current = None
    for i, line in enumerate(lines):
        if line.speaker != caller:
            continue
        if current is not None and done[current] < len(mine[current]):
            k = mine[current][done[current]]
            said, call = _norm(line.text), _norm(throws[k]["call"])
            if said[:len(call)] == call and (len(said) == len(call) or said[len(call)] not in _ONES[1:]):
                found[k], done[current] = i, done[current] + 1
                continue
        text = line.text.lower()
        at = {who: max(text.rfind(full), max((m.start() for m in re.finditer(rf"\b{re.escape(first)}\b", text)),
                                             default=-1))
              for who, (full, first) in names.items()}
        if max(at.values()) >= 0:
            current = max(at, key=at.get)          # the last thrower the line names is up
    return found if all(f is not None for f in found) else None


def overlay(seg, line_idx: int) -> dict | None:
    """The window at this line: the thrower whose darts have been called, their darts in so far, the
    running total; before the first call, the board and the first thrower."""
    darts = seg.work.get("darts")
    if not darts:
        return None
    called = [d for d in darts if d["line"] <= line_idx]
    who = called[-1]["who"] if called else darts[0]["who"]
    mine = [d for d in called if d["who"] == who]
    return {"who": who, "to": next(d["to"] for d in darts if d["who"] == who),
            "darts": [(d["x"], d["y"]) for d in mine], "total": sum(d["points"] for d in mine),
            "call": mark(mine[-1]["points"], mine[-1]["call"]) if mine else ""}


# ---------------------------------------------------------------- the window

BOX = pygame.Rect(6, 4, 100, 62)     # top left, above every head on the set (Clive's is at y 75)
BOARD_R = 24                         # px to the outside of the number ring
_SCALE = 22 / DOUBLE_OUT             # px per mm: the doubles' outer edge 22 px out
TEAM = ((90, 160, 240), (250, 200, 70))   # the home pair's flights, the away pair's
_board: pygame.Surface | None = None


def board() -> pygame.Surface:
    """The board, drawn once: black and cream singles, red and green doubles and trebles, the bulls,
    and the black number ring, pixel by pixel from the same geometry that scores the darts."""
    global _board
    if _board is None:
        d = 2 * BOARD_R + 1
        s = pygame.Surface((d, d), pygame.SRCALPHA)
        for py in range(d):
            for px in range(d):
                x, y = (px - BOARD_R) / _SCALE, (BOARD_R - py) / _SCALE
                r = math.hypot(x, y)
                if r > BOARD_R / _SCALE:
                    continue
                angle = (math.degrees(math.atan2(x, y)) + 360) % 360
                odd = int(((angle + 9) % 360) // 18) % 2
                if r <= BULL + 2:
                    c = (200, 30, 40)
                elif r <= OUTER_BULL + 2:
                    c = (30, 140, 60)
                elif r > DOUBLE_OUT:
                    c = (24, 22, 22)
                elif TREBLE_IN <= r <= TREBLE_OUT + 4 or r >= DOUBLE_IN - 4:
                    c = (30, 140, 60) if odd else (200, 30, 40)
                else:
                    c = (235, 222, 190) if odd else (30, 28, 28)
                s.set_at((px, py), c)
        pygame.draw.line(s, (240, 240, 240), (BOARD_R, 1), (BOARD_R, 2))       # the twenty at the top
        _board = s
    return _board


def draw(canvas: pygame.Surface, v) -> None:
    """The window: the thrower in their team's colour, the board with their darts in, the total so far."""
    from newsroom import scenes, schedule

    o = v.overlay
    box = BOX
    pygame.draw.rect(canvas, (20, 20, 30), box.inflate(4, 4))
    pygame.draw.rect(canvas, (26, 34, 56), box)
    pygame.draw.rect(canvas, schedule.get(v.show).colour, (box.x, box.y, box.w, 11))
    scenes.text(canvas, o["who"], box.centerx, box.y + 6, 8, center=True, maxw=box.w - 4)
    top = (box.x + 3, box.y + 13)
    canvas.blit(board(), top)
    cx, cy = top[0] + BOARD_R, top[1] + BOARD_R
    for x, y in o["darts"]:
        px, py = round(cx + x * _SCALE), round(cy - y * _SCALE)
        pygame.draw.line(canvas, (16, 16, 16), (px, py), (px + 3, py - 3), 2)     # the barrel
        pygame.draw.rect(canvas, (16, 16, 16), (px + 2, py - 7, 5, 5))           # the flight, outlined
        pygame.draw.rect(canvas, TEAM[o["to"]], (px + 3, py - 6, 3, 3))
        canvas.set_at((px, py), (255, 255, 255))                                 # the point
    right = (top[0] + 2 * BOARD_R + 1 + box.right) // 2
    scenes.text(canvas, "SCORED", right, box.y + 22, 8, (170, 180, 200), center=True)
    scenes.text(canvas, f"{o['total']}", right, box.y + 38, 16, TEAM[o["to"]], center=True)
    scenes.text(canvas, o["call"], right, box.y + 54, 8, center=True)
