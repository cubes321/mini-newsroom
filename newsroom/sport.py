"""Port Wexley's football, worked out rather than written by the model, like the tides.

Tidewater Town FC ("the Tides") play at Tidewater Stadium in the Greymouth & District
League: fourteen clubs, home and away, 26 rounds on Saturday afternoons from early August,
with one Saturday in four left for the cup. The fixtures come from a fixed round-robin and
every score from a seeded draw on the clubs' strengths, so a result is the same in every
bulletin, on the sports desk and in Vincent's monologue, and the table adds up. A result is
known once the match is over on the broadcast clock (kick-off plus FULL_TIME_MIN).

Fictional, like the town: the clubs, the players and the league are invented.

    python -m newsroom.sport [YYYY-MM-DD HH:MM]
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

CLUB, NICK, GROUND = "Tidewater Town FC", "the Tides", "Tidewater Stadium"
LEAGUE = "Greymouth & District League"
MANAGER = "Gary Rundle"
# The squad: (name, position). The captain first. Forwards score most.
SQUAD = [("Liam Tregear", "DF"), ("Owen Pascoe", "GK"), ("Danny Okonjo", "DF"), ("Sam Whitlock", "DF"),
         ("Reece Mabbott", "DF"), ("Kai Penrose", "MF"), ("Jordan Treen", "MF"), ("Tom Varley", "MF"),
         ("Callum Price", "MF"), ("Ellis Kemp", "FW"), ("Nathan Shore", "FW"), ("Josh Pengelly", "FW")]
SCORE_WEIGHT = {"FW": 5, "MF": 2, "DF": 1, "GK": 0}
# The league, with a strength for each club (1.0 is average). The Tides first.
CLUBS: list[tuple[str, float]] = [
    (CLUB, 1.08), ("Saltby Rovers", 1.0), ("Greymouth Athletic", 1.22), ("Kessick Bay", 0.86),
    ("Carrow Point", 0.95), ("Lowmoor Town", 1.12), ("Trevane Wanderers", 0.9), ("Fennick Vale", 0.8),
    ("St Aldric's", 1.04), ("Pellow Harbour", 0.92), ("Morwen United", 1.15), ("Brackwater", 0.84),
    ("Stannock Town", 0.98), ("Polgrey Rangers", 1.0),
]
OTHER_SPORT = ("Wexley Gulls FC (the Sunday-league side, always short of players), Wexley Bowls Club "
               "(indoors for the winter league), Wexley Rowing Club (gig rowing in the estuary), "
               "Tidewater Swimming Club (the sea swimmers, all year round)")
KICKOFF = (15, 0)
FULL_TIME_MIN = 115                      # kick-off to the final whistle, half time and stoppages included
CUP_EVERY = 4                            # one Saturday in four has no league round
SEASON_OPENS = (8, 1)                    # the season starts on the first Saturday on or after 1 August


@dataclass(frozen=True)
class Fixture:
    round: int
    kickoff: datetime
    home: str
    away: str


@dataclass(frozen=True)
class Result:
    fixture: Fixture
    home_goals: int
    away_goals: int
    scorers: tuple[str, ...]             # the Tides' scorers, in order (theirs only; others aren't named)


def _first_saturday(y: int) -> date:
    d = date(y, *SEASON_OPENS)
    return d + timedelta(days=(5 - d.weekday()) % 7)


def season_start(day: date) -> date:
    """The opening Saturday of the season `day` falls in (or the one just finished)."""
    start = _first_saturday(day.year)
    return start if day >= start else _first_saturday(day.year - 1)


def _rounds() -> list[list[tuple[str, str]]]:
    """A double round-robin by the circle method: each club at home to every other once."""
    names = [c for c, _ in CLUBS]
    n = len(names)
    first = []
    for r in range(n - 1):
        pairs = [(names[i], names[n - 1 - i]) for i in range(n // 2)]
        first.append([(a, b) if (r + i) % 2 == 0 else (b, a) for i, (a, b) in enumerate(pairs)])
        names = [names[0], names[-1]] + names[1:-1]
    return first + [[(b, a) for a, b in rnd] for rnd in first]


def fixtures(day: date) -> list[Fixture]:
    """Every league match of the season `day` falls in."""
    start = season_start(day)
    saturdays = (start + timedelta(weeks=k) for k in range(200))
    league_days = [d for k, d in enumerate(saturdays) if k % CUP_EVERY != CUP_EVERY - 1]
    out = []
    for r, (d, rnd) in enumerate(zip(league_days, _rounds())):
        ko = datetime.combine(d, datetime.min.time()).replace(hour=KICKOFF[0], minute=KICKOFF[1])
        out += [Fixture(r + 1, ko, h, a) for h, a in rnd]
    return out


def _poisson(rng: random.Random, lam: float) -> int:
    k, p, limit = 0, 1.0, math.exp(-lam)
    while True:
        p *= rng.random()
        if p <= limit:
            return k
        k += 1


def result(fx: Fixture) -> Result:
    """The match's score, the same every time it is asked for."""
    strength = dict(CLUBS)
    rng = random.Random(f"{fx.kickoff:%Y-%m-%d}|{fx.home}|{fx.away}")
    sh, sa = strength[fx.home], strength[fx.away]
    hg, ag = _poisson(rng, 1.25 * 1.12 * sh / sa), _poisson(rng, 1.25 * sa / sh)
    ours = hg if fx.home == CLUB else ag if fx.away == CLUB else 0
    names, weights = zip(*[(n, SCORE_WEIGHT[pos]) for n, pos in SQUAD])
    scorers = tuple(rng.choices(names, weights)[0] for _ in range(ours))
    return Result(fx, hg, ag, scorers)


def played(now: datetime) -> list[Result]:
    """This season's results so far: matches whose final whistle has gone."""
    done = now - timedelta(minutes=FULL_TIME_MIN)
    return [result(f) for f in fixtures(now.date()) if f.kickoff <= done]


def table(now: datetime) -> list[dict]:
    """The league table: points, then goal difference, then goals scored."""
    rows = {c: dict(club=c, p=0, w=0, d=0, l=0, gf=0, ga=0, pts=0) for c, _ in CLUBS}
    for r in played(now):
        for club, gf, ga in ((r.fixture.home, r.home_goals, r.away_goals), (r.fixture.away, r.away_goals, r.home_goals)):
            row = rows[club]
            row["p"] += 1; row["gf"] += gf; row["ga"] += ga
            key = "w" if gf > ga else "d" if gf == ga else "l"
            row[key] += 1
            row["pts"] += {"w": 3, "d": 1, "l": 0}[key]
    return sorted(rows.values(), key=lambda r: (-r["pts"], -(r["gf"] - r["ga"]), -r["gf"], r["club"]))


def _ours(fx: Fixture) -> bool:
    return CLUB in (fx.home, fx.away)


def _score_line(r: Result) -> str:
    """'the Tides beat Saltby Rovers 2-1 at home (Kemp, Shore)'."""
    fx = r.fixture
    home = fx.home == CLUB
    us, them = (r.home_goals, r.away_goals) if home else (r.away_goals, r.home_goals)
    other = fx.away if home else fx.home
    verb = "beat" if us > them else "drew with" if us == them else "lost to"
    where = "at home" if home else "away"
    goals = f" ({', '.join(n.split()[-1] for n in r.scorers)})" if r.scorers else ""
    if us < them:
        return f"{NICK} lost {them}-{us} to {other} {where}{goals}"
    return f"{NICK} {verb} {other} {us}-{them} {where}{goals}"


def _ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _when(fx: Fixture) -> str:
    return f"{fx.kickoff:%A %d %B, %H:%M}"


def summary(now: datetime) -> str:
    """One line for every writer's briefing: the Tides' last result, the next game, the position."""
    ours = [f for f in fixtures(now.date()) if _ours(f)]
    done = [result(f) for f in ours if f.kickoff <= now - timedelta(minutes=FULL_TIME_MIN)]
    live = [f for f in ours if f.kickoff <= now < f.kickoff + timedelta(minutes=FULL_TIME_MIN)]
    nxt = next((f for f in ours if f.kickoff > now), None)
    parts = []
    if done:
        parts.append(f"on {done[-1].fixture.kickoff:%A %d %B} {_score_line(done[-1])}")
    if live:
        f = live[0]
        parts.append(f"they are playing {f.away if f.home == CLUB else f.home} right now (kicked off at {f.kickoff:%H:%M})")
    elif nxt:
        parts.append(f"next: {'at home to' if nxt.home == CLUB else 'away at'} "
                     f"{nxt.away if nxt.home == CLUB else nxt.home}, {_when(nxt)}")
    else:
        parts.append("the season is over")
    pos = next(i for i, row in enumerate(table(now), 1) if row["club"] == CLUB)
    parts.append(f"{_ordinal(pos)} in the {LEAGUE}" if done else f"the {LEAGUE} season starts soon")
    return f"{CLUB} ({NICK}): " + "; ".join(parts) + "."


def for_prompt(now: datetime) -> str:
    """Everything the sports desk may use, in words: results, fixtures, the table, the squad."""
    lines = [f"SPORT FACTS (use these exact scores, dates and names; never invent a result or a fixture):",
             summary(now)]
    ours = [r for r in played(now) if _ours(r.fixture)]
    if ours:
        form = "".join("W" if (r.home_goals > r.away_goals) == (r.fixture.home == CLUB) and r.home_goals != r.away_goals
                       else "D" if r.home_goals == r.away_goals else "L" for r in ours[-5:])
        lines.append(f"The Tides' recent results, oldest first (form {form}): "
                     + "; ".join(f"{r.fixture.kickoff:%d %b} {_score_line(r)}" for r in ours[-5:]) + ".")
        last_round = [r for r in played(now) if r.fixture.round == ours[-1].fixture.round and not _ours(r.fixture)]
        if last_round:
            lines.append("The rest of that round: " + "; ".join(
                f"{r.fixture.home} {r.home_goals}-{r.away_goals} {r.fixture.away}" for r in last_round) + ".")
    rows = table(now)
    if any(r["p"] for r in rows):
        top = "; ".join(f"{i}. {r['club']} {r['pts']} pts (P{r['p']})" for i, r in enumerate(rows, 1) if i <= 4)
        pos, us = next((i, r) for i, r in enumerate(rows, 1) if r["club"] == CLUB)
        lines.append(f"{LEAGUE} table: {top}. The Tides are {_ordinal(pos)}: played {us['p']}, won {us['w']}, "
                     f"drawn {us['d']}, lost {us['l']}, scored {us['gf']}, conceded {us['ga']}, {us['pts']} points.")
    upcoming = [f for f in fixtures(now.date()) if _ours(f) and f.kickoff > now][:2]
    if upcoming:
        lines.append("Coming up: " + "; ".join(
            f"{_when(f)}, {'at home to' if f.home == CLUB else 'away at'} {f.away if f.home == CLUB else f.home}"
            for f in upcoming) + ".")
    lines.append(f"The club: manager {MANAGER}; captain {SQUAD[0][0]}; in the squad "
                 + ", ".join(f"{n} ({pos})" for n, pos in SQUAD[1:]) + f". Home ground {GROUND}.")
    lines.append(f"Other local sport (no fixed results; small-town scale): {OTHER_SPORT}.")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    at = datetime.strptime(" ".join(sys.argv[1:3]), "%Y-%m-%d %H:%M") if len(sys.argv) > 2 else datetime.now()
    for f in fixtures(at.date()):
        if _ours(f):
            r = result(f)
            print(f"R{f.round:>2} {f.kickoff:%a %d %b %H:%M}  {f.home} {r.home_goals}-{r.away_goals} {f.away}"
                  + (f"  ({', '.join(r.scorers)})" if r.scorers else ""))
    print()
    print(for_prompt(at))
