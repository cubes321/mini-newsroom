"""The bestiary: the coast's creatures, drawn in code, for Channel 8's wildlife series (docs/FACTUAL.md).

Each creature is a small pixel sprite written as rows of letters (one letter a colour, "." nothing), facing right,
with a second frame or two for its idle movement: a heron's head going down, an oystercatcher probing, a seal
lifting its head. `draw` puts one on a canvas with (x, y) its bottom centre, like sprites.draw_character. Flocks (the
brent geese) and the starling murmuration are drawn by functions of their own.

`SPOTS` are the places on each backdrop where a creature may be, and `draw_hide` is the hide view: the composed
backdrop cropped round a spot and scaled up 2x (nearest neighbour, a long lens), the creature drawn at the same 2x
so its pixels match the backdrop's, letterboxed like the documentary.

    python -m entertainment.creatures --sheet out.png     # every creature, on its backdrop and in the hide
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

RGB = tuple[int, int, int]


@dataclass(frozen=True)
class Creature:
    id: str
    name: str
    palette: dict                      # letter -> RGB
    frames: tuple                      # each a tuple of rows; frame 0 is the rest pose
    beat: tuple = ((0, 3.0),)          # (frame, seconds) in turn, round and round
    home: tuple = ()                   # (backdrop, spot) it is shown at first
    edge: RGB | None = (34, 30, 30)    # the outline's colour, or None for none

    def frame_at(self, t: float, phase: float = 0.0) -> tuple:
        total = sum(s for _, s in self.beat)
        k = (t + phase) % total
        for f, s in self.beat:
            if k < s:
                return self.frames[f]
            k -= s
        return self.frames[0]


def _rows(art: str) -> tuple:
    rows = [r for r in art.strip("\n").split("\n")]
    w = max(len(r) for r in rows)
    return tuple(r.ljust(w, ".") for r in rows)


# ------------------------------------------------------------------ the sprites (facing right)

HERON = Creature(
    "heron", "grey heron",
    {"w": (226, 228, 226), "s": (186, 190, 194), "g": (140, 148, 158), "d": (92, 98, 110), "k": (28, 28, 34),
     "y": (222, 184, 70), "l": (150, 128, 92)},
    (_rows("""
........sww.....
......kkwwkyyyy.
....kk..sww.....
.........ww.....
........wk......
........ww......
.......wk.......
.....ggwwg......
...ggggswgg.....
..ddgggggggg....
.dddggggggg.....
dddddddgggg.....
..dddddddgs.....
....ddddgg......
.......l.l......
.......l.l......
.......l.l......
.......l..l.....
.......l..l.....
......ll..ll....
"""), _rows("""
................
................
................
................
................
................
........sww.....
......kkwwkyyyy.
....kk.wkw......
.....ggwwg......
...ggggswgg.....
..ddgggggggg....
.dddggggggg.....
dddddddgggg.....
..dddddddgs.....
....ddddgg......
.......l.l......
.......l.l......
.......l..l.....
......ll..ll....
""")),
    beat=((0, 4.0), (1, 2.0)),
    home=("estuary", "pool"),
)

EGRET = Creature(
    "egret", "little egret",
    {"w": (246, 246, 242), "s": (200, 206, 212), "k": (30, 30, 34), "y": (232, 206, 60)},
    (_rows("""
......ww.....
...w.wwwkkkk.
....wwww.....
......w......
......ww.....
.......w.....
......ww.....
.....ww......
..swwwww.....
swwwwwwww....
.sswwwwwww...
...sswwww....
.....k.k.....
.....k.k.....
.....k.k.....
.....k.k.....
....yy.yy....
"""), _rows("""
.............
.............
.............
.............
.........ww....
.......wwwwkkkk
......ww.......
......w........
.....ww........
..swwwww.......
swwwwwwww......
.sswwwwwww.....
...sswwww......
.....k.k.......
.....k.k.......
.....k..k......
....yy..yy.....
""")),
    beat=((0, 2.5), (1, 1.2)),
    home=("estuary", "pool_edge"),
)

CURLEW = Creature(
    "curlew", "curlew",
    {"b": (150, 118, 80), "B": (96, 72, 48), "p": (196, 172, 132), "c": (70, 52, 40), "k": (24, 22, 20),
     "l": (110, 112, 118)},
    (_rows("""
.......bbb.....
......bbkbc....
......bbb..c...
.....bb.....c..
bbbbbbb......c.
BbBbbbBb.......
.bBbBbbbp......
..ppppppp......
....l.l........
....l.l........
...l..l........
"""), _rows("""
...............
...............
...............
...............
bbbbbb.........
BbBbbbBbbb.....
.bBbBbbbkbc....
..pppppppb.c...
....l.l.....c..
....l.l......c.
...l..l........
""")),
    beat=((0, 2.0), (1, 1.4)),
    home=("estuary", "mud"),
)

OYSTERCATCHER = Creature(
    "oystercatcher", "oystercatcher",
    {"k": (24, 24, 28), "w": (240, 240, 236), "o": (236, 112, 36), "r": (220, 40, 30), "p": (226, 150, 150)},
    (_rows("""
.....kkk....
....kkrkoooo
....kkk.....
kkkkkkk.....
kkkkkkww....
.kwwwwww....
..wwwww.....
....p.p.....
....p.p.....
"""), _rows("""
............
............
............
kkkkkk......
kkkkkkkkk...
.kwwwwwkrk..
..wwwwwkk...
....p.p..o..
....p.p...o.
""")),
    beat=((0, 1.0), (1, 0.6), (0, 0.8), (1, 0.5)),
    home=("estuary", "shore"),
)

BRENT = Creature(
    "brent", "brent goose",
    {"k": (26, 26, 30), "w": (236, 236, 232), "D": (64, 62, 66), "d": (104, 100, 102), "v": (170, 196, 214)},
    (_rows("""
.......kk.
.......kkk
......kw..
......kk..
wDDDDDDk..
wwDdDdDD..
.vvvvvvv..
"""), _rows("""
..........
..........
..........
wDDDDDD...
wwDdDdDDk.
.vvvvvvvkk
..........
""")),
    beat=((0, 2.2), (1, 1.6)),
    home=("estuary", "channel"),
)

SEAL = Creature(
    "seal", "grey seal",
    {"g": (128, 130, 136), "G": (86, 88, 96), "s": (178, 176, 170), "k": (20, 20, 24), "n": (50, 46, 46),
     "f": (96, 98, 104)},
    (_rows("""
..................ggg..
................ggggkg.
..............ggggggggn
....gggGggGggggggggg...
..ggggGgggGgggGgggg....
fgggggggggggggggggs....
ffgssssssssssssss......
.f..ssssssssssss.......
"""), _rows("""
.......................
.......................
.......................
....gggGggGgggggggggggn
..ggggGgggGgggGggggkgg.
fgggggggggggggggggggs..
ffgssssssssssssss......
.f..ssssssssssss.......
""")),
    beat=((0, 3.5), (1, 2.5)),
    home=("slipway", "ramp"),
)

PUP = Creature(
    "pup", "grey seal pup",
    {"c": (238, 234, 222), "s": (204, 198, 186), "k": (16, 16, 20), "n": (60, 50, 50)},
    (_rows("""
.........ccc.
........cckcc
.......cccccn
..cccccccccc.
cccccccccccc.
.cssssssssc..
"""), _rows("""
.............
.............
.........ccc.
..ccccccckccn
ccccccccccc..
.cssssssssc..
""")),
    beat=((0, 2.0), (1, 2.6)),
    home=("slipway", "ramp_low"),
)

SEAL_HEAD = Creature(
    "seal_head", "grey seal in the water",
    {"g": (118, 120, 128), "k": (16, 16, 20), "n": (50, 46, 46), "w": (196, 222, 236)},
    (_rows("""
..ggg..
.ggkgg.
.ggggn.
.gggg..
wwwwwww
"""), _rows("""
.......
..ggg..
.ggkgg.
.ggggn.
wwwwwww
""")),
    beat=((0, 2.5), (1, 1.5)),
    home=("harbour", "water"),
)

OTTER = Creature(
    "otter", "otter",
    {"o": (104, 70, 42), "O": (78, 50, 30), "p": (190, 160, 120), "k": (16, 14, 12), "n": (40, 30, 26)},
    (_rows("""
...............oo..
.............ooko..
.....oooooooooooon.
oooooOooooooooopp..
...oOoooooooooo....
.....o..o...o.o....
"""), _rows("""
...................
...................
.....oooooooooo....
oooooOoooooooooooo.
...oOoooooooooookoon
.....o..o...o.o.pp.
""")),
    beat=((0, 2.8), (1, 1.4)),
    home=("estuary", "reeds"),
)

CREATURES = {c.id: c for c in (HERON, EGRET, CURLEW, OYSTERCATCHER, BRENT, SEAL, PUP, SEAL_HEAD, OTTER)}

# Where a creature may be on each backdrop: (x, y), its bottom centre on the 320 x 180 canvas.
SPOTS: dict[str, dict[str, tuple[int, int]]] = {
    "estuary": {"mud": (112, 160), "shore": (150, 166), "pool": (214, 164), "pool_edge": (190, 156),
                "reeds": (74, 150), "channel": (150, 112), "sky": (170, 44)},
    "slipway": {"ramp": (196, 160), "ramp_low": (178, 168), "water": (286, 142)},
    "harbour": {"water": (248, 170), "quay": (60, 160)},
    "lighthouse": {"sea": (80, 112)},
    "seafront": {"sea": (170, 120)},
}


# The hide's two shots (the user, on the contact sheet, 2026-11-14): a close-up of one creature at 4x with the place
# soft behind it, and a wide at 2x, sharp, for setting the scene and for the flocks.
SHOTS = {"close": {"zoom": 4, "soft": True}, "wide": {"zoom": 2, "soft": False}}


def shot_for(creature: str) -> str:
    """The shot a creature is filmed in unless the plan says otherwise: the flocks wide, anything else close."""
    return "wide" if creature in ("starlings", "brent") else "close"


# ------------------------------------------------------------------ drawing

def _lit(col: RGB, light) -> RGB:
    if not light:
        return col
    return tuple(min(255, int(c * k)) for c, k in zip(col, light))


def draw(canvas: pygame.Surface, creature: str, x: int, y: int, t: float, *, scale: int = 1, facing: int = 1,
         light=None, phase: float = 0.0) -> None:
    """One creature with (x, y) its bottom centre, `scale` canvas pixels a unit, mirrored for facing left."""
    c = CREATURES[creature]
    rows = c.frame_at(t, phase)
    h, w = len(rows), len(rows[0])
    left, top = x - (w * scale) // 2, y - h * scale
    if c.edge:                                   # a dark edge a unit wide, as Gully has, so it reads on mud and reeds
        edge = _lit(c.edge, light)
        filled = {(r, i) for r, row in enumerate(rows) for i, ch in enumerate(row) if ch != "."}
        for r, i in {(r + a, i + b) for r, i in filled for a, b in ((1, 0), (-1, 0), (0, 1), (0, -1))} - filled:
            dx = i if facing >= 0 else w - 1 - i
            canvas.fill(edge, (left + dx * scale, top + r * scale, scale, scale))
    for r, row in enumerate(rows):
        for i, ch in enumerate(row):
            if ch == ".":
                continue
            col = _lit(c.palette[ch], light)
            dx = i if facing >= 0 else w - 1 - i
            canvas.fill(col, (left + dx * scale, top + r * scale, scale, scale))


def draw_flock(canvas: pygame.Surface, creature: str, x: int, y: int, t: float, *, n: int = 7, spread: int = 70,
               scale: int = 1, light=None, seed: int = 7) -> None:
    """A loose flock about (x, y): brent geese grazing on the water, each on its own beat."""
    rnd = random.Random(seed)
    birds = sorted(((rnd.uniform(-spread / 2, spread / 2), rnd.uniform(-5, 5), rnd.choice((-1, 1)),
                     rnd.uniform(0, 4)) for _ in range(n)), key=lambda b: b[1])
    for dx, dy, f, ph in birds:
        drift = math.sin(t * 0.3 + ph) * 1.5
        draw(canvas, creature, int(x + (dx + drift) * scale), int(y + dy * scale), t, scale=scale, facing=f,
             light=light, phase=ph)


def draw_murmuration(canvas: pygame.Surface, x: int, y: int, t: float, *, n: int = 260, scale: int = 1,
                     size: float = 1.0, seed: int = 11) -> None:
    """Starlings over the reeds at dusk: a cloud that drifts, stretches and folds, each bird a dark pixel."""
    rnd = random.Random(seed)
    cx = x + math.sin(t * 0.21) * 34 * size
    cy = y + math.sin(t * 0.33 + 1.0) * 10 * size
    sx = (26 + 14 * math.sin(t * 0.47)) * size        # the cloud's width and height breathe out of step
    sy = (11 + 6 * math.sin(t * 0.61 + 2.0)) * size
    tilt = math.sin(t * 0.17) * 0.7
    col = (24, 22, 30)
    for _ in range(n):
        a = rnd.uniform(0, math.tau)
        r = math.sqrt(rnd.random())
        ph = rnd.uniform(0, math.tau)
        u = r * math.cos(a + 0.4 * math.sin(t * 0.9 + ph))
        v = r * math.sin(a + 0.4 * math.sin(t * 0.9 + ph))
        px = cx + (u * math.cos(tilt) - v * math.sin(tilt)) * sx
        py = cy + (u * math.sin(tilt) + v * math.cos(tilt)) * sy + math.sin(t * 2.0 + ph) * 0.8
        canvas.fill(col, (int(px), int(py), scale, scale))


def draw_at(canvas: pygame.Surface, creature: str, backdrop: str, spot: str, t: float, *, scale: int = 1,
            offset: tuple[int, int] = (0, 0), light=None, facing: int = 1) -> None:
    """A creature (or "brent" as a flock, "starlings" as a murmuration) at a named spot, on a canvas whose origin is
    `offset` canvas pixels into the backdrop and `scale` pixels a backdrop pixel (the hide view's crop)."""
    sx, sy = SPOTS[backdrop][spot]
    x, y = (sx - offset[0]) * scale, (sy - offset[1]) * scale
    if creature == "starlings":
        draw_murmuration(canvas, x, y, t, scale=scale, size=scale)
    elif creature == "brent":
        draw_flock(canvas, "brent", x, y, t, scale=scale, light=light)
    else:
        draw(canvas, creature, x, y, t, scale=scale, light=light, facing=facing)


def hide_crop(backdrop: str, spot: str, zoom: int = 2, size: tuple[int, int] = (320, 180),
              feet: float = 0.72) -> pygame.Rect:
    """The part of the backdrop the hide view shows: the screen's size over `zoom`, round the spot with the creature's
    feet `feet` of the way down (on air 0.6, clear of the ticker), kept inside the picture."""
    w, h = size[0] // zoom, size[1] // zoom
    sx, sy = SPOTS[backdrop][spot]
    x = min(max(0, sx - w // 2), size[0] - w)
    y = min(max(0, sy - (h // 2 if spot == "sky" else int(h * feet))), size[1] - h)   # a flock in the sky: centred
    return pygame.Rect(x, y, w, h)


def draw_hide(canvas: pygame.Surface, backdrop: str, spot: str, creature: str, t: float, *, tod: str = "day",
              wx: str | None = None, zoom: int = 2, label: str = "TIDELINE", facing: int = 1,
              soft: bool = False, shot: str | None = None, feet: float = 0.72) -> None:
    """The hide view: the composed backdrop (sky, grade and all) cropped round the spot and scaled up `zoom`x with
    nearest neighbour, the creature at the same scale, the documentary's letterbox and a strand label. `shot`
    ("close" or "wide", SHOTS) sets the zoom and the focus together."""
    if shot:
        zoom, soft = SHOTS[shot]["zoom"], SHOTS[shot]["soft"]
    from newsroom import backdrops
    w, h = canvas.get_size()
    full = pygame.Surface((w, h))
    backdrops.draw(full, backdrop, tod, wx, t)
    crop = hide_crop(backdrop, spot, zoom, (w, h), feet)
    part = full.subsurface(crop)
    if soft:                                      # a long lens's shallow focus: the place soft, the creature sharp
        small = pygame.transform.smoothscale(part, (max(1, crop.w // 2), max(1, crop.h // 2)))
        canvas.blit(pygame.transform.smoothscale(small, (w, h)), (0, 0))
    else:
        canvas.blit(pygame.transform.scale(part, (w, h)), (0, 0))
    light = backdrops.person_light(backdrop, tod, wx)
    draw_at(canvas, creature, backdrop, spot, t, scale=zoom, offset=crop.topleft, light=light, facing=facing)
    pygame.draw.rect(canvas, (0, 0, 0), (0, 0, w, 14))
    pygame.draw.rect(canvas, (0, 0, 0), (0, h - 14, w, 14))
    if label:
        from newsroom.scenes import text
        lw = max(60, len(label) * 5 + 10)
        pygame.draw.rect(canvas, (120, 170, 110), (8, 3, lw, 9))
        text(canvas, label, 8 + lw // 2, 7, 8, (20, 20, 20), center=True)


def draw_wide(canvas: pygame.Surface, backdrop: str, spot: str, creature: str, t: float, *, tod: str = "day",
              wx: str | None = None, facing: int = 1) -> None:
    """The creature at its own size on the whole backdrop, for comparison with the hide view."""
    from newsroom import backdrops
    backdrops.draw(canvas, backdrop, tod, wx, t)
    draw_at(canvas, creature, backdrop, spot, t, light=backdrops.person_light(backdrop, tod, wx), facing=facing)


# ------------------------------------------------------------------ the contact sheet

SHEET = (   # (creature, backdrop, spot, time of day, facing, caption)
    ("seal", "slipway", "ramp", "day", -1, "grey seal hauled out on the cannery slipway"),
    ("pup", "slipway", "ramp_low", "day", -1, "grey seal pup"),
    ("seal_head", "harbour", "water", "day", -1, "a seal bottling in the harbour"),
    ("heron", "estuary", "pool", "day", 1, "grey heron in the pool"),
    ("egret", "estuary", "pool_edge", "day", -1, "little egret"),
    ("curlew", "estuary", "mud", "day", 1, "curlew on the mud"),
    ("oystercatcher", "estuary", "shore", "day", -1, "oystercatcher probing"),
    ("brent", "estuary", "channel", "day", 1, "brent geese on the channel"),
    ("starlings", "estuary", "sky", "dusk", 1, "the starling roost over the reeds, at dusk"),
    ("otter", "estuary", "reeds", "day", 1, "otter by the reeds"),
)


def _sheet(path: str, t: float = 1.0, zoom: int = 2) -> None:
    cw, ch, k = 320, 180, 2                       # each picture at 2x for the sheet
    pad, cap = 8, 22
    rows = len(SHEET)
    font = pygame.font.SysFont("consolas", 16)
    sheet = pygame.Surface((pad + 3 * (cw * k + pad) + 230, pad + rows * (ch * k + cap + pad)))
    sheet.fill((24, 24, 28))
    for i, (cr, bd, sp, tod, f, caption) in enumerate(SHEET):
        y = pad + i * (ch * k + cap + pad)
        wide, hide, close = (pygame.Surface((cw, ch)) for _ in range(3))
        draw_wide(wide, bd, sp, cr, t, tod=tod, facing=f)
        draw_hide(hide, bd, sp, cr, t, tod=tod, zoom=zoom, facing=f, label="")
        draw_hide(close, bd, sp, cr, t, tod=tod, zoom=4, facing=f, label="", soft=True)
        for j, pic in enumerate((wide, hide, close)):
            sheet.blit(pygame.transform.scale(pic, (cw * k, ch * k)), (pad + j * (cw * k + pad), y + cap))
        sheet.blit(font.render(f"{i + 1}. {caption}:   A as it is   B the hide at {zoom}x   "
                               "C a close-up at 4x, the place soft", True, (230, 230, 230)), (pad, y + 2))
        if cr not in ("starlings", "brent"):          # the sprite itself, large, both frames
            c = CREATURES[cr]
            for j, rows_ in enumerate(c.frames):
                big = 8 if len(rows_[0]) <= 16 else 6
                surf = pygame.Surface((len(rows_[0]) * big, len(rows_) * big), pygame.SRCALPHA)
                for r, row in enumerate(rows_):
                    for q, chh in enumerate(row):
                        if chh != ".":
                            surf.fill(c.palette[chh], (q * big, r * big, big, big))
                bg = pygame.Surface(surf.get_size())
                bg.fill((96, 102, 112))
                bg.blit(surf, (0, 0))
                sheet.blit(bg, (pad * 4 + 3 * cw * k, y + cap + j * (ch * k // 2)))
    pygame.image.save(sheet, path)


if __name__ == "__main__":
    import argparse
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    ap = argparse.ArgumentParser()
    ap.add_argument("--sheet", required=True, help="write the contact sheet PNG here")
    ap.add_argument("--zoom", type=int, default=2)
    ap.add_argument("--t", type=float, default=1.0, help="the moment drawn")
    a = ap.parse_args()
    pygame.init()
    pygame.display.set_mode((1, 1))
    _sheet(a.sheet, a.t, a.zoom)
    print(a.sheet)
