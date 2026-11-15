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


def test_the_test_card_says_when_that_days_programmes_resume(by_calendar, tmp_path):
    """next_start looked only in the ordinary day: 06:00 on Christmas morning, when breakfast is at seven, and
    StopIteration (the station off air) for a show the ordinary day doesn't have."""
    from newsroom import adverts
    from newsroom.buffer import Buffer
    from newsroom.models import Line, SegmentState
    from newsroom.player import Player
    from newsroom.producer import Producer

    assert schedule.next_start("overnight", _at(AFTER, 3)) == "06:00"
    assert schedule.next_start("overnight", _at(DAY, 5, 55)) == "07:00"
    assert schedule.next_start("midnight", _at(DAY, 0, 10)) == "00:30"
    assert schedule.next_start("midnight") == "" and schedule.next_start("overnight") == "06:00"

    buf = Buffer()
    pl = Player(buf, world_mod.seed(), Producer(buf, 600), audio=False, ads=adverts.AdPool(tmp_path / "ads"))
    card = Segment(slot_id=0, type=T.testcard, lines=[Line(speaker="anchor", text="", duration_s=120.0)])
    buf.submit(card)
    buf.mark(card, SegmentState.ready)
    for when, resume in ((_at(DAY, 5, 55), "07:00"), (_at(DAY, 0, 10), "00:30")):
        pl.update(when)
        assert pl.current is card and pl.view(when).resume_at == resume
        pl._resume_of = ("", "")


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
        assert schedule.show_at(_at(DAY, 11, 20)).id == "closedown"             # Channel 8 is off air by day
    finally:
        undo()


def test_a_tale_is_told_in_breaths_in_the_middle_of_the_hour_and_two_come_before_a_break(by_calendar):
    """The scratch run, 2026-11-07: one tale came as one line of over a thousand characters, twice, and
    opened "Good evening, and welcome"; and an ad break after every tale."""
    w = world_mod.seed()
    system, user = writers.build_prompt(T.links, w, target_s=300, show=christmas.TALES, brief="THE WREN HUNT",
                                        at_ts=_at(EVE, 20, 20))
    assert "six to ten lines" in system and "PLACE IN THE SHOW: the MIDDLE of Hugh's Christmas Tales" in user
    loop = [schedule.as_item(e).type for e in christmas.TALES.pattern[christmas.TALES.loop_from:]]
    assert loop == [T.links, T.links, T.ad_break]


def test_the_service_comes_from_the_harbour_church_dressed_for_christmas(monkeypatch):
    """The church is a place in town all year (approved 2026-11-15); from Christmas Eve to Twelfth Night its
    picture is the dressed one, and the built pictures are kept apart, since the station is on through midnight."""
    import pygame

    from newsroom import backdrops, locations

    church = locations.BY_ID["church"]
    assert christmas.CAROLS.location == "church" and church.interior and "church" in locations.BACKDROP_IDS
    assert backdrops.has_art("church") and (backdrops.ART_DIR / "church_christmas.png").exists()
    for d, yes in ((date(2026, 12, 23), False), (EVE, True), (DAY, True), (date(2026, 12, 31), True),
                   (date(2027, 1, 6), True), (date(2027, 1, 7), False), (date(2026, 7, 1), False)):
        assert christmas.dressed(_at(d, 9)) is yes, d
    monkeypatch.setattr(schedule, "_offset_s", _at(date(2026, 7, 1), 9) - time.time())
    assert not christmas.dressed()                                             # July, on the station's clock
    monkeypatch.setenv("NEWSROOM_SPECIAL_DAY", "Christmas Day")               # a rehearsal forcing the day
    assert christmas.dressed() and christmas.DRESSED["church"]() == "christmas"
    monkeypatch.setenv("NEWSROOM_SPECIAL_DAY", "0")
    assert not christmas.dressed() and christmas.DRESSED["church"]() == ""
    assert backdrops.DRESSED["church"] is christmas.DRESSED["church"]          # scenes registers it

    monkeypatch.setitem(backdrops.DRESSED, "church", lambda: "")
    assert backdrops._art_file(church, "day")[0].name == "church.png"
    plain = backdrops.surface("church")
    monkeypatch.setitem(backdrops.DRESSED, "church", lambda: "christmas")
    assert backdrops._art_file(church, "day")[0].name == "church_christmas.png"
    dressed = backdrops.surface("church")
    assert dressed is not plain
    assert pygame.image.tobytes(dressed, "RGB") != pygame.image.tobytes(plain, "RGB")
    assert backdrops.picture("church", "day", None, (98, 58)) is not None
    monkeypatch.setitem(backdrops.DRESSED, "church", lambda: "")
    assert backdrops.surface("church") is plain                                # back to the plain one, from the cache
    hall = locations.BY_ID["village_hall"]                                     # a place with no dressing: as before
    assert backdrops._art_file(hall, "day")[0].name == "village_hall.png"
