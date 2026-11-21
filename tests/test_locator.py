"""The news locator (newsroom/locator.py): a Channel 7 news item's place on the town's map, or nothing."""
from types import SimpleNamespace

import pygame
import pytest

from newsroom import channel, locator, player, scenes
from newsroom.models import Line, Segment, SegmentType as T
from newsroom.player import View


def _seg(kind=T.field_report, headline="", brief="", show="news", lines=None, **kw):
    lines = lines or [Line(speaker="anchor", text="Over to Miles.", duration_s=4.0),
                      Line(speaker="reporter", text="I'm here.", duration_s=8.0)]
    return Segment(slot_id=1, type=kind, show=show, headline=headline, brief=brief, lines=lines, **kw)


def test_the_words_place_it_first():
    assert locator.place_of(_seg(headline="Hake glut softens fish quay prices"), "", "harbour") == "fish_quay"
    assert locator.place_of(_seg(brief="The Greenhill Road bowling green after the frost")) == "greenhill_road"
    assert locator.place_of(_seg(headline="Rain again"), "Kessick Bay fans send kippers. The tin arrived.") \
        == "kessick_bay"


def test_then_a_backdrop_that_shows_one_place():
    assert locator.place_of(_seg(headline="A long wait for the doctor"), "", "village") == "saltby"
    assert locator.place_of(_seg(headline="Lambing starts early"), "", "farm") is None       # a farm: anywhere
    assert locator.place_of(_seg(headline="Pub quiz night"), "", "pub") is None
    assert locator.place_of(_seg(), "", None) is None


def test_it_never_guesses_between_the_two_sides():
    assert locator.place_of(_seg(headline="Saltby hall roof to be mended"), "", "harbour") is None
    assert locator.place_of(_seg(headline="The coast road above Saltby sands closes"), "", None) is None


def test_only_channel_7s_news_with_miles():
    assert locator.wanted(_seg(), "reporter")
    assert locator.wanted(_seg(T.vox_pop), "reporter")
    assert not locator.wanted(_seg(T.bulletin), "reporter")
    assert not locator.wanted(_seg(show="outabout"), "travel")                 # Meg's days out
    assert not locator.wanted(_seg(), "sport_reporter")
    undo = channel.use(channel.Channel(number="8", name="Channel 8"))
    try:
        assert not locator.wanted(_seg(), "reporter")
    finally:
        channel.use(undo)


def _locator(seg, v, elapsed):
    me = SimpleNamespace(world=SimpleNamespace(thread=lambda _id: None), _locator_of=("", None))
    return player.Player._locator(me, seg, v, elapsed)


def test_up_on_the_wall_and_for_the_first_seconds_out_there():
    seg = _seg(headline="Hake glut softens fish quay prices")
    assert _locator(seg, View(mode="studio", shot="wall", reporter="reporter", backdrop="fish_quay"), 2.0) == "fish_quay"
    out = View(mode="field", reporter="reporter", backdrop="fish_quay")
    assert _locator(seg, out, 4.0 + 1.0) == "fish_quay"                       # the reporter's first line is at 4 s
    assert _locator(seg, out, 4.0 + locator.SHOW_S + 0.5) is None
    assert _locator(seg, View(mode="studio", shot="wide", reporter="reporter"), 1.0) is None
    farm = View(mode="field", reporter="reporter", backdrop="farm")
    assert _locator(_seg(headline="Lambing starts early"), farm, 5.0) is None  # nowhere the map can say


@pytest.fixture
def canvas():
    pygame.init()
    return pygame.Surface((320, 180))


@pytest.mark.parametrize("v", [View(mode="field", backdrop="fish_quay", tag="LIVE", speaker="reporter"),
                               View(mode="studio", shot="wall", backdrop="lighthouse", wall_label="LIVE")])
def test_it_is_drawn_only_while_up_and_clear_of_the_captions(canvas, v):
    scenes.render(canvas, v, 1.0)
    assert not [k for k, *_ in scenes._pictures if k[0] == "locator"]
    v.locator = "fish_quay"
    scenes.render(canvas, v, 1.0)
    (key, make, at), = [p for p in scenes._pictures if p[0][0] == "locator"]
    x, y, w, h = locator.FIELD_RECT if v.mode == "field" else locator.WALL_RECT
    assert at == (x, y) and make(1).get_size() == (w, h)
    box = pygame.Rect(x, y, w, h)
    for keep_clear in (pygame.Rect(276, 4, 40, 12), pygame.Rect(8, 128, 262, 26), pygame.Rect(0, 166, 320, 14)):
        assert not box.colliderect(keep_clear)
    if v.mode == "field":
        assert not box.colliderect(pygame.Rect(64, 86, 52, 74))              # the reporter


def test_where_the_report_says_it_is_comes_before_its_headline():
    """Over the reports of 2026-11-20 and 21 the script's location placed 117 of 118 and the headline 79, and the
    headline was wrong where they differed: it names the story's subject, not where Miles is standing."""
    seg = Segment(slot_id=1, type=T.field_report, headline="Wreckers Hold Their Shape Ahead of Saltby Trip")
    assert locator.place_of(seg) == "saltby"                           # by the headline alone: across the water
    seg.work["said_at"] = "the Quarry Field, home of Port Wexley RFC"
    assert locator.place_of(seg) == "quarry_field"
    seg = Segment(slot_id=2, type=T.field_report, headline="Hard Frost Grips the Harbour Edges")
    seg.work["said_at"] = "the fish quay, Port Wexley harbour"         # the first place named, not the longest
    assert locator.place_of(seg) == "fish_quay"
    seg.work["said_at"] = "a doorstep somewhere"                       # nothing the map knows: the headline again
    assert locator.place_of(seg) == "harbour"
    seg.work["said_at"] = "the Saltby slip, looking across to the Quay Steps"      # both sides: say nothing...
    assert locator.place_of(seg) == "harbour"                          # ...so the headline decides


def test_in_the_old_town_the_locator_goes_down_to_the_streets():
    """2026-11-21: a mile across with the street plan (townplan.py), so Gull's Rest is not the fish quay."""
    def across(pid):
        x0, x1, _, _ = locator.box(pid, 0.57)
        return round(x1 - x0, 2)
    assert across("gulls_rest") == across("fish_quay") == across("library") == locator.STREET_MILES
    assert across("stadium") > locator.STREET_MILES and across("saltby") > locator.STREET_MILES   # out of the old town
    assert across("polgrey") == locator.AREA_MILES
    pygame.init()
    close, wide = locator.picture("gulls_rest", (72, 52), 2, False), locator.picture("polgrey", (72, 52), 2, False)
    roofs = {tuple(c) for c in __import__("newsroom.townplan", fromlist=["ROOFS"]).ROOFS}

    def has_roofs(img):
        return any(tuple(img.get_at((x, y)))[:3] in roofs for x in range(0, img.get_width(), 2)
                   for y in range(0, img.get_height() - 24, 2))
    assert has_roofs(close) and not has_roofs(wide)
