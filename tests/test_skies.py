"""Drifting skies: the painted clouds are lifted out of the art and drift behind the buildings,
leaving the buildings, the sea and the stars where they were."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

import numpy as np
import pygame

from newsroom import backdrops, locations, skies

SKY, CLOUD, WALL, SEA, GRASS = (140, 190, 235), (245, 248, 250), (170, 80, 60), (60, 140, 215), (80, 150, 70)


def _picture():
    """Sky to row 60, then sea, then grass from row 90; a house standing up into the sky,
    a cloud in the open, a cloud resting on the roof and a star-sized speck."""
    a = np.zeros((120, 120, 3), np.uint8)
    a[:, :60] = SKY
    a[:, 60:90] = SEA
    a[:, 90:] = GRASS
    a[70:100, 30:90] = WALL                    # the house, rising to row 30
    a[10:30, 15:35] = CLOUD                    # free
    a[75:85, 24:30] = CLOUD                    # resting on the roof
    a[90:92, 5:7] = (255, 255, 255)            # a speck
    return a


def test_a_free_cloud_and_one_on_a_roof_both_lift_out_and_the_house_stays():
    a = _picture()
    sky = skies.find(a)
    assert sky.floor == 60
    clouds = sky.layers[0][1] | sky.layers[1][1]
    assert clouds[10:30, 15:35].all() and clouds[75:85, 24:30].all()
    assert (sky.clean[10:30, 15:35] == SKY).all() and (sky.clean[75:85, 24:30] == SKY).all()
    assert (sky.clean[70:100, 30:90] == WALL).all() and not sky.mask[70:100, 30:90].any()
    assert not sky.mask[:, 60:].any()          # the sea is not sky
    assert (sky.clean[90:92, 5:7] == 255).all()  # specks (stars) stay painted


def _setup():
    pygame.init()
    if pygame.display.get_surface() is None:
        pygame.display.set_mode((1, 1))


def test_every_exterior_drifts_without_touching_what_is_below_its_horizon():
    _setup()
    for loc in locations.LOCATIONS:
        if not (loc.exterior and backdrops.has_art(loc.id)):
            continue
        for tod in backdrops.TODS:
            art = backdrops._art_file(loc, tod)
            sky = backdrops._sky_of(art[0])
            before = pygame.surfarray.array3d(backdrops._load(art[0]))
            assert (sky.clean[:, sky.floor:] == before[:, sky.floor:]).all(), (loc.id, tod)
            a, b = pygame.Surface((320, 180)), pygame.Surface((320, 180))
            backdrops.draw(a, loc.id, tod, None, 0.0)
            backdrops.draw(b, loc.id, tod, None, 40.0)
            if sky.has_clouds:
                assert pygame.surfarray.array3d(a).tolist() != pygame.surfarray.array3d(b).tolist(), (loc.id, tod)


def test_the_still_keeps_its_painted_clouds_for_studio_screens():
    _setup()
    painted = pygame.surfarray.array3d(backdrops.surface("harbour", "day", None))
    clean = pygame.surfarray.array3d(backdrops.surface("harbour", "day", None, clean=True))
    assert (painted != clean).any() and (painted[:, 120:] == clean[:, 120:]).all()
