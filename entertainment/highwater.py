"""High Water: Channel 8's gameshow at 18:00 (docs/ENGINE.md, "High Water"; the format, the host and the rules agreed
with the user on 2026-11-19).

Two residents a night climb the harbour steps against the tide, Des Kneebone hosting. This module is the game,
played in code at booking time as Wits' darts are (oche.py), so every step, answer and wave is the code's and the
writer only puts words to it:

- **The steps**: STEPS of them up the harbour wall, a prize on each of PRIZE_STEPS (from the town's advertisers) and
  the star prize, a weekend away, for the spring tide.
- **A turn**: PADDLE, an easy question (right: up one; wrong: stay); SWIM, a hard one (right: up two; wrong: slip down
  one); or MAKE FAST, no question: bank the best prize at or below the climber's step, kept whatever happens. A prize
  stood at or above but not made fast is in hand.
- **The tide**: after each round (TURNS each) it rises one to three steps, the rolls bigger as it comes in
  (TIDE_ROLLS). Reaching a climber, it washes them off: what's in hand is lost, what's banked kept, and they start
  again one step above the water, sit out their next turn, and only a prize they climb onto again from there is
  theirs to take (washed off, the water lifts them: without that, it handed out prizes).
- **The spring tide**: after ROUNDS rounds the higher climber answers SPRING_QUESTIONS swim questions for the star
  prize, and needs SPRING_NEEDED right.
- **The climbers**: each has a chance of answering a paddle question right (`ability`; a swim's is SWIM_ODDS of it)
  and a temperament: cautious, making fast as soon as there's room above the water and paddling unless the tide is
  close; bold, swimming every time and making fast only with a good prize in hand and the water close.

The booking (which residents, the questions, the prizes) and the programme come later in the build (TODO.md).
"""
from __future__ import annotations

import random
from dataclasses import dataclass

STEPS = 12
PRIZE_STEPS = (3, 6, 9)
ROUNDS = 4
TURNS = 2                            # each climber's goes in a round, in turn
START = 1                            # the bottom step, just above the water
# Low water two steps below the bottom one: from 0, someone was washed off in 96% of 3,000 played games and twice in
# 87%; from -2, in 76% and 55%, and the prizes taken home spread (nothing 26%, steps 3, 6 and 9 19%, 43%, 11%).
TIDE_START = -2
TIDE_CAP = STEPS - 1                 # the top step is dry land: the tide never covers it
# The tide's roll after each round: the chances of one, two and three steps, bigger as it comes in.
TIDE_ROLLS = ((0.6, 0.3, 0.1), (0.45, 0.35, 0.2), (0.3, 0.4, 0.3), (0.2, 0.4, 0.4))
SWIM_ODDS = 0.65                     # a swim question's chance, as a share of the climber's paddle chance
SPRING_QUESTIONS, SPRING_NEEDED = 3, 2
PADDLE, SWIM, FAST, OUT = "paddle", "swim", "fast", "out"


def prize_at(step: int) -> int:
    """The best prize step at or below `step`; 0 for none."""
    return max((p for p in PRIZE_STEPS if p <= step), default=0)


@dataclass
class Climber:
    name: str
    ability: float                   # the chance of a right paddle answer
    bold: bool
    step: int = START
    banked: int = 0                  # the prize step made fast (0: none)
    base: int = 0                    # the step they last started from: only prizes above it are theirs to take
    out: bool = False                # washed off: they sit out their next turn, wringing out

    @property
    def in_hand(self) -> int:
        """The best prize they have climbed onto since they last started, stand at or above, and haven't made fast:
        lost if the tide comes first. Not one the water lifted them past (the first engine's flaw, 2026-11-19: washed
        off, a climber restarted above the prizes and had them in hand, and nobody went home with less than step 6)."""
        return max((p for p in PRIZE_STEPS if self.base < p <= self.step and p > self.banked), default=0)


def choose(c: Climber, tide: int) -> str:
    """The climber's choice for a turn, by temperament, from where they stand and where the water is."""
    room = c.step - tide                                   # steps above the water
    if c.step >= STEPS:                                    # dry land: nothing to climb, only to make fast
        return FAST if c.in_hand else PADDLE
    if c.bold:
        return FAST if c.in_hand >= PRIZE_STEPS[1] and room <= 2 else SWIM
    if c.in_hand and room >= 2:
        return FAST
    return SWIM if room <= 1 else PADDLE


def _turn(rng: random.Random, c: Climber, tide: int) -> dict:
    if c.out:                                              # washed off last round: this turn is spent wringing out
        c.out = False
        return {"who": c.name, "choice": OUT, "right": None, "from": c.step, "to": c.step, "banked": c.banked,
                "in_hand": c.in_hand}
    choice, before, right = choose(c, tide), c.step, None
    if choice == FAST:
        c.banked = max(c.banked, c.in_hand)
    else:
        right = rng.random() < (c.ability if choice == PADDLE else c.ability * SWIM_ODDS)
        if choice == PADDLE:
            c.step = min(STEPS, c.step + (1 if right else 0))
        else:
            c.step = min(STEPS, c.step + 2) if right else max(START, c.step - 1)
    return {"who": c.name, "choice": choice, "right": right, "from": before, "to": c.step, "banked": c.banked,
            "in_hand": c.in_hand}


def play(rng: random.Random, climbers: list[dict]) -> dict:
    """The whole game: every turn, every wave, the spring tide and what each climber takes home. `climbers` are two
    {name, ability, bold}; the first goes first in odd rounds, the second in even ones."""
    cs = [Climber(c["name"], c["ability"], c["bold"]) for c in climbers]
    tide, rounds = TIDE_START, []
    for r in range(ROUNDS):
        order = cs if r % 2 == 0 else cs[::-1]
        turns = [_turn(rng, c, tide) for _ in range(TURNS) for c in order]
        before = tide
        roll = rng.choices((1, 2, 3), TIDE_ROLLS[r])[0]
        tide = min(TIDE_CAP, tide + roll)
        washed = []
        for c in cs:
            if c.step <= tide:
                washed.append({"who": c.name, "lost": c.in_hand, "kept": c.banked, "from": c.step, "to": tide + 1})
                c.step = c.base = tide + 1
                c.out = True
        rounds.append({"turns": turns, "tide_from": before, "roll": roll, "tide": tide, "washed": washed,
                       "after": [{"who": c.name, "step": c.step, "banked": c.banked, "in_hand": c.in_hand}
                                 for c in cs]})
    # The spring tide: the higher climber; level, the one with the better prize made fast; then the first.
    top = max(cs, key=lambda c: (c.step, c.banked, -cs.index(c)))
    answers = [rng.random() < top.ability * SWIM_ODDS for _ in range(SPRING_QUESTIONS)]
    star = sum(answers) >= SPRING_NEEDED
    results = [{"who": c.name, "prize": max(c.banked, c.in_hand), "star": c is top and star, "step": c.step}
               for c in cs]
    return {"climbers": [{"name": c["name"], "ability": c["ability"], "bold": c["bold"]} for c in climbers],
            "rounds": rounds,
            "spring": {"who": top.name, "answers": answers, "won": star}, "tide": tide, "results": results}
