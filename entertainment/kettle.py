"""The Kettle's On: Channel 8's teatime magazine, 19:00 to 20:00 (docs/ENGINE.md; agreed with the user 2026-11-13).

A homely forty minutes from a studio kitchen with a sofa corner, presented by a double act whose ways clash in the
kitchen (Coastwide's Pat and Clive showed that clashing pairs are the most watchable thing on air):
Maggie Truscott ("kettle_a"), thirty years running the Cannery café's kitchen, who measures nothing, and Nigel
Spargo ("kettle_b"), a retired chemistry teacher who weighs everything to the gram.

Each night a local cook makes one dish at the counter (in two parts: it goes in, it comes out), one of four
experts takes the phone-in (the garden, pets, what's it worth, mending: in turn, a different one each Channel 8
night), a guest on the sofa has a nice story, and the community noticeboard is read out. All of it is booked
by one back-office call from BOOK_FROM (The Chamber's route unless config.toml gives "kettle" its own), recorded
in `world.kettles`, and handed to every item; if the call fails, a stand-in booking is made in code. The calls
reuse Have Your Say's `call` item: the caller is cast and remembered like any, and the expert answers them.

Light: no news, no threads. Fictional, like the town; the experts and cooks become its residents.
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

SHOW = "kettle"
TITLE = "The Kettle's On"
AIRS_AT = "19:00"
BOOK_FROM = "17:00"
CALLED = f"{TITLE}, on the phone"       # how a caller's memory names the show
NUMBER = "oh one six three two, nine six oh, eight eight eight"   # the drama range: no real line
TASK = "kettle" if "kettle" in CONFIG.llm.routes else "chamber"
REST_DAYS = 28                          # a dish, a cook or a sofa guest isn't booked again within this
SO_FAR_CHARS = 200
TOKEN = re.compile(r"\{(cook|dish|sofa|expert|says|question|notices|caller)\}")
CALLS_ASKED = 24                        # problems the booking is asked for, one a call: the hour took nineteen
CALLS_KEPT = 30

# The phone-in's experts, one a night in turn; each joins the town as a resident the first time.
EXPERTS = (
    {"topic": "the garden", "name": "Lowenna Chenoweth", "role": "allotment secretary at the Salting, our gardening expert",
     "gender": "f", "age": "old", "says": "forty years on the same allotment; plain-spoken, swears by seaweed"},
    {"topic": "pets", "name": "Sam Lander", "role": "vet on Harrow Street, our pets expert",
     "gender": "m", "age": "middle", "says": "calm and kind; has seen every swallowed sock in town"},
    {"topic": "what's it worth", "name": "Ruth Greet", "role": "valuer at the Port Wexley saleroom",
     "gender": "f", "age": "middle", "says": "brisk, dry, and honest when the heirloom is worth a fiver"},
    {"topic": "fixing and mending", "name": "Stan Coombe", "role": "retired joiner, our mending expert",
     "gender": "m", "age": "old", "says": "can fix anything with a screwdriver and patience; hates waste"},
)

# What a call can be about when the booking has no problem left for it, by the expert's topic: each used once a
# night, and never one the booking has already had a call on. On the first night on air (2026-11-14) the booking
# gave five kinds of caller and the hour took nineteen calls: waterlogged clay rang three times and leeks four.
THINGS = {
    "the garden": (
        "roses that want pruning", "bare patches in a lawn", "a hedge that has got away", "houseplants by a radiator",
        "slugs and snails", "an old apple tree", "spring bulbs still in the bag", "a small pond", "herbs on a windowsill",
        "raspberry canes", "seed potatoes", "hanging baskets", "a neighbour's overhanging tree", "a hedgehog in the "
        "garden", "rusty tools", "a new-build plot full of rubble", "a north-facing yard", "seeds saved from last year",
        "ivy on a wall", "cats digging in the beds", "tomatoes for next year", "a wind-blown seaside border"),
    "pets": (
        "a dog that pulls on the lead", "a cat scratching the furniture", "a rabbit off its food", "a budgie that has "
        "stopped singing", "a puppy chewing shoes", "an old dog stiff in the mornings", "a cat that won't use the flap",
        "a hamster awake all night", "a tortoise and the winter", "a dog frightened of fireworks", "goldfish in a "
        "cloudy tank", "two cats that don't get on", "a spaniel that bolts its dinner", "a kitten and a new baby",
        "guinea pigs in the cold", "a parrot that swears", "a collie scared of the car", "fleas that keep coming back",
        "a tabby getting fat", "hens in the back garden", "a terrier that barks at the postman", "a rescue greyhound "
        "settling in"),
    "what's it worth": (
        "a grandfather's pocket watch", "a box of old postcards", "a ship in a bottle", "a set of fish knives",
        "a brass ship's lamp", "a tin toy car", "a great-aunt's brooch", "an old sewing machine", "a painting of the "
        "harbour", "an early children's book", "a tea set with one cup missing", "a medal from the war", "a barometer",
        "a doll with a china face", "a chest of drawers from a house clearance", "a stamp album", "a silver "
        "christening spoon", "an old football programme", "a wind-up gramophone", "an enamel cannery sign", "a pair "
        "of vases", "a sailor's sea chest"),
    "fixing and mending": (
        "a wobbly chair", "a sticking door", "a dripping tap", "a zip that has gone", "a cracked teapot", "a squeaky "
        "stair", "a drawer that won't run", "a lamp that flickers", "a bicycle puncture", "a torn deckchair",
        "a wardrobe door off its hinge", "a garden gate that drags", "blunt shears", "a rocking horse", "a leaking "
        "welly", "a picture frame with a split corner", "a clock that stops", "a broken umbrella", "a stool with a "
        "split seat", "a loose saucepan handle", "a draughty sash window", "a radio that crackles"),
}


# ------------------------------------------------------------------ the show

_RECIPE_1 = ("THE RECIPE, part one: {cook} at the counter with Maggie and Nigel, making {dish}: why this dish, "
             "the ingredients, and the first steps until it goes in the oven or the pan. Maggie throws things in by "
             "eye, Nigel wants the weights; the cook settles it")
# Written while part one is still on air, so it can't see it: on the first scratch run (2026-11-13) part two
# opened with part one's first line and went through the ingredients again.
_RECIPE_2 = ("THE RECIPE, part two, after the break: part one has already done the ingredients and the method, so "
             "none of that again: it starts with {dish} coming out of the oven or from under the grill. {cook} "
             "finishes it and serves up; Maggie and Nigel taste it and give their verdicts (Nigel's is precise, "
             "Maggie's is a noise of joy); the cook's tip for doing it at home")
_SOFA = ("ON THE SOFA: {sofa}. Maggie and Nigel chat with them about it, with a cup of tea: warm and a bit nosy, "
         "the details people like")
# The expert's way of talking ({says}) is given here and nowhere else: in every expert item's brief it was said in
# every item, and Lowenna pushed seaweed in nine spots out of ten (2026-11-14).
_EXPERT = ("THE EXPERT on the sofa before the phones open: {expert} ({says}), on tonight's phone-in, {question}: one "
           "good tip for the time of year, and Nigel asks the question everyone's too embarrassed to ask")
_NOTICES = ("THE NOTICEBOARD: Maggie and Nigel read out the community notices: {notices}. A line on each, with "
            "when and where; they bicker gently about which one they're going to")
# The loop's expert item, a different angle each lap (Show.item): with one brief, the second scratch run's hour
# (2026-11-13) had Lowenna on "frosted dahlias, rhubarb and seaweed" five times. Ten, for the nine laps an hour
# takes: with six, the first night on air (2026-11-14) had the postbag and Myth or True twice each.
_POSTBAG = tuple(b + ", nothing the expert has already said tonight, and nothing a caller has asked" for b in (
    "THE POSTBAG: {expert} answers two letters that came in on tonight's subject, with Maggie and Nigel",
    "MYTH OR TRUE: Nigel reads out three things people swear by in the expert's field, and {expert} says which "
    "are true and why",
    "THIS WEEKEND: {expert} gives three jobs for the weekend in the expert's field, with the weather in mind; "
    "Maggie promises to do one of them",
    "MAGGIE'S DISASTER: Maggie owns up to a disaster of her own in the expert's field, {expert} explains what went "
    "wrong, and Nigel takes notes",
    "THE ONE THING: {expert}, Maggie and Nigel each name the one thing every home should have for it, and argue",
    "QUICK-FIRE: Nigel puts five quick questions from the postbag to {expert}, a line or two each",
    "WHAT IS IT?: Maggie holds up something a viewer has sent in from the expert's field and says what it looks "
    "like; {expert} says what it is and what to do about it, and Nigel guesses wrong first",
    "THEN AND NOW: {expert} on how one job in the expert's field was done when they started out and how it is done "
    "now; Maggie is for the old way, Nigel for the new",
    "A VIEWER'S TRIUMPH: Maggie reads a letter from a viewer for whom something went right in the expert's field, "
    "and {expert} says why it worked and how anyone could do the same",
    "NIGEL'S EXPERIMENT: Nigel reports a careful test he ran at home in the expert's field, with his figures; "
    "{expert} says what he got right and the one thing he missed",
))

SHOW_DEF = Show(
    SHOW, "THE KETTLE'S ON", "KETTLE'S ON", (214, 120, 70),
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Maggie and Nigel open The Kettle's On: a cosy good evening from the kitchen, "
                                 "tonight's dish and cook, tonight's sofa guest, and the expert on the phones",
          target_s=50.0),
        I(T.interview, brief=_RECIPE_1, target_s=200.0),
        I(T.interview, brief=_EXPERT, target_s=110.0),
        I(T.call, brief="{caller}"),
        I(T.call, brief="{caller}"),
        T.ad_break,
        I(T.interview, brief=_SOFA, target_s=220.0),
        I(T.links, brief=_NOTICES, target_s=60.0),
        I(T.interview, brief=_RECIPE_2, target_s=160.0),
        # Wraps to here until the close: more calls, and the postbag.
        I(T.call, brief="{caller}"),
        I(T.call, brief="{caller}"),
        T.ad_break,
        I(T.interview, brief=_POSTBAG, target_s=120.0),
    ),
    loop_from=10,
    closing=(I(T.links, "close", brief="Maggie and Nigel close The Kettle's On: what's left of the dish, thanks to "
                                       "the cook, the sofa guest and the expert, the number for next time's phone-in, "
                                       "and a cosy goodnight", target_s=40.0),),
    target_s={T.bumper: 8.0, T.links: 50.0, T.interview: 180.0, T.call: 120.0, T.ad_break: 60.0},
    cast=("kettle_a", "kettle_b"), lead="kettle_a",
    cast_by_type={T.links: ("kettle_a", "kettle_b"), T.interview: ("kettle_a", "kettle_b", "guest"),
                  T.call: ("kettle_a", "kettle_b", "guest")},
    station="The Kettle's On, the teatime magazine on Channel 8, Port Wexley's second channel, with Maggie Truscott "
            "and Nigel Spargo",
    tone="homely, warm and gently funny: a kitchen full of chat, Maggie's instinct against Nigel's method",
    light=True,
    repeats_overnight=False,
)

# Its own set (a studio kitchen with a sofa corner) waits for art the user approves; until then the breakfast
# sofa stands in: Maggie and Nigel on the sofa, the guest in the chair (scenes._interview_marks seats the
# first presenter to speak at "host", then "panel_1", "panel_2", so the prompt has Maggie speak first).
STAND_IN_SET = "studio_sofa"
SET = "studio_kettle"
MARKS = {"host": (122, 146, 2, 1), "panel_1": (186, 146, 2, -1), "panel_2": (272, 150, 2, -1)}

_RULES = """
This is part of THE KETTLE'S ON, a homely teatime magazine from a studio kitchen with a sofa corner,
presented by a double act: Maggie Truscott ("kettle_a"), thirty years in the Cannery café's kitchen,
generous and chaotic, measures nothing, feeds everyone, laughs at her own disasters; and Nigel Spargo
("kettle_b"), a retired chemistry teacher, precise and fussy, weighs everything to the gram, worries
about oven temperatures, and secretly can't cook. They are fond of each other and disagree about
everything in the kitchen: that is the fun, never a real row. TONIGHT gives the cook, the dish, the
sofa guest, the expert and tonight's phone-in. Both presenters speak in every item, Maggie first.
Light: no news stories, no threads (thread_id is null), nothing grim. Cooking is real cooking: real
ingredients, real quantities, real times and temperatures, said the way a cook says them.
"""

SYSTEMS = {
    T.links: _COMMON_RULES + _RULES + """
These are Maggie's and Nigel's words TO CAMERA ("kettle_a" and "kettle_b" only), as THIS ITEM and the
PLACE IN THE SHOW say. No guest speaks. Short lines, back and forth. When you give the phone-in number,
say it as written. headline = the point in under 12 words. lower_third = "The Kettle's On" plus a short tag.
""",
    T.interview: _COMMON_RULES + _RULES + """
This is Maggie and Nigel with ONE GUEST, as THIS ITEM says (the cook, the sofa guest or the expert, by
their exact name from TONIGHT). The guest is speaker "guest", with guest_name their exact name and
guest_role their role. The guest talks more than either presenter; Maggie and Nigel each get their
own angle in. headline = the guest and the best of it in under 12 words. lower_third = a short caption.
""",
    T.call: _COMMON_RULES + _RULES + """
This is ONE CALL to tonight's phone-in with the expert. The presenter THIS ITEM names brings the caller
in, with their first name and where they're ringing from, in their own words (never the way another call
began). The caller is speaker "guest" with guest_name null on their lines; name them once in caller_name
(first name and surname), with caller_from, caller_gender, caller_age and caller_accent. They ask the
expert about their own problem on tonight's subject, in their own words, with a detail from their own
life. THE EXPERT answers, not the presenters: every line the expert says is speaker "guest" with
guest_name the expert's exact name (never null: a null "guest" line is the caller's), practical and
specific. The other presenter chips in once (Nigel with a precise follow-up, Maggie with a story of her own). Be THIS CALLER, not
someone who has rung already. A real voice: chatty, nervous or funny, not a speech. End with thanks.
caller_memory: one line on what they asked. thread_id is null. No viewer tips: tip_used is null.
headline = the caller and their problem in under 12 words. lower_third = "The Kettle's On" plus the problem, short.
""",
}

PLACE = {
    (SHOW, T.links): {
        "open": f"PLACE IN THE SHOW: this OPENS {TITLE}: the first words of the programme.",
        "close": f"PLACE IN THE SHOW: this CLOSES {TITLE}: the last words of the programme.",
        "": _MIDDLE.format(title=TITLE, extra=""),
    },
    (SHOW, T.interview): {"": _MIDDLE.format(title=TITLE, extra="")},
    (SHOW, T.call): {"": _MIDDLE.format(title=TITLE, extra="")},
}

IDENT = "It's teatime, and The Kettle's On! On Channel 8."



# ------------------------------------------------------------------ the booking

class Dish(BaseModel):
    dish: str = Field(min_length=3, max_length=60, description="the dish, as a cook would name it")
    cook: str = Field(min_length=3, max_length=40, description="the cook's first name and surname")
    cook_role: str = Field(min_length=3, max_length=80,
                           description="who they are: where they cook in town (a café, a pub kitchen, a bakery, home)")
    cook_gender: str = Field(default="", max_length=1, description="'f' or 'm'")
    cook_age: str = Field(default="", max_length=6, description="young, middle or old")
    why: Annotated[str, _clip_words(160)] = Field(      # cut, not failed: a long one cost a second call (2026-11-14)
        min_length=3, max_length=160, description="why this dish tonight: the season, a story, a family recipe")


class Sofa(BaseModel):
    name: str = Field(min_length=3, max_length=40, description="first name and surname")
    role: str = Field(min_length=3, max_length=80)
    gender: str = Field(default="", max_length=1, description="'f' or 'm'")
    age: str = Field(default="", max_length=6, description="young, middle or old")
    about: Annotated[str, _clip_words(200)] = Field(     # cut, not failed: a long one cost a second call (2026-11-14)
        min_length=8, max_length=200, description="their nice story, in a sentence")


class KettleBooking(BaseModel):
    """Tonight's The Kettle's On (entertainment/kettle.py)."""
    dish: Dish
    sofa: Sofa
    question: str = Field(min_length=8, max_length=120,
                          description="tonight's phone-in subject in the expert's field, as Maggie would put it")
    # One problem a call, each used once (brief_for). A short list is not failed (that would cost the cook and the
    # sofa guest too): the calls past it take a spare subject from THINGS. A long one is cut.
    callers: Annotated[list[str], creative._first(CALLS_KEPT)] = Field(
        min_length=4, description=f"about {CALLS_ASKED} callers' problems, one line each, in the order they ring: each "
                                  "about a different plant, animal or object and a different trouble; never a name")
    notices: list[str] = Field(min_length=3, max_length=4,
                               description="community notices: what, when and where, one line each")


_SYSTEM = """\
You book THE KETTLE'S ON, a homely teatime magazine on a small-town TV station's second channel, in the
FICTIONAL town in the briefing, presented by Maggie Truscott and Nigel Spargo from a studio kitchen.
Book tonight's show:
- dish: ONE dish a local cook makes at the counter in about ten minutes of television: real food with
  real ingredients, suited to the season (it is {month}), homely more than fancy. The cook is from town:
  someone in PEOPLE who cooks (a café, a pub kitchen, a bakery), or a new resident with a cook's job; why
  this dish tonight in a line.
- sofa: ONE guest with a nice story, never news: a long marriage, a record, a rescue, a hobby, a reunion,
  a first. Someone from PEOPLE, or a new resident.
- question: tonight's phone-in in THE EXPERT's field, as Maggie would put it to viewers, right for the
  time of year, and wide enough for a whole evening of different problems (the field in this season,
  not one worry within it).
- callers: {calls} callers' problems, one line each, in the order they ring. The hour takes about twenty
  calls and each line is one call, used once, so no two may be alike: each about a different plant,
  animal or object, and a different trouble (never two on the same vegetable, the same weather or the
  same cure; at most three touching the season's big worry). The caller and their problem as a
  description, never a name: "someone whose bay tree in a pot has gone brown on one side".
- notices: three or four community notices: a jumble sale, a choir wanting tenors, a lost cat, a coffee
  morning, a talk at the library; what, when and where, from the town's places in the briefing.
None of RECENT SHOWS again: no dish, cook or sofa guest from there. Everything is fiction. Return ONLY JSON.
"""


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def tonight(world: World) -> dict | None:
    return next((k for k in reversed(world.kettles) if k.get("date") == world.last_date), None)


def should_commission(world: World, now: float | None = None) -> bool:
    now = now or schedule.now()
    return (tonight(world) is None and _at(BOOK_FROM, now) <= now < _at(AIRS_AT, now) + 30 * 60
            and schedule.show_at(_at(AIRS_AT, now)).id == SHOW)


def expert(world: World) -> dict:
    """Tonight's expert: the next in turn after the last show's."""
    before = [k for k in world.kettles if k.get("date") != world.last_date]
    last = before[-1].get("expert", {}).get("name") if before else None
    i = next((n for n, e in enumerate(EXPERTS) if e["name"] == last), -1)
    return EXPERTS[(i + 1) % len(EXPERTS)]


def _recent(world: World) -> list[dict]:
    since = date.fromordinal(date.fromisoformat(world.last_date).toordinal() - REST_DAYS).isoformat()
    return [k for k in world.kettles if since <= k.get("date", "") < world.last_date]


def _people(world: World) -> list:
    """Residents and worthies the town knows, the most seen first: the cook and the sofa guest may be one."""
    return sorted((p for p in world.people if p.kind in ("resident", "worthy")),
                  key=lambda p: -p.appearances)[:40]


def commission(world: World) -> dict:
    """Book tonight's show (the model, or the stand-in if it fails) and record it."""
    ex = expert(world)
    recent = _recent(world)
    month = date.fromisoformat(world.last_date).strftime("%B")
    user = (f"BRIEFING\n{world.summary_for_editor()}\n\nPEOPLE:\n"
            + "\n".join(f"  - {p.name}, {p.role}" for p in _people(world))
            + f"\n\nTHE EXPERT tonight: {ex['name']}, {ex['role']} ({ex['topic']})."
            + ("\n\nRECENT SHOWS (none of these again):\n" + "\n".join(
                f"  - {k['dish']['dish']} by {k['dish']['cook']}; on the sofa {k['sofa']['name']}; the phones: "
                f"{k['question']}" for k in recent) if recent else "")
            + creative.for_planner(world, SHOW))
    try:
        b = llm.complete_json(TASK, KettleBooking,
                              _SYSTEM.replace("{month}", month).replace("{calls}", str(CALLS_ASKED)), user)
    except llm.LLMError as e:
        log.warning("kettle: no booking (%s); the stand-in takes tonight", e)
        b = None
    if b and any(b.dish.dish.lower() == k["dish"]["dish"].lower() or b.sofa.name == k["sofa"]["name"]
                 for k in recent):
        log.warning("kettle: booking repeats a recent show (%s, %s); the stand-in takes tonight",
                    b.dish.dish, b.sofa.name)
        b = None
    return _record(world, ex, b)


def digest(world: World, day: str) -> str:
    """The show booked for `day`, as the creative editor reads it after it has aired; "" for none or the stand-in."""
    k = next((x for x in world.kettles if x.get("date") == day), None)
    if not k or k.get("stand_in"):
        return ""
    d, s, ex = k["dish"], k["sofa"], k.get("expert") or {}
    callers = k.get("callers") or []
    return (f"The recipe: {d['dish']} by {d['cook']}, {d['cook_role']} ({d.get('why', '')}).\n"
            f"The sofa: {s['name']}, {s['role']}: {s['about']}\n"
            f"The phones, with {ex.get('name', 'the expert')} on {ex.get('topic', 'their subject')} (in turn, not "
            f"the booking's choice): {k['question']} The booking gave {len(callers)} callers' problems, one a call, "
            f"and {k.get('calls', 0)} calls were taken; the first eight: {'; '.join(callers[:8])}\n"
            f"The noticeboard: {'; '.join(k.get('notices') or [])}")


def enrol():
    """Enrol the show with the creative editor: notes after air, for the next booking. Returns an undo."""
    return creative.register(
        SHOW, TITLE, kind="light", airs_at=AIRS_AT,
        brief=("A homely teatime magazine, an hour from a studio kitchen: Maggie Truscott, the Cannery café's cook, who "
               "measures nothing, and Nigel Spargo, a retired chemistry teacher, who weighs everything. A local cook's "
               "recipe in two parts, a sofa guest with a nice story, an expert taking viewers' calls, the noticeboard. "
               "Never news. The pair's ways clash, warmly: that is the show."),
        decides=("tonight's dish and its cook; the sofa guest and their story; the phone-in's subject and every "
                 "caller's problem (one a call, about twenty, no two alike); the community notices. Not the "
                 "presenters' lines, the expert (in turn) or how the hour runs"),
        digest=digest, books=should_commission)


# How a call begins, in turn: calls written side by side, before any of them airs, all began "the phones are open
# and we've got someone on the line already" on the second scratch run (2026-11-13).
WAYS_IN = (
    "reading the caller's name and street off the note in front of them",
    "straight in with the caller's problem, before the caller has said a word",
    "apologising to the caller for keeping them waiting while the other one talked",
    "after a quick word to the expert about the last call",
    "with the caller already halfway through saying hello",
)

_STAND_IN_DISHES = (
    ("a proper fish pie", "it's the season for it, and the boats had a good week"),
    ("saffron buns", "her grandmother's recipe, baked every winter"),
    ("a leek and potato soup", "cheap, warming and done in half an hour"),
    ("an apple and blackberry crumble", "the last of the hedgerow blackberries from the freezer"),
    ("a pasty, crimped the old way", "the crimp is a family argument"),
)
_STAND_IN_CALLERS = (
    "someone who has tried everything and nothing works",
    "a beginner who isn't sure where to start",
    "someone who thinks they have found a clever shortcut",
    "an older viewer who remembers how it used to be done",
    "someone ringing for a relative who is too shy to ring",
)


def _stand_in(world: World, ex: dict) -> KettleBooking:
    rng = random.Random(f"kettle-{world.last_date}")
    dish, why = rng.choice(_STAND_IN_DISHES)
    things = rng.sample(THINGS.get(ex["topic"], ()), k=len(THINGS.get(ex["topic"], ())))
    # A kind of caller and a thing of their own each, so the stand-in's calls differ too; with no list for the
    # topic, the kinds alone, as before.
    callers = ([f"{_STAND_IN_CALLERS[i % len(_STAND_IN_CALLERS)]}, about {t}" for i, t in enumerate(things)]
               or list(_STAND_IN_CALLERS))
    return KettleBooking(
        dish=Dish(dish=dish, cook="Jean Truscott", cook_role="Maggie's sister-in-law, a home cook in the Salting",
                  cook_gender="f", cook_age="old", why=why),
        sofa=Sofa(name="Bill Lander", role="retired harbour pilot", gender="m", age="old",
                  about="fifty years married this week, and he still brings his wife tea in bed"),
        question=f"Your questions on {ex['topic']}",
        callers=callers,
        notices=["a coffee morning at the village hall on Saturday at ten, in aid of the lifeboat",
                 "the Harbour Choir is looking for tenors: rehearsals on Tuesdays at seven at the chapel",
                 "a tabby cat called Pickle is missing from Harrow Street: answers to the sound of a tin opener"])


def _record(world: World, ex: dict, b: KettleBooking | None) -> dict:
    stand_in = b is None
    b = b or _stand_in(world, ex)
    entry = {"date": world.last_date, "expert": ex, "stand_in": stand_in, "calls": 0, **b.model_dump()}
    _cast(world, entry)
    with world.lock:
        world.kettles = [k for k in world.kettles if k.get("date") != world.last_date] + [entry]
        world.kettles = world.kettles[-30:]
    log.info("kettle: tonight %s by %s, %s on the sofa, %s on the phones%s", entry["dish"]["dish"],
             entry["dish"]["cook"], entry["sofa"]["name"], ex["name"], " (stand-in)" if stand_in else "")
    return entry


def _cast(world: World, k: dict) -> None:
    """The cook, the sofa guest and the expert join the town's people (their voices and looks stay theirs)."""
    d, s, e = k["dish"], k["sofa"], k["expert"]
    for name, role, gender, age in ((d["cook"], d["cook_role"], d["cook_gender"], d["cook_age"]),
                                    (s["name"], s["role"], s["gender"], s["age"]),
                                    (e["name"], e["role"], e["gender"], e["age"])):
        world.ensure_person(name, role, "resident", gender=gender or None, age=age or None, accent="british")


def studio(world: World) -> str:
    """The guest in the studio during a call: tonight's expert (writers.STUDIO_HOOKS)."""
    return booked(world)["expert"]["name"]


def booked(world: World) -> dict:
    """Tonight's booking; the first item to need it books it, if idle time hasn't."""
    return tonight(world) or commission(world)


def caption(world: World, name: str) -> str | None:
    """The guest's caption tonight: the cook by their kitchen, the expert by their field."""
    k = tonight(world)
    if not k:
        return None
    if name == k["dish"]["cook"]:
        return f"Tonight's cook: {k['dish']['dish']}"[:60]
    if name == k["expert"]["name"]:
        return f"Our expert: {k['expert']['topic']}"[:60]
    return None


def brief_for(world: World, brief: str) -> str:
    """A brief's tokens from tonight's booking; "{caller}" takes the next call's problem (`problem`)."""
    k = booked(world)

    def part(m: re.Match) -> str:
        tok = m.group(1)
        if tok == "cook":
            return f"{k['dish']['cook']} ({k['dish']['cook_role']})"
        if tok == "dish":
            return f"{k['dish']['dish']} ({k['dish']['why']})"
        if tok == "sofa":
            s = k["sofa"]
            return f"{s['name']}, {s['role']}: {s['about']}"
        if tok == "expert":
            return f"{k['expert']['name']}, {k['expert']['role']}"
        if tok == "says":
            return k["expert"]["says"]
        if tok == "question":
            return f"\"{k['question']}\""
        if tok == "notices":
            return "; ".join(k["notices"])
        with world.lock:                                      # the caller: the next kind in turn
            n = k["calls"]
            k["calls"] = n + 1
        host = ("Maggie", "Nigel")[n % 2]                     # in turn: two calls began alike on the first run
        # The problem in a sentence of its own, labelled: joined to the way in by a colon, "after a quick word to
        # the expert about the last call: a caller whose compost heap has gone slimy" was read as the last call's
        # problem, and the writer made up this caller's (leeks, four times on 2026-11-14).
        return (f"ONE CALL to the phone-in (call {n + 1} tonight). {host} takes it, {WAYS_IN[n % len(WAYS_IN)]}. "
                f"THIS CALLER'S PROBLEM, the only one they ring about and the whole of the call: {problem(k, n)}. "
                "Keep to it: not another plant, pet or thing, and nothing from PROBLEMS ON THE PHONES ALREADY TONIGHT")
    return TOKEN.sub(part, brief or "")


_DULL = {"about", "their", "there", "which", "where", "whose", "garden", "thing", "something", "someone", "caller",
         "want", "would", "could", "should", "still", "never", "every", "after", "before", "tonight", "winter",
         "that", "with", "from", "have", "next", "year", "last", "full", "keep", "gone", "away", "over", "into",
         "what", "when", "they", "them", "this", "been", "will", "doe", "back", "viewer", "question", "morning",
         "night", "cold", "small", "that'", "won't", "don't", "want", "getting", "come", "coming", "home", "house",
         "back", "side", "time", "each", "only", "just", "more", "some", "know", "whether", "always"}


def _words(text: str) -> set[str]:
    """The telling words of a problem: four letters or more, a plural as its singular, the dull ones left out."""
    return {w for w in (x.rstrip("s") for x in re.findall(r"[a-z']{4,}", text.lower())) if len(w) >= 3} - _DULL


def spares(k: dict) -> list[str]:
    """The expert's spare subjects the booking hasn't already had a call on (a telling word in common counts as
    had: "slugs and snails" is no spare on a night with slugs on the hostas)."""
    had = _words(" ".join(k.get("callers") or []))
    return [t for t in THINGS.get((k.get("expert") or {}).get("topic"), ()) if not _words(t) & had]


def problem(k: dict, n: int) -> str:
    """What tonight's call number `n` (from 0) is about: the booking's problems in order, each once; then the
    expert's spare subjects, each once; only then round again."""
    booked = k.get("callers") or []
    if n < len(booked):
        return booked[n]
    spare = spares(k)
    if spare:
        m = n - len(booked)
        return (f"a viewer with a question about {spare[m % len(spare)]}"
                + (" (asked about tonight already: this caller's trouble with it is a different one)"
                   if m >= len(spare) else ""))
    return booked[n % len(booked)] if booked else "a viewer with a question for the expert"


def for_prompt(world: World) -> str:
    """Tonight's booking for every item, with what has been on so far."""
    k = booked(world)
    e = k["expert"]
    with world.lock:
        aired = [a for a in world.archive if a["date"] == world.last_date and a.get("show") == SHOW
                 and a["type"] != T.ad_break.value]
    rang = [p.name for p in world.people if any(m.get("show") == CALLED and m["date"] == world.last_date
                                                for m in p.memories)]
    out = (f"TONIGHT: {k['dish']['cook']}, {k['dish']['cook_role']}, cooks {k['dish']['dish']}. On the sofa: "
           f"{k['sofa']['name']}, {k['sofa']['role']}. THE EXPERT on the phones: {e['name']}, {e['role']}. "
           f"Tonight's phone-in: \"{k['question']}\". The number to ring: {NUMBER}. On a call, THE EXPERT's lines "
           f"are speaker \"guest\" with guest_name \"{e['name']}\".")
    if aired:
        out += ("\nSO FAR TONIGHT (don't do these again; a call is a new caller with a new problem):\n" + "\n".join(
            f"  - {a['type'].replace('_', ' ')}: {a['headline']}: {a['text'][:SO_FAR_CHARS]}" for a in aired[-10:]))
    # Every call tonight, not just the last ten items: by the third lap the first calls had dropped out of SO FAR
    # TONIGHT, and the same five problems came round again (dahlias three times, raspberries three times).
    calls = [a["headline"] for a in aired if a["type"] == T.call.value]
    if calls:
        out += ("\nPROBLEMS ON THE PHONES ALREADY TONIGHT (a new call is a different problem, about a different "
                "plant, pet or thing):\n" + "\n".join(f"  - {h}" for h in calls))
    # The expert's own spots, all of them, as the calls: only the last ten items are in SO FAR TONIGHT, and by the
    # seventh lap the expert was sorting the same myths again (2026-11-14).
    spots = [a["headline"] for a in aired if a["type"] == T.interview.value
             and e["name"].split()[0].lower() in a["headline"].lower()]
    if spots:
        out += (f"\n{e['name'].upper()}'S OWN SPOTS ALREADY TONIGHT (a new one is on other matters, with other "
                "advice):\n" + "\n".join(f"  - {h}" for h in spots))
    if rang:
        out += f"\nRUNG ALREADY TONIGHT: {', '.join(rang)}. A new caller has a name unlike all of these."
    return out


# ------------------------------------------------------------------ with no model

def template(seg_type, world, rng: random.Random, part: str, work: dict, brief: str):
    """The Kettle's On with no model: still tonight's cook, guest and expert, from the booking."""
    from newsroom.models import BulletinScript, CallLine, CallScript, GuestLine, InterviewScript, LiveLine

    k = booked(world)
    d, s, e = k["dish"], k["sofa"], k["expert"]
    if seg_type is T.links:
        if part == "open":
            said = [("kettle_a", "Good evening, and welcome to The Kettle's On! Pull up a chair."),
                    ("kettle_b", f"Tonight {d['cook']} is making {d['dish']}, and I have brought my scales."),
                    ("kettle_a", f"He has. On the sofa, {s['name']}. And {e['name']} is on the phones."),
                    ("kettle_b", f"The number is {NUMBER}.")]
        elif part == "close":
            said = [("kettle_a", f"That's all from the kitchen. Thank you to {d['cook']}, and to {s['name']}."),
                    ("kettle_b", f"And to {e['name']}, and everyone who rang."),
                    ("kettle_a", "Pop the kettle on next time. Goodnight!")]
        else:
            said = [("kettle_a", "Now, the noticeboard."),
                    *(("kettle_b" if i % 2 else "kettle_a", n[0].upper() + n[1:] + ".")
                      for i, n in enumerate(k["notices"])),
                    ("kettle_b", "I'll be at all of those."), ("kettle_a", "You will not.")]
        return BulletinScript(lines=[LiveLine(speaker=w, text=t) for w, t in said],
                              headline=f"{TITLE}: {d['dish']}", lower_third=TITLE)
    if seg_type is T.call:
        lines = [CallLine(speaker="kettle_a", text="We've got someone on the line. Hello, you're on The Kettle's On."),
                 CallLine(speaker="guest", text=f"Hello, Maggie. It's about {e['topic']}. I've tried everything, "
                                                "honestly, and I'm at my wits' end."),
                 CallLine(speaker="guest", guest_name=e["name"],
                          text="Start simple, and give it a fortnight before you change anything else."),
                 CallLine(speaker="kettle_b", text="A fortnight exactly? Write that down."),
                 CallLine(speaker="kettle_a", text="Thanks for ringing, love.")]
        return CallScript(lines=lines, headline=f"A caller asks about {e['topic']}", lower_third=TITLE,
                          caller_name="Pam Opie", caller_from="Cannery Row", caller_gender="f", caller_age="old",
                          caller_accent="british", thread_id=None)
    if seg_type is not T.interview:
        return None
    if "RECIPE, part one" in brief:
        guest, role, said = d["cook"], d["cook_role"], [
            ("kettle_a", f"{d['cook']}, what are we making?"),
            ("guest", f"{d['dish'][0].upper() + d['dish'][1:]}. {d['why'][0].upper() + d['why'][1:]}."),
            ("kettle_b", "And how much of everything? Exactly?"),
            ("guest", "Enough. You'll know."), ("kettle_a", "That's my kind of recipe.")]
        head = f"{d['cook']} makes {d['dish']}"
    elif "RECIPE, part two" in brief:
        guest, role, said = d["cook"], d["cook_role"], [
            ("kettle_a", "Here it comes. Oh, look at that."),
            ("guest", "Leave it five minutes before you cut it."),
            ("kettle_b", "Five minutes. Noted. It's very good. Nine out of ten."),
            ("kettle_a", "Mmm!")]
        head = f"{d['dish'][0].upper() + d['dish'][1:]}, tasted"
    elif "ON THE SOFA" in brief:
        guest, role, said = s["name"], s["role"], [
            ("kettle_a", f"{s['name']}, sit yourself down. Tell us everything."),
            ("guest", s["about"][0].upper() + s["about"][1:] + "."),
            ("kettle_b", "And how did that come about?"),
            ("guest", "Oh, by accident, like most good things.")]
        head = f"{s['name']} on the sofa"
    else:
        guest, role, said = e["name"], e["role"], [
            ("kettle_a", f"{e['name']}, what are people asking you about this week?"),
            ("guest", "The same as every week, and the answer is usually patience."),
            ("kettle_b", "Patience. Not my strong point."), ("kettle_a", "No.")]
        head = f"{e['name']} on {e['topic']}"
    return InterviewScript(lines=[GuestLine(speaker=w, text=t) for w, t in said],
                           headline=head, lower_third=TITLE, guest_name=guest, guest_role=role[:60])
