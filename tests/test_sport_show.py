"""Full Time, fifteen minutes of local sport at 18:45 from the sports corner, and the sport in
the news once in three loops: Fran Kellaway at the sports desk, the scores from sport.py.
"""
import time

from newsroom import schedule, world as world_mod, writers
from newsroom.models import SegmentType


def _at(hh: int, mm: int) -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))


def test_full_time_airs_at_a_quarter_to_seven_and_hands_to_coastwide():
    assert schedule.show_at(_at(18, 44)).id == "news"
    assert schedule.show_at(_at(18, 50)).id == "sport"
    assert schedule.show_end(_at(18, 0)) == _at(18, 45)
    assert schedule.show_end(_at(18, 50)) == _at(19, 0)


def test_the_news_has_the_sport_once_in_three_loops():
    news = schedule.get("news")
    assert news.pattern.count(SegmentType.sport) == 1
    assert news.cast_for(SegmentType.sport) == ("sport",)


def test_fran_is_on_the_staff():
    fran = world_mod.seed().character("sport")
    assert fran.name == "Fran Kellaway"


def test_the_sports_desk_gets_the_facts_and_not_the_news_big_story():
    w = world_mod.seed()
    for seg_type, show in ((SegmentType.sport, "news"), (SegmentType.interview, "sport"),
                           (SegmentType.field_report, "sport")):
        system, user = writers.build_prompt(seg_type, w, target_s=60, show=schedule.get(show))
        assert "SPORT FACTS" in user and "Fran" in system
        assert "BIG RUNNING STORY" not in user


def test_the_template_is_fran_with_the_real_result():
    w = world_mod.seed()
    script = writers._template(SegmentType.sport, w, __import__("random").Random(1), schedule.get("sport"))
    assert {l.speaker for l in script.lines} == {"sport"}
    assert "Tides" in script.lines[1].text


def test_nobody_in_town_shares_frans_voice():
    w = world_mod.seed()
    p = w.ensure_person("Maureen Tapp", "night ferry hand", gender="f")
    p.voice = "af_jessica"                                  # cast before Fran took it
    w2 = world_mod._from_dict(world_mod._to_dict(w))
    assert w2.person_by_name("Maureen Tapp").voice in world_mod.GUEST_VOICES_F
    assert "af_jessica" not in world_mod.GUEST_VOICES
