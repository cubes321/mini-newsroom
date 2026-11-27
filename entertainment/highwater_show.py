"""High Water on air: the booking, the programme, its prompts and its checks. The game itself is highwater.py's.

Half an hour at 18:00 (docs/ENGINE.md, "High Water"; agreed with the user 2026-11-19). Des Kneebone ("hw_host") hosts;
two residents climb. The booking is made in code where it can be: the climbers (residents not on Channel 8 lately,
each with their own ability and temperament, the same every time they play), the four prize donors from the town's
advertisers, and the whole game, played from the night's seed. One back-office call then books the questions
(paddle, swim and the spring tide's, each with its answer and a wrong answer to give) and puts words to the prizes.

Each round is one interview item whose brief carries every turn as played ("{r2}"): who goes, what they choose, the
question and whether they get it, where they end up, then the tide and who it washes off. The writer puts Des's patter
round results already decided, and `check` holds every question to the script (asked once more, then the code's own
round stands in). The climbers sit beside Des all show (SEAT_HOOKS). If the items come in short, the order wraps to a
word with one climber or the other until the spring tide and the result close it.
"""
from __future__ import annotations

import logging
import random
import re
import zlib
from datetime import date, datetime

from pydantic import BaseModel, Field

from newsroom import llm, schedule
from newsroom.config import CONFIG
from newsroom.models import SegmentType as T
from newsroom.schedule import Item as I, Show
from newsroom.world import World
from newsroom.writers import _COMMON_RULES, _MIDDLE

from . import creative, highwater as hw

log = logging.getLogger(__name__)

SHOW = "highwater"
TITLE = "High Water"
AIRS_AT = "18:00"
BOOK_FROM = "16:30"
TASK = "highwater" if "highwater" in CONFIG.llm.routes else "chamber"
HOST, HOST_NAME = "hw_host", "Des Kneebone"
REST_DAYS = 60                          # a climber doesn't climb again within this
CHANNEL8_DAYS = 14                      # nor if they were on Channel 8 in another show this lately
SPARE = 2                               # questions asked for beyond what the played game needs, of each kind
MOST_ASKED = 30                         # a night needs at most 15 easy and 19 hard (5,000 played games, three turns)
TOKEN = re.compile(r"\{(open|meet[12]|r[1-4]|hm|chat[12]|sofar|spring|close)\}")

SET = "set_highwater"
SET_NAME = "the harbour steps"
SET_BLURB = "the harbour steps at dusk: twelve stone steps up the wall, the tide gauge beside them, the boats behind"
# Its own art (assets/backdrops/set_highwater.png, approved 2026-11-20), painted for its own dusk light, so it is
# registered as a studio set (never graded, no weather), as Marina Row's are. The gauge hangs on its plain low wall.
SET_COLOURS = ((120, 80, 140), (112, 96, 106))
MARKS = {"host": (70, 152, 2, 1), "panel_1": (186, 150, 2, -1), "panel_2": (250, 150, 2, -1)}
# The banner is on for this long at the start of each item, then clears, so the tide gauge's lower steps show under it
# (player.BANNER_S; 2026-11-20, the user's choice over moving the gauge up).
BANNER_S = 6.0

# Prize donors when the advert pool is empty (the tests; a new town): the town's shops of the stand-in adverts.
DONORS = ("Fowle & Sons Hardware", "the Harbour Bell Bakery", "Gull's Rest Fish & Chips", "the Saltby Arms")


# ------------------------------------------------------------------ the booking

class Q(BaseModel):
    question: str = Field(min_length=8, max_length=200, description="as Des asks it aloud, short")
    answer: str = Field(min_length=1, max_length=80, description="the answer, a few words")
    wrong: str = Field(min_length=1, max_length=80, description="a plausible wrong answer someone might give with "
                                                                "confidence, different from the answer")


class Prize(BaseModel):
    business: str = Field(min_length=3, max_length=60, description="the business giving it, exactly as given")
    prize: str = Field(min_length=3, max_length=80, description="what it is, as Des would say it: 'a fish supper for two'")


class HighWaterBooking(BaseModel):
    """Tonight's questions and prizes for High Water (entertainment/highwater_show.py)."""
    # As many as the night's played game needs, asked for by number; a short list is topped up from the stand-in's.
    paddle: list[Q] = Field(min_length=1, max_length=MOST_ASKED)
    swim: list[Q] = Field(min_length=1, max_length=MOST_ASKED)
    spring: list[Q] = Field(min_length=hw.SPRING_QUESTIONS, max_length=hw.SPRING_QUESTIONS + 1)
    harbour: list[Q] = Field(min_length=1, max_length=hw.HARBOUR_QUESTIONS + 3)
    prizes: list[Prize] = Field(min_length=len(hw.PRIZE_STEPS) + 1, max_length=len(hw.PRIZE_STEPS) + 1)


_SYSTEM = """\
You set the questions and word the prizes for HIGH WATER, a gameshow on a small-town TV station's second channel, in
the FICTIONAL town in the briefing. Des Kneebone asks the questions; two residents climb the harbour steps against the
tide. Book:
- paddle: {paddle} EASY questions, for grown-ups, not children: general knowledge most adults know, with one
  short, settled answer, and a flavour of the sea, the coast or a trade where one fits. Never nursery questions (what a
  cow says, what bees make, the colour of a banana).
- swim: {swim} HARD questions, still fair: a keen quizzer's general knowledge, or the town's own facts from the
  BRIEFING (the answer must be stated there). Not the pub-quiz chestnuts everyone has heard (the Battle of Hastings,
  the capital of Australia, the Night Watch).
- spring: {spring} HARD questions for the spring tide, the star prize's: general knowledge, settled and fair.
Check every answer: it must be right beyond argument, as asked. "The longest river in the British Isles" is the
Shannon, not the Severn (2026-11-20, marked right on air): ask about Great Britain, or don't ask it.
- harbour: {harbour} quick-fire questions about PORT WEXLEY itself, for the Harbourmaster's round, ONLY from facts in
  the BRIEFING (the answer must be stated there): its places, clubs, people, landmarks and doings. Short, a word or two
  to answer.
Each with its answer and one plausible wrong answer someone would give with confidence. Short, as Des would ask them
aloud; no multiple choice; nothing about living people's private lives, no politics, nothing after 2020; none from
RECENT SHOWS again; none giving away another's answer; never say where a fact came from.
- prizes: for each of THE DONORS, in the order given, the prize it gives, a few words, as Des would announce it: the
  first three get bigger ({steps}: a treat, a good prize, a big one), and the last is the STAR PRIZE,
  a weekend away the donor gives or pays for. Real things a local business could give.
Everything is fiction except the general knowledge. Return ONLY JSON.
"""


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def tonight(world: World) -> dict | None:
    return next((k for k in reversed(world.highwaters) if k.get("date") == world.last_date), None)


def should_commission(world: World, now: float | None = None) -> bool:
    now = now or schedule.now()
    return (tonight(world) is None and _at(BOOK_FROM, now) <= now < _at(AIRS_AT, now) + 20 * 60
            and schedule.show_at(_at(AIRS_AT, now)).id == SHOW)


def _since(world: World, days: int) -> str:
    return date.fromordinal(date.fromisoformat(world.last_date).toordinal() - days).isoformat()


def _lately_on_channel8(world: World) -> set[str]:
    """Everyone who climbed lately, or was on Channel 8 in another show lately: not tonight's climbers."""
    names = {c["name"] for k in world.highwaters if k.get("date", "") >= _since(world, REST_DAYS)
             and k.get("date") != world.last_date for c in k["climbers"]}
    since = _since(world, CHANNEL8_DAYS)
    for k in getattr(world, "kettles", []):
        if k.get("date", "") >= since:
            names |= {k["dish"]["cook"], k["sofa"]["name"]}
    for k in getattr(world, "slipways", []):
        if k.get("date", "") >= since:
            names |= {k["feature"]["name"], k["howto"]["name"], k["pupil"]["name"]}
    for q in getattr(world, "quizzes", []):
        if q.get("date", "") >= since:
            names |= {m for t in q["teams"] for m in t["members"]}
    return names


def _nature(name: str) -> tuple[float, bool]:
    """A resident's ability and temperament: their own, the same every time they play."""
    h = zlib.crc32(name.encode())
    return round(0.6 + 0.25 * (h % 1000) / 1000, 2), bool((h >> 10) % 2)


def climbers(world: World) -> list[dict]:
    """Tonight's two, a seeded draw on the date among grown-up residents not on Channel 8 lately."""
    from newsroom import world as world_mod

    out = _lately_on_channel8(world)
    pool = sorted((p for p in world.people if p.kind == "resident" and not world_mod.is_teen(p.role)
                   and p.name not in out and p.role and p.role != "resident"), key=lambda p: p.name)
    rng = random.Random(f"highwater-{world.last_date}")
    two = rng.sample(pool, 2)
    return [{"name": p.name, "role": p.role, "ability": _nature(p.name)[0], "bold": _nature(p.name)[1],
             "gender": (p.voice or "")[1:2]} for p in two]                  # a resident's gender is in their voice


def donors(world: World) -> list[str]:
    """Four of the town's advertisers, in the order of the prizes: step 3, 6, 9 and the star prize."""
    from newsroom import adverts

    try:
        names = sorted(set(adverts.pool().businesses()))
    except Exception:                                                 # no pool: a test, a new town
        names = []
    if len(names) < 4:
        names = sorted(set(names) | set(DONORS))
    return random.Random(f"highwater-donors-{world.last_date}").sample(names, 4)


def _recent_questions(world: World) -> list[str]:
    return [q["q"] for k in world.highwaters[-6:] if k.get("date") != world.last_date for q in k.get("asked", [])]


def needs(game: dict) -> dict[str, int]:
    """How many easy and hard questions the played game takes."""
    return {k: sum(t["choice"] == k for r in game["rounds"] for t in r["turns"]) for k in (hw.PADDLE, hw.SWIM)}


def commission(world: World) -> dict:
    """Book tonight's game: the climbers and donors here, the game played here, then the questions it needs by the
    model."""
    cs, ds = climbers(world), donors(world)
    game = hw.play(random.Random(f"highwater-play-{world.last_date}"), cs)
    need = needs(game)
    recent = _recent_questions(world)
    user = (f"BRIEFING\n{world.summary_for_editor()}\n\nTONIGHT'S CLIMBERS: {cs[0]['name']}, {cs[0]['role']}; "
            f"{cs[1]['name']}, {cs[1]['role']}.\n\nTHE DONORS, in order: " + "; ".join(ds)
            + ("\n\nRECENT SHOWS (don't ask these again):\n" + "\n".join(f"  - {q}" for q in recent) if recent else "")
            + creative.for_planner(world, SHOW))
    system = (_SYSTEM.replace("{paddle}", str(need[hw.PADDLE] + SPARE)).replace("{swim}", str(need[hw.SWIM] + SPARE))
              .replace("{spring}", str(hw.SPRING_QUESTIONS)).replace("{harbour}", str(hw.HARBOUR_QUESTIONS + 1))
              .replace("{steps}", ", ".join(f"step {s}" for s in hw.PRIZE_STEPS)))
    try:
        b = llm.complete_json(TASK, HighWaterBooking, system, user)
    except llm.LLMError as e:
        log.warning("highwater: no questions (%s); the stand-in questions take tonight", e)
        b = None
    return _record(world, cs, ds, game, b)


def _q(x: Q) -> dict:
    return {"q": x.question, "a": x.answer, "wrong": x.wrong}


def _enough(got: list, spare: list, n: int, kind: str) -> list:
    """`got` topped up to `n` from the stand-in's (round again if even those run out): a short list never fails the
    booking, which would lose the prizes' words too."""
    out = list(got)
    if len(out) < n:
        log.warning("highwater: %d %s questions for %d turns; the stand-in's make up the rest", len(got), kind, n)
        extra = [q for q in spare if q.question not in {x.question for x in out}] or list(spare)
        while len(out) < n:
            out += extra[:n - len(out)]
    return out


def _record(world: World, cs: list[dict], ds: list[str], game: dict, b: HighWaterBooking | None) -> dict:
    stand_in = b is None
    spare = _stand_in()
    b = b or spare
    need = needs(game)
    paddle = iter(_enough(b.paddle, spare.paddle, need[hw.PADDLE], "easy"))
    swim = iter(_enough(b.swim, spare.swim, need[hw.SWIM], "hard"))
    for r in game["rounds"]:                      # each question to the turn that takes it, in the order played
        for t in r["turns"]:
            if t["choice"] == hw.PADDLE:
                t["question"] = _q(next(paddle))
            elif t["choice"] == hw.SWIM:
                t["question"] = _q(next(swim))
    game["spring"]["questions"] = [_q(x) for x in b.spring[:hw.SPRING_QUESTIONS]]
    for row, x in zip(game["harbour"]["questions"], _enough(b.harbour, spare.harbour, hw.HARBOUR_QUESTIONS, "town")):
        row["question"] = _q(x)
    prizes = [{"business": d, "prize": p.prize} for d, p in zip(ds, b.prizes)]       # the donors as given, always
    asked = ([t["question"] for r in game["rounds"] for t in r["turns"] if "question" in t]
             + [row["question"] for row in game["harbour"]["questions"]] + game["spring"]["questions"])
    entry = {"date": world.last_date, "stand_in": stand_in, "climbers": cs, "game": game, "asked": asked,
             "prizes": {str(s): p for s, p in zip(hw.PRIZE_STEPS, prizes)}, "star": prizes[-1]}
    for c in cs:
        world.ensure_person(c["name"], c["role"], "resident")
    with world.lock:
        world.highwaters = [k for k in world.highwaters if k.get("date") != world.last_date] + [entry]
        world.highwaters = world.highwaters[-30:]
    res = {x["who"]: x for x in game["results"]}
    log.info("highwater: tonight %s and %s; %s take%s%s", cs[0]["name"], cs[1]["name"],
             " and ".join(f"{n} {_prize_said(entry, res[n]['prize'])}" for n in res), "",
             (" and the star prize" if game["spring"]["won"] else "") + (" (stand-in)" if stand_in else ""))
    return entry


def booked(world: World) -> dict:
    """Tonight's game; the first item to need it books it, if idle time hasn't."""
    return tonight(world) or commission(world)


def seats(world: World) -> list[str]:
    return [c["name"] for c in booked(world)["climbers"]]


# ------------------------------------------------------------------ the briefs

def _prize_said(k: dict, step: int) -> str:
    if not step:
        return "nothing"
    p = k["prizes"][str(step)]
    return f"the step-{step} prize, {p['prize']} from {p['business']}"


def _where(tide: int) -> str:
    return "still below the bottom step" if tide < hw.START else f"up to step {tide}"


def _turn(k: dict, t: dict, n: int, before: int = 0) -> str:
    """One turn, as given. `before`: the prize step the climber had made fast before it, if any."""
    who, frm, to = t["who"], t["from"], t["to"]
    head = f"{n}. {who.upper()}, on step {frm}"
    if t["choice"] == hw.OUT:
        return f"{head}: sits this turn out, wringing out after the soaking. Des has a word with them."
    if t["choice"] == hw.FAST:
        # A climber keeps one prize, their best: on 2026-11-20 Hector made fast the tap, then the fish supper, and
        # the close (rightly) gave him only the supper, which read as the tap gone missing.
        swap = (f", IN PLACE OF {_prize_said(k, before)}: a climber keeps one prize, their best, so Des says the "
                "swap" if before and before != t["banked"] else "")
        return (f"{head}: MAKES FAST: banks {_prize_said(k, t['banked'])}{swap}; it's theirs now, whatever the tide "
                "does. No question.")
    q = t["question"]
    kind = "PADDLES (an easy question)" if t["choice"] == hw.PADDLE else "SWIMS for it (a hard question)"
    if t["right"]:
        move = (f"RIGHT, up to step {to}" if to != frm else "RIGHT, but they're at the top already")
        got = (f"; {_prize_said(k, t['in_hand'])} is now IN HAND, not made fast" if t["in_hand"] and
               t["in_hand"] > hw.prize_at(frm) else "")
    else:
        move = (f"WRONG, saying \"{q['wrong']}\" (the answer: {q['a']}); "
                + ("they stay on step " + str(to) if to == frm else f"they slip down to step {to}"))
        got = ""
    return f"{head}: {kind}. Des asks: \"{q['q']}\" (the answer: {q['a']}). {who} answers: {move}{got}."


def _stand(k: dict, after: list[dict]) -> str:
    return "; ".join(f"{a['who']} on step {a['step']} (made fast: {_prize_said(k, a['banked'])}; in hand: "
                     f"{_prize_said(k, a['in_hand']) if a['in_hand'] else 'nothing'}"
                     + ("; holding a life ring" if a.get("rings") else "") + ")" for a in after)


def _round(k: dict, n: int) -> str:
    r = k["game"]["rounds"][n]
    banked = ({a["who"]: a["banked"] for a in k["game"]["rounds"][n - 1]["after"]} if n else {})
    rows = []
    for i, t in enumerate(r["turns"]):
        rows.append(_turn(k, t, i + 1, banked.get(t["who"], 0)))
        banked[t["who"]] = t["banked"]
    asked = sum("question" in t for t in r["turns"])
    # Told only the turn's parts, rounds two and four of the 2026-11-20 evening came back at 18 lines (151 s and 145 s
    # of a 220 s target) and the loop filled the gap with four chats; round one, each turn in full, ran 33.
    lines = 5 * asked + 2 * (len(r["turns"]) - asked) + 4
    tide = (f"THEN THE TIDE: Des turns to the gauge, and the tide comes in {r['roll']} step"
            f"{'s' if r['roll'] > 1 else ''}, {_where(r['tide'])}.")
    for w in r["washed"]:
        if w.get("ring"):
            tide += (f" It reaches {w['who']} on step {w['from']}: {w['who']} THROWS THE LIFE RING: saved, staying on "
                     f"step {w['from']} with all they have" + (", and no ring left." if not w["rings_left"] else "."))
            continue
        tide += (f" It reaches {w['who']} on step {w['from']}: WASHED OFF, losing "
                 f"{_prize_said(k, w['lost']) if w['lost'] else 'nothing in hand'} "
                 f"(keeping {_prize_said(k, w['kept']) if w['kept'] else 'nothing made fast'}), and starts again on "
                 f"step {w['to']}, sitting out their next turn.")
    if not r["washed"]:
        tide += " It reaches nobody."
    # Told only "turn by turn", round four of the fourth rehearsal (2026-11-19) dropped a turn and its question.
    return (f"ROUND {n + 1} OF {hw.ROUNDS}: {len(rows)} TURNS, and every one of them goes out, in this order, none left "
            "out or merged (a dropped turn is a hole in the game). Des runs it turn by turn, each exactly as given, "
            f"asking every question word for word. About {lines} lines: a question turn is five (Des's word with the "
            "climber, their choice and why, the question, their answer, his verdict), never squeezed into two:\n" + "\n".join(rows) + f"\n{tide}\nWHERE THEY STAND, for Des to sum "
            f"up: {_stand(k, r['after'])}.")


def _harbour(k: dict) -> str:
    h = k["game"]["harbour"]
    rows = []
    for i, x in enumerate(h["questions"]):
        q = x["question"]
        row = f"{i + 1}. Des asks: \"{q['q']}\" (the answer: {q['a']}). {x['first']} is in first: "
        if x["right"]:
            row += "RIGHT, " + ("and wins a LIFE RING." if x["ring"] else "but already holds a ring: no second.")
        else:
            row += f"WRONG, saying \"{q['wrong']}\"; {x['second']} has a go: "
            row += (("RIGHT, " + ("and wins a LIFE RING." if x["ring"] else "but already holds a ring: no second."))
                    if x["second_right"] else "WRONG too, with a different wrong answer; Des gives the answer.")
        rows.append(row)
    held = "; ".join(f"{n} {'holds a life ring' if v else 'has no ring'}" for n, v in h["rings"].items())
    return ("THE HARBOURMASTER'S ROUND, halfway: quick-fire questions about Port Wexley, no climbing; whoever's in first "
            "answers, and a right answer wins a LIFE RING, which saves its holder from one tide, one ring each at most. "
            "Each exactly as given:\n" + "\n".join(rows) + f"\nAFTER IT, for Des to say: {held}.")


def _open(k: dict) -> str:
    cs = k["climbers"]
    prizes = "; ".join(f"step {s}: {p['prize']} from {p['business']}" for s, p in k["prizes"].items())
    return (f"tonight's climbers, {cs[0]['name']} ({cs[0]['role']}) and {cs[1]['name']} ({cs[1]['role']}); the "
            f"prizes on the steps ({prizes}), and the star prize at the spring tide: {k['star']['prize']} from "
            f"{k['star']['business']}. The rules in a line: an easy question climbs one step, a hard one two (and a "
            "slip if it's wrong), making fast banks the prize; the tide comes in after every round; and halfway, the "
            "Harbourmaster's round, for life rings")


def _meet(k: dict, i: int) -> str:
    c, other = k["climbers"][i], k["climbers"][1 - i]
    how = "they'll go bold, swimming for it" if c["bold"] else "they'll play it safe and make fast early"
    # Told only that the other "listens", the rehearsal's first meet introduced both, and the second said it again.
    rest = (f"ONLY {c['name']} is met in this item: {other['name']} is met in the next, so Des doesn't introduce them or "
            "ask them anything yet" if i == 0 else f"{other['name']}, met already, gets a line in")
    return (f"{c['name']}, {c['role']}: who they are in Port Wexley, why they've come to climb, and how they'll play it "
            f"({how}). {rest}")


def _so_far(k: dict) -> str:
    """The game after the last round, for the chats: where they stand, every soaking and life ring, and who's next."""
    g = k["game"]
    wet = [f"{w['who']} {'saved by the life ring' if w.get('ring') else 'washed off'} in round {n + 1}"
           for n, r in enumerate(g["rounds"]) for w in r["washed"]]
    return (f"all {hw.ROUNDS} rounds are played; {_stand(k, g['rounds'][-1]['after'])}; "
            + ("; ".join(wet) if wet else "nobody has been washed off or soaked tonight")
            + f"; next, {g['spring']['who']} plays the spring tide for the star prize")


def _spring(k: dict) -> str:
    g = k["game"]
    sp, res = g["spring"], {x["who"]: x for x in g["results"]}
    other = next(c["name"] for c in k["climbers"] if c["name"] != sp["who"])
    rows = [f"{i + 1}. Des asks: \"{q['q']}\" (the answer: {q['a']}). {sp['who']} answers: "
            + ("RIGHT." if right else f"WRONG, saying \"{q['wrong']}\".")
            for i, (q, right) in enumerate(zip(sp["questions"], sp["answers"]))]
    return (f"THE SPRING TIDE: {sp['who']}, the higher climber on step {res[sp['who']]['step']}, plays for the star "
            f"prize, {k['star']['prize']} from {k['star']['business']}: three hard questions, two right to win. "
            f"They play from step {res[sp['who']]['step']}, where they stand"
            + (" (the top step)" if res[sp["who"]]["step"] >= hw.STEPS else f", not the top step ({hw.STEPS})")
            + ". "
            f"{other} watches from step {res[other]['step']}. Each exactly as given:\n" + "\n".join(rows)
            + (f"\n{sp['who']} WINS THE STAR PRIZE." if sp["won"] else f"\n{sp['who']} doesn't get the two: no star "
               "prize tonight, and Des is kind about it."))


def _close(k: dict) -> str:
    g = k["game"]
    rows = [f"{x['who']} goes home with {_prize_said(k, x['prize'])}"
            + (f" AND the star prize, {k['star']['prize']} from {k['star']['business']}" if x["star"] else "")
            for x in g["results"]]
    return ("THE RESULT: " + "; ".join(rows) + ". Each takes home one prize, their best (one made fast lower down "
            "was swapped for it, so it isn't theirs as well). Des thanks the climbers and the donors, and says "
            "goodnight: The Slipway is next")


def aired(seg, world: World) -> None:
    """player.AIRED_HOOKS: the result went out, so tonight's booking says so, for the town's talk the next day
    (newsroom/talk.py). On the booking, not the archive, as the Kettle's On's are (kettle.aired): a Channel 7 night can
    fill the whole archive before the talk is wanted."""
    k = tonight(world)
    if k is not None and "{close}" in (seg.brief or "") and not k.get("result_aired"):
        with world.lock:
            k["result_aired"] = True


def brief_for(world: World, brief: str) -> str:
    """An item's brief with its part of the game in full: "{r2}" becomes round two, "{close}" the result."""
    k = booked(world)

    def part(m: re.Match) -> str:
        tok = m.group(1)
        if tok == "open":
            return _open(k)
        if tok.startswith("meet"):
            return _meet(k, int(tok[4]) - 1)
        if tok.startswith("r"):
            return _round(k, int(tok[1]) - 1)
        if tok == "hm":
            return _harbour(k)
        if tok.startswith("chat"):
            c = k["climbers"][int(tok[4]) - 1]
            return f"{c['name']}, {c['role']}"
        if tok == "sofar":
            return _so_far(k)
        if tok == "spring":
            return _spring(k)
        return _close(k)
    return TOKEN.sub(part, brief or "")


def for_prompt(world: World) -> str:
    """The game for every item: the climbers, and what has happened so far tonight."""
    k = booked(world)
    with world.lock:
        aired = [e for e in world.archive if e["date"] == world.last_date and e.get("show") == SHOW
                 and e["type"] != T.ad_break.value]
    cs = k["climbers"]
    done = ("\nSO FAR TONIGHT (don't do these again):\n" + "\n".join(
        f"  - {e['type'].replace('_', ' ')}: {e['headline']}" for e in aired)) if aired else ""
    return (f"THE GAME: High Water, on the harbour steps. THE CLIMBERS (each speaks as speaker \"guest\" with "
            f"guest_name their exact name): {cs[0]['name']}, {cs[0]['role']}; {cs[1]['name']}, {cs[1]['role']}. "
            "Every question, answer, step and wave is fixed: keep to them exactly." + done)


# ------------------------------------------------------------------ the checks

_PLAIN = {"what", "which", "when", "where", "does", "have", "with", "that", "this", "from", "into", "your", "there",
          "their", "they", "them", "were", "many", "much", "name", "known", "called", "would", "could", "about"}


def _words(text: str, short: int = 4) -> set[str]:
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", text.lower()).split() if len(w) >= short and w not in _PLAIN}


def _questions(k: dict, brief: str) -> list[dict]:
    m = re.search(r"\{r([1-4])\}", brief or "")
    if m:
        return [t["question"] for t in k["game"]["rounds"][int(m.group(1)) - 1]["turns"] if "question" in t]
    if "{hm}" in (brief or ""):
        return [row["question"] for row in k["game"]["harbour"]["questions"]]
    return k["game"]["spring"]["questions"] if "{spring}" in (brief or "") else []


def _asked_in(q: str, line: set[str]) -> bool:
    """Is question `q` in a line of Des's: most of its telling words there, in any order, as he'd put it in his own
    way ("What does fortissimo mean, in music?"). By its first five words in order, a paraphrase failed two rounds of
    four in the rehearsal (2026-11-19), and one went to the code's own round."""
    want = _words(q)
    if len(want) < 3:                     # "What is nine times six?": two words of four letters; the three-letter ones too
        want, line = _words(q, 3), line | {w for w in line if len(w) == 3}
    return bool(want) and len(want & line) >= max(min(2, len(want)), -(-len(want) * 3 // 5))


def asked_at(lines, qs: list[dict]) -> list[int | None]:
    """The line (its index in `lines`) where Des asks each question, each in a line of its own; None where he doesn't.
    In any order: two climbers' turns swapped in a round change nothing in the game, and in order, the fourth
    rehearsal's round four failed for it (2026-11-19). The check and the tide gauge (tidegauge.py) both read it."""
    said = [(i, _words(l.text or "", 3)) for i, l in enumerate(lines) if getattr(l, "speaker", "") == HOST]
    out, used = [], set()
    for q in qs:
        at = next((i for i, words in said if i not in used and _asked_in(q["q"], words)), None)
        out.append(at)
        if at is not None:
            used.add(at)
    return out


def missing(lines, qs: list[dict]) -> list[str]:
    """The questions Des doesn't ask (asked_at)."""
    return [q["q"] for q, at in zip(qs, asked_at(lines, qs)) if at is None]


_NUMBERS = {w: n for n, w in enumerate("zero one two three four five six seven eight nine ten eleven twelve".split())}
_ON_STEP = re.compile(r"\b(?:on|at) step (\d+|" + "|".join(_NUMBERS) + r")\b", re.I)


def step_slips(lines, k: dict, n: int) -> list[str]:
    """Where Des puts a climber "on step N" in round `n + 1` (in his line, with their name) and they weren't there.
    The 2026-11-24 rounds opened "Doris Penhallow, you're on step seven" (round 2: on five, seven where her first turn
    took her) and "on step twelve" (round 4: on eleven, twelve after her first turn), so a step is held to the moment:
    before a climber's question, the step that turn starts from; after it, where it left them; after their last,
    where the round and its tide leave them. A climber whose question Des didn't ask can't be placed: any step of
    theirs this round will do."""
    r = k["game"]["rounds"][n]
    turns = r["turns"]
    asked = [t for t in turns if "question" in t]
    at = {id(t): i for t, i in zip(asked, asked_at(lines, [t["question"] for t in asked]))}
    names = {c["name"]: c["name"].split()[0] for c in k["climbers"]}
    ends = {a["who"]: a["step"] for a in r.get("after", [])}
    washed = {w["who"]: {w["from"], w["to"]} for w in r.get("washed", [])}
    out = []
    for i, line in enumerate(lines):
        if getattr(line, "speaker", "") != HOST:
            continue
        for sentence in re.split(r"(?<=[.!?])\s+", line.text or ""):
            for m in _ON_STEP.finditer(sentence):
                before = [(sentence.lower().rfind(first.lower(), 0, m.start()), who) for who, first in names.items()]
                pos, who = max(before)
                if pos < 0:
                    continue                                 # no climber named before it: "the water's at step two"
                mine = [t for t in turns if t["who"] == who]
                every = {s for t in mine for s in (t["from"], t["to"])} | {ends.get(who)} | washed.get(who, set())
                done = [j for j, t in enumerate(mine) if at.get(id(t)) is not None and at[id(t)] < i]
                last = done[-1] if done else -1
                if any("question" in t and at.get(id(t)) is None for t in mine[:last + 2]):
                    allowed = every                          # a turn up to here that can't be placed
                elif not done:
                    allowed = {mine[0]["from"]}
                else:
                    allowed = {mine[last]["to"]} | {t["from"] for t in mine[last + 1:last + 2]}
                    if all(at.get(id(t)) is not None and at[id(t)] < i for t in mine if "question" in t):
                        allowed |= {ends.get(who)} | washed.get(who, set())
                said = int(m.group(1)) if m.group(1).isdigit() else _NUMBERS[m.group(1).lower()]
                if said not in allowed:
                    out.append(f"{who} is on step {' or '.join(map(str, sorted(s for s in allowed if s is not None)))}"
                               f" there, not {said} (\"{sentence.strip()[:90]}\")")
    return out


def check(seg, script, world: World) -> None:
    """writers.CHECK_HOOKS: a round, or the spring tide, asks every question it was given, in order. A round puts each
    climber on the step they're on (step_slips): asked once more, and a step still wrong after that stands (logged),
    rather than give the round to the code's own script for a step."""
    if seg.type is not T.interview:
        return
    k = booked(world)
    gone = missing(script.lines, _questions(k, seg.brief or ""))
    m = re.search(r"\{r([1-4])\}", seg.brief or "")
    slips = step_slips(script.lines, k, int(m.group(1)) - 1) if m else []
    if not gone and not slips:
        return
    if not gone and seg.work.get("steps_asked"):
        log.warning("high water slot %s: steps still wrong after asking again; they stand: %s", seg.slot_id,
                    "; ".join(slips))
        return
    seg.work["steps_asked"] = True
    said = []
    if gone:
        said.append("Des must ask every question in THIS ITEM, word for word and in order; these weren't asked: "
                    + " / ".join(f"\"{q}\"" for q in gone))
    if slips:
        said.append("every climber is on the step THIS ITEM gives them at that moment (the step a turn starts from "
                    "until Des asks its question); these were wrong: " + "; ".join(slips))
    raise llm.AskAgain(". ".join(said))


def caption(world: World, name: str) -> str | None:
    k = tonight(world)
    c = next((c for c in (k or {}).get("climbers", []) if c["name"] == name), None)
    return f"Climbing tonight: {c['role']}"[:60] if c else None


# ------------------------------------------------------------------ the show

# The chats come after the last round, before the spring tide. Not told so, nor what had happened, the 2026-11-20
# evening's had waves over the steps on a night nobody got wet, and "let's see what the tide has in store for you next".
_DONE = ("a word with the climbers between the last round and the spring tide, no questions and no climbing. THE GAME "
         "SO FAR, fixed, nothing added (no wave, soaking or climb that isn't here): {sofar}. ")
SHOW_DEF = Show(
    SHOW, "HIGH WATER", "HIGH WATER", (30, 110, 170),
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Des opens High Water: a showman's good evening from the harbour steps, {open}. A "
                                 "line for each climber and a line for each prize",
          target_s=50.0),
        # One climber an item since 2026-11-19 (the user): both in one item came to 73 s.
        I(T.interview, brief="MEET THE CLIMBER: Des meets {meet1}. No questions and no climbing yet", target_s=120.0),
        I(T.interview, brief="MEET THE CLIMBER: Des meets {meet2}. No questions and no climbing yet", target_s=120.0),
        I(T.interview, brief="{r1}", target_s=220.0),
        T.ad_break,
        I(T.interview, brief="{r2}", target_s=220.0),
        I(T.interview, brief="{hm}", target_s=180.0),           # the Harbourmaster's round, halfway
        T.ad_break,
        I(T.interview, brief="{r3}", target_s=220.0),
        T.ad_break,
        I(T.interview, brief="{r4}", target_s=220.0),
        # Wraps to here until the close: a word with one climber or both, a different angle each lap.
        I(T.interview, brief=tuple(_DONE + b for b in (
            "Des has a word with {chat1} about their life in Port Wexley and what they'd do with the star prize",
            "Des has a word with {chat2} about their life in Port Wexley and what they'd do with the star prize",
            "Des asks both climbers about the climb so far: the question they'll remember, and who's been the braver",
            "Des tells the climbers a terrible pier-theatre story, and they tell him one of their own",
            "Des asks {chat1} what the harbour was like when they were young, and {chat2} chips in",
            "Des asks both climbers which prize they'd swap theirs for, the star prize aside, and why, and they argue",
        )), target_s=110.0),
    ),
    loop_from=12,
    whole_order=True,                   # every round airs, however long they run: a round cut for time loses the game
    # Near what they ran in the rehearsal (82 s and 70 s), so the producer's sums close the half hour on time.
    closing=(I(T.interview, brief="{spring}", target_s=100.0),
             I(T.interview, "close", brief="{close}", target_s=75.0)),
    # Three breaks of two minutes, as a commercial half hour has (the user, 2026-11-19): about 23 minutes of programme.
    target_s={T.bumper: 8.0, T.links: 50.0, T.interview: 200.0, T.ad_break: 120.0},
    cast=(HOST,), lead=HOST,
    cast_by_type={T.links: (HOST,), T.interview: (HOST, "guest")},
    station="High Water, the gameshow on Channel 8, Port Wexley's second channel, with Des Kneebone",
    tone="a showman's warmth and terrible puns: tension at every decision, cheers for a climb, groans for a wave",
    light=True,
    repeats_overnight=False,
)

_RULES = """
This is part of HIGH WATER, a gameshow on the harbour steps. Des Kneebone ("hw_host") hosts: sixties, thirty
summers at the Saltby pier theatre, a bow tie, catchphrases ("Mind the weed!", "Steady as she goes"), terrible
puns, soft on a losing climber. Every climber is speaker "guest" with guest_name their exact name from THE GAME.
The game is FIXED: every choice (paddle, swim, make fast), question, answer, step and wave goes exactly as THIS ITEM
says. Never add a question, change an answer, a step or the tide. The general knowledge questions are real-world
facts, given to you: read them as given. A wrong answer is the one given, said with conviction. Light and kind:
no news, thread_id is null.
"""

SYSTEMS = {
    T.links: _COMMON_RULES + _RULES + """
These are Des's words TO CAMERA ("hw_host" alone), as THIS ITEM and the PLACE IN THE SHOW say. No climber speaks.
Short lines, one thing a line: at least six of them, never a speech in one (an opening in one line of over 900
characters failed twice in the rehearsal, 2026-11-19).
headline = the point in under 12 words. lower_third = "High Water" plus a short tag.
""",
    T.interview: _COMMON_RULES + _RULES + """
This is Des with the climbers, as THIS ITEM says. When it is a ROUND: turn by turn, Des says whose go it is and has a
quick word with them before they choose (the water, their nerve, the prize in sight: a line each way), they say what
they choose, Des asks the question word for word, the climber answers as given, and Des says where that leaves them;
then the tide comes in as given, and Des sums up where they stand. At most 38 lines. Every climber speaks. When it is THE HARBOURMASTER'S ROUND, it's quick-fire: Des asks each question as
given, whoever's in first answers as given, and Des hands out the life rings. When it is the SPRING TIDE, it goes question by question as given. When it is a
word between rounds, there are no questions. Every "guest" line names its speaker in guest_name. headline = the
round and how it went, under 12 words. lower_third = "High Water" plus the round, short.
""",
}

PLACE = {
    (SHOW, T.links): {"open": f"PLACE IN THE SHOW: this OPENS {TITLE}: the first words of the programme.",
                      "": _MIDDLE.format(title=TITLE, extra="")},
    (SHOW, T.interview): {"close": f"PLACE IN THE SHOW: this CLOSES {TITLE}: the last words of the programme.",
                          "": _MIDDLE.format(title=TITLE, extra="")},
}

IDENT = "Hold on to your hats: it's High Water! On Channel 8."


# ------------------------------------------------------------------ the creative editor

def digest(world: World, day: str) -> str:
    """The game booked for `day`, as the creative editor reads it after it has aired; "" for none or the stand-in."""
    k = next((x for x in world.highwaters if x.get("date") == day), None)
    if not k or k.get("stand_in"):
        return ""
    g = k["game"]
    washed = sum(len(r["washed"]) for r in g["rounds"])
    return (f"The climbers: {'; '.join(c['name'] + ', ' + c['role'] + (' (bold)' if c['bold'] else ' (cautious)') for c in k['climbers'])}\n"
            f"The prizes: {'; '.join(f'step {s}: ' + p['prize'] + ' from ' + p['business'] for s, p in k['prizes'].items())}; "
            f"the star prize {k['star']['prize']} from {k['star']['business']}\n"
            f"The game (played in code, not the booking's choice): {washed} soaking(s); the spring tide "
            f"{'won' if g['spring']['won'] else 'lost'} by {g['spring']['who']}\n"
            f"Some of the questions: {'; '.join(q['q'] for q in k['asked'][:8])}")


def enrol():
    """Enrol the show with the creative editor: notes after air, for the next booking. Returns an undo."""
    return creative.register(
        SHOW, TITLE, kind="light", airs_at=AIRS_AT,
        brief=("A half-hour gameshow on the harbour steps: Des Kneebone, an end-of-pier showman, hosts two residents "
               "who climb against the tide with easy and hard questions, banking prizes from the town's businesses, "
               "the higher one playing the spring tide for a weekend away. The game is played in code; the show is "
               "the patter, the tension and the town's own people."),
        decides=("the questions and their answers, and the prizes' wording. Not the climbers, the donors or the game "
                 "(all in code), nor Des's lines or how the half hour runs"),
        digest=digest, books=should_commission)


# ------------------------------------------------------------------ with no model

_STAND_IN_PADDLE = (("How many days are there in a leap year?", "366", "365"),
                    ("What colour do you get by mixing blue and yellow?", "green", "purple"),
                    ("How many legs does a spider have?", "eight", "six"),
                    ("What is the largest planet in our solar system?", "Jupiter", "Saturn"),
                    ("Which bird is the symbol of peace?", "the dove", "the swan"),
                    ("How many minutes are there in an hour?", "sixty", "a hundred"),
                    ("What do bees make?", "honey", "wax"),
                    ("Which ocean lies between Europe and America?", "the Atlantic", "the Pacific"),
                    ("What is frozen water called?", "ice", "snow"),
                    ("How many sides does a triangle have?", "three", "four"),
                    ("What is the opposite of high tide?", "low tide", "slack water"),
                    ("Which month comes after March?", "April", "May"))
_STAND_IN_SWIM = (("What is the capital city of Canada?", "Ottawa", "Toronto"),
                  ("How many bones are there in the adult human body?", "206", "212"),
                  ("Which element has the chemical symbol Fe?", "iron", "lead"),
                  ("In which year did the Titanic sink?", "1912", "1915"),
                  ("What is the longest river in Africa?", "the Nile", "the Congo"),
                  ("Who wrote Pride and Prejudice?", "Jane Austen", "Charlotte Bronte"),
                  ("How many hearts does an octopus have?", "three", "two"),
                  ("What is the hardest natural substance?", "diamond", "granite"),
                  ("Which planet is known as the Red Planet?", "Mars", "Venus"),
                  ("What is the square root of 144?", "twelve", "fourteen"),
                  ("Which sea creature has a mouth on its underside and five arms?", "a starfish", "a crab"),
                  ("What does a barometer measure?", "air pressure", "wind speed"))
_STAND_IN_SPRING = (("What is the smallest country in the world?", "Vatican City", "Monaco"),
                    ("Which composer wrote the Four Seasons?", "Vivaldi", "Mozart"),
                    ("What is the chemical symbol for gold?", "Au", "Ag"))
# The town's settled facts, for the Harbourmaster's round with no model: places that are in every briefing.
_STAND_IN_HARBOUR = (("What's the name of the secondary school?", "Greymouth Academy", "Port Wexley High"),
                     ("Which village is across the bay by the foot ferry?", "Saltby", "Greymouth"),
                     ("What's the marsh reserve called?", "the Salting", "the Levels"),
                     ("Which street has the market stalls and the bakeries?", "Harrow Street", "Quay Street"),
                     ("What number is the town's own television channel?", "seven", "five"),
                     ("What do the boats land at Monday's auction?", "fish", "crabs"))
_STAND_IN_PRIZES = ("a cream tea for two", "a hamper of local treats", "a voucher for a hundred pounds",
                    "a weekend away for two")


def _stand_in() -> HighWaterBooking:
    def qs(rows):
        return [{"question": q, "answer": a, "wrong": w} for q, a, w in rows]
    return HighWaterBooking.model_validate({
        "paddle": qs(_STAND_IN_PADDLE), "swim": qs(_STAND_IN_SWIM), "spring": qs(_STAND_IN_SPRING),
        "harbour": qs(_STAND_IN_HARBOUR),
        "prizes": [{"business": "a donor", "prize": p} for p in _STAND_IN_PRIZES]})


def template(seg_type, world, rng: random.Random, part: str, work: dict, brief: str):
    """High Water with no model, or a round the writer wouldn't keep to: the code's own, exactly as played."""
    from newsroom.models import BulletinScript, LiveLine, PanelLine, PanelScript

    k = booked(world)
    cs = k["climbers"]
    if seg_type is T.links:
        return BulletinScript(lines=[
            LiveLine(speaker=HOST, text="Good evening, and welcome to High Water, on the harbour steps!"),
            LiveLine(speaker=HOST, text=f"Tonight {cs[0]['name']} and {cs[1]['name']} climb against the tide."),
            LiveLine(speaker=HOST, text=f"And at the spring tide: {k['star']['prize']}. Mind the weed!")],
            headline=f"High Water: {cs[0]['name']} and {cs[1]['name']}", lower_third=TITLE)
    if seg_type is not T.interview:
        return None
    lines: list = []
    m = re.search(r"\{r([1-4])\}", brief or "")
    if m:
        n = int(m.group(1)) - 1
        r = k["game"]["rounds"][n]
        lines.append(PanelLine(speaker=HOST, text=f"Round {n + 1}! Steady as she goes."))
        for t in r["turns"]:
            if t["choice"] == hw.OUT:
                lines.append(PanelLine(speaker=HOST, text=f"{t['who']}, you're wringing out this turn."))
                continue
            if t["choice"] == hw.FAST:
                lines.append(PanelLine(speaker=HOST, text=f"{t['who']}, you're making fast: {_prize_said(k, t['banked'])} "
                                                          "is yours."))
                lines.append(PanelLine(speaker="guest", guest_name=t["who"], text="I'll take it, Des!"))
                continue
            q = t["question"]
            lines.append(PanelLine(speaker=HOST, text=f"{t['who']}, {'paddle' if t['choice'] == hw.PADDLE else 'swim'}: "
                                                      f"{q['q']}"))
            lines.append(PanelLine(speaker="guest", guest_name=t["who"], text=(q["a"] if t["right"] else q["wrong"])
                                   .capitalize() + "?"))
            lines.append(PanelLine(speaker=HOST, text=(f"Right! Up to step {t['to']}." if t["right"] else
                                                       f"Oh, no, it was {q['a']}. Step {t['to']}.")))
        washed = ", ".join(w["who"] for w in r["washed"])
        lines.append(PanelLine(speaker=HOST, text=f"And here comes the tide: {r['roll']} up, {_where(r['tide'])}."
                                                  + (f" {washed}, you're washed off!" if washed else " Nobody wet!")))
        head = f"High Water, round {n + 1}"
    elif "{hm}" in (brief or ""):
        h = k["game"]["harbour"]
        lines.append(PanelLine(speaker=HOST, text="It's the Harbourmaster's round! Quick-fire, Port Wexley only."))
        for x in h["questions"]:
            q = x["question"]
            lines.append(PanelLine(speaker=HOST, text=q["q"]))
            lines.append(PanelLine(speaker="guest", guest_name=x["first"],
                                   text=(q["a"] if x["right"] else q["wrong"]).capitalize() + "!"))
            if not x["right"]:
                lines.append(PanelLine(speaker="guest", guest_name=x["second"],
                                       text=(q["a"].capitalize() + "!") if x["second_right"] else "Pass, Des."))
            lines.append(PanelLine(speaker=HOST, text=(f"A life ring for {x['ring']}!" if x["ring"] else
                                                       f"It was {q['a']}." if not (x["right"] or x["second_right"])
                                                       else "Right, but you've a ring already!")))
        head = "The Harbourmaster's round"
    elif "{spring}" in (brief or ""):
        sp = k["game"]["spring"]
        lines.append(PanelLine(speaker=HOST, text=f"{sp['who']}, it's the spring tide. Three questions, two to win."))
        for q, right in zip(sp["questions"], sp["answers"]):
            lines.append(PanelLine(speaker=HOST, text=q["q"]))
            lines.append(PanelLine(speaker="guest", guest_name=sp["who"],
                                   text=(q["a"] if right else q["wrong"]).capitalize() + "?"))
        lines.append(PanelLine(speaker=HOST, text="You've won the star prize!" if sp["won"] else "Not tonight, my love."))
        head = "The spring tide"
    elif part == "close":
        lines = [PanelLine(speaker=HOST, text="That's High Water for tonight!"),
                 PanelLine(speaker="guest", guest_name=cs[0]["name"], text="Thanks, Des!"),
                 PanelLine(speaker="guest", guest_name=cs[1]["name"], text="I'm still wet."),
                 PanelLine(speaker=HOST, text="The Slipway is next. Goodnight!")]
        head = "High Water: the result"
    else:
        c = cs[rng.randrange(2)]
        lines = [PanelLine(speaker=HOST, text=f"{c['name']}, how's life in Port Wexley?"),
                 PanelLine(speaker="guest", guest_name=c["name"], text="Busy, Des. Like the tide."),
                 PanelLine(speaker=HOST, text="Steady as she goes!")]
        head = f"A word with {c['name']}"
    return PanelScript(lines=lines[:40], headline=head, lower_third=TITLE,
                       guest_name=next((l.guest_name for l in lines if l.speaker == "guest"), None))
