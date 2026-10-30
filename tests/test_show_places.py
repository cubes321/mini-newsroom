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
    assert "END of the programme" in close and "PLACE IN THE SHOW" not in close


def test_the_last_ferrys_desk_pieces_leave_the_goodnight_to_the_end():
    assert "MIDDLE of The Last Ferry" in _user(SegmentType.links, "late", hh=22, mm=30)
    assert "PLACE IN THE SHOW" not in _user(SegmentType.links, "late", "close", hh=22, mm=55)


def test_the_rolling_news_never_signs_off():
    for seg_type in (SegmentType.bulletin, SegmentType.interview):
        assert "rolling news" in _user(seg_type, "news", hh=20, mm=30)
    assert "rolling news" not in _user(SegmentType.field_report, "news", hh=20, mm=30)
    assert "PLACE IN THE SHOW" not in _user(SegmentType.bulletin, "breakfast", "open", hh=6, mm=5)
    assert "PLACE IN THE SHOW" not in _user(SegmentType.sofa, "breakfast", hh=7, mm=0)
