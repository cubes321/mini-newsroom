"""Drawing. Pure functions of (canvas, View, t); no I/O, no threads.

The whole frame is painted on a 320x180 canvas and scaled to the window
with nearest-neighbour, which is what gives it the pixel-art look for free.
Every scene paints the full canvas; overlays (lower third, ticker, clock)
are drawn on top by `render()`.
"""
from __future__ import annotations

import math

import pygame

from .player import View
from .sprites import draw_character, draw_mic

CANVAS = (320, 180)

BARS = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]
SKY = {
    "sunny": (120, 180, 240), "cloudy": (150, 160, 175), "rain": (90, 100, 120), "storm": (50, 55, 70),
    "snow": (200, 205, 215), "fog": (170, 170, 170), "wind": (140, 170, 210), None: (110, 140, 200),
}
BACKDROPS = {
    "harbour": ((70, 110, 150), (40, 70, 100)), "main_street": ((160, 140, 120), (90, 80, 70)),
    "town_hall": ((190, 180, 160), (110, 100, 90)), "park": ((110, 160, 90), (60, 100, 50)),
    "factory": ((120, 110, 110), (70, 60, 60)), "farm": ((170, 150, 90), (100, 90, 50)),
    "stadium": ((90, 130, 90), (50, 70, 50)), "school": ((190, 160, 130), (120, 90, 70)),
}

_fonts: dict[int, pygame.font.Font] = {}


def font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont("consolas,couriernew,monospace", size, bold=size >= 10)
    return _fonts[size]


def text(canvas, s: str, x: int, y: int, size: int = 8, color=(240, 240, 240), center=False, maxw: int | None = None):
    f = font(size)
    if maxw:
        while len(s) > 4 and f.size(s)[0] > maxw:
            s = s[:-2]
        if f.size(s)[0] > maxw:
            s = s[:-1] + "…"
    surf = f.render(s, False, color)
    r = surf.get_rect(center=(x, y)) if center else surf.get_rect(topleft=(x, y))
    canvas.blit(surf, r)
    return r


# -------------------------------------------------------------------- scenes


def draw_test_card(canvas: pygame.Surface, t: float) -> None:
    w, h = canvas.get_size()
    bar_w = w / len(BARS)
    for i, c in enumerate(BARS):
        pygame.draw.rect(canvas, c, (int(i * bar_w), 0, int(bar_w) + 1, int(h * 0.7)))
    pygame.draw.rect(canvas, (20, 20, 24), (0, int(h * 0.7), w, h - int(h * 0.7)))
    text(canvas, "MINI NEWSROOM", w // 2, int(h * 0.8), 14, center=True)
    if int(t * 2) % 2 == 0:
        text(canvas, "STAND BY", w // 2, int(h * 0.91), 8, (200, 200, 60), center=True)
    cx = int(w / 2 + math.cos(t) * w * 0.3)
    pygame.draw.circle(canvas, (255, 255, 255), (cx, int(h * 0.35)), 5, 1)


def draw_filler(canvas: pygame.Surface, v: View, t: float) -> None:
    w, h = canvas.get_size()
    canvas.fill((16, 24, 48))
    for i in range(0, w, 8):
        y = int(h * 0.55 + math.sin(t * 0.8 + i * 0.05) * 6)
        pygame.draw.rect(canvas, (24, 36, 70), (i, y, 8, h - y))
    text(canvas, "PORT WEXLEY NEWS", w // 2, 50, 14, center=True)
    text(canvas, "we'll be right back", w // 2, 72, 8, (180, 190, 220), center=True)
    if v.map_state:
        text(canvas, f"{v.map_state} · {v.temp_c}°C", w // 2, 92, 8, (220, 220, 160), center=True)
    pygame.draw.rect(canvas, (255, 255, 255), (w // 2 - 20 + int(math.sin(t * 3) * 18), 110, 4, 4))


def draw_bumper(canvas: pygame.Surface, v: View, t: float) -> None:
    w, h = canvas.get_size()
    canvas.fill((200, 40, 40))
    k = int((t * 60) % (w + 40)) - 40
    pygame.draw.rect(canvas, (240, 240, 240), (k, 0, 16, h))
    pygame.draw.rect(canvas, (30, 30, 40), (40, 60, w - 80, 60))
    text(canvas, "CHANNEL 7", w // 2, 78, 14, center=True)
    text(canvas, "PORT WEXLEY NEWS", w // 2, 102, 8, (255, 200, 200), center=True)


def _studio_bg(canvas: pygame.Surface, t: float) -> None:
    w, h = canvas.get_size()
    canvas.fill((28, 34, 60))
    for i in range(6):                                            # back-wall skyline screens
        pygame.draw.rect(canvas, (40, 60, 110), (12 + i * 50, 30, 40, 50))
        pygame.draw.rect(canvas, (70, 110, 180), (16 + i * 50, 34 + int(math.sin(t + i) * 2), 32, 20))
    pygame.draw.rect(canvas, (80, 60, 50), (0, 130, w, 50))         # desk
    pygame.draw.rect(canvas, (120, 95, 80), (0, 130, w, 4))


def draw_studio(canvas: pygame.Surface, v: View, t: float) -> None:
    _studio_bg(canvas, t)
    draw_character(canvas, 110, 134, "anchor", v.mouth if v.speaker == "anchor" else 0.0, t, scale=2)
    if v.speaker == "reporter":                                   # anchor hands to the reporter box
        pygame.draw.rect(canvas, (20, 20, 20), (190, 40, 110, 80))
        pygame.draw.rect(canvas, (60, 90, 70), (194, 44, 102, 72))
        draw_character(canvas, 245, 112, "reporter", v.mouth, t, scale=1)
        text(canvas, "LIVE", 198, 46, 8, (255, 80, 80))


def draw_weather(canvas: pygame.Surface, v: View, t: float) -> None:
    w, h = canvas.get_size()
    canvas.fill(SKY.get(v.map_state, SKY[None]))
    # Coastline map
    pygame.draw.rect(canvas, (90, 130, 170), (40, 20, 180, 120))
    pygame.draw.polygon(canvas, (120, 150, 90), [(40, 140), (40, 70), (90, 60), (130, 90), (180, 80), (220, 110), (220, 140)])
    pygame.draw.rect(canvas, (230, 230, 230), (118, 86, 4, 4))          # the town
    text(canvas, "Port Wexley", 126, 82, 8, (10, 10, 10))
    if v.map_state in ("rain", "storm"):
        for i in range(18):
            x = 50 + (i * 37 + int(t * 120)) % 160
            y = 25 + (i * 53 + int(t * 200)) % 100
            pygame.draw.rect(canvas, (210, 220, 240), (x, y, 1, 4))
    if v.map_state == "sunny":
        pygame.draw.circle(canvas, (255, 230, 120), (200, 36), 10)
    if v.map_state in ("cloudy", "fog", "storm"):
        for i in range(3):
            pygame.draw.ellipse(canvas, (220, 220, 225), (60 + i * 50 + int(math.sin(t * 0.5 + i) * 4), 28 + i * 6, 40, 14))
    if v.temp_c is not None:
        pygame.draw.rect(canvas, (20, 20, 30), (236, 24, 70, 40))
        text(canvas, f"{v.temp_c}°C", 271, 44, 14, center=True)
        text(canvas, (v.map_state or "").upper(), 271, 58, 8, (200, 200, 120), center=True)
    pygame.draw.rect(canvas, (40, 40, 50), (0, 150, w, 30))
    draw_character(canvas, 270, 152, "weather", v.mouth if v.speaker == "weather" else 0.0, t, scale=2)
    if v.speaker == "anchor":
        draw_character(canvas, 30, 160, "anchor", v.mouth, t, scale=1)


def draw_field(canvas: pygame.Surface, v: View, t: float) -> None:
    w, h = canvas.get_size()
    sky, ground = BACKDROPS.get(v.backdrop, BACKDROPS["main_street"])
    canvas.fill(sky)
    pygame.draw.rect(canvas, ground, (0, 120, w, 60))
    for i in range(5):                                            # generic buildings / shapes
        bh = 40 + (i * 23) % 50
        pygame.draw.rect(canvas, tuple(max(0, c - 30) for c in ground), (10 + i * 62, 120 - bh, 48, bh))
    if v.backdrop == "harbour":
        pygame.draw.rect(canvas, (40, 70, 110), (0, 128, w, 52))
        for i in range(8):
            pygame.draw.rect(canvas, (90, 130, 170), (i * 42 + int(t * 10) % 42, 140 + (i % 3) * 10, 20, 1))
    draw_character(canvas, 90, 160, "reporter", v.mouth if v.speaker == "reporter" else 0.0, t, scale=2)
    draw_mic(canvas, 105, 118)
    pygame.draw.rect(canvas, (255, 60, 60), (8, 8, 28, 10))
    text(canvas, "LIVE", 22, 13, 8, center=True)


# ------------------------------------------------------------------ overlays


def draw_lower_third(canvas: pygame.Surface, v: View) -> None:
    if not v.lower_third:
        return
    title, sub = v.lower_third
    w = canvas.get_width()
    pygame.draw.rect(canvas, (200, 30, 30), (8, 128, 6, 26))
    pygame.draw.rect(canvas, (20, 20, 30), (14, 128, w - 60, 16))
    pygame.draw.rect(canvas, (240, 240, 240), (14, 144, w - 60, 10))
    text(canvas, title, 18, 131, 10, maxw=w - 70)
    text(canvas, sub, 18, 145, 8, (20, 20, 30), maxw=w - 70)


def draw_ticker(canvas: pygame.Surface, v: View, t: float) -> None:
    w, h = canvas.get_size()
    pygame.draw.rect(canvas, (10, 10, 16), (0, h - 14, w, 14))
    pygame.draw.rect(canvas, (200, 30, 30), (0, h - 14, 44, 14))
    text(canvas, "NEWS", 22, h - 7, 8, center=True)
    items = v.ticker or ["Port Wexley News, channel seven"]
    s = "   •   ".join(items) + "   •   "
    f = font(8)
    tw = f.size(s)[0] or 1
    x = 48 - int((t * 30) % tw)
    clip = canvas.get_clip()
    canvas.set_clip(pygame.Rect(46, h - 14, w - 46, 14))
    while x < w:
        canvas.blit(f.render(s, False, (230, 230, 230)), (x, h - 12))
        x += tw
    canvas.set_clip(clip)


def draw_clock(canvas: pygame.Surface, v: View) -> None:
    w = canvas.get_width()
    pygame.draw.rect(canvas, (10, 10, 16), (w - 44, 4, 40, 12))
    text(canvas, v.clock, w - 24, 10, 8, center=True)
    if v.replay:
        text(canvas, "REPLAY", w - 24, 22, 8, (255, 200, 80), center=True)


SCENES = {"filler": draw_filler, "bumper": draw_bumper, "studio": draw_studio, "weather": draw_weather, "field": draw_field}


def render(canvas: pygame.Surface, v: View, t: float, *, debug: str | None = None) -> None:
    if v.mode == "testcard":
        draw_test_card(canvas, t)
    else:
        SCENES.get(v.mode, draw_studio)(canvas, v, t)
        if v.mode not in ("bumper",):
            draw_lower_third(canvas, v)
            draw_ticker(canvas, v, t)
        draw_clock(canvas, v)
    if debug:
        text(canvas, debug, 2, 2, 8, (255, 255, 120))
