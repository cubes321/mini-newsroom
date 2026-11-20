"""The Coast Road: Channel 8's travelogue at 20:40, on the nights Tideline doesn't air (docs/FACTUAL.md).

A town celebrity's journey round the Greymouth coast in six legs, one a night. The first series' host is **Lorna
Quayle** (chosen 2026-11-14 from four; data/contact-sheets/2026-11-14-travelogue-hosts.png): the town's most-seen
comedian and singer, whose running story is waiting. She makes the journey by every slow way there is, collecting
waiting stories. It is canon: the residents she meets are the town's, and remember it.

- **She stays a resident.** Making her a presenter would have had `World.drop_presenter_people` delete her resident
  record (73 appearances, her memories) at the next load. So every line is a "guest" line with its speaker's name,
  as Marina Row's are (writers.DEBATE_SHOWS), and her look (A of three, data/contact-sheets/2026-11-14-lorna-quayle-looks.png)
  and voice (`bf_quayle`, C of three) are pinned to her name on Channel 8. Her voice moves to `bf_quayle` in the
  town too, at the first leg, so Channel 7 hears her in it. Channel 7 still draws her as before.
- **The route** is planned once a series, in one back-office call: a title, her reason for the journey, and six
  legs, each with how she travels and three stops, each stop with its backdrop, its place, what happens there and a
  resident to meet. A route saved by `python -m entertainment.travelogue --plan` (data/travelogue/<host>.json) is
  used as it stands, so the user can read it first; if neither exists the call is made at the first booking. If it
  fails, a stand-in route made in code takes its place.
- **A leg** is the opening, which arrives at the first stop, then a meeting with each stop's resident and between
  them the road, which ends on the arrival at the next stop; waiting moments for spare minutes (three, then a break,
  round again), and the close at dusk. (Until 2026-11-16 each stop had an arrival item of its own, and every place
  was arrived at two or three times; the user cut them.) Each brief says where the leg has got to (`day_so_far`). It
  is filmed by day, with no LIVE tag, in its own view (scenes.SCENES["road"], player.VIEW_HOOKS).
- **Aired** is stamped when a leg's first meeting goes out (player.AIRED_HOOKS); the next leg follows the last aired
  one. After the sixth, the series is over and Tideline has the slot every night until the user picks a new host.
- **The alternation** (`schedule.ROTATIONS`, which wildlife.py's slot shares): on a Channel 8 night the slot goes to
  whichever series aired less recently before today, by the world's records, not the weekday, since the channels
  alternate nights.
"""
from __future__ import annotations

import json
import logging
import random
import re
from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field

from newsroom import geography, llm, schedule
from newsroom.config import CONFIG
from newsroom.models import SegmentType as T
from newsroom.schedule import Item as I, Show
from newsroom.sprites import Look
from newsroom.world import World

from . import creative

log = logging.getLogger(__name__)

SHOW = "coastroad"
TITLE = "The Coast Road"
HOST = "Lorna Quayle"
HOST_VOICE = "bf_quayle"
# A canary-yellow raincoat over a navy top, gold earrings, a ready grin; her skin, hair and ponytail as the town knows them.
HOST_LOOK = Look(skin=(232, 190, 160), hair=(150, 110, 60), top=(232, 190, 40), under=(40, 52, 96),
                 hair_style="ponytail", top_style="jacket", extra="earrings", extra_col=(220, 180, 60), mouth="smile",
                 brows="raised")
HOST_ABOUT = ("a comedian and singer, the town's best-known; her running story is waiting: fourteen minutes at the "
              "Saltby ferry office for a biscuit, a tin of parkin that won over the sorting office, and a waiting club")
# What every item is told of her: the biscuit story only in the first leg's opening (the run on 2026-11-14 had every
# item tell it: "fourteen" sixteen times in one leg).
HOST_SHORT = "a comedian and singer, the town's best-known, whose running story is waiting"
LEGS = 6
STOPS = 3
# 2026-11-19: with meetings of 150 s and roads of 80 the leg came to twelve minutes of twenty, and eight waiting
# moments filled the rest ("waits on the Saltby slip" three times); longer meetings and roads leave about three.
MEETING_S = 210.0
ROAD_S = 100.0
SPARES = 12
AIRS_AT = "20:40"
BOOK_FROM = "18:30"
TASK = "travelogue" if "travelogue" in CONFIG.llm.routes else "chamber"
# The route is planned once a series. Sonnet's fallback ran out at 16000 with the map in its prompt, and planned
# one that kept to it first time at 32000 (2026-11-20 rehearsals), as soap.py's plan does. Flash's thinking spends
# the lot, 16000 or 32000, and answers nothing, with or without the map: a `travelogue` route to Sonnet would skip it.
PLAN_TOKENS = 32000
PLAN_TIMEOUT_S = 420.0
IDENT = "The Coast Road, with Lorna Quayle. On Channel 8."
SAID_CHARS = 3000                       # each item said so far, in full (a meeting is about 2,000)
TOKEN = re.compile(r"\{(open|close|a[0-9]+|m[0-9]+|r[0-9]+|x[0-9]+)\}")
# Where the stops may be: the town's places out and about (not the studios, the council chamber or the police).
STOP_BACKDROPS = ("harbour", "slipway", "fish_quay", "lighthouse", "lifeboat_station", "seafront", "coast_road",
                  "woods", "estuary", "village", "village_hall", "tea_room", "dining_room", "market", "main_street",
                  "farm", "cannery", "quarry_field", "pub", "town_hall")
# How she travels decides where the road and the waiting are filmed.
TRAVEL = ((re.compile(r"ferry|boat|crossing", re.I), "slipway"), (re.compile(r"bus|coach", re.I), "main_street"),
          (re.compile(r".", re.I), "coast_road"))


def _road(travel: str) -> str:
    return next(b for pat, b in TRAVEL if pat.search(travel or ""))


# ------------------------------------------------------------------ the record

def state(world: World) -> dict:
    with world.lock:
        return world.travelogue.setdefault("series", []), world.travelogue.setdefault("legs", [])


def series(world: World) -> dict | None:
    """The host's series in hand: the newest for HOST."""
    all_, _ = state(world)
    return next((s for s in reversed(all_) if s.get("host") == HOST), None)


def aired_legs(world: World, before: str | None = None) -> list[dict]:
    _, legs = state(world)
    return [l for l in legs if l.get("aired") and (before is None or l["date"] < before)]


def tonight(world: World) -> dict | None:
    _, legs = state(world)
    return next((l for l in reversed(legs) if l["date"] == world.last_date), None)


def finished(world: World) -> bool:
    """Has the host's series aired all its legs? Then Tideline has the slot every night until a new host."""
    s = series(world)
    return bool(s) and len({l["n"] for l in aired_legs(world) if l.get("made") == s["made"]}) >= LEGS


# ------------------------------------------------------------------ the route, in the back office

class Stop(BaseModel):
    backdrop: Literal[STOP_BACKDROPS] = Field(description="where it is filmed")
    place: str = Field(min_length=3, max_length=80, description="the place, as Lorna would name it")
    where: str = Field(default="", max_length=40, description="where it is on THE COAST: the id of the place, or of "
                                                              "the nearest one")
    what: str = Field(min_length=8, max_length=400, description="what happens there, in a sentence or two")
    meet: str = Field(min_length=3, max_length=40, description="the resident she meets: an exact name from PEOPLE, or "
                                                                "a new resident's first name and surname")
    role: str = Field(min_length=3, max_length=80, description="who they are, as their caption would say")
    gender: str = Field(default="", max_length=1, description="'f' or 'm'")
    age: str = Field(default="", max_length=6, description="young, middle or old")
    talk: str = Field(min_length=8, max_length=400, description="what they talk about, in a sentence or two")


class Leg(BaseModel):
    title: str = Field(min_length=3, max_length=60)
    travel: str = Field(min_length=3, max_length=200, description="how she gets along this leg: the ferry, a bus, a "
                                                                   "borrowed bike, on foot")
    stops: list[Stop] = Field(min_length=STOPS, max_length=STOPS)
    ends: str = Field(min_length=3, max_length=200, description="where she ends up, and how the next leg starts")


class Route(BaseModel):
    """The Coast Road's journey (entertainment/travelogue.py)."""
    title: str = Field(min_length=3, max_length=60, description="the series' subtitle")
    why: str = Field(min_length=8, max_length=400, description="her own reason for the journey, in a sentence or two")
    legs: list[Leg] = Field(min_length=LEGS, max_length=LEGS)


_SYSTEM = """\
You plan THE COAST ROAD, a travelogue on Channel 8, Port Wexley's second television channel, in the FICTIONAL town
in the briefing. Its host is {host}: {about}. She goes round the Greymouth coast in {legs} legs, one an episode, by
every slow way there is (the foot ferry, the bus, a borrowed bike, on foot), and collects waiting stories as she goes.
Plan the journey:
- title: the series' subtitle, a few words. why: her own reason for making it, in a sentence or two, from what the
  town knows of her: nothing new about her family or her past.
- legs: {legs} of them, in order round the coast, starting and ending in Port Wexley. Each says how she travels, has
  {stops} stops on the town's own places (a backdrop from the list, the place as she'd name it, `where` it is on THE
  COAST, what happens there) and ends where the next one starts. THE COAST is the map: a leg's stops run one way
  along it, in the order she reaches them by its travel, each further on than the last: never back to a place she
  has left. She crosses the Grey only by the foot ferry, from the Quay Steps (harbour) or the Saltby slip, after the
  leg's stops on that side, or round by Polgrey Bridge. A leg starts on the side of the water where the last one
  ended. (2026-11-20: a ferry leg from the town quay stopped at the fish quay, in town, then crossed.)
- at each stop, one resident she meets, with something of their own: a job, a place, a long wait of some kind. People
  from PEOPLE first (their exact names); keep to what PEOPLE says of them and give them no new history. A new resident
  only if nobody there fits, with a job that fits the place. Never a presenter, nobody twice in the whole journey.
The legs air over about a month, one every few days: nothing at a stop may hang on a date or on news that will be
over by then (no "Monday", no "the seventeenth", no award, survey, vote or event still to come); a place, a job, a
long habit, a story from years back. The first draft (2026-11-14) had a crane booked for the seventeenth and Monday's
committee.
Warm and funny, never cruel: she laughs with people, not at them. Places and people from the briefing; invent no new
town or landmark. No real organisations or people. Return ONLY JSON.
"""


def _people(world: World) -> list:
    """Residents the town knows, the most seen first, to meet along the way."""
    return sorted((p for p in world.people if p.kind in ("resident", "worthy") and p.name != HOST
                   and all(w[:1].isupper() for w in p.name.split())), key=lambda p: -p.appearances)[:50]


def _check(route: Route, world: World) -> None:
    names = [s.meet.strip().lower() for leg in route.legs for s in leg.stops]
    if len(set(names)) != len(names):
        raise llm.LLMError("the route meets someone twice")
    for leg in route.legs:
        for s in leg.stops:
            if world.presenter_named(s.meet) or s.meet.strip().lower() == HOST.lower():
                raise llm.LLMError(f"{s.meet} is a presenter or the host, not a resident to meet")
    if wrong := route_trouble(route.model_dump()["legs"]):
        raise llm.AskAgain("THE ROUTE GOES AGAINST THE MAP (THE COAST): " + "; ".join(wrong)
                           + ". Plan it again so every leg runs one way along THE COAST.")


def route_trouble(legs: list[dict]) -> list[str]:
    """Where a route's legs go against the gazetteer (newsroom/geography.py): back on themselves, across the Grey
    without the ferry, starting on the other side of the water from where the last leg ended, or a journey that
    doesn't start and end in Port Wexley."""
    return geography.check_legs([
        (leg["title"], leg["travel"], [geography.Placed(s["place"], geography.place_for(
            s["place"], s["backdrop"], s.get("where", ""))) for s in leg["stops"]], leg.get("ends", ""))
        for leg in legs], round_trip=True)


def _leg_text(i: int, leg: dict) -> str:
    return (f"  Leg {i}: {leg['title']} ({leg['travel']})\n" + "\n".join(
        f"    - {s['place']} [{s['backdrop']}]: {s['what']} Meets {s['meet']}, {s['role']}: {s['talk']}"
        for s in leg["stops"]) + f"\n    Ends: {leg['ends']}")


def _route_text(route: Route) -> str:
    r = route.model_dump()
    return f"\"{r['title']}\": {r['why']}\n" + "\n".join(_leg_text(i, leg) for i, leg in enumerate(r["legs"], 1))


def _asked(world: World) -> str:
    """What the route's planner is asked, apart from the town's briefing: the creative editor reads this much too."""
    return ("PEOPLE:\n" + "\n".join(f"  - {p.name}, {p.role}" for p in _people(world))
            + "\n\n" + geography.coast_text()
            + "\n\nBACKDROPS for the stops: " + ", ".join(STOP_BACKDROPS)
            + creative.for_planner(world, SHOW, series=True))


def _ask(system: str, user: str) -> Route:
    return llm.complete_json(TASK, Route, system, user, max_tokens=PLAN_TOKENS, timeout_s=PLAN_TIMEOUT_S)


def plan_route(world: World, unhurried: bool = False) -> dict:
    """The series' route: the model's (or the stand-in's), not yet recorded. The creative editor reads it and may
    send it back once; `unhurried` for a route planned ahead by hand, days from air (the CLI)."""
    asked = _asked(world)
    user = f"BRIEFING\n{world.summary_for_editor()}\n\n{asked}"
    system = _SYSTEM.format(host=HOST, about=HOST_ABOUT, legs=LEGS, stops=STOPS)
    try:
        route = _ask(system, user)
        try:
            _check(route, world)
        except llm.AskAgain as e:                       # off the map: once more, told where
            log.info("coast road: the route goes against the map (%s); asking once more", str(e)[:300])
            route = _ask(system, f"{user}\n\nYOUR FIRST DRAFT of the route:\n{_route_text(route)}\n\n{e}")
            _check(route, world)
        route = creative.redraft(world, SHOW, "route", route, text=_route_text, context=asked, margin=not unhurried,
                                 check=lambda r: _check(r, world),
                                 again=lambda more: _ask(system, user + more))
        return {**route.model_dump(), "stand_in": False}
    except llm.LLMError as e:
        log.warning("coast road: no route (%s); the stand-in route takes the series", e)
        return {**_stand_in_route(), "stand_in": True}


def _saved_route_path():
    slug = re.sub(r"[^a-z]+", "_", HOST.lower()).strip("_")
    return CONFIG.paths.data / "travelogue" / f"{slug}.json"


def _start_series(world: World) -> dict:
    """The host's route: one saved for the user to read first, or planned now."""
    path = _saved_route_path()
    route = None
    if path.exists():
        try:
            route = json.loads(path.read_text(encoding="utf-8"))
            Route.model_validate({k: route[k] for k in ("title", "why", "legs")})
            if wrong := route_trouble(route["legs"]):
                raise ValueError("it goes against the map: " + "; ".join(wrong))
            log.info("coast road: the route saved in %s", path)
        except (ValueError, KeyError) as e:
            log.warning("coast road: the saved route in %s won't do (%s); planning one", path, e)
            route = None
    route = route or plan_route(world)
    entry = {"host": HOST, "made": f"{world.last_date}#{HOST}", **route}
    for leg in entry["legs"]:
        for s in leg["stops"]:
            if known := world.person_by_name(s["meet"]):          # their role is the town's, not the plan's
                s["role"] = known.role[:80]
            else:
                world.ensure_person(s["meet"], s["role"], "resident", gender=s.get("gender") or None,
                                    age=s.get("age") or None, accent="british")
    all_, _ = state(world)
    with world.lock:
        all_.append(entry)
    log.info("coast road: %s's route, %r: %s", HOST, entry["title"], " / ".join(l["title"] for l in entry["legs"]))
    return entry


def _cast_host(world: World) -> None:
    """Her voice is hers in the town too, from the first leg, so Channel 7 hears her in it."""
    p = world.person_by_name(HOST)
    if p is not None and p.voice != HOST_VOICE:
        with world.lock:
            p.voice = HOST_VOICE
        log.info("coast road: %s speaks in %s from now", HOST, HOST_VOICE)


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def should_commission(world: World, now: float | None = None) -> bool:
    now = now or schedule.now()
    return (tonight(world) is None and _at(BOOK_FROM, now) <= now < _at(AIRS_AT, now) + 20 * 60
            and schedule.show_at(_at(AIRS_AT, now)).id == SHOW)


def commission(world: World) -> dict:
    """Book tonight's leg: the next after the last aired one, on the host's route (planned now if need be)."""
    _cast_host(world)
    s = series(world) or _start_series(world)
    done = {l["n"] for l in aired_legs(world) if l.get("made") == s["made"]}
    n = min((k for k in range(1, LEGS + 1) if k not in done), default=LEGS)
    entry = {"date": world.last_date, "made": s["made"], "n": n, "aired": False}
    _, legs = state(world)
    with world.lock:
        legs[:] = [l for l in legs if l["date"] != world.last_date] + [entry]
        del legs[:-200]
    log.info("coast road: tonight leg %d of %d, %r", n, LEGS, s["legs"][n - 1]["title"])
    return entry


def booked(world: World) -> tuple[dict, dict]:
    """Tonight's leg entry and its plan from the route."""
    entry = tonight(world) or commission(world)
    s = next(x for x in state(world)[0] if x["made"] == entry["made"])
    return entry, s


def aired(seg, world: World) -> None:
    """player.AIRED_HOOKS: the leg's first meeting went out: the next booking moves on to the leg after. (The first
    stop's arrival item until 2026-11-16, when the arrival items went and the opening took the first stop.)"""
    if seg.brief != "{m1}":
        return
    entry = tonight(world)
    if entry and not entry.get("aired"):
        with world.lock:
            entry["aired"] = True
        log.info("coast road: leg %d aired", entry["n"])


def digest(world: World, day: str) -> str:
    """The leg that aired on `day`, as the creative editor reads it afterwards; "" for none, or the stand-in route.
    A leg has no planner of its own (it is the route's): the editor's notes wait for the next series' route."""
    all_, legs = state(world)
    entry = next((l for l in legs if l["date"] == day), None)
    s = next((x for x in all_ if entry and x["made"] == entry["made"]), None)
    if not s or s.get("stand_in"):
        return ""
    return (f"\"{s['title']}\" with {s['host']}: {s['why']}\nLeg {entry['n']} of {len(s['legs'])}:\n"
            + _leg_text(entry["n"], s["legs"][entry["n"] - 1]))


def enrol():
    """Enrol The Coast Road with the creative editor: its route is read before it stands, and each leg after it has
    aired. Returns an undo."""
    return creative.register(
        SHOW, TITLE, kind="factual", vetted=True, airs_at=AIRS_AT,
        brief=(f"A travelogue round the Greymouth coast in {LEGS} legs, one an episode, by every slow way there is: "
               f"{HOST}, {HOST_SHORT}, arrives at {STOPS} stops a leg and meets a resident at each. Warm and funny, "
               "never cruel. It is canon: the residents met remember it."),
        series_decides=("the next series' route: its legs, how the host travels each, the stops, the resident met at "
                        "each and what they talk about"),
        digest=digest, aired=lambda world: [l["date"] for l in aired_legs(world)])


# ------------------------------------------------------------------ the alternation

def rotation(day: date) -> str | None:
    """schedule.ROTATIONS for the 20:40 slot: the travelogue on the nights it's its turn, else None (Tideline).
    Whichever aired less recently before `day` goes on; tonight's booking, once made, holds it for the night."""
    from newsroom import world as world_mod

    w = world_mod.current()
    if w is None:
        return None
    d = day.isoformat()
    _, legs = state(w)
    if any(l["date"] == d for l in legs):         # tonight's holds, even the last leg once its first stop has aired
        return SHOW
    if finished(w):
        return None
    if any(ep["date"] == d for ep in w.wildlife.get("episodes", [])):
        return None
    last_road = max((l["date"] for l in legs if l.get("aired") and l["date"] < d), default="")
    last_wild = max((ep["date"] for ep in w.wildlife.get("episodes", []) if ep.get("aired") and ep["date"] < d),
                    default="")
    if not last_road and not last_wild:
        return None                                   # Tideline first
    return SHOW if last_wild > last_road else None


# ------------------------------------------------------------------ the items

def _item(entry: dict, s: dict, token: str) -> dict:
    leg = s["legs"][entry["n"] - 1]
    kind, k = token[0], int(token[1:]) if token[1:].isdigit() else 0
    stops = leg["stops"]
    if token == "open":
        return {"kind": "open", "backdrop": stops[0]["backdrop"], "tod": "day", "leg": leg}
    if token == "close":
        return {"kind": "close", "backdrop": stops[-1]["backdrop"], "tod": "dusk", "leg": leg}
    if kind in "am":
        stop = stops[min(k, STOPS) - 1]
        return {"kind": "arrive" if kind == "a" else "meet", "k": k, "stop": stop, "backdrop": stop["backdrop"],
                "tod": "day", "leg": leg}
    if kind == "r":
        return {"kind": "road", "k": k, "backdrop": _road(leg["travel"]), "tod": "day", "leg": leg,
                "to": stops[min(k, STOPS - 1)]}
    # At the last stop: the waits come after the last meeting. Filmed on the travel backdrop and told only how she
    # travels, the 2026-11-20 evening's had her back at the town quay waiting for the ferry, and "still on the boat",
    # after she had landed at the Saltby slip.
    return {"kind": "wait", "k": k, "backdrop": stops[-1]["backdrop"], "tod": "day", "leg": leg}


WAITING = (
    "A WAITING STORY: Lorna tells one from her collection, from someone she met on the way (not one met on camera)",
    "THE VIEW WHILE SHE WAITS: what she can see from where she's waiting, and what she makes of it",
    "THE SIGN: Lorna reads what a sign or a notice where she is says, and what actually happens there",
    "THE WAITING CLUB: a new rule for her waiting club, from today",
    "A SONG WHILE SHE WAITS: a few lines of something she makes up about the journey so far, said, not sung",
    "THE SNACK: what she brought to eat while waiting, and what's left of it",
)


def _token(brief: str) -> str | None:
    m = TOKEN.search(brief or "")
    return m.group(1) if m else None


def _place(backdrop: str) -> str:
    from newsroom import locations
    return locations.get(backdrop).name


def _said_today(world: World) -> list[str]:
    """Each item written today, in order, in full: from its cache entry, since the archive keeps only its first 400
    characters (and an item's later lines are where a meeting establishes things: the brakes tested on the hill)."""
    from newsroom.config import CONFIG

    with world.lock:
        entries = [a for a in world.archive if a["date"] == world.last_date and a.get("show") == SHOW
                   and a["type"] != T.ad_break.value]
    out = []
    for a in entries:
        words = ""
        if a.get("hash"):
            try:
                seg = json.loads((CONFIG.paths.cache / f"{a['hash']}.json").read_text(encoding="utf-8"))
                words = " ".join(l.get("text", "") for l in seg.get("lines", []) if l.get("text"))
            except (OSError, ValueError):
                pass
        out.append(words or a.get("text") or "")
    return out


ORDER_STEPS = ("open", *(t for k in range(1, STOPS + 1) for t in (f"m{k}",) + ((f"r{k}",) if k < STOPS else ())),
               "close")                     # as show_def: no arrival items since 2026-11-16


def how(leg: dict) -> str:
    """How she travels, without the leg's joke: "On foot from the lighthouse gate" of "On foot from the lighthouse gate,
    down the estuary path... boots, not the good shoes". The whole line is the opening's; given to every item, the
    boots came up in nine items of ten, and leg 3's brakes in seven (rehearsal, 2026-11-16)."""
    return re.split(r"\s*[,;:–—]\s*|\s+-\s+", leg["travel"].strip(), maxsplit=1)[0].rstrip(".")


def _step(leg: dict, tok: str) -> str:
    stops = leg["stops"]
    if tok == "open":
        return f"setting off, at {stops[0]['place']}"
    if tok == "close":
        return f"the goodbye at {stops[-1]['place']}"
    k = int(tok[1:])
    st = stops[k - 1]
    nxt = stops[min(k, STOPS - 1)]['place']
    return {"a": f"arriving at {st['place']}", "m": f"meeting {st['meet']} at {st['place']}",
            "r": f"the way from {st['place']} to {nxt}, arriving there"}[tok[0]]


def day_so_far(leg: dict, tok: str) -> str:
    """Where the leg has got to at this item, worked out from the plan: what's done and what's still to come, in order.
    Without it a road item said "third leg done" before the third meeting (rehearsal, 2026-11-16). The spare
    waiting moments come after the last meeting, before the goodbye."""
    waiting = tok.startswith("x")
    at = len(ORDER_STEPS) - 1 if waiting else ORDER_STEPS.index(tok)   # a wait: everything but the goodbye is done
    done = [_step(leg, t) for t in ORDER_STEPS[:at]]
    to_come = [_step(leg, t) for t in ORDER_STEPS[at if waiting else at + 1:]]
    # For her to know, not to say: with the stops still to come in every brief, the links read the route aloud ("the
    # next stop is... and after that...", leg 5 of the rehearsal, 2026-11-16).
    return ("THE DAY SO FAR (for knowing where she is, never for saying: no reading out what's ahead): done: "
            + ("; ".join(done) if done else "nothing yet") + ". Now: "
            + (f"a moment while she waits at {leg['stops'][-1]['place']}, the travelling done" if waiting
               else _step(leg, tok)) + ". Still to come: "
            + ("; ".join(to_come) if to_come else "nothing: this is the end of the leg") + ". Nothing still to come "
            "has happened yet: nobody still to come has been met, no place still to come reached, and the leg isn't "
            "over until the goodbye")


# Words that say nothing about what has been made much of.
_PLAIN = set("""a about above after again all also always am an and any are aren't around as at away back bad be been
before being best better big bit both but by came can can't come could day did didn't do does doesn't doing done don't
down each even ever every far few first for from get gets getting go goes going gone good got had has hasn't have
haven't he her here him his home how i i'd i'll i'm i've if in into is isn't it it's its just keep know last least left
let like little long look looks made make many may me might more most much must my never new next no not nothing now of
off oh old on once one only or other our out over own people place put quite really right round said same say says see
seen she should since so some something still such take tell than that that's the their them then there there's these
they they're thing things think this those though through time times to today told too took two under until up us very
want was wasn't way we we're we've well went were what when where which while who why will with without won't would
yes yet you you'd you'll you're you've your years year bit lot lots love lovely mind away even going because already
nobody somebody anybody everyone everybody someone anyone need needs needed feel feeling felt past behind ahead stand
standing minute minute hour morning afternoon evening kind sort enough maybe perhaps rather thank thanks hello goodbye
sure once twice three four five six seven eight nine hundred whole half another along across between almost just
wait waiting waited wait stop asked asking hoping hope plan leave proper making else fair give against coming week
street hand water town""".split())                     # waiting is the series' own subject: never "enough"


_VEHICLES = {"bike", "bicycle", "ferry", "boat", "bus", "coach", "train", "tram", "foot", "walk", "walking", "cart",
             "tractor", "van", "lift", "punt", "dinghy", "rowing", "barge", "horse", "pony", "trap", "taxi", "car"}


def said_enough(said: list[str], leg: dict) -> list[str]:
    """What has come up in three items or more today: the bike's brakes came up in seven items of one leg (rehearsal,
    2026-11-16), and told only not to repeat a phrase, the writers kept finding new ways to say it. People's and places'
    own names are left out, and the leg's way of travelling, which every item is about."""
    names = {w for st in leg["stops"] for w in re.findall(r"[a-z']+", (st["place"] + " " + st["meet"]).lower())}
    names |= {w for w in re.findall(r"[a-z']+", (HOST + " " + TITLE).lower())}
    names |= {w.rstrip("s") for w in names if len(w) > 4}                # "Ellis", as the words are stemmed
    # The way she travels, but only the thing itself: leg 3's "a borrowed bike... brakes I've been told to test" is
    # where the brakes came from, and they were what came up in seven items.
    names |= set(re.findall(r"[a-z]+", leg["travel"].lower())) & _VEHICLES
    counts: dict[str, int] = {}
    for text in said:
        for w in {x.rstrip("s") if len(x) > 4 else x for x in re.findall(r"\b[a-z]{4,}\b(?!')", text.lower())}:
            if w not in _PLAIN and w not in names:
                counts[w] = counts.get(w, 0) + 1
    return sorted((w for w, c in counts.items() if c >= 3), key=lambda w: (-counts[w], w))[:8]


def brief_for(world: World, brief: str) -> str:
    """The item's brief, and where the leg has got to (`day_so_far`)."""
    tok = _token(brief)
    out = _brief(world, brief)
    if tok is None:
        return out
    entry, s = booked(world)
    return f"{out}. {day_so_far(s['legs'][entry['n'] - 1], tok)}"


def _brief(world: World, brief: str) -> str:
    entry, s = booked(world)
    tok = _token(brief)
    if tok is None:
        return brief
    it = _item(entry, s, tok)
    leg, n = it["leg"], entry["n"]
    if it["kind"] == "open":
        prev = "" if n == 1 else f" Last time she got to: {s['legs'][n - 2]['ends']}."
        first = leg["stops"][0]
        # The opening is the first stop's arrival too, since 2026-11-16 (the user): a road item, an arrival and a
        # meeting at every stop arrived at each place two or three times, five reviews running.
        return (f"THE OPENING of leg {n} of {LEGS}, \"{leg['title']}\": Lorna to camera at {first['place']}: "
                f"\"Hello, and welcome to {TITLE}\", where she is and how she's going today: {leg['travel']}."
                + (f" Her reason for the journey: {s['why']}" if n == 1 else prev)
                + f" Then the place itself, in her own words (the plan's note, not to be read out): {first['what']} "
                  f"{first['meet']} doesn't speak in this item: meeting them is the next one. Not the stops ahead one "
                  "by one, and nothing of how the day ends. Only Lorna speaks, six to nine lines")
    # Where she is in the leg, item by item: told only "ON THE ROAD to the quay rail", the writer had her there
    # already, the arrival arrived again, and the meeting opened by arriving a third time (rehearsal, 2026-11-16).
    # Since then the road item ends on the arrival, and there is no arrival item.
    if it["kind"] == "close":
        nxt = f" Next time: {s['legs'][n]['title']}." if n < LEGS else " That's the whole journey: the last leg."
        last = leg["stops"][-1]
        return (f"THE CLOSE of leg {n}, Lorna to camera in the last of the light, still at {last['place']} after "
                f"meeting {last['meet']}: no arriving again and nothing about the place that's been said; a line "
                f"back over the day, then: {leg['ends']}{nxt} No hello: a goodbye, without saying when. Only Lorna "
                "speaks, five to seven lines")
    if it["kind"] == "meet":
        st = it["stop"]
        return (f"LORNA MEETS {st['meet']} ({st['role']}) at {st['place']}: {st['talk']} She has just got here and "
                "told us about the place in the item before: straight into the talk, with no arriving again and "
                f"no describing the place again. Eighteen to twenty-two lines, every one either Lorna (guest_name "
                f"\"{HOST}\") or {st['meet']} (guest_name \"{st['meet']}\"), and they talk more than she does. "
                f"{st['meet']} wasn't at the earlier stops and knows nothing of who she met there")
    if it["kind"] == "road":
        frm, to = leg["stops"][it["k"] - 1], it["to"]
        # The plan's note is in her voice, and went out word for word (rehearsal, 2026-11-16): hers to tell.
        return (f"ON THE WAY from {frm['place']} to {to['place']} ({how(leg)}), ending as she gets there: she has "
                f"left {frm['place']}; what she sees on the way, briefly; then she arrives, and tells us about "
                f"{to['place']} in her own words (the plan's note, not to be read out): {to['what']} {to['meet']} "
                "doesn't speak in this item: meeting them is the next one. Only Lorna speaks, seven to ten lines"
                # The last stop's note can be the ending itself ("Full circle... finish the last of the parkin"),
                # and arriving there, leg 6 said its goodbye a meeting early (rehearsal, 2026-11-16).
                + (". This is the last stop, but not the end: the meeting and the goodbye are still to come, so she "
                   "arrives and nothing more: no summing up, no thanks, no farewell, and nothing finished yet"
                   if it["k"] == STOPS - 1 else ""))
    last = leg["stops"][-1]
    return (f"WHILE SHE WAITS at {last['place']}, after meeting {last['meet']}: the day's travelling is done and she is "
            "still there, before the goodbye: no boarding, no crossing, no setting off, nowhere else; "
            + WAITING[(it["k"] - 1) % len(WAITING)]
            + ". Only Lorna speaks, five to seven lines; nothing said earlier today again")


def for_prompt(world: World) -> str:
    entry, s = booked(world)
    leg = s["legs"][entry["n"] - 1]
    said = _said_today(world)
    earlier = [x for x in s["legs"][:entry["n"] - 1]]
    out = (f"THE SERIES: {TITLE}: \"{s['title']}\", with {HOST} ({HOST_SHORT})\n"
           f"TODAY: leg {entry['n']} of {LEGS}, \"{leg['title']}\", by {how(leg)}: "
           # Not how it ends: that is the close's (its brief has it), and with it in every prompt the opening gave
           # the ending away (rehearsal, 2026-11-16).
           + "; then ".join(f"{st['place']} (meeting {st['meet']}, {st['role']})" for st in leg["stops"]) + ".")
    if earlier:
        out += "\nTHE LEGS BEFORE: " + "; ".join(f"{i + 1}. {l['title']} (ended: {l['ends']})"
                                                 for i, l in enumerate(earlier))
    if said:
        # In full: what an item established (the brakes tested, the auction over) is what the next must keep to.
        out += ("\nSAID ALREADY TODAY, in order, in full (never again: not a joke, not a story, not a phrase, and not "
                "the way an item opens; and keep to what it established):\n"
                + "\n".join(f"  - {t[:SAID_CHARS]}" for t in said))
        if enough := said_enough(said, leg):
            out += ("\nMADE MUCH OF ALREADY (each has come up in three items or more today: leave it alone now, "
                    f"unless this item is about it): {', '.join(enough)}")
    return out


def after(seg, world: World) -> None:
    """Out on the road, filmed by day; each item where its stop or its road is."""
    from .wildlife import DAYTIME

    entry = tonight(world)
    tok = _token(seg.brief)
    if not entry or tok is None:
        return
    s = next(x for x in state(world)[0] if x["made"] == entry["made"])
    it = _item(entry, s, tok)
    for line in seg.lines:
        for pat, day in DAYTIME:
            line.text = pat.sub(lambda m, d=day: d.capitalize() if m.group(0)[0].isupper() else d, line.text)
    seg.work["location"], seg.work["tod"], seg.work["filmed"] = it["backdrop"], it["tod"], True
    seg.work["road"] = {"other": it["stop"]["meet"] if it["kind"] == "meet" else None}


FAMILY = re.compile(r"\bmy (?:late |old |dear )?(wife|husband|missus|hubby|sister|brother|son|daughter|kids|children|"
                    r"grandson|granddaughter|grandkids|grandchildren|mum|mother|dad|father|nan|gran|grandad|grandpa|"
                    r"grandfather|grandmother|aunt|auntie|uncle|cousin|niece|nephew|partner|fianc[eé]e?|twin)s?\b",
                    re.IGNORECASE)


def _new_family(world: World, name: str, text: str) -> str | None:
    """A relative `name` speaks of that their record never mentions ("my wife's dresser": Stan Tully has a mother on
    record, and no wife), or None. Their role and what they've said on air are the record."""
    p = world.person_by_name(name)
    record = " ".join([p.role, *(m.get("said", "") for m in p.memories)]).lower() if p else ""
    if name == HOST:
        record += " " + HOST_ABOUT.lower()
    for m in FAMILY.finditer(text):
        words = next((g for g in _KIN if m.group(1).lower() in g), {m.group(1).lower()})
        if not any(re.search(rf"\b{re.escape(w)}s?\b", record) for w in words):
            return m.group(0)
    return None


# The same relative by other words: "my mum" for a record that says "named after his mother".
_KIN = ({"wife", "missus"}, {"husband", "hubby"}, {"mum", "mother"}, {"dad", "father"},
        {"nan", "gran", "grandmother"}, {"grandad", "grandpa", "grandfather"}, {"kids", "children", "son", "daughter"},
        {"grandkids", "grandchildren", "grandson", "granddaughter"}, {"aunt", "auntie"})


def _keep_to_the_record(world: World, script) -> None:
    """The rule against new family didn't hold on the model (a sister for Stan Tully on the first run, a wife at the
    rehearsal of 2026-11-16), and an aired line is canon: a sentence that gives a speaker a relative their record
    doesn't have goes, and a line with nothing left goes with it. The resident's memory of the item too."""
    kept = []
    for l in script.lines:
        name = (l.guest_name or "").strip()
        sentences = re.split(r"(?<=[.!?])\s+", l.text.strip())
        left = [x for x in sentences if not _new_family(world, name, x)]
        if len(left) != len(sentences):
            log.info("coast road: %s's line lost %d sentence(s) giving them family off the record", name,
                     len(sentences) - len(left))
        if left:
            l.text = " ".join(left)
            kept.append(l)
    script.lines = kept
    memo = getattr(script, "guest_memory", None)
    if memo and script.guest_name and _new_family(world, script.guest_name, memo):
        script.guest_memory = None


def _no_biscuit(script) -> None:
    """Her own old waiting story is the first leg's opening's and nowhere else's (the rule), and on leg 5 of the
    rehearsal (2026-11-16) she told it at every stop, four times: a sentence of hers about the biscuit goes."""
    kept = []
    for l in script.lines:
        if (l.guest_name or "").strip() == HOST:
            sentences = re.split(r"(?<=[.!?])\s+", l.text.strip())
            left = [x for x in sentences if not re.search(r"\bbiscuits?\b", x, re.IGNORECASE)]
            if not left:
                continue
            l.text = " ".join(left)
        kept.append(l)
    script.lines = kept


FAREWELL = re.compile(r"\b(?:thanks?|thank you)\s+(?:so much\s+)?for\s+(?:coming|watching|joining|travelling|"
                      r"tagging)\b|\buntil next time\b|\bsee you next time\b|\bgoodbye\b|\bgoodnight\b",
                      re.IGNORECASE)


def _no_goodbye(script) -> None:
    """The goodbye is the close's: on leg 6 of the rehearsal (2026-11-16) the road to the last stop thanked us for
    coming along and said farewell a meeting early. A sentence of Lorna's that signs off goes from any other item."""
    kept = []
    for l in script.lines:
        if (l.guest_name or "").strip() == HOST:
            left = [x for x in re.split(r"(?<=[.!?])\s+", l.text.strip()) if not FAREWELL.search(x)]
            if not left:
                continue
            l.text = " ".join(left)
        kept.append(l)
    script.lines = kept


def _words_of(sentence: str) -> str:
    return " ".join(re.findall(r"[a-z0-9']+", sentence.lower()))


def _not_again(world: World, script) -> None:
    """A sentence said word for word in an earlier item today goes: told not to, the meeting at the Crown still
    opened with the arrival's "Right, I've made it to the back room of the Crown" (rehearsal, 2026-11-16). Only
    sentences of five words or more, so "Thank you." and "Right." may come round. Each earlier item in full
    (`_said_today`): the archive's own text stops at 400 characters."""
    said = {_words_of(x) for text in _said_today(world) for x in re.split(r"(?<=[.!?])\s+", text)}
    kept = []
    for l in script.lines:
        sentences = re.split(r"(?<=[.!?])\s+", l.text.strip())
        left = [x for x in sentences if len(_words_of(x).split()) < 5 or _words_of(x) not in said]
        if left:
            l.text = " ".join(left)
            kept.append(l)
    script.lines = kept


def check(seg, script, world: World) -> None:
    """Lorna alone to camera, or Lorna and the stop's resident; the memory is the resident's, never one an item.
    Nobody gains family off the record (`_keep_to_the_record`). A piece Lorna gives alone that has someone else
    speaking loses their lines (the rehearsal's arrival at the quay rail had Ellis Porrett in it, and went to the
    template), so long as enough of hers are left."""
    entry = tonight(world)
    tok = _token(seg.brief)
    if not entry or tok is None:
        return
    s = next(x for x in state(world)[0] if x["made"] == entry["made"])
    it = _item(entry, s, tok)
    _keep_to_the_record(world, script)
    _not_again(world, script)
    if not (entry["n"] == 1 and it["kind"] == "open"):
        _no_biscuit(script)
    if it["kind"] not in ("close", "meet"):                 # a meeting may thank its resident
        _no_goodbye(script)
    if it["kind"] != "meet" and sum((l.guest_name or "").strip() == HOST for l in script.lines) >= 3:
        script.lines = [l for l in script.lines if (l.guest_name or "").strip() == HOST]
    names = {(l.guest_name or "").strip() for l in script.lines}
    if it["kind"] == "meet":
        other = it["stop"]["meet"]
        if names != {HOST, other}:
            raise llm.LLMError(f"{seg.brief} should be {HOST} and {other}, not {sorted(names)}")
        script.guest_name, script.guest_role = other, it["stop"]["role"][:60]     # the memory is theirs
    else:
        if names != {HOST}:
            raise llm.LLMError(f"{seg.brief} should be {HOST} alone, not {sorted(names)}")
        script.guest_memory = None                                                 # not one a piece to camera


def caption(world: World, name: str) -> str | None:
    entry = tonight(world)
    if not entry:
        return None
    if name == HOST:
        return f"{TITLE}: leg {entry['n']} of {LEGS}"
    s = next((x for x in state(world)[0] if x["made"] == entry["made"]), None)
    leg = s["legs"][entry["n"] - 1] if s else {"stops": []}
    st = next((st for st in leg["stops"] if st["meet"] == name), None)
    return st["role"][:60] if st else None


def view(seg, v, line_idx: int) -> None:
    """player.VIEW_HOOKS: filmed, not live; Lorna, and the resident when one speaks."""
    if not seg.work.get("filmed"):
        return
    v.tag, v.mode = "", "road"
    v.backdrop, v.tod = seg.work["location"], seg.work.get("tod") or v.tod
    v.scene = {"host": HOST, "other": (seg.work.get("road") or {}).get("other")}


def draw_scene(canvas, v, t: float) -> None:
    """scenes.SCENES["road"]: Lorna on location; when the resident she meets speaks, they take the frame."""
    from newsroom import backdrops
    from newsroom.scenes import FAR_Y, _guest, _mood, draw_mic
    from newsroom.sprites import draw_character

    backdrops.draw(canvas, v.backdrop, v.tod, v.weather, t)
    light = backdrops.person_light(v.backdrop, v.tod, v.weather)
    other = (v.scene or {}).get("other")
    if other and v.guest_name == other:
        draw_character(canvas, 215, 156, "guest", v.mouth, t, scale=2, facing=-1, look=_guest(v, other),
                       light=light, mood=v.mood)
        draw_character(canvas, 62, FAR_Y, "guest", 0.0, t, scale=1, look=HOST_LOOK, light=light,
                       mood=_mood(v, False))
        draw_mic(canvas, 190, 116)
    else:
        talking = v.guest_name == HOST
        draw_character(canvas, 90, 160, "guest", v.mouth if talking else 0.0, t, scale=2, look=HOST_LOOK,
                       light=light, mood=v.mood if talking else "")
        if other:                                     # the resident beside her, listening
            draw_character(canvas, 230, 160, "guest", 0.0, t, scale=2, facing=-1, look=_guest(v, other),
                           light=light)


# ------------------------------------------------------------------ with no model

def _stand_in_route() -> dict:
    """A route made in code: the town's own places, round from Port Wexley and back, the way the map
    (newsroom/geography.py) goes: over on the ferry, down the Saltby side to the lighthouse, round by Polgrey
    Bridge, down the town's shore, out along the cliffs to Kessick Bay, and home over the hill on the bus."""
    def stop(backdrop, where, place, what, meet, role, g, a):
        return {"backdrop": backdrop, "where": where, "place": place, "what": what, "meet": meet, "role": role,
                "gender": g, "age": a, "talk": f"what waiting means at {place}"}
    legs = [
        ("The First Crossing", "the Saltby foot ferry", [
            stop("harbour", "harbour", "the Quay Steps", "where it starts", "Ruth Hallam", "boatwoman, Saltby foot ferry crew", "f", "middle"),
            stop("slipway", "saltby_slip", "the Saltby slip", "the other side", "Morag Lyle", "Saltby foot ferry deckhand", "f", "middle"),
            stop("village", "saltby", "Saltby green", "the village", "Tom Nancarrow", "Councillor, Saltby ward", "m", "old")]),
        ("Down to the Light", "on foot", [
            stop("village_hall", "saltby", "Saltby village hall", "the hall's tea urn", "Marian Tolley", "choir leader", "f", "old"),
            stop("seafront", "saltby_sands", "Saltby sands", "the tide going out", "Ruth Ellerby", "open water swimmer", "f", "middle"),
            stop("lighthouse", "greymouth_point", "the Greymouth light", "the view", "Eamon Trask", "retired lighthouse keeper", "m", "old")]),
        ("Round by the Bridge", "the coast bus", [
            stop("tea_room", "saltby", "a tea room in Saltby", "a pot of tea", "Agnes Penhale", "potter and mender", "f", "old"),
            stop("village", "polgrey", "Polgrey Bridge", "the bus stop on the bridge", "Ned Trevena", "estuary walker", "m", "old"),
            stop("woods", "wexley_woods", "Wexley Woods", "the footpath", "Peggy Tallack", "birdwatcher", "f", "old")]),
        ("Market Day", "on foot", [
            stop("estuary", "the_salting", "the Salting path", "the mud at low water", "Carys Lunt", "volunteer bird counter", "f", "old"),
            stop("market", "harrow_street", "Harrow Street market", "the stalls", "Gwen Pascoe", "baker, Harrow Street market", "f", "middle"),
            stop("fish_quay", "fish_quay", "the fish quay", "the auction", "Ivy Marchetti", "harbour hand", "f", "middle")]),
        ("Up the Coast Road", "a borrowed bike", [
            stop("cannery", "cannery", "the old cannery", "the slipway", "Gideon Ashby", "landlord, the Cannery Tap", "m", "middle"),
            stop("lifeboat_station", "lifeboat_station", "the lifeboat station", "the crew's kettle", "Eileen Harcombe", "retired lifeboat tractor driver", "f", "old"),
            stop("coast_road", "east_cliffs", "the coast road", "the long climb", "Bill Lander", "retired harbour pilot", "m", "old")]),
        ("Home Again", "the coast bus", [
            stop("seafront", "kessick_bay", "Kessick Bay", "the cove", "Jan Couch", "darts player", "m", "middle"),
            stop("main_street", "main_street", "Main Street", "the bus stop", "Brenda Fisk", "shopkeeper, Main Street", "f", "middle"),
            stop("harbour", "harbour", "the harbour", "where it started", "Gideon Ferrow", "jar-tower builder and comedian", "m", "middle")]),
    ]
    return {"title": "Every Slow Way There Is", "why": "to collect waiting stories for her waiting club",
            "legs": [{"title": t, "travel": tr, "stops": st, "ends": f"the end of {t.lower()}"} for t, tr, st in legs]}


_STAND_IN = ("Well, here we are.", "I've been told it's worth the wait.", "I'll be the judge of that.",
             "Right. On we go.")


def template(seg_type, world, rng: random.Random, part: str, work: dict, brief: str):
    """The Coast Road with no model: Lorna on today's leg, from the route."""
    from newsroom.models import PanelLine, PanelScript

    if seg_type is not T.interview:
        return None
    entry, s = booked(world)
    tok = _token(brief)
    if tok is None:
        return None
    it = _item(entry, s, tok)
    leg = it["leg"]
    if it["kind"] == "meet":
        st = it["stop"]
        said = [(HOST, f"So, {st['meet']}. How long have you been waiting for me?"),
                (st["meet"], "Long enough to put the kettle on twice."),
                (HOST, f"And what's {st['place']} like, really?"),
                (st["meet"], "You'd have to stay a while to find out."), (HOST, "Then I'll stay a while.")]
        return PanelScript(lines=[PanelLine(speaker="guest", guest_name=n, text=x) for n, x in said],
                           headline=f"Lorna meets {st['meet']}", lower_third=TITLE, guest_name=st["meet"],
                           guest_role=st["role"][:60])
    if it["kind"] == "open":
        said = [f"Hello, and welcome to {TITLE}.", f"Today: {leg['title']}, by {leg['travel']}.", *_STAND_IN[:2]]
    elif it["kind"] == "close":
        said = [f"And that's where I've got to: {leg['ends']}.", "My feet have opinions about it.", "Until next time.",
                "Keep waiting. It's worth it."]           # a panel script needs four lines
    elif it["kind"] == "road":
        said = [f"On to {it['to']['place']}.", *_STAND_IN[1:3], f"And here we are: {it['to']['place']}."]
    else:
        said = list(_STAND_IN)
    return PanelScript(lines=[PanelLine(speaker="guest", guest_name=HOST, text=x) for x in said],
                       headline=f"{TITLE}: {leg['title']}"[:80], lower_third=TITLE, guest_name=HOST,
                       guest_role=f"{TITLE}"[:60])


# ------------------------------------------------------------------ the show

def show_def() -> Show:
    items: list = []
    # No arrival items since 2026-11-16 (the user): the opening arrives at the first stop, and each road item ends on
    # the arrival at the next.
    for k in range(1, STOPS + 1):
        items.append(I(T.interview, brief="{m%d}" % k, target_s=MEETING_S))
        if k < STOPS:
            items.append(I(T.interview, brief="{r%d}" % k, target_s=ROAD_S))
    spares = tuple(I(T.interview, brief=tuple("{x%d}" % (k + 1 + 3 * lap) for lap in range(SPARES // 3)),
                     target_s=50.0) for k in range(3))
    return Show(
        SHOW, TITLE.upper(), "COAST ROAD", (214, 160, 40),
        pattern=(T.bumper, I(T.interview, "open", brief="{open}", target_s=70.0), *items, *spares, T.ad_break),
        loop_from=2 + len(items),
        closing=(I(T.interview, "close", brief="{close}", target_s=45.0),),
        target_s={T.bumper: 10.0, T.interview: 90.0, T.ad_break: 60.0},
        cast=("guest",), lead="guest", cast_by_type={T.interview: ("guest",)},
        station=f"{TITLE}, the travelogue on Channel 8, Port Wexley's second channel, with {HOST}",
        tone="warm, funny and nosy in the nicest way: a comedian on a slow journey, laughing with people",
        light=True, repeats_overnight=False,
    )


_RULES = f"""
This is part of THE COAST ROAD, a travelogue on Channel 8: {HOST}, {HOST_SHORT}, goes round the Greymouth coast by
every slow way there is. Her own old waiting story (the ferry office and the biscuit) belongs to the first leg's
opening and nowhere else: the waiting stories from now on are other people's. No figures or news of the day from the
briefing (the auction's takings and prices, votes, fixtures, anything due on a date): it airs days after it was
filmed. Nobody makes up news either: no results, scores, league places, surveys, repairs or plans the briefing
doesn't give (a darts win of 7-2 and a survey of the slip were invented at a rehearsal); what residents say is about
what they do and what they've seen. Every line is speaker "guest" with guest_name the person speaking: "{HOST}" for her, and the
resident by their exact name. It was FILMED EARLIER, BY DAY: never "tonight", "this evening", "good evening" or
"live", and no clock times. The day only moves on: each item is later than everything in SAID ALREADY TODAY, so
nothing happens earlier in the day than it already has (once the auction is over it stays over, and a "first boat"
can't come in after the afternoon). Warm and funny, never cruel: she laughs with people, not at them. Places and people from
TODAY and the briefing only; no new history for anyone the town knows, and nothing new about Lorna's own family or
past. A resident she meets talks about what they do and what they've seen; they have no family on air (no sister,
brother, husband, wife, children or grandchildren) unless the briefing gives them one: the first run gave Stan Tully a
sister he never had ("a cot for my sister's first"). Every item is new: nothing from SAID ALREADY TODAY again, no joke, no story, no phrase, and each opens its own
way. Not news: thread_id is null. headline = what happens, in under 10 words. lower_third = "{TITLE}".
"""


def register():
    """Put The Coast Road on air through the engine's registries, sharing Tideline's slot. Returns an undo."""
    from newsroom import assets, player, scenes, workers, world as world_mod, writers
    from newsroom.writers import _COMMON_RULES, _MIDDLE

    sh = show_def()
    schedule.SHOWS[SHOW] = sh
    schedule.ROTATIONS["tideline"] = rotation
    assets.IDENTS[SHOW] = (assets.CONFIG.paths.assets / "bumper_coastroad.wav", IDENT)
    assets.IDENT_MUSIC[SHOW] = "rockpool"            # the toy arrangement, until it has music of its own (by ear)
    assets.IDENT_VOICES[SHOW] = HOST_VOICE
    scenes.PINNED_LOOKS[HOST] = HOST_LOOK
    world_mod.PINNED_VOICES[HOST] = (HOST_VOICE, 1.0, "b")
    player.SEATS[SHOW] = 2
    player.VIEW_HOOKS[SHOW] = view
    player.AIRED_HOOKS[SHOW] = aired
    scenes.SCENES["road"] = draw_scene
    jobs = (should_commission, commission)
    workers.IDLE_JOBS.append(jobs)
    writers.SHOW_SYSTEMS[SHOW] = {T.interview: _COMMON_RULES + _RULES}
    writers._PLACE[(SHOW, T.interview)] = {
        "open": f"PLACE IN THE SHOW: this OPENS {TITLE}: the first words of the programme.",
        "close": f"PLACE IN THE SHOW: this CLOSES {TITLE}: the last words of the programme.",
        "": _MIDDLE.format(title=TITLE, extra=""),
    }
    writers.BRIEF_HOOKS[SHOW] = brief_for
    writers.PROMPT_HOOKS[SHOW] = for_prompt
    writers.TEMPLATE_HOOKS[SHOW] = template
    writers.CHECK_HOOKS[SHOW] = check
    writers.AFTER_HOOKS[SHOW] = after
    writers.CAPTION_HOOKS[SHOW] = caption
    writers.LINE_CAPS[SHOW] = 28
    for reg in (writers.BOOKED_SHOWS, writers.DEBATE_SHOWS, writers.UNFILED_SHOWS):
        reg.add(SHOW)
    undo_creative = enrol()

    def undo() -> None:
        undo_creative()
        schedule.SHOWS.pop(SHOW, None)
        schedule.ROTATIONS.pop("tideline", None)
        scenes.PINNED_LOOKS.pop(HOST, None)
        world_mod.PINNED_VOICES.pop(HOST, None)
        scenes.SCENES.pop("road", None)
        for reg in (assets.IDENTS, assets.IDENT_MUSIC, assets.IDENT_VOICES, player.SEATS, player.VIEW_HOOKS,
                    player.AIRED_HOOKS, writers.SHOW_SYSTEMS, writers.BRIEF_HOOKS, writers.PROMPT_HOOKS,
                    writers.TEMPLATE_HOOKS, writers.CHECK_HOOKS, writers.AFTER_HOOKS, writers.CAPTION_HOOKS,
                    writers.LINE_CAPS):
            reg.pop(SHOW, None)
        writers._PLACE.pop((SHOW, T.interview), None)
        if jobs in workers.IDLE_JOBS:
            workers.IDLE_JOBS.remove(jobs)
        for reg in (writers.BOOKED_SHOWS, writers.DEBATE_SHOWS, writers.UNFILED_SHOWS):
            reg.discard(SHOW)
    return undo


# ------------------------------------------------------------------ planning a route ahead, for the user to read

def _cli(argv: list[str]) -> int:
    """python -m entertainment.travelogue --plan [--world PATH] [--out PATH]: plan the host's route on a world (a
    copy, by default the town's, read only) and save it to data/travelogue/<host>.json (or --out) for the user to
    read before it airs. The creative editor reads the draft and may send it back once. --vet instead prints the
    editor's notes on the route already saved, and changes nothing."""
    import argparse
    from pathlib import Path

    from newsroom import world as world_mod

    ap = argparse.ArgumentParser(prog="python -m entertainment.travelogue")
    ap.add_argument("--plan", action="store_true", help="plan the route and save it")
    ap.add_argument("--vet", action="store_true", help="the creative editor's notes on the saved route; nothing is written")
    ap.add_argument("--world", help="the world to read (default: data/world.json; it isn't saved)")
    ap.add_argument("--out", help="--plan: where to save the route (default: the station's own, which it then airs)")
    a = ap.parse_args(argv)
    if not (a.plan or a.vet):
        ap.print_help()
        return 1
    w = world_mod._from_dict(json.loads(Path(a.world or CONFIG.paths.world).read_text(encoding="utf-8")))
    enrol()
    if a.vet:
        path = _saved_route_path()
        if not path.exists():
            print(f"no route saved in {path}")
            return 1
        saved = json.loads(path.read_text(encoding="utf-8"))
        route = Route.model_validate({k: saved[k] for k in ("title", "why", "legs")})
        if not creative._on():
            print("the creative editor can't be asked (the models are off, or its model couldn't be reached)")
            return 1
        notes = creative.vet(w, SHOW, "route", _route_text(route), _asked(w), margin=False)
        print(f"{route.title}: " + ("the creative editor would send it back:\n" + "\n".join(f"  - {n}" for n in notes)
                                    if notes else "the creative editor has no notes on it"))
        return 0
    route = plan_route(w, unhurried=True)
    path = Path(a.out) if a.out else _saved_route_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(route, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"{route['title']}: {route['why']}")
    for i, leg in enumerate(route["legs"], 1):
        print(f"\nLeg {i}: {leg['title']} ({leg['travel']})")
        for st in leg["stops"]:
            print(f"  - {st['place']} [{st['backdrop']}]: {st['what']} Meets {st['meet']}, {st['role']}: {st['talk']}")
        print(f"  Ends: {leg['ends']}")
    print(f"\nsaved to {path}" + (" (the stand-in: the model's route didn't come)" if route.get("stand_in") else ""))
    return 0


if __name__ == "__main__":
    import sys
    logging.basicConfig(level=logging.INFO)
    sys.exit(_cli(sys.argv[1:]))
