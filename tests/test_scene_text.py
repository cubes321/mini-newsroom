"""On-screen text is laid out on the 320x180 canvas but drawn at the window's size by present()."""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from newsroom import scenes  # noqa: E402
from newsroom.player import View  # noqa: E402


def test_text_is_drawn_at_full_size_over_the_scaled_frame():
    pygame.init()
    canvas, screen = pygame.Surface(scenes.CANVAS), pygame.Surface((960, 540))
    scenes.render(canvas, View(mode="studio", show="news", clock="20:07", ticker=["Harbour wall report Friday"],
                               lower_third=("Harbour Wall Report Due Friday", "Dana Ferris")), 1.0)
    words = [s for s, *_ in scenes._layer]
    assert "Harbour Wall Report Due Friday" in words and "20:07" in words
    plain = pygame.transform.scale(canvas, screen.get_size())
    scenes.present(canvas, screen)
    band = pygame.Rect(54, 390, 600, 30)            # the headline, in window pixels
    assert any(screen.get_at((x, y)) != plain.get_at((x, y)) for x in range(band.x, band.right, 3)
               for y in range(band.y, band.bottom, 3))
    scenes.render(canvas, View(mode="testcard"), 1.0)
    assert scenes._layer == []                      # each frame starts with no text


def test_layout_is_measured_in_canvas_pixels():
    w, h = scenes.font(8).size("Port Wexley")
    assert 20 < w < 80 and 6 <= h <= 14
    assert scenes.font(10).size("Port Wexley")[0] > w
