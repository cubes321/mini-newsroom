"""The weather map (weathermap.py): Gordon's wall screen drawn from the town's map, four spots with a temperature
each worked out from the script's one. Approved on data/contact-sheets/2026-11-21-weather-map.png."""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from newsroom import geography as g, scenes, schedule, weathermap, world as world_mod, writers  # noqa: E402
from newsroom.models import SegmentType as T  # noqa: E402
from newsroom.player import View  # noqa: E402

STATES = ("sunny", "cloudy", "rain", "storm", "snow", "fog", "wind")


def test_the_spots_temperatures_come_from_port_wexleys():
    assert weathermap.spots(9, "sunny") == {"harbour": 9, "polgrey": 8, "greymouth": 9, "pellow_harbour": 10}
    assert weathermap.spots(6, "rain") == {"harbour": 6, "polgrey": 5, "greymouth": 5, "pellow_harbour": 6}
    assert weathermap.spots(0, "snow")["polgrey"] == -2 and weathermap.spots(3, "cloudy")["polgrey"] == 1   # frost
    assert weathermap.spots(4, "fog")["polgrey"] == 2 and weathermap.spots(8, "wind")["greymouth"] == 7
    for state in STATES:                                   # never more than two degrees between any two spots
        t = weathermap.spots(5, state)
        assert t["harbour"] == 5 and max(t.values()) - min(t.values()) <= 2
    assert {pid for pid, *_ in weathermap.SPOTS} == set(weathermap.spots(5, None)) <= set(g.BY_ID)


def test_the_map_is_the_towns_own_coast():
    pygame.init()
    w, h = scenes.WALL_SCREEN.size
    m = weathermap.base((w, h))

    def colour(pid=None, xy=None):
        return tuple(m.get_at(weathermap._at(xy or g.BY_ID[pid].xy, w)))[:3]
    assert colour(xy=(0.0, -6.0)) in (weathermap.SEA, weathermap.SEA_DEEP)        # the sea off Wexley Point
    assert colour(xy=(-0.9, -1.5)) == weathermap.SEA                              # the bay, between the two shores
    assert colour(xy=(6.0, 3.0)) in (weathermap.LAND, weathermap.LAND_HIGH)       # inland, east of the Grey
    assert colour(xy=(-6.0, 2.0)) in (weathermap.LAND, weathermap.LAND_HIGH)      # and on the Saltby side
    for pid, *_ in weathermap.SPOTS:                       # every spot is on the screen, above the lower third
        x, y = weathermap._at(g.BY_ID["main_street" if pid == "harbour" else pid].xy, w)
        assert 0 < x < w and 0 < y < scenes.LOWER_THIRD_Y - scenes.WALL_SCREEN.y, pid


def test_every_sky_draws_with_its_spots_named():
    pygame.init()
    pygame.display.set_mode((320, 180))
    canvas = pygame.Surface(scenes.CANVAS)
    for state in STATES:
        v = View(mode="weather", show="news", speaker="weather", map_state=state, temp_c=4)
        scenes.render(canvas, v, 12.3)
        said = " ".join(s for s, *_ in scenes._layer)
        for name in ("Greymouth", "Polgrey", "Port Wexley", "Pellow Harbour"):
            assert name in said, (state, name)
        assert f" {weathermap.spots(4, state)['polgrey']}°" in said
    scenes.render(canvas, View(mode="weather", show="news", speaker="weather"), 1.0)   # before the first forecast
    assert "Polgrey" in " ".join(s for s, *_ in scenes._layer)


def test_gordon_is_told_the_spots_and_nobody_else_is():
    w = world_mod.seed()
    weather = writers.build_prompt(T.weather, w, target_s=60, show=schedule.get("news"))[1]
    assert "THE WEATHER MAP behind Gordon" in weather and "Polgrey" in weather
    assert "THE WEATHER MAP" not in writers.build_prompt(T.bulletin, w, target_s=60, show=schedule.get("news"))[1]
