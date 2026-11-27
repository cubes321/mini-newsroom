"""The ticker's weather keeps to the hour: the next weather's headline takes the last one's place, and one left
standing goes after TICKER_WEATHER_S (the 2026-11-15 night's breakfast ticker read "Calm Evening, Clear Spells
Overnight" at 06:04)."""
from __future__ import annotations

from newsroom import player as player_mod
from newsroom import world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Segment
from newsroom.models import SegmentType as T
from newsroom.player import Player


def _air(pl: Player, slot: int, kind: T, headline: str, at: float) -> None:
    pl._start(Segment(slot_id=slot, type=kind, show="news", headline=headline), at)


def test_the_weather_headline_gives_way_and_goes_stale():
    pl = Player(Buffer(), world_mod.seed(), producer=None, audio=False)
    pl.buffer.mark = lambda *a: None
    t = 1_000_000.0
    _air(pl, 1, T.weather, "Calm Evening, Clear Spells Overnight", t)
    _air(pl, 2, T.bulletin, "Harbour wall report due Friday", t + 60)
    _air(pl, 3, T.weather, "Frost Lifts by Mid-Morning", t + 3600)
    assert pl.view(t + 3600).ticker == ["Harbour wall report due Friday", "Frost Lifts by Mid-Morning"]
    later = t + 3600 + player_mod.TICKER_WEATHER_S + 1                   # overnight, no weather since
    assert pl.view(later).ticker == ["Harbour wall report due Friday"]
    _air(pl, 4, T.weather, "Sunny Morning, Cloud Later", later + 60)
    assert pl.view(later + 60).ticker[-1] == "Sunny Morning, Cloud Later"
