"""Characters stay on their marks, mirror cleanly, talk, and guests get a stable look of their own.

No model, no TTS: just drawing onto surfaces.
"""
import pygame
import pytest

from newsroom import sprites
from newsroom.sprites import LOOKS, SAMPLE_GUESTS, draw_character, guest_look

BG = (1, 2, 3)
LOOKS_TO_CHECK = [(w, None) for w in LOOKS] + [("guest", guest_look(*g)) for g in SAMPLE_GUESTS]


def _drawn(scale=2, facing=1, who="anchor", look=None, mouth=0.0, t=0.0, w=200, h=200, light=None):
    c = pygame.Surface((w, h))
    c.fill(BG)
    draw_character(c, w // 2, h - 10, who, mouth, t, scale=scale, facing=facing, look=look, light=light)
    return c


def _box(c):
    m = pygame.mask.from_threshold(c, BG, (1, 1, 1, 255))
    m.invert()
    return m.get_bounding_rects()[0]


@pytest.mark.parametrize("scale", [1, 2, 4])
@pytest.mark.parametrize("facing", [1, -1])
def test_everyone_fits_the_footprint(scale, facing):
    """26 x 37 units on the baseline; hair and hats get 2 units a side and 5 above (the close crops)."""
    for who, look in LOOKS_TO_CHECK:
        r = _box(_drawn(scale, facing, who, look))
        assert r.bottom == 190, who                          # t=0: no idle bob
        assert r.width <= 30 * scale, (who, r)
        assert r.top >= 190 - 42 * scale, (who, r)


@pytest.mark.parametrize("who,look", LOOKS_TO_CHECK[:9] + LOOKS_TO_CHECK[9::4])
def test_facing_left_is_a_mirror(who, look):
    right = _drawn(2, 1, who, look)
    left = _drawn(2, -1, who, look)
    assert pygame.image.tobytes(pygame.transform.flip(right, True, False), "RGB") == \
        pygame.image.tobytes(left, "RGB")


def test_mouth_opens_with_the_audio():
    shut = pygame.image.tobytes(_drawn(mouth=0.0), "RGB")
    assert pygame.image.tobytes(_drawn(mouth=0.7), "RGB") != shut
    assert pygame.image.tobytes(_drawn(mouth=0.05), "RGB") == shut        # below the talking threshold


def test_blink_closes_the_eyes():
    beat = sprites._beat("anchor", None)
    assert pygame.image.tobytes(_drawn(t=(3.9 - beat) % 4.0), "RGB") != pygame.image.tobytes(_drawn(t=0.0), "RGB")


def test_guest_look_is_stable_and_agrees_with_the_voice():
    guest_look.cache_clear()
    a = guest_look("Ken Hollis", "am_fenrir", "Retired fisherman")
    guest_look.cache_clear()
    assert guest_look("Ken Hollis", "am_fenrir", "Retired fisherman") == a
    names = [f"Resident {i}" for i in range(60)]
    for n in names:
        f = guest_look(n, "af_bella", "resident")
        assert f.facial == "" and f.tie is None
        assert guest_look(n, "bm_lewis", "resident").extra != "earrings"
    assert len({guest_look(n, "af_bella", "resident") for n in names}) > 40      # a crowd, not five palettes


def test_roles_dress_the_guest():
    assert guest_look("Bea Kowalczyk", "af_kore", "Fire station officer").extra == "stripe"
    assert guest_look("Helen Strand", "bf_emma", "Mayor of Port Wexley").extra == "chain"
    assert guest_look("Alan Moss", "bm_fable", "Vicar of St Petroc's").extra == "collar"
    assert guest_look("Ken Hollis", "am_fenrir", "Retired fisherman").hat == "beanie"
    assert guest_look("Ken Hollis", "am_fenrir", "Retired fisherman").hair in sprites.GREYS


def test_people_take_the_light_of_an_exterior():
    from newsroom import backdrops
    assert backdrops.person_light("studio_interview", "night", "rain") == (1.0, 1.0, 1.0)
    assert backdrops.person_light("harbour", "day", None) == (1.0, 1.0, 1.0)
    r, g, b = backdrops.person_light("harbour", "night", None)
    assert 0.5 < r < b < 1.0                                  # dimmer, and cool
    lit = _drawn(light=(r, g, b))
    plain = _drawn()
    px = _box(plain).center
    assert sum(lit.get_at(px)[:3]) < sum(plain.get_at(px)[:3])
    assert _box(lit) == _box(plain)                           # same shape, only darker


def test_scenes_draw_a_guest_with_or_without_their_details():
    from newsroom import scenes
    from newsroom.player import View
    pygame.font.init()
    c = pygame.Surface(scenes.CANVAS)
    for guests in ({}, {"Tom Penrose": ("am_puck", "Lifeboat coxswain")}):
        v = View(mode="field", backdrop="harbour", speaker="guest", guest_name="Tom Penrose", mouth=0.5,
                 guests=guests)
        scenes.render(c, v, 0.5)
        v = View(mode="studio", set="interview", people=[("anchor", None), ("guest", "Tom Penrose")], guests=guests)
        scenes.render(c, v, 0.5)
