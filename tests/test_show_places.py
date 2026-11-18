"""Pieces in the middle of a show don't open or close it: Coastwide's links, The Last Ferry's desk
pieces, and the rolling news, which never signs off (Full Time's are in test_sport_show.py)."""
import time

from newsroom import schedule, world as world_mod, writers
from newsroom.models import SegmentType


def _at(hh: int, mm: int) -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))


def _user(seg_type, show, part="", hh=19, mm=20):
    return writers.build_prompt(seg_type, world_mod.seed(), target_s=45, show=schedule.get(show), part=part,
                                at_ts=_at(hh, mm))[1]


def test_coastwide_welcomes_viewers_once_and_its_middle_links_carry_on():
    system, _ = writers.build_prompt(SegmentType.links, world_mod.seed(), target_s=45, show=schedule.get("magazine"))
    assert "welcome" not in system
    assert "OPENS Coastwide" in _user(SegmentType.links, "magazine", "open")
    middle = _user(SegmentType.links, "magazine")
    assert "MIDDLE of Coastwide" in middle and "OPENS" not in middle
    close = _user(SegmentType.links, "magazine", "close")
    assert "END of Coastwide" in close and "PLACE IN THE SHOW" not in close


def test_the_last_ferrys_desk_pieces_leave_the_goodnight_to_the_end():
    assert "MIDDLE of The Last Ferry" in _user(SegmentType.links, "late", hh=22, mm=30)
    assert "PLACE IN THE SHOW" not in _user(SegmentType.links, "late", "close", hh=22, mm=55)


def test_the_last_ferrys_guests_and_night_owls_leave_the_goodnight_to_the_end_too():
    """On 2026-11-18 Ruth Carrow's chat at 22:05 ended "Good night, Port Wexley" with the show running on."""
    for seg_type, part in ((SegmentType.interview, ""), (SegmentType.interview, "cont"),
                           (SegmentType.interview, "couch"), (SegmentType.vox_pop, "")):
        assert "MIDDLE of The Last Ferry" in _user(seg_type, "late", part, hh=22, mm=5)
    assert "thanking them is fine" in _user(SegmentType.interview, "late", "couch", hh=22, mm=5)
    assert "OPENS" not in _user(SegmentType.monologue, "late", "open", hh=22, mm=0)
    assert "PLACE IN THE SHOW" not in _user(SegmentType.interview, "late", "close", hh=22, mm=55)


def test_the_rolling_news_never_signs_off():
    for seg_type in (SegmentType.bulletin, SegmentType.interview):
        assert "rolling news" in _user(seg_type, "news", hh=20, mm=30)
    assert "PLACE IN THE SHOW" not in _user(SegmentType.bulletin, "breakfast", "open", hh=6, mm=5)
    assert "rolling news" not in _user(SegmentType.sofa, "breakfast", hh=7, mm=0)


def test_every_middle_piece_of_a_show_that_opens_knows_its_place():
    """Until 2026-11-18 only the pieces _PLACE named had a place: two weeks of Coastwide's interviews, features
    and vox pops all opened "Good evening", and so did 353 of Morning Tide's 376 sofa chats."""
    for seg_type, show, hh in ((SegmentType.interview, "magazine", 19), (SegmentType.feature, "magazine", 19),
                               (SegmentType.vox_pop, "magazine", 19), (SegmentType.consumer, "magazine", 19),
                               (SegmentType.sofa, "breakfast", 7), (SegmentType.interview, "breakfast", 7),
                               (SegmentType.field_report, "breakfast", 7), (SegmentType.vox_pop, "inquiry", 20),
                               (SegmentType.vox_pop, "panel", 20), (SegmentType.bulletin, "phonein", 10),
                               (SegmentType.interview, "sport", 18), (SegmentType.vox_pop, "sport", 18)):
        title = writers._title(schedule.get(show))
        assert f"MIDDLE of {title}" in _user(seg_type, show, hh=hh, mm=50), (show, seg_type)
    assert "welcoming the guest or caller" in _user(SegmentType.interview, "magazine", mm=40)
    assert "welcoming" not in _user(SegmentType.vox_pop, "magazine", mm=40)
    # the openings and closes keep their own words, and the breakfast news may say good morning
    assert "MIDDLE" not in _user(SegmentType.links, "magazine", "open")
    assert "MIDDLE" not in _user(SegmentType.interview, "magazine", "close", hh=19, mm=55)
    breakfast_news = _user(SegmentType.bulletin, "breakfast", hh=7, mm=30)
    assert "a quick good morning is fine" in breakfast_news and "MIDDLE" not in breakfast_news


def test_the_rolling_news_reports_follow_on_without_a_hello():
    for seg_type in (SegmentType.field_report, SegmentType.sport, SegmentType.interview):
        user = _user(seg_type, "news", hh=20, mm=30)
        assert "rolling news" in user and "No hello either" in user
    assert "welcoming the guest" in _user(SegmentType.interview, "news", hh=20, mm=30)
    assert "No hello" not in _user(SegmentType.bulletin, "news", hh=20, mm=30)
