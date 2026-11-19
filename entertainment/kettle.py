"""The Kettle's On: Channel 8's teatime magazine, 19:00 to 20:00 (docs/ENGINE.md; agreed with the user 2026-11-13).

A homely hour from a studio kitchen with a sofa corner, presented by a double act whose ways clash in the
kitchen (Coastwide's Pat and Clive showed that clashing pairs are the most watchable thing on air):
Maggie Truscott ("kettle_a"), thirty years running the Cannery café's kitchen, who measures nothing, and Nigel
Spargo ("kettle_b"), a retired chemistry teacher who weighs everything to the gram.

Each night a local cook makes one dish at the counter (in two parts: it goes in at the top of the hour, and it
comes out as the last thing before the goodnight; the order is spread across the hour, SHOW_DEF), one of four
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
TOKEN = re.compile(r"\{(cook|dish|card|sofa|expert|says|question|notices|caller)\}")
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
             "eye, Nigel wants the weights; the cook settles it from the card. {card}")
# On the first scratch run (2026-11-13) part two opened with part one's first line and went through the
# ingredients again. Since 2026-11-15 it is the last thing in the hour, before the goodnight (SHOW_DEF.closing).
_RECIPE_2 = ("THE RECIPE, part two, at the end of the hour: the dish went in at the start of the programme and has "
             "been cooking through it. Part one has already done the ingredients and the method, so "
             "none of that again: it starts with {dish} coming out of the oven or from under the grill. {cook} "
             "finishes it and serves up; Maggie and Nigel taste it and give their verdicts (Nigel's is precise, "
             "Maggie's is a noise of joy); the cook's tip for doing it at home. {card}")
_SOFA = ("ON THE SOFA: {sofa}. Maggie and Nigel chat with them about it, with a cup of tea: warm and a bit nosy, "
         "the details people like")
# The sofa guest back for a second cup since 2026-11-19 (the user): once, they had two minutes of the hour, and the
# calls had thirty.
_SOFA_2 = ("ON THE SOFA, part two: {sofa}, back on the sofa for a second cup. The rest of their story: what happened "
           "next, what it means to them now, and what's coming up for them; nothing from part one told again. "
           "Maggie and Nigel each bring something of their own to it")
# The expert's way of talking ({says}) is given here and nowhere else: in every expert item's brief it was said in
# every item, and Lowenna pushed seaweed in nine spots out of ten (2026-11-14).
_EXPERT = ("THE EXPERT on the sofa before the phones open: {expert} ({says}), on tonight's phone-in, {question}: one "
           "good tip for the time of year, and Nigel asks the question everyone's too embarrassed to ask")
_NOTICES = ("THE NOTICEBOARD: Maggie and Nigel read out the community notices: {notices}. A line on each, with "
            "when and where; they bicker gently about which one they're going to")
# The expert's own items between the calls, each a different angle: with one brief, the second scratch run's hour
# (2026-11-13) had Lowenna on "frosted dahlias, rhubarb and seaweed" five times; with six, the first night on air
# (2026-11-14) had the postbag and Myth or True twice each. Thirteen: the first three have places of their own in the
# hour, and the loop at its end takes the rest in turn, one a lap (Show.item).
# On 2026-11-19 four of the vet's eight spots were frost, from the night's question ("Frost's in: ..."): the
# question is the callers', and a spot is about the weather or the season only if its own brief says so.
_POSTBAG = tuple(b + ", nothing the expert has already said tonight, and nothing a caller has asked; on the "
                     "weather or the season only if this says so" for b in (
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
    # Three more since 2026-11-19: with one call a block the loop has about eight laps, and ten briefs came round.
    "THE MISTAKE EVERYONE MAKES: {expert} names the one mistake they see most in the expert's field and how to "
    "put it right; Nigel admits he makes it, and Maggie claims she never has",
    "NIGEL'S QUESTION: Nigel asks {expert} the one question in the expert's field he has always wanted answered, "
    "and Maggie has a theory of her own before the answer",
    "ON A SHOESTRING: {expert} on doing right by it in the expert's field for next to nothing, with what people "
    "already have at home; Maggie has a cheaper way still",
))

# The hour's order, spread out since 2026-11-15 (the user): on the first night on air (2026-11-14) everything
# booked was over in 17 minutes and the other 43 were one phone-in. Since 2026-11-19 (the user) fewer calls: one a
# block after the first two, and the sofa guest twice. Now the dish goes in at the top and comes out
# as the last thing before the goodnight (the closing, so it lands at the end however long the items run), the
# sofa guest is about twenty minutes in and the noticeboard at the half hour, and the phones come in short blocks
# between them, each with one of the expert's own items. The times are the targets' running total.
_CALL = I(T.call, brief="{caller}")

# Since 2026-11-19 (the user) the loop's second half is one of these, in turn, so the last half hour isn't the expert
# on every other item: Maggie and Nigel's own kitchen duel (presenters only), and a look back in on the cook while the
# dish cooks (the cook is otherwise only at the start and the end).
_DUELS = tuple(b + ". Only Maggie and Nigel speak, to each other more than to camera; nothing of tonight's dish, and "
                   "nothing a caller or the expert has said" for b in (
    "MAGGIE V NIGEL: the perfect cup of tea. Maggie makes hers by eye and by feel, Nigel his by the gram and the "
    "stopwatch; they taste each other's, and argue about what brewed means",
    "MAGGIE V NIGEL: the boiled egg. Nigel's timer and his water at exactly the boil against Maggie's 'when it "
    "rattles'; they open them up and judge",
    "MAGGIE V NIGEL: a blind tasting. Nigel tastes three of one thing from the town's shops (butters, jams or "
    "biscuits) with his eyes shut and tries to say which is which; Maggie keeps the score and gloats",
    "MAGGIE V NIGEL: the cheese on toast, against the clock. Nigel measures, Maggie doesn't; they swap plates and "
    "give marks out of ten",
))
_COOK_AGAIN = tuple(b + ". Figures only off the card, and nothing from the recipe so far said again. {card}" for b in (
    "AT THE COUNTER: a look in on {cook} while {dish} cooks: how it's getting on, a story from their own kitchen, "
    "and what they'd serve alongside it",
    "AT THE COUNTER, again: {cook} gets something ready to go with {dish} when it comes out (a side, a dressing, or "
    "the table), and tells Maggie and Nigel how they started cooking",
))
SHOW_DEF = Show(
    SHOW, "THE KETTLE'S ON", "KETTLE'S ON", (214, 120, 70),
    pattern=(
        T.bumper,
        I(T.links, "open", brief="Maggie and Nigel open The Kettle's On: a cosy good evening from the kitchen, "
                                 "tonight's dish and cook (it goes in now and comes out before the goodnight), "
                                 "tonight's sofa guest, and the expert on the phones", target_s=50.0),
        I(T.interview, brief=_RECIPE_1, target_s=200.0),               # the dish goes in
        I(T.interview, brief=_EXPERT, target_s=110.0),
        _CALL, _CALL,
        T.ad_break,                                                    # 19:11
        I(T.interview, brief=_POSTBAG[0], target_s=120.0),
        _CALL, _CALL,
        I(T.interview, brief=_SOFA, target_s=220.0),                   # 19:17, the sofa guest
        T.ad_break,                                                    # 19:21
        _CALL,
        I(T.interview, brief=_POSTBAG[1], target_s=120.0),
        _CALL,
        I(T.links, brief=_NOTICES, target_s=60.0),                     # 19:28, the noticeboard
        T.ad_break,
        _CALL,
        I(T.interview, brief=_POSTBAG[2], target_s=120.0),
        _CALL,
        I(T.interview, brief=_SOFA_2, target_s=180.0),                 # 19:26, the sofa guest again
        # Wraps to here until the close, ONE call before each of: the expert's next item, Maggie v Nigel, the expert
        # again, the cook at the counter, with a break every two; each a new one each lap (two calls a block until
        # 2026-11-19, when 21 calls took thirty minutes of the hour; the expert after every call, until the duel and
        # the cook joined the same evening). The expert's angles are shared out so neither place repeats one.
        T.ad_break, _CALL,
        I(T.interview, brief=_POSTBAG[3::2], target_s=120.0),
        _CALL,
        I(T.links, brief=_DUELS, target_s=80.0),
        T.ad_break, _CALL,
        I(T.interview, brief=_POSTBAG[4::2], target_s=120.0),
        _CALL,
        I(T.interview, brief=_COOK_AGAIN, target_s=100.0),   # these two set where the hour ends: swept at 0.7-1.15
    ),
    loop_from=21,
    closing=(I(T.interview, brief=_RECIPE_2, target_s=160.0),          # the dish comes out
             I(T.links, "close", brief="Maggie and Nigel close The Kettle's On: what's left of the dish, thanks to "
                                       "the cook, the sofa guest and the expert, the number for next time's phone-in, "
                                       "and a cosy goodnight", target_s=40.0)),
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

# Its own set, a studio kitchen with a sofa corner (assets/backdrops/studio_kettle.png, approved 2026-11-15, seed
# 101; the breakfast sofa stood in before): Maggie and Nigel stand behind the kitchen island (its top's back edge
# at y 143, 3 px above their baseline), the guest sits on the mustard sofa, the kettle is on the range under the
# window, and the plain wall at the top right is where a caller's box goes (scenes.CALLER_BOX).
# scenes._interview_marks seats the first presenter to speak at "host", then "panel_1", "panel_2", so the prompt
# has Maggie speak first. The set is registered for the run by entertainment.use(), never in locations.py.
SET = "studio_kettle"
SET_NAME = "The Kettle's On's kitchen"
SET_BLURB = ("a studio kitchen with a sofa corner: the range with the kettle on it, a plate rack, the kitchen "
             "island, a mustard sofa")
SET_COLOURS = ((240, 228, 198), (184, 108, 74))     # the cream wall and the terracotta floor, for a placeholder
MARKS = {"host": (122, 146, 2, 1), "panel_1": (186, 146, 2, -1), "panel_2": (272, 150, 2, -1)}

_RULES = """
This is part of THE KETTLE'S ON, a homely teatime magazine from a studio kitchen with a sofa corner,
presented by a double act: Maggie Truscott ("kettle_a"), thirty years in the Cannery café's kitchen,
generous and chaotic, measures nothing, feeds everyone, laughs at her own disasters; and Nigel Spargo
("kettle_b"), a retired chemistry teacher, precise and fussy, weighs everything to the gram, worries
about oven temperatures, and secretly can't cook. They are fond of each other and disagree about
everything in the kitchen: that is the fun, never a real row. TONIGHT gives the cook, the dish, the
sofa guest, the expert and tonight's phone-in. Both presenters speak in every item, Maggie first.
Light: no news stories, no threads (thread_id is null), nothing grim, and nothing from the council: no votes,
petitions or campaigns, not even in passing (an opening plugged a petition going before council). Cooking is real cooking: real
ingredients, real quantities, real times and temperatures, said the way a cook says them.
Maggie and Nigel have only the pasts given here: the café kitchen and the classroom. A story of their
own is a small one from there; they never take a guest's history, family, years or places as theirs
(not "forty years on the allotment" because the expert has them, not the cook's mother as Maggie's).
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
    # The figures said on air, read off one card: in a rehearsal (2026-11-14) Nigel asked for 250 g of flour and the
    # cook then gave 150 g, on a show built on Nigel's weighing. Empty for a booking made before there was a card.
    card: Annotated[list[str], creative._first(16)] = Field(
        default_factory=list, description="the recipe card: each ingredient with its exact quantity, one a line, "
                                          "then the oven or hob, the temperature and the time")


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
  real ingredients, suited to the season (it is {month}), homely more than fancy. It goes in the oven or
  on the hob at the top of the hour and comes out at the end, so it cooks in forty minutes to an hour,
  nothing that wants all afternoon. The cook is from town: someone in PEOPLE who cooks (a café, a pub
  kitchen, a bakery), or a new resident with a cook's job; why this dish tonight in a line. card: the
  recipe card, the only figures anyone says on air: each ingredient with its exact quantity (grams,
  millilitres, spoons or a count), one a line, then a last line with the oven or hob, its temperature
  and the time.
- sofa: ONE guest with a nice story, never news: a long marriage, a record, a rescue, a hobby, a reunion,
  a first. Someone from PEOPLE, or a new resident.
- question: tonight's phone-in in THE EXPERT's field, as Maggie would put it to viewers, right for the
  time of year, and wide enough for a whole evening of different problems (the field in this season,
  not one worry within it). It is the callers' question, not the night's theme: the expert's own spots
  are on other matters.
- callers: {calls} callers' problems, one line each, in the order they ring. The hour takes about twenty
  calls and each line is one call, used once, so no two may be alike: each about a different plant,
  animal or object, and a different trouble (never two on the same vegetable, the same weather or the
  same cure; at most three touching the season's big worry). Spread them: no kind of thing more than twice
  in the night (one bird and one more at most, one rabbit, one pony; two dogs, two cats), and never one
  complaint twice under another name: a budgie, a hen, a parrot and a canary losing feathers are one
  problem four times (2026-11-19). The caller and their problem as a
  description, never a name: "someone whose bay tree in a pot has gone brown on one side".
- notices: three or four community notices: a jumble sale, a choir wanting tenors, a lost cat, a coffee
  morning, a talk at the library; what, when and where, from the town's places in the briefing. Tonight is
  {today}: an event is on a day after tonight, and a lost pet went missing on a day before it.
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
    day = date.fromisoformat(world.last_date)
    today = f"{day:%A} {day.day} {month}"           # a notice said "missing since Monday 16 November" on the 14th
    user = (f"BRIEFING\n{world.summary_for_editor()}\n\nPEOPLE:\n"
            + "\n".join(f"  - {p.name}, {p.role}" for p in _people(world))
            + f"\n\nTHE EXPERT tonight: {ex['name']}, {ex['role']} ({ex['topic']})."
            + ("\n\nRECENT SHOWS (none of these again):\n" + "\n".join(
                f"  - {k['dish']['dish']} by {k['dish']['cook']}; on the sofa {k['sofa']['name']}; the phones: "
                f"{k['question']}" for k in recent) if recent else "")
            + creative.for_planner(world, SHOW))
    try:
        b = llm.complete_json(TASK, KettleBooking,
                              _SYSTEM.replace("{month}", month).replace("{today}", today)
                              .replace("{calls}", str(CALLS_ASKED)), user)
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
    card = f" The card: {'; '.join(d['card'])}." if d.get("card") else ""
    return (f"The recipe: {d['dish']} by {d['cook']}, {d['cook_role']} ({d.get('why', '')}).{card}\n"
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


def aired(seg, world: World) -> None:
    """player.AIRED_HOOKS: the recipe or the sofa went out, so tonight's booking says so, for the town's talk the next
    day (newsroom/talk.py). On the booking, not the archive: a Channel 7 night writes up to about a thousand entries,
    the archive's whole length, so the morning after its Kettle's On items would have gone."""
    k = tonight(world)
    brief = seg.brief or ""
    key = "dish_aired" if brief.startswith("THE RECIPE") else "sofa_aired" if brief.startswith("ON THE SOFA") else None
    if k is not None and key and not k.get(key):
        with world.lock:
            k[key] = True


def guest_for(k: dict, brief: str) -> str:
    """Whose item this is, by its brief: the cook's recipe, the sofa guest's sofa, or else the expert's."""
    if brief.startswith(("THE RECIPE", "AT THE COUNTER")):
        return k["dish"]["cook"]
    if brief.startswith("ON THE SOFA"):
        return k["sofa"]["name"]
    return k["expert"]["name"]


def check(seg, script, world: World) -> None:
    """writers.CHECK_HOOKS: an interview's guest is the one its brief books. On 2026-11-19 a "Maggie's disaster" spot
    of the vet's came back as the cook's traybake, with figures off the card (400 g of hake for 800), and aired."""
    if seg.type is not T.interview:
        return
    want = guest_for(booked(world), seg.brief or "")
    got = (getattr(script, "guest_name", None) or "").strip()
    if got.lower() != want.lower():
        raise llm.AskAgain(f"THIS ITEM is {want}'s, so the guest is {want} (guest_name \"{want}\"), not {got or 'nobody'}"
                           ": write THIS ITEM as it says, with them")


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
        if tok == "card":
            card = [c.strip() for c in k["dish"].get("card") or [] if c.strip()]
            if not card:
                return "Each quantity, temperature and time is said once and never changed."
            return ("THE RECIPE CARD, the only figures anyone says (Nigel reads his weights off it; no other "
                    "quantity, temperature or time, and none of these changed): " + "; ".join(card) + ".")
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
                "Keep to it: not another plant, pet or thing, and nothing from PROBLEMS ON THE PHONES ALREADY TONIGHT"
                + (f". If their animal has a name, it is {pet_name(k, n)}: no other name for it"
                   if k["expert"].get("topic") == "pets" else ""))
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


# Each call's pet named in code: written one call at a time, six pets were "Biscuit" and three "Bramble" on
# 2026-11-19. Mixed by the night, so the first caller's dog isn't always the same name.
PET_NAMES = ("Biscuit", "Pickle", "Bramble", "Mabel", "Dougal", "Pepper", "Winston", "Hettie", "Rolo", "Nell",
             "Barney", "Juniper", "Captain", "Moss", "Toffee", "Ziggy", "Percy", "Clementine", "Bosun", "Fudge",
             "Kipper", "Dot", "Gordon", "Marmalade", "Wilf", "Sprout", "Duchess", "Pip", "Teasel", "Monty")


def pet_name(k: dict, n: int) -> str:
    """Call `n`'s pet's name: a different one each call, in an order of the night's own."""
    names = list(PET_NAMES)
    random.Random(f"kettle-pets-{k.get('date')}").shuffle(names)
    return names[n % len(names)]


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
    # "On the sofa: Brenda Fisk" in every item had the hosts turning to her in the recipe ("Brenda, you've been sat
    # there very patiently") and her replies going out under the cook's name, the only guest an item has (2026-11-19).
    out = (f"TONIGHT: {k['dish']['cook']}, {k['dish']['cook_role']}, cooks {k['dish']['dish']}. The sofa guest: "
           f"{k['sofa']['name']}, {k['sofa']['role']}, in the studio only for the items ON THE SOFA: in any other "
           "item nobody talks to them or as if they were there. "
           f"THE EXPERT on the phones: {e['name']}, {e['role']}. "
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
        elif brief.startswith("MAGGIE V NIGEL"):
            said = [("kettle_a", "Right, Nigel. You and me. Best of three."),
                    ("kettle_b", "I have my scales and my stopwatch. You have nothing."),
                    ("kettle_a", "I have thirty years, love."), ("kettle_b", "Then let the tasting decide."),
                    ("kettle_a", "Mine's better. Look at your face."), ("kettle_b", "It's... acceptable. A draw.")]
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
    if brief.startswith("AT THE COUNTER"):
        guest, role, said = d["cook"], d["cook_role"], [
            ("kettle_a", f"Let's have a look in on {d['cook']}. How's it coming along?"),
            ("guest", "Nicely. Smell that? That's how you know."),
            ("kettle_b", "I'd rather know by the thermometer."),
            ("guest", "You'll know when it comes out, Nigel."), ("kettle_a", "I can't wait.")]
        head = f"{d['cook']} at the counter"
    elif "RECIPE, part one" in brief:
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
