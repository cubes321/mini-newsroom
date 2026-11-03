"""Parallax on location (docs/PARALLAX.md): a backdrop in pieces that slide past each other as the
camera drifts a few pixels from side to side.

Every pixel of the art stands on a row of the screen, its foot. A sideways camera move shifts it by
an amount in proportion to how far its foot is below the horizon: the ground shears row by row, an
upright thing (a boat, a lamp post, the van) moves as one piece at its foot's offset, and the sky
stays put. The pieces are drawn at the window's size, so a slow drift moves a window pixel at a time
instead of a whole art pixel; people on location are moved by their own feet (scenes.py).

Data, in assets/backdrops/parallax/ (`python -m newsroom.parallax import` makes it from a trial's layers):
  <art>_plate.png      the art padded by PAD all round, with what the near pieces hide filled in (RGB)
  <art>_near.png       optional: the near pieces lifted off the plate, in their own colours (RGBA)
  <id>_feet.png        each plate pixel's foot as a padded row, in grey (0 = sky)
  <id>_near_feet.png   each near pixel's foot, the same way (needed with a _near.png)
  parallax.json        {id: {"horizon": row}}: the screen row where the ground runs out
<art> is the art file's own name (harbour, harbour_night). A backdrop drifts at a time of day only
when that art has a plate, so until the night art has one the night stays flat. The feet are shared:
the night art made with ref-latent lines up with the day's. A cliff or a hillside has no flat ground,
so its pixels take the foot that gives the depth model's offset (the lighthouse, the coast road).
"""
from __future__ import annotations

import json
import logging
import math
import os
import sys
import threading
from collections import OrderedDict
from pathlib import Path

import numpy as np
import pygame

from . import backdrops, locations
from .config import CONFIG

log = logging.getLogger(__name__)

DIR = backdrops.ART_DIR / "parallax"
W, H = backdrops.W, backdrops.H
PAD = 10                        # art px of plate past each edge of the frame
NEAR = 5.0                      # art px the bottom row swings either way (the trial's, approved by eye)
PERIOD = 8.0                    # s for one swing there and back
SMEAR = 3                       # art px a farther piece is carried under a nearer one, so a drift opens no hole
EASE_S = 1.5                    # s for the drift to grow from still when a shot starts in layers
CACHE = 12                      # scenes kept, about 5 MB each at 3x: a pilot evening's backdrops, times and weathers


def enabled() -> bool:
    return CONFIG.broadcast.parallax or os.environ.get("NEWSROOM_PARALLAX") == "1"


def scale() -> int:
    """The window as so many canvases over, or 0 when it isn't a whole number of them (then it stays flat)."""
    k = CONFIG.broadcast.width // W
    return k if (CONFIG.broadcast.width, CONFIG.broadcast.height) == (W * k, H * k) else 0


def swing(t: float, since: float | None = None) -> float:
    """Where the camera is, -1 to 1: a slow sine, eased in from still over EASE_S after `since`, when the
    shot went into layers. Without the ease, a scene that finished building mid-shot would jump the
    picture by up to the full swing."""
    s = math.sin(2 * math.pi * t / PERIOD)
    if since is None:
        return s
    u = min(1.0, max(0.0, (t - since) / EASE_S))
    return s * u * u * (3 - 2 * u)


_meta_cache: dict[Path, dict] = {}


def _meta() -> dict:
    if DIR not in _meta_cache:
        path = DIR / "parallax.json"
        _meta_cache[DIR] = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    return _meta_cache[DIR]


def _files(loc: locations.Location, tod: str) -> tuple[Path, bool, Path, Path] | None:
    """The art, whether it was made for this time of day, its plate and the feet; None to stay flat."""
    if not loc.exterior or loc.id not in _meta():
        return None
    art = backdrops._art_file(loc, tod)
    if art is None:
        return None
    path, own = art
    plate, feet = DIR / f"{path.stem}_plate.png", DIR / f"{loc.id}_feet.png"
    return (path, own, plate, feet) if plate.exists() and feet.exists() else None


def has_layers(backdrop_id: str | None, tod: str = "day") -> bool:
    return _files(locations.get(backdrop_id), tod) is not None


# ------------------------------------------------------------------ building a scene


def _rgb(path: Path) -> np.ndarray:
    return pygame.surfarray.array3d(pygame.image.load(str(path)))                   # [x, y, 3]


def _grey(path: Path) -> np.ndarray:
    return pygame.surfarray.array3d(pygame.image.load(str(path)))[..., 0].astype(np.int16)


def _graded(a: np.ndarray, loc: locations.Location, tod: str, wx: str | None, own: bool) -> np.ndarray:
    """A padded plate graded exactly as the flat art is (backdrops._grade_art), row for row."""
    s = pygame.Surface(a.shape[:2], 0, 32)
    pygame.surfarray.blit_array(s, a)
    backdrops._grade_art(s, loc, tod, wx, own, top=PAD)
    return pygame.surfarray.array3d(s)


def _sky_rows(art: Path, size: tuple[int, int]) -> np.ndarray:
    """The sky behind everything: each row's sky colour across the whole plate, from the art with its
    clouds lifted out (skies.py), so the clouds can drift over it as they do on the flat art. A row
    with no sky in it takes the one above, and the padding the nearest row of the frame."""
    sky = backdrops._sky_of(art)
    pw, ph = size
    colours = np.zeros((H, 3), np.uint8)
    have = np.zeros(H, bool)
    for y in range(H):
        on = sky.mask[:, y]
        if on.any():
            colours[y] = np.median(sky.clean[on, y], axis=0)
            have[y] = True
    if have.any():
        first = int(np.argmax(have))
        colours[:first] = colours[first]
        for y in range(first + 1, H):
            if not have[y]:
                colours[y] = colours[y - 1]
    rows = np.concatenate([np.repeat(colours[:1], PAD, 0), colours, np.repeat(colours[-1:], ph - H - PAD, 0)])
    return np.broadcast_to(rows[None, :, :], (pw, ph, 3)).copy()


def _carry(rgb: np.ndarray, own: np.ndarray, under: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """`own`'s colours carried up to SMEAR px sideways into `under` (the nearer pieces' pixels), so when
    a nearer piece slides it shows this one behind it, not a hole. rgb [x, y, 3], masks [x, y]."""
    rgb, have = rgb.copy(), own.copy()
    for _ in range(SMEAR):
        for d in (1, -1):
            src = np.roll(have, d, axis=0)
            src[0 if d == 1 else -1] = False
            grow = src & under & ~have
            rgb[grow] = np.roll(rgb, d, axis=0)[grow]
            have |= grow
    return rgb, have


def _surface(rgb: np.ndarray, alpha: np.ndarray | None, k: int) -> pygame.Surface:
    """An art-sized array as a window-sized surface, nearest neighbour; with alpha, a binary mask."""
    w, h = rgb.shape[:2]
    s = pygame.Surface((w, h), pygame.SRCALPHA if alpha is not None else 0, 32)
    pygame.surfarray.blit_array(s, rgb)
    if alpha is not None:
        pygame.surfarray.pixels_alpha(s)[:] = np.where(alpha, 255, 0).astype(np.uint8)
    return pygame.transform.scale(s, (w * k, h * k))


class Scene:
    """One backdrop at one time of day and weather, cut into pieces at the window's scale `k`."""

    def __init__(self, loc: locations.Location, tod: str, wx: str | None, k: int,
                 files: tuple[Path, bool, Path, Path]) -> None:
        art, own, plate_path, feet_path = files
        self.loc, self.tod, self.wx, self.k = loc, tod, wx, k
        self.horizon = float(_meta()[loc.id]["horizon"])
        plate = _graded(_rgb(plate_path), loc, tod, wx, own)
        feet = _grey(feet_path)
        pw, ph = feet.shape
        self.size = (pw, ph)
        near_path, near_feet_path = DIR / f"{art.stem}_near.png", DIR / f"{loc.id}_near_feet.png"
        if near_path.exists() and near_feet_path.exists():
            alpha = pygame.surfarray.array_alpha(pygame.image.load(str(near_path)))
            near_rgb = _graded(_rgb(near_path), loc, tod, wx, own)
            near_feet = np.where(alpha > 0, _grey(near_feet_path), 0)
        else:
            near_rgb, near_feet = None, np.zeros_like(feet)
        rows = np.arange(ph)[None, :]
        ground = (feet > 0) & (feet == rows)
        upright = (feet > 0) & ~ground
        front = np.maximum(np.where(upright, feet, 0), near_feet)     # the nearest foot standing on each pixel

        sky = _graded(_sky_rows(art, (pw, ph)), loc, tod, wx, own)
        self.sky = _surface(sky[PAD:PAD + W, PAD:PAD + H], None, k)
        g_rgb, g_have = _carry(plate, ground, front > 0)
        self.ground = _surface(g_rgb, g_have, k)
        self.ground_rows = [r for r in range(PAD, PAD + H) if g_have[:, r].any()]
        water = [(y0, y0 + h) for _, y0, _, h in backdrops.WATER.get(loc.id, ())]
        self.water = (min(a for a, _ in water), max(b for _, b in water)) if water else None   # screen rows
        self.cloud_rows = min(H, backdrops._sky_of(art).floor + 1)
        self._clouds: tuple[tuple, pygame.Surface | None] = ((), None)  # scaled, until they drift a pixel
        self._shimmer: tuple[int, pygame.Surface | None] = (-1, None)

        pieces = []                     # (foot as a screen row, order, surface, (x, y) in the plate)
        for f in np.unique(feet[upright]):
            own_px = upright & (feet == f)
            rgb, have = _carry(plate, own_px, front > f)
            pieces.append((float(f) - PAD, 0, *self._crop(rgb, have)))
        if near_rgb is not None:
            for f in np.unique(near_feet[near_feet > 0]):
                pieces.append((float(f) - PAD, 1, *self._crop(near_rgb, near_feet == f)))
        self.pieces = [(f, s, at) for f, _, s, at in sorted(pieces, key=lambda p: (p[0], p[1]))]

    def _crop(self, rgb: np.ndarray, have: np.ndarray) -> tuple[pygame.Surface, tuple[int, int]]:
        xs, ys = np.nonzero(have)
        x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
        return _surface(rgb[x0:x1, y0:y1], have[x0:x1, y0:y1], self.k), (int(x0), int(y0))

    def shift(self, foot: float, s: float) -> int:
        """Window px a pixel standing on screen row `foot` moves at camera position `s`."""
        return round(s * NEAR * (foot - self.horizon) / (H - self.horizon) * self.k)

    def bands(self, s: float, *, banded: bool = True) -> list[tuple[int, int, int]]:
        """The ground's rows in runs that share a shift: (first padded row, rows, shift). At rest it's one
        run; at full swing, one per window pixel of the bottom row's offset."""
        out: list[list[int]] = []
        for r in self.ground_rows:
            dx = self.shift(r - PAD, s)
            if banded and out and out[-1][0] + out[-1][1] == r and out[-1][2] == dx:
                out[-1][1] += 1
            else:
                out.append([r, 1, dx])
        return [tuple(b) for b in out]

    def draw(self, screen: pygame.Surface, s: float, t: float, *, banded: bool = True) -> None:
        """The backdrop at camera position `s`, filling the window: the still sky and its drifting
        clouds, the ground in bands with the water's shimmer riding it, then the upright pieces,
        farthest first."""
        k, (pw, _) = self.k, self.size
        screen.blit(self.sky, (0, 0))
        clouds = backdrops._clouds(self.loc, self.tod, self.wx)
        if clouds:
            step = backdrops.drift_steps(len(clouds[0]), self.wx, t)
            if step != self._clouds[0]:
                buf = _buffer()
                buf.fill((0, 0, 0, 0))
                backdrops._drift(buf, clouds, self.wx, t)
                h = self.cloud_rows
                self._clouds = (step, pygame.transform.scale(buf.subsurface((0, 0, W, h)), (W * k, h * k)))
            screen.blit(self._clouds[1], (0, 0))
        bands = self.bands(s, banded=banded)
        for r, n, dx in bands:
            screen.blit(self.ground, (-PAD * k + dx, (r - PAD) * k), pygame.Rect(0, r * k, pw * k, n * k))
        if self.water:
            y0, y1 = self.water
            step = backdrops.shimmer_step(t)
            if step != self._shimmer[0]:
                buf = _buffer()
                buf.fill((0, 0, 0, 0))
                backdrops._shimmer(buf, self.loc.id, self.tod, t)
                self._shimmer = (step, pygame.transform.scale(buf.subsurface((0, y0, W, y1 - y0)),
                                                              (W * k, (y1 - y0) * k)))
            for r, n, dx in bands:                       # the shimmer rides the water it's on
                a, b = max(r - PAD, y0), min(r - PAD + n, y1)
                if a < b:
                    screen.blit(self._shimmer[1], (dx, a * k), pygame.Rect(0, (a - y0) * k, W * k, (b - a) * k))
        for f, surf, (x, y) in self.pieces:
            screen.blit(surf, ((x - PAD) * k + self.shift(f, s), (y - PAD) * k))


_buf: pygame.Surface | None = None


def _buffer() -> pygame.Surface:
    global _buf
    if _buf is None:
        _buf = pygame.Surface((W, H), pygame.SRCALPHA)
    return _buf


# ------------------------------------------------------------------ the cache


_scenes: OrderedDict[tuple, Scene] = OrderedDict()
_building: set[tuple] = set()
_failed: set[tuple] = set()
_lock = threading.Lock()


def reset() -> None:
    """Forget every scene and the metadata (tests, and after new data is written)."""
    with _lock:
        _scenes.clear()
        _building.clear()
        _failed.clear()
    _meta_cache.clear()


def scene(backdrop_id: str | None, tod: str, wx: str | None, k: int, *, wait: bool = False) -> Scene | None:
    """The layered backdrop, if parallax is on and it has layers for this time of day. A scene not yet
    built is built on a thread (a second or so) and the shot stays flat until it is; `wait` builds it
    here and now."""
    if not enabled() or k < 1:
        return None
    loc = locations.get(backdrop_id)
    files = _files(loc, tod)
    if files is None:
        return None
    key = (loc.id, tod, wx, k)
    with _lock:
        sc = _scenes.get(key)
        if sc is not None:
            _scenes.move_to_end(key)
            return sc
        if key in _failed or (key in _building and not wait):
            return None
        _building.add(key)
    if wait:
        _build(key, loc, tod, wx, k, files)
        return _scenes.get(key)
    threading.Thread(target=_build, args=(key, loc, tod, wx, k, files), name="parallax", daemon=True).start()
    return None


def _build(key: tuple, loc, tod: str, wx: str | None, k: int, files) -> None:
    try:
        sc = Scene(loc, tod, wx, k, files)
    except Exception:  # noqa: BLE001
        log.exception("parallax: couldn't build %s; it stays flat", key)
        with _lock:
            _building.discard(key)
            _failed.add(key)
        return
    with _lock:
        _building.discard(key)
        _scenes[key] = sc
        while len(_scenes) > CACHE:
            _scenes.popitem(last=False)


# ------------------------------------------------------------------ import from a trial's layers


def import_layers(npz: Path, backdrop_id: str, out: Path | None = None) -> list[Path]:
    """Write a backdrop's data from a trial's layers file (the 2026-11-03 trial's `.npz`: plate, sky,
    foot and sprites, row-major and padded by PAD): the plate, the feet, the near pieces and the horizon."""
    out = out or DIR
    out.mkdir(parents=True, exist_ok=True)
    d = np.load(npz)
    plate, sky, foot = d["plate"].copy(), d["sky"], d["foot"]
    feet = np.where(sky, 0, np.clip(np.round(foot) + PAD, 1, 255)).astype(np.uint8)
    masks = d["sprite_masks"] if "sprite_masks" in d.files else np.zeros((0,) + feet.shape, bool)
    # The fill reached a pixel or two past the near pieces it was for, and inside the frame it would show
    # there: keep the art's own pixels everywhere a near piece doesn't stand.
    shown = np.zeros(feet.shape, bool)
    shown[PAD:PAD + H, PAD:PAD + W] = True
    shown &= ~masks.any(axis=0) if len(masks) else True
    plate[shown] = d["orig"][shown]

    def save(a: np.ndarray, name: str, alpha: np.ndarray | None = None) -> Path:
        a = a.transpose(1, 0, *range(2, a.ndim))             # row-major to pygame's [x, y]
        if a.ndim == 2:
            a = np.repeat(a[..., None], 3, 2)
        s = pygame.Surface(a.shape[:2], pygame.SRCALPHA if alpha is not None else 0, 32)
        pygame.surfarray.blit_array(s, a)
        if alpha is not None:
            pygame.surfarray.pixels_alpha(s)[:] = alpha.T
        path = out / name
        pygame.image.save(s, str(path))
        return path

    written = [save(plate, f"{backdrop_id}_plate.png"), save(feet, f"{backdrop_id}_feet.png")]
    if len(masks):
        near_feet = np.zeros(feet.shape, np.uint8)
        for m, f in zip(masks, d["sprite_feet"]):
            near_feet[m] = np.clip(round(float(f)) + PAD, 1, 255)
        near = np.where(near_feet[..., None] > 0, d["orig"], 0).astype(np.uint8)
        written += [save(near, f"{backdrop_id}_near.png", np.where(near_feet > 0, 255, 0).astype(np.uint8)),
                    save(near_feet, f"{backdrop_id}_near_feet.png")]
    meta_path = out / "parallax.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8")) if meta_path.exists() else {}
    meta[backdrop_id] = {"horizon": float(d["horizon"])}
    meta_path.write_text(json.dumps(meta, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    written.append(meta_path)
    reset()
    return written


def _cli(argv: list[str]) -> int:
    if len(argv) == 3 and argv[0] == "import":
        pygame.init()
        for path in import_layers(Path(argv[1]), argv[2]):
            print(path)
        return 0
    print("usage: python -m newsroom.parallax import LAYERS.npz BACKDROP_ID", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))
