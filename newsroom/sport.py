"""Port Wexley's football, worked out rather than written by the model, like the tides.

Tidewater Town FC ("the Tides") play at Tidewater Stadium in the Greymouth & District
League: fourteen clubs, home and away, 26 rounds on Saturday afternoons from early August,
with one Saturday in four left for the cup. The fixtures come from a fixed round-robin and
every score from a seeded draw on the clubs' strengths, so a result is the same in every
bulletin, on the sports desk and in Vincent's monologue, and the table adds up. A result is
known once the match is over on the broadcast clock (kick-off plus FULL_TIME_MIN).

The rugby (rugby.py) and the pub darts league (darts.py) are worked out the same way; briefing()
and for_prompt() here gather all three for the writers.

Fictional, like the town: the clubs, the players and the league are invented.

    python -m newsroom.sport [YYYY-MM-DD HH:MM]
"""
from __future__ import annotations

import math
import random
import re
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


def first_weekday(y: int, opens: tuple[int, int], weekday: int) -> date:
    """The first `weekday` (Monday 0) on or after the month and day `opens` in year `y`."""
    d = date(y, *opens)
    return d + timedelta(days=(weekday - d.weekday()) % 7)


def season_start(day: date, opens: tuple[int, int] = SEASON_OPENS, weekday: int = 5) -> date:
    """The opening day of the season `day` falls in (or the one just finished)."""
    start = first_weekday(day.year, opens, weekday)
    return start if day >= start else first_weekday(day.year - 1, opens, weekday)


def round_robin(names: list[str]) -> list[list[tuple[str, str]]]:
    """A double round-robin by the circle method: each club at home to every other once.
    The rugby and the darts (rugby.py, darts.py) draw their fixtures the same way."""
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
    for r, (d, rnd) in enumerate(zip(league_days, round_robin([c for c, _ in CLUBS]))):
        ko = datetime.combine(d, datetime.min.time()).replace(hour=KICKOFF[0], minute=KICKOFF[1])
        out += [Fixture(r + 1, ko, h, a) for h, a in rnd]
    return out


def poisson(rng: random.Random, lam: float) -> int:
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
    hg, ag = poisson(rng, 1.25 * 1.12 * sh / sa), poisson(rng, 1.25 * sa / sh)
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
    # Who scored how many, and whether the other side did: from "(Shore, Kemp, Price)" Full Time gave Shore and
    # Price two goals each and the keeper "a clean sheet" in a 3-1 (2026-11-21).
    counts = {n.split()[-1]: r.scorers.count(n) for n in r.scorers}
    goals = (" (goals: " + ", ".join(f"{n} {k}" if k > 1 else n for n, k in counts.items())
             + (", one each" if len(counts) > 1 and all(k == 1 for k in counts.values()) else "")
             + ("; a clean sheet" if them == 0 else "") + ")") if r.scorers else ""
    if us < them:
        return f"{NICK} lost {them}-{us} to {other} {where}{goals}"
    return f"{NICK} {verb} {other} {us}-{them} {where}{goals}"


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _when(fx: Fixture) -> str:
    """"Saturday 28 November, three o'clock (15:00)": given "15:00" alone, the sport said "kick-off fifteen
    hundred" eleven times on 2026-11-21."""
    from .schedule import said_clock        # schedule imports this module (through calendar)

    return f"{fx.kickoff:%A %d %B}, {said_clock(fx.kickoff.hour, fx.kickoff.minute)} ({fx.kickoff:%H:%M})"


def ago(day: date, now: datetime) -> str:
    """How long ago a day was, in words: the Wreckers' win of Saturday 14 November was "a fortnight ago" on the
    21st (Full Time, 2026-11-21)."""
    n = (now.date() - day).days
    return {0: "today", 1: "yesterday", 7: "a week ago", 14: "a fortnight ago"}.get(n, f"{n} days ago")


def summary(now: datetime) -> str:
    """One line for every writer's briefing: the Tides' last result, the next game, the position."""
    ours = [f for f in fixtures(now.date()) if _ours(f)]
    done = [result(f) for f in ours if f.kickoff <= now - timedelta(minutes=FULL_TIME_MIN)]
    live = [f for f in ours if f.kickoff <= now < f.kickoff + timedelta(minutes=FULL_TIME_MIN)]
    nxt = next((f for f in ours if f.kickoff > now), None)
    parts = []
    if done:
        k = done[-1].fixture.kickoff
        parts.append(f"on {k:%A %d %B} ({ago(k.date(), now)}) {_score_line(done[-1])}")
    if live:
        f = live[0]
        parts.append(f"they are playing {f.away if f.home == CLUB else f.home} right now (kicked off at {f.kickoff:%H:%M})")
    elif nxt:
        parts.append(f"next: {'at home to' if nxt.home == CLUB else 'away at'} "
                     f"{nxt.away if nxt.home == CLUB else nxt.home}, {_when(nxt)}")
    else:
        parts.append("the season is over")
    pos = next(i for i, row in enumerate(table(now), 1) if row["club"] == CLUB)
    parts.append(f"{ordinal(pos)} in the {LEAGUE}" if done else f"the {LEAGUE} season starts soon")
    return f"{CLUB} ({NICK}): " + "; ".join(parts) + "."


_RESULT = re.compile(
    r"\b(?:(?:nil|one|two|three|four|five|six|seven|\d{1,2})[- ](?:nil|one|two|three|four|five|six|seven|all|apiece|\d{1,2})\b"
    r"|draws?\b|drew\b|drawn\b|beat(?:s|en)?\b(?= (?:the )?(?-i:[A-Z]))|wins?\b|won\b(?!')|loses?\b|lost\b|defeat(?:s|ed)?\b"
    r"|victory\b|leads? at (?:the break|half[- ]time)|a goal up\b|levels?\b|levelled\b|equalis\w+|winner\b"
    r"|scores?\b|scored\b|hat[- ]trick|clean sheet|full[- ]time score|final score|(?:match|game|side|team) go(?:es)? down\b|go(?:es)? down (?:\d|nil|one|two|three|four|five|by)"
    r"|ends? (?:level|all square|one|two|nil|\d))", re.I)


def sides() -> tuple[str, ...]:
    """Every side whose results are worked out here, as a story would name it: the clubs of both leagues, the Tides
    and the Wreckers by their nicknames, the darts league's pubs."""
    from . import darts, rugby              # they import this module's helpers

    names = [c for c, _ in CLUBS] + [c for c, _ in rugby.CLUBS] + [p for p, *_ in darts.PUBS]
    names += [NICK, rugby.NICK, "Tidewater Town", "Saltby Rovers"]
    return tuple(dict.fromkeys(n.removeprefix("the ") for n in names))


def without_result(text: str, known: str = "") -> str:
    """A story's planned NEXT with any result of a game taken off: the text up to the clause that gives one, or the
    whole of it when it names none of the sides or gives no result.

    The scores are worked out in code, the same for every writer. On 2026-11-21 the story desk planned the Tides'
    match before it was played ("Saltby lead at the break, the Tides level from a corner, and it ends one apiece"),
    the sports desk made it 3-1, and Coastwide and The Last Ferry gave the draw from the story. Over the town's
    backups of that fortnight the desk had done it in 12 of 363 planned NEXTs: "the Tides draw 1-1 at Greymouth
    Athletic", "Liam Tregear's side take it 2-1", "the match goes down five-three"."""
    if not text or not any(re.search(rf"\b{re.escape(n)}\b", text) for n in sides()):
        return text
    # A result the story already has (`known`: its title and where it stands) is not one being made up: "the 28-19
    # card goes up beside the board" on "The Crown at Saltby Take the Ferryman 28-19".
    m = next((m for m in _RESULT.finditer(text) if m.group(0).lower() not in known.lower()), None)
    if not m:
        return text
    cut = max(text.rfind(mark, 0, m.start()) for mark in (";", " \u2014 ", ": ", ". "))
    if cut < 0:
        cut = text.rfind(", ", 0, m.start())
    kept = text[:cut].rstrip(" ,;:\u2014-") if cut > 0 else ""
    return kept + "." if kept else ""


def briefing(now: datetime) -> str:
    """The sport line in every writer's briefing: the Tides first, then the rugby and the darts."""
    from . import darts, rugby              # they import this module's helpers

    return " ".join((summary(now), rugby.summary(now), darts.summary(now)))


def for_prompt(now: datetime) -> str:
    """Everything the sports desk may use, in words: the football's results, fixtures, table and
    squad, then the rugby's and the darts'."""
    from . import darts, rugby

    lines =[f"SPORT FACTS (use these exact scores, dates and names; never invent a result or a fixture):",
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
        lines.append(f"{LEAGUE} table: {top}. The Tides are {ordinal(pos)}: played {us['p']}, won {us['w']}, "
                     f"drawn {us['d']}, lost {us['l']}, scored {us['gf']}, conceded {us['ga']}, {us['pts']} points.")
    upcoming = [f for f in fixtures(now.date()) if _ours(f) and f.kickoff > now][:2]
    if upcoming:
        lines.append("Coming up: " + "; ".join(
            f"{_when(f)}, {'at home to' if f.home == CLUB else 'away at'} {f.away if f.home == CLUB else f.home}"
            for f in upcoming) + ".")
    lines.append(f"The club: manager {MANAGER}; captain {SQUAD[0][0]}; in the squad "
                 + ", ".join(f"{n} ({pos})" for n, pos in SQUAD[1:]) + f". Home ground {GROUND}.")
    lines.append(f"Other local sport (no fixed results; small-town scale): {OTHER_SPORT}.")
    return "\n\n".join(("\n".join(lines), rugby.for_prompt(now), darts.for_prompt(now)))


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
