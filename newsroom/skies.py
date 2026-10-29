"""Drifting skies: lift the painted clouds out of a backdrop so they can drift behind the buildings.

A cheap parallax for flat, screen-sized art. The sky is found by colour, not drawn by hand: pixels
joined to the top edge that match their row's sky colour, or are near-white, down to the horizon,
plus anything up there the ground can't reach (painted clouds, a gull). The clouds are the sky
pixels that differ from the sky's own colour; each one goes on a wrap-around layer, the high ones
moving a little faster than those near the horizon, and the sky they leave behind is filled with
its row's colour. Specks smaller than CLOUD_MIN_PX (stars) stay painted where they are.

Pure numpy on arrays indexed [x, y, channel] (pygame's surfarray layout), so any channel's art
can use it; backdrops.py grades and draws the layers.
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

CLOUD_MIN_PX = 6
FRINGE = 10                   # how far from the sky's colour a cloud's edge pixels still count
LAYERS = 2                    # 0: high clouds, 1: near the horizon (further away, slower)
HIGH_SHARE = 0.45             # a cloud whose middle is above this fraction of the horizon is high


@dataclass
class Sky:
    mask: np.ndarray          # bool [x, y]: where clouds may show
    floor: int                # the horizon row: nothing below it is sky
    clean: np.ndarray         # uint8 [x, y, 3]: the art with its clouds lifted out
    layers: list[tuple[np.ndarray, np.ndarray]]   # per layer: rgb [x, y, 3] on the sky, cloud bool [x, y]

    @property
    def has_clouds(self) -> bool:
        return any(c.any() for _, c in self.layers)


def grow(seed: np.ndarray, ok: np.ndarray) -> np.ndarray:
    """Flood fill: everything in ok joined to seed by 4-neighbour steps."""
    m = seed & ok
    while True:
        d = m.copy()
        d[1:] |= m[:-1]
        d[:-1] |= m[1:]
        d[:, 1:] |= m[:, :-1]
        d[:, :-1] |= m[:, 1:]
        d &= ok
        if np.array_equal(d, m):
            return m
        m = d


def _edge(shape, row: int) -> np.ndarray:
    e = np.zeros(shape, bool)
    e[:, row] = True
    return e


def find(a: np.ndarray) -> Sky:
    """The sky and its clouds in a picture (uint8 [x, y, 3])."""
    w, h = a.shape[:2]
    f = a.astype(np.int32)                      # int16 overflows r * 299
    r, g, b = f[..., 0], f[..., 1], f[..., 2]
    top = _edge((w, h), 0)
    strict = grow(top, (b > r + 20) & (b + 5 > g))
    # each row's sky colour: the median of the plainly blue sky in it, carried down past rows with none
    ref = np.zeros((h, 3), np.float32)
    last = np.array([150, 190, 230], np.float32)
    for y in range(h):
        px = f[strict[:, y], y]
        if len(px) >= 8:
            last = np.median(px, axis=0).astype(np.float32)
        ref[y] = last
    # the horizon: the first row where that colour jumps (the sea starts), else the lowest sky row
    rows = np.flatnonzero(strict.any(axis=0))
    floor = int(rows.max()) + 1 if len(rows) else 0
    jumps = np.flatnonzero(np.abs(np.diff(ref, axis=0)).sum(axis=1)[: max(0, floor - 1)] > 30)
    if len(jumps):
        floor = int(jumps[0]) + 1
    above = np.zeros((w, h), bool)
    above[:, :floor] = True
    off_sky = np.abs(f - ref[None]).sum(axis=2)
    lum = (r * 299 + g * 587 + b * 114) // 1000
    # how close counts as sky scales with its brightness: a night sky is near the dark roofs
    ref_lum = ref @ np.array([0.299, 0.587, 0.114], np.float32)
    tol = np.clip(ref_lum * 0.3, 14, 40)[None, :]
    cloud_tol = np.clip(tol * 2, 28, 40)
    white = (lum > 215) & (f.max(axis=2) - f.min(axis=2) < 30)
    warm = r > b + 10                                            # lamps and their glow are never sky
    mask = grow(top, ((off_sky < tol) | white) & above & ~warm)
    mask |= ~grow(_edge((w, h), h - 1), ~mask) & above          # holes: clouds, birds
    # a cloud resting against a roof can't be a hole; take it by the colours the free clouds use
    # (the art has a small palette), starting from where it touches the sky
    code = (f[..., 0] << 16) | (f[..., 1] << 8) | f[..., 2]
    free = mask & (off_sky >= cloud_tol) & (lum > 150) & (b + 5 >= r)
    stuck = above & ~mask & ~warm & np.isin(code, np.unique(code[free]))
    near_sky = mask.copy()
    near_sky[1:] |= mask[:-1]
    near_sky[:-1] |= mask[1:]
    near_sky[:, 1:] |= mask[:, :-1]
    near_sky[:, :-1] |= mask[:, 1:]
    mask |= grow(near_sky & stuck, stuck)

    clean = a.copy()
    layers = [(np.broadcast_to(ref[None].astype(np.uint8), a.shape).copy(), np.zeros((w, h), bool))
              for _ in range(LAYERS)]
    todo = mask & (off_sky >= cloud_tol)
    while todo.any():
        x, y = np.unravel_index(np.argmax(todo), todo.shape)
        seed = np.zeros_like(todo)
        seed[x, y] = True
        blob = grow(seed, todo)
        todo &= ~blob
        if blob.sum() < CLOUD_MIN_PX:
            continue
        blob = grow(blob, mask & (off_sky >= FRINGE))            # its soft edge goes with it, or a ghost stays
        todo &= ~blob
        ys = np.flatnonzero(blob.any(axis=0))
        rgb, cloud = layers[0 if ys.mean() < floor * HIGH_SHARE else 1]
        rgb[blob] = a[blob]
        cloud |= blob
        clean[blob] = np.broadcast_to(ref[None].astype(np.uint8), a.shape)[blob]
    return Sky(mask, floor, clean, layers)
