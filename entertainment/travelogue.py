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
- **A leg** is the opening, three stops (Lorna arriving to camera, then meeting the stop's resident), the road
  between them, waiting moments for spare minutes (three, then a break, round again), and the close at dusk. It is
  filmed by day, with no LIVE tag, in its own view (scenes.SCENES["road"], player.VIEW_HOOKS).
- **Aired** is stamped when a leg's first stop goes out (player.AIRED_HOOKS); the next leg follows the last aired
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

from newsroom import llm, schedule
from newsroom.config import CONFIG
from newsroom.models import SegmentType as T
from newsroom.schedule import Item as I, Show
from newsroom.sprites import Look
from newsroom.world import World

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
SPARES = 12
AIRS_AT = "20:40"
BOOK_FROM = "18:30"
TASK = "travelogue" if "travelogue" in CONFIG.llm.routes else "chamber"
IDENT = "The Coast Road, with Lorna Quayle. On Channel 8."
SAID_CHARS = 420
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
  {stops} stops on the town's own places (a backdrop from the list, the place as she'd name it, what happens there)
  and ends where the next one starts.
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


def plan_route(world: World) -> dict:
    """The series' route: the model's (or the stand-in's), not yet recorded."""
    user = (f"BRIEFING\n{world.summary_for_editor()}\n\nPEOPLE:\n"
            + "\n".join(f"  - {p.name}, {p.role}" for p in _people(world))
            + "\n\nBACKDROPS for the stops: " + ", ".join(STOP_BACKDROPS))
    system = _SYSTEM.format(host=HOST, about=HOST_ABOUT, legs=LEGS, stops=STOPS)
    try:
        route = llm.complete_json(TASK, Route, system, user)
        _check(route, world)
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
    """player.AIRED_HOOKS: the leg's first stop went out: the next booking moves on to the leg after."""
    if seg.brief != "{a1}":
        return
    entry = tonight(world)
    if entry and not entry.get("aired"):
        with world.lock:
            entry["aired"] = True
        log.info("coast road: leg %d aired", entry["n"])


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
    return {"kind": "wait", "k": k, "backdrop": _road(leg["travel"]), "tod": "day", "leg": leg}


WAITING = (
    "A WAITING STORY: Lorna tells one from her collection, from someone she met on the way (not one met on camera)",
    "THE VIEW WHILE SHE WAITS: what she can see from where she's waiting, and what she makes of it",
    "THE TIMETABLE: Lorna reads what the timetable or the sign says, and what has actually happened",
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


def brief_for(world: World, brief: str) -> str:
    entry, s = booked(world)
    tok = _token(brief)
    if tok is None:
        return brief
    it = _item(entry, s, tok)
    leg, n = it["leg"], entry["n"]
    if it["kind"] == "open":
        prev = "" if n == 1 else f" Last time she got to: {s['legs'][n - 2]['ends']}."
        return (f"THE OPENING of leg {n} of {LEGS}, \"{leg['title']}\": Lorna to camera at {leg['stops'][0]['place']}: "
                f"\"Hello, and welcome to {TITLE}\", where she is, where today's leg goes and how: {leg['travel']}."
                + (f" Her reason for the journey: {s['why']}" if n == 1 else prev)
                + " Only Lorna speaks, five to eight lines")
    if it["kind"] == "close":
        nxt = f" Next time: {s['legs'][n]['title']}." if n < LEGS else " That's the whole journey: the last leg."
        return (f"THE CLOSE of leg {n}, Lorna to camera in the last of the light: {leg['ends']}{nxt} A goodbye "
                "without saying when. Only Lorna speaks, five to seven lines")
    if it["kind"] == "arrive":
        st = it["stop"]
        return (f"STOP {it['k']} of {STOPS}: Lorna arrives at {st['place']} and tells us about it to camera: "
                f"{st['what']} Only Lorna speaks, five to eight lines")
    if it["kind"] == "meet":
        st = it["stop"]
        return (f"LORNA MEETS {st['meet']} ({st['role']}) at {st['place']}: {st['talk']} Twelve to sixteen lines, "
                f"every one either Lorna (guest_name \"{HOST}\") or {st['meet']} (guest_name \"{st['meet']}\"), and "
                "they talk more than she does")
    if it["kind"] == "road":
        return (f"ON THE ROAD to {it['to']['place']}: Lorna to camera on the way ({leg['travel']}): the journey so "
                "far, and what she's hoping for at the next stop. Only Lorna speaks, five to eight lines")
    return ("WHILE SHE WAITS (" + leg["travel"] + "): " + WAITING[(it["k"] - 1) % len(WAITING)]
            + ". Only Lorna speaks, five to seven lines; nothing said earlier today again")


def for_prompt(world: World) -> str:
    entry, s = booked(world)
    leg = s["legs"][entry["n"] - 1]
    with world.lock:
        said = [a for a in world.archive if a["date"] == world.last_date and a.get("show") == SHOW
                and a["type"] != T.ad_break.value]
    earlier = [x for x in s["legs"][:entry["n"] - 1]]
    out = (f"THE SERIES: {TITLE}: \"{s['title']}\", with {HOST} ({HOST_SHORT})\n"
           f"TODAY: leg {entry['n']} of {LEGS}, \"{leg['title']}\", by {leg['travel']}: "
           + "; then ".join(f"{st['place']} (meeting {st['meet']}, {st['role']})" for st in leg["stops"])
           + f". It ends: {leg['ends']}")
    if earlier:
        out += "\nTHE LEGS BEFORE: " + "; ".join(f"{i + 1}. {l['title']} (ended: {l['ends']})"
                                                 for i, l in enumerate(earlier))
    if said:
        out += ("\nSAID ALREADY TODAY, in order (never again: not a joke, not a story, not a phrase, and not the way an "
                "item opens):\n" + "\n".join(f"  - {a['text'][:SAID_CHARS]}" for a in said))
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


def check(seg, script, world: World) -> None:
    """Lorna alone to camera, or Lorna and the stop's resident; the memory is the resident's, never one an item."""
    entry = tonight(world)
    tok = _token(seg.brief)
    if not entry or tok is None:
        return
    s = next(x for x in state(world)[0] if x["made"] == entry["made"])
    it = _item(entry, s, tok)
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
    """A route made in code: the town's own places, round from Port Wexley and back."""
    def stop(backdrop, place, what, meet, role, g, a):
        return {"backdrop": backdrop, "place": place, "what": what, "meet": meet, "role": role, "gender": g,
                "age": a, "talk": f"what waiting means at {place}"}
    legs = [
        ("The First Crossing", "the Saltby foot ferry", [
            stop("harbour", "the harbour", "where it starts", "Ruth Hallam", "boatwoman, Saltby foot ferry crew", "f", "middle"),
            stop("slipway", "the ferry slip", "waiting for the boat", "Morag Lyle", "Saltby foot ferry deckhand", "f", "middle"),
            stop("village", "Saltby green", "the other side", "Tom Nancarrow", "Councillor, Saltby ward", "m", "old")]),
        ("Over the Salting", "on foot", [
            stop("village_hall", "Saltby village hall", "the hall's tea urn", "Marian Tolley", "choir leader", "f", "old"),
            stop("estuary", "the Salting path", "the mud at low water", "Carys Lunt", "volunteer bird counter", "f", "old"),
            stop("tea_room", "a tea room by the path", "a pot of tea", "Agnes Penhale", "potter and mender", "f", "old")]),
        ("Up the Coast Road", "a borrowed bike", [
            stop("coast_road", "the coast road", "the long climb", "Ned Trevena", "estuary walker", "m", "old"),
            stop("lifeboat_station", "the lifeboat station", "the crew's kettle", "Eileen Harcombe", "retired lifeboat tractor driver", "f", "old"),
            stop("lighthouse", "the Greymouth light", "the view", "Eamon Trask", "retired lighthouse keeper", "m", "old")]),
        ("Market Day", "the bus", [
            stop("market", "Harrow Street market", "the stalls", "Gwen Pascoe", "baker, Harrow Street market", "f", "middle"),
            stop("fish_quay", "the fish quay", "the auction", "Ivy Marchetti", "harbour hand", "f", "middle"),
            stop("dining_room", "a pub dining room", "lunch", "Gideon Ashby", "landlord, the Cannery Tap", "m", "middle")]),
        ("Inland", "the country bus", [
            stop("farm", "a farm outside town", "the yard", "Bill Lander", "retired harbour pilot", "m", "old"),
            stop("woods", "Wexley Woods", "the footpath", "Peggy Tallack", "birdwatcher", "f", "old"),
            stop("village", "back at Saltby", "the bus shelter", "Jan Couch", "darts player", "m", "middle")]),
        ("Home Again", "the last ferry", [
            stop("seafront", "the seafront", "the benches", "Ruth Ellerby", "open water swimmer", "f", "middle"),
            stop("main_street", "the high street", "the bus stop", "Brenda Fisk", "shopkeeper, Main Street", "f", "middle"),
            stop("harbour", "the harbour", "where it started", "Gideon Ferrow", "jar-tower builder and comedian", "m", "middle")]),
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
    elif it["kind"] == "arrive":
        said = [f"Here we are: {it['stop']['place']}.", *_STAND_IN[1:]]
    else:
        said = list(_STAND_IN)
    return PanelScript(lines=[PanelLine(speaker="guest", guest_name=HOST, text=x) for x in said],
                       headline=f"{TITLE}: {leg['title']}"[:80], lower_third=TITLE, guest_name=HOST,
                       guest_role=f"{TITLE}"[:60])


# ------------------------------------------------------------------ the show

def show_def() -> Show:
    items: list = []
    for k in range(1, STOPS + 1):
        items.append(I(T.interview, brief="{a%d}" % k, target_s=60.0))
        items.append(I(T.interview, brief="{m%d}" % k, target_s=150.0))
        if k < STOPS:
            items.append(I(T.interview, brief="{r%d}" % k, target_s=60.0))
    spares = tuple(I(T.interview, brief=tuple("{x%d}" % (k + 1 + 3 * lap) for lap in range(SPARES // 3)),
                     target_s=50.0) for k in range(3))
    return Show(
        SHOW, TITLE.upper(), "COAST ROAD", (214, 160, 40),
        pattern=(T.bumper, I(T.interview, "open", brief="{open}", target_s=50.0), *items, *spares, T.ad_break),
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
filmed. Every line is speaker "guest" with guest_name the person speaking: "{HOST}" for her, and the
resident by their exact name. It was FILMED EARLIER, BY DAY: never "tonight", "this evening", "good evening" or
"live", and no clock times. Warm and funny, never cruel: she laughs with people, not at them. Places and people from
TODAY and the briefing only; no new history for anyone the town knows, and nothing new about Lorna's own family or
past. Every item is new: nothing from SAID ALREADY TODAY again, no joke, no story, no phrase, and each opens its own
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
    writers.LINE_CAPS[SHOW] = 24
    for reg in (writers.BOOKED_SHOWS, writers.DEBATE_SHOWS, writers.UNFILED_SHOWS):
        reg.add(SHOW)

    def undo() -> None:
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
    """python -m entertainment.travelogue --plan [--world PATH]: plan the host's route on a world (a copy, by
    default the town's, read only) and save it to data/travelogue/<host>.json for the user to read before it airs."""
    import argparse
    from pathlib import Path

    from newsroom import world as world_mod

    ap = argparse.ArgumentParser(prog="python -m entertainment.travelogue")
    ap.add_argument("--plan", action="store_true", help="plan the route and save it")
    ap.add_argument("--world", help="the world to read (default: data/world.json; it isn't saved)")
    a = ap.parse_args(argv)
    if not a.plan:
        ap.print_help()
        return 1
    w = world_mod._from_dict(json.loads(Path(a.world or CONFIG.paths.world).read_text(encoding="utf-8")))
    route = plan_route(w)
    path = _saved_route_path()
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
