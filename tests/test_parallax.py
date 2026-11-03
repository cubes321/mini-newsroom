"""Parallax on location (parallax.py, docs/PARALLAX.md): a field shot's backdrop in pieces that slide
past each other as the camera drifts. At rest the window is exactly the flat picture; the ground moves
in bands that give the same frame as moving it row by row; people move with the ground at their feet;
and anything without layers, or with the switch off, stays flat.

The layers here are made in a temp dir from the fish quay's own art, so the tests don't depend on the
pilot's plates, which wait for the user's approval.
"""
from __future__ import annotations

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame
import pytest

from newsroom import backdrops, parallax, scenes
from newsroom.player import View

pygame.init()
P, K = parallax.PAD, scenes.REF
VAN = (270, 100, 40, 26)          # an upright block standing on row 125
BOX = (150, 150, 6, 10)           # a near piece standing on row 175, with something else painted behind it


def _save(a: np.ndarray, path, alpha: np.ndarray | None = None) -> None:
    s = pygame.Surface(a.shape[:2], pygame.SRCALPHA if alpha is not None else 0, 32)
    pygame.surfarray.blit_array(s, a if a.ndim == 3 else np.repeat(a[..., None], 3, 2))
    if alpha is not None:
        pygame.surfarray.pixels_alpha(s)[:] = alpha
    pygame.image.save(s, str(path))


@pytest.fixture
def layers(tmp_path, monkeypatch):
    """Layers for the fish quay: the art padded, all of it ground but the sky, a van-sized upright block
    and one near piece; and a harbour with feet but no plate for its night art."""
    art = backdrops.ART_DIR / "fish_quay.png"
    a = pygame.surfarray.array3d(pygame.image.load(str(art)))
    plate = np.pad(a, ((P, P), (P, P), (0, 0)), mode="edge")
    sky = np.pad(backdrops._sky_of(art).mask, P, mode="edge")
    feet = np.where(sky, 0, np.arange(plate.shape[1])[None, :]).astype(np.uint8)
    x, y, w, h = VAN
    feet[P + x:P + x + w, P + y:P + y + h] = 125 + P
    x, y, w, h = BOX
    near_alpha = np.zeros(feet.shape, np.uint8)
    near_alpha[P + x:P + x + w, P + y:P + y + h] = 255
    near = np.where(near_alpha[..., None] > 0, plate, 0).astype(np.uint8)
    plate[near_alpha > 0] = (0, 0, 0)                                 # the "fill" the near piece hides
    _save(plate, tmp_path / "fish_quay_plate.png")
    _save(feet, tmp_path / "fish_quay_feet.png")
    _save(near, tmp_path / "fish_quay_near.png", near_alpha)
    _save(np.where(near_alpha > 0, 175 + P, 0).astype(np.uint8), tmp_path / "fish_quay_near_feet.png")
    _save(feet, tmp_path / "harbour_feet.png")                       # the harbour's day art has no plate either
    (tmp_path / "parallax.json").write_text(json.dumps({"fish_quay": {"horizon": 80}, "harbour": {"horizon": 98}}))
    monkeypatch.setattr(parallax, "DIR", tmp_path)
    monkeypatch.setenv("NEWSROOM_PARALLAX", "1")
    monkeypatch.setattr(scenes, "_par", None)
    parallax.reset()
    yield tmp_path
    parallax.reset()


def _flat_window(bid: str, t: float) -> np.ndarray:
    c = pygame.Surface(scenes.CANVAS)
    backdrops.draw_still(c, bid, "day", None, t)
    return pygame.surfarray.array3d(pygame.transform.scale(c, (320 * K, 180 * K)))


def _window(sc: parallax.Scene, s: float, t: float = 0.0, **kw) -> np.ndarray:
    screen = pygame.Surface((320 * K, 180 * K))
    sc.draw(screen, s, t, **kw)
    return pygame.surfarray.array3d(screen)


@pytest.mark.parametrize("tod", ["day", "dusk"])
@pytest.mark.parametrize("wx", [None, "rain", "fog"])
def test_at_rest_the_layers_are_the_flat_picture(layers, tod, wx):
    sc = parallax.scene("fish_quay", tod, wx, K, wait=True)
    assert sc is not None and len(sc.pieces) == 2                     # the van block and the near piece
    flat = pygame.Surface(scenes.CANVAS)
    backdrops.draw_still(flat, "fish_quay", tod, wx, 0.0)             # graded alike, the padding's rows included
    assert np.array_equal(_window(sc, 0.0), pygame.surfarray.array3d(pygame.transform.scale(flat, (320 * K, 180 * K))))


def test_a_scene_is_built_on_a_thread_and_the_shot_is_flat_until_then(layers):
    assert parallax.scene("fish_quay", "day", None, K) is None        # asked for: building
    for _ in range(200):
        sc = parallax.scene("fish_quay", "day", None, K)
        if sc is not None:
            break
        pygame.time.wait(10)
    assert sc is not None
    screen = pygame.Surface((320 * K, 180 * K))
    sc.draw(screen, 0.0, 0.0)                                          # its surfaces, made off the main thread
    assert np.array_equal(pygame.surfarray.array3d(screen), _flat_window("fish_quay", 0.0))


def test_the_drift_eases_in_when_a_shot_goes_into_layers(layers):
    assert parallax.scene("fish_quay", "day", None, K, wait=True) is not None
    t = parallax.PERIOD / 4                                            # where the sine is at full swing
    _frame(_field(), t)
    assert scenes._par.s == 0.0                                        # no jump from the flat frame before
    _frame(_field(), t + parallax.EASE_S / 2)
    assert 0 < abs(scenes._par.s) < abs(parallax.swing(t + parallax.EASE_S / 2))
    _frame(_field(), t + parallax.PERIOD)                              # eased in, and a whole swing later
    assert scenes._par.s == pytest.approx(1.0)


def test_water_that_moves_as_a_piece_keeps_its_shimmer(layers):
    """The coast road's sea is pieces, under the hillside sliding over it: the shimmer rides them too."""
    feet = parallax._grey(layers / "fish_quay_feet.png").astype(np.uint8)
    for x0, y0, w, h in backdrops.WATER["fish_quay"]:
        feet[P + x0:P + x0 + w, P + y0:P + y0 + h] = np.where(feet[P + x0:P + x0 + w, P + y0:P + y0 + h] > 0, 140 + P, 0)
    _save(feet, layers / "fish_quay_feet.png")
    parallax.reset()
    sc = parallax.scene("fish_quay", "day", None, K, wait=True)
    for t in (0.0, 1.3, 2.7):
        assert np.array_equal(_window(sc, 0.0, t), _flat_window("fish_quay", t))


def test_the_ground_shears_and_the_sky_stays(layers):
    sc = parallax.scene("fish_quay", "day", None, K, wait=True)
    assert sc.shift(80, 1.0) == 0 and sc.shift(180, 1.0) == round(parallax.NEAR * K) == -sc.shift(180, -1.0)
    assert 0 < sc.shift(125, 1.0) < sc.shift(160, 1.0)
    rest, swung = _window(sc, 0.0), _window(sc, 1.0)
    assert np.array_equal(rest[:, :40 * K], swung[:, :40 * K])         # the sky
    assert not np.array_equal(rest[:, 170 * K:], swung[:, 170 * K:])   # the quay at the bottom


def test_bands_give_the_frame_row_by_row_would(layers):
    sc = parallax.scene("fish_quay", "day", None, K, wait=True)
    for s in (-1.0, -0.37, 0.5, 1.0):
        assert len(sc.bands(s)) < len(sc.bands(s, banded=False))
        assert np.array_equal(_window(sc, s, 1.5), _window(sc, s, 1.5, banded=False))


def test_flat_without_layers_the_switch_or_a_plate_for_the_hour(layers, monkeypatch):
    assert parallax.scene("harbour", "day", None, K, wait=True) is None      # feet, but no plate
    assert parallax.scene("pub", "day", None, K, wait=True) is None          # an interior
    assert parallax.scene("main_street", "day", None, K, wait=True) is None  # no layers at all
    assert parallax.scene("fish_quay", "day", None, K, wait=True) is not None
    monkeypatch.setenv("NEWSROOM_PARALLAX", "0")
    assert parallax.scene("fish_quay", "day", None, K, wait=True) is None


def test_the_harbours_night_art_needs_its_own_plate(layers):
    (layers / "harbour_plate.png").write_bytes((layers / "fish_quay_plate.png").read_bytes())
    parallax.reset()
    assert parallax.has_layers("harbour", "day") and not parallax.has_layers("harbour", "night")


DRIFTS = next(n for n in range(100) if parallax.drifts(n))         # an item that drifts
STILL = next(n for n in range(100) if not parallax.drifts(n))      # and one locked off


def _field(**kw) -> View:
    return View(**{"mode": "field", "backdrop": "fish_quay", "speaker": "reporter", "mouth": 0.4, "tag": "LIVE",
                   "clock": "13:05", "lower_third": ("Miles Okafor", "On the fish quay"),
                   "ticker": ["Hake leads the auction"], "slot_id": DRIFTS, **kw})


def test_about_one_item_in_three_drifts_and_the_rest_are_locked_off(layers):
    share = sum(parallax.drifts(n) for n in range(3000)) / 3000
    assert 0.28 < share < 0.39 and not parallax.drifts(None)
    assert parallax.scene("fish_quay", "day", None, K, wait=True) is not None
    _frame(_field(slot_id=STILL), parallax.PERIOD / 4)
    assert scenes._par is None                                         # flat, though its place has layers
    _frame(_field(), parallax.PERIOD / 4)
    assert scenes._par is not None


def _frame(v: View, t: float, size=(320 * K, 180 * K)) -> tuple[np.ndarray, np.ndarray]:
    canvas, screen = pygame.Surface(scenes.CANVAS), pygame.Surface(size)
    scenes.render(canvas, v, t)
    scenes.present(canvas, screen)
    return pygame.surfarray.array3d(canvas), pygame.surfarray.array3d(screen)


def test_a_field_shot_at_rest_is_the_flat_shot_and_the_canvas_always_is(layers, monkeypatch):
    v = _field()
    assert parallax.scene("fish_quay", "day", None, K, wait=True) is not None
    rest, swung = _frame(v, 0.0), _frame(v, parallax.PERIOD / 4)
    assert scenes._par is not None
    monkeypatch.setenv("NEWSROOM_PARALLAX", "0")
    flat_rest, flat_swung = _frame(v, 0.0), _frame(v, parallax.PERIOD / 4)
    assert scenes._par is None
    assert np.array_equal(rest[1], flat_rest[1])                       # the window, at rest
    assert np.array_equal(rest[0], flat_rest[0]) and np.array_equal(swung[0], flat_swung[0])   # the canvas
    assert not np.array_equal(swung[1], flat_swung[1])                 # the window, swung


def test_the_reporter_moves_with_the_ground_at_their_feet(layers):
    v = _field(lower_third=None, ticker=[], clock="", tag="")
    sc = parallax.scene("fish_quay", "day", None, K, wait=True)
    _frame(v, 0.0)                                                     # into layers, easing in
    t = parallax.PERIOD / 4 + parallax.PERIOD                         # full swing, well after the ease
    _frame(v, t)
    assert scenes._par.s == pytest.approx(1.0)
    (layer, foot), = scenes._par.people
    assert foot == 160
    drawn = pygame.surfarray.array_alpha(layer) > 0
    screen = pygame.Surface((320 * K, 180 * K))
    scenes._par.draw(screen)
    alone = pygame.Surface((320 * K, 180 * K))
    sc.draw(alone, scenes._par.s, t)
    band = slice(90 * K, 125 * K)                                     # head and shoulders: below the tags,
    moved = np.any(pygame.surfarray.array3d(screen)[:, band] != pygame.surfarray.array3d(alone)[:, band], axis=2)
    mx, _ = np.nonzero(moved)                                         # above the lower third and ticker
    left = np.nonzero(drawn[:, 90:125])[0].min()
    assert mx.min() == left * K + sc.shift(160, 1.0) and sc.shift(160, 1.0) > 0   # moved with row 160


def test_only_field_shots_on_a_window_of_the_right_size(layers, monkeypatch):
    assert parallax.scene("fish_quay", "day", None, K, wait=True) is not None
    _frame(View(mode="studio"), 0.0)
    assert scenes._par is None
    _, screen = _frame(_field(), parallax.PERIOD / 4, size=(640, 360))
    assert scenes._par is not None                                    # laid out in layers, but this window
    monkeypatch.setenv("NEWSROOM_PARALLAX", "0")                      # isn't 3x, so it gets the flat canvas
    _, flat = _frame(_field(), parallax.PERIOD / 4, size=(640, 360))
    assert np.array_equal(screen, flat)
