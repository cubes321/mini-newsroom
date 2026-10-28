"""The pub darts league, worked out like the football (sport.py): the lighter end of Full Time.

Ten pubs in the Wexley & District Darts League meet four times a season, one match a week:
each round's five matches split between Tuesday and Thursday nights at eight, from September,
with Christmas and New Year off. A match is nine games (six singles, three pairs), each won on
the pubs' strengths from a seeded draw; a pub scores a league point for every game it wins.
The night's 180s and the best checkout go to the pubs' named regulars.

Fictional, like the town: the pubs, the players and the league are invented (the Anchor and
Bell was already in town).

    python -m newsroom.darts [YYYY-MM-DD HH:MM]
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date, datetime, timedelta

from .sport import poisson, round_robin, season_start

LEAGUE = "Wexley & District Darts League"
# (pub, strength, its regulars: the captain first)
PUBS: list[tuple[str, float, tuple[str, str]]] = [
    ("the Anchor and Bell", 1.1, ("Shirley Vosper", "Dennis Rowe")),
    ("the Lugger", 1.0, ("Gav Polglase", "Tracy Hendy")),
    ("the Harbour Lights", 1.15, ("Kev Moyle", "Bev Carne")),
    ("the Ferryman", 0.95, ("Alan Treweek", "Sue Blewett")),
    ("the Pilchard", 0.9, ("Mick Jewell", "Lorraine Oates")),
    ("the Crown at Saltby", 1.05, ("Terry Bawden", "Jan Couch")),
    ("the Lantern", 0.85, ("Rob Kneebone", "Dawn Sleeman")),
    ("the Cannery Tap", 1.0, ("Craig Uren", "Mel Tamblyn")),
    ("the Wexley Legion", 0.92, ("Ray Prowse", "Pauline Hocking")),
    ("the Railway", 1.08, ("Darren Rodda", "Kath Bunt")),
]
GAMES = 9
NIGHTS = (1, 3)                          # Tuesday and Thursday
START = (20, 0)
DONE_MIN = 150                           # the last leg is thrown by half past ten
SEASON_OPENS = (9, 8)
MEETINGS = 2                             # times through the double round-robin: four meetings a season


@dataclass(frozen=True)
class Fixture:
    round: int
    start: datetime
    home: str
    away: str


@dataclass(frozen=True)
class Result:
    fixture: Fixture
    home_games: int
    away_games: int
    one_eighties: tuple[str, ...]        # who threw them
    checkout: tuple[str, int]            # the match's best checkout: who, and how many


def _christmas(d: date) -> bool:
    return (d.month == 12 and d.day >= 20) or (d.month == 1 and d.day <= 3)


def fixtures(day: date) -> list[Fixture]:
    """Every match of the season `day` falls in."""
    start = season_start(day, SEASON_OPENS, NIGHTS[0])
    weeks = [w for w in (start + timedelta(weeks=k) for k in range(80)) if not _christmas(w)]
    rounds = round_robin([p for p, _, _ in PUBS]) * MEETINGS
    out = []
    for r, (tue, rnd) in enumerate(zip(weeks, rounds)):
        for i, (h, a) in enumerate(rnd):          # alternate the nights so no pub always plays Thursday
            d = tue + timedelta(days=NIGHTS[(i + r) % 2] - NIGHTS[0])
            out.append(Fixture(r + 1, datetime.combine(d, datetime.min.time()).replace(hour=START[0], minute=START[1]), h, a))
    return sorted(out, key=lambda f: f.start)


def result(fx: Fixture) -> Result:
    """The match's score, the same every time it is asked for."""
    pubs = {p: (s, regs) for p, s, regs in PUBS}
    rng = random.Random(f"darts|{fx.start:%Y-%m-%d}|{fx.home}|{fx.away}")
    (sh, rh), (sa, ra) = pubs[fx.home], pubs[fx.away]
    p_home = sh * 1.06 / (sh * 1.06 + sa)
    hg = sum(rng.random() < p_home for _ in range(GAMES))
    regulars = rh + ra
    tons = tuple(rng.choice(regulars) for _ in range(poisson(rng, 0.9)))
    best = 60 + int(rng.random() ** 2.2 * 111)    # mostly 60 to 100; a 170 is a night to remember
    return Result(fx, hg, GAMES - hg, tons, (rng.choice(regulars), best))


def played(now: datetime) -> list[Result]:
    """This season's results so far: matches whose last leg has been thrown."""
    done = now - timedelta(minutes=DONE_MIN)
    return [result(f) for f in fixtures(now.date()) if f.start <= done]


def table(now: datetime) -> list[dict]:
    """The league table: points (a point a game), then matches won."""
    rows = {p: dict(pub=p, p=0, w=0, l=0, gf=0, ga=0, pts=0) for p, _, _ in PUBS}
    for r in played(now):
        for pub, us, them in ((r.fixture.home, r.home_games, r.away_games), (r.fixture.away, r.away_games, r.home_games)):
            row = rows[pub]
            row["p"] += 1; row["gf"] += us; row["ga"] += them; row["pts"] += us
            row["w" if us > them else "l"] += 1
    return sorted(rows.values(), key=lambda r: (-r["pts"], -r["w"], r["pub"]))


def _line(r: Result) -> str:
    """'the Anchor and Bell beat the Lugger 6-3 (180s: Shirley Vosper; best checkout 121, Kev Moyle)'."""
    fx = r.fixture
    win, lose, w, l = ((fx.home, fx.away, r.home_games, r.away_games) if r.home_games > r.away_games
                       else (fx.away, fx.home, r.away_games, r.home_games))
    where = "at home" if win == fx.home else "away"
    extra = [f"180s: {', '.join(r.one_eighties)}"] if r.one_eighties else []
    extra.append(f"best checkout {r.checkout[1]}, {r.checkout[0]}")
    return f"{win} beat {lose} {w}-{l} {where} ({'; '.join(extra)})"


def _last_night(now: datetime) -> list[Result]:
    done = played(now)
    return [r for r in done if r.fixture.start.date() == done[-1].fixture.start.date()] if done else []


def summary(now: datetime) -> str:
    """One line for every writer's briefing: the last match night, the leaders, the next night."""
    last = _last_night(now)
    nxt = next((f for f in fixtures(now.date()) if f.start > now - timedelta(minutes=DONE_MIN)), None)
    parts = []
    if last:
        best = max(last, key=lambda r: r.checkout[1])
        parts.append(f"on {last[0].fixture.start:%A} {_line(best).split(' (')[0]}, "
                     f"and the best checkout was {best.checkout[1]} by {best.checkout[0]}")
        parts.append(f"{table(now)[0]['pub']} top the table")
    if nxt:
        parts.append("they are playing tonight" if nxt.start.date() == now.date() else f"next match night {nxt.start:%A %d %B}")
    else:
        parts.append("the season is over")
    return f"{LEAGUE}: " + "; ".join(parts) + "."


def for_prompt(now: datetime) -> str:
    """Everything the sports desk may use about the darts, in words."""
    lines = ["DARTS FACTS (pub darts: keep it light; use these exact scores, names and checkouts, never invent one):",
             summary(now)]
    last = _last_night(now)
    if last:
        lines.append(f"{last[0].fixture.start:%A %d %B}'s matches: " + "; ".join(_line(r) for r in last) + ".")
    rows = table(now)
    if any(r["p"] for r in rows):
        lines.append(f"The table (a point for every game won, nine games a match): "
                     + "; ".join(f"{i}. {r['pub']} {r['pts']} (P{r['p']} W{r['w']})" for i, r in enumerate(rows, 1)) + ".")
    upcoming = [f for f in fixtures(now.date()) if f.start > now]
    if upcoming:
        night = upcoming[0].start.date()
        lines.append(f"Next, {upcoming[0].start:%A %d %B} at eight: " + "; ".join(
            f"{f.home} v {f.away}" for f in upcoming if f.start.date() == night) + ".")
    lines.append("The regulars (captain first): " + "; ".join(f"{p}: {a}, {b}" for p, _, (a, b) in PUBS) + ".")
    return "\n".join(lines)


if __name__ == "__main__":
    import sys

    at = datetime.strptime(" ".join(sys.argv[1:3]), "%Y-%m-%d %H:%M") if len(sys.argv) > 2 else datetime.now()
    for r in played(at)[-10:]:
        print(f"R{r.fixture.round:>2} {r.fixture.start:%a %d %b}  {_line(r)}")
    print()
    print(for_prompt(at))
