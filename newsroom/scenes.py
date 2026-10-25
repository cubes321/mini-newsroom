"""Drawing. Pure functions of (canvas, View, t); no I/O, no threads.

The whole frame is painted on a 320x180 canvas and scaled to the window
with nearest-neighbour, which is what gives it the pixel-art look for free.
Every scene paints the full canvas; overlays (lower third, ticker, clock)
are drawn on top by `render()`.
"""
from __future__ import annotations

import math

import pygame

from . import backdrops, locations, schedule
from .player import View
from .sprites import draw_character, draw_mic, guest_palette

CANVAS = (320, 180)

BARS = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]
SKY = {
    "sunny": (120, 180, 240), "cloudy": (150, 160, 175), "rain": (90, 100, 120), "storm": (50, 55, 70),
    "snow": (200, 205, 215), "fog": (170, 170, 170), "wind": (140, 170, 210), None: (110, 140, 200),
}

_fonts: dict[int, pygame.font.Font] = {}


def font(size: int) -> pygame.font.Font:
    if size not in _fonts:
        _fonts[size] = pygame.font.SysFont("consolas,couriernew,monospace", size, bold=size >= 10)
    return _fonts[size]


def wrap(s: str, size: int, maxw: int, max_lines: int = 3) -> list[str]:
    """Greedy word wrap for the pixel font; last line gets an ellipsis if it still overflows."""
    f = font(size)
    lines, cur = [], ""
    for word in s.split():
        trial = f"{cur} {word}".strip()
        if f.size(trial)[0] <= maxw or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    if len(lines) > max_lines:
        lines = lines[:max_lines]
        lines[-1] = lines[-1].rstrip(".,;") + "…"
    return lines


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


def draw_test_card(canvas: pygame.Surface, t: float, v: View | None = None) -> None:
    """Start-up card, and the overnight card (with when programmes resume)."""
    w, h = canvas.get_size()
    bar_w = w / len(BARS)
    for i, c in enumerate(BARS):
        pygame.draw.rect(canvas, c, (int(i * bar_w), 0, int(bar_w) + 1, int(h * 0.7)))
    pygame.draw.rect(canvas, (20, 20, 24), (0, int(h * 0.7), w, h - int(h * 0.7)))
    overnight = v is not None and v.resume_at
    text(canvas, "CHANNEL 7" if overnight else "MINI NEWSROOM", w // 2, int(h * 0.8), 14, center=True)
    if overnight:
        text(canvas, f"PROGRAMMES RESUME AT {v.resume_at}", w // 2, int(h * 0.91), 8, (200, 200, 60), center=True)
    elif int(t * 2) % 2 == 0:
        text(canvas, "STAND BY", w // 2, int(h * 0.91), 8, (200, 200, 60), center=True)
    cx = int(w / 2 + math.cos(t) * w * 0.3)
    pygame.draw.circle(canvas, (255, 255, 255), (cx, int(h * 0.35)), 5, 1)


def draw_filler(canvas: pygame.Surface, v: View, t: float) -> None:
    w, h = canvas.get_size()
    canvas.fill((16, 24, 48))
    for i in range(0, w, 8):
        y = int(h * 0.55 + math.sin(t * 0.8 + i * 0.05) * 6)
        pygame.draw.rect(canvas, (24, 36, 70), (i, y, 8, h - y))
    text(canvas, schedule.get(v.show).title, w // 2, 50, 14, center=True)
    text(canvas, "we'll be right back", w // 2, 72, 8, (180, 190, 220), center=True)
    if v.map_state:
        text(canvas, f"{v.map_state} · {v.temp_c}°C", w // 2, 92, 8, (220, 220, 160), center=True)
    pygame.draw.rect(canvas, (255, 255, 255), (w // 2 - 20 + int(math.sin(t * 3) * 18), 110, 4, 4))


def draw_bumper(canvas: pygame.Surface, v: View, t: float) -> None:
    w, h = canvas.get_size()
    show = schedule.get(v.show)
    canvas.fill(show.colour)
    if show.id == "breakfast":                                   # the sun coming up behind the card
        pygame.draw.circle(canvas, (255, 220, 120), (w // 2, int(150 - min(t % 12, 4) * 12)), 34)
    k = int((t * 60) % (w + 40)) - 40
    pygame.draw.rect(canvas, (240, 240, 240), (k, 0, 16, h))
    pygame.draw.rect(canvas, (30, 30, 40), (40, 60, w - 80, 60))
    text(canvas, "CHANNEL 7", w // 2, 78, 14, center=True)
    text(canvas, show.title, w // 2, 102, 8, (255, 220, 190), center=True)


def draw_breaking(canvas: pygame.Surface, v: View, t: float) -> None:
    """The card over the breaking sting: red, flashing, with the story's caption."""
    w, h = canvas.get_size()
    canvas.fill((150, 10, 16))
    for i in range(0, w + h, 24):                                 # diagonal stripes, moving
        x = i - int(t * 40) % 24
        pygame.draw.line(canvas, (175, 20, 26), (x, 0), (x - h, h), 8)
    pygame.draw.rect(canvas, (20, 10, 12), (0, 52, w, 56))
    if int(t * 3) % 2 == 0:
        text(canvas, "BREAKING NEWS", w // 2, 70, 14, center=True)
    else:
        text(canvas, "BREAKING NEWS", w // 2, 70, 14, (255, 210, 80), center=True)
    title = v.lower_third[0] if v.lower_third else ""
    for k, ln in enumerate(wrap(title, 8, w - 40, 2)):
        text(canvas, ln, w // 2, 90 + k * 10, 8, (240, 230, 230), center=True)
    text(canvas, "PORT WEXLEY NEWS", w // 2, 130, 8, (255, 200, 200), center=True)


def _studio_bg(canvas: pygame.Surface, t: float) -> None:
    backdrops.draw(canvas, "studio_wide")
    if not backdrops.has_art("studio_wide"):
        for i in range(6):                                        # the placeholder's back-wall screens
            pygame.draw.rect(canvas, (70, 110, 180), (16 + i * 50, 34 + int(math.sin(t + i) * 2), 32, 20))


CLOSE_CROP = pygame.Rect(50, 45, 160, 90)      # a 2x zoom on the anchor's end of the desk
WALL_SCREEN = pygame.Rect(40, 20, 180, 120)    # the weather wall's big screen
WALL_PANEL = pygame.Rect(234, 20, 76, 124)
_studio_buf: pygame.Surface | None = None


def _studio_close(canvas: pygame.Surface, v: View, t: float) -> None:
    """The desk shot again through a tighter lens: paint wide, crop, scale 2x."""
    global _studio_buf
    if _studio_buf is None:
        _studio_buf = pygame.Surface(CANVAS)
    _studio_bg(_studio_buf, t)
    pygame.transform.scale(_studio_buf.subsurface(CLOSE_CROP), CANVAS, canvas)
    draw_character(canvas, (110 - CLOSE_CROP.x) * 2, (134 - CLOSE_CROP.y) * 2, "anchor", v.mouth, t, scale=4)


def _studio_wall(canvas: pygame.Surface, v: View, t: float) -> None:
    """The anchor at the big wall, the story's location up on the screen."""
    backdrops.draw(canvas, "weather_wall")
    canvas.blit(backdrops.picture(v.backdrop, v.tod, v.weather, WALL_SCREEN.size), WALL_SCREEN)
    pygame.draw.rect(canvas, (20, 20, 30), WALL_PANEL)
    tag = (200, 30, 30) if v.wall_label == "LIVE" else (200, 170, 60)
    pygame.draw.rect(canvas, tag, (WALL_PANEL.x + 4, WALL_PANEL.y + 6, WALL_PANEL.w - 8, 12))
    text(canvas, v.wall_label, WALL_PANEL.centerx, WALL_PANEL.y + 12, 8, center=True, maxw=WALL_PANEL.w - 10)
    y = WALL_PANEL.y + 24
    name = locations.get(v.backdrop).name
    for ln in wrap(name[:1].upper() + name[1:], 8, WALL_PANEL.w - 8, 3):
        text(canvas, ln, WALL_PANEL.x + 4, y, 8, (220, 220, 230))
        y += 10
    who = v.presenter or "anchor"
    draw_character(canvas, 270, 152, who, v.mouth if v.speaker == who else 0.0, t, scale=2)


INTERVIEW = locations.MARKS["studio_interview"]
_night: pygame.Surface | None = None


def _night_look() -> pygame.Surface:
    """The interview set after ten: lights down, the floor lamp and a pool of light on the chairs."""
    global _night
    if _night is None:
        _night = pygame.Surface(CANVAS, pygame.SRCALPHA)
        _night.fill((6, 6, 24, 150))
        for (cx, cy), radius, floor in (((305, 60), 50, 40), ((160, 128), 100, 30)):    # lamp, then the chairs
            for r in range(radius, 0, -2):                      # soft-edged: alpha falls towards the centre
                alpha = int(floor + (150 - floor) * (r / radius) ** 2)
                pygame.draw.circle(_night, (6, 6, 24, alpha), (cx, cy), r)
    return _night


def _interview_marks(v: View) -> list[tuple[str, str | None, tuple[int, int, int, int]]]:
    """(who, guest name, mark) for each person on the interview set."""
    if len(v.people) == 1:                                      # alone: centre stage, standing
        who, name = v.people[0]
        return [(who, name, (160, 156, 2, 1))]
    slots = [INTERVIEW["host"], INTERVIEW["guest"]]
    return [(who, name, slots[i]) for i, (who, name) in enumerate(v.people[:2])]


def _interview_wide(canvas: pygame.Surface, v: View, t: float) -> None:
    backdrops.draw(canvas, "studio_interview")
    if v.show == "late":
        canvas.blit(_night_look(), (0, 0))
    for who, name, (x, y, scale, facing) in _interview_marks(v):
        palette = guest_palette(name) if who == "guest" else None
        draw_character(canvas, x, y, who, v.mouth if v.speaker == who else 0.0, t,
                       scale=scale, facing=facing, palette=palette)


_interview_buf: pygame.Surface | None = None


def draw_interview(canvas: pygame.Surface, v: View, t: float) -> None:
    """The interview set: a presenter and a guest, two presenters, or the talk-show host alone.
    The close shot crops round whoever is speaking, like the sofa's."""
    global _interview_buf
    marks = {who: m for who, _, m in _interview_marks(v)}
    if v.shot == "close" and v.speaker in marks:
        if _interview_buf is None:
            _interview_buf = pygame.Surface(CANVAS)
        _interview_wide(_interview_buf, v, t)
        x, y = marks[v.speaker][:2]
        crop = pygame.Rect(0, 0, 160, 90)
        crop.midbottom = (x, y + 6)
        crop.clamp_ip(_interview_buf.get_rect())
        pygame.transform.scale(_interview_buf.subsurface(crop), CANVAS, canvas)
        return
    _interview_wide(canvas, v, t)


SOFA = locations.MARKS["studio_sofa"]
SOFA_INSET = pygame.Rect(214, 22, 98, 58)       # the handover box, top right, clear of the clock
_sofa_buf: pygame.Surface | None = None


def _sofa_wide(canvas: pygame.Surface, v: View, t: float) -> None:
    backdrops.draw(canvas, "studio_sofa")
    for who in ("host_a", "host_b"):
        x, y, scale, facing = SOFA[who]
        draw_character(canvas, x, y, who, v.mouth if v.speaker == who else 0.0, t, scale=scale, facing=facing)


def draw_sofa(canvas: pygame.Surface, v: View, t: float) -> None:
    """Morning Tide on the breakfast sofa: two-shot, a close-up on whoever is talking,
    and a box with the location in it while they hand over to a field report."""
    global _sofa_buf
    if v.shot == "close" and v.speaker in SOFA:
        if _sofa_buf is None:
            _sofa_buf = pygame.Surface(CANVAS)
        _sofa_wide(_sofa_buf, v, t)
        x, y = SOFA[v.speaker][:2]
        crop = pygame.Rect(0, 0, 160, 90)
        crop.midbottom = (x, y + 6)            # head room above, the sofa cushion below
        crop.clamp_ip(_sofa_buf.get_rect())
        pygame.transform.scale(_sofa_buf.subsurface(crop), CANVAS, canvas)
        return
    _sofa_wide(canvas, v, t)
    if v.shot == "wall" and v.backdrop:
        pygame.draw.rect(canvas, (20, 20, 30), SOFA_INSET.inflate(4, 4))
        canvas.blit(backdrops.picture(v.backdrop, v.tod, v.weather, SOFA_INSET.size), SOFA_INSET)
        pygame.draw.rect(canvas, (200, 30, 30), (SOFA_INSET.x + 3, SOFA_INSET.y + 3, 26, 10))
        text(canvas, v.wall_label or "LIVE", SOFA_INSET.x + 16, SOFA_INSET.y + 8, 8, center=True)


def draw_studio(canvas: pygame.Surface, v: View, t: float) -> None:
    if v.show == "breakfast":
        return draw_sofa(canvas, v, t)
    if v.shot == "wall":
        return _studio_wall(canvas, v, t)
    if v.set == "interview":
        return draw_interview(canvas, v, t)
    if v.shot == "close":
        return _studio_close(canvas, v, t)
    _studio_bg(canvas, t)
    draw_character(canvas, 110, 134, "anchor", v.mouth if v.speaker == "anchor" else 0.0, t, scale=2)
    if v.speaker == "reporter":                                   # anchor hands to the reporter box
        pygame.draw.rect(canvas, (20, 20, 20), (190, 40, 110, 80))
        pygame.draw.rect(canvas, (60, 90, 70), (194, 44, 102, 72))
        draw_character(canvas, 245, 112, "reporter", v.mouth, t, scale=1)
        text(canvas, "PHONE" if v.breaking else "LIVE", 198, 46, 8, (255, 80, 80))


def draw_weather(canvas: pygame.Surface, v: View, t: float) -> None:
    backdrops.draw(canvas, "weather_wall")
    pygame.draw.rect(canvas, SKY.get(v.map_state, SKY[None]), (234, 20, 76, 124))   # side panel
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
    draw_character(canvas, 270, 152, "weather", v.mouth if v.speaker == "weather" else 0.0, t, scale=2)
    if v.speaker not in (None, "weather"):                       # whoever handed over, small at the left
        draw_character(canvas, 30, 160, v.speaker, v.mouth, t, scale=1)


def draw_field(canvas: pygame.Surface, v: View, t: float) -> None:
    """Miles on location; when a resident speaks (a filmed piece, a vox pop) they take the frame."""
    backdrops.draw(canvas, v.backdrop, v.tod, v.weather, t)
    if v.speaker not in (None, "reporter"):        # a resident, or a presenter interviewed as themselves
        palette = guest_palette(v.guest_name) if v.speaker == "guest" else None
        draw_character(canvas, 215, 156, v.speaker, v.mouth, t, scale=2, palette=palette)
        draw_character(canvas, 62, 152, "reporter", 0.0, t, scale=1)
        draw_mic(canvas, 190, 116)
    else:
        draw_character(canvas, 90, 160, "reporter", v.mouth if v.speaker == "reporter" else 0.0, t, scale=2)
        draw_mic(canvas, 105, 118)
    if v.tag:
        w = font(8).size(v.tag)[0] + 8
        pygame.draw.rect(canvas, (255, 60, 60) if v.tag == "LIVE" else (40, 140, 150), (8, 8, w, 10))
        text(canvas, v.tag, 8 + w // 2, 13, 8, center=True)


def draw_special(canvas: pygame.Surface, v: View, t: float) -> None:
    """Documentary look: letterboxed location, presenter or guest, chapter cards."""
    w, h = canvas.get_size()
    backdrops.draw(canvas, v.backdrop, v.tod, v.weather, t)
    # Slightly desaturated, moodier grade: a translucent dark wash.
    wash = pygame.Surface((w, h), pygame.SRCALPHA)
    wash.fill((10, 10, 30, 70))
    canvas.blit(wash, (0, 0))
    if v.speaker == "guest":
        draw_character(canvas, 215, 152, "guest", v.mouth, t, scale=2, palette=guest_palette(v.guest_name))
        draw_character(canvas, 62, 148, "reporter", 0.0, t, scale=1)
        draw_mic(canvas, 72, 122)
    else:
        draw_character(canvas, 90, 152, "reporter", v.mouth if v.speaker == "reporter" else 0.0, t, scale=2)
        draw_mic(canvas, 105, 110)
    # Letterbox bars
    pygame.draw.rect(canvas, (0, 0, 0), (0, 0, w, 14))
    pygame.draw.rect(canvas, (0, 0, 0), (0, h - 28, w, 14))
    pygame.draw.rect(canvas, (200, 170, 60), (8, 3, 70, 9))
    text(canvas, "SPECIAL REPORT", 43, 7, 8, (20, 20, 20), center=True)

    ch = v.chapter
    if ch:
        if ch.get("number") == 1 and v.chapter_age_s < 7.0:
            # Title card over the opening seconds
            card = pygame.Surface((w, h), pygame.SRCALPHA)
            card.fill((5, 5, 15, 225))
            canvas.blit(card, (0, 0))
            text(canvas, "A PORT WEXLEY NEWS SPECIAL", w // 2, 46, 8, (200, 170, 60), center=True)
            y = 66
            for ln in wrap(ch.get("title", ""), 14, w - 24, 2):
                text(canvas, ln, w // 2, y, 14, center=True)
                y += 18
            y += 6
            for ln in wrap(ch.get("standfirst", ""), 8, w - 40, 3):
                text(canvas, ln, w // 2, y, 8, (200, 200, 210), center=True)
                y += 11
        elif v.chapter_age_s < 6.0:
            slide = min(1.0, v.chapter_age_s / 0.4)
            x = int(-120 + 128 * slide)
            pygame.draw.rect(canvas, (200, 170, 60), (x, 22, 120, 18))
            text(canvas, f"PART {ch.get('number')}", x + 6, 25, 8, (20, 20, 20))
            text(canvas, ch.get("heading", ""), x + 6, 33, 8, (20, 20, 20), maxw=110)


# ------------------------------------------------------------------ overlays


def draw_lower_third(canvas: pygame.Surface, v: View) -> None:
    if not v.lower_third:
        return
    title, sub = v.lower_third
    w = canvas.get_width()
    pygame.draw.rect(canvas, (200, 30, 30), (8, 128, 6, 26))
    pygame.draw.rect(canvas, (170, 16, 22) if v.breaking else (20, 20, 30), (14, 128, w - 60, 16))
    pygame.draw.rect(canvas, (240, 240, 240), (14, 144, w - 60, 10))
    text(canvas, title, 18, 131, 10, maxw=w - 70)
    text(canvas, sub, 18, 145, 8, (20, 20, 30), maxw=w - 70)


def draw_ticker(canvas: pygame.Surface, v: View, t: float) -> None:
    w, h = canvas.get_size()
    pygame.draw.rect(canvas, (10, 10, 16), (0, h - 14, w, 14))
    show = schedule.get(v.show)
    if v.breaking and int(t * 2) % 2 == 0:
        pygame.draw.rect(canvas, (230, 40, 40), (0, h - 14, 44, 14))
    else:
        pygame.draw.rect(canvas, show.colour, (0, h - 14, 44, 14))
    text(canvas, "BREAKING" if v.breaking else show.ticker, 22, h - 7, 8, center=True, maxw=42)
    items = v.ticker or [f"{show.title.title()}, channel seven"]
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
    if v.replay or v.repeat:
        text(canvas, "REPEAT" if v.repeat else "REPLAY", w - 24, 22, 8, (255, 200, 80), center=True)


SCENES = {"filler": draw_filler, "bumper": draw_bumper, "studio": draw_studio, "weather": draw_weather,
          "field": draw_field, "special": draw_special, "breaking": draw_breaking}


def render(canvas: pygame.Surface, v: View, t: float, *, debug: str | None = None) -> None:
    if v.mode == "testcard":
        draw_test_card(canvas, t, v)
        if v.resume_at:
            draw_clock(canvas, v)
    else:
        SCENES.get(v.mode, draw_studio)(canvas, v, t)
        if v.mode not in ("bumper", "breaking"):
            draw_lower_third(canvas, v)
            draw_ticker(canvas, v, t)
        draw_clock(canvas, v)
    if debug:
        # Bottom-left, between the lower third and the ticker, clear of scene tags.
        text(canvas, debug, 2, canvas.get_height() - 24, 8, (255, 255, 120))
