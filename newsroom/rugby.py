"""Port Wexley's rugby, worked out like the football (sport.py): the same score everywhere.

Port Wexley RFC ("the Wreckers") play at the Quarry Field in Coastal Counties One: twelve
clubs, home and away, 22 rounds on Saturday afternoons from September, with one Saturday in
four free. Each side's tries, conversions and penalties come from a seeded draw on the clubs'
strengths. League points: 4 for a win, 2 for a draw, a bonus point for four tries or more and
one for losing by seven or fewer.

Fictional, like the town: the clubs, the players and the league are invented.

    python -m newsroom.rugby [YYYY-MM-DD HH:MM]
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .sport import ordinal, poisson, round_robin, season_start

CLUB, NICK, GROUND = "Port Wexley RFC", "the Wreckers", "the Quarry Field"
LEAGUE = "Coastal Counties One"
COACH = "Ros Jago"
# The squad: (name, position). The captain first; the fly-half takes the kicks.
SQUAD = [("Jory Kitto", "number eight"), ("Sam Hosking", "hooker"), ("Ben Rowse", "prop"),
         ("Matt Chegwidden", "prop"), ("Tom Eddy", "lock"), ("Rhys Bolitho", "lock"),
         ("Kieran Nance", "flanker"), ("Alfie Laity", "scrum-half"), ("Ollie Tonkin", "fly-half"),
         ("Dom Penhaligon", "centre"), ("Marcus Opie", "centre"), ("Leon Ashby", "wing"),
         ("Tyler Grose", "wing"), ("Harry Mitchell", "full-back")]
KICKER = "Ollie Tonkin"
TRY_WEIGHT = {"wing": 5, "full-back": 4, "centre": 4, "number eight": 3, "scrum-half": 2,
              "fly-half": 2, "flanker": 2, "hooker": 2, "prop": 1, "lock": 1}
CLUBS: list[tuple[str, float]] = [
    (CLUB, 1.05), ("Greymouth RFC", 1.2), ("Saltby", 0.9), ("Lowmoor", 1.1), ("Hendra Vale", 0.95),
    ("St Aldric's Old Boys", 1.0), ("Pellow", 0.85), ("Morwen", 1.15), ("Brackwater", 0.88),
    ("Kessick Bay", 0.97), ("Treloan", 1.02), ("Stannock", 0.92),
]
KICKOFF = (14, 30)
FULL_TIME_MIN = 105
FREE_EVERY = 4                           # one Saturday in four has no league round
SEASON_OPENS = (9, 1)


@dataclass(frozen=True)
class Fixture:
    round: int
    kickoff: datetime
    home: str
    away: str


@dataclass(frozen=True)
class Side:
    tries: int
    cons: int
    pens: int

    @property
    def points(self) -> int:
        return 5 * self.tries + 2 * self.cons + 3 * self.pens


@dataclass(frozen=True)
class Result:
    fixture: Fixture
    home: Side
    away: Side
    try_scorers: tuple[str, ...]         # the Wreckers' try scorers, in order (theirs only)


def fixtures(day: date) -> list[Fixture]:
    """Every league match of the season `day` falls in."""
    start = season_start(day, SEASON_OPENS, 5)
    saturdays = (start + timedelta(weeks=k) for k in range(200))
    league_days = [d for k, d in enumerate(saturdays) if k % FREE_EVERY != FREE_EVERY - 1]
    out = []
    for r, (d, rnd) in enumerate(zip(league_days, round_robin([c for c, _ in CLUBS]))):
        ko = datetime.combine(d, datetime.min.time()).replace(hour=KICKOFF[0], minute=KICKOFF[1])
        out += [Fixture(r + 1, ko, h, a) for h, a in rnd]
    return out


def _side(rng: random.Random, att: float, dfn: float, home: bool) -> Side:
    tries = poisson(rng, 2.4 * (1.12 if home else 1.0) * att / dfn)
    cons = sum(rng.random() < 0.65 for _ in range(tries))
    return Side(tries, cons, poisson(rng, 1.4 * (att / dfn) ** 0.5))


def result(fx: Fixture) -> Result:
    """The match's score, the same every time it is asked for."""
    strength = dict(CLUBS)
    rng = random.Random(f"rugby|{fx.kickoff:%Y-%m-%d}|{fx.home}|{fx.away}")
    sh, sa = strength[fx.home], strength[fx.away]
    home, away = _side(rng, sh, sa, True), _side(rng, sa, sh, False)
    ours = home if fx.home == CLUB else away if fx.away == CLUB else Side(0, 0, 0)
    names, weights = zip(*[(n, TRY_WEIGHT[pos]) for n, pos in SQUAD])
    return Result(fx, home, away, tuple(rng.choices(names, weights)[0] for _ in range(ours.tries)))


def played(now: datetime) -> list[Result]:
    """This season's results so far: matches whose final whistle has gone."""
    done = now - timedelta(minutes=FULL_TIME_MIN)
    return [result(f) for f in fixtures(now.date()) if f.kickoff <= done]


def league_points(us: Side, them: Side) -> int:
    pts = 4 if us.points > them.points else 2 if us.points == them.points else 0
    pts += us.tries >= 4                                         # the try bonus
    pts += 0 < them.points - us.points <= 7                      # the losing bonus
    return pts


def table(now: datetime) -> list[dict]:
    """The league table: points, then points difference, then tries."""
    rows = {c: dict(club=c, p=0, w=0, d=0, l=0, pf=0, pa=0, tries=0, bonus=0, pts=0) for c, _ in CLUBS}
    for r in played(now):
        for club, us, them in ((r.fixture.home, r.home, r.away), (r.fixture.away, r.away, r.home)):
            row = rows[club]
            row["p"] += 1; row["pf"] += us.points; row["pa"] += them.points; row["tries"] += us.tries
            row["w" if us.points > them.points else "d" if us.points == them.points else "l"] += 1
            pts = league_points(us, them)
            row["pts"] += pts
            row["bonus"] += pts - (4 if us.points > them.points else 2 if us.points == them.points else 0)
    return sorted(rows.values(), key=lambda r: (-r["pts"], -(r["pf"] - r["pa"]), -r["tries"], r["club"]))


def _ours(fx: Fixture) -> bool:
    return CLUB in (fx.home, fx.away)


def _score_line(r: Result) -> str:
    """'the Wreckers beat Saltby 24-17 at home (tries: Kitto, Grose; Tonkin 2 conversions, 2 penalties)'."""
    fx = r.fixture
    home = fx.home == CLUB
    us, them = (r.home, r.away) if home else (r.away, r.home)
    other = fx.away if home else fx.home
    where = "at home" if home else "away"
    kicks = [f"{n} {one if n == 1 else many}" for n, one, many in
             ((us.cons, "conversion", "conversions"), (us.pens, "penalty", "penalties")) if n]
    detail = []
    if r.try_scorers:
        counts = {n: r.try_scorers.count(n) for n in r.try_scorers}      # in order of their first try
        detail.append("tries: " + ", ".join(n.split()[-1] + (f" {k}" if k > 1 else "") for n, k in counts.items()))
    if kicks:
        detail.append(f"{KICKER.split()[-1]} " + " and ".join(kicks))
    goals = f" ({'; '.join(detail)})" if detail else ""
    if us.points < them.points:
        return f"{NICK} lost {them.points}-{us.points} to {other} {where}{goals}"
    verb = "beat" if us.points > them.points else "drew with"
    return f"{NICK} {verb} {other} {us.points}-{them.points} {where}{goals}"


def _when(fx: Fixture) -> str:
    return f"{fx.kickoff:%A %d %B, %H:%M}"


def summary(now: datetime) -> str:
    """One line for every writer's briefing: the Wreckers' last result, the next game, the position."""
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
    parts.append(f"{ordinal(pos)} in {LEAGUE}" if done else f"the {LEAGUE} season starts soon")
    return f"{CLUB} ({NICK}, rugby): " + "; ".join(parts) + "."


def for_prompt(now: datetime) -> str:
    """Everything the sports desk may use about the rugby, in words."""
    lines = ["RUGBY FACTS (use these exact scores, dates and names; never invent a result or a fixture):",
             summary(now)]
    ours = [r for r in played(now) if _ours(r.fixture)]
    if ours:
        lines.append("The Wreckers' recent results, oldest first: "
                     + "; ".join(f"{r.fixture.kickoff:%d %b} {_score_line(r)}" for r in ours[-4:]) + ".")
        last_round = [r for r in played(now) if r.fixture.round == ours[-1].fixture.round and not _ours(r.fixture)]
        if last_round:
            lines.append("The rest of that round: " + "; ".join(
                f"{r.fixture.home} {r.home.points}-{r.away.points} {r.fixture.away}" for r in last_round) + ".")
    rows = table(now)
    if any(r["p"] for r in rows):
        top = "; ".join(f"{i}. {r['club']} {r['pts']} pts (P{r['p']})" for i, r in enumerate(rows, 1) if i <= 4)
        pos, us = next((i, r) for i, r in enumerate(rows, 1) if r["club"] == CLUB)
        lines.append(f"{LEAGUE} table (4 for a win, 2 for a draw, a bonus point for four tries or for losing by "
                     f"seven or fewer): {top}. The Wreckers are {ordinal(pos)}: played {us['p']}, won {us['w']}, "
                     f"drawn {us['d']}, lost {us['l']}, points for {us['pf']}, against {us['pa']}, "
                     f"{us['bonus']} bonus points, {us['pts']} points.")
    upcoming = [f for f in fixtures(now.date()) if _ours(f) and f.kickoff > now][:2]
    if upcoming:
        lines.append("Coming up: " + "; ".join(
            f"{_when(f)}, {'at home to' if f.home == CLUB else 'away at'} {f.away if f.home == CLUB else f.home}"
            for f in upcoming) + ".")
    lines.append(f"The club: head coach {COACH}; captain {SQUAD[0][0]} ({SQUAD[0][1]}); in the squad "
                 + ", ".join(f"{n} ({pos})" for n, pos in SQUAD[1:]) + f". Home ground {GROUND}.")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    at = datetime.strptime(" ".join(sys.argv[1:3]), "%Y-%m-%d %H:%M") if len(sys.argv) > 2 else datetime.now()
    for f in fixtures(at.date()):
        if _ours(f):
            r = result(f)
            print(f"R{f.round:>2} {f.kickoff:%a %d %b %H:%M}  {f.home} {r.home.points}-{r.away.points} {f.away}"
                  + (f"  (tries {', '.join(r.try_scorers)})" if r.try_scorers else ""))
    print()
    print(for_prompt(at))
