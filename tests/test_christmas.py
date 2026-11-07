"""Christmas Eve, Christmas Day and Boxing Day: days of their own, chosen by the calendar (christmas.py).
The model is off (conftest): the stand-in scripts show each item is wired; nothing goes to the network."""
from __future__ import annotations

import time
from datetime import date

import pytest

from newsroom import assets, christmas, schedule, scenes, writers, world as world_mod
from newsroom.models import Segment, SegmentType as T


def _at(d: date, h: int, m: int = 0) -> float:
    return time.mktime((d.year, d.month, d.day, h, m, 0, 0, 0, -1))


EVE, DAY, BOXING, AFTER = date(2026, 12, 24), date(2026, 12, 25), date(2026, 12, 26), date(2026, 12, 27)


@pytest.fixture
def by_calendar(monkeypatch):
    monkeypatch.delenv("NEWSROOM_SPECIAL_DAY", raising=False)     # the calendar decides, as on air


def test_the_three_days_follow_the_calendar(by_calendar):
    title = lambda d, h, m=0: schedule.show_at(_at(d, h, m)).title
    assert title(EVE, 14) == "PORT WEXLEY NEWS" and title(EVE, 19, 10) == "COASTWIDE ON CHRISTMAS EVE"
    assert title(EVE, 20, 40) == "HUGH'S CHRISTMAS TALES" and title(EVE, 22, 30) == "THE LAST FERRY: CHRISTMAS EVE"
    assert title(EVE, 23, 45) == "MIDNIGHT ON THE QUAY" and title(DAY, 0, 15) == "MIDNIGHT ON THE QUAY"
    assert schedule.show_end(_at(EVE, 23, 45)) == _at(DAY, 0, 30)            # the bells, then the test card
    assert title(DAY, 6) == "PORT WEXLEY NEWS" and title(DAY, 7, 30) == "MORNING TIDE: CHRISTMAS MORNING"
    assert [title(DAY, h, m) for h, m in ((10, 20), (11, 20), (12, 30), (13, 30), (15, 5), (15, 30), (19, 30))] == [
        "THE CHRISTMAS MORNING SERVICE", "THE CHRISTMAS DAY SWIM", "ROCK POOL'S CHRISTMAS",
        "OUT AND ABOUT AT CHRISTMAS", "THE MAYOR'S CHRISTMAS MESSAGE", "CHRISTMASES PAST",
        "COASTWIDE ON CHRISTMAS NIGHT"]
    assert title(BOXING, 11, 20) == "THE BOXING DAY DIP" and title(BOXING, 13, 10) == "QUAYSIDE: THE BOXING DAY SALES"
    assert title(BOXING, 14, 30) == "FULL TIME: BOXING DAY" and title(BOXING, 19, 30) == "COASTWIDE"
    assert title(AFTER, 11, 20) == "PORT WEXLEY NEWS" and title(AFTER, 20, 10) == "THE INQUIRY"


def test_the_writers_get_the_version_that_airs_then(by_calendar):
    """On Bonfire Night 2026-11-05 the writers got the ordinary Coastwide: not one prompt said where it was."""
    w = world_mod.seed()
    eve = schedule.get("magazine", _at(EVE, 19, 20))
    assert eve.title == "COASTWIDE ON CHRISTMAS EVE" and eve.location == "harbour"
    assert schedule.get("magazine").title == "COASTWIDE" and schedule.get("magazine", _at(AFTER, 19, 20)).location == ""
    _, user = writers.build_prompt(T.vox_pop, w, target_s=60, show=eve, at_ts=_at(EVE, 19, 20),
                                   brief="the crowd at the carols")
    assert "ON LOCATION: Coastwide on Christmas Eve" in user


def test_every_new_programme_has_a_prompt_and_a_stand_in_in_its_cast(by_calendar):
    w = world_mod.seed()
    for show in christmas.NEW_SHOWS:
        for e in show.pattern + show.closing:
            item = schedule.as_item(e)
            if item.type in (T.bumper, T.ad_break):
                continue
            assert writers.SHOW_SYSTEMS[show.id][item.type], (show.id, item.type)
            brief = item.brief if isinstance(item.brief, str) else item.brief[0]
            seg = Segment(slot_id=1, type=item.type, show=show.id, part=item.part, brief=brief, target_s=60,
                          nominal_start_ts=_at(DAY, 12))
            writers.script_segment(seg, w)
            assert seg.lines and {l.speaker for l in seg.lines} <= set(show.cast_for(item.type)) | {"guest"}, (
                show.id, item.type, {l.speaker for l in seg.lines})
    msg = Segment(slot_id=2, type=T.interview, show="mayor", brief="the message", target_s=330,
                  nominal_start_ts=_at(DAY, 15, 2))
    writers.script_segment(msg, w)
    assert {l.guest_name for l in msg.lines} == {"Helen Strand"} and {l.speaker for l in msg.lines} == {"guest"}


def test_the_new_programmes_have_idents_on_a_shows_music_and_sets():
    for show in christmas.NEW_SHOWS:
        assert show.id in assets.IDENTS and assets.IDENT_MUSIC[show.id] in assets.IDENTS
    assert scenes.SHOW_SETS["tales"] == "studio_late" and scenes.SHOW_SETS["mayor"] == "council_chamber"
    assert writers._title(christmas.TALES) == "Hugh's Christmas Tales"


def test_another_channel_has_no_christmas(by_calendar):
    import entertainment

    undo = entertainment.use()
    try:
        assert schedule.show_at(_at(DAY, 11, 20)).id == "overnight"
    finally:
        undo()
