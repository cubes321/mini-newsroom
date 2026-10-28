"""The town's football is worked out, not written: every show quotes the same score, and the
league table adds up.
"""
from datetime import datetime, timedelta

from newsroom import sport, world as world_mod

NOW = datetime(2026, 10, 28, 18, 45)


def test_each_club_plays_every_other_home_and_away():
    fx = sport.fixtures(NOW.date())
    pairs = {(f.home, f.away) for f in fx}
    n = len(sport.CLUBS)
    assert len(fx) == n * (n - 1) and len(pairs) == n * (n - 1)
    assert all(f.kickoff.weekday() == 5 for f in fx)


def test_a_result_is_the_same_every_time_and_only_known_after_full_time():
    f = next(f for f in sport.fixtures(NOW.date()) if sport.CLUB in (f.home, f.away))
    assert sport.result(f) == sport.result(f)
    during = f.kickoff + timedelta(minutes=60)
    after = f.kickoff + timedelta(minutes=sport.FULL_TIME_MIN)
    assert f not in [r.fixture for r in sport.played(during)]
    assert f in [r.fixture for r in sport.played(after)]
    assert "right now" in sport.summary(during)


def test_the_table_adds_up():
    rows = sport.table(NOW)
    assert sum(r["gf"] for r in rows) == sum(r["ga"] for r in rows)
    assert sum(r["w"] for r in rows) == sum(r["l"] for r in rows)
    assert all(r["pts"] == 3 * r["w"] + r["d"] for r in rows)


def test_the_tides_scorers_match_their_goals():
    for r in sport.played(NOW):
        f = r.fixture
        ours = r.home_goals if f.home == sport.CLUB else r.away_goals if f.away == sport.CLUB else 0
        assert len(r.scorers) == ours


def test_every_writer_hears_the_last_result_and_the_next_game():
    brief = world_mod.seed().summary_for_prompt()
    assert "Sport: Tidewater Town FC (the Tides):" in brief
