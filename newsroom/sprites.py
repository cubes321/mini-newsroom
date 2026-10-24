"""Programmatic pixel characters.

Everything is drawn onto a low-resolution canvas (see scenes.CANVAS) and
scaled up with nearest-neighbour, so a 2x3 rectangle here is a chunky
pixel block on screen. Real sprite sheets can replace these later by
keeping the same `draw_character(canvas, x, y, who, mouth, t)` signature.
"""
from __future__ import annotations

import math

import pygame

PALETTES = {
    # skin, hair, jacket, shirt
    "anchor":   ((232, 190, 160), (60, 40, 30), (40, 60, 110), (240, 240, 240)),
    "weather":  ((210, 170, 140), (120, 120, 120), (90, 110, 70), (255, 230, 150)),
    "reporter": ((150, 100, 70), (20, 20, 20), (120, 60, 50), (230, 230, 230)),
}


def draw_character(canvas: pygame.Surface, x: int, y: int, who: str, mouth: float, t: float,
                   *, scale: int = 1, facing: int = 1) -> None:
    """Head-and-shoulders character with feet at (x, y) baseline. mouth in 0..1."""
    skin, hair, jacket, shirt = PALETTES.get(who, PALETTES["anchor"])
    s = scale
    bob = int(round(math.sin(t * 2.0) * 0.6))                 # idle breathing
    head_w, head_h = 14 * s, 14 * s
    body_w, body_h = 26 * s, 20 * s

    bx = x - body_w // 2
    by = y - body_h
    # Shoulders / jacket
    pygame.draw.rect(canvas, jacket, (bx, by + bob, body_w, body_h))
    # Shirt / tie triangle
    pygame.draw.polygon(canvas, shirt, [(x - 4 * s, by + bob), (x + 4 * s, by + bob), (x, by + 9 * s + bob)])
    # Neck
    pygame.draw.rect(canvas, skin, (x - 3 * s, by - 3 * s + bob, 6 * s, 4 * s))
    # Head
    hx, hy = x - head_w // 2, by - 3 * s - head_h + bob
    pygame.draw.rect(canvas, skin, (hx, hy, head_w, head_h))
    # Hair
    pygame.draw.rect(canvas, hair, (hx, hy, head_w, 4 * s))
    pygame.draw.rect(canvas, hair, (hx, hy, 2 * s, 8 * s))
    # Eyes (blink every ~4 s)
    blink = (t % 4.0) > 3.85
    eye_h = 1 * s if blink else 2 * s
    ex = x - 4 * s if facing > 0 else x - 5 * s
    pygame.draw.rect(canvas, (20, 20, 30), (ex, hy + 6 * s, 2 * s, eye_h))
    pygame.draw.rect(canvas, (20, 20, 30), (ex + 6 * s, hy + 6 * s, 2 * s, eye_h))
    # Mouth: height follows the audio envelope
    mh = max(1 * s, int(round(mouth * 5 * s)))
    pygame.draw.rect(canvas, (120, 40, 50), (x - 3 * s, hy + 10 * s, 6 * s, mh))


def draw_mic(canvas: pygame.Surface, x: int, y: int) -> None:
    pygame.draw.rect(canvas, (40, 40, 40), (x, y, 3, 10))
    pygame.draw.rect(canvas, (90, 90, 90), (x - 1, y - 4, 5, 5))
