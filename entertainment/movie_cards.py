"""The TV movie's opening titles and end credits (entertainment/movies.py): two items of their own, either side of the
scenes, each with its own music and drawn whole-frame by the scenes (scenes.SCENES, no clock, no bug).

Opening titles, one pass of the music (about 22 seconds): "CHANNEL 8 presents" on black, then the first scene's place,
empty, fading up, and the title written across it in the logo's lettering, then down to black for scene one.
End credits, two passes (about 44 seconds): a crawl of the cast (each part and who they are), the places it was
filmed, the writing and the music, ending on Channel 8's card, held, then down to black.

The music is the station's strings bed (jingle.bed "strings": a string pad, harp and the tune on the glockenspiel),
cut to the passes that carry a melody; provisional until chosen by ear (2026-11-23)."""
from __future__ import annotations

from datetime import date
from pathlib import Path

import numpy as np

TITLES_MODE, CREDITS_MODE = "movie_titles", "movie_credits"
THEME_STYLE = "strings"


# ------------------------------------------------------------------ the music

def _pass_s() -> float:
    from newsroom import jingle

    bpm, _ = jingle.BED_TEMPO[THEME_STYLE]
    return len(jingle.BED_CHORDS) * 4 * 60.0 / bpm


def theme_dir() -> Path:
    """Beside the films (data/movies/_theme), out of the cache the station prunes: rendered once, about half a minute."""
    from .movies import bank_dir

    return bank_dir() / "_theme"


def ensure_theme(cache: Path | None = None) -> tuple[Path, Path]:
    """The titles' music (the bed's second pass, the station tune and its answer) and the credits' (its third and
    fourth), faded, in `cache` (theme_dir() by default); rendered once."""
    import soundfile as sf

    from newsroom import jingle

    cache = cache or theme_dir()
    titles, credits = cache / "_movie_titles.wav", cache / "_movie_credits.wav"
    if titles.exists() and credits.exists():
        return titles, credits
    audio = jingle.bed(THEME_STYLE, passes=4)
    n = int(round(_pass_s() * jingle.SR))

    def faded(x: np.ndarray, fade_in: float, fade_out: float) -> np.ndarray:
        x = x.copy()
        a, b = (min(int(s * jingle.SR), len(x) // 2) for s in (fade_in, fade_out))
        x[:a] *= np.linspace(0, 1, a)[:, None]
        x[-b:] *= np.linspace(1, 0, b)[:, None]
        return x

    cache.mkdir(parents=True, exist_ok=True)
    sf.write(titles, faded(audio[n:2 * n], 0.4, 2.5), jingle.SR, subtype="PCM_16")
    sf.write(credits, faded(audio[2 * n:4 * n], 0.4, 4.0), jingle.SR, subtype="PCM_16")
    return titles, credits


# ------------------------------------------------------------------ the items

def _segment(slot: int, show: str, wav: Path, card: dict):
    import soundfile as sf

    from newsroom.models import Line, Segment, SegmentState, SegmentType

    info = sf.info(str(wav))
    card["duration_s"] = info.frames / info.samplerate
    line = Line(speaker="guest", text="", wav_path=wav, duration_s=card["duration_s"], mouth_env=[])
    # A bumper, so the station's bed stays silent under the film's own music (player._play_line).
    return Segment(slot_id=slot, type=SegmentType.bumper, show=show, state=SegmentState.ready,
                   headline=card["card"].title(), lines=[line], part=card["card"], work={"card": card})


def titles_segment(slot: int, show: str, title: str, first: dict, cache: Path | None = None):
    """`first`: the first scene (its set and its when), shown empty behind the title."""
    from .movies import TOD

    wav, _ = ensure_theme(cache)
    return _segment(slot, show, wav, {"card": "titles", "title": title, "set": first["set"],
                                      "tod": TOD.get(first.get("when", "day"), "day")})


def role(who: str) -> str:
    """The credits' few words for a part: "The young auctioneer, who took..." -> "the young auctioneer"; a one-word
    lead-in is skipped ("Twenty-three, the Wren's barmaid, ..." -> "the Wren's barmaid"). A part's own `credit` in
    cast.toml wins over this (credits_segment)."""
    clauses = [c.strip() for c in who.split(".")[0].split(" who ")[0].split(",")]
    first = next((c for c in clauses if len(c.split()) > 1), clauses[0])
    for art in ("The ", "A ", "An "):
        if first.startswith(art):
            first = art.lower() + first[len(art):]
    return first


def credits_segment(slot: int, show: str, title: str, cast: dict, sets: list[str], cache: Path | None = None,
                    year: int | None = None):
    """`cast`: cast.toml's parts, in billing order; `sets`: the set ids, in the order the film first goes there."""
    from .movies import SETS

    _, wav = ensure_theme(cache)
    places = []
    for sid in sets:
        name = SETS.get(sid, (sid.replace("_", " "),))[0]
        name = name[4:] if name.startswith("the ") else name
        if name.capitalize() not in places:
            places.append(name.capitalize())
    return _segment(slot, show, wav, {"card": "credits", "title": title, "year": year or date.today().year,
                                      "cast": [[n, c.get("credit") or role(c.get("who", ""))] for n, c in cast.items()],
                                      "places": places})


# ------------------------------------------------------------------ drawing

def _black(canvas, alpha: float) -> None:
    import pygame

    if alpha <= 0:
        return
    s = pygame.Surface(canvas.get_size(), pygame.SRCALPHA)
    s.fill((0, 0, 0, max(0, min(255, int(alpha)))))
    canvas.blit(s, (0, 0))


def _ramp(t: float, start: float, length: float) -> float:
    return max(0.0, min(1.0, (t - start) / length))


def _dim(col, k: float):
    return tuple(int(c * k) for c in col)


def _fits_logo(s: str) -> bool:
    from newsroom import logo

    return all(ch in logo.GLYPHS for ch in s.upper())


def _title_lines(title: str) -> tuple[list[str], int]:
    """The title in the logo's lettering: the biggest scale that fits, on two lines if one won't."""
    from newsroom import logo

    up = title.upper()
    for scale in (4, 3, 2):
        if logo.text_width(up, scale) <= 296:
            return [up], scale
    words = up.split()
    best = min(range(1, len(words)), key=lambda i: abs(len(" ".join(words[:i])) - len(" ".join(words[i:]))))
    lines = [" ".join(words[:best]), " ".join(words[best:])]
    for scale in (3, 2):
        if max(logo.text_width(ln, scale) for ln in lines) <= 296:
            return lines, scale
    return lines, 1


CREAM_TEXT, GOLD, GREY = (240, 232, 214), (214, 190, 130), (180, 180, 190)


def draw_titles(canvas, v, t: float) -> None:
    from newsroom import backdrops, channel, logo, scenes

    c = v.scene or {}
    w, h = canvas.get_size()
    e = scenes._elapsed(v, t)
    canvas.fill((0, 0, 0))
    if e < 5.4:                                          # CHANNEL 8 presents, on black
        k = _ramp(e, 0.6, 0.5) * (1 - _ramp(e, 4.3, 0.8))
        if k <= 0:
            return
        word = f"CHANNEL {channel.CURRENT.number}"
        logo.draw_text(canvas, word, w // 2, 70, 3, _dim(logo.CREAM, k), center=True, reveal=_ramp(e, 0.6, 0.7))
        if e > 1.7:
            scenes.text(canvas, "presents", w // 2, 102, 8, _dim(GOLD, k * _ramp(e, 1.7, 0.6)), center=True)
        return
    backdrops.draw(canvas, c.get("set"), c.get("tod", "day"), None, t)
    lines, scale = _title_lines(c.get("title", ""))
    line_h = 7 * scale + 2 * scale
    block = line_h * len(lines) - 2 * scale
    top = h // 2 - block // 2 - 6
    band = _ramp(e, 8.0, 0.8)
    if band:
        import pygame

        s = pygame.Surface((w, block + 30), pygame.SRCALPHA)
        s.fill((0, 0, 0, int(130 * band)))
        canvas.blit(s, (0, top - 12))
    if _fits_logo(c.get("title", "")):
        for i, ln in enumerate(lines):
            logo.draw_text(canvas, ln, w // 2, top + i * line_h, scale, logo.CREAM, center=True, shadow=(30, 24, 20),
                           reveal=_ramp(e, 8.2 + 0.25 * i, 1.2))
    elif e > 8.2:
        for i, ln in enumerate(lines):
            scenes.text(canvas, ln.title(), w // 2, top + i * line_h + 6, 14, CREAM_TEXT, center=True)
    fade_in, fade_out = 1 - _ramp(e, 5.4, 1.6), _ramp(e, 18.8, 2.4)
    _black(canvas, 255 * max(fade_in, fade_out))
    if 10.6 < e and fade_out < 0.15:
        scenes.text(canvas, f"A Channel {channel.CURRENT.number} film", w // 2, top + block + 10, 8, GOLD, center=True)
    for i in range(2):                                    # the film's letterbox
        canvas.fill((0, 0, 0), (0, 0 if i == 0 else h - 16, w, 16))


def _credit_rows(c: dict) -> tuple[list[tuple[str, int, tuple, int]], int]:
    """(text, size, colour, y) rows in crawl order, and the y of the last card's middle, which is held centred."""
    from newsroom import channel

    rows, y = [], 0

    def add(s: str, size: int, col, gap: int) -> None:
        nonlocal y
        rows.append((s, size, col, y))
        y += gap

    add(c.get("title", ""), 14, CREAM_TEXT, 40)
    add("THE CAST", 8, GOLD, 16)
    for name, who in c.get("cast", []):
        add(name, 10, CREAM_TEXT, 12)
        add(who, 8, GREY, 18)
    y += 14
    add("FILMED IN PORT WEXLEY", 8, GOLD, 14)
    for p in c.get("places", []):
        add(p, 8, GREY, 11)
    y += 18
    add("WRITTEN BY", 8, GOLD, 12)
    add(f"the Channel {channel.CURRENT.number} film unit", 8, GREY, 26)
    add("MUSIC", 8, GOLD, 12)
    add(f"the Channel {channel.CURRENT.number} strings", 8, GREY, 120)    # off the top when the last card holds
    last = y
    add(f"CHANNEL {channel.CURRENT.number}", 14, CREAM_TEXT, 22)
    add("A Wexley Television production", 8, GREY, 12)
    add(f"© WTV {c.get('year', date.today().year)}", 8, GREY, 12)
    return rows, last + 22


HOLD_S = 9.0                                              # the last card, still, before the fade


def draw_credits(canvas, v, t: float) -> None:
    from newsroom import scenes

    c = v.scene or {}
    w, h = canvas.get_size()
    e = scenes._elapsed(v, t)
    canvas.fill((0, 0, 0))
    rows, mid = _credit_rows(c)
    dur = c.get("duration_s") or 2 * _pass_s()
    stop = max(4.0, dur - HOLD_S)
    speed = (h + 4 + mid - h / 2) / (stop - 1.0)
    off = h + 4 - speed * min(max(e - 1.0, 0.0), stop - 1.0)   # rows rise from under the frame, then hold
    k = 1 - _ramp(e, dur - 3.0, 2.6)
    for s, size, col, y in rows:
        at = y + off
        if -20 < at < h + 2:
            f = scenes.font(size)
            scenes.queue_text(s, size, _dim(col, k), (w / 2 - f.size(s)[0] / 2, at))
