"""Channel 7's on-screen logo, drawn in code on the 320x180 canvas.

The mark is a roundel in the show's colour with a bold 7 standing in the harbour and a
lighthouse at its foot whose beam sweeps the frame; under it, the wordmark
CHANNEL 7 · PORT WEXLEY in a blocky 5x7 face of its own. The painted ident on the
interview set (backdrops.py) is the same red roundel with the same 7.

- `draw_ident(surf, t, show, onsets)`: the full-frame ident in the 70s manner. Stripes sweep
  in, the mark assembles one piece per note of the tune (`jingle.onsets()`), the beam swings
  across on the held note, then the logo holds with the sea moving and the beam turning.
- `draw_mark(...)` and `draw_wordmark(...)`: the logo at rest, for the filler and test cards.
- `draw_bug(surf)`: the small see-through dog in the corner during programmes.

    python -m newsroom.logo --sheet out.png                   # key frames of every show's ident
    python -m newsroom.logo --mp4 out.mp4 [--audio x.wav]     # 1080p, muxed with ffmpeg
"""
from __future__ import annotations

import math
import random
from functools import lru_cache

import pygame

from . import schedule

RGB = tuple[int, int, int]

CREAM = (244, 238, 222)
LAMP = (255, 232, 150)
BEAM = (255, 242, 196)
SUN = (255, 214, 110)
DAWN = (46, 40, 84)              # Morning Tide's sky before the sun is up
OUTLINE_K = 0.45                 # outlines are the fill colour this dark, as in sprites.py

R = 34                           # the roundel's radius in the ident; geometry below is in these units
CENTRE = (160, 76)               # where the ident puts the roundel
DEFAULT_ONSETS = [0.0, 0.35, 0.7, 1.05, 1.6]
POP_S = 0.18                     # each piece takes this long to land
SWEEP_S = 0.32                   # the stripes' run in from the side
WORDMARK_S = 0.45                # after the held note: the wordmark wipes in over this,
TITLE_DELAY_S, TITLE_S = 0.3, 0.4   # and the show's title after it; all in well before the voice-over
BEAM_TURN = math.pi / 1.3        # radians a second: right, a flash at the lamp, left, every 2.6 s
BUG_ALPHA = 150


def _dark(c: RGB, k: float) -> RGB:
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _mix(a: RGB, b: RGB, k: float) -> RGB:
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


def _clamp(x: float) -> float:
    return 0.0 if x < 0 else 1.0 if x > 1 else x


def _ease(x: float) -> float:
    return 1 - (1 - _clamp(x)) ** 3


def _back(x: float) -> float:
    """Ease out past the mark and settle back: how a piece lands with a little bounce."""
    x, c = _clamp(x), 1.70158
    return 1 + (c + 1) * (x - 1) ** 3 + c * (x - 1) ** 2


def colour(show: str | None) -> RGB:
    return schedule.get(show).colour


# ------------------------------------------------------------------ the face

GLYPHS = {
    "A": ".###. #...# #...# ##### #...# #...# #...#", "B": "####. #...# #...# ####. #...# #...# ####.",
    "C": ".###. #...# #.... #.... #.... #...# .###.", "D": "####. #...# #...# #...# #...# #...# ####.",
    "E": "##### #.... #.... ####. #.... #.... #####", "F": "##### #.... #.... ####. #.... #.... #....",
    "G": ".###. #...# #.... #.### #...# #...# .####", "H": "#...# #...# #...# ##### #...# #...# #...#",
    "I": ".###. ..#.. ..#.. ..#.. ..#.. ..#.. .###.", "J": "..### ...#. ...#. ...#. #..#. #..#. .##..",
    "K": "#...# #..#. #.#.. ##... #.#.. #..#. #...#", "L": "#.... #.... #.... #.... #.... #.... #####",
    "M": "#...# ##.## #.#.# #.#.# #...# #...# #...#", "N": "#...# ##..# #.#.# #.#.# #..## #...# #...#",
    "O": ".###. #...# #...# #...# #...# #...# .###.", "P": "####. #...# #...# ####. #.... #.... #....",
    "Q": ".###. #...# #...# #...# #.#.# #..#. .##.#", "R": "####. #...# #...# ####. #.#.. #..#. #...#",
    "S": ".#### #.... #.... .###. ....# ....# ####.", "T": "##### ..#.. ..#.. ..#.. ..#.. ..#.. ..#..",
    "U": "#...# #...# #...# #...# #...# #...# .###.", "V": "#...# #...# #...# #...# #...# .#.#. ..#..",
    "W": "#...# #...# #...# #.#.# #.#.# ##.## #...#", "X": "#...# #...# .#.#. ..#.. .#.#. #...# #...#",
    "Y": "#...# #...# .#.#. ..#.. ..#.. ..#.. ..#..", "Z": "##### ....# ...#. ..#.. .#... #.... #####",
    "7": "##### ....# ...#. ..#.. .#... .#... .#...", "·": ". . . # . . .", "'": "# # . . . . .",
    " ": "... ... ... ... ... ... ...",
}


def text_width(s: str, scale: int = 1, gap: int = 1) -> int:
    widths = [len(GLYPHS.get(ch, GLYPHS[" "]).split()[0]) for ch in s.upper()]
    return (sum(widths) + gap * (len(widths) - 1)) * scale


@lru_cache(maxsize=64)
def _text_surface(s: str, scale: int, col: RGB, gap: int, shadow: RGB | None) -> pygame.Surface:
    w, h = text_width(s, scale, gap), 7 * scale
    out = pygame.Surface((w + (scale if shadow else 0), h + (scale if shadow else 0)), pygame.SRCALPHA)
    for c, off in ((shadow, scale), (col, 0)) if shadow else ((col, 0),):
        x = off
        for ch in s.upper():
            rows = GLYPHS.get(ch, GLYPHS[" "]).split()
            for j, row in enumerate(rows):
                for i, px in enumerate(row):
                    if px == "#":
                        out.fill(c, (x + i * scale, off + j * scale, scale, scale))
            x += (len(rows[0]) + gap) * scale
    return out


def draw_text(surf: pygame.Surface, s: str, x: int, y: int, scale: int = 1, col: RGB = CREAM, *,
              gap: int = 1, center: bool = False, shadow: RGB | None = None, reveal: float = 1.0) -> None:
    """The logo's own blocky face. `reveal` wipes it in from the left, 0..1."""
    if reveal <= 0:
        return
    img = _text_surface(s, scale, col, gap, shadow)
    if center:
        x -= img.get_width() // 2
    surf.blit(img, (x, y), (0, 0, round(img.get_width() * _clamp(reveal)), img.get_height()))


WORDMARK = "CHANNEL 7 · PORT WEXLEY"


def draw_wordmark(surf: pygame.Surface, cx: int, y: int, show: str | None, *, scale: int = 2,
                  reveal: float = 1.0) -> None:
    draw_text(surf, WORDMARK, cx, y, scale, CREAM, center=True, shadow=_dark(colour(show), 0.3), reveal=reveal)


# ------------------------------------------------------------------ the mark

# The 7, in roundel units from its centre (as on the set's painted ident: a bar and a stroke).
BAR = [(-19, -22), (19, -22), (19, -13), (-19, -13)]
STEM = [(9, -13), (19, -13), (1, 25), (-9, 25)]
LIGHT_X = 23                     # the lighthouse stands here, right of the 7's stroke
LAMP_Y = -8


@lru_cache(maxsize=32)
def _disc_mask(rr: int) -> pygame.Surface:
    m = pygame.Surface((2 * rr + 1, 2 * rr + 1), pygame.SRCALPHA)
    pygame.draw.circle(m, (255, 255, 255, 255), (rr, rr), rr)
    return m


def _poly(pts, ox: float, oy: float, u: float) -> list[tuple[int, int]]:
    return [(round(ox + x * u), round(oy + y * u)) for x, y in pts]


def _seven(layer: pygame.Surface, ox: float, oy: float, u: float, col: RGB, bar: float, stem: float) -> None:
    """The 7 with a dark outline and a drop shadow, its bar sliding in and its stroke dropping."""
    tmp = pygame.Surface(layer.get_size(), pygame.SRCALPHA)
    if bar > 0:
        pygame.draw.polygon(tmp, CREAM, _poly(BAR, ox - (1 - _back(bar)) * 44 * u, oy, u))
    if stem > 0:
        pygame.draw.polygon(tmp, CREAM, _poly(STEM, ox, oy - (1 - _back(stem)) * 50 * u, u))
    m = pygame.mask.from_surface(tmp)
    if not m.count():
        return
    edge = m.to_surface(setcolor=(*_dark(col, OUTLINE_K), 255), unsetcolor=(0, 0, 0, 0))
    d = max(1, round(2 * u))
    layer.blit(m.to_surface(setcolor=(*_dark(col, 0.7), 255), unsetcolor=(0, 0, 0, 0)), (d, d))
    for off in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        layer.blit(edge, off)
    layer.blit(tmp, (0, 0))


def _lighthouse(layer: pygame.Surface, ox: float, oy: float, u: float, col: RGB) -> None:
    edge, band = _dark(col, OUTLINE_K), _dark(col, 0.8)
    x = LIGHT_X
    tower = _poly([(x - 3.5, 22), (x + 3.5, 22), (x + 2.5, -6), (x - 2.5, -6)], ox, oy, u)
    pygame.draw.polygon(layer, edge, tower, 0)
    pygame.draw.polygon(layer, CREAM, _poly([(x - 2.5, 22), (x + 2.5, 22), (x + 1.5, -5), (x - 1.5, -5)],
                                            ox, oy, u))
    for y0 in (1, 10):                                             # two bands round the tower
        pygame.draw.polygon(layer, band, _poly([(x - 2.3, y0 + 3), (x + 2.3, y0 + 3), (x + 2, y0), (x - 2, y0)],
                                               ox, oy, u))
    pygame.draw.polygon(layer, edge, _poly([(x - 4, -7), (x + 4, -7), (x + 4, -5.5), (x - 4, -5.5)], ox, oy, u))
    pygame.draw.polygon(layer, LAMP, _poly([(x - 1.5, -11), (x + 1.5, -11), (x + 1.5, -7), (x - 1.5, -7)],
                                           ox, oy, u))
    pygame.draw.polygon(layer, edge, _poly([(x - 3, -11), (x + 3, -11), (x, -14.5)], ox, oy, u))


def _harbour(layer: pygame.Surface, ox: float, oy: float, u: float, col: RGB, t: float) -> None:
    """Two rows of sea across the bottom of the roundel, each with a cream crest, rolling."""
    w, h = layer.get_size()
    far, near = _mix(col, CREAM, 0.35), _mix(col, CREAM, 0.62)
    for x in range(w):
        dx = (x - ox) / u
        ya = round(oy + (16 + 1.6 * math.sin(dx * 0.32 + t * 2.2)) * u)
        yb = round(oy + (24 + 1.4 * math.sin(dx * 0.32 - t * 1.7 + 1.3)) * u)
        if ya < h:
            layer.fill(far, (x, ya, 1, h - ya))
            layer.fill(CREAM, (x, ya, 1, 1))
        if yb < h:
            layer.fill(near, (x, yb, 1, h - yb))
            layer.fill(CREAM, (x, yb, 1, 1))


def _beam(surf: pygame.Surface, lx: int, ly: int, turn: float, u: float, reach: float, strength: float) -> None:
    """The lighthouse beam seen side-on: it reaches out right, shrinks to a flash at the lamp
    as it turns towards us, then reaches out left."""
    d = math.cos(turn)
    over = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
    a = int(110 * strength * abs(d) ** 0.5)
    if abs(d) > 0.04 and a > 0:
        tip = lx + d * reach
        half = (3 + 9 * abs(d)) * u
        pygame.draw.polygon(over, (*BEAM, a), [(lx, ly - u), (tip, ly - half), (tip, ly + half), (lx, ly + u)])
        pygame.draw.polygon(over, (*BEAM, min(255, a + 40)),
                            [(lx, ly), (lx + d * reach * 0.6, ly - half * 0.3), (lx + d * reach * 0.6, ly + half * 0.3)])
    glow = (1 - abs(d)) ** 3
    if glow > 0.05:                                                # facing us: a flash at the lamp
        pygame.draw.circle(over, (*BEAM, int(200 * glow * strength)), (lx, ly), round((2 + 7 * glow) * u))
    surf.blit(over, (0, 0))


def draw_mark(surf: pygame.Surface, cx: int, cy: int, show: str | None, *, r: int = R, t: float = 0.0,
              pieces: tuple[float, float, float, float] = (1, 1, 1, 1), beam: float | None = None,
              beam_strength: float = 1.0, reach: float | None = None, flash: float = 0.0) -> None:
    """The roundel at (cx, cy). `pieces` is how far the disc, the 7's bar, its stroke and the
    harbour (sea and lighthouse) have come in, 0..1 each. `beam` is the lighthouse's turn in
    radians (0 shines right), None for no beam; `flash` brightens the disc on a note."""
    col = colour(show)
    u = r / R
    disc, bar, stem, harbour = pieces
    rr = round(r * _back(disc))
    if rr <= 1:
        return
    pygame.draw.circle(surf, _dark(col, OUTLINE_K), (cx, cy), rr + max(2, round(3 * u)))
    pygame.draw.circle(surf, CREAM, (cx, cy), rr + max(1, round(2 * u)))
    layer = pygame.Surface((2 * rr + 1, 2 * rr + 1), pygame.SRCALPHA)
    layer.fill((*_mix(col, CREAM, 0.3 * _clamp(flash)), 255))
    o = rr
    _seven(layer, o, o, u, col, bar, stem)
    if harbour > 0:
        rise = (1 - _ease(harbour)) * 24 * u
        _lighthouse(layer, o, o + rise, u, col)
        _harbour(layer, o, o + rise, u, col, t)
    layer.blit(_disc_mask(rr), (0, 0), special_flags=pygame.BLEND_RGBA_MULT)
    surf.blit(layer, (cx - rr, cy - rr))
    if beam is not None and harbour >= 1:
        _beam(surf, round(cx + LIGHT_X * u), round(cy + LAMP_Y * u), beam, u,
              reach if reach is not None else 150 * u, beam_strength)


# ------------------------------------------------------------------ the ident


def piece_times(onsets: list[float]) -> list[float]:
    """When each of the five pieces lands (disc, bar, stroke, harbour, beam and wordmark).
    The first and last notes always start the first and last pieces; a longer tune spreads
    the middle ones across its notes, a shorter one brings the rest in on its last note."""
    n = len(onsets)
    if n >= 5:
        return [onsets[int(i * (n - 1) / 4 + 0.5)] for i in range(5)]
    return [onsets[min(i, n - 1)] for i in range(5)]


def _stars(surf: pygame.Surface, t: float) -> None:
    rnd = random.Random(7)
    w, h = surf.get_size()
    for k in range(28):
        x, y = rnd.randrange(w), rnd.randrange(h)
        if 0.5 + 0.5 * math.sin(t * 2.3 + k * 1.7) > 0.25:
            surf.fill((200, 200, 230) if k % 3 else (255, 240, 200), (x, y, 1, 1))


STRIPES = 7                      # seven of them, naturally


def _stripes(surf: pygame.Surface, col: RGB, bg: RGB, t: float, flash: float, cy: int) -> None:
    """Seven bands behind the roundel, running in alternately from left and right."""
    w = surf.get_width()
    top = cy - 33
    for i in range(STRIPES):
        k = _ease((t - i * 0.035) / SWEEP_S)
        if k <= 0:
            continue
        c = _mix(_mix(bg, col, 0.4 + 0.12 * (i % 2)), CREAM, 0.35 * flash)
        y = top + i * 10
        if i % 2:
            surf.fill(c, (round(w * (1 - k)), y, w, 6))
        else:
            surf.fill(c, (0, y, round(w * k), 6))


def draw_ident(surf: pygame.Surface, t: float, show: str | None, onsets: list[float] | None = None) -> None:
    """The full-frame ident at `t` seconds in. `onsets` are the tune's note times (jingle.onsets);
    each lands a piece of the mark, the last swings the beam across and writes the wordmark."""
    onsets = sorted(onsets or DEFAULT_ONSETS)
    w, h = surf.get_size()
    col = colour(show)
    bg = DAWN if show == "breakfast" else _dark(col, 0.24)
    surf.fill(bg)
    cx, cy = CENTRE
    if show in ("late", "overnight"):
        _stars(surf, t)
    flash = min(1.0, sum(math.exp(-(t - o) / 0.14) for o in onsets if o <= t))
    _stripes(surf, col, bg, t, flash, cy)
    at = piece_times(onsets)
    last = at[4]
    if show == "breakfast":                                       # the sun comes up behind the roundel
        rise = _ease(t / (last + 0.8))
        pygame.draw.circle(surf, SUN, (cx, round(cy + (1 - rise) * 130)), R + 12)
        pygame.draw.circle(surf, _mix(SUN, CREAM, 0.5), (cx, round(cy + (1 - rise) * 130)), R + 7)
    pieces = tuple((t - at[i]) / POP_S for i in range(4))
    beam = (t - last) * BEAM_TURN if t >= last else None
    draw_mark(surf, cx, cy, show, t=t, pieces=pieces, beam=beam, beam_strength=_ease((t - last) / 0.3),
              reach=w * 0.62, flash=flash)
    draw_wordmark(surf, w // 2, 124, show, reveal=(t - last) / WORDMARK_S)
    title = schedule.get(show).title
    k = _ease((t - last - TITLE_DELAY_S) / TITLE_S)
    if k > 0:
        tw = text_width(title, 1, 2)
        y = 146
        draw_text(surf, title, w // 2, y, 1, _mix(col, CREAM, 0.6), gap=2, center=True, reveal=k)
        rule = round((w // 2 - tw // 2 - 14) * k)
        surf.fill(col, (w // 2 - tw // 2 - 8 - rule, y + 3, rule, 1))
        surf.fill(col, (w // 2 + tw // 2 + 8, y + 3, rule, 1))


# ------------------------------------------------------------------ the bug

BUG_SIZE = 13


@lru_cache(maxsize=1)
def _bug() -> pygame.Surface:
    """A cream disc with the 7 knocked out of it, see-through, a few pixels high."""
    s = pygame.Surface((BUG_SIZE, BUG_SIZE), pygame.SRCALPHA)
    c = (BUG_SIZE - 1) / 2
    seven = {(x, y) for y in (3, 4) for x in range(3, 10)}
    seven |= {(x, y) for y, x0 in ((5, 7), (6, 7), (7, 6), (8, 6), (9, 5), (10, 5)) for x in (x0, x0 + 1)}
    for y in range(BUG_SIZE):
        for x in range(BUG_SIZE):
            if (x - c) ** 2 + (y - c) ** 2 <= (c + 0.4) ** 2 and (x, y) not in seven:
                s.set_at((x, y), (*CREAM, BUG_ALPHA))
    return s


def bug_rect(size: tuple[int, int]) -> pygame.Rect:
    """Bottom right, above the ticker and right of the lower third."""
    w, h = size
    return pygame.Rect(w - BUG_SIZE - 6, h - 14 - BUG_SIZE - 6, BUG_SIZE, BUG_SIZE)


def draw_bug(surf: pygame.Surface) -> None:
    surf.blit(_bug(), bug_rect(surf.get_size()))


# ------------------------------------------------------------------ contact sheet and video

SHEET_SHOWS = ["news", "breakfast", "magazine", "late", "sport", "overnight"]


def key_times(onsets: list[float]) -> list[tuple[str, float]]:
    at = piece_times(onsets)
    last = at[4]
    return [("stripes", 0.12), ("bar", at[1] + 0.06), ("stroke", at[2] + 0.08), ("harbour", at[3] + 0.1),
            ("held note", last + 0.15), ("flash", last + 0.65), ("beam left", last + 1.25), ("hold", last + 3.0)]


def contact_sheet(path: str, onsets: list[float] | None = None, shows: list[str] | None = None) -> None:
    """Eight key frames of each show's ident, one show a row, at 2x."""
    pygame.font.init()
    f = pygame.font.SysFont("consolas", 10)
    onsets = onsets or DEFAULT_ONSETS
    shows = shows or SHEET_SHOWS
    keys = key_times(onsets)
    cw, ch = 320 + 4, 180 + 14
    sheet = pygame.Surface((len(keys) * cw, (len(shows) + 1) * ch))
    sheet.fill((30, 30, 36))
    frame = pygame.Surface((320, 180))

    def cell(col_i: int, row: int, label: str) -> None:
        x, y = col_i * cw + 2, row * ch
        sheet.blit(frame, (x, y + 12))
        sheet.blit(f.render(label, True, (220, 220, 220)), (x + 2, y))

    for row, show in enumerate(shows):
        for col_i, (label, t) in enumerate(keys):
            draw_ident(frame, t, show, onsets)
            cell(col_i, row, f"{show} · {label} · {t:.2f}s")
    from . import scenes                                          # the logo where the channel uses it
    from .player import View
    on_screen = [
        ("filler", View(mode="filler", show="news", map_state="rain", temp_c=11)),
        ("test card, start-up", None),
        ("test card, overnight", View(mode="testcard", show="overnight", resume_at="06:00", clock="02:14")),
        ("bug: studio", View(mode="studio", show="news", clock="18:04",
                             lower_third=("Harbour wall repairs", "Port Wexley"), ticker=["Tide high at 19:40"])),
        ("bug: weather", View(mode="weather", show="news", map_state="sunny", temp_c=17, clock="18:09")),
        ("bug: field", View(mode="field", show="breakfast", backdrop="harbour", speaker="reporter", tag="LIVE",
                            clock="07:21", lower_third=("Miles Okafor", "At the harbour"))),
        ("no bug: breaking", View(mode="studio", show="news", breaking=True, clock="18:30",
                                  lower_third=("Fire at the fish market", "Breaking news"))),
    ]
    for col_i, (label, v) in enumerate(on_screen):
        if v is None:
            scenes.draw_test_card(frame, 0.2)
        else:
            scenes.render(frame, v, 2.0)
        cell(col_i, len(shows), label)
    bug = pygame.Surface((320, 180))
    bug.fill((60, 90, 130))
    draw_bug(bug)
    zoom = pygame.Rect(0, 0, 64, 36)
    zoom.center = bug_rect(bug.get_size()).center
    zoom.clamp_ip(bug.get_rect())
    frame.blit(pygame.transform.scale(bug.subsurface(zoom), (320, 180)), (0, 0))
    cell(len(on_screen), len(shows), "the bug, close")
    pygame.image.save(pygame.transform.scale(sheet, (sheet.get_width() * 2, sheet.get_height() * 2)), path)


def _wav_seconds(path: str) -> float:
    import wave
    with wave.open(path) as wf:
        return wf.getnframes() / wf.getframerate()


def video(path: str, show: str = "news", onsets: list[float] | None = None, audio: str | None = None,
          seconds: float | None = None, fps: int = 30, scale: int = 6) -> bool:
    """Render the ident off-screen at `scale`x and pipe it to ffmpeg; False if there's no ffmpeg."""
    import shutil
    import subprocess
    exe = shutil.which("ffmpeg")
    if not exe:
        print("ffmpeg isn't on PATH: no video written")
        return False
    onsets = onsets or DEFAULT_ONSETS
    if seconds is None:
        seconds = _wav_seconds(audio) if audio else max(onsets) + 4.0
    size = (320 * scale, 180 * scale)
    cmd = [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{size[0]}x{size[1]}",
           "-r", str(fps), "-i", "-"]
    if audio:
        cmd += ["-i", audio, "-c:a", "aac", "-b:a", "192k", "-shortest"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf", "16", path]
    frame, big = pygame.Surface((320, 180)), pygame.Surface(size)
    proc = subprocess.Popen(cmd, stdin=subprocess.PIPE)
    try:
        for i in range(int(seconds * fps)):
            draw_ident(frame, i / fps, show, onsets)
            pygame.transform.scale(frame, size, big)
            proc.stdin.write(pygame.image.tobytes(big, "RGB"))
    finally:
        proc.stdin.close()
        proc.wait()
    return proc.returncode == 0


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sheet", help="write a contact sheet PNG here")
    ap.add_argument("--mp4", help="write the ident as a 1080p video here (needs ffmpeg)")
    ap.add_argument("--audio", help="a WAV to put under the video; its length sets the video's")
    ap.add_argument("--show", default="news", choices=sorted(schedule.SHOWS), help="the show's ident, for --mp4")
    ap.add_argument("--onsets", help="note times in seconds, comma-separated (default: %(default)s)")
    args = ap.parse_args()
    times = [float(x) for x in args.onsets.split(",")] if args.onsets else None
    if not (args.sheet or args.mp4):
        ap.error("give --sheet and/or --mp4")
    if args.sheet:
        contact_sheet(args.sheet, times)
        print(f"wrote {args.sheet}")
    if args.mp4 and video(args.mp4, args.show, times, args.audio):
        print(f"wrote {args.mp4}")
