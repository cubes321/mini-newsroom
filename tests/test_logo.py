"""The Channel 7 logo: every show's ident assembles on its notes, and the bug stays in its corner.

No audio, no model: just drawing onto surfaces.
"""
import pygame
import pytest

from newsroom import logo, scenes, schedule
from newsroom.player import View


def _ident(t, show="news", onsets=None):
    s = pygame.Surface((320, 180))
    logo.draw_ident(s, t, show, onsets)
    return s


@pytest.mark.parametrize("show", list(schedule.SHOWS))
@pytest.mark.parametrize("onsets", [[0.0], logo.DEFAULT_ONSETS, [0, .2, .4, .6, .8, 1.0, 1.4]])
def test_every_ident_builds_up_then_holds(show, onsets):
    first, done = _ident(0.0, show, onsets), _ident(max(onsets) + 3, show, onsets)
    assert pygame.image.tobytes(first, "RGB") != pygame.image.tobytes(done, "RGB")


def test_pieces_land_on_the_first_and_last_notes():
    for onsets in ([0.0], [0, 1], logo.DEFAULT_ONSETS, [0, .2, .4, .6, .8, 1.0, 1.4]):
        at = logo.piece_times(onsets)
        assert len(at) == 5 and at[0] == onsets[0] and at[-1] == onsets[-1] and at == sorted(at)


def test_wordmark_is_written_only_after_the_held_note():
    last = logo.DEFAULT_ONSETS[-1]
    band = pygame.Rect(0, 124, 320, 14)                   # where the wordmark goes
    before, after = _ident(last - 0.05), _ident(last + 1.0)
    assert pygame.image.tobytes(before.subsurface(band), "RGB") != pygame.image.tobytes(after.subsurface(band), "RGB")


def test_the_bug_stays_in_its_corner():
    s = pygame.Surface((320, 180))
    s.fill((0, 0, 0))
    logo.draw_bug(s)
    m = pygame.mask.from_threshold(s, (0, 0, 0), (1, 1, 1, 255))
    m.invert()
    box = m.get_bounding_rects()[0]
    assert logo.bug_rect(s.get_size()).contains(box)


@pytest.mark.parametrize("v, bug", [
    (View(mode="studio"), True), (View(mode="weather"), True), (View(mode="field"), True),
    (View(mode="special", chapter={"number": 2}), True),
    (View(mode="special", chapter={"number": 1}, chapter_age_s=2.0), False),     # the title card
    (View(mode="studio", breaking=True), False), (View(mode="bumper"), False), (View(mode="filler"), False),
    (View(mode="advert"), False), (View(mode="testcard"), False), (View(mode="breaking"), False),
])
def test_bug_only_during_programmes(v, bug):
    assert scenes.shows_bug(v) is bug


def test_bumper_times_the_ident_from_when_it_came_up():
    pygame.font.init()
    a, b = pygame.Surface((320, 180)), pygame.Surface((320, 180))
    tune = scenes.ident_onsets("news")
    scenes.render(a, View(mode="bumper", slot_id=901), 500.0)             # its first frame: the ident's start
    assert pygame.image.tobytes(a, "RGB") == pygame.image.tobytes(_with_clock(_ident(0.0, onsets=tune)), "RGB")
    scenes.render(b, View(mode="bumper", slot_id=901), 503.0)
    assert pygame.image.tobytes(b, "RGB") == pygame.image.tobytes(_with_clock(_ident(3.0, onsets=tune)), "RGB")


@pytest.mark.parametrize("show", list(schedule.SHOWS))
def test_the_logo_is_whole_before_the_spoken_ident(show):
    """The voice-over starts about a second after the held note; the wordmark and title are in by then."""
    tune = scenes.ident_onsets(show)
    assert logo.piece_times(tune)[-1] == tune[-1]
    assert logo.WORDMARK_S < 1.0 and logo.TITLE_DELAY_S + logo.TITLE_S < 1.0


def _with_clock(s):
    scenes.draw_clock(s, View())
    return s


def test_contact_sheet(tmp_path):
    out = tmp_path / "logo.png"
    logo.contact_sheet(str(out))
    assert out.stat().st_size > 0
