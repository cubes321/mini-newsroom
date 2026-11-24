"""The TV movie: Channel 8's 21:00 to 22:30 (docs/ENGINE.md, "The TV movie"; agreed with the user 2026-11-23).

A bank of finished films, grown a film at a time. Each is written in full ahead of air, here, never live: the soap
is written on the night and only finds out its length on air, and an hour and a quarter of story (about 40 scenes) is too much for
one plan call. A finished film has a known running time, can be read by the creative editor and approved by the user
before it joins the bank, and costs nothing to repeat.

    uv run python -m entertainment.movies pitch [--genre mystery]      # three pitches, saved to data/movies/pitches.json
    uv run python -m entertainment.movies new 2                        # the second pitch becomes data/movies/<slug>/
    uv run python -m entertainment.movies new --title T --genre G --premise "..."    # or your own
    uv run python -m entertainment.movies write data/movies/<slug>     # outline, acts, scenes; stops and resumes
    uv run python -m entertainment.movies read data/movies/<slug>      # the creative editor reads the finished film
    uv run python -m entertainment.movies estimate data/movies/<slug>  # the running time of script.md as it stands
    uv run python -m entertainment.movies approve data/movies/<slug>   # once the user has read it
    uv run python -m entertainment.movies list

`write` goes in three levels, each saved as it lands in the film's film.json, so a failure costs only the call that
failed: the outline (premise, parts, ACTS acts, the ending), vetted once by the creative editor; each act's plan
(SCENES_PER_ACT scenes: where, when, who, who knows what, what happens, what it ends on); then the dialogue, scene
by scene in order, each scene given the whole script so far. Then script.md, which is what the user reads, edits
and approves, and what will air: `## Act` and `### n.` headings naming the set, the time of day and who is in it,
and `NAME (mood): text` lines as in tools/one_off.py.

Nothing here touches the town: the world is read (the creative editor's notes, the residents' names a part must
not take) and never saved. There is no stand-in: with the model off, `write` stops and says so. The parts carry a
gender and an age so they can be cast later; actors, looks and voices are not the writer's business. Not on air yet:
the air step (casting, the sets' marks, voicing, the slot) comes after the first films are read.
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Literal

from pydantic import BaseModel, Field, field_validator

from newsroom import llm
from newsroom.config import CONFIG
from newsroom.models import MOOD_NAMES, _clip_words
from newsroom.world import World

from . import creative, soap

log = logging.getLogger(__name__)

SHOW = "movie"
TITLE = "The Channel 8 Film"       # the slot's name, until it has one
AIRS_AT = "21:00"                  # to 22:30 (the user, 2026-11-23)
GENRES = ("mystery", "romance", "thriller", "comedy", "family drama", "ghost story")
ACTS = 4
# 2026-11-23: asked 150 words (75 s), Sonnet wrote about 240 in every one of The Last Lot's 32 scenes, whatever it was
# asked, so a film's length is set by its number of scenes. The Last Lot, voiced, ran 56 minutes (7,693 words in 3,362 s,
# 2.29 a second), short of the ninety-minute slot; the user chose longer films (the same day), and a film that still
# comes up short is padded (docs/ENGINE.md "The TV movie": borrowed news from Channel 7, perhaps).
SCENES_PER_ACT = 10                # 40 scenes: about 73 minutes of story, 89 with the titles, credits and breaks
SCENE_S = 110.0                    # about 250 words, what Sonnet writes anyway
WORDS_PER_S = 2.3                  # The Last Lot's voices (Pocket, the guest pool), measured
TARGET_S = ACTS * SCENES_PER_ACT * SCENE_S      # 73 minutes
MAX_PARTS = 6
PLAN_TOKENS = 32000                # as the soap's plan: Sonnet's thinking counts against it
PLAN_TIMEOUT_S = 420.0
SCENE_TOKENS = 16000
SCENE_TIMEOUT_S = 240.0
# Sonnet unless config.toml routes them elsewhere: "movie" for the outline and acts, "movie_scene" for the dialogue.
_routes = CONFIG.llm.routes
TASK = "movie" if "movie" in _routes else ("soap" if "soap" in _routes else "senior_editor")
SCENE_TASK = "movie_scene" if "movie_scene" in _routes else TASK
PITCHES = 3

# Where a film can be shot: the town's own backdrops (assets/backdrops/<id>.png), named as a film would use them.
# Not the Marina Row sets (they are the soap's street) nor the studios. The air step still needs marks on these, and a
# way to hide where a seated figure ends with no lower third (the soap's sets have furniture across the front).
SETS: dict[str, tuple[str, str]] = {
    "harbour": ("the harbour", "fishing boats, the harbour wall, gulls"),
    "fish_quay": ("the fish quay", "fish boxes on ice, the auction floor, the boats tied up"),
    "slipway": ("the slipway", "a stone ramp into the water by an old cannery, small boats"),
    "cannery": ("the old cannery", "brick sheds, a rusting sign, broken windows"),
    "lifeboat_station": ("the lifeboat station", "the boathouse and the launch ramp"),
    "lighthouse": ("the lighthouse", "the tower on the point, rocks and the sea"),
    "seafront": ("the seafront", "the promenade: railings, benches, the beach"),
    "coast_road": ("the coast road", "a stone wall along the cliffs, the sea far below"),
    "main_street": ("the high street", "shopfronts, the bus stop, the post office"),
    "residential_street": ("a terraced street", "terraced houses, parked cars, front gardens"),
    "market": ("the street market", "striped stalls along the street"),
    "police_station": ("the police station", "the blue lamp and the front desk entrance"),
    "church": ("the harbour church", "inside: the chancel arch and its coloured window, the pews"),
    "pub": ("the pub", "inside a darts pub: the bar, the dartboard, the chalk scoreboard"),
    "dining_room": ("the country pub's dining room", "beams, an inglenook fire, tables laid"),
    "tea_room": ("the tea room", "inside a seaside tea room: the cake counter, little tables with cloths"),
    "village": ("the village green", "a village green, the church spire, a pub"),
    "village_hall": ("the village hall", "inside: the stage with its curtains, rows of chairs"),
    "farm": ("the farm", "fields, a barn, a tractor track"),
    "woods": ("the woods", "a footpath under tall trees"),
    "estuary": ("the estuary", "mudflats, reeds, wading birds"),
}

_SPOKEN = re.compile(r"^([A-Z][A-Z' .-]*[A-Z])(?:\s*\((\w+)\))?:\s+(.+)$")     # NAME: text, or NAME (mood): text
_SCENE_HEAD = re.compile(r"^###\s+(\d+)\.\s+(.+?)\s+\((\w+), (\w+)\):\s+(.+?)(?:\s+\[~\d+ s\])?\s*$")


# ------------------------------------------------------------------ the shapes

class Pitch(BaseModel):
    title: str = Field(min_length=2, max_length=60)
    genre: str = Field(min_length=3, max_length=40)
    logline: Annotated[str, _clip_words(300)] = Field(min_length=20, max_length=300,
                                                      description="the film in one or two sentences")
    hook: Annotated[str, _clip_words(300)] = Field(min_length=10, max_length=300,
                                                   description="why it would be good to watch: the twist, the pairing, "
                                                               "the question that keeps people watching")


class Pitches(BaseModel):
    pitches: list[Pitch] = Field(min_length=PITCHES, max_length=PITCHES)


class Part(BaseModel):
    name: str = Field(min_length=3, max_length=40, description="first name and surname")
    gender: Literal["f", "m"]
    age: Literal["young", "middle", "old"] = Field(description="young: under 30; middle: 30 to 60; old: over 60")
    who: Annotated[str, _clip_words(240)] = Field(min_length=10, max_length=240, description="who they are")
    wants: Annotated[str, _clip_words(200)] = Field(min_length=5, max_length=200,
                                                    description="what they want, and what stands in the way")


class Act(BaseModel):
    name: str = Field(min_length=3, max_length=60)
    happens: Annotated[str, _clip_words(600)] = Field(min_length=20, max_length=600,
                                                      description="what happens in it, in three to five sentences")
    ends_on: Annotated[str, _clip_words(240)] = Field(min_length=5, max_length=240,
                                                      description="the moment it ends on, which carries the film over "
                                                                  "the ad break")


class Outline(BaseModel):
    title: str = Field(min_length=2, max_length=60)
    genre: str = Field(min_length=3, max_length=40)
    logline: Annotated[str, _clip_words(300)] = Field(min_length=20, max_length=300)
    tone: Annotated[str, _clip_words(200)] = Field(min_length=5, max_length=200,
                                                   description="how it should feel and sound")
    parts: list[Part] = Field(min_length=3, max_length=MAX_PARTS)
    acts: list[Act] = Field(min_length=ACTS, max_length=ACTS)
    ending: Annotated[str, _clip_words(400)] = Field(min_length=20, max_length=400,
                                                     description="how it ends, and the film's last line and who says it")


class FilmScene(BaseModel):
    set: str = Field(description="a set id from THE SETS")
    when: Literal["day", "evening", "night"]
    characters: list[str] = Field(min_length=2, max_length=3, description="exact names from THE PARTS")
    knows: str = Field(min_length=3, max_length=300, description="who knows what as the scene starts")
    beats: str = Field(min_length=8, max_length=500, description="what happens, in two or three sentences")
    ends_on: str = Field(min_length=3, max_length=240,
                         description="the moment it ends on: a line someone says, or a look on a face; never an action, "
                                     "since a scene is only what its people say")


class ActPlan(BaseModel):
    scenes: list[FilmScene] = Field(min_length=SCENES_PER_ACT, max_length=SCENES_PER_ACT)


class FilmLine(BaseModel):
    character: str = Field(description="who says it: an exact name from the scene")
    mood: str = Field(default="", description=f"how they say it, or empty: one of {', '.join(MOOD_NAMES)}")
    text: str = Field(min_length=1, max_length=400, description="only the words said")

    @field_validator("mood")
    @classmethod
    def _known(cls, v: str) -> str:
        v = (v or "").strip().lower()
        return v if v in MOOD_NAMES else ""


class Dialogue(BaseModel):
    lines: list[FilmLine] = Field(min_length=6, max_length=36)


# ------------------------------------------------------------------ the prompts

_RULES = """You write TV movies for Channel 8, Port Wexley's second television channel: made-for-television films,
made by WTV and shot on location around the town, in a Cornish harbour. They are fiction: every character is made
up and played by an actor; never a resident of the town, a real person or the town's own news. An hour and a half on
air with the ad breaks, about an hour and a quarter of story; it airs at nine in the evening, so nothing graphic, no swearing worse
than "bloody", and any violence off screen. It is drama on a small budget: every scene is two or three people
talking in one place, and only what they say reaches the screen, so the story must live in dialogue."""

_PITCH = _RULES + """
Pitch {n} different films. Each a {genre}, unless told otherwise, with its own title, a logline and a hook. Each needs
at most {parts} speaking parts. Make them distinct from one another and from the films already made. Return ONLY JSON."""

_OUTLINE = _RULES + """
Outline THE FILM from its pitch: the title, the genre, the logline, the tone, at most {parts} parts (first name and
surname each, made up, none from RESIDENTS; a gender and an age band each, for casting), {acts} acts, and the
ending with the film's last line and who says it. Each act is about {act_min} minutes, {scenes} scenes, and ends on a moment
that carries the audience over the ad break; the last act ends the film. A story that plays fair: set up what
pays off, and nothing solved by luck. The places are THE SETS only, as the film names them. Return ONLY JSON."""

_ACT = _RULES + """
Plan ACT {n} of {acts} of THE FILM: exactly {scenes} scenes, in order, keeping to the outline and to the acts already
planned. Each on one set from THE SETS (by id), at day, evening or night, with two or three of THE PARTS (exact
names). For each: who knows what as it starts (where each of them has been, what each knows and only suspects), what
happens, and what it ends on: a line or a look, never an action. Vary the places and the pairings; let scenes cut
between threads. {last}Return ONLY JSON."""

_SCENE = _RULES + """
Write THIS SCENE of THE FILM as dialogue: every line one of the scene's characters (exact name) speaking, with a mood
when it shows on their face (one of {moods}), or none. No narrator, no stage directions, no captions, no names in
front of a line, never a character calling themselves by name. Real dialogue: people interrupt, dodge, say less than
they mean and give themselves away; British, West Country where it suits. Anything the audience must see has to be
said, briefly and naturally ("You've cut your hand."). Start where the plan starts and end exactly on what it ends
on. Keep to everything THE SCRIPT SO FAR says, and never repeat it. About {words} words, {lo} to {hi} lines.
Return ONLY JSON."""


def _sets_text() -> str:
    return "\n".join(f"  - {sid}: {name}: {blurb}" for sid, (name, blurb) in SETS.items())


def _parts_text(o: Outline) -> str:
    return "\n".join(f"  - {p.name} ({p.gender}, {p.age}): {p.who} Wants: {p.wants}" for p in o.parts)


def _outline_text(o: Outline) -> str:
    return (f"\"{o.title}\", a {o.genre}. {o.logline}\nTone: {o.tone}\nTHE PARTS:\n{_parts_text(o)}\n"
            + "\n".join(f"ACT {i + 1}, \"{a.name}\": {a.happens} Ends on: {a.ends_on}" for i, a in enumerate(o.acts))
            + f"\nTHE ENDING: {o.ending}")


def _scene_row(sc: FilmScene | dict) -> str:
    sc = sc if isinstance(sc, dict) else sc.model_dump()
    return (f"{SETS[sc['set']][0]} ({sc['when']}): {', '.join(sc['characters'])}. As it starts: {sc['knows']} "
            f"What happens: {sc['beats']} Ends on: {sc['ends_on']}")


def _act_text(plan: ActPlan | dict) -> str:
    scenes = plan.scenes if isinstance(plan, ActPlan) else plan["scenes"]
    return "\n".join(f"  {i + 1}. {_scene_row(sc)}" for i, sc in enumerate(scenes))


# ------------------------------------------------------------------ the film's folder

def bank_dir() -> Path:
    """data/movies, or NEWSROOM_MOVIES (the tests' own: they must never air, list or change the real bank)."""
    import os

    return Path(os.environ.get("NEWSROOM_MOVIES") or CONFIG.paths.data / "movies")


def slug(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", title.lower()).strip("-")[:48] or "film"


def load(folder: Path) -> dict:
    return json.loads((folder / "film.json").read_text(encoding="utf-8"))


def save(folder: Path, film: dict) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    tmp = folder / "film.json.tmp"
    tmp.write_text(json.dumps(film, indent=1, ensure_ascii=False), encoding="utf-8")
    tmp.replace(folder / "film.json")


def films(bank: Path | None = None) -> list[tuple[Path, dict]]:
    bank = bank or bank_dir()
    return [(p.parent, load(p.parent)) for p in sorted(bank.glob("*/film.json"))]


def start(pitch: Pitch | dict, bank: Path | None = None) -> Path:
    """A new film's folder from its pitch: nothing written yet."""
    pitch = pitch if isinstance(pitch, dict) else pitch.model_dump()
    bank = bank or bank_dir()
    folder = bank / slug(pitch["title"])
    if (folder / "film.json").exists():
        raise FileExistsError(f"{folder} is already a film")
    save(folder, {"made": date.today().isoformat(), "pitch": pitch, "outline": None, "acts": [], "scenes": {},
                  "approved": None})
    return folder


# ------------------------------------------------------------------ the calls

def _residents(world: World) -> set[str]:
    return {p.name for p in world.people} if world is not None else set()


def _check_outline(o: Outline, world: World) -> None:
    names = [p.name for p in o.parts]
    if len(set(names)) != len(names):
        raise llm.AskAgain("two parts have the same name")
    if len({n.split()[0] for n in names}) != len(names):
        raise llm.AskAgain("two parts share a first name: give each their own, so the dialogue never confuses them")
    taken = sorted(set(names) & _residents(world))
    if taken:
        raise llm.AskAgain(f"{', '.join(taken)} is a resident of the town: the parts are made up, so rename them")


def _check_act(plan: ActPlan, o: Outline) -> None:
    names = {p.name for p in o.parts}
    for i, sc in enumerate(plan.scenes):
        if sc.set not in SETS:
            raise llm.AskAgain(f"scene {i + 1} is on {sc.set!r}, which is not one of THE SETS")
        if not set(sc.characters) <= names or len(set(sc.characters)) != len(sc.characters):
            raise llm.AskAgain(f"scene {i + 1} names {sc.characters}: only THE PARTS, each once")


def _ask(task: str, schema, system: str, user: str, check, *, max_tokens: int, timeout_s: float):
    """The model's answer, checked; once more, told what was wrong, if the check fails."""
    got = llm.complete_json(task, schema, system, user, max_tokens=max_tokens, timeout_s=timeout_s)
    try:
        check(got)
    except llm.AskAgain as e:
        log.info("movies: asking once more (%s)", e)
        got = llm.complete_json(task, schema, system, f"{user}\n\nYOUR FIRST DRAFT was wrong: {e}. Write it again.",
                                max_tokens=max_tokens, timeout_s=timeout_s)
        check(got)
    return got


def pitch(world: World, genre: str | None = None, bank: Path | None = None) -> Pitches:
    made = [f"  - \"{f['pitch']['title']}\", a {f['pitch']['genre']}: {f['pitch']['logline']}" for _, f in films(bank)]
    genre = genre or next((g for g in GENRES if g not in {f["pitch"]["genre"] for _, f in films(bank)}), GENRES[0])
    user = ("THE FILMS ALREADY MADE:\n" + ("\n".join(made) if made else "  none yet")
            + f"\n\nTHE SETS (where it can be shot):\n{_sets_text()}" + creative.for_planner(world, SHOW, series=True))
    return llm.complete_json(TASK, Pitches, _PITCH.format(n=PITCHES, genre=genre, parts=MAX_PARTS), user,
                             max_tokens=PLAN_TOKENS, timeout_s=PLAN_TIMEOUT_S)


def outline(world: World, film: dict) -> Outline:
    p = film["pitch"]
    residents = sorted(_residents(world))
    user = (f"THE PITCH: \"{p['title']}\", a {p['genre']}. {p['logline']} {p.get('hook', '')}\n\n"
            f"THE SETS:\n{_sets_text()}\n\nRESIDENTS (never a part's name): {', '.join(residents)}"
            + creative.for_planner(world, SHOW, series=True))
    system = _OUTLINE.format(parts=MAX_PARTS, acts=ACTS, scenes=SCENES_PER_ACT, act_min=round(TARGET_S / ACTS / 60))
    check = lambda o: _check_outline(o, world)        # noqa: E731
    ask = lambda more="": _ask(TASK, Outline, system, user + more, check,  # noqa: E731
                               max_tokens=PLAN_TOKENS, timeout_s=PLAN_TIMEOUT_S)
    first = ask()
    context = user.split("RESIDENTS")[0] + "(and the residents' names, which no part may take)"
    return creative.redraft(world, SHOW, "outline", first, text=_outline_text, again=ask, check=check,
                            context=context, margin=False)


def plan_act(film: dict, n: int) -> ActPlan:
    o = Outline.model_validate(film["outline"])
    before = "".join(f"\n\nACT {i + 1}, AS PLANNED:\n{_act_text(a)}" for i, a in enumerate(film["acts"][:n]))
    user = f"THE FILM:\n{_outline_text(o)}\n\nTHE SETS:\n{_sets_text()}{before}"
    last = (f"The last scene is the film's last: it ends on the ending, with its last line. " if n == ACTS - 1 else
            "The last scene ends on the act's moment, before the ad break. ")
    return _ask(TASK, ActPlan, _ACT.format(n=n + 1, acts=ACTS, scenes=SCENES_PER_ACT, last=last), user,
                lambda a: _check_act(a, o), max_tokens=PLAN_TOKENS, timeout_s=PLAN_TIMEOUT_S)


def _key(act: int, scene: int) -> str:
    return f"{act + 1}.{scene + 1}"


def _plan_rows(film: dict) -> list[tuple[str, dict]]:
    return [(_key(a, s), sc) for a, plan in enumerate(film["acts"]) for s, sc in enumerate(plan["scenes"])]


def _live_rows(film: dict) -> list[tuple[str, dict]]:
    """The scenes still in the film: film["cut"] lists the ones taken out after it was written (for length, the user,
    2026-11-23), kept in film.json but never written again, rendered or voiced."""
    cut = set(film.get("cut", ()))
    return [(k, sc) for k, sc in _plan_rows(film) if k not in cut]


def finished(film: dict) -> bool:
    return len(film.get("acts", ())) == ACTS and all(k in film["scenes"] for k, _ in _live_rows(film))


def _lines_text(lines: list[dict]) -> str:
    return "\n".join(f"{l['character']}: {l['text']}" for l in lines)


def _so_far(film: dict, upto: str) -> str:
    out = []
    for k, sc in _live_rows(film):
        if k == upto:
            break
        if k in film["scenes"]:
            out.append(f"[Scene {k}, {SETS[sc['set']][0]}, {sc['when']}]\n{_lines_text(film['scenes'][k])}")
    return "\n\n".join(out)


# What leaked into the spoken words of the six films written on 2026-11-23 (66 lines of about 3,800, found by the
# creative editor's read): the JSON's own mood field on the end of a line (`','mood':'happy`, `","mood":"worried`,
# `Mood: worried`), `</br>`, a stray brace or pilcrow, zero-width spaces, a `.com`, and two sentences run together
# ("else.Whoever's"). All of it would be voiced.
_Q = "\"'" + "".join(map(chr, (0x2018, 0x2019, 0x201C, 0x201D)))       # straight and curly quotes, either may leak
_ZW = "".join(map(chr, (0x200B, 0x200C, 0x200D, 0xFEFF)))                       # zero-width spaces
_MARKS = chr(0xB6) + chr(0xA7) + chr(0xFFFD)                                    # a pilcrow, a section sign
_LEAKED_MOOD = re.compile(rf"\s*[{_Q}]*\s*,?\s*[{_Q}]?\bmood[{_Q}]?\s*:\s*[{_Q}]?([A-Za-z]*)[^.!?]*[.!?]?$", re.I)
_MARKUP = re.compile(rf"</?\s*br\s*/?>|<[a-z/][^>]{{0,12}}>|[{{}}{_ZW}{_MARKS}]")
_RUN_ON = re.compile(r"([a-z])([.!?])([A-Z][a-z])")
_STILL_BAD = re.compile(rf"[<>{{}}\[\]]|\bmood\s*[{_Q}:]|[a-z][.!?][a-z]{{2}}", re.I)


def scrub(text: str, mood: str = "") -> tuple[str, str]:
    """A line's words with what leaked into them taken out, and its mood (a leaked one, when it had none)."""
    if m := _LEAKED_MOOD.search(text):
        text = text[:m.start()]
        found = m.group(1).lower()
        mood = mood or (found if found in MOOD_NAMES else "")
    text = _MARKUP.sub("", text).replace(chr(0x2009), " ").replace(chr(0xA0), " ")
    text = re.sub(r"\.com$", ".", text.rstrip())
    text = _RUN_ON.sub(r"\1\2 \3", text)
    text = re.sub(r"[\s,]+$", "", text)
    left, right = chr(0x201C), chr(0x201D)                # a quote left dangling at the end, never a closed one
    if (text.endswith('"') and text.count('"') % 2 or text.endswith(left)
            or text.endswith(right) and text.count(right) > text.count(left)):
        text = text[:-1].rstrip()
    return re.sub(r"\s{2,}", " ", text).strip(), mood


def check_scene(d: Dialogue, sc: dict, cast: list[str], keep: str = "") -> None:
    """scrub() and soap.tidy mend what a scene writer gets wrong in the lines (leaked markup, a name in front, a
    direction, a speaker naming themselves); then nothing markup-like is left, every line is one of the scene's people
    and at least two of them speak."""
    for l in d.lines:
        l.text, l.mood = scrub(l.text, l.mood)
    script = SimpleNamespace(lines=[SimpleNamespace(guest_name=l.character, text=l.text, mood=l.mood)
                                    for l in d.lines if l.text])
    soap.tidy(script, list(sc["characters"]), cast, keep)
    d.lines = [FilmLine(character=l.guest_name, text=l.text, mood=l.mood) for l in script.lines]
    who = [l.character for l in d.lines]
    if stray := set(who) - set(sc["characters"]):
        raise llm.AskAgain(f"lines are spoken by {sorted(stray)}, who are not in this scene")
    if len(set(who)) < 2:
        raise llm.AskAgain("only one character speaks")
    if bad := [l.text for l in d.lines if _STILL_BAD.search(l.text)]:
        raise llm.AskAgain(f"a line has markup or run-together words in it, which would be read aloud: {bad[0]!r}. "
                           "Each line's text is only the words said; the mood goes in its own field")
    if len(d.lines) < 6:
        raise llm.AskAgain("the scene is too short")


def write_scene(film: dict, key: str) -> Dialogue:
    o = Outline.model_validate(film["outline"])
    rows = _plan_rows(film)
    idx = [k for k, _ in rows].index(key)
    sc = rows[idx][1]
    last = idx == len(rows) - 1
    act = int(key.split(".")[0])
    plan = "\n".join(f"  {'>' if k == key else ' '} {k}. {_scene_row(s)}" for k, s in rows)
    so_far = _so_far(film, key)
    words = int(SCENE_S * WORDS_PER_S)
    user = (f"THE FILM:\n{_outline_text(o)}\n\nEVERY SCENE (> marks this one):\n{plan}\n\n"
            f"THE SCRIPT SO FAR:\n{so_far or '(nothing yet: this is the opening scene)'}\n\n"
            f"THIS SCENE, {key} (act {act} of {ACTS}): at {SETS[sc['set']][0]} ({SETS[sc['set']][1]}), {sc['when']}. "
            f"In it: {', '.join(sc['characters'])}. As it starts: {sc['knows']} What happens: {sc['beats']} "
            f"It ends on: {sc['ends_on']}"
            + (" This is the LAST scene of the film: it ends on the ending, with the film's last line." if last else
               " It is the last scene before the ad break." if key.endswith(f".{SCENES_PER_ACT}") else ""))
    system = _SCENE.format(moods=", ".join(MOOD_NAMES), words=words, lo=12, hi=24)
    cast = [p.name for p in o.parts]
    return _ask(SCENE_TASK, Dialogue, system, user, lambda d: check_scene(d, sc, cast),
                max_tokens=SCENE_TOKENS, timeout_s=SCENE_TIMEOUT_S)


def _models_on() -> str | None:
    """Why the film can't be written now, or None."""
    for task in {TASK, SCENE_TASK}:
        name = llm.provider_for(task)
        if name == "off":
            return "the models are off (NEWSROOM_LLM=off)"
        try:
            llm._api_key(llm._provider(name))
        except llm.LLMError as e:
            return str(e)
    return None


def write(folder: Path, world: World, say=print) -> dict:
    """Write the film as far as it goes: the outline, each act's plan, then each scene, saving after every call.
    Stops on a failure (LLMError) with everything so far kept; run again to go on."""
    film = load(folder)
    if film.get("outline") is None:
        say("outline ...")
        film["outline"] = outline(world, film).model_dump()
        save(folder, film)
        say(_outline_text(Outline.model_validate(film["outline"])))
    while len(film["acts"]) < ACTS:
        n = len(film["acts"])
        say(f"act {n + 1} ...")
        film["acts"].append(plan_act(film, n).model_dump())
        save(folder, film)
        say(_act_text(film["acts"][-1]))
    for key, _ in _live_rows(film):
        if key in film["scenes"]:
            continue
        d = write_scene(film, key)
        film["scenes"][key] = [l.model_dump() for l in d.lines]
        save(folder, film)
        say(f"scene {key}: {len(d.lines)} lines, ~{seconds(film['scenes'][key]):.0f} s")
    render(folder, film, say)
    return film


# ------------------------------------------------------------------ script.md

def seconds(lines: list[dict]) -> float:
    """An estimate until the film is voiced: the words at Marina Row's measured pace."""
    return sum(len(l["text"].split()) for l in lines) / WORDS_PER_S


def script_text(film: dict) -> str:
    o = film["outline"]
    out = [f"# {o['title']}", "", f"*A {o['genre']}. {o['logline']}*", "", "Cast:"]
    out += [f"- {p['name']} ({p['gender']}, {p['age']}): {p['who']}" for p in o["parts"]]
    live = dict(_live_rows(film))
    n = 0
    for a, plan in enumerate(film["acts"]):
        out += ["", f"## Act {a + 1}: {o['acts'][a]['name']}"]
        for s, sc in enumerate(plan["scenes"]):
            k = _key(a, s)
            if k not in live:
                continue
            lines = film["scenes"].get(k, [])
            n += 1
            out += ["", f"### {n}. {SETS[sc['set']][0]} ({sc['set']}, {sc['when']}): {', '.join(sc['characters'])}"
                        f" [~{seconds(lines):.0f} s]"]
            out += [f"{l['character'].upper()}{' (' + l['mood'] + ')' if l.get('mood') else ''}: {l['text']}"
                    for l in lines] or ["(not written yet)"]
    total = sum(seconds(film["scenes"][k]) for k in live if k in film["scenes"])
    written = sum(k in film["scenes"] for k in live)
    cut = f", {len(film['cut'])} cut" if film.get("cut") else ""
    out += ["", "---", f"Estimated running time: {total / 60:.1f} minutes of {TARGET_S / 60:.0f} "
                       f"({written} scenes written of {len(live)}{cut}), at {WORDS_PER_S} words a "
                       "second; the real figure comes once it is voiced."]
    return "\n".join(out) + "\n"


def _hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()


def render(folder: Path, film: dict, say=print) -> Path:
    """script.md from film.json. A script.md edited by hand since it was last written is never overwritten: the new
    one goes to script.new.md."""
    text = script_text(film)
    path = folder / "script.md"
    if path.exists() and film.get("rendered") and _hash(path.read_text(encoding="utf-8")) != film["rendered"]:
        path = folder / "script.new.md"
        say(f"script.md has been edited by hand, so this one is {path.name}")
    else:
        film["rendered"] = _hash(text)
        save(folder, film)
    path.write_text(text, encoding="utf-8")
    say(f"wrote {path}")
    return path


@dataclass
class Scene:
    number: int
    set: str
    when: str
    characters: list[str]
    lines: list[tuple[str, str, str]]      # (character, text, mood or "")


def parse(path: Path) -> tuple[list[str], list[Scene]]:
    """script.md as written (and perhaps edited): the cast by name, and the scenes in order. A line's NAME is a
    cast member's name in capitals; anything after `---` is not read."""
    cast: list[str] = []
    scenes: list[Scene] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "---":
            break
        if line.startswith("- ") and not scenes and "(" in line:
            cast.append(line[2:line.index("(")].strip())
        elif m := _SCENE_HEAD.match(line):
            if m.group(3) not in SETS:
                raise ValueError(f"scene {m.group(1)} is on {m.group(3)!r}, not one of the sets")
            scenes.append(Scene(int(m.group(1)), m.group(3), m.group(4), [c.strip() for c in m.group(5).split(",")], []))
        elif (m := _SPOKEN.match(line)) and scenes:
            by_caps = {c.upper(): c for c in cast}
            who = by_caps.get(m.group(1))
            if who is None:
                raise ValueError(f"scene {scenes[-1].number}: {m.group(1)!r} is not in the cast")
            mood = m.group(2) or ""
            if mood and mood not in MOOD_NAMES:
                raise ValueError(f"scene {scenes[-1].number}: {mood!r} is not a mood ({', '.join(MOOD_NAMES)})")
            scenes[-1].lines.append((who, m.group(3).strip(), mood))
    return cast, scenes


def estimate(path: Path) -> float:
    _, scenes = parse(path)
    return sum(len(t.split()) for s in scenes for _, t, _ in s.lines) / WORDS_PER_S


# ------------------------------------------------------------------ the creative editor

def enrol():
    """Enrol the film with the creative editor, vetted (its outline before the acts are planned). Returns an undo."""
    return creative.register(
        SHOW, TITLE, kind="fiction", vetted=True, airs_at=AIRS_AT,
        brief=("Channel 8's TV movie at nine: a bank of made-for-television films, each written in full ahead of air "
               f"and read before it joins the bank; about an hour and a quarter of story in {ACTS} acts, 21:00 to 22:30 with the breaks, two or three people "
               "talking in each scene, on location around the town. Fiction: none of it reaches the town."),
        decides="the film's premise, parts, acts and ending; each act's scenes; then the dialogue")


def read(folder: Path, world: World) -> list[str] | None:
    """The creative editor reads the finished script once: its notes, or None (it passes, or can't be asked)."""
    return creative.vet(world, SHOW, "film", (folder / "script.md").read_text(encoding="utf-8"), margin=False)


# ------------------------------------------------------------------ casting and the scenes on air

# Where the people stand on a town backdrop: the soap's sets have furniture across the front to hide where a seated
# figure ends, these don't, so the figures stand in the foreground with the frame's bottom edge as the cut (as a medium
# shot does). Provisional, until the first recording is watched (2026-11-23): (x, baseline y, scale, facing).
FILM_MARKS = {"a": (88, 182, 2, 1), "b": (232, 182, 2, -1), "c": (160, 182, 2, -1)}
TOD = {"day": "day", "evening": "dusk", "night": "night"}
SPEED = {"young": 1.03, "middle": 1.0, "old": 0.94}


def _hash_of(name: str) -> int:
    return int(hashlib.sha1(name.encode("utf-8")).hexdigest()[:8], 16)


def cast(film: dict) -> dict:
    """A voice for each part from the town's guest pool, by gender and age, no two the same where the pool allows;
    the cast is the film's own and none of them joins the town (they are pinned by name, never residents). Written
    to cast.toml, where a voice or a look can be changed by hand."""
    from newsroom import world as world_mod

    used: set[str] = set()
    out = {}
    for p in film["outline"]["parts"]:
        pool = world_mod.guest_pool(p["gender"], p["age"]) or world_mod.guest_pool(p["gender"], None)
        free = [v for v in pool if v not in used] or pool
        voice = free[_hash_of(p["name"]) % len(free)]
        used.add(voice)
        out[p["name"]] = {"voice": voice, "speed": SPEED.get(p["age"], 1.0), "gender": p["gender"], "age": p["age"],
                          "who": p["who"]}
    return out


def cast_toml(cast: dict) -> str:
    lines = ["# Who speaks as whom: a voice from assets/voices/voices.toml for each part, and its speed. Change a",
             "# voice here and only that part's lines are voiced again. A [\"Name\".look] table (sprites.Look fields)",
             "# dresses a part by hand; otherwise the look is drawn from the name, the voice and the age.", ""]
    for name, c in cast.items():
        lines += [f"[{json.dumps(name)}]", f"voice = {json.dumps(c['voice'])}", f"speed = {c['speed']}",
                  f"gender = {json.dumps(c['gender'])}", f"age = {json.dumps(c['age'])}", f"who = {json.dumps(c['who'])}", ""]
    return "\n".join(lines)


def load_cast(folder: Path) -> dict:
    import tomllib
    return tomllib.loads((folder / "cast.toml").read_text(encoding="utf-8"))


def look_of(name: str, c: dict):
    from newsroom.sprites import Look, guest_look

    if spec := c.get("look"):
        tup = lambda v: tuple(tup(x) for x in v) if isinstance(v, list) else v     # noqa: E731  Looks are hashed
        return Look(**{k: tup(v) for k, v in spec.items()})
    return guest_look(name, c["voice"], c.get("who", ""), c.get("age", ""))


def _view(seg, v, idx) -> None:
    """A scene at its time of day; the titles and the credits as cards of their own (movie_cards.py). Anything else in
    the film's slot (the ident, the adverts in a break) is left as the engine draws it."""
    card = seg.work.get("card")
    if card:
        v.mode, v.scene, v.speaker = f"movie_{card['card']}", card, None
        v.tod = card.get("tod", v.tod)
    elif seg.work.get("set") in SETS:
        v.tod = seg.work.get("tod") or "day"


def install():
    """The film's show on the engine, whatever film: the scenes bare (no lower third, ticker or clock) on the town's
    backdrops with FILM_MARKS, each graded for its time of day, and the titles and credits as cards of their own.
    Returns an undo. (Nobody else is seated on the town's backdrops on Channel 8: Tideline and The Coast Road film
    on location, so FILM_MARKS can stand for the whole run.)"""
    from newsroom import locations, player, scenes

    from . import movie_cards as cards

    saved = dict(locations.MARKS)
    for sid in SETS:
        locations.MARKS[sid] = dict(FILM_MARKS)
    player.SEATS[SHOW] = 3
    player.BARE_SHOWS.add(SHOW)
    player.VIEW_HOOKS[SHOW] = _view
    scenes.SCENES[cards.TITLES_MODE], scenes.SCENES[cards.CREDITS_MODE] = cards.draw_titles, cards.draw_credits
    scenes.NO_CLOCK.update((cards.TITLES_MODE, cards.CREDITS_MODE))

    def undo() -> None:
        for mode in (cards.TITLES_MODE, cards.CREDITS_MODE):
            scenes.SCENES.pop(mode, None)
            scenes.NO_CLOCK.discard(mode)
        locations.MARKS.clear(), locations.MARKS.update(saved)
        for reg in (player.SEATS, player.VIEW_HOOKS):
            reg.pop(SHOW, None)
        player.BARE_SHOWS.discard(SHOW)
    return undo


def pin(cast: dict):
    """A film's characters' voices and looks, pinned by name (never residents). Returns an undo."""
    from newsroom import scenes, world as world_mod

    for name, c in cast.items():
        world_mod.PINNED_VOICES[name] = (c["voice"], float(c.get("speed", 1.0)), "b")
        scenes.PINNED_LOOKS[name] = look_of(name, c)

    def undo() -> None:
        for name in cast:
            world_mod.PINNED_VOICES.pop(name, None)
            scenes.PINNED_LOOKS.pop(name, None)
    return undo


def register_film(cast: dict, title: str):
    """One film on its own (tools/film.py): Channel 8, the film's show (install), its cast pinned, and a plain show
    for its scenes. Returns an undo."""
    from newsroom import channel, schedule
    from newsroom.models import SegmentType as T
    from newsroom.schedule import Show

    from . import CHANNEL_8

    before = channel.use(CHANNEL_8)               # Channel 8's bug in the corner, not Channel 7's
    schedule.SHOWS[SHOW] = Show(SHOW, title.upper(), "CHANNEL 8", (70, 50, 96), pattern=(T.interview,),
                                target_s={T.interview: SCENE_S}, cast=("guest",), lead="guest",
                                station=f"{title}, a TV movie on Channel 8", light=False, repeats_overnight=False)
    undo_show, undo_pins = install(), pin(cast)

    def undo() -> None:
        undo_pins()
        undo_show()
        schedule.SHOWS.pop(SHOW, None)
        channel.use(before)
    return undo


# ------------------------------------------------------------------ voiced, and fit to air

def voice_hash(folder: Path) -> str:
    """What a film's voicing depends on: script.md, and each part's voice and speed in cast.toml (a look or a credit
    can change without the film being voiced again)."""
    import tomllib

    cast = tomllib.loads((folder / "cast.toml").read_text(encoding="utf-8"))
    voices = json.dumps({n: [c["voice"], c.get("speed", 1.0)] for n, c in sorted(cast.items())})
    return hashlib.sha1((folder / "script.md").read_bytes() + voices.encode("utf-8")).hexdigest()


def voiced(folder: Path) -> list[dict] | None:
    """The film's voiced scenes (segments.json), or None if it isn't fit to air: not approved, not finished, voiced
    for another script or cast, or a clip gone from disk."""
    try:
        film = load(folder)
        if not film.get("approved") or not finished(film):
            return None
        data = json.loads((folder / "segments.json").read_text(encoding="utf-8"))
        if data["script"] != voice_hash(folder):
            return None
    except (OSError, ValueError, KeyError):
        return None
    scenes = data["scenes"]
    if len(scenes) != len(_live_rows(film)) or not all(
            l.get("wav_path") and Path(l["wav_path"]).exists() for s in scenes for l in s["lines"]):
        return None
    return scenes


def line_key(c: dict, name: str, text: str) -> str:
    """A voiced line's cache key: the voice, its speed, the speaker and the words, so a recast part or a changed line
    is voiced again and nothing else."""
    return "film_" + hashlib.sha1(f"{c['voice']}|{c.get('speed', 1.0)}|{name}|{text}".encode("utf-8")).hexdigest()[:12]


def scene_segment(slot: int, sc: dict, lines: list):
    """One scene, ready to air: an interview item whose every line is a character, on its set, its people seated in
    order, at its time of day."""
    from newsroom.models import Segment, SegmentState, SegmentType

    return Segment(slot_id=slot, type=SegmentType.interview, show=SHOW, state=SegmentState.ready,
                   headline=f"Scene {sc['number']}", lines=lines, part=f"scene {sc['number']}",
                   work={"set": sc["set"], "seats": list(sc["characters"]), "tod": TOD.get(sc["when"], "day")})


# ------------------------------------------------------------------ the command line

def _world(path: str | None) -> World:
    from newsroom import world as world_mod
    return world_mod._from_dict(json.loads(Path(path or CONFIG.paths.world).read_text(encoding="utf-8")))


def _cli(argv: list[str]) -> int:
    import argparse

    ap = argparse.ArgumentParser(prog="python -m entertainment.movies", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pitch", help="three pitches, saved to data/movies/pitches.json")
    p.add_argument("--genre", help=f"one of {', '.join(GENRES)}, or anything (default: the next not yet made)")
    n = sub.add_parser("new", help="start a film from a pitch, or from your own premise")
    n.add_argument("pick", nargs="?", type=int, help="the pitch's number in data/movies/pitches.json")
    n.add_argument("--title"), n.add_argument("--genre"), n.add_argument("--premise")
    for name, what in (("write", "write the film, or go on with it"), ("read", "the creative editor's notes"),
                       ("estimate", "the running time of script.md"), ("approve", "into the bank")):
        s = sub.add_parser(name, help=what)
        s.add_argument("folder")
    sub.add_parser("list", help="the films in the bank")
    for s in sub.choices.values():
        s.add_argument("--world", help="the world to read (default: data/world.json; never saved)")
    a = ap.parse_args(argv)

    if a.cmd == "list":
        for folder, f in films():
            t = f["outline"]["title"] if f.get("outline") else f["pitch"]["title"]
            state = ("approved " + f["approved"] if f.get("approved") else
                     f"{len(f['scenes'])}/{ACTS * SCENES_PER_ACT} scenes" if f.get("acts") else "pitched")
            print(f"{folder.name}: {t} ({f['pitch']['genre']}), {state}")
        return 0
    if a.cmd == "estimate":
        print(f"{estimate(Path(a.folder) / 'script.md') / 60:.1f} minutes")
        return 0
    if a.cmd == "approve":
        folder = Path(a.folder)
        f = load(folder)
        if not finished(f):
            print("not finished: write it first")
            return 1
        f["approved"] = date.today().isoformat()
        save(folder, f)
        print(f"{folder.name} approved")
        return 0
    if a.cmd == "new":
        if a.pick:
            got = json.loads((bank_dir() / "pitches.json").read_text(encoding="utf-8"))["pitches"]
            chosen = got[a.pick - 1]
        elif a.title and a.premise:
            chosen = {"title": a.title, "genre": a.genre or GENRES[0], "logline": a.premise, "hook": ""}
        else:
            print("give a pitch's number, or --title and --premise")
            return 1
        print(f"started {start(chosen)}")
        return 0

    if why := _models_on():
        print(f"can't ask the model: {why}")
        return 1
    world = _world(a.world)
    enrol()
    if a.cmd == "pitch":
        got = pitch(world, a.genre)
        bank_dir().mkdir(parents=True, exist_ok=True)
        (bank_dir() / "pitches.json").write_text(json.dumps(got.model_dump(), indent=1, ensure_ascii=False),
                                                 encoding="utf-8")
        for i, pt in enumerate(got.pitches, 1):
            print(f"{i}. {pt.title} ({pt.genre})\n   {pt.logline}\n   {pt.hook}\n")
        print(llm.usage_summary())
        return 0
    folder = Path(a.folder)
    if a.cmd == "write":
        try:
            write(folder, world)
        except llm.LLMError as e:
            print(f"stopped: {e}. Everything so far is saved; run write again to go on.")
            print(llm.usage_summary())
            return 1
        print(llm.usage_summary())
        return 0
    if a.cmd == "read":
        notes = read(folder, world)
        text = "\n".join(f"- {x}" for x in notes) if notes else "The creative editor has no notes."
        (folder / "notes.md").write_text(f"# The creative editor on {folder.name}\n\n{text}\n", encoding="utf-8")
        print(text)
        print(llm.usage_summary())
        return 0
    return 1


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    sys.exit(_cli(sys.argv[1:]))
