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


def test_a_planned_next_loses_the_result_of_a_game():
    """On 2026-11-21 the story desk planned the Tides' match before it was played, "it ends one apiece"; the sports
    desk made it 3-1, and Coastwide and The Last Ferry gave the draw from the story."""
    planned = ("On Saturday 21 November the Tides kick off at three on a pitch still hard with frost, Hal Anand "
               "watching from the stand with his shoulder strapped; Saltby lead at the break, the Tides level from a "
               "corner, and it ends one apiece with the home crowd on the referee \u2014 the match report closes the thread.")
    assert sport.without_result(planned) == ("On Saturday 21 November the Tides kick off at three on a pitch still hard "
                                            "with frost, Hal Anand watching from the stand with his shoulder strapped.")
    assert sport.without_result("On Thursday the Cannery Tap beat the Railway seven-two at darts.") == ""
    assert sport.without_result("On Saturday the Wreckers travel to Saltby: Mitchell is fit, and they win by ten.") == \
        "On Saturday the Wreckers travel to Saltby."
    # nothing to take off: no side named, or no result given
    for fine in ("On Tuesday the harbour office wins the tender it wanted.",
                 "On Saturday 28 November the Tides are away at Polgrey Rangers, and the supporters' coach leaves at one.",
                 "On Monday the two panels are surveyed, three on the list still to do.", ""):
        assert sport.without_result(fine) == fine
    # words that only look like a result, in stories that happen to name a side
    for fine in ("On Saturday Alan weighs the squash and won't say which show, and a plot-holder from Saltby Road enters one.",
                 "On Saturday, with the Tides crowd on the quay, Dougal fits the rope: one short beat on the bulletin and done.",
                 "On Wednesday the traders' meeting at the Anchor and Bell ends with no start date."):
        assert sport.without_result(fine) == fine
    # a result the story already has is not being made up
    card = "On Thursday 26 November, darts night, the 28-19 card goes up beside the Ferryman's board."
    assert sport.without_result(card, known="The Crown at Saltby Take the Ferryman 28-19") == card
    assert sport.without_result(card) == "On Thursday 26 November, darts night."
    assert sport.without_result("On Tuesday the Railway go to the Lantern and the match goes down five-three.") == ""
    assert {"Tides", "Wreckers", "Saltby Rovers", "Cannery Tap", "Tidewater Town FC"} <= set(sport.sides())
