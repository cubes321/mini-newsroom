"""High Water's game (entertainment/highwater.py; rules agreed with the user 2026-11-19): played in code, as Wits'
darts are. No model, no network."""
from __future__ import annotations

import random
import statistics

from entertainment import highwater as hw

PAIR = [{"name": "Jan Pascoe", "ability": 0.75, "bold": False}, {"name": "Dev Hocking", "ability": 0.7, "bold": True}]


def _game(seed, pair=PAIR):
    return hw.play(random.Random(seed), pair)


def test_the_same_night_plays_the_same_game():
    assert _game(11) == _game(11) and _game(11) != _game(12)


def test_the_tide_only_rises_one_to_three_steps_a_round_and_never_covers_the_top():
    for s in range(300):
        g = _game(s)
        tide = hw.TIDE_START
        for r in g["rounds"]:
            assert r["tide_from"] == tide and 1 <= r["roll"] <= 3 and r["tide"] == min(hw.TIDE_CAP, tide + r["roll"])
            tide = r["tide"]
        assert g["tide"] == tide < hw.STEPS


def test_every_turn_moves_by_the_rules():
    for s in range(300):
        for r in _game(s)["rounds"]:
            for t in r["turns"]:
                d = t["to"] - t["from"]
                if t["choice"] in (hw.FAST, hw.OUT):
                    assert d == 0 and t["right"] is None
                elif t["choice"] == hw.PADDLE:
                    assert d == (1 if t["right"] and t["from"] < hw.STEPS else 0)
                elif t["right"]:
                    assert t["to"] == min(hw.STEPS, t["from"] + 2)
                else:
                    assert t["to"] == max(hw.START, t["from"] - 1)
                assert hw.START <= t["to"] <= hw.STEPS


def test_the_tide_washes_off_whoever_it_reaches_who_keeps_what_was_banked_and_sits_out_a_turn():
    seen = 0
    for s in range(300):
        g = _game(s)
        for i, r in enumerate(g["rounds"]):
            for w in r["washed"]:
                seen += 1
                after = next(a for a in r["after"] if a["who"] == w["who"])
                assert w["from"] <= r["tide"] and after["step"] == w["to"] == r["tide"] + 1
                assert after["banked"] == w["kept"] and after["in_hand"] == 0          # nothing in hand from the water
                if i + 1 < len(g["rounds"]):
                    nxt = next(t for t in g["rounds"][i + 1]["turns"] if t["who"] == w["who"])
                    assert nxt["choice"] == hw.OUT                                   # wringing out
            stood = {a["who"]: a["step"] for a in r["after"]}
            assert all(step > r["tide"] for step in stood.values())                 # nobody left in the water
    assert seen > 100


def test_a_prize_is_only_in_hand_if_climbed_onto_since_starting_again():
    """2026-11-19, the first engine: washed off, a climber restarted above the prizes and had them in hand, and in
    2,000 games nobody went home with less than the step-6 prize."""
    c = hw.Climber("Jan", 0.8, False, step=8, base=7)
    assert c.in_hand == 0                                    # step 6 is below where the water put her
    c.step = 9
    assert c.in_hand == 9
    c.banked = 9
    assert c.in_hand == 0                                    # made fast: banked, not in hand


def test_making_fast_banks_whats_in_hand():
    for s in range(300):
        for r in _game(s)["rounds"]:
            for t in r["turns"]:
                if t["choice"] == hw.FAST:
                    assert t["banked"] >= 3 and t["in_hand"] == 0


def test_the_higher_climber_plays_the_spring_tide_and_needs_two_of_three():
    for s in range(300):
        g = _game(s)
        sp = g["spring"]
        top = max(g["results"], key=lambda r: r["step"])
        assert next(r for r in g["results"] if r["who"] == sp["who"])["step"] == top["step"]
        assert len(sp["answers"]) == hw.SPRING_QUESTIONS and sp["won"] == (sum(sp["answers"]) >= hw.SPRING_NEEDED)
        assert [r["who"] for r in g["results"] if r["star"]] == ([sp["who"]] if sp["won"] else [])
        last = {a["who"]: a for a in g["rounds"][-1]["after"]}
        for res in g["results"]:
            assert res["prize"] == max(last[res["who"]]["banked"], last[res["who"]]["in_hand"])


def test_over_many_nights_the_tide_bites_most_nights_and_the_prizes_spread():
    """The balance agreed in the build (2026-11-19), with room either side."""
    washed = star = 0
    prizes, bold, cautious = [], [], []
    for s in range(2000):
        rng = random.Random(f"hw-{s}")
        pair = [{"name": n, "ability": rng.uniform(0.6, 0.85), "bold": rng.random() < 0.5} for n in ("A", "B")]
        g = _game(s, pair)
        washed += any(r["washed"] for r in g["rounds"])
        star += g["spring"]["won"]
        for res, c in zip(g["results"], pair):
            prizes.append(res["prize"])
            (bold if c["bold"] else cautious).append(res["prize"])
    assert 0.6 <= washed / 2000 <= 0.9 and 0.35 <= star / 2000 <= 0.65
    share = {p: prizes.count(p) / len(prizes) for p in (0, 3, 6, 9)}
    assert 0.15 <= share[0] <= 0.4 and share[9] >= 0.05 and all(v > 0.05 for v in share.values())
    assert statistics.mean(cautious) > statistics.mean(bold) - 0.5           # temperament matters, neither a sure thing
