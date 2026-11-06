"""Special nights (schedule.SPECIAL_NIGHTS): Coastwide at the Bonfire on 5 November, out on location all
hour with the fireworks at half past seven; and no council on New Year's Eve or election day."""
from __future__ import annotations

from datetime import date, datetime

import pygame
import pytest

from newsroom import calendar, council, scenes, schedule, writers, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentType as T
from newsroom.player import Player
from newsroom.producer import Producer

BONFIRE_NIGHT = date(2026, 11, 5)


def _at(day: date, hh: int, mm: int) -> float:
    return datetime(day.year, day.month, day.day, hh, mm).timestamp()


@pytest.fixture
def by_calendar(monkeypatch):
    monkeypatch.delenv("NEWSROOM_SPECIAL_NIGHT", raising=False)


def test_no_council_on_new_years_eve_or_election_day():
    assert council.election_day(2027) == date(2027, 5, 6) and council.election_day(2028) is None
    assert council.election_day(2031) == date(2031, 5, 1)
    assert not council.meets_on(date(2026, 12, 31)) and not council.meets_on(date(2027, 5, 6))
    assert council.next_meetings(date(2026, 12, 20)) == [date(2027, 1, 14), date(2027, 1, 28)]   # cancelled, not moved
    assert council.next_meetings(date(2027, 5, 1)) == [date(2027, 5, 20), date(2027, 6, 3)]
    assert calendar.next_on("mayor-making", date(2027, 5, 1)).first == date(2027, 5, 20)


def test_coastwide_goes_to_the_bonfire_on_bonfire_night_only(by_calendar):
    show = schedule.show_at(_at(BONFIRE_NIGHT, 19, 5))
    assert show is schedule.BONFIRE and show.id == "magazine" and show.location == "estuary"
    assert show.title == "COASTWIDE AT THE BONFIRE" and show.tod == "night"
    assert schedule.show_at(_at(date(2026, 11, 6), 19, 5)).title == "COASTWIDE"
    assert schedule.show_at(_at(BONFIRE_NIGHT, 18, 50)).id == "sport"
    assert schedule.show_at(_at(BONFIRE_NIGHT, 20, 5)).id != "magazine"
    assert schedule.show_at(_at(date(2027, 11, 5), 19, 5)) is schedule.BONFIRE      # every year


def test_the_switch_forces_or_stops_it(monkeypatch):
    monkeypatch.setenv("NEWSROOM_SPECIAL_NIGHT", "1")
    assert schedule.show_at(_at(date(2026, 11, 3), 19, 5)) is schedule.BONFIRE
    monkeypatch.setenv("NEWSROOM_SPECIAL_NIGHT", "0")
    assert schedule.show_at(_at(BONFIRE_NIGHT, 19, 5)).title == "COASTWIDE"


def test_the_producer_runs_the_bonfire_order_and_marks_every_slot(by_calendar):
    p = Producer(Buffer(), 600, start_ts=_at(BONFIRE_NIGHT, 18, 59))
    slots = [p.plan_one() for _ in range(40)]
    ours = [s for s in slots if s.show == "magazine"]
    assert ours and all(s.work.get("location") == "estuary" and s.work.get("tod") == "night" for s in ours)
    assert all(s.work.get("fireworks") == ["19:30", "19:50"] and s.work.get("bonfire") for s in ours)
    briefs = [s.brief for s in ours]
    assert any("bonfire is about to be lit" in b for b in briefs) and any("guy competition" in b for b in briefs)
    assert not any(s.work.get("location") for s in slots if s.show != "magazine")


def test_the_writers_are_told_where_and_where_the_fireworks_have_got_to(by_calendar):
    show = schedule.BONFIRE
    before, during, after = (schedule.on_location(show, _at(BONFIRE_NIGHT, 19, m)) for m in (5, 35, 55))
    assert "no studio" in before and "go up at 19:30: not yet" in before
    assert "RIGHT NOW" in during and "are over" in after
    assert "at 20:00" in after
    _, user = writers.build_prompt(T.links, world_mod.seed(), target_s=45.0, show=show,
                                   at_ts=_at(BONFIRE_NIGHT, 19, 35))
    assert "ON LOCATION" in user and "RIGHT NOW" in user
    _, user = writers.build_prompt(T.links, world_mod.seed(), target_s=45.0, show=schedule.get("magazine"),
                                   at_ts=_at(BONFIRE_NIGHT, 19, 35))
    assert "ON LOCATION" not in user


def _view(seg: Segment, hh: int, mm: int):
    pl = Player(Buffer(), world_mod.seed(), producer=None, audio=False)
    now = _at(BONFIRE_NIGHT, hh, mm)
    pl.current, pl.line_idx = seg, 0
    pl.seg_start = pl.line_start = now - 0.5
    return pl.view(now)


def _seg(seg_type: T, *speakers: str) -> Segment:
    lines = [Line(speaker=s, guest_name="Bea Kowalczyk" if s == "guest" else None, text="...", duration_s=2.0,
                  mouth_env=[0.5] * 40) for s in speakers]
    return Segment(slot_id=5, type=seg_type, show="magazine", target_s=45, lines=lines,
                   work={"location": "estuary", "fireworks": ["19:30", "19:50"], "tod": "night", "bonfire": True})


def test_the_player_puts_the_whole_show_on_location(by_calendar):
    v = _view(_seg(T.links, "mag_b", "mag_a"), 19, 10)
    assert (v.mode, v.backdrop, v.tod, v.reporter, v.tag) == ("field", "estuary", "night", "mag_a", "LIVE")
    assert v.bonfire and not v.fireworks
    assert _view(_seg(T.interview, "guest", "mag_a"), 19, 35).fireworks
    assert not _view(_seg(T.links, "mag_a"), 19, 50).fireworks
    film = _view(_seg(T.feature, "reporter", "guest"), 19, 40)
    assert (film.mode, film.backdrop, film.reporter, film.tag) == ("field", "estuary", "reporter", "")
    weather = _view(_seg(T.weather, "weather"), 19, 15)
    assert weather.mode == "weather" and not weather.bonfire                 # Gordon stays in the studio
    studio = _seg(T.links, "mag_a")
    studio.work = {}
    assert _view(studio, 19, 10).mode == "studio"


def test_the_fire_and_the_fireworks_draw_and_move():
    pygame.init()
    shots = []
    for t in (0.0, 0.0, 1.3):
        c = pygame.Surface((320, 180))
        c.fill((30, 40, 80))
        scenes.draw_fireworks(c, t)
        scenes.draw_bonfire(c, t)
        shots.append(pygame.image.tobytes(c, "RGB"))
    assert shots[0] == shots[1] and shots[0] != shots[2]                     # the same t, the same sky
    blank = pygame.Surface((320, 180))
    blank.fill((30, 40, 80))
    assert shots[0] != pygame.image.tobytes(blank, "RGB")


def _half(show: schedule.Show, entries) -> float:
    """The entries' length as they came in on 2026-11-05: near half their targets, the adverts in full."""
    return sum(show.target_for(e) * (1.0 if schedule.as_item(e).type is T.ad_break else 0.5) for e in entries)


@pytest.mark.parametrize("slot", sorted(schedule.SPECIAL_NIGHTS))
def test_a_special_night_never_asks_for_the_same_piece_twice_in_its_hour(slot):
    """Coastwide at the Bonfire went round its loop six times, and with one brief each Dev's parkin aired
    six times, the firework code five and the volunteers four (2026-11-05)."""
    show = schedule.SPECIAL_NIGHTS[slot][1]
    head, loop = show.pattern[:show.loop_from], show.pattern[show.loop_from:]
    laps = -(-(3600 - show.closing_s - _half(show, head)) // _half(show, loop))
    assert laps >= 6                                                   # the night's six, at least
    seen: dict[int, list[str]] = {}
    for pos in range(len(show.pattern) + int(laps - 1) * len(loop)):
        item = show.item(pos)
        if item.brief and item.part not in ("open", "close"):
            seen.setdefault(show.loop_from + (pos - show.loop_from) % len(loop) if pos >= show.loop_from else pos,
                            []).append(item.brief)
    for where, briefs in seen.items():
        assert len(set(briefs)) == len(briefs), (where, briefs[0][:60])
    dev = [b for bs in seen.values() for b in bs if "Dev Ramachandran" in b]
    assert len(dev) == 1                                               # his parkin once, in the first lap
