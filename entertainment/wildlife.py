"""Tideline: Channel 8's wildlife series, 20:40 to 21:00 (docs/FACTUAL.md; planned with the user 2026-11-14).

Rowan Polglase ("naturalist"), thirty years the warden of the Salting reserve, shows one creature of the season each
Channel 8 night. It is canon, not fiction: the coast and its counters are the town's, and what is filmed is true in
Port Wexley.

**The sight is chosen in code**, from the hand-written seasonal list (seasons.py): one lead sight an episode, in
season, rested since it last aired (`Sight.rest_days`), a rare one at most once a winter; the one longest unseen
first, and when every sight is resting, the one rested longest. Its number (eleven pups, a hundred and forty brent)
is drawn in code from the sight's range, seeded by the date, so the booking owns the fact and the script reads it
back. A second sight on the same backdrop, if the list has one, is the episode's neighbour: one sequence, no count,
no rest.

**The episode is planned in the back office** from BOOK_FROM, in one call (The Chamber's route unless config.toml
gives "wildlife" its own): a title, five sequences on the sight (what we watch, close or wide), three residents met on
location (the town's counters, its fishermen and its ferry crew first, or a new resident) and the close. If the call
fails, a stand-in plan is made in code.

**On air** it is filmed, not live: every item is out on location by day (`seg.work["location"]`, `["tod"]`), with
no LIVE tag. Rowan's narration over a creature is the hide view (creatures.draw_hide, through scenes.SCENES and
player.VIEW_HOOKS): a close-up at 4x with the place soft, or a wide at 2x. Spare minutes are field-notebook
moments, three and then a break, and the close comes last, at the end of the slot.

**The wildlife log**: an episode is stamped aired when its first sequence, the one that gives the count, goes out
(player.AIRED_HOOKS), since the archive keeps only about a night. Only aired episodes count for the rests, the
contributors' rest and the town's talk (newsroom/talk.py).
"""
from __future__ import annotations

import logging
import random
import re
import time
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from newsroom import llm, schedule
from newsroom.config import CONFIG
from newsroom.models import SegmentType as T
from newsroom.schedule import Item as I, Show
from newsroom.world import World
from newsroom.writers import _COMMON_RULES, _MIDDLE

from . import creative, creatures, seasons

log = logging.getLogger(__name__)

SHOW = "tideline"
TITLE = "Tideline"                       # the working title (docs/FACTUAL.md)
AIRS_AT = "20:40"
BOOK_FROM = "18:30"
TASK = "wildlife" if "wildlife" in CONFIG.llm.routes else "chamber"
SEQUENCES = 5                            # watch items; the first gives the count (four left the slot two-thirds spare)
MEETS = 3                                # residents met, after the first three sequences
SPARES = 12                              # field-notebook moments the loop can take (three a lap, four laps)
CONTRIBUTOR_REST_DAYS = 14               # a resident isn't met again on Tideline within this
RARE_CHANCE = 0.25                       # a rare sight in season and rested is the lead on one night in four
KEEP = 200                               # episodes kept: rests run to sixty days, "once a winter" to four months
IDENT = "Tideline, with Rowan Polglase. On Channel 8."
SAID_CHARS = 420                         # each earlier item as the later ones see it: all of tonight's, not the last ten
# Filmed by day: what slips through anyway is put into the daytime (the first model run had "Good evening, and welcome
# to Tideline", a resident's "Good evening to you too, Rowan" and "the tide is making slowly tonight").
DAYTIME = ((re.compile(r"\bgood evening\b", re.I), "hello"), (re.compile(r"\bthis evening\b", re.I), "today"),
           (re.compile(r"\btonight\b", re.I), "today"))
ON_AIR_FEET = 0.6                        # the creature's feet this far down the hide: clear of the ticker (on-air frames)
TOKEN = re.compile(r"\{(open|close|w[0-9]+|m[0-9]+|x[0-9]+)\}")
# Who has something to say about the coast's wildlife: the counters and watchers first (WILD), then the people who
# work the water (COAST). "harbour" alone matched half the town: the first stand-in met a net-loft landlord.
# A first try matched "county", the bell ringers and the Salting Harmony Choir: a role says it (WILD_ROLE), or a memory
# names a creature (WILD_SAID).
WILD_ROLE = re.compile(r"counter|bird|ringing scheme|ringer and|warden|wader|naturalist|ecolog", re.I)
WILD_SAID = re.compile(r"wader|redshank|curlew|heron|egret|brent|seals?|otter|starling|avocet|spoonbill|"
                       r"roost|oystercatcher", re.I)
COAST = re.compile(r"lifeboat|ferry|lighthouse|keeper of the|fisherm|skipper|crabber|boatwoman|boatman", re.I)


# ------------------------------------------------------------------ the log

def state(world: World) -> dict:
    with world.lock:
        return world.wildlife.setdefault("episodes", [])


def tonight(world: World) -> dict | None:
    return next((ep for ep in reversed(state(world)) if ep["date"] == world.last_date), None)


def aired_episodes(world: World) -> list[dict]:
    return [ep for ep in state(world) if ep.get("aired")]


def _day(world: World) -> date:
    return date.fromisoformat(world.last_date)


def _winter(d: date) -> int:
    """The winter a date belongs to, by the year it starts in: November 2026 to February 2027 is 2026's."""
    return d.year if d.month >= 7 else d.year - 1


def _since(eps: list[dict], sight_id: str, today: date) -> int | None:
    """Days since `sight_id` last aired as the lead, or None if it never has."""
    days = [(today - date.fromisoformat(ep["date"])).days for ep in eps if ep["sight"] == sight_id]
    return min(days) if days else None


# ------------------------------------------------------------------ the sight, in code

def pick(world: World, today: date | None = None) -> tuple[seasons.Sight, seasons.Sight | None]:
    """Tonight's lead sight and its neighbour (another in season on the same backdrop), from the seasonal list."""
    today = today or _day(world)
    eps = [ep for ep in aired_episodes(world) if ep["date"] < today.isoformat()]
    rng = random.Random(f"tideline-{today.isoformat()}")
    season = [s for s in seasons.in_season(today.month) if s.creature]
    if not season:                                       # outside the list's months: the winter's stands in
        season = [s for s in seasons.SIGHTS if s.creature and not s.rare]
    winter = _winter(today)
    seen_this_winter = {ep["sight"] for ep in eps if _winter(date.fromisoformat(ep["date"])) == winter}

    def rested(s: seasons.Sight) -> bool:
        d = _since(eps, s.id, today)
        return d is None or d >= s.rest_days

    rare_ok = rng.random() < RARE_CHANCE
    usable = [s for s in season if not (s.rare and (s.id in seen_this_winter or not rare_ok))]
    pool = [s for s in usable if rested(s)] or [s for s in usable if not s.rare] or season

    def key(s: seasons.Sight):
        d = _since(eps, s.id, today)
        return (1 if d is None else 0, d or 0, rng.random())
    lead = max(pool, key=key)
    near = [s for s in season if s.place[0] == lead.place[0] and s.id != lead.id and not s.rare]
    return lead, (rng.choice(near) if near else None)


def count_for(sight: seasons.Sight, day: date) -> int | None:
    """The sight's number on `day`, drawn in code: the booking owns it, the script says it."""
    if not sight.count:
        return None
    n = random.Random(f"tideline-count-{day.isoformat()}-{sight.id}").randint(*sight.count)
    return round(n, -3 if n >= 5000 else -1 if n >= 200 else 0)


# ------------------------------------------------------------------ the plan, in the back office

class Watch(BaseModel):
    angle: str = Field(min_length=8, max_length=600, description="what we watch in this sequence and what Rowan "
                                                                  "tells us about it, in two or three sentences")
    shot: Literal["close", "wide"] = Field(description="close: one creature, filling the frame; wide: the place, a "
                                                       "flock")


class Meet(BaseModel):
    name: str = Field(min_length=3, max_length=40, description="an exact name from PEOPLE, or a new resident's "
                                                                "first name and surname")
    role: str = Field(min_length=3, max_length=80, description="who they are, as their caption would say")
    gender: str = Field(default="", max_length=1, description="'f' or 'm'")
    age: str = Field(default="", max_length=6, description="young, middle or old")
    talk: str = Field(min_length=8, max_length=600, description="what they tell Rowan, in a sentence or two")


class WildEpisode(BaseModel):
    """Tonight's Tideline (entertainment/wildlife.py)."""
    title: str = Field(min_length=3, max_length=50, description="the episode's title, a few words")
    watches: list[Watch] = Field(min_length=SEQUENCES, max_length=SEQUENCES)
    meets: list[Meet] = Field(min_length=MEETS, max_length=MEETS)
    close: str = Field(min_length=8, max_length=600, description="what to look for this week, where and when, and "
                                                                  "how to keep your distance")


_SYSTEM = """\
You plan TIDELINE, a wildlife series on Channel 8, Port Wexley's second television channel, in the FICTIONAL town in
the briefing. Its presenter is Rowan Polglase, for thirty years the warden of the Salting reserve (he retired in
2021): unhurried, quietly delighted, speaking low so as not to disturb the birds. It is filmed by day on the town's
own coast, and everything in it is true in the town.
Plan this episode, about THE SIGHT and nothing else bigger than it:
- title: a few words, plain and warm.
- watches: {seq} sequences of Rowan's narration over pictures of THE SIGHT, each a different angle on it (where it
  came from or why it's here, how it feeds or lives, what it does at this time of year and why, a detail you'd only
  see up close). Sequence {near} is about THE NEIGHBOUR instead, if there is one. Each says close or wide: close for
  one creature filling the frame, wide for a flock or the place.
- meets: {meets} residents Rowan meets out there, after the first three sequences, each with something of their own
  to say about the sight: a counter's long record, a fisherman's or a ferry rower's view of it. People from PEOPLE
  first (their exact names); keep to what PEOPLE says of them: nothing new about their own lives (no spouses, gifts,
  family stories), only what they have seen of the sight. A new resident only if nobody there fits, with a job on the
  coast. Never Rowan, never a presenter, nobody twice.
- close: what to look for this week, where and when, and how to watch without disturbing anything.
Each watch and each meeting has its own fact or detail: the first watch gives THE SIGHT's facts and its number, and no
other one repeats them.
THE SEASON lists what is about this month: mention nothing outside it. Use THE SIGHT's facts as given, and its
number exactly. No real organisations (no real charities, trusts or societies), no real people. Return ONLY JSON.
"""


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def should_commission(world: World, now: float | None = None) -> bool:
    now = now or schedule.now()
    return (tonight(world) is None and _at(BOOK_FROM, now) <= now < _at(AIRS_AT, now) + 20 * 60
            and schedule.show_at(_at(AIRS_AT, now)).id == SHOW)


def _met_lately(world: World, today: date) -> set[str]:
    return {m["name"].lower() for ep in aired_episodes(world)
            if 0 <= (today - date.fromisoformat(ep["date"])).days < CONTRIBUTOR_REST_DAYS for m in ep["meets"]}


def _people(world: World, today: date) -> list:
    """Residents with something to say about the coast's wildlife, the most seen first, not met lately."""
    lately = _met_lately(world, today)

    def tier(p) -> int:
        said = " ".join(m.get("said", "") for m in p.memories)
        return 2 if WILD_ROLE.search(p.role) or WILD_SAID.search(said) else 1 if COAST.search(p.role) else 0
    near = [p for p in world.people if p.kind in ("resident", "worthy") and p.name.lower() not in lately
            and all(w[:1].isupper() for w in p.name.split()) and tier(p)]       # "Eleven people" is in the town
    return sorted(near, key=lambda p: (-tier(p), -p.appearances))[:30]


def _said(p) -> str:
    said = next((m.get("said", "") for m in reversed(p.memories) if m.get("said")), "")
    return f" ({said[:140]})" if said else ""


def _sight_text(s: seasons.Sight, n: int | None) -> str:
    return (f"{s.what}. {s.note}" + (f" THE NUMBER: {n} {s.counted} (say it exactly as this)." if n is not None
                                     else ""))


REMEMBERED = 12                          # earlier episodes' titles the planner sees


def _earlier(world: World, lead: seasons.Sight) -> str:
    """What Tideline has shown before: every recent title, and on tonight's sight what those episodes covered, so a
    sight that comes round again (about every sixteen days in November) gets a new episode, not the same one."""
    eps = [ep for ep in aired_episodes(world) if ep["date"] < world.last_date]
    if not eps:
        return "\n\nEARLIER EPISODES: none. This is the first Tideline."
    same = [ep for ep in eps if ep["sight"] == lead.id]
    out = ("\n\nEARLIER EPISODES (no title like these again):\n"
           + "\n".join(f"  - {ep['date']}: \"{ep['title']}\" ({ep['what']})" for ep in eps[-REMEMBERED:]))
    if same:
        out += ("\nTHE SIGHT HAS BEEN ON BEFORE: find new angles, new residents and a new close; not these:\n"
                + "\n".join(f"  - {ep['date']}, \"{ep['title']}\": " + " / ".join(w["angle"][:120] for w in ep["watches"])
                             + f" / met {', '.join(m['name'] for m in ep['meets'])}" for ep in same[-3:]))
    return out


def commission(world: World) -> dict:
    """Book tonight's episode: the sight in code, the plan by the model (or the stand-in), recorded in the log."""
    today = _day(world)
    lead, near = pick(world, today)
    n = count_for(lead, today)
    season = seasons.in_season(today.month)
    people = _people(world, today)
    near_at = SEQUENCES - 1                               # the neighbour's sequence: the third of four
    started = time.monotonic()
    # What the planner is asked, apart from the town's briefing: the creative editor reads this much of it too.
    asked = (f"THE SIGHT: {_sight_text(lead, n)}"
             + (f"\n\nTHE NEIGHBOUR (sequence {near_at}, no number): {near.what}. {near.note}" if near else
                "\n\nTHE NEIGHBOUR: none tonight; every sequence is about THE SIGHT.")
             + "\n\nTHE SEASON (what is about this month):\n" + "\n".join(f"  - {s.what}" for s in season)
             + "\n\nPEOPLE:\n" + ("\n".join(f"  - {p.name}, {p.role}{_said(p)}" for p in people) or "  (nobody yet)")
             + _earlier(world, lead) + creative.for_planner(world, SHOW))
    user = f"BRIEFING\n{world.summary_for_editor()}\n\n{asked}\n\nToday is {today:%A %d %B}."
    system = _SYSTEM.format(seq=SEQUENCES, near=near_at, meets=MEETS)
    try:
        plan = llm.complete_json(TASK, WildEpisode, system, user)
        _check(plan, world, today)
        plan = creative.redraft(world, SHOW, "episode", plan, text=_plan_text, context=asked, started=started,
                                check=lambda p: _check(p, world, today),
                                again=lambda more: llm.complete_json(TASK, WildEpisode, system, user + more))
        entry, stand_in = plan.model_dump(), False
    except llm.LLMError as e:
        log.warning("tideline: no plan (%s); the stand-in takes tonight", e)
        entry, stand_in = _stand_in(world, lead, people), True
    return _record(world, lead, near, n, entry, stand_in)


def _plan_text(plan: WildEpisode) -> str:
    return (f"\"{plan.title}\"\n" + "\n".join(f"  Sequence {i + 1} ({w.shot}): {w.angle}" for i, w in enumerate(plan.watches))
            + "\n" + "\n".join(f"  Meets {m.name}, {m.role}: {m.talk}" for m in plan.meets) + f"\n  Close: {plan.close}")


def digest(world: World, day: str) -> str:
    """The episode booked for `day`, as the creative editor reads it after it has aired; "" for none or the
    stand-in (not the planner's work)."""
    ep = next((e for e in state(world) if e["date"] == day), None)
    if not ep or ep.get("stand_in"):
        return ""
    try:
        plan = _plan_text(WildEpisode.model_validate({k: ep[k] for k in WildEpisode.model_fields}))
    except (KeyError, ValueError):
        plan = f"\"{ep.get('title')}\""
    return (f"The sight (chosen in code): {ep['what']}"
            + (f", {ep['count']} {ep['counted']}" if ep.get("count") is not None else "") + f".\n{plan}")


def _check(plan: WildEpisode, world: World, today: date) -> None:
    names = [m.name.strip().lower() for m in plan.meets]
    if len(set(names)) != len(names):
        raise llm.LLMError("the same resident is met twice")
    for m in plan.meets:
        if world.presenter_named(m.name) or m.name.strip().lower() == "rowan polglase":
            raise llm.LLMError(f"{m.name} is a presenter, not a resident to meet")
        if m.name.strip().lower() in _met_lately(world, today):
            raise llm.LLMError(f"{m.name} was on Tideline in the last {CONTRIBUTOR_REST_DAYS} days")


# The stand-in's sequences, by angle, and the residents it meets if the town has nobody fitting.
_STAND_IN_ANGLES = (
    ("Where we are and what we're looking at: {what}.", "wide"),
    ("Up close: what to look for, the colour, the shape, the way it moves.", "close"),
    ("Why it's here at this time of year, and where it goes after.", "wide"),
    ("{neighbour}", "close"),                            # the neighbour's sequence: SEQUENCES - 1
    ("One last look before the light goes.", "close"),
)
_STAND_IN_MEETS = (
    ("Carys Lunt", "volunteer counter for the county wader survey", "f", "old"),
    ("Eamon Trask", "retired keeper of the Greymouth light", "m", "old"),
    ("Ruth Hallam", "boatwoman, Saltby foot ferry crew", "f", "middle"),
    ("Ned Trevena", "birdwatcher and estuary walker", "m", "old"),
)


def _stand_in(world: World, lead: seasons.Sight, people: list) -> dict:
    meets = [{"name": p.name, "role": p.role[:80], "gender": "", "age": "",
              "talk": f"what they have seen of {lead.what} over the years"} for p in people[:MEETS]]
    taken = {m["name"].lower() for m in meets}
    for name, role, g, a in _STAND_IN_MEETS:
        if len(meets) >= MEETS:
            break
        if name.lower() not in taken and name.lower() not in _met_lately(world, _day(world)):
            meets.append({"name": name, "role": role, "gender": g, "age": a,
                          "talk": f"what they have seen of {lead.what} over the years"})
    watches = [{"angle": a.format(what=lead.what, neighbour="Something else about here, while we wait."),
                "shot": shot} for a, shot in _STAND_IN_ANGLES]
    return {"title": lead.what[0].upper() + lead.what[1:][:49], "watches": watches, "meets": meets[:MEETS],
            "close": f"Where to see {lead.what} this week, and how to keep your distance."}


def _record(world: World, lead: seasons.Sight, near: seasons.Sight | None, n: int | None, plan: dict,
            stand_in: bool) -> dict:
    entry = {"date": world.last_date, "sight": lead.id, "near": near.id if near else None, "count": n,
             "counted": lead.counted, "what": lead.what, "stand_in": stand_in, "aired": False, **plan}
    for m in entry["meets"]:
        if known := world.person_by_name(m["name"]):          # their role is the town's, not the plan's
            m["role"] = known.role[:80]
        else:
            world.ensure_person(m["name"], m["role"], "resident", gender=m.get("gender") or None,
                                age=m.get("age") or None, accent="british")
    with world.lock:
        eps = world.wildlife.setdefault("episodes", [])
        eps[:] = [e for e in eps if e["date"] != world.last_date] + [entry]
        del eps[:-KEEP]
    log.info("tideline: tonight %s%s, %r, meeting %s%s", lead.id, f" ({n} {lead.counted})" if n is not None else "",
             entry["title"], ", ".join(m["name"] for m in entry["meets"]), " (stand-in)" if stand_in else "")
    return entry


def booked(world: World) -> dict:
    return tonight(world) or commission(world)


def aired(seg, world: World) -> None:
    """player.AIRED_HOOKS: the first sequence, which gives the sight and its number, went out: the log has it."""
    if seg.brief != "{w1}":
        return
    ep = tonight(world)
    if ep and not ep.get("aired"):
        with world.lock:
            ep["aired"] = True
        log.info("tideline: %s aired%s", ep["sight"],
                 f" ({ep['count']} {ep['counted']})" if ep.get("count") is not None else "")


# ------------------------------------------------------------------ the items

def _sights(ep: dict) -> tuple[seasons.Sight, seasons.Sight | None]:
    by = {s.id: s for s in seasons.SIGHTS}
    return by[ep["sight"]], by.get(ep.get("near") or "")


def _place(s: seasons.Sight) -> str:
    from newsroom import locations
    return locations.get(s.place[0]).name


# The field notebook: the spare minutes, an angle at a time on tonight's sights, never the same one twice a night.
NOTEBOOK = (
    "HOW TO TELL IT: how to tell {what} from what it might be mistaken for",
    "WHAT IT EATS: what it's after, and how it finds it",
    "WHERE TO WATCH: the best spot and time of day this week, and how to keep your distance",
    "FROM THE WARDEN'S NOTEBOOK: one memory from Rowan's thirty years on the reserve, of {what}",
    "THE WEATHER AND THE TIDE: how this week's weather and tides suit {what}",
    "A QUIET MOMENT: Rowan says almost nothing, three or four short lines while we watch {what}",
)


def _item(ep: dict, token: str) -> dict:
    """What an item is: its kind, its sight, where, when and how it's filmed."""
    lead, near = _sights(ep)
    kind, n = token[0], int(token[1:]) if token[1:].isdigit() else 0
    if token in ("open", "close"):
        return {"kind": token, "sight": lead, "tod": "dusk" if token == "close" else "day"}
    if kind == "w":
        s = near if (n == SEQUENCES - 1 and near) else lead
        w = ep["watches"][min(n, len(ep["watches"])) - 1]
        shot = "wide" if creatures.shot_for(s.creature) == "wide" else (w.get("shot") or "close")   # flocks: wide
        return {"kind": "watch", "n": n, "sight": s, "shot": shot,
                "angle": w["angle"], "tod": s.tod}
    if kind == "m":
        return {"kind": "meet", "n": n, "sight": lead, "meet": ep["meets"][min(n, len(ep["meets"])) - 1],
                "tod": "day"}
    sights = [s for s in (lead, near) if s]
    s = sights[(n - 1) % len(sights)]
    angle = NOTEBOOK[((n - 1) // len(sights)) % len(NOTEBOOK)]
    return {"kind": "spare", "n": n, "sight": s, "shot": creatures.shot_for(s.creature), "angle": angle,
            "tod": s.tod}


def _token(brief: str) -> str | None:
    m = TOKEN.search(brief or "")
    return m.group(1) if m else None


def brief_for(world: World, brief: str) -> str:
    ep = booked(world)
    tok = _token(brief)
    if tok is None:
        return brief
    it = _item(ep, tok)
    s, place = it["sight"], _place(it["sight"])
    if it["kind"] == "open":
        return (f"THE OPENING, Rowan to camera at {place}: \"Hello, and welcome to {TITLE}\", where we are and what "
                f"we've come to see: {s.what}. Filmed earlier, by day: no time of day")
    if it["kind"] == "close":
        return (f"THE CLOSE, Rowan to camera at {place} in the last of the light: {ep['close']} Then goodbye until "
                "next time, without saying when or what's next")
    if it["kind"] == "meet":
        m = it["meet"]
        return (f"ROWAN MEETS {m['name']} ({m['role']}) out at {place}, about {s.what}: {m['talk']} They talk as "
                "people do outdoors, side by side, looking at the same thing")
    shot = "a close-up, one creature filling the frame" if it["shot"] == "close" else "a wide, the place and the flock"
    if it["kind"] == "spare":
        return (f"A FIELD-NOTEBOOK MOMENT in the hide ({shot}), on {s.what}: "
                + it["angle"].format(what=s.what) + ". Only Rowan speaks, four to six lines, about this and nothing "
                "else: no fact, phrase or number from SAID ALREADY")
    out = (f"SEQUENCE {it['n']} of {SEQUENCES}, in the hide ({shot}), on {s.what}: {it['angle']} Only Rowan speaks, "
           "six to nine lines, low and unhurried: the pictures carry it")
    if it["n"] == 1:
        out += f". THE FACTS, said here and not again tonight: {s.note}"
        if ep.get("count") is not None:
            out += f" THE NUMBER: {ep['count']} {ep['counted']}: say it once, exactly"
    elif s.id != ep["sight"]:
        out += f". ITS FACTS: {s.note}"
    return out


def for_prompt(world: World) -> str:
    ep = booked(world)
    lead, near = _sights(ep)
    with world.lock:
        aired = [a for a in world.archive if a["date"] == world.last_date and a.get("show") == SHOW
                 and a["type"] != T.ad_break.value]
    # The sight by name only: with its facts and number in every prompt, the first model run said "eight little
    # egrets" and "thirty years ago there were none on this coast" in nearly every item. They are in the first
    # sequence's brief (brief_for), and everything said tonight is here in full.
    out = (f"THIS EPISODE: \"{ep['title']}\", about {lead.what}" + (f", with {near.what}" if near else "")
           + "\nTHE SEASON (mention nothing else that lives here): "
           + "; ".join(s.what for s in seasons.in_season(_day(world).month))
           + "\nWHO ROWAN MEETS: " + "; ".join(f"{m['name']} ({m['role']})" for m in ep["meets"]))
    if aired:
        out += ("\nSAID ALREADY TONIGHT, in order (never again: not a fact, not a number, not a phrase, and not the "
                "way an item opens):\n" + "\n".join(f"  - {a['text'][:SAID_CHARS]}" for a in aired))
    return out


def after(seg, world: World) -> None:
    """Out on location, filmed by day; Rowan's narration over a creature is the hide view."""
    ep = tonight(world)
    tok = _token(seg.brief)
    if not ep or tok is None:
        return
    it = _item(ep, tok)
    s = it["sight"]
    for line in seg.lines:                    # filmed by day, whatever slipped through
        for pat, day in DAYTIME:
            line.text = pat.sub(lambda m, d=day: d.capitalize() if m.group(0)[0].isupper() else d, line.text)
    seg.work["location"], seg.work["tod"], seg.work["filmed"] = s.place[0], it["tod"], True
    if it["kind"] in ("watch", "spare"):
        facing = -1 if random.Random(f"{ep['date']}-{tok}").random() < 0.5 else 1
        seg.work["hide"] = {"backdrop": s.place[0], "spot": s.place[1], "creature": s.creature,
                            "shot": it["shot"], "facing": facing, "label": TITLE.upper()}


def check(seg, script, world: World) -> None:
    """Narration is Rowan's alone; a meeting is Rowan and the resident booked for it."""
    ep = tonight(world)
    tok = _token(seg.brief)
    if not ep or tok is None:
        return
    it = _item(ep, tok)
    if it["kind"] == "meet":
        name = it["meet"]["name"].strip().lower()
        top = (getattr(script, "guest_name", "") or "").strip().lower()
        guests = {(getattr(l, "guest_name", None) or top).strip().lower()           # an interview names its guest
                  for l in script.lines if l.speaker == "guest"}                    # once, a panel on each line
        if guests - {name} or top not in (name, ""):
            raise llm.LLMError(f"{seg.brief} has someone other than {it['meet']['name']}")
    elif any(l.speaker != "naturalist" for l in script.lines):
        raise llm.LLMError(f"{seg.brief} has a voice other than Rowan's")


def caption(world: World, name: str) -> str | None:
    ep = tonight(world)
    m = next((m for m in (ep or {}).get("meets", []) if m["name"] == name), None)
    return m["role"][:60] if m else None


def view(seg, v, line_idx: int) -> None:
    """player.VIEW_HOOKS: filmed, not live; the hide's items in the hide."""
    if not seg.work.get("filmed"):
        return
    v.tag = ""
    if seg.work.get("hide"):                 # no caption over the creature: the pictures carry it
        v.mode, v.scene, v.lower_third = "hide", seg.work["hide"], None
        v.backdrop, v.tod = seg.work["hide"]["backdrop"], seg.work.get("tod") or v.tod


def draw_scene(canvas, v, t: float) -> None:
    """scenes.SCENES["hide"]: the creature in the hide, from the view's scene."""
    h = v.scene or {}
    if not h.get("backdrop"):
        from newsroom.scenes import draw_studio
        return draw_studio(canvas, v, t)
    creatures.draw_hide(canvas, h["backdrop"], h["spot"], h["creature"], t, tod=v.tod, wx=v.weather,
                        shot=h.get("shot") or "close", facing=h.get("facing", 1), label=h.get("label", ""),
                        feet=ON_AIR_FEET)


# ------------------------------------------------------------------ with no model

def template(seg_type, world, rng: random.Random, part: str, work: dict, brief: str):
    """Tideline with no model: Rowan on tonight's sight, from the booking and the seasonal list's facts."""
    from newsroom.models import BulletinScript, GuestLine, InterviewScript, LiveLine

    ep = booked(world)
    tok = _token(brief)
    if tok is None:
        return None
    it = _item(ep, tok)
    s = it["sight"]
    facts = [x.strip() + "." for x in s.note.split(".") if x.strip()]
    if it["kind"] == "meet":
        m = it["meet"]
        said = [("naturalist", f"I've brought {m['name']} out with me. You know this place better than most."),
                ("guest", "I've been coming down here a long time, Rowan."),
                ("naturalist", f"And {s.what}? What do you make of it this year?"),
                ("guest", "Same as ever, and different every time. That's why I keep coming."),
                ("naturalist", "That's the best answer I've heard.")]
        return InterviewScript(lines=[GuestLine(speaker=w, text=x) for w, x in said],
                               headline=f"Rowan meets {m['name']}", lower_third=TITLE,
                               guest_name=m["name"], guest_role=m["role"][:60])
    if it["kind"] == "open":
        said = ["Hello, and welcome to Tideline.", f"We're out at {_place(s)}.",
                f"And we've come to see {s.what}.", "Keep your voice down. Let's go and look."]
    elif it["kind"] == "close":
        said = [f"That's {s.what}, for this time.", ep["close"], "Until next time. Keep your eyes open."]
    else:
        said = facts[:5] or [f"There. {s.what[0].upper() + s.what[1:]}.", "Just watch."]
        if it["kind"] == "watch" and it["n"] == 1 and ep.get("count") is not None:
            said = said[:3] + [f"I make it {ep['count']} {ep['counted']} today."] + said[3:]
    return BulletinScript(lines=[LiveLine(speaker="naturalist", text=x) for x in said],
                          headline=f"{TITLE}: {s.what}"[:80], lower_third=TITLE)


# ------------------------------------------------------------------ the show

def show_def() -> Show:
    """The opening, SEQUENCES sequences (the first MEETS with a resident after), the field notebook for spare minutes
    (three, then a break, as a lap), and the close at the end of the slot."""
    seqs: list = []
    for k in range(1, SEQUENCES + 1):
        seqs.append(I(T.links, brief="{w%d}" % k, target_s=75.0))
        if k <= MEETS:
            seqs.append(I(T.interview, brief="{m%d}" % k, target_s=150.0))
    spares = tuple(I(T.links, brief=tuple("{x%d}" % (k + 1 + 3 * lap) for lap in range(SPARES // 3)), target_s=60.0)
                   for k in range(3))
    return Show(
        SHOW, TITLE.upper(), TITLE.upper(), (60, 110, 80),
        pattern=(T.bumper, I(T.links, "open", brief="{open}", target_s=45.0), *seqs, *spares, T.ad_break),
        loop_from=2 + len(seqs),
        closing=(I(T.links, "close", brief="{close}", target_s=45.0),),
        target_s={T.bumper: 10.0, T.links: 70.0, T.interview: 150.0, T.ad_break: 60.0},
        cast=("naturalist",), lead="naturalist",
        cast_by_type={T.links: ("naturalist",), T.interview: ("naturalist", "guest")},
        station=f"{TITLE}, the wildlife programme on Channel 8, Port Wexley's second channel, with Rowan Polglase",
        tone="quiet, warm and wondering: an old warden showing you something he loves, never a lecture",
        light=True, repeats_overnight=False,
    )


_RULES = """
This is part of TIDELINE, a wildlife film on Channel 8, presented by Rowan Polglase ("naturalist"), for thirty years
the warden of the Salting reserve, retired in 2021: unhurried, warm, quietly delighted, speaking low so as not to
disturb anything. It was FILMED EARLIER, BY DAY, out on the town's coast: never "tonight", "this evening", "good
evening" or "live"; say "today" or "this week". THIS EPISODE gives the sight, its facts and its number: keep to them,
say the number exactly as written, and mention no creature that isn't in THE SEASON. Nobody says "good evening",
the residents neither, and nobody gives the time of day or the clock ("coming up to nine o'clock"). Every item is new: nothing from SAID ALREADY TONIGHT again, no fact, no number, no phrase, and
each opens its own way (not "keep still" or "let your eyes settle" once an earlier item has). Real natural history in plain
words, the way a warden talks, not a textbook. No real organisations, charities or people. Not news: thread_id is
null. headline = what we see, in under 10 words. lower_third = "Tideline" plus a short tag.
"""

SYSTEMS = {
    T.links: _COMMON_RULES + _RULES + """
These are Rowan's words alone ("naturalist" only, every line), as THIS ITEM says: to camera, or his voice over the
pictures in the hide. Short lines; leave room for the pictures.
""",
    T.interview: _COMMON_RULES + _RULES + """
This is Rowan out on location with ONE resident, the one THIS ITEM names: speaker "guest", with guest_name their exact
name and guest_role their role. Twelve to sixteen lines. They talk more than Rowan; Rowan asks, listens and adds one
thing of his own. Nothing about their own life beyond what they do and what they've seen out here: no husband or
wife, no family stories (the second model run gave a counter a husband she never had). If
WHO ROWAN MEETS or the briefing says what they're known for, keep to it: no new history for them.
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


def register():
    """Put Tideline on air through the engine's registries. Returns an undo."""
    from newsroom import assets, player, scenes, workers, writers

    sh = show_def()
    schedule.SHOWS[SHOW] = sh
    assets.IDENTS[SHOW] = (assets.CONFIG.paths.assets / "bumper_tideline.wav", IDENT)
    assets.IDENT_MUSIC[SHOW] = "outabout"               # folk, until it has music of its own (by ear)
    assets.IDENT_VOICES[SHOW] = CONFIG.tts.voices.get("naturalist", "bm_polglase")
    player.SEATS[SHOW] = 1
    player.VIEW_HOOKS[SHOW] = view
    player.AIRED_HOOKS[SHOW] = aired
    scenes.SCENES["hide"] = draw_scene
    jobs = (should_commission, commission)
    workers.IDLE_JOBS.append(jobs)
    writers.SHOW_SYSTEMS[SHOW] = SYSTEMS
    writers._PLACE.update(PLACE)
    writers.BRIEF_HOOKS[SHOW] = brief_for
    writers.PROMPT_HOOKS[SHOW] = for_prompt
    writers.TEMPLATE_HOOKS[SHOW] = template
    writers.CHECK_HOOKS[SHOW] = check
    writers.AFTER_HOOKS[SHOW] = after
    writers.CAPTION_HOOKS[SHOW] = caption
    writers.BOOKED_SHOWS.add(SHOW)                      # its residents are booked: no loose ends
    writers.UNFILED_SHOWS.add(SHOW)                     # never news
    undo_creative = creative.register(
        SHOW, TITLE, kind="factual", vetted=True, airs_at=AIRS_AT,
        brief=("A wildlife series on the town's own coast, filmed by day: Rowan Polglase, thirty years the warden of "
               "the Salting reserve, unhurried and quietly delighted, shows one creature of the season in five "
               "sequences and meets three residents out there. It is canon: what it shows is true in the town."),
        decides=("the title; the five sequences' angles and shots; the three residents met and what each tells him; "
                 "the close. The sight and its number are chosen in code, with their rests: not the planner's"),
        digest=digest, aired=lambda world: [ep["date"] for ep in aired_episodes(world)], books=should_commission)

    def undo() -> None:
        undo_creative()
        schedule.SHOWS.pop(SHOW, None)
        for reg in (assets.IDENTS, assets.IDENT_MUSIC, assets.IDENT_VOICES, player.SEATS, player.VIEW_HOOKS,
                    player.AIRED_HOOKS, writers.SHOW_SYSTEMS, writers.BRIEF_HOOKS, writers.PROMPT_HOOKS,
                    writers.TEMPLATE_HOOKS, writers.CHECK_HOOKS, writers.AFTER_HOOKS, writers.CAPTION_HOOKS):
            reg.pop(SHOW, None)
        scenes.SCENES.pop("hide", None)
        for key in PLACE:
            writers._PLACE.pop(key, None)
        if jobs in workers.IDLE_JOBS:
            workers.IDLE_JOBS.remove(jobs)
        writers.BOOKED_SHOWS.discard(SHOW)
        writers.UNFILED_SHOWS.discard(SHOW)
    return undo
