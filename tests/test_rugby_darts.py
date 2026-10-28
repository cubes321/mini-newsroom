"""The Wreckers' rugby and the pub darts league are worked out like the football: the same score
everywhere, tables that add up, and both on Full Time before the order wraps.
"""
from collections import Counter
from datetime import datetime, timedelta

from newsroom import darts, rugby, schedule, sport, world as world_mod, writers
from newsroom.models import SegmentType

NOW = datetime(2026, 10, 28, 18, 45)


def test_each_rugby_club_plays_every_other_home_and_away_on_saturdays():
    fx = rugby.fixtures(NOW.date())
    n = len(rugby.CLUBS)
    assert len(fx) == n * (n - 1) and len({(f.home, f.away) for f in fx}) == n * (n - 1)
    assert all(f.kickoff.weekday() == 5 for f in fx)


def test_a_rugby_result_is_fixed_and_only_known_after_full_time():
    f = next(f for f in rugby.fixtures(NOW.date()) if rugby.CLUB in (f.home, f.away))
    assert rugby.result(f) == rugby.result(f)
    assert f not in [r.fixture for r in rugby.played(f.kickoff + timedelta(minutes=60))]
    assert f in [r.fixture for r in rugby.played(f.kickoff + timedelta(minutes=rugby.FULL_TIME_MIN))]
    assert "right now" in rugby.summary(f.kickoff + timedelta(minutes=60))


def test_the_rugby_table_adds_up_with_bonus_points():
    rows = rugby.table(NOW)
    assert sum(r["pf"] for r in rows) == sum(r["pa"] for r in rows)
    assert sum(r["w"] for r in rows) == sum(r["l"] for r in rows)
    assert all(r["pts"] == 4 * r["w"] + 2 * r["d"] + r["bonus"] for r in rows)
    assert any(r["bonus"] for r in rows)


def test_bonus_points():
    win4, lose_close, lose_big = rugby.Side(4, 2, 0), rugby.Side(3, 2, 0), rugby.Side(0, 0, 1)
    assert rugby.league_points(win4, lose_close) == 5          # a win with four tries
    assert rugby.league_points(lose_close, win4) == 1          # 19-24: lost by five
    assert rugby.league_points(lose_big, win4) == 0


def test_the_wreckers_try_scorers_match_their_tries():
    for r in rugby.played(NOW):
        f = r.fixture
        ours = r.home if f.home == rugby.CLUB else r.away if f.away == rugby.CLUB else rugby.Side(0, 0, 0)
        assert len(r.try_scorers) == ours.tries


def test_each_pub_meets_every_other_four_times_on_tuesday_or_thursday_nights():
    fx = darts.fixtures(NOW.date())
    pairs = Counter(frozenset((f.home, f.away)) for f in fx)
    assert set(pairs.values()) == {2 * darts.MEETINGS}
    assert {f.start.weekday() for f in fx} == set(darts.NIGHTS)
    assert not [f for f in fx if (f.start.month, f.start.day) in ((12, 24), (12, 31))]
    weeks = Counter((f.round, f.home) for f in fx) + Counter((f.round, f.away) for f in fx)
    assert set(weeks.values()) == {1}                          # one match a week for every pub


def test_a_darts_match_is_nine_games_and_the_table_adds_up():
    done = darts.played(NOW)
    assert done and all(r.home_games + r.away_games == darts.GAMES for r in done)
    rows = darts.table(NOW)
    assert sum(r["gf"] for r in rows) == sum(r["ga"] for r in rows)
    assert all(r["pts"] == r["gf"] for r in rows)
    regulars = {n for _, _, regs in darts.PUBS for n in regs}
    assert all(r.checkout[0] in regulars and set(r.one_eighties) <= regulars for r in done)


def test_a_darts_result_waits_for_the_last_leg():
    f = darts.fixtures(NOW.date())[0]
    assert f not in [r.fixture for r in darts.played(f.start + timedelta(minutes=60))]
    assert f in [r.fixture for r in darts.played(f.start + timedelta(minutes=darts.DONE_MIN))]


def test_every_writer_hears_all_three():
    brief = world_mod.seed().summary_for_prompt()
    assert "Sport: Tidewater Town FC (the Tides):" in brief
    assert "Port Wexley RFC (the Wreckers, rugby):" in brief and darts.LEAGUE in brief


def test_the_sports_desk_gets_the_rugby_and_darts_facts():
    system, user = writers.build_prompt(SegmentType.sport, world_mod.seed(), target_s=60, show=schedule.get("sport"))
    assert "RUGBY FACTS" in user and "DARTS FACTS" in user and "DARTS FACTS" in system
    assert "RUGBY FACTS" in sport.for_prompt(NOW)


def test_full_time_has_the_rugby_and_the_darts_before_it_wraps():
    show = schedule.get("sport")
    briefs = [show.item(i).brief for i in range(show.loop_from)]
    assert any("rugby" in b for b in briefs) and any("darts" in b for b in briefs)
