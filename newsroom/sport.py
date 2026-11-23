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
import sys
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


def _score_line(r: Result, said: bool = True) -> str:
    """'the Tides beat Saltby Rovers 2-1 at home (goals: Kemp, Shore, one each)'; `said` False is Seventext's
    '(Kemp, Shore)'."""
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
    if not said:
        goals = f" ({', '.join(n.split()[-1] for n in r.scorers)})" if r.scorers else ""
    if us < them:
        return f"{NICK} lost {them}-{us} to {other} {where}{goals}"
    return f"{NICK} {verb} {other} {us}-{them} {where}{goals}"


def ordinal(n: int) -> str:
    return f"{n}{'th' if 10 <= n % 100 <= 20 else {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th')}"


def _when(fx: Fixture, said: bool = True) -> str:
    """"Saturday 28 November, three o'clock (15:00)": given "15:00" alone, the sport said "kick-off fifteen
    hundred" eleven times on 2026-11-21."""
    from .schedule import said_clock        # schedule imports this module (through calendar)

    if not said:
        return f"{fx.kickoff:%A %d %B, %H:%M}"
    return f"{fx.kickoff:%A %d %B}, {said_clock(fx.kickoff.hour, fx.kickoff.minute)} ({fx.kickoff:%H:%M})"


def ago(day: date, now: datetime) -> str:
    """How long ago a day was, in words: the Wreckers' win of Saturday 14 November was "a fortnight ago" on the
    21st (Full Time, 2026-11-21)."""
    n = (now.date() - day).days
    return {0: "today", 1: "yesterday", 7: "a week ago", 14: "a fortnight ago"}.get(n, f"{n} days ago")


def summary(now: datetime, said: bool = True) -> str:
    """One line for every writer's briefing: the Tides' last result, the next game, the position. `said` False is
    for the screen (Seventext) and the stand-in script: figures, no "(today)", as before 2026-11-22."""
    ours = [f for f in fixtures(now.date()) if _ours(f)]
    done = [result(f) for f in ours if f.kickoff <= now - timedelta(minutes=FULL_TIME_MIN)]
    live = [f for f in ours if f.kickoff <= now < f.kickoff + timedelta(minutes=FULL_TIME_MIN)]
    nxt = next((f for f in ours if f.kickoff > now), None)
    parts = []
    if done:
        k = done[-1].fixture.kickoff
        parts.append(f"on {k:%A %d %B}" + (f" ({ago(k.date(), now)})" if said else "") + f" {_score_line(done[-1], said)}")
    if live:
        f = live[0]
        parts.append(f"they are playing {f.away if f.home == CLUB else f.home} right now (kicked off at {f.kickoff:%H:%M})")
    elif nxt:
        parts.append(f"next: {'at home to' if nxt.home == CLUB else 'away at'} "
                     f"{nxt.away if nxt.home == CLUB else nxt.home}, {_when(nxt, said)}")
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

    # The news had the Tides "on top of the league" in fourth and a points table of its own (2026-11-22).
    return " ".join((summary(now), rugby.summary(now), darts.summary(now),
                     "That is all the sport there is here: no other club's result, no points totals, and each side's "
                     "place exactly as given."))


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


# ------------------------------------------------------------------ slips: what a script says against the facts

_WORD_N = {w: i for i, w in enumerate("nil one two three four five six seven eight nine ten".split())} | {"zero": 0}
_N = r"(nil|zero|one|two|three|four|five|six|seven|eight|nine|ten|\d{1,2})"
_SCORE = re.compile(rf"\b{_N}(?:[- ]|\s+goals?\s+to\s+){_N}\b", re.I)
_PLACES = "first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth".split()
_PLACE = re.compile(r"\b(?:sit|sits|sitting|are|is|lie|lies|lying|in|now|still|climb to|up to|down to)\s+"
                    r"(" + "|".join(_PLACES) + r"|\d{1,2}(?:st|nd|rd|th))\b(?!\s+(?:half|minute|goal|try|game|match))",
                    re.I)
_TOP = re.compile(r"\btop of the (?:[\w&]+\s+){0,4}?(?:table|league)\b|\bleague leaders\b|\btop the (?:table|league)\b", re.I)
_AGO = ((re.compile(r"\b(?:this afternoon|today(?!'s)|this evening)\b", re.I), (0, 0), "today"),
        (re.compile(r"\byesterday\b", re.I), (1, 1), "yesterday"),
        (re.compile(r"\b(?:last week|a week ago|a week back)\b", re.I), (5, 9), "a week ago"),
        (re.compile(r"\b(?:a fortnight|two weeks)\b", re.I), (12, 16), "a fortnight ago"))
_WON = r"\b(?:beat|beats|win over|won|victory over|saw off|edged|thrashed)\b"
_LOST = r"\b(?:lost|lose|went down|defeat to|beaten by)\b"


def _n(s: str) -> int:
    return _WORD_N.get(s.lower(), None) if not s.isdigit() else int(s)


def _sentences(lines: list[str]) -> list[str]:
    return [s for t in lines for s in re.split(r"(?<=[.!?])\s+", t or "") if s.strip()]


def _alias(club: str, clubs: list[str]) -> str:
    """A club as people say it: "Polgrey" for Polgrey Rangers when no other club starts so."""
    if club == CLUB:                                 # "Tidewater Town", "the Tides"
        return r"(?:Tidewater Town(?: FC)?|Tides)"
    first = club.split()[0]
    return rf"(?:{re.escape(club)}|{re.escape(first)}(?!\s+(?:and|&)\s+District|\s+\w*(?:RFC|Athletic|Rovers|Rangers|Bay|Town)\b))" \
        if sum(c.split()[0] == first for c in clubs) == 1 and first not in ("St", "The") else re.escape(club)


def slips(lines: list[str], now: datetime) -> list[str]:
    """What a script says about the sport against the sports desk's facts: how long ago a result was, a club's place
    in its league, and another match's score or winner. On the 2026-11-22 night Full Time had Polgrey's "two-nil win
    over Greymouth Athletic" at 18:51 and "Polgrey Rangers lost two-nil to Greymouth Athletic" at 18:54; the
    Wreckers' win of eight days before was "a fortnight back" on three shows; the news had the Tides "on top of the
    league" in fourth. Each note says what is so, for the writer's second ask."""
    from . import rugby

    said = _sentences(lines)
    out: list[str] = []
    for mod, nick, short in ((sys.modules[__name__], NICK, "Tides"), (rugby, rugby.NICK, "Wreckers")):
        ours = [r for r in mod.played(now) if mod.CLUB in (r.fixture.home, r.fixture.away)]
        if ours:                                    # how long ago their last game was
            fx = ours[-1].fixture
            other = fx.away if fx.home == mod.CLUB else fx.home
            days = (now.date() - fx.kickoff.date()).days
            for s in said:
                at = re.search(rf"\b{re.escape(other)}\b", s)
                if at and (short in s or mod.CLUB in s or "beat" in s.lower() or "win" in s.lower()):
                    near = s[max(0, at.start() - 50):at.end() + 70]          # the result's own clause, not "Also today"
                    hits = [(rng, word) for rx, rng, word in _AGO if rx.search(near)]
                    if len(hits) == 1 and not hits[0][0][0] <= days <= hits[0][0][1]:
                        out.append(f"\"{s.strip()[:110]}\": the {short}' game with {other} was {ago(fx.kickoff.date(), now)} "
                                   f"({fx.kickoff:%A %d %B}), not {hits[0][1]}")
        pos = next((i for i, row in enumerate(mod.table(now), 1) if row["club"] == mod.CLUB), None)
        if pos and ours:                            # their place in the league
            for s in said:
                if short in s or mod.CLUB in s:
                    if _TOP.search(s) and pos != 1:
                        out.append(f"\"{s.strip()[:110]}\": the {short} are {_PLACES[pos - 1]} in the league, not top")
                    for m in _PLACE.finditer(s):
                        w = m.group(1).lower()
                        n = _PLACES.index(w) + 1 if w in _PLACES else int(re.sub(r"\D", "", w))
                        if n != pos and not re.search(r"\b(?:minute|half|place in the cup)\b", s[m.end():m.end() + 12]):
                            out.append(f"\"{s.strip()[:110]}\": the {short} are {_PLACES[pos - 1]} in the league, "
                                       f"not {w}")
    clubs = [c for c, _ in CLUBS]                   # another match's score or winner (the football)
    done = played(now)
    for s in said:
        if re.search(r"\b(?:Wreckers|rugby|RFC|Quarry Field|tries|try)\b", s, re.I):
            continue                                # the rugby's Saltby and Lowmoor aren't the football's
        if re.search(r"\b(?:next|travel|travels|head to|heads to|away to|away at|at home to|host|hosts|face|faces)\b",
                     s, re.I):
            continue                                # a fixture named beside a result: "beat Saltby, next away to Polgrey"
        names = [c for c in clubs if re.search(rf"\b{_alias(c, clubs)}\b", s)]
        if len(names) != 2 or not (_SCORE.search(s) or re.search(f"{_WON}|{_LOST}", s, re.I)):
            continue
        a, b = names
        r = next((x for x in reversed(done) if {x.fixture.home, x.fixture.away} == {a, b}), None)
        if r is None:
            continue
        goals = {r.fixture.home: r.home_goals, r.fixture.away: r.away_goals}
        winner = None if goals[a] == goals[b] else a if goals[a] > goals[b] else b
        pa, pb = _alias(a, clubs), _alias(b, clubs)
        claimed = (a if re.search(rf"{pa}[^.]*?{_WON}[^.]*?{pb}|{pb}[^.]*?{_LOST}[^.]*?{pa}", s) else
                   b if re.search(rf"{pb}[^.]*?{_WON}[^.]*?{pa}|{pa}[^.]*?{_LOST}[^.]*?{pb}", s) else None)
        score = _SCORE.search(s)
        nums = sorted((_n(score.group(1)), _n(score.group(2)))) if score else None
        real = f"{r.fixture.home} {r.home_goals}-{r.away_goals} {r.fixture.away} ({r.fixture.kickoff:%A %d %B})"
        if (claimed and claimed != winner) or (nums and None not in nums and nums != sorted(goals.values())):
            out.append(f"\"{s.strip()[:110]}\": the result was {real}")
    return list(dict.fromkeys(out))
