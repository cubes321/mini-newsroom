"""Drawing. Pure functions of (canvas, View, t); no I/O, no threads.

The whole frame is painted on a 320x180 canvas and scaled to the window
with nearest-neighbour, which is what gives it the pixel-art look for free.
Every scene paints the full canvas; overlays (lower third, ticker, clock)
are drawn on top by `render()`. Text is the exception: `text()` lays it out
on the canvas but draws it at the window's size, in `present()`, because an
8-pixel font scaled up three times breaks up and is hard to read.
"""
from __future__ import annotations

import math
from functools import lru_cache

import pygame

from . import backdrops, locations, logo, schedule
from .models import FIELD_REPORTERS
from .player import WAVE_WINDOWS as WAVE_BARS, View
from .sprites import draw_character, draw_mic, guest_look

CANVAS = (320, 180)
LOWER_THIRD_Y = 128                             # the banner's top edge; it runs the width of the frame
FAR_Y = LOWER_THIRD_Y + 12                      # a small figure further back in a two-shot: head and
                                                # shoulders stand clear of the banner, the rest behind it

BARS = [(192, 192, 192), (192, 192, 0), (0, 192, 192), (0, 192, 0), (192, 0, 192), (192, 0, 0), (0, 0, 192)]
SKY = {
    "sunny": (120, 180, 240), "cloudy": (150, 160, 175), "rain": (90, 100, 120), "storm": (50, 55, 70),
    "snow": (200, 205, 215), "fog": (170, 170, 170), "wind": (140, 170, 210), None: (110, 140, 200),
}

TEXT_FACE = "bahnschrift,segoeui,dejavusans,arial"     # drawn at full size, so a proper screen face
TEXT_SCALE = 1.0                # the full-size face's size against the canvas size it's laid out at
REF = 3                         # the window is the canvas this many times over (960x540)

_fonts: dict[int, "CanvasFont"] = {}
_full: dict[tuple[int, bool], pygame.font.Font] = {}
_layer: list[tuple[str, int, tuple, tuple[int, int], pygame.Rect | None]] = []   # this frame's text


def _face(px: int, bold: bool) -> pygame.font.Font:
    if (px, bold) not in _full:
        _full[px, bold] = pygame.font.SysFont(TEXT_FACE, px, bold=bold)
    return _full[px, bold]


class CanvasFont:
    """The full-size face, measured in canvas pixels, so layout stays on the 320x180 grid."""

    def __init__(self, size: int):
        self.px, self.bold = size, size >= 10

    def full(self, k: float) -> pygame.font.Font:
        return _face(max(6, round(self.px * k * TEXT_SCALE)), self.bold)

    def size(self, s: str) -> tuple[int, int]:
        w, h = self.full(REF).size(s)
        return math.ceil(w / REF), math.ceil(h / REF)

    def get_height(self) -> int:
        return math.ceil(self.full(REF).get_height() / REF)


def font(size: int) -> CanvasFont:
    if size not in _fonts:
        _fonts[size] = CanvasFont(size)
    return _fonts[size]


def queue_text(s: str, size: int, color, at: tuple[int, int], clip: pygame.Rect | None = None) -> None:
    """Draw `s` at canvas position `at` when the frame is presented, over everything on the canvas."""
    _layer.append((s, size, tuple(color), at, clip))


def present(canvas: pygame.Surface, screen: pygame.Surface) -> None:
    """Scale the canvas to `screen` and draw this frame's text on it at full size."""
    pygame.transform.scale(canvas, screen.get_size(), screen)
    k = screen.get_width() / canvas.get_width()
    for s, size, color, (x, y), clip in _layer:
        if clip:
            screen.set_clip(pygame.Rect(round(clip.x * k), round(clip.y * k), round(clip.w * k), round(clip.h * k)))
        screen.blit(font(size).full(k).render(s, True, color), (round(x * k), round(y * k)))
        if clip:
            screen.set_clip(None)


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


def clip(s: str, f: pygame.font.Font, maxw: int) -> str:
    """Cut s to fit maxw with an ellipsis, at a word break when one leaves most of the line."""
    while len(s) > 1 and f.size(s + "…")[0] > maxw:
        s = s[:-1]
    cut = s.rfind(" ")
    if cut > len(s) * 0.6:
        s = s[:cut]
    return s.rstrip(" .,;:-") + "…"


def text(canvas, s: str, x: int, y: int, size: int = 8, color=(240, 240, 240), center=False, maxw: int | None = None):
    f = font(size)
    if maxw and f.size(s)[0] > maxw:
        s = clip(s, f, maxw)
    r = pygame.Rect((0, 0), f.size(s))
    if center:
        r.center = (x, y)
    else:
        r.topleft = (x, y)
    queue_text(s, size, color, r.topleft)
    return r


# -------------------------------------------------------------------- scenes


def draw_test_card(canvas: pygame.Surface, t: float, v: View | None = None) -> None:
    """Start-up card, and the overnight card (with when programmes resume). The channel's
    roundel sits in the middle of the bars, like the circle on a real test card."""
    w, h = canvas.get_size()
    bar_w = w / len(BARS)
    for i, c in enumerate(BARS):
        pygame.draw.rect(canvas, c, (int(i * bar_w), 0, int(bar_w) + 1, int(h * 0.7)))
    pygame.draw.rect(canvas, (20, 20, 24), (0, int(h * 0.7), w, h - int(h * 0.7)))
    show = v.show if v else "news"
    pygame.draw.circle(canvas, (20, 20, 24), (w // 2, int(h * 0.35)), 30)
    logo.draw_mark(canvas, w // 2, int(h * 0.35), show, r=22, t=t)
    overnight = v is not None and v.resume_at
    if overnight:
        logo.draw_wordmark(canvas, w // 2, int(h * 0.76), show)
        text(canvas, f"PROGRAMMES RESUME AT {v.resume_at}", w // 2, int(h * 0.91), 8, (200, 200, 60), center=True)
    else:
        text(canvas, "MINI NEWSROOM", w // 2, int(h * 0.8), 14, center=True)
        if int(t * 2) % 2 == 0:
            text(canvas, "STAND BY", w // 2, int(h * 0.91), 8, (200, 200, 60), center=True)
    cx = int(w / 2 + math.cos(t) * w * 0.3)
    pygame.draw.circle(canvas, (255, 255, 255), (cx, int(h * 0.35)), 5, 1)


def draw_filler(canvas: pygame.Surface, v: View, t: float) -> None:
    w, h = canvas.get_size()
    canvas.fill((16, 24, 48))
    for i in range(0, w, 8):
        y = int(h * 0.62 + math.sin(t * 0.8 + i * 0.05) * 6)
        pygame.draw.rect(canvas, (24, 36, 70), (i, y, 8, h - y))
    logo.draw_mark(canvas, w // 2, 42, v.show, r=24, t=t)
    logo.draw_text(canvas, logo.WORDMARK, w // 2, 76, 1, gap=2, center=True)
    text(canvas, schedule.get(v.show).title, w // 2, 98, 14, center=True)
    text(canvas, "we'll be right back", w // 2, 116, 8, (180, 190, 220), center=True)
    if v.map_state:
        text(canvas, f"{v.map_state} · {v.temp_c}°C", w // 2, 130, 8, (220, 220, 160), center=True)
    pygame.draw.rect(canvas, (255, 255, 255), (w // 2 - 20 + int(math.sin(t * 3) * 18), 142, 4, 4))


_on_since: tuple[tuple, float] = ((), 0.0)


def _elapsed(v: View, t: float) -> float:
    """Seconds since this segment's picture came up: the View carries no elapsed time of
    its own, so the first frame of each (slot, mode) starts the count."""
    global _on_since
    key = (v.slot_id, v.mode, v.show)
    if _on_since[0] != key:
        _on_since = (key, t)
    return t - _on_since[1]


@lru_cache(maxsize=8)
def ident_onsets(show: str) -> list[float]:
    """The tune's note times in this show's arrangement: the ident lands a piece on each."""
    from . import jingle
    return jingle.onsets(voicing=show if show in jingle.VOICINGS else "news")


def draw_bumper(canvas: pygame.Surface, v: View, t: float) -> None:
    logo.draw_ident(canvas, _elapsed(v, t), v.show, ident_onsets(v.show))


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


LATE_LIGHT = (0.86, 0.84, 0.96)                 # the talk show's lights down: a little dimmer and cooler


def _guest(v: View, name: str | None):
    """A guest's look from their voice and role, as the player found them; by name alone otherwise."""
    return guest_look(name, *v.guests.get(name or "", ("", "", "")))


def _interview_set(v: View) -> str:
    """The Last Ferry has its own desk-and-couch set, the sport its corner of the studio; every
    other show uses the armchairs."""
    if v.set == "sports":
        return "studio_sports"
    return {"late": "studio_late", "panel": "studio_panel", "rockpool": "studio_kids"}.get(v.show, "studio_interview")


def _interview_marks(v: View) -> list[tuple[str, str | None, tuple[int, int, int, int]]]:
    """(who, guest name, mark) for each person on the interview set."""
    marks = locations.MARKS[_interview_set(v)]
    if "gully" in marks:                                        # Rock Pool: Poppy, Gully on her arm, a visitor
        seat = {"kids": "host", "gully": "gully"}
        return [(who, name, marks[seat.get(who, "guest")]) for who, name in v.people[:3]]
    if len(v.people) == 1:
        who, name = v.people[0]
        if v.show == "late" or v.set == "sports":               # the monologue, the sports desk
            return [(who, name, marks["host"])]
        return [(who, name, (160, 156, 2, 1))]                  # alone: centre stage, standing
    if len(v.people) >= 2 and "panel_1" in marks:               # The Panel: the chair and up to three
        slots = [marks["host"], marks["panel_1"], marks["panel_2"], marks["panel_3"]]
        return [(who, name, slots[i]) for i, (who, name) in enumerate(v.people[:4])]
    if len(v.people) >= 3 and "guest_far" in marks:             # the late couch: two guests
        slots = [marks["host"], marks["guest_near"], marks["guest_far"]]
        return [(who, name, slots[i]) for i, (who, name) in enumerate(v.people[:3])]
    slots = [marks["host"], marks["guest"]]
    return [(who, name, slots[i]) for i, (who, name) in enumerate(v.people[:2])]


def _speaking(v: View, who: str, name: str | None) -> bool:
    """Is this person the one talking? With two guests on the couch, the name says which."""
    return v.speaker == who and (who != "guest" or not v.guest_name or name == v.guest_name)


def _interview_wide(canvas: pygame.Surface, v: View, t: float) -> None:
    backdrops.draw(canvas, _interview_set(v))
    late = v.show == "late"
    for who, name, (x, y, scale, facing) in _interview_marks(v):
        draw_character(canvas, x, y, who, v.mouth if _speaking(v, who, name) else 0.0, t, scale=scale, facing=facing,
                       look=_guest(v, name) if who == "guest" else None, light=LATE_LIGHT if late else None)


_interview_buf: pygame.Surface | None = None


def draw_interview(canvas: pygame.Surface, v: View, t: float) -> None:
    """The interview set: a presenter and a guest, two presenters, or the talk-show host alone.
    The close shot crops round whoever is speaking, like the sofa's."""
    global _interview_buf
    mark = next((m for who, name, m in _interview_marks(v) if _speaking(v, who, name)), None)
    if v.shot == "close" and mark:
        if _interview_buf is None:
            _interview_buf = pygame.Surface(CANVAS)
        _interview_wide(_interview_buf, v, t)
        x, y = mark[:2]
        crop = pygame.Rect(0, 0, 160, 90)
        crop.midbottom = (x, y + 6)
        crop.clamp_ip(_interview_buf.get_rect())
        pygame.transform.scale(_interview_buf.subsurface(crop), CANVAS, canvas)
    else:
        _interview_wide(canvas, v, t)
    if v.caller:
        _caller_box(canvas, v)


CALLER_BOX = pygame.Rect(214, 22, 98, 50)       # top right, under the clock, clear of the armchair guest's head


def _caller_box(canvas: pygame.Surface, v: View) -> None:
    """A phone-in caller: nobody on the set, so a box with their name, where they're ringing from, and
    their voice as a waveform (the envelope that moves a face's mouth), flat while they listen."""
    box = CALLER_BOX
    pygame.draw.rect(canvas, (20, 20, 30), box.inflate(4, 4))
    pygame.draw.rect(canvas, (26, 34, 56), box)
    pygame.draw.rect(canvas, schedule.get(v.show).colour, (box.x, box.y, box.w, 11))
    text(canvas, "ON THE LINE", box.centerx, box.y + 6, 8, center=True)
    name, where = v.caller
    text(canvas, name, box.x + 4, box.y + 14, 8, maxw=box.w - 8)
    text(canvas, where, box.x + 4, box.y + 24, 8, (170, 180, 200), maxw=box.w - 8)
    mid, n = box.bottom - 10, len(v.wave)
    colour = (120, 220, 160) if any(x > 0.08 for x in v.wave) else (80, 100, 120)
    for k in range(WAVE_BARS):
        x = box.x + 4 + k * (box.w - 8) // WAVE_BARS
        val = v.wave[k - WAVE_BARS + n] if k >= WAVE_BARS - n else 0.0      # the newest on the right
        h = max(1, int(val * 8))
        pygame.draw.rect(canvas, colour, (x, mid - h, 2, 2 * h))


SOFA = locations.MARKS["studio_sofa"]
SOFA_INSET = pygame.Rect(214, 22, 98, 58)       # the handover box, top right, clear of the clock
_sofa_buf: pygame.Surface | None = None


def _sofa_marks(v: View) -> dict[str, tuple[tuple[int, int, int, int], str | None]]:
    """who -> (mark, guest name): the two hosts, and a guest in the armchair when there is one
    (a presenter booked as a guest sits there as themselves)."""
    marks = {who: (SOFA[who], None) for who in ("host_a", "host_b")}
    for who, name in v.people:
        if who not in marks:
            marks[who] = (SOFA["guest"], name)
            break
    return marks


def _sofa_wide(canvas: pygame.Surface, v: View, t: float) -> None:
    backdrops.draw(canvas, "studio_sofa")
    for who, ((x, y, scale, facing), name) in _sofa_marks(v).items():
        draw_character(canvas, x, y, who, v.mouth if v.speaker == who else 0.0, t, scale=scale, facing=facing,
                       look=_guest(v, name) if who == "guest" else None)


def draw_sofa(canvas: pygame.Surface, v: View, t: float) -> None:
    """Morning Tide on the breakfast sofa: two-shot, a close-up on whoever is talking,
    and a box with the location in it while they hand over to a field report."""
    global _sofa_buf
    marks = _sofa_marks(v)
    if v.shot == "close" and v.speaker in marks:
        if _sofa_buf is None:
            _sofa_buf = pygame.Surface(CANVAS)
        _sofa_wide(_sofa_buf, v, t)
        x, y = marks[v.speaker][0][:2]
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
    if v.set in ("interview", "sports"):
        return draw_interview(canvas, v, t)
    if v.shot == "close":
        return _studio_close(canvas, v, t)
    _studio_bg(canvas, t)
    draw_character(canvas, 110, 134, "anchor", v.mouth if v.speaker == "anchor" else 0.0, t, scale=2)
    if v.speaker in FIELD_REPORTERS:                              # anchor hands to the reporter box
        pygame.draw.rect(canvas, (20, 20, 20), (190, 40, 110, 80))
        pygame.draw.rect(canvas, (60, 90, 70), (194, 44, 102, 72))
        draw_character(canvas, 245, 112, v.speaker, v.mouth, t, scale=1)
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
        draw_character(canvas, 30, FAR_Y, v.speaker, v.mouth, t, scale=1)


def draw_field(canvas: pygame.Surface, v: View, t: float) -> None:
    """The reporter on location (Miles, or Tamsin for Full Time); when a resident speaks (a filmed
    piece, a vox pop) they take the frame."""
    backdrops.draw(canvas, v.backdrop, v.tod, v.weather, t)
    light = backdrops.person_light(v.backdrop, v.tod, v.weather)
    if v.speaker not in (None, v.reporter):        # a resident, or a presenter interviewed as themselves
        look = _guest(v, v.guest_name) if v.speaker == "guest" else None
        draw_character(canvas, 215, 156, v.speaker, v.mouth, t, scale=2, facing=-1, look=look, light=light)
        draw_character(canvas, 62, FAR_Y, v.reporter, 0.0, t, scale=1, light=light)
        draw_mic(canvas, 190, 116)
    else:
        draw_character(canvas, 90, 160, v.reporter, v.mouth if v.speaker == v.reporter else 0.0, t, scale=2,
                       light=light)
        draw_mic(canvas, 105, 118)
    if v.tag:
        w = font(8).size(v.tag)[0] + 8
        pygame.draw.rect(canvas, (255, 60, 60) if v.tag == "LIVE" else (40, 140, 150), (8, 8, w, 10))
        text(canvas, v.tag, 8 + w // 2, 13, 8, center=True)
    if v.verdict:
        _verdict_card(canvas, v.verdict)


VERDICT_CARD = pygame.Rect(176, 24, 136, 62)    # top right of the location, clear of the clock and Meg
STAR_GOLD, STAR_EMPTY = (245, 196, 60), (70, 76, 96)


def _star(canvas: pygame.Surface, cx: int, cy: int, r: int, colour) -> None:
    pts = [(cx + (r if k % 2 == 0 else r * 0.45) * math.sin(k * math.pi / 5),
            cy - (r if k % 2 == 0 else r * 0.45) * math.cos(k * math.pi / 5)) for k in range(10)]
    pygame.draw.polygon(canvas, colour, pts)


def _verdict_card(canvas: pygame.Surface, r: dict) -> None:
    """Out and About's review: the place, its stars out of five and the one-line verdict."""
    box = VERDICT_CARD
    pygame.draw.rect(canvas, (20, 20, 30), box.inflate(4, 4))
    pygame.draw.rect(canvas, (30, 40, 34), box)
    pygame.draw.rect(canvas, schedule.get("outabout").colour, (box.x, box.y, box.w, 12))
    text(canvas, r["place"], box.centerx, box.y + 6, 8, center=True, maxw=box.w - 6)
    for k in range(5):
        _star(canvas, box.x + 24 + k * 22, box.y + 24, 7, STAR_GOLD if k < r["stars"] else STAR_EMPTY)
    for i, ln in enumerate(wrap(r["verdict"], 8, box.w - 8, 2)):
        text(canvas, ln, box.centerx, box.y + 40 + i * 10, 8, (225, 230, 225), center=True)


def _title_card(v: View) -> bool:
    """A special's opening title card is up: the first chapter's first seconds."""
    return bool(v.chapter) and v.chapter.get("number") == 1 and v.chapter_age_s < 7.0


def draw_special(canvas: pygame.Surface, v: View, t: float) -> None:
    """Documentary look: letterboxed location, presenter or guest, chapter cards."""
    w, h = canvas.get_size()
    backdrops.draw(canvas, v.backdrop, v.tod, v.weather, t)
    # Slightly desaturated, moodier grade: a translucent dark wash.
    wash = pygame.Surface((w, h), pygame.SRCALPHA)
    wash.fill((10, 10, 30, 70))
    canvas.blit(wash, (0, 0))
    light = backdrops.person_light(v.backdrop, v.tod, v.weather)
    # Miles or Hugh presents; an archive clip of Miles in a history piece shows Miles.
    host = v.presenter if v.presenter in ("reporter", "historian") else "reporter"
    who = v.speaker if v.speaker in ("reporter", "historian") else host
    if v.speaker == "guest":
        draw_character(canvas, 215, 152, "guest", v.mouth, t, scale=2, facing=-1, look=_guest(v, v.guest_name),
                       light=light)
        draw_character(canvas, 62, FAR_Y, host, 0.0, t, scale=1, light=light)
        draw_mic(canvas, 72, FAR_Y - 26)
    else:
        draw_character(canvas, 90, 152, who, v.mouth if v.speaker == who else 0.0, t, scale=2, light=light)
        draw_mic(canvas, 105, 110)
    if v.archive:                                    # archive footage: black and white with a warm cast
        canvas.blit(pygame.transform.grayscale(canvas), (0, 0))
        tint = pygame.Surface((w, h), pygame.SRCALPHA)
        tint.fill((120, 90, 40, 40))
        canvas.blit(tint, (0, 0))
    # Letterbox bars
    pygame.draw.rect(canvas, (0, 0, 0), (0, 0, w, 14))
    pygame.draw.rect(canvas, (0, 0, 0), (0, h - 28, w, 14))
    if v.archive:
        pygame.draw.rect(canvas, (230, 230, 230), (w - 52, 3, 44, 9))
        text(canvas, "ARCHIVE", w - 30, 7, 8, (20, 20, 20), center=True)
    label = v.strand or "SPECIAL REPORT"
    lw = max(70, len(label) * 5 + 10)                 # the strand name can be longer than "SPECIAL REPORT"
    pygame.draw.rect(canvas, (200, 170, 60), (8, 3, lw, 9))
    text(canvas, label, 8 + lw // 2, 7, 8, (20, 20, 20), center=True)

    ch = v.chapter
    if ch:
        if _title_card(v):
            # Title card over the opening seconds
            card = pygame.Surface((w, h), pygame.SRCALPHA)
            card.fill((5, 5, 15, 225))
            canvas.blit(card, (0, 0))
            _layer.clear()                          # the card covers the strand label's words as well
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


def draw_advert(canvas: pygame.Surface, v: View, t: float) -> None:
    """A local advert: the business's own place, the owner if they're in it, and the end card.
    No lower third or ticker: it's an advert, not the news."""
    a = v.advert or {}
    backdrops.draw(canvas, v.backdrop, v.tod, v.weather, t)
    owner = a.get("owner")
    if owner:                                       # on screen throughout, talking on their own lines
        who = a.get("owner_id", "guest")
        draw_character(canvas, 250, 150, who, v.mouth if v.speaker in (who, "guest") else 0.0, t, scale=2,
                       facing=-1, look=_guest(v, owner) if who == "guest" else None,
                       light=backdrops.person_light(v.backdrop, v.tod, v.weather))
    accent = tuple(a.get("colour", (200, 60, 60)))
    card = pygame.Rect(10, 116, 196 if owner else 252, 46)
    pygame.draw.rect(canvas, (14, 16, 26), card)
    pygame.draw.rect(canvas, accent, (card.x, card.y, 5, card.h))
    pygame.draw.rect(canvas, accent, (card.x, card.bottom - 13, card.w, 13))
    text(canvas, a.get("business", ""), card.x + 11, card.y + 4, 14, maxw=card.w - 16)
    text(canvas, a.get("tagline", ""), card.x + 11, card.y + 21, 8, (215, 215, 225), maxw=card.w - 16)
    text(canvas, a.get("where", ""), card.x + 11, card.bottom - 12, 8, (16, 16, 22), maxw=card.w - 16)
    pygame.draw.rect(canvas, (235, 235, 235), (8, 8, 70, 10))
    text(canvas, "ADVERTISEMENT", 43, 13, 8, (30, 30, 36), center=True)


def draw_notice(canvas: pygame.Surface, v: View, t: float) -> None:
    """Continuity's information slide: the programme card or a notice, read by the announcer."""
    c = v.continuity or {}
    w, h = canvas.get_size()
    col = logo.colour(v.show)
    canvas.fill((14, 18, 30))
    for i in range(0, w, 8):                        # the slow sea along the foot of the slide
        y = int(h - 22 + math.sin(t * 0.7 + i * 0.06) * 3)
        pygame.draw.rect(canvas, (22, 30, 52), (i, y, 8, h - y))
    pygame.draw.rect(canvas, col, (0, 0, w, 24))
    logo.draw_mark(canvas, 16, 12, v.show, r=9, t=t)
    logo.draw_text(canvas, logo.WORDMARK, 32, 8, 1, gap=1)
    text(canvas, c.get("title", ""), w // 2, 40, 14, center=True, maxw=w - 20)
    pygame.draw.rect(canvas, col, (w // 2 - 40, 52, 80, 2))
    y = 62
    for line in c.get("lines", []):
        for row in wrap(line, 8, w - 40, 3):
            if y > h - 30:
                break
            text(canvas, row, 20, y, 8, (225, 225, 235))
            y += 11
        y += 4


# ------------------------------------------------------------------ overlays


def draw_lower_third(canvas: pygame.Surface, v: View) -> None:
    if not v.lower_third:
        return
    title, sub = v.lower_third
    w, y = canvas.get_width(), LOWER_THIRD_Y
    pygame.draw.rect(canvas, (200, 30, 30), (8, y, 6, 26))
    pygame.draw.rect(canvas, (170, 16, 22) if v.breaking else (20, 20, 30), (14, y, w - 60, 16))
    pygame.draw.rect(canvas, (240, 240, 240), (14, y + 16, w - 60, 10))
    size = 10 if font(10).size(title)[0] <= w - 70 else 8     # a long headline drops a size first
    text(canvas, title, 18, y + 3 if size == 10 else y + 4, size, maxw=w - 70)
    text(canvas, sub, 18, y + 17, 8, (20, 20, 30), maxw=w - 70)


def draw_ticker(canvas: pygame.Surface, v: View, t: float) -> None:
    w, h = canvas.get_size()
    pygame.draw.rect(canvas, (10, 10, 16), (0, h - 14, w, 14))
    show = schedule.get(v.show)
    if v.breaking and int(t * 2) % 2 == 0:
        pygame.draw.rect(canvas, (230, 40, 40), (0, h - 14, 44, 14))
    else:
        pygame.draw.rect(canvas, show.colour, (0, h - 14, 44, 14))
    label = "BREAKING" if v.breaking else show.ticker
    size = next((n for n in (8, 7) if font(n).size(label)[0] <= 42), 6)      # COASTWIDE is a long word
    text(canvas, label, 22, h - 7, size, center=True, maxw=42)
    items = v.ticker or [f"{show.title.title()}, channel seven"]
    s = "   •   ".join(items) + "   •   "
    f = font(8)
    tw = f.size(s)[0] or 1
    x = 48 - int((t * 30) % tw)
    band = pygame.Rect(46, h - 14, w - 46, 14)
    while x < w:
        queue_text(s, 8, (230, 230, 230), (x, h - 7 - f.get_height() // 2), band)
        x += tw


def draw_clock(canvas: pygame.Surface, v: View) -> None:
    w = canvas.get_width()
    pygame.draw.rect(canvas, (10, 10, 16), (w - 44, 4, 40, 12))
    text(canvas, v.clock, w - 24, 10, 8, center=True)
    if v.replay or v.repeat:
        text(canvas, "REPEAT" if v.repeat else "REPLAY", w - 24, 22, 8, (255, 200, 80), center=True)


SCENES = {"filler": draw_filler, "bumper": draw_bumper, "studio": draw_studio, "weather": draw_weather,
          "field": draw_field, "special": draw_special, "breaking": draw_breaking,
          "advert": draw_advert, "ident": draw_bumper, "notice": draw_notice}


PROGRAMMES = ("studio", "weather", "field", "special")


def shows_bug(v: View) -> bool:
    """The corner logo is up during programmes: not on idents, breaking news, the test card,
    the filler, adverts, or a special's title card."""
    return v.mode in PROGRAMMES and not v.breaking and not (v.mode == "special" and _title_card(v))


def render(canvas: pygame.Surface, v: View, t: float, *, debug: str | None = None) -> None:
    _layer.clear()
    if v.mode == "testcard":
        draw_test_card(canvas, t, v)
        if v.resume_at:
            draw_clock(canvas, v)
    else:
        SCENES.get(v.mode, draw_studio)(canvas, v, t)
        if v.mode not in ("bumper", "breaking", "advert", "ident", "notice"):
            draw_lower_third(canvas, v)
            draw_ticker(canvas, v, t)
        if shows_bug(v):
            logo.draw_bug(canvas)
        draw_clock(canvas, v)
    if debug:
        # Bottom-left, between the lower third and the ticker, clear of scene tags.
        text(canvas, debug, 2, canvas.get_height() - 24, 8, (255, 255, 120))
