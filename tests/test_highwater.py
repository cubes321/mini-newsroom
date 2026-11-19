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
                after = next(a for a in r["after"] if a["who"] == w["who"])
                assert w["from"] <= r["tide"] and after["banked"] == w["kept"]
                if w["ring"]:                                                       # the life ring: saved, where they are
                    assert after["step"] == w["to"] == w["from"] and w["lost"] == 0 and after["rings"] == w["rings_left"]
                    continue
                seen += 1
                assert after["step"] == w["to"] == r["tide"] + 1 and after["in_hand"] == 0   # nothing in hand from the water
                if i + 1 < len(g["rounds"]):
                    nxt = next(t for t in g["rounds"][i + 1]["turns"] if t["who"] == w["who"])
                    assert nxt["choice"] == hw.OUT                                   # wringing out
            saved = {w["who"] for w in r["washed"] if w["ring"]}
            assert all(a["step"] > r["tide"] for a in r["after"] if a["who"] not in saved)   # nobody else in the water
    assert seen > 100


def test_a_prize_is_only_in_hand_if_climbed_onto_since_starting_again():
    """2026-11-19, the first engine: washed off, a climber restarted above the prizes and had them in hand, and in
    2,000 games nobody went home with less than the step-6 prize."""
    low, mid, top = hw.PRIZE_STEPS
    c = hw.Climber("Jan", 0.8, False, step=mid + 1, base=mid)
    assert c.in_hand == 0                                    # the step-mid prize is where the water put her: not climbed
    c.step = top
    assert c.in_hand == top
    c.banked = top
    assert c.in_hand == 0                                    # made fast: banked, not in hand


def test_making_fast_banks_whats_in_hand():
    for s in range(300):
        for r in _game(s)["rounds"]:
            for t in r["turns"]:
                if t["choice"] == hw.FAST:
                    assert t["banked"] >= hw.PRIZE_STEPS[0] and t["in_hand"] == 0


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
    share = {p: prizes.count(p) / len(prizes) for p in (0, *hw.PRIZE_STEPS)}
    assert 0.15 <= share[0] <= 0.4 and 0.05 <= share[hw.PRIZE_STEPS[-1]] <= 0.3 and all(v > 0.05 for v in share.values())
    assert statistics.mean(cautious) > statistics.mean(bold) - 0.5           # temperament matters
    assert statistics.mean(bold) > 3                                         # bold is a worse bet, never a hopeless one


def test_the_harbourmasters_round_hands_out_life_rings_and_a_ring_saves_one_tide():
    """Added the same evening, at the user's choice, to fill the half hour with game: quick-fire questions on the town
    at halfway, a race for each; a right answer wins a life ring (one each at most), thrown when the tide reaches its
    holder."""
    thrown = 0
    for s in range(400):
        g = _game(s)
        h = g["harbour"]
        assert len(h["questions"]) == hw.HARBOUR_QUESTIONS and all(v <= hw.RING_CAP for v in h["rings"].values())
        won = {}
        for x in h["questions"]:
            assert (x["second"] is None) == x["right"]                              # a second go only after a miss
            if x["ring"]:
                assert x["ring"] == (x["first"] if x["right"] else x["second"]) and (x["right"] or x["second_right"])
                won[x["ring"]] = won.get(x["ring"], 0) + 1
        assert won == {n: v for n, v in h["rings"].items() if v}
        before = {a["who"]: a.get("rings", 0) for a in g["rounds"][hw.HARBOUR_AFTER - 1]["after"]}
        assert not any(before.values())                                             # none before the round
        for r in g["rounds"][hw.HARBOUR_AFTER:]:
            thrown += sum(w["ring"] for w in r["washed"])
        rings_at_end = {a["who"]: a["rings"] for a in g["rounds"][-1]["after"]}
        used = {n: sum(w["ring"] for r in g["rounds"] for w in r["washed"] if w["who"] == n) for n in rings_at_end}
        assert all(h["rings"][n] - used[n] == rings_at_end[n] for n in rings_at_end)    # a ring is thrown once
    assert thrown > 100
