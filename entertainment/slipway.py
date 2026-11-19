"""The Slipway: Channel 8's teen magazine, 18:30 to 19:00 (agreed with the user 2026-11-19, in place of Cartoon Time,
whose films are hard to render well).

Half an hour from a studio of its own, presented by a double act whose ways clash (as The Kettle's On's and
Coastwide's do, the most watchable thing on air): Tegan Trevenna ("slip_a"), twenty-one, who throws herself into
everything and finishes nothing, and Elis Pengilly ("slip_b"), twenty-two, who plans, makes lists and checks the
rules. Both are presenters, never residents.

Each night: THE FEATURE, a young person from town with something to show (and, later in the half hour, Tegan has a
go at it with them); HOW TO, someone showing how to do one useful thing; ACADEMY CORNER, a pupil from Greymouth
Academy on something at school; viewers' messages, THE BIG QUESTION (a daft one the presenters take sides on), what's
on for young people this week, and THE CHALLENGE: how last time's went and the next one. All booked by one
back-office call from BOOK_FROM (The Chamber's route unless config.toml gives "slipway" its own), recorded in
`world.slipways` and handed to every item; if the call fails, a stand-in booking is made in code.

Light, safe and kind: no news, no threads, nothing grim, nothing risky to copy at home (no harbour jumping, nothing in
the water without a club). The guests join the town as residents; the pupil is a teenager (world.is_teen) and speaks
in a teenager's voice.
"""
from __future__ import annotations

import logging
import random
import re
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from newsroom import llm, schedule
from newsroom.config import CONFIG
from newsroom.models import SegmentType as T, _clip_words
from newsroom.schedule import Item as I, Show
from newsroom.world import World
from newsroom.writers import _COMMON_RULES, _MIDDLE

from . import creative

log = logging.getLogger(__name__)

SHOW = "slipway"
TITLE = "The Slipway"
AIRS_AT = "18:30"
BOOK_FROM = "17:00"
TASK = "slipway" if "slipway" in CONFIG.llm.routes else "chamber"
REST_DAYS = 28                          # a feature guest, a how-to or a pupil isn't booked again within this
SO_FAR_CHARS = 200
TOKEN = re.compile(r"\{(feature|howto|steps|pupil|letters|more|question|whatson|challenge|last)\}")
HOST_A, HOST_B = "Tegan Trevenna", "Elis Pengilly"

# Its own set until its art is made and approved: the breakfast sofa's painter (a window onto the harbour) stands
# in, under an id of its own, with marks for the pair and one guest as The Kettle's On has.
SET = "studio_slipway"
SET_NAME = "The Slipway's studio"
SET_BLURB = "a bright studio with a window onto the harbour, a low sofa, bean bags and a board of viewers' messages"
SET_COLOURS = ((70, 150, 170), (230, 120, 60))
STAND_IN_PAINTER = "studio_sofa"
MARKS = {"host": (122, 146, 2, 1), "panel_1": (186, 146, 2, -1), "panel_2": (272, 150, 2, -1)}

_FEATURE = ("THE FEATURE: {feature}. Tegan and Elis talk to them about it: how they started, what it's like, the best "
            "and worst moment, and one thing a viewer could do to start. Tegan wants to try it at once; Elis wants to "
            "know the rules")
_HAVE_A_GO = ("HAVE A GO: {feature} is back, and Tegan has a go at it with them, coached step by step, while Elis "
              "reads the safety notes and keeps score. Nothing from the first part told again; nothing anyone could "
              "get hurt copying at home")
_HOWTO = ("HOW TO: {howto} shows Tegan and Elis how to do it, in these steps, in order: {steps}. Elis follows the "
          "steps exactly, Tegan skips ahead; the guest keeps them both right")
_ACADEMY = ("ACADEMY CORNER: {pupil}. Tegan and Elis ask them about it, kindly: what it is, who's in it, and how "
            "people can come or join. The pupil is called by their first name only, and nothing personal is asked")
_LETTERS = ("THE MESSAGES: Tegan and Elis read out viewers' messages, each with the sender's first name and where "
            "they're from: {letters}. A line or two on each; they disagree about one")
_QUESTION = ("THE BIG QUESTION: {question} Tegan and Elis take opposite sides, each with three reasons, and say "
             "viewers can send in their answer for next time. Only Tegan and Elis speak")
_WHATSON = ("WHAT'S ON: Tegan and Elis go through what's on for young people this week: {whatson}. When and where for "
            "each; Elis has made a plan to get to all of them, Tegan will get to one")
_CHALLENGE = ("THE CHALLENGE: last time's challenge was {last}; Tegan and Elis say how viewers got on and how they did "
              "themselves (Tegan didn't finish it). Then this week's: {challenge}. Elis reads the rules")

# The loop, until the close: Tegan and Elis on their own, a new bit each lap (only they speak in these).
_ONLY = ". Only Tegan and Elis speak, to each other more than to camera; nothing a guest has said tonight"
_BITS_A = tuple(b + _ONLY for b in (
    "ELIS'S LIST: Elis reads out his top three of something (things to do in Port Wexley on a wet Saturday, ways to "
    "save up for something, the best chips on the front), and Tegan argues with every one",
    "TRY IT: Tegan tries something Elis has prepared for her (a tongue-twister, a card trick, folding a paper boat "
    "that floats) while Elis reads the instructions out exactly",
    "QUICK-FIRE: Elis puts eight quick this-or-that questions to Tegan (chips or pasty, sunrise or sunset), she "
    "answers without thinking, then he answers them all the other way",
    "THE PLAN: Elis unveils his plan for the weekend, to the quarter hour; Tegan takes it apart and says what she'll "
    "actually do",
    "ELIS EXPLAINS: Elis explains properly how one everyday thing works (why the tide comes in twice a day, how a "
    "lighthouse lamp turns), and Tegan gives her own much shorter version",
))
_BITS_B = tuple(b + _ONLY for b in (
    "MORE MESSAGES: Tegan and Elis read out more viewers' messages: {more}. A line or two on each",
    "TEGAN'S WEEK: Tegan tells Elis about something she started this week and didn't finish, and Elis works out what "
    "went wrong",
    "WOULD YOU RATHER: Tegan and Elis take turns with would-you-rather questions about life in a seaside town, and "
    "have to choose",
    "WHO WON THE WEEK: Tegan and Elis go back over the arguments they've had this week, and decide who won each",
))

# Between the bits, a guest again: five quick questions to each of tonight's three in turn (with only the bits, a
# half hour whose items ran short was half Tegan and Elis on their own, in the producer's own sums).
_QUICK = tuple(b + ". Five short answers, a laugh or two; nothing from their own item told again" for b in (
    "QUICK FIVE, THE FEATURE: Tegan and Elis put five quick questions to {feature} (first thing they'd save in a "
    "fire, best advice they were ever given, and three of their own)",
    "QUICK FIVE, HOW TO: Tegan and Elis put five quick questions to {howto} (the thing they're worst at, their first "
    "job, and three of their own)",
    "QUICK FIVE, ACADEMY: Tegan and Elis put five quick, kind questions to {pupil} (favourite lesson, best school "
    "trip, and three of their own; nothing personal)",
))

SHOW_DEF = Show(
    SHOW, "THE SLIPWAY", "SLIPWAY", (40, 160, 190),
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Tegan and Elis open The Slipway: a quick hello from the studio, and what's on "
                                 "tonight: the feature, the how-to, Academy Corner and the challenge", target_s=40.0),
        I(T.interview, brief=_FEATURE, target_s=220.0),
        I(T.links, brief=_LETTERS, target_s=70.0),
        T.ad_break,
        I(T.interview, brief=_HOWTO, target_s=200.0),
        I(T.links, brief=_QUESTION, target_s=80.0),
        I(T.interview, brief=_ACADEMY, target_s=160.0),
        T.ad_break,
        I(T.interview, brief=_HAVE_A_GO, target_s=150.0),
        I(T.links, brief=_WHATSON, target_s=60.0),
        # Wraps to here until the close: a bit of Tegan's and Elis's, a guest's quick five, another bit; new each lap.
        # 90, 140, 90: swept at the rehearsal's lengths (interviews at 0.8 of target, Tegan and Elis's at 1.05) so the
        # half hour ends by seven with the fewest laps: two or three, each guest's quick five once at most.
        I(T.links, brief=_BITS_A, target_s=90.0),
        I(T.interview, brief=_QUICK, target_s=140.0),
        I(T.links, brief=_BITS_B, target_s=90.0),
    ),
    loop_from=11,
    closing=(I(T.links, brief=_CHALLENGE, target_s=80.0),
             # Not told, the rehearsal's goodbye (2026-11-19) said Marina Row was next "at twenty past".
             I(T.links, "close", brief="Tegan and Elis close The Slipway: thanks to tonight's guests, the challenge "
                                       "once more in a line, see you next time, and The Kettle's On is next, at seven",
               target_s=35.0)),
    target_s={T.bumper: 8.0, T.links: 60.0, T.interview: 180.0, T.ad_break: 60.0},
    cast=("slip_a", "slip_b"), lead="slip_a",
    cast_by_type={T.links: ("slip_a", "slip_b"), T.interview: ("slip_a", "slip_b", "guest")},
    station="The Slipway, the teen magazine on Channel 8, Port Wexley's second channel, with Tegan Trevenna and "
            "Elis Pengilly",
    tone="quick, warm and funny: two young presenters who disagree about everything and are on the viewers' side",
    light=True,
    repeats_overnight=False,
)

_RULES = """
This is part of THE SLIPWAY, Channel 8's half-hour magazine for teenagers, from a bright studio with a window
onto the harbour, presented by a double act: Tegan Trevenna ("slip_a"), twenty-one, born in Port Wexley, throws
herself into everything, never reads instructions, finishes nothing, laughs at herself; and Elis Pengilly
("slip_b"), twenty-two, a planner, makes lists, reads the rules out, worries about safety, secretly the more
competitive. They are fond of each other and argue about everything: that is the fun, never a real row. Both speak
in every item, Tegan first. TONIGHT gives the guests. Talk WITH young people, never down to them: no "kids", no
lecturing, no slang that tries too hard. Light, kind and safe: no news stories, no threads (thread_id is null),
nothing grim, nothing from the council, and nothing anyone could get hurt copying (no jumping off the harbour wall,
nothing in the sea without a club and a grown-up who knows it). Tegan and Elis have only the pasts given here: a
story of their own is a small one from school at Greymouth Academy or a first job; never a guest's.
"""

SYSTEMS = {
    T.links: _COMMON_RULES + _RULES + """
These are Tegan's and Elis's words ("slip_a" and "slip_b" only), as THIS ITEM and the PLACE IN THE SHOW say. No guest
speaks. Short lines, back and forth. headline = the point in under 12 words. lower_third = "The Slipway" plus a
short tag.
""",
    T.interview: _COMMON_RULES + _RULES + """
This is Tegan and Elis with ONE GUEST, as THIS ITEM says (the feature guest, the how-to guest or the pupil, by their
exact name from TONIGHT). The guest is speaker "guest", with guest_name their exact name and guest_role their role.
The guest talks more than either presenter; Tegan and Elis each get their own angle in. headline = the guest and the
best of it in under 12 words. lower_third = a short caption.
""",
}

PLACE = {
    (SHOW, T.links): {
        "open": f"PLACE IN THE SHOW: this OPENS {TITLE}: the first words of the programme.",
        "close": f"PLACE IN THE SHOW: this CLOSES {TITLE}: the last words of the programme.",
        "": _MIDDLE.format(title=TITLE, extra=""),
    },
    (SHOW, T.interview): {"": _MIDDLE.format(title=TITLE, extra="")},
}

IDENT = "It's half six, and this is The Slipway! On Channel 8."


# ------------------------------------------------------------------ the booking

class Guest(BaseModel):
    name: str = Field(min_length=3, max_length=40, description="first name and surname")
    role: str = Field(min_length=3, max_length=80, description="who they are in town, in a few words")
    gender: str = Field(default="", max_length=1, description="'f' or 'm'")
    age: str = Field(default="young", max_length=6, description="young or middle")
    about: Annotated[str, _clip_words(200)] = Field(min_length=8, max_length=200,
                                                    description="what they'll show or talk about, in a sentence")


class HowTo(BaseModel):
    what: str = Field(min_length=3, max_length=60, description="the one thing they show how to do")
    name: str = Field(min_length=3, max_length=40, description="who shows it: first name and surname")
    role: str = Field(min_length=3, max_length=80)
    gender: str = Field(default="", max_length=1, description="'f' or 'm'")
    age: str = Field(default="young", max_length=6, description="young or middle")
    steps: Annotated[list[str], creative._first(6)] = Field(
        min_length=3, description="the steps, in order, one short line each: the only way it's done on air")


class Pupil(BaseModel):
    name: str = Field(min_length=3, max_length=40, description="a pupil's first name and surname")
    year: str = Field(min_length=3, max_length=20, description="their year: Year 9 to Year 11, or the sixth form")
    gender: str = Field(default="", max_length=1, description="'f' or 'm'")
    about: Annotated[str, _clip_words(200)] = Field(
        min_length=8, max_length=200, description="the school thing they talk about (a club, the play, a fundraiser), in a sentence")


class SlipwayBooking(BaseModel):
    """Tonight's The Slipway (entertainment/slipway.py)."""
    feature: Guest
    howto: HowTo
    pupil: Pupil
    letters: Annotated[list[str], creative._first(6)] = Field(
        min_length=4, description="viewers' messages: a first name, where from, and what they say, one line each")
    question: str = Field(min_length=8, max_length=140, description="THE BIG QUESTION, a daft one to take sides on")
    whats_on: Annotated[list[str], creative._first(3)] = Field(
        min_length=2, description="things on for young people this week: what, when and where, one line each")
    challenge: str = Field(min_length=8, max_length=160, description="this week's challenge for viewers, safe and free")


_SYSTEM = """\
You book THE SLIPWAY, a half-hour magazine for teenagers on a small-town TV station's second channel, in the
FICTIONAL town in the briefing, presented by Tegan Trevenna and Elis Pengilly. Book tonight's show:
- feature: ONE young person from town (eighteen to thirty) with something to show or tell: a band, a sport, a club
  they started, a small business, a record, a skill. Someone from PEOPLE, or a new resident.
- howto: ONE useful thing a teenager might want to do, shown by someone who knows (eighteen or over): mend a bike
  puncture, cook a cheap tea, write a first CV, look after a houseplant, a basic skateboard move, sew on a button.
  Its steps, in order, three to six short lines: the only way it's done on air. Nothing dangerous.
- pupil: ONE pupil at Greymouth Academy (Year 9 to the sixth form) with something at school to talk about: a club,
  the school play, a fundraiser, a team, a competition. A made-up pupil, never someone in PEOPLE.
- letters: four to six viewers' messages: a first name, where in town or nearby they're from, and what they say (a
  reply to last time's big question, a joke, a tip, a shout-out to a friend). Nothing unkind or private.
- question: THE BIG QUESTION, a daft one to take sides on: is a pasty a meal or a snack, sea swim or pool.
- whats_on: two or three things on for young people this week: what, when and where, from the town's places in
  the briefing. Tonight is {today}: each on a day after tonight.
- challenge: this week's challenge for viewers, safe, free and done at home or in town (learn three knots, find
  five kinds of seaweed on the beach with a grown-up, draw the harbour from memory).
None of RECENT SHOWS again: no feature guest, how-to or pupil from there. Light, kind and safe; everything is
fiction. Return ONLY JSON.
"""


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def tonight(world: World) -> dict | None:
    return next((k for k in reversed(world.slipways) if k.get("date") == world.last_date), None)


def should_commission(world: World, now: float | None = None) -> bool:
    now = now or schedule.now()
    return (tonight(world) is None and _at(BOOK_FROM, now) <= now < _at(AIRS_AT, now) + 20 * 60
            and schedule.show_at(_at(AIRS_AT, now)).id == SHOW)


def _recent(world: World) -> list[dict]:
    since = date.fromordinal(date.fromisoformat(world.last_date).toordinal() - REST_DAYS).isoformat()
    return [k for k in world.slipways if since <= k.get("date", "") < world.last_date]


def _people(world: World) -> list:
    """Young residents the town knows, the most seen first: the feature guest may be one."""
    return sorted((p for p in world.people if p.kind in ("resident", "worthy") and p.age == "young"
                   and not _teen(p.role)), key=lambda p: -p.appearances)[:30]


def _teen(role: str | None) -> bool:
    from newsroom import world as world_mod
    return world_mod.is_teen(role)


def last_challenge(world: World) -> str:
    """The challenge set on the last show before tonight's, for tonight's to say how it went."""
    before = [k for k in world.slipways if k.get("date", "") < world.last_date]
    return before[-1]["challenge"] if before else "to tell us what you'd like to see on The Slipway"


def commission(world: World) -> dict:
    """Book tonight's show (the model, or the stand-in if it fails) and record it."""
    recent = _recent(world)
    day = date.fromisoformat(world.last_date)
    today = f"{day:%A} {day.day} {day:%B}"
    user = (f"BRIEFING\n{world.summary_for_editor()}\n\nPEOPLE (young residents):\n"
            + "\n".join(f"  - {p.name}, {p.role}" for p in _people(world))
            + f"\n\nLAST TIME'S CHALLENGE: {last_challenge(world)}"
            + ("\n\nRECENT SHOWS (none of these again):\n" + "\n".join(
                f"  - the feature {k['feature']['name']}; how to {k['howto']['what']}; Academy Corner "
                f"{k['pupil']['name']}; the big question: {k['question']}" for k in recent) if recent else "")
            + creative.for_planner(world, SHOW))
    try:
        b = llm.complete_json(TASK, SlipwayBooking, _SYSTEM.replace("{today}", today), user)
    except llm.LLMError as e:
        log.warning("slipway: no booking (%s); the stand-in takes tonight", e)
        b = None
    if b and any(b.feature.name == k["feature"]["name"] or b.pupil.name == k["pupil"]["name"]
                 or b.howto.what.lower() == k["howto"]["what"].lower() for k in recent):
        log.warning("slipway: booking repeats a recent show (%s, %s); the stand-in takes tonight", b.feature.name,
                    b.howto.what)
        b = None
    return _record(world, b)


def _record(world: World, b: SlipwayBooking | None) -> dict:
    stand_in = b is None
    b = b or _stand_in(world)
    entry = {"date": world.last_date, "stand_in": stand_in, "last": last_challenge(world), **b.model_dump()}
    _cast(world, entry)
    with world.lock:
        world.slipways = [k for k in world.slipways if k.get("date") != world.last_date] + [entry]
        world.slipways = world.slipways[-30:]
    log.info("slipway: tonight %s (the feature), how to %s with %s, %s at Academy Corner%s", entry["feature"]["name"],
             entry["howto"]["what"], entry["howto"]["name"], entry["pupil"]["name"], " (stand-in)" if stand_in else "")
    return entry


def pupil_role(p: dict) -> str:
    """The pupil's role in the town: a pupil, so a teenager's voice (world.is_teen)."""
    return f"pupil at Greymouth Academy, {p['year']}"


def _cast(world: World, k: dict) -> None:
    """The feature guest, the how-to guest and the pupil join the town's people."""
    f, h, p = k["feature"], k["howto"], k["pupil"]
    for name, role, gender, age in ((f["name"], f["role"], f["gender"], f["age"]),
                                    (h["name"], h["role"], h["gender"], h["age"]),
                                    (p["name"], pupil_role(p), p["gender"], "young")):
        world.ensure_person(name, role, "resident", gender=gender or None, age=age or None, accent="british")


def booked(world: World) -> dict:
    """Tonight's booking; the first item to need it books it, if idle time hasn't."""
    return tonight(world) or commission(world)


_STAND_INS = (
    (("Morwenna Kitto", "founder of the Harbour Slip sailing club's junior section", "f",
      "she started a Saturday club for twelve-year-olds who had never been in a boat"),
     ("mend a bike puncture", "Danny Hocking", "bike repair stall, Harrow Street", "m",
      ["Take the wheel off and let the rest of the air out", "Lever the tyre off with two tyre levers",
       "Find the hole: pump a little air in and listen", "Sand round it, add the glue, wait a minute, press the patch on",
       "Tyre back on with your thumbs, pump it up"]),
     ("Ellie Penrose", "Year 10", "f", "she runs the Academy's new board games club on Thursday lunchtimes"),
     "Is a pasty a meal or a snack?",
     "learn three knots: a reef knot, a figure of eight and a bowline"),
)


def _stand_in(world: World) -> SlipwayBooking:
    rng = random.Random(f"slipway-{world.last_date}")
    (fn, fr, fg, fa), (what, hn, hr, hg, steps), (pn, py, pg, pa), q, ch = rng.choice(_STAND_INS)
    return SlipwayBooking(
        feature={"name": fn, "role": fr, "gender": fg, "age": "young", "about": fa},
        howto={"what": what, "name": hn, "role": hr, "gender": hg, "age": "young", "steps": steps},
        pupil={"name": pn, "year": py, "gender": pg, "about": pa},
        letters=["Jade from Saltby says hello to everyone in her netball team",
                 "Owen from the Salting says a pasty is definitely a meal",
                 "Priya from Harbour Row wants to know if Tegan ever finished last week's challenge",
                 "Sam from Greenhill Road says the best chips are at the kiosk by the slipway"],
        question=q,
        whats_on=["a beach clean on Saturday at ten, meeting at the lifeboat station",
                  "the library's games night on Friday from six"],
        challenge=ch)


# ------------------------------------------------------------------ on air

def guest_for(k: dict, brief: str) -> str | None:
    """Whose interview this is, by its brief: the feature guest's, the how-to guest's or the pupil's."""
    if brief.startswith(("THE FEATURE", "HAVE A GO", "QUICK FIVE, THE FEATURE")):
        return k["feature"]["name"]
    if brief.startswith(("HOW TO", "QUICK FIVE, HOW TO")):
        return k["howto"]["name"]
    if brief.startswith(("ACADEMY CORNER", "QUICK FIVE, ACADEMY")):
        return k["pupil"]["name"]
    return None


def check(seg, script, world: World) -> None:
    """writers.CHECK_HOOKS: an interview's guest is the one its brief books (the Kettle's lesson of 2026-11-19, when a
    spot of the expert's came back as the cook's)."""
    if seg.type is not T.interview:
        return
    want = guest_for(booked(world), seg.brief or "")
    got = (getattr(script, "guest_name", None) or "").strip()
    if want and got.lower() != want.lower():
        raise llm.AskAgain(f"THIS ITEM is {want}'s, so the guest is {want} (guest_name \"{want}\"), not "
                           f"{got or 'nobody'}: write THIS ITEM as it says, with them")


def caption(world: World, name: str) -> str | None:
    """The guest's caption tonight."""
    k = tonight(world)
    if not k:
        return None
    if name == k["howto"]["name"]:
        return f"How to: {k['howto']['what']}"[:60]
    if name == k["pupil"]["name"]:
        return f"Greymouth Academy, {k['pupil']['year']}"[:60]
    return None


def brief_for(world: World, brief: str) -> str:
    """A brief's tokens from tonight's booking."""
    k = booked(world)

    def part(m: re.Match) -> str:
        tok = m.group(1)
        if tok == "feature":
            f = k["feature"]
            return f"{f['name']}, {f['role']}: {f['about']}"
        if tok == "howto":
            h = k["howto"]
            return f"{h['name']}, {h['role']}, on how to {h['what']}"
        if tok == "steps":
            return "; ".join(f"{i}. {s}" for i, s in enumerate(k["howto"]["steps"], 1))
        if tok == "pupil":
            p = k["pupil"]
            return f"{p['name']}, {p['year']} at Greymouth Academy: {p['about']}"
        if tok == "letters":
            return "; ".join(k["letters"][:3])
        if tok == "more":
            rest = k["letters"][3:]
            return "; ".join(rest) if rest else "two more of their own choosing, as viewers would write them"
        if tok == "question":
            return k["question"]
        if tok == "whatson":
            return "; ".join(k["whats_on"])
        if tok == "challenge":
            return k["challenge"]
        return k.get("last") or last_challenge(world)
    return TOKEN.sub(part, brief or "")


def for_prompt(world: World) -> str:
    """Tonight's booking for every item, with what has been on so far."""
    k = booked(world)
    with world.lock:
        aired = [a for a in world.archive if a["date"] == world.last_date and a.get("show") == SHOW
                 and a["type"] != T.ad_break.value]
    f, h, p = k["feature"], k["howto"], k["pupil"]
    out = (f"TONIGHT: the feature, {f['name']}, {f['role']}; how to {h['what']} with {h['name']}, {h['role']}; "
           f"Academy Corner, {p['name']} ({p['year']}). Each guest is in the studio only for their own items: in any "
           "other item nobody talks to them or as if they were there.")
    if aired:
        out += ("\nSO FAR TONIGHT (don't do these again):\n" + "\n".join(
            f"  - {a['type'].replace('_', ' ')}: {a['headline']}: {a['text'][:SO_FAR_CHARS]}" for a in aired[-10:]))
    return out


def digest(world: World, day: str) -> str:
    """The show booked for `day`, as the creative editor reads it after it has aired; "" for none or the stand-in."""
    k = next((x for x in world.slipways if x.get("date") == day), None)
    if not k or k.get("stand_in"):
        return ""
    f, h, p = k["feature"], k["howto"], k["pupil"]
    return (f"The feature: {f['name']}, {f['role']}: {f['about']}\n"
            f"How to {h['what']} with {h['name']}: {'; '.join(h['steps'])}\n"
            f"Academy Corner: {p['name']}, {p['year']}: {p['about']}\n"
            f"The messages: {'; '.join(k['letters'])}\nThe big question: {k['question']}\n"
            f"What's on: {'; '.join(k['whats_on'])}\nThe challenge: {k['challenge']} (last time's: {k.get('last')})")


def enrol():
    """Enrol the show with the creative editor: notes after air, for the next booking. Returns an undo."""
    return creative.register(
        SHOW, TITLE, kind="light", airs_at=AIRS_AT,
        brief=("A half-hour magazine for teenagers: Tegan Trevenna, who throws herself into everything and finishes "
               "nothing, and Elis Pengilly, who plans and reads the rules. A young person from town with something to "
               "show (and Tegan having a go at it), a how-to, a pupil from Greymouth Academy, viewers' messages, a "
               "daft big question, what's on, and a weekly challenge. Never news; talks with teenagers, not down to "
               "them. The pair's ways clash, warmly: that is the show."),
        decides=("tonight's feature guest and what they show; the how-to and its steps; the pupil and their school "
                 "thing; the viewers' messages; the big question; what's on; the challenge. Not the presenters' lines "
                 "or how the half hour runs"),
        digest=digest, books=should_commission)


# ------------------------------------------------------------------ with no model

def template(seg_type, world, rng: random.Random, part: str, work: dict, brief: str):
    """The Slipway with no model: still tonight's guests, from the booking."""
    from newsroom.models import BulletinScript, GuestLine, InterviewScript, LiveLine

    k = booked(world)
    f, h, p = k["feature"], k["howto"], k["pupil"]
    if seg_type is T.links:
        if part == "open":
            said = [("slip_a", "Hiya! This is The Slipway."), ("slip_b", f"Tonight: {f['name']}, and how to {h['what']}."),
                    ("slip_a", "And Academy Corner. Let's go!")]
        elif part == "close":
            said = [("slip_a", "That's it from us!"), ("slip_b", f"This week's challenge: {k['challenge']}."),
                    ("slip_a", "See you next time!")]
        elif brief.startswith("THE CHALLENGE"):
            said = [("slip_b", f"Last time's challenge was {k.get('last')}."), ("slip_a", "I nearly finished it."),
                    ("slip_b", f"This week: {k['challenge']}."), ("slip_a", "I'll definitely finish this one.")]
        else:
            said = [("slip_a", "Elis, I've had an idea."), ("slip_b", "Have you read the rules?"),
                    ("slip_a", "There are rules?"), ("slip_b", "There are always rules.")]
        return BulletinScript(lines=[LiveLine(speaker=w, text=t) for w, t in said],
                              headline=f"{TITLE}", lower_third=TITLE)
    if seg_type is not T.interview:
        return None
    who = guest_for(k, brief) or f["name"]
    role = (h["role"] if who == h["name"] else pupil_role(p) if who == p["name"] else f["role"])[:60]
    about = h["what"] if who == h["name"] else p["about"] if who == p["name"] else f["about"]
    said = [("slip_a", f"{who.split()[0]}, welcome to The Slipway!"),
            ("guest", f"Thanks for having me. It's about {about}."),
            ("slip_b", "And how would someone start?"),
            ("guest", "Just have a go. Everyone's rubbish at first."),
            ("slip_a", "That's my kind of answer.")]
    return InterviewScript(lines=[GuestLine(speaker=w, text=t) for w, t in said],
                           headline=f"{who} on The Slipway", lower_third=TITLE, guest_name=who, guest_role=role)
