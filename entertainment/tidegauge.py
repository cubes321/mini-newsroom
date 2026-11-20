"""High Water's tide gauge: the twelve steps, the climbers, the water and the life rings, drawn in code on the set.

As Wexley Wits' scoreboard is (wits.draw_board, quiz.view): the writer's after-hook ties each change to the line of
Des's that makes it (`after`), the player's view hook sets the gauge for the line on air (`view`), and the set's
dressing draws it (`draw`), behind the people, so a close shot zooms it with them.

- **A step** moves on Des's verdict: his next line after the climber answers the question he asked. A turn with no
  question (making fast, sitting out) shows with the next change.
- **The tide** comes in on his line about it after the last turn: the first to name the tide, a wave or the gauge,
  else the round's last line of his. Never before the last turn.
- **A life ring** is won on his verdict in the Harbourmaster's round; **the star prize** on the spring tide's.
- Nothing ever runs ahead of him: a line that can't be placed shows late, and the item's last line always puts the
  gauge right. Every item has a state from its brief alone (`for_brief`), so the gauge is never empty on its set.

The whole gauge is code, opaque, inside RECT: the set's art leaves that patch of wall clear (the user, 2026-11-20).
"""
from __future__ import annotations

import math
import re

from . import highwater as hw, highwater_show as hs

# On the 320x180 canvas, between Des (mark x 70) and the first climber (x 186): inside Des's close shot, which crops
# 160x90 round his mark (scenes.draw_interview), so it moves where he is seen moving it.
RECT = (97, 66, 56, 94)               # x, y, w, h: everything the gauge draws, the set's art kept clear behind it
STEP_H = 6
BASE_Y = 152                          # the bottom of step 1
BOARD_X, BOARD_W = 106, 19            # the white board
CHIP_X = (128, 138)                   # each climber's marker, by seat
TAG_X = 99                            # the prize tags, left of the board
STAR_Y = 69

INK = (24, 26, 34)
FACE = (236, 234, 224)
FRAME = (52, 56, 66)
GOLD, GOLD_DK = (240, 196, 70), (170, 120, 30)
WATER, FOAM = (40, 110, 160), (190, 226, 240)
RING_RED, RING_WHITE = (214, 48, 52), (246, 244, 236)
SEAT_COLS = ((236, 120, 40), (40, 160, 170))   # each seat's marker: orange, teal (not their clothes: two
                                               # climbers can wear the same colour)

_DIGITS = {"0": "111101101101111", "1": "010110010010111", "2": "111001111100111", "3": "111001111001111",
           "4": "101101111001001", "5": "111100111001111", "6": "111100111101111", "7": "111001001010010",
           "8": "111101111101111", "9": "111101111001111",
           "A": "010101111101101", "B": "110101110101110", "C": "011100100100011", "D": "110101101101110",
           "E": "111100110100111", "F": "111100110100100", "G": "011100101101011", "H": "101101111101101",
           "I": "111010010010111", "J": "001001001101010", "K": "101101110101101", "L": "100100100100111",
           "M": "101111111101101", "N": "110101101101101", "O": "010101101101010", "P": "110101110100100",
           "Q": "010101101110011", "R": "110101110101101", "S": "011100010001110", "T": "111010010010010",
           "U": "101101101101111", "V": "101101101101010", "W": "101101111111101", "X": "101101010101101",
           "Y": "101101010010010", "Z": "111001010100111"}
_TIDE_WORDS = ("tide", "wave", "gauge")
_WET_WORDS = ("water", "sea", "splash", "soak", "wet")


# ------------------------------------------------------------------ the state, from the game

def _state(pos, tide, rings=(0, 0), banked=(0, 0), star=None) -> dict:
    return {"pos": list(pos), "tide": tide, "rings": list(rings), "banked": list(banked), "star": star}


def _names(k: dict) -> list[str]:
    return [c["name"] for c in k["climbers"]]


def start(k: dict) -> dict:
    return _state((hw.START, hw.START), hw.TIDE_START)


def after_round(k: dict, n: int) -> dict:
    """Where everyone stands after round n (0-based) and its tide."""
    r = k["game"]["rounds"][n]
    by = {a["who"]: a for a in r["after"]}
    names = _names(k)
    return _state([by[x]["step"] for x in names], r["tide"], [by[x].get("rings", 0) for x in names],
                  [by[x]["banked"] for x in names])


def before_round(k: dict, n: int) -> dict:
    if n == 0:
        return start(k)
    s = after_round(k, n - 1)
    if n == hw.HARBOUR_AFTER and k["game"].get("harbour"):        # the Harbourmaster's rings, won since
        held = k["game"]["harbour"]["rings"]
        s["rings"] = [held.get(x, 0) for x in _names(k)]
    return s


def end(k: dict, star: bool = False) -> dict:
    s = after_round(k, hw.ROUNDS - 1)
    sp = k["game"]["spring"]
    if star and sp["won"]:
        s["star"] = _names(k).index(sp["who"])
    return s


def for_brief(k: dict, brief: str) -> dict:
    """The gauge as an item starts, from its brief alone: before its round, or where the game stands at that point."""
    brief = brief or ""
    if m := re.search(r"\{r([1-4])\}", brief):
        return before_round(k, int(m.group(1)) - 1)
    if "{hm}" in brief:
        return after_round(k, hw.HARBOUR_AFTER - 1)
    if "{close}" in brief:
        return end(k, star=True)
    if "{spring}" in brief or "{chat" in brief or "{sofar}" in brief:      # every chat comes after the rounds
        return end(k)
    return start(k)


# ------------------------------------------------------------------ the state, line by line

def _verdict(lines, asked: int, after: int) -> int | None:
    """Des's verdict on a question asked at line `asked`: his first line after someone answers it."""
    answered = False
    for i in range(max(asked + 1, after), len(lines)):
        sp = getattr(lines[i], "speaker", "")
        if sp == "guest":
            answered = True
        elif sp == hs.HOST and answered:
            return i
    return None


def _host_lines(lines) -> list[int]:
    return [i for i, l in enumerate(lines) if getattr(l, "speaker", "") == hs.HOST]


def _tide_line(lines, after: int) -> int | None:
    hosts = [i for i in _host_lines(lines) if i >= after]
    for words in (_TIDE_WORDS, _WET_WORDS):
        for i in hosts:
            if any(w in (lines[i].text or "").lower() for w in words):
                return i
    return hosts[-1] if hosts else None


def changes(k: dict, brief: str, lines) -> list[tuple[int, dict, object]]:
    """[(line, state, lit)] for one item: the gauge after each change, on the line of Des's that makes it. `lit` is the
    seat that just moved, "tide", "ring:<seat>" or "star". The lines never go backwards, and the last state is the
    game's own at the end of the item."""
    brief = brief or ""
    names = _names(k)
    s = for_brief(k, brief)
    out: list[tuple[int, dict, object]] = []
    cursor = 0

    def emit(i: int, lit) -> None:
        nonlocal cursor
        out.append((i, {**s, "pos": list(s["pos"]), "rings": list(s["rings"]), "banked": list(s["banked"])}, lit))
        cursor = i + 1

    def asked(qs: list[dict]) -> list[int | None]:
        return hs.asked_at(lines, qs)

    if m := re.search(r"\{r([1-4])\}", brief):
        n = int(m.group(1)) - 1
        r = k["game"]["rounds"][n]
        turns = r["turns"]
        at = iter(asked([t["question"] for t in turns if "question" in t]))
        placed, trailing = True, 0          # every question turn placed; turns with no question since the last one
        for t in turns:
            seat = names.index(t["who"])
            line = None
            if "question" in t:
                a = next(at)
                if a is not None and a >= cursor:
                    line = _verdict(lines, a, cursor)
                placed, trailing = placed and line is not None, 0
            else:
                trailing += 1
            s["pos"][seat], s["banked"][seat] = t["to"], t["banked"]
            if line is not None:
                emit(line, seat)
        # The tide after the last turn: a turn that couldn't be placed might come after any line, so then it waits
        # for Des's last line; a last turn or two with no question (making fast) has a line of his each first.
        hosts = [i for i in _host_lines(lines) if i >= cursor]
        tide_at = (_tide_line(lines, hosts[trailing] if trailing < len(hosts) else len(lines)) if placed
                   else (hosts[-1] if hosts else None))
        s.update(after_round(k, n))
        if tide_at is not None:
            emit(tide_at, "tide")
    elif "{hm}" in brief:
        rows = k["game"]["harbour"]["questions"]
        for row, a in zip(rows, asked([x["question"] for x in rows])):
            if not row["ring"]:
                continue
            s["rings"][names.index(row["ring"])] += 1
            line = _verdict(lines, a, cursor) if a is not None and a >= cursor else None
            if line is not None:
                emit(line, f"ring:{names.index(row['ring'])}")
        held = k["game"]["harbour"]["rings"]
        s["rings"] = [held.get(x, 0) for x in names]
    elif "{spring}" in brief:
        sp = k["game"]["spring"]
        rights = 0
        for ok, a in zip(sp["answers"], asked(sp["questions"])):
            rights += bool(ok)
            line = _verdict(lines, a, cursor) if a is not None and a >= cursor else None
            if line is not None:
                cursor = line + 1
            if ok and rights == hw.SPRING_NEEDED:
                s["star"] = names.index(sp["who"])
                if line is not None:
                    emit(line, "star")
                break
        s.update(end(k, star=True))
    last = len(lines) - 1
    if last >= 0 and (not out or out[-1][1] != s):              # the item's last line puts the gauge right
        emit(max(last, out[-1][0] if out else 0), None)
    return out


def after(seg, world) -> None:
    """writers.AFTER_HOOKS: tie the gauge's changes to Des's lines, for the set (view, draw)."""
    seg.work.pop("gauge", None)
    k = hs.tonight(world)
    if not k:
        return
    try:
        steps = changes(k, seg.brief or "", seg.lines or [])
        seg.work["gauge"] = {"names": _names(k), "start": for_brief(k, seg.brief or ""),
                             "steps": [[i, st, lit] for i, st, lit in steps]}
    except (KeyError, IndexError, TypeError, ValueError):
        hs.log.exception("tide gauge: no changes for %r", seg.brief)


def view(seg, v, line_idx: int) -> None:
    """player.VIEW_HOOKS: the gauge at this line; what just changed, lit on the line that changes it."""
    g = seg.work.get("gauge")
    if not g:
        return
    now, lit = g["start"], None
    for i, st, what in g["steps"]:
        if i <= line_idx:
            now, lit = st, (what if i == line_idx else None)
    v.scene = {"gauge": now, "names": g["names"], "lit": lit}


# ------------------------------------------------------------------ the drawing

def _digits(canvas, s: str, right: int, y: int, col) -> None:
    x = right - (len(s) * 4 - 1)
    for ch in s:
        bits = _DIGITS[ch]
        for j in range(5):
            for i in range(3):
                if bits[j * 3 + i] == "1":
                    canvas.set_at((x + i, y + j), col)
        x += 4


def _row_top(step: int) -> int:
    return BASE_Y - step * STEP_H


def _star(canvas, cx: int, cy: int, col, rim) -> None:
    import pygame
    pts = []
    for i in range(10):
        r = 5.5 if i % 2 == 0 else 2.4
        a = -math.pi / 2 + i * math.pi / 5
        pts.append((cx + r * math.cos(a), cy + r * math.sin(a)))
    pygame.draw.polygon(canvas, col, pts)
    pygame.draw.polygon(canvas, rim, pts, 1)


def _ring(canvas, x: int, y: int) -> None:
    """A life ring, 5x5: red and white quarters round a hole."""
    for (dx, dy) in ((1, 0), (2, 0), (3, 0), (0, 1), (4, 1), (0, 2), (4, 2), (0, 3), (4, 3), (1, 4), (2, 4), (3, 4)):
        canvas.set_at((x + dx, y + dy), RING_RED if (dx + dy) % 3 else RING_WHITE)


def draw(canvas, v, t: float) -> None:
    """scenes.DRESSINGS: the gauge, in pixels on the set, behind the people."""
    import pygame

    sc = getattr(v, "scene", None) or {}
    g = sc.get("gauge")
    if not g:
        return
    lit = sc.get("lit")
    flash = int(t * 4) % 2 == 0
    names = sc.get("names") or ["", ""]
    top = _row_top(hw.STEPS)
    # The post and the board's frame, the star prize's plaque on top.
    canvas.fill(FRAME, (BOARD_X + 6, BASE_Y, 5, 6))
    canvas.fill(FRAME, (BOARD_X - 1, top - 1, BOARD_W + 2, BASE_Y - top + 2))
    canvas.fill(FACE, (BOARD_X, top, BOARD_W, BASE_Y - top))
    canvas.fill(FRAME, (BOARD_X - 3, STAR_Y - 2, CHIP_X[1] + 12 - BOARD_X, top - STAR_Y + 1))   # room for a winner
    star_lit = lit == "star" and flash
    _star(canvas, BOARD_X + BOARD_W // 2, STAR_Y + 4, (255, 248, 200) if star_lit else GOLD, GOLD_DK)
    # Each step: its number, a tick on the board's spine, a longer one every other step; a prize step's tick in gold,
    # its tag beside the board.
    spine = BOARD_X + 10
    canvas.fill(INK, (spine, top, 1, BASE_Y - top))
    for s in range(1, hw.STEPS + 1):
        y = _row_top(s)
        prize = s in hw.PRIZE_STEPS
        _digits(canvas, str(s), BOARD_X + 8, y + 1, GOLD_DK if prize else INK)
        canvas.fill(GOLD_DK if prize else INK, (spine, y, (BOARD_W - 10) if s % 2 == 0 or prize else 5, 1 + prize))
        if prize:
            canvas.fill(GOLD_DK, (TAG_X, y, 6, 5))
            canvas.fill(GOLD, (TAG_X + 1, y + 1, 4, 3))
            for seat, b in enumerate(g["banked"]):          # made fast here: a knot of rope in that climber's colour
                if b == s:
                    canvas.fill(SEAT_COLS[seat], (TAG_X + 1 + 2 * seat, y + 1, 2, 3))
    # The water: up to the tide's step, over the board, a lighter line of foam on top that moves.
    tide_y = _row_top(g["tide"]) if g["tide"] >= 1 else BASE_Y + 2 + min(4, -g["tide"] * 2)
    x0, x1 = BOARD_X - 1, BOARD_X + BOARD_W + 1
    if tide_y < BASE_Y + 6:
        water = pygame.Surface((x1 - x0, BASE_Y + 6 - tide_y), pygame.SRCALPHA)
        water.fill((*WATER, 170))
        canvas.blit(water, (x0, tide_y))
        foam = (255, 255, 255) if lit == "tide" and flash else FOAM
        for x in range(x0, x1):
            canvas.set_at((x, tide_y + (1 if math.sin(x * 0.7 + t * 3) > 0.3 else 0)), foam)
    # The climbers: a marker each by their step, with their initial (on the plaque when the star is won), and a life
    # ring beside its holder.
    for seat, step in enumerate(g["pos"]):
        x = CHIP_X[seat]
        y = STAR_Y - 1 if g.get("star") == seat else _row_top(step) - 1
        rim = (255, 255, 255) if lit in (seat, "star") and flash and (lit == seat or g.get("star") == seat) else INK
        canvas.fill(rim, (x, y, 7, 7))
        canvas.fill(SEAT_COLS[seat], (x + 1, y + 1, 5, 5))
        canvas.set_at((x - 1, y + 3), rim)                   # pointing at the board
        initial = (names[seat] or "?")[:1].upper()
        if initial in _DIGITS:
            _digits(canvas, initial, x + 5, y + 1, (255, 255, 255))
        if g["rings"][seat] and not (lit == f"ring:{seat}" and not flash):
            _ring(canvas, x + 8, y + 1)
