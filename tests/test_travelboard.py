"""The travel board (travelboard.py) and the route map (routemap.py): the town's map on the wall while the travel
is read, and The Coast Road's journey in the corner. Approved on
data/contact-sheets/2026-11-21-travel-board-and-route-map.png."""
from __future__ import annotations

import os
from datetime import datetime
from types import SimpleNamespace

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from newsroom import geography as g, player, routemap, scenes, schedule, tides, travelboard as tb  # noqa: E402
from newsroom.models import Line, Segment, SegmentType as T  # noqa: E402
from newsroom.player import View  # noqa: E402

DAY = datetime(2026, 11, 23)             # high 05:51, low 12:03, high 18:16


def _at(h, m=0):
    return DAY.replace(hour=h, minute=m)


def test_the_boards_rows_are_tides_pys_facts():
    ferry, bus, tide = tb.lines(_at(10, 20), "cloudy")
    assert ferry == ("FERRY", "none 11:13-12:53, last 23:15", tb.FIGURE)          # the low-water gap still to come
    assert bus[:2] == ("BUS", "hourly, round by Polgrey") and g.BUS_EVERY_MIN == 60 and "polgrey" in g.BUS_ROUTE
    assert tide[:2] == ("TIDE", "high 18:16 5.4m  low 12:03 0.5m")                # the next of each from now
    assert tb.lines(_at(12, 3), "sunny")[0] == ("FERRY", "none till 12:53, low water", tb.OFF)
    assert tb.lines(_at(14), "sunny")[0] == ("FERRY", "every 30 min, last 23:15", tb.GOOD)
    assert tb.lines(_at(10, 20), "storm")[0] == ("FERRY", "off: storm", tb.OFF)
    assert tb.lines(_at(23, 40), "sunny")[0] == ("FERRY", "finished for today", tb.OFF)
    said = tides.for_prompt(DAY.date(), "cloudy")                                  # what the presenter is given
    assert "the last ferry leaves at 23:15" in said and "none 11:13-12:53" in said and "18:16 (5.4 m)" in said


def test_whoever_reads_the_travel_stands_at_the_wall_with_the_board_up():
    me = SimpleNamespace(line_idx=0)
    travel = next(schedule.as_item(e) for e in schedule.SHOWS["phonein"].pattern
                  if tb.is_travel(schedule.as_item(e).brief))
    seg = Segment(slot_id=1, type=T.links, show="phonein", brief=travel.brief,
                  lines=[Line(speaker="host_b", text="The travel now.", duration_s=4.0)])
    v = View(mode="studio", show="phonein", speaker="host_b")
    player.Player._studio_shot(me, seg, v)
    assert (v.shot, v.board, v.wall_label, v.presenter) == ("wall", "travel", "TRAVEL", "host_b")
    gap = View(mode="studio", show="phonein", speaker=None)                 # between two lines: nobody speaking
    player.Player._studio_shot(me, seg, gap)
    assert (gap.board, gap.presenter) == ("travel", "host_b")              # still Jonah at the wall, not the anchor
    seg.brief = "Jonah opens Have Your Say: today's question"
    v = View(mode="studio", show="phonein", speaker="host_b")
    player.Player._studio_shot(me, seg, v)
    assert v.board == "" and v.shot != "wall"
    assert not tb.is_travel(None) and not tb.is_travel("a day out by bus: the travel")


def test_the_board_is_drawn_with_its_rows_and_places(monkeypatch):
    pygame.init()
    pygame.display.set_mode((320, 180))
    monkeypatch.setattr(schedule, "now", lambda: _at(10, 20).timestamp())
    canvas = pygame.Surface(scenes.CANVAS)
    for sky in ("cloudy", "storm", None):
        scenes.render(canvas, View(mode="studio", show="phonein", shot="wall", board="travel", wall_label="TRAVEL",
                                   presenter="host_b", speaker="host_b", weather=sky), 3.2)
        said = [s for s, *_ in scenes._layer]
        for word in ("FERRY", "BUS", "TIDE", "Saltby", "Polgrey", "Port Wexley", "TRAVEL"):
            assert word in said, (sky, word)
        assert ("off: storm" in said) == (sky == "storm")
    w = scenes.WALL_SCREEN.w                                                       # both ends of the crossing show
    for pid in g.FERRY:
        x, y = scenes.weathermap._at(g.BY_ID[pid].xy, w, tb.WINDOW)
        assert 0 < x < w and 0 < y < scenes.LOWER_THIRD_Y - scenes.WALL_SCREEN.y


def test_the_route_map_keeps_every_stop_its_number_and_fits_the_route():
    legs = routemap.legs_of([
        {"stops": [{"place": "the Quay Steps", "backdrop": "harbour", "where": "harbour"},
                   {"place": "a doorstep somewhere", "backdrop": "farm"},
                   {"place": "Saltby green", "backdrop": "village", "where": "saltby"}]},
        {"stops": [{"place": "the Greymouth light", "backdrop": "lighthouse", "where": "greymouth_point"},
                   {"place": "Polgrey Bridge", "backdrop": "village", "where": "polgrey"}]}])
    assert legs == [["harbour", None, "saltby"], ["greymouth_point", "polgrey"]]   # the unplaced stop keeps its place
    x0, x1, y1 = routemap.window_for(legs, 0.6)
    assert x1 - x0 >= routemap.MIN_MILES
    for leg in legs:
        for pid in filter(None, leg):
            x, y = g.BY_ID[pid].xy
            assert x0 < x < x1 and y1 - (x1 - x0) * 0.6 < y < y1, pid
    assert routemap.window_for([[None]], 0.6) == scenes.weathermap.WINDOW
    pygame.init()
    pygame.display.set_mode((320, 180))
    canvas = pygame.Surface(scenes.CANVAS)
    scenes._layer.clear()
    routemap.draw(canvas, routemap.RECT, legs, 1, 1, 0.0, scenes.text, "Leg 1 of 6: The First Crossing")   # to a stop
    routemap.draw(canvas, routemap.RECT, legs, 2, None, 0.0, scenes.text, "Leg 2 of 6")                      # it can't place
    assert any("Leg 1 of 6" in s for s, *_ in scenes._layer)
    x, y, w, h = routemap.RECT                                    # under the clock, above the lower third
    assert y >= 16 and y + h <= scenes.LOWER_THIRD_Y and x + w <= scenes.CANVAS[0]


def test_the_travel_item_goes_through_the_player_to_the_board(tmp_path):
    from newsroom import adverts, world as world_mod
    from newsroom.buffer import Buffer
    from newsroom.models import SegmentState
    from newsroom.producer import Producer

    buf = Buffer()
    pl = player.Player(buf, world_mod.seed(), Producer(buf, 600), audio=False, ads=adverts.AdPool(tmp_path / "ads"))
    travel = next(schedule.as_item(e) for e in schedule.SHOWS["phonein"].pattern
                  if tb.is_travel(schedule.as_item(e).brief))
    seg = Segment(slot_id=0, type=T.links, show="phonein", brief=travel.brief, state=SegmentState.ready,
                  headline="Ferry gap at low water", lines=[Line(speaker="host_b", text="The travel.", duration_s=6.0)])
    buf.submit(seg)
    buf.mark(seg, SegmentState.ready)
    now = 1_000_000.0
    pl.update(now)
    v = pl.view(now + 1.0)
    assert pl.current is seg and (v.mode, v.shot, v.board, v.presenter) == ("studio", "wall", "travel", "host_b")
    pygame.init()
    pygame.display.set_mode((320, 180))
    scenes.render(pygame.Surface(scenes.CANVAS), v, 1.0)
    assert "FERRY" in [s for s, *_ in scenes._layer]
