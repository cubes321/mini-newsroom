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
    assert a.tagline == "Everything for the kettle"                  # at its comma, whole (2026-11-28)


def test_a_tagline_stored_cut_is_never_used_again():
    """2026-11-28: two of the town's taglines were kept cut ("Everything for the boat, since before the tide…"), and
    every advert for the business ends on its tagline, word for word."""
    from newsroom import directory, world as world_mod

    w = world_mod.seed()
    plain = next(b for b in directory.CORE if not b.tagline)
    w.directory[directory._key(plain.name)] = {"tagline": "Everything for the boat, since before the tide…"}
    w.directory["veryan's chandlery"] = {"invented": w.last_date, "kind": "chandlery", "where": "the quay",
                                         "backdrop": "harbour", "tagline": "Grown close, sold fresh…"}
    known = {b.name: b for b in directory.businesses(w)}
    assert known[plain.name].tagline == "" and directory.find(w, "Veryan's Chandlery").tagline == ""
    w.directory[directory._key(plain.name)]["tagline"] = "Tied up tight since 1871"
    assert directory.find(w, plain.name).tagline == "Tied up tight since 1871"


def test_a_long_caption_drops_a_size_before_it_is_cut():
    """At 8, "What's been the best thing in Port Wexley this week, or where's the…" went out (2026-11-28)."""
    import pygame
    pygame.init()
    q = "What's been the best thing in Port Wexley this week, or where's the best chips?"
    assert scenes.fitting(q, (10, 8, 7), 250) == 7
    assert scenes.fitting("Vox pop", (10, 8, 7), 250) == 10
    assert scenes.fitting("x " * 200, (8, 7), 250) == 7                 # too long even so: cut at 7
