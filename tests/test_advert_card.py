"""The advert's end card (2026-11-24): nineteen of 32 names were cut at size 14, and every cut one ended "_", the
bold face's ellipsis; five taglines were stored cut inside a word ("nothing you can't ca…")."""
from __future__ import annotations

import pygame

from newsroom import scenes
from newsroom.models import AdvertScript


def test_a_cut_in_bold_ends_in_three_full_stops_and_in_plain_text_an_ellipsis():
    pygame.font.init()
    name = "Wexley Gull Feather & Net Mending Stall"
    bold, plain = scenes.font(10), scenes.font(8)
    assert bold.bold and not plain.bold
    assert scenes.clip(name, bold, 100).endswith("...")
    assert scenes.clip(name, plain, 60).endswith("…")
    assert not scenes.clip("Wexley Kettle & Cake Supplies", bold, scenes.font(10).size("Wexley Kettle &")[0] + 12) \
        .rstrip(".").endswith("&")                                 # never left hanging on the ampersand


def test_a_long_tagline_is_cut_at_a_word():
    a = AdvertScript.model_validate({
        "business": "Wexley Kettle & Cake Supplies", "tagline": "Everything for the kettle, nothing you can't carry home",
        "where": "Harrow Street", "backdrop": "main_street", "lines": [{"speaker": "voiceover", "text": "Hello."},
                                                                    {"speaker": "voiceover", "text": "Come in."}]})
    assert a.tagline == "Everything for the kettle, nothing you can't…"
