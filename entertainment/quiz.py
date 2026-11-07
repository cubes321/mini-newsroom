"""Wexley Wits: the pub quiz, booked in the back office and scored here, like The Chamber's votes.

Two pubs from the darts league (newsroom/darts.py) send their two regulars, the captain first, and the
home pub is the venue. In idle time from BOOK_FROM (or when the first item needs it), one call sets four
rounds of six questions (a fifth, the darts round, is thrown in oche.py): general knowledge, Port Wexley from the briefing and the town's past, the
week's news from its headlines, and pot luck, each question rated 1 to 3, and a tiebreak with a number for an answer.
Then this module plays the quiz: which team each question goes to and who answers, whether they get it
(a seeded draw on the question's difficulty and the pub's darts strength, with a small home-town edge
on the local round), and, when they don't, whether the other team takes the bonus. Two points for a
question of your own, one for a bonus; a tie goes to the tiebreak, nearest guess wins.

The live writer is given all of it, item by item ("{r2}" in a brief is round two, every question, who
answers, right or wrong, and the score Clive reads out), so the script is written towards a result
already decided and the score always adds up. If the call fails, a stand-in quiz from a small bank
and the town's own facts takes the night, so the half hour always has questions.

Fictional, like the town: the pubs and their regulars are the darts league's.
"""
from __future__ import annotations

import logging
import random
import re
from datetime import date, datetime, timedelta

from pydantic import BaseModel, Field

from newsroom import darts, llm, schedule

from . import oche
from newsroom.config import CONFIG
from newsroom.models import SegmentType
from newsroom.world import World

log = logging.getLogger(__name__)

SHOW = "wits"
AIRS_AT = "20:00"
BOOK_FROM = "18:00"
PER_ROUND = 6                          # four made rounds of 85 s on 2026-11-07's scratch run: chat filled the rest
# The darts round (oche.py) has no questions: three darts each, thrown in code.
ROUNDS = (("general", "general knowledge"), ("local", "Port Wexley and the coast"), ("darts", "the darts round"),
          ("news", "the week's news"), ("potluck", "pot luck"))
OWN_POINTS, BONUS_POINTS = 2, 1
RIGHT = {1: 0.8, 2: 0.6, 3: 0.4}       # the chance a pub of strength 1.0 gets its own question, by difficulty
BONUS = 0.6                            # a bonus is harder: the first team's guess is out, the clock is on
LOCAL_EDGE = 1.1                       # regulars know their own town
REST_PAIRS = 5                         # a pairing doesn't come back within this many quizzes
HEADLINES = 30
TOKEN = re.compile(r"\{(open|r[1-5]|close|chat[12])\}")

# The darts regulars' genders, for their voices and looks (darts.PUBS names them, nothing more).
GENDER = {"Shirley Vosper": "f", "Dennis Rowe": "m", "Gav Polglase": "m", "Tracy Hendy": "f",
          "Kev Moyle": "m", "Bev Carne": "f", "Alan Treweek": "m", "Sue Blewett": "f", "Mick Jewell": "m",
          "Lorraine Oates": "f", "Terry Bawden": "m", "Jan Couch": "f", "Rob Kneebone": "m",
          "Dawn Sleeman": "f", "Craig Uren": "m", "Mel Tamblyn": "f", "Ray Prowse": "m",
          "Pauline Hocking": "f", "Darren Rodda": "m", "Kath Bunt": "f"}

# The booking's route: its own, or The Chamber's (config.toml is the user's; a booking is a booking).
TASK = "quiz" if "quiz" in CONFIG.llm.routes else "chamber"


class Question(BaseModel):
    question: str = Field(min_length=8, max_length=220, description="as Clive asks it aloud, short")
    answer: str = Field(min_length=1, max_length=80, description="the answer, a few words")
    difficulty: int = Field(ge=1, le=3, description="1 easy, 2 middling, 3 hard")


class Tiebreak(BaseModel):
    question: str = Field(min_length=8, max_length=220)
    answer: int = Field(description="a whole number")
    unit: str = Field(default="", max_length=30, description="metres, people, the year ... or empty")


class QuizBooking(BaseModel):
    """Tonight's questions for Wexley Wits (entertainment/quiz.py)."""
    general: list[Question] = Field(min_length=PER_ROUND, max_length=PER_ROUND + 2)
    local: list[Question] = Field(min_length=PER_ROUND, max_length=PER_ROUND + 2)
    news: list[Question] = Field(min_length=PER_ROUND, max_length=PER_ROUND + 2)
    potluck: list[Question] = Field(min_length=PER_ROUND, max_length=PER_ROUND + 2)
    tiebreak: Tiebreak


_SYSTEM = """\
You set the questions for WEXLEY WITS, a pub quiz on a small-town TV station's second channel, in the
FICTIONAL town in the briefing. Clive Ashdown asks them in a darts pub; two pub teams answer. Four
rounds of SIX questions each:
- general: general knowledge, the kind every pub quiz asks: well known and settled, with one short,
  unambiguous answer. Nothing about living people's private lives, no politics, nothing after 2020.
- local: Port Wexley and the coast, ONLY from facts in the BRIEFING and THE TOWN'S PAST below (its
  founding, landmarks, clubs, councillors, people, past stories). The answer must be stated there.
- news: this week's Port Wexley stories, ONLY from THIS WEEK'S HEADLINES. The answer must be in the
  headline as given.
- potluck: lighter general knowledge to finish: food and drink, animals, the sea and ships, sport,
  words and sayings. Same rules as general, none the same as it.
Rate each 1 (easy), 2 or 3 (hard), and mix them in every round. Then a TIEBREAK: a question whose answer
is a whole number (a year, a height, a count), general or from the town's facts, with its unit.
Questions as Clive would ask them aloud, short; no multiple choice; no question that gives away another's
answer; none from RECENT QUIZZES again. Never name where a fact came from ("according to the town's
past", "in the briefing"): Clive just asks. Return ONLY JSON.
"""


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def tonight(world: World) -> dict | None:
    return next((q for q in reversed(world.quizzes) if q.get("date") == world.last_date), None)


def should_commission(world: World, now: float | None = None) -> bool:
    now = now or schedule.now()
    return (tonight(world) is None and _at(BOOK_FROM, now) <= now < _at(AIRS_AT, now) + 30 * 60
            and schedule.show_at(_at(AIRS_AT, now)).id == SHOW)


def _title(pub: str) -> str:
    return pub[0].upper() + pub[1:]


def teams(world: World) -> list[dict]:
    """Tonight's two pubs, home first: a seeded draw on the date among pairings not met in the last
    REST_PAIRS quizzes. Each with its two regulars, captain first, and its darts strength."""
    met = {frozenset(t["pub"] for t in q["teams"]) for q in world.quizzes[-REST_PAIRS:] if q.get("date") != world.last_date}
    rng = random.Random(f"wits-{world.last_date}")
    pairs = [(a, b) for i, a in enumerate(darts.PUBS) for b in darts.PUBS[i + 1:]
             if frozenset((a[0], b[0])) not in met]
    a, b = rng.choice(pairs)
    if rng.random() < 0.5:
        a, b = b, a
    return [{"pub": pub, "name": _title(pub), "members": list(regulars), "strength": strength}
            for pub, strength, regulars in (a, b)]


def _cast(world: World, ts: list[dict]) -> None:
    """The regulars join the town's people (their voices and looks stay theirs)."""
    for t in ts:
        for i, name in enumerate(t["members"]):
            world.ensure_person(name, f"{'captain, ' if i == 0 else ''}{t['name']} quiz team", "resident",
                                gender=GENDER.get(name), accent="british")


def _week(world: World) -> list[str]:
    since = (date.fromisoformat(world.last_date) - timedelta(days=7)).isoformat()
    with world.lock:
        heads = [e["headline"] for e in world.archive if e["date"] >= since and e.get("headline")
                 and e["type"] in ("bulletin", "field_report", "breaking")]
    return list(dict.fromkeys(reversed(heads)))[:HEADLINES]


def _past(world: World) -> list[str]:
    done = [t for t in world.threads if t.phase in ("resolving", "closed", "faded")]
    return [f"{t.title}: {t.status}" for t in done[-15:]]


def commission(world: World) -> dict:
    """Book tonight's quiz: the questions (the model, or the stand-in if it fails), then play it here."""
    ts = teams(world)
    asked = [q["q"] for quiz in world.quizzes[-6:] for r in quiz["rounds"] for q in r.get("questions", [])]
    user = (f"BRIEFING\n{world.summary_for_editor()}\n\nTHIS WEEK'S HEADLINES:\n"
            + "\n".join(f"  - {h}" for h in _week(world))
            + "\n\nTHE TOWN'S PAST:\n" + ("\n".join(f"  - {p}" for p in _past(world)) or "  (nothing yet)")
            + f"\n\nTONIGHT: {ts[0]['name']} against {ts[1]['name']}, at {ts[0]['name']}."
            + ("\n\nRECENT QUIZZES (don't ask these again):\n" + "\n".join(f"  - {q}" for q in asked) if asked else ""))
    try:
        booking = llm.complete_json(TASK, QuizBooking, _SYSTEM, user)
    except llm.LLMError as e:
        log.warning("quiz: no questions (%s); the stand-in quiz takes tonight", e)
        booking = None
    return _record(world, ts, booking)


def _stand_in(world: World) -> QuizBooking:
    """A quiz with no call: a small bank for the general rounds, the town's own facts for the local one."""
    rng = random.Random(f"wits-bank-{world.last_date}")
    bank = rng.sample(BANK, 3 * PER_ROUND)
    local = [Question(question=f"In what year was {world.town} founded?", answer=str(world.founded), difficulty=2),
             Question(question=f"Who is the mayor of {world.town}?", answer="Helen Strand", difficulty=1),
             Question(question="What is Tidewater Town Football Club's nickname?", answer="the Tides", difficulty=1),
             Question(question=f"What do they call {world.town}'s rugby club?", answer="the Wreckers", difficulty=2),
             Question(question="Where do the Tides play their home games?", answer="Tidewater Stadium", difficulty=1),
             Question(question="What is the name of the town's darts league?", answer=darts.LEAGUE, difficulty=3)]
    return QuizBooking(general=bank[:PER_ROUND], local=local, news=bank[PER_ROUND:2 * PER_ROUND],
                       potluck=bank[2 * PER_ROUND:],
                       tiebreak=Tiebreak(question=f"To the nearest thousand, how many people live in {world.town}?",
                                         answer=round(world.population, -3), unit="people"))


def _play(booking: QuizBooking, ts: list[dict], seed: str) -> tuple[list[dict], list[int], dict | None]:
    """Every question's outcome and the scores after each round; the tiebreak if the scores are level."""
    rng = random.Random(seed)
    score = [0, 0]
    rounds = []
    for r, (kind, title) in enumerate(ROUNDS):
        if kind == "darts":
            throws, totals = oche.play(rng, ts)
            if totals[0] == totals[1]:
                score[0] += 1
                score[1] += 1
            else:
                score[0 if totals[0] > totals[1] else 1] += oche.POINTS
            rounds.append({"kind": kind, "title": title, "throws": throws, "totals": totals,
                           "scores_after": list(score)})
            continue
        qs = getattr(booking, kind)[:PER_ROUND]
        out = []
        for i, q in enumerate(qs):
            to = (i + r) % 2                   # the teams take turns, and the other one starts the next round
            other = 1 - to
            who = ts[to]["members"][(i // 2 + r) % 2]
            p = min(0.95, RIGHT[q.difficulty] * ts[to]["strength"] * (LOCAL_EDGE if kind == "local" else 1.0))
            right = rng.random() < p
            stolen = False
            if right:
                score[to] += OWN_POINTS
            else:
                p2 = min(0.9, RIGHT[q.difficulty] * BONUS * ts[other]["strength"])
                stolen = rng.random() < p2
                if stolen:
                    score[other] += BONUS_POINTS
            out.append({"q": q.question, "a": q.answer, "difficulty": q.difficulty, "to": to, "who": who,
                        "right": right, "stolen": stolen,
                        "bonus_who": ts[other]["members"][i % 2] if not right else None})
        rounds.append({"kind": kind, "title": title, "questions": out, "scores_after": list(score)})
    tie = None
    if score[0] == score[1]:
        a = booking.tiebreak.answer
        guesses = [round(a * (1 + rng.gauss(0, 0.2 / t["strength"]))) for t in ts]
        while abs(guesses[1] - a) == abs(guesses[0] - a):          # one of them has to be nearer
            guesses[1] += max(1, abs(a) // 50)
        winner = min((0, 1), key=lambda i: abs(guesses[i] - a))
        score[winner] += 1
        tie = {"q": booking.tiebreak.question, "a": a, "unit": booking.tiebreak.unit, "guesses": guesses,
               "winner": winner}
    return rounds, score, tie


def _record(world: World, ts: list[dict], booking: QuizBooking | None) -> dict:
    stand_in = booking is None
    booking = booking or _stand_in(world)
    rounds, final, tie = _play(booking, ts, f"wits-play-{world.last_date}-{ts[0]['pub']}-{ts[1]['pub']}")
    entry = {"date": world.last_date, "venue": ts[0]["name"], "teams": ts, "rounds": rounds, "tiebreak": tie,
             "final": final, "winner": 0 if final[0] > final[1] else 1, "stand_in": stand_in}
    _cast(world, ts)
    with world.lock:
        world.quizzes = [q for q in world.quizzes if q.get("date") != world.last_date] + [entry]
        world.quizzes = world.quizzes[-30:]
    log.info("quiz: tonight %s %d, %s %d%s%s", ts[0]["name"], final[0], ts[1]["name"], final[1],
             " (after the tiebreak)" if tie else "", " (stand-in)" if stand_in else "")
    return entry


def booked(world: World) -> dict:
    """Tonight's quiz; the first item to need it books it, if idle time hasn't."""
    return tonight(world) or commission(world)


def seats(world: World) -> list[str]:
    q = booked(world)
    return [*q["teams"][0]["members"], *q["teams"][1]["members"]]


def darts_round(world: World, brief: str) -> dict | None:
    """The darts round, if this item's brief is it."""
    m = re.search(r"\{r([1-5])\}", brief or "")
    q = tonight(world)
    r = q["rounds"][int(m.group(1)) - 1] if m and q else None
    return r if r and r["kind"] == "darts" else None


def check(seg, script, world: World) -> None:
    """A darts round's script must call every dart, in order, each in a line of Clive's (oche.calls_in)."""
    r = darts_round(world, seg.brief)
    if r and oche.calls_in(script.lines, r["throws"]) is None:
        raise llm.LLMError("the darts round's calls weren't all there, in order")


def after(seg, world: World) -> None:
    """Tie each dart to the line that calls it, for the window (oche.overlay)."""
    seg.work.pop("darts", None)
    r = darts_round(world, seg.brief)
    found = oche.calls_in(seg.lines, r["throws"]) if r else None
    if found:
        seg.work["darts"] = sorted(({**d, "line": i} for d, i in zip(r["throws"], found)), key=lambda d: d["line"])


def caption(world: World, name: str) -> str | None:
    q = tonight(world)
    for t in (q or {}).get("teams", []):
        if name in t["members"]:
            return f"{t['name']}{', captain' if name == t['members'][0] else ''}"
    return None


def _team(q: dict, i: int) -> str:
    t = q["teams"][i]
    return f"{t['name'].upper()} ({' and '.join(t['members'])}, {t['members'][0]} the captain)"


def _score(q: dict, s: list[int]) -> str:
    return f"{q['teams'][0]['name']} {s[0]}, {q['teams'][1]['name']} {s[1]}"


def _round(q: dict, n: int) -> str:
    r = q["rounds"][n]
    if r["kind"] == "darts":
        return oche.brief(q, r, n, _score(q, r["scores_after"]))
    rows = []
    for i, x in enumerate(r["questions"]):
        team, other = q["teams"][x["to"]]["name"], q["teams"][1 - x["to"]]["name"]
        row = f"{i + 1}. To {team.upper()}: \"{x['q']}\" (the answer: {x['a']}). {x['who']} answers: "
        if x["right"]:
            row += f"RIGHT, {OWN_POINTS} points."
        else:
            row += (f"WRONG (a wrong answer of their own that a pub regular might give); Clive offers it over to "
                    f"{other}, and {x['bonus_who']} answers: "
                    + (f"RIGHT, a bonus point." if x["stolen"] else
                       "WRONG too (another wrong answer); Clive gives the answer."))
        rows.append(row)
    return (f"ROUND {n + 1}: {r['title'].upper()}. Clive asks these in this order, word for word, and each goes "
            f"exactly as given:\n" + "\n".join(rows)
            + f"\nTHE SCORE AFTER ROUND {n + 1}, for Clive to read out: {_score(q, r['scores_after'])}.")


def brief_for(world: World, brief: str) -> str:
    """An item's brief with its part of the quiz in full: "{r2}" becomes round two, "{close}" the result."""
    q = booked(world)

    def part(m: re.Match) -> str:
        k = m.group(1)
        if k == "open":
            return (f"tonight's quiz, at {q['venue']}: {_team(q, 0)}, at home, against {_team(q, 1)}. "
                    f"{oche.words(len(ROUNDS)).capitalize()} rounds: {', '.join(t for _, t in ROUNDS)}; "
                    f"{OWN_POINTS} points for a question of your own, {BONUS_POINTS} for a bonus when it's offered "
                    f"over, and {oche.POINTS} for the pair with the higher total at the darts")
        if k.startswith("r"):
            return _round(q, int(k[1]) - 1)
        if k.startswith("chat"):
            return _team(q, int(k[4]) - 1)
        before = q["rounds"][-1]["scores_after"]
        out = f"after all {oche.words(len(ROUNDS))} rounds: {_score(q, before)}. "
        if q["tiebreak"]:
            t = q["tiebreak"]
            unit = f" {t['unit']}" if t["unit"] else ""
            out += (f"LEVEL, so THE TIEBREAK: Clive asks \"{t['q']}\"; nearest wins. "
                    f"{q['teams'][0]['members'][0]} says {t['guesses'][0]}{unit}, "
                    f"{q['teams'][1]['members'][0]} says {t['guesses'][1]}{unit}; the answer is {t['a']}{unit}, "
                    f"so {q['teams'][t['winner']]['name']} take it. ")
        w = q["teams"][q["winner"]]["name"]
        return out + f"THE FINAL SCORE, for Clive to read out: {_score(q, q['final'])}. {w} win."
    return TOKEN.sub(part, brief)


def for_prompt(world: World) -> str:
    """The quiz for every item: the teams, the venue, and what has happened so far tonight."""
    q = booked(world)
    with world.lock:
        aired = [e for e in world.archive if e["date"] == world.last_date and e.get("show") == SHOW
                 and e["type"] != SegmentType.ad_break.value]
    done = ("\nSO FAR TONIGHT (don't do these again):\n" + "\n".join(
        f"  - {e['type'].replace('_', ' ')}: {e['headline']}" for e in aired)) if aired else ""
    return (f"THE QUIZ: Wexley Wits, live from {q['venue']}, a darts pub in the "
            f"{darts.LEAGUE}. THE TEAMS (each contestant speaks as speaker \"guest\" with guest_name their exact "
            f"name): {_team(q, 0)}, at home; {_team(q, 1)}. The questions, who answers, right or wrong, and the "
            f"scores are fixed: keep to them exactly.{done}")


# The stand-in's general rounds: well-known, settled answers.
BANK = [
    Question(question="What is the capital city of Australia?", answer="Canberra", difficulty=2),
    Question(question="How many sides does a hexagon have?", answer="six", difficulty=1),
    Question(question="Which planet is known as the Red Planet?", answer="Mars", difficulty=1),
    Question(question="What is the chemical symbol for gold?", answer="Au", difficulty=2),
    Question(question="Who wrote Pride and Prejudice?", answer="Jane Austen", difficulty=2),
    Question(question="What is the largest ocean on Earth?", answer="the Pacific", difficulty=1),
    Question(question="How many players are there in a rugby union side?", answer="fifteen", difficulty=2),
    Question(question="In darts, what is the highest checkout with three darts?", answer="170", difficulty=2),
    Question(question="What is the longest river in the United Kingdom?", answer="the Severn", difficulty=2),
    Question(question="How many pints are there in a gallon?", answer="eight", difficulty=2),
    Question(question="Which element has the chemical symbol Fe?", answer="iron", difficulty=2),
    Question(question="In what year was the Battle of Hastings?", answer="1066", difficulty=1),
    Question(question="Who painted the Mona Lisa?", answer="Leonardo da Vinci", difficulty=1),
    Question(question="What is the smallest prime number?", answer="two", difficulty=2),
    Question(question="Which sea creature has three hearts?", answer="the octopus", difficulty=3),
    Question(question="How many minutes are there in a full day?", answer="1,440", difficulty=3),
    Question(question="What is a baby kangaroo called?", answer="a joey", difficulty=1),
    Question(question="How many legs does a spider have?", answer="eight", difficulty=1),
    Question(question="Which vegetable is the main ingredient of a traditional borscht?", answer="beetroot",
             difficulty=2),
    Question(question="What is the front of a ship called?", answer="the bow", difficulty=1),
    Question(question="In cricket, how many balls are there in an over?", answer="six", difficulty=1),
    Question(question="What is the largest mammal in the world?", answer="the blue whale", difficulty=1),
    Question(question="Which fruit is a prune when it is dried?", answer="the plum", difficulty=2),
    Question(question="What colour is the black box on an aeroplane?", answer="orange", difficulty=3),
    Question(question="How many strings does a standard violin have?", answer="four", difficulty=2),
    Question(question="Which gas do plants take in from the air?", answer="carbon dioxide", difficulty=2),
]
