"""A soap on Channel 8: a series played one episode a Channel 8 night (docs/ENGINE.md, "Channel 8's evening";
the first is Marina Row, entertainment/marina_row.py and docs/MARINA_ROW.md).

Each episode is planned in the back office, in one call, from BOOK_FROM: its scenes (where, who, who knows what at
the start, what happens, what each ends on) and its cliffhanger, the question the town will ask and the closing
line that leaves it. Every ARC_EPISODES aired episodes another call plans the arc: two or three storylines, a beat
for each episode. Both are on the "soap" route (Sonnet unless config.toml routes it elsewhere).

The episode is written live, scene by scene, as interview items whose every line is a character (speaker "guest",
guest_name the character), like Wexley Wits' rounds. Each scene's brief carries its plan ("{s3}"), and every
scene is given the whole episode and what the scenes before it say, since they are written side by side before
any airs. The cliffhanger scene is the show's closing item, so it lands at the end of the slot; spare minutes go
to adverts before it.

Fiction inside the town (writers.FICTION_SHOWS): no character becomes a resident, gets a memory or makes the
news, and its archive entries say only that it aired. Its actors are residents. On air it is bare
(player.BARE_SHOWS: no lower third, ticker or clock), each scene on its own set (seg.work["set"]), the cast seated
on its marks, each character drawn as their actor in costume (scenes.PINNED_LOOKS) and speaking in their actor's
voice (world.PINNED_VOICES). An episode is "aired" once its last scene went out; only then does the town talk
about its cliffhanger (newsroom/talk.py), does "previously" include it, or does the arc move on: the arc's plan
never reaches any other writer.
"""
from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from datetime import date, datetime
from typing import Annotated

from pydantic import BaseModel, Field

from newsroom import llm, schedule
from newsroom.config import CONFIG
from newsroom.models import SegmentType as T, _clip_words
from newsroom.schedule import Item as I, Show
from newsroom.world import World

from . import creative

log = logging.getLogger(__name__)

SCENES = 6
ARC_EPISODES = 6
BOOK_FROM = "18:30"
TASK = "soap" if "soap" in CONFIG.llm.routes else "senior_editor"     # Sonnet, either way, as config.toml stands
PREVIOUSLY = 3                     # aired episodes the planner and the writers are reminded of
WRITTEN_CHARS = 700                # each scene written so far tonight, as the later scenes see it
TOKEN = re.compile(r"\{([sx])([0-9]+)\}")        # {s3}: the plan's third scene; {x2}: its second spare
SPARES = 6                         # short side scenes for the minutes the plan leaves (the loop: three, then adverts)


@dataclass(frozen=True)
class Series:
    id: str                        # the show id
    title: str                     # "Marina Row"
    bible: str                     # the premise, the street and the rule that it is fiction, for every prompt
    cast: tuple                    # marina_row.Part: character, actor, gender, age, household, look, voice
    sets: dict                     # set id -> (name, blurb with who takes mark a, marks)
    airs_at: str                   # "20:20"
    opening: tuple[str, ...]       # the first arc's storylines
    stand_in: tuple                # with no model: (title, cliffhanger, last line, scenes, spares), each (set, cast, beats)
    quiet: tuple = ()              # spares the plan didn't give, in turn: (set, characters, what about)
    colour: tuple = (40, 90, 120)
    tone: str = "warm, sharp and a little heightened, a British soap: rows over the bins, secrets in the pub"
    ident: str = ""                # the opening titles' announcement
    characters: dict = field(default_factory=dict, compare=False, hash=False)

    def __post_init__(self):
        self.characters.update({p.character: p for p in self.cast})


# ------------------------------------------------------------------ the plans

class Storyline(BaseModel):
    name: str = Field(min_length=3, max_length=60, description="a short name for the storyline")
    characters: list[str] = Field(min_length=1, max_length=4, description="exact names from THE CHARACTERS")
    beats: list[str] = Field(min_length=ARC_EPISODES, max_length=ARC_EPISODES,
                             description=f"what happens in it in each of the next {ARC_EPISODES} episodes, one line each")


class Arc(BaseModel):
    storylines: list[Storyline] = Field(min_length=2, max_length=3)
    # Cut at a word, not failed: on the first run with the creative editor (2026-11-14) an arc failed on a turning
    # point past 200 characters and cost a second call; a second draft that failed so would lose the send-back.
    # Asked for in one sentence and given room: cut at 200, a turning point reached the creative editor ending
    # "and…", and the editor sent the arc back for an unfinished sentence (the first night on air, 2026-11-14).
    turning_point: Annotated[str, _clip_words(320)] = Field(
        min_length=8, max_length=320,
        description="the arc's big moment and in which episode, in one sentence of at most thirty words")


class Scene(BaseModel):
    set: str = Field(description="a set id from THE SETS")
    characters: list[str] = Field(min_length=2, max_length=3, description="exact names, the one at mark a first")
    knows: str = Field(min_length=3, max_length=240, description="who knows what as the scene starts")
    beats: str = Field(min_length=8, max_length=400, description="what happens, in two or three sentences")
    ends_on: str = Field(min_length=3, max_length=200, description="the moment the scene ends on")


class Episode(BaseModel):
    title: str = Field(min_length=3, max_length=60)
    scenes: list[Scene] = Field(min_length=SCENES, max_length=SCENES)
    cliffhanger: str = Field(min_length=8, max_length=120, description="the question the town will ask, as people "
                                                                        "would ask it, e.g. 'Will Queenie tell Davey?'")
    last_line: str = Field(min_length=3, max_length=200, description="the episode's closing line, said by a "
                                                                     "character in the last scene, that leaves it")
    said_by: str = Field(description="who says the last line: an exact name from the last scene")
    summary: str = Field(min_length=20, max_length=600, description="what happens, for the episodes to come")
    spares: list[Scene] = Field(min_length=5, max_length=SPARES,
                                description="short side scenes that change nothing in the story, for spare minutes")


_RULES = """You plan {title}, a British soap opera on Channel 8, Port Wexley's second television channel.
{bible}
Use only THE CHARACTERS (exact names) and THE SETS (exact ids). Never a resident of the town, never a real person,
never the town's own news: this street is fiction. Small, human stakes: money, love, pride, family, secrets.
Nothing grim or graphic: it airs at twenty past eight. Return ONLY JSON."""

_ARC = _RULES + """
Plan the next {n} episodes as two or three storylines that cross, each with one beat per episode, building to a
turning point; keep what the episodes so far have established, and pick up what they left open."""

_EPISODE = _RULES + """
Plan TONIGHT'S EPISODE: {scenes} scenes, each on one set with two or three characters (the one at the set's
mark a first), cutting between the storylines. For each: who knows what as it starts, what happens, what it ends
on. It must first answer the LAST CLIFFHANGER, if there is one, early in the episode. The last scene ends on the
episode's cliffhanger: give the question the town will ask, and the exact closing line, said by a character in that
scene. Then a short summary of what happens, for the episodes to come. Then {spares} SPARES: short side
scenes that may air between the fifth scene and the last, or not at all, so nothing in them may change the story or
give anything away: a joke in the pub, an old grievance, a small kindness, someone's hobby. They must not
contradict the scenes around them. Each on a different set or with different people from the one before, each
with a subject of its own."""


def _people(series: Series) -> str:
    return "\n".join(f"  - {p.character} ({p.household}), played by {p.actor}" for p in series.cast)


def _sets(series: Series) -> str:
    return "\n".join(f"  - {sid}: {name}: {blurb}" for sid, (name, blurb, _) in series.sets.items())


def state(world: World, series: Series) -> dict:
    with world.lock:
        return world.soaps.setdefault(series.id, {"show": series.id, "title": series.title, "arc": None,
                                                  "episodes": []})


def aired(world: World, series: Series, ep: dict) -> bool:
    """Did this episode's last scene go out? Planned and written isn't shown (the station may be off). The stamp
    is what lasts (stamp, below): the archive keeps about two and a half nights, and by the fourth Channel 8 night
    the first episode had left it, so the arc stopped moving on and "previously" forgot it. The archive still
    answers for an episode aired before there was a stamp."""
    return bool(ep.get("aired")) or any(
        e.get("show") == series.id and e.get("date") == ep["date"] and e.get("brief") == ep["last_brief"]
        for e in world.aired_archive())


def stamp(seg, world: World, series: Series) -> None:
    """player.AIRED_HOOKS: the episode's last scene went out, so the episode has aired, for good."""
    ep = tonight(world, series)
    if ep and seg.brief == ep["last_brief"] and not ep.get("aired"):
        with world.lock:
            ep["aired"] = True
        log.info("soap: %s episode %d aired", series.title, ep["number"])


def _aired_episodes(world: World, series: Series) -> list[dict]:
    return [ep for ep in state(world, series)["episodes"] if ep["date"] != world.last_date and aired(world, series, ep)]


def tonight(world: World, series: Series) -> dict | None:
    return next((ep for ep in reversed(state(world, series)["episodes"]) if ep["date"] == world.last_date), None)


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def should_commission(world: World, series: Series, now: float | None = None) -> bool:
    now = now or schedule.now()
    return (tonight(world, series) is None and _at(BOOK_FROM, now) <= now < _at(series.airs_at, now) + 20 * 60
            and schedule.show_at(_at(series.airs_at, now)).id == series.id)


def _previously(world: World, series: Series) -> str:
    done = _aired_episodes(world, series)[-PREVIOUSLY:]
    if not done:
        return "PREVIOUSLY: nothing yet. Tonight is the first episode."
    return ("PREVIOUSLY ON " + series.title.upper() + ":\n" + "\n".join(
        f"  - Episode {ep['number']}, \"{ep['title']}\": {ep['summary']} It ended on: {ep['cliffhanger']}"
        for ep in done))


def _arc_text(a: Arc) -> str:
    return ("\n".join(f"  - {s.name} ({', '.join(s.characters)}): " + " / ".join(
        f"{i + 1}. {b}" for i, b in enumerate(s.beats)) for s in a.storylines)
            + f"\n  The turning point: {a.turning_point}")


def _episode_text(ep: Episode) -> str:
    def row(sc: Scene) -> str:
        return (f"{sc.set}: {', '.join(sc.characters)}. As it starts: {sc.knows} What happens: {sc.beats} "
                f"Ends on: {sc.ends_on}")
    return (f"\"{ep.title}\"\n" + "\n".join(f"  {i + 1}. {row(sc)}" for i, sc in enumerate(ep.scenes))
            + f"\n  The cliffhanger: {ep.cliffhanger} ({ep.said_by}: \"{ep.last_line}\")\n  Summary: {ep.summary}\n"
            + "  Side scenes:\n" + "\n".join(f"    - {row(sc)}" for sc in ep.spares))


def _arc(world: World, series: Series, started: float | None = None) -> dict:
    """The arc this episode follows: the one in hand, until ARC_EPISODES aired episodes have used it."""
    st = state(world, series)
    arc = st.get("arc")
    used = len([ep for ep in _aired_episodes(world, series) if arc and ep.get("arc") == arc.get("made")])
    if arc and used < ARC_EPISODES:
        return {**arc, "step": used}
    old = ("THE LAST ARC: " + "; ".join(f"{s['name']}: {' / '.join(s['beats'])}" for s in arc["storylines"])
           if arc else "THE FIRST ARC. Start from these storylines:\n" + "\n".join(f"  - {o}" for o in series.opening))
    user = (f"THE CHARACTERS:\n{_people(series)}\n\nTHE SETS:\n{_sets(series)}\n\n{_previously(world, series)}\n\n{old}"
            + creative.for_planner(world, series.id, series=True))
    system = _ARC.format(title=series.title, bible=series.bible, n=ARC_EPISODES)

    def check(a: Arc) -> None:
        if not all(set(s.characters) <= set(series.characters) for s in a.storylines):
            raise llm.LLMError("an arc storyline named someone not in the cast")
    try:
        a = llm.complete_json(TASK, Arc, system, user)
        check(a)
        # The creative editor reads it before it stands for six episodes, and may send it back once.
        a = creative.redraft(world, series.id, "arc", a, text=_arc_text, context=user, check=check, started=started,
                             again=lambda more: llm.complete_json(TASK, Arc, system, user + more))
        made = {"made": f"{world.last_date}#{len(st['episodes'])}", **a.model_dump()}
    except llm.LLMError as e:
        log.warning("soap: no arc (%s); the opening storylines stand in", e)
        made = {"made": f"{world.last_date}#{len(st['episodes'])}", "turning_point": "",
                "storylines": [{"name": o.split(":")[0][:60], "characters": [], "beats": [o] * ARC_EPISODES}
                               for o in series.opening]}
    with world.lock:
        st["arc"] = made
    log.info("soap: %s's arc: %s", series.title, "; ".join(s["name"] for s in made["storylines"]))
    return {**made, "step": 0}


def _check(ep: Episode, series: Series) -> None:
    names = set(series.characters)
    for i, sc in enumerate(ep.scenes):
        if sc.set not in series.sets:
            raise llm.LLMError(f"scene {i + 1} is on {sc.set!r}, not one of the sets")
        if not set(sc.characters) <= names or len(set(sc.characters)) != len(sc.characters):
            raise llm.LLMError(f"scene {i + 1} names {sc.characters}, not the cast")
    if ep.said_by not in ep.scenes[-1].characters:
        raise llm.LLMError(f"the last line's {ep.said_by!r} isn't in the last scene")
    for i, sc in enumerate(ep.spares):
        if sc.set not in series.sets or not set(sc.characters) <= names:
            raise llm.LLMError(f"spare {i + 1} is somewhere or with someone not in the series")


def commission(world: World, series: Series) -> dict:
    """Plan tonight's episode (the model, or the stand-in if it fails) and record it."""
    _cast_actors(world, series)
    started = time.monotonic()                 # the editor's reading stops once the booking has taken long enough
    arc = _arc(world, series, started)
    st = state(world, series)
    last = next(iter(_aired_episodes(world, series)[-1:]), None)
    step = arc["step"]
    beats = "\n".join(f"  - {s['name']}: {s['beats'][min(step, len(s['beats']) - 1)]}" for s in arc["storylines"])
    user = (f"THE CHARACTERS:\n{_people(series)}\n\nTHE SETS:\n{_sets(series)}\n\n{_previously(world, series)}\n\n"
            + (f"THE LAST CLIFFHANGER (answer it tonight): {last['cliffhanger']} ({last['said_by']}: "
               f"\"{last['last_line']}\")\n\n" if last else "")
            + f"TONIGHT, in the arc (episode {step + 1} of {ARC_EPISODES}):\n{beats}"
            + (f"\nThe arc's turning point: {arc['turning_point']}" if arc.get("turning_point") else "")
            + creative.for_planner(world, series.id)
            + f"\n\nTonight is {date.fromisoformat(world.last_date):%A %d %B}.")
    system = _EPISODE.format(title=series.title, bible=series.bible, scenes=SCENES, spares=SPARES)
    try:
        ep = llm.complete_json(TASK, Episode, system, user)
        _check(ep, series)
        ep = creative.redraft(world, series.id, "episode", ep, text=_episode_text, context=user, started=started,
                              check=lambda e: _check(e, series),
                              again=lambda more: llm.complete_json(TASK, Episode, system, user + more))
        plan, stand_in = ep.model_dump(), False
    except llm.LLMError as e:
        log.warning("soap: no episode (%s); the stand-in takes tonight", e)
        plan, stand_in = _stand_in(series), True
    entry = {"date": world.last_date, "number": len(st["episodes"]) + 1, "arc": arc["made"], "stand_in": stand_in,
             "last_brief": "{s%d}" % SCENES, "written": {}, **plan}
    with world.lock:
        st["episodes"] = [e for e in st["episodes"] if e["date"] != world.last_date] + [entry]
        st["episodes"] = st["episodes"][-60:]
    log.info("soap: %s episode %d, %r, ends on %r%s", series.title, entry["number"], entry["title"],
             entry["cliffhanger"], " (stand-in)" if stand_in else "")
    return entry


def _stand_in(series: Series) -> dict:
    title, cliff, last_line, scenes, spares = series.stand_in
    plan, spare = ([{"set": sid, "characters": list(who), "knows": "", "beats": beats, "ends_on": ""}
                    for sid, who, beats in group] for group in (scenes, spares))
    return {"title": title, "scenes": plan, "spares": spare, "cliffhanger": cliff, "last_line": last_line,
            "said_by": plan[-1]["characters"][0], "summary": " ".join(s["beats"] for s in plan)[:600]}


def digest(world: World, series: Series, day: str) -> str:
    """The episode booked for `day` and the arc it follows, as the creative editor reads them after it has aired;
    "" for none, or the stand-in (not the planner's work)."""
    st = state(world, series)
    ep = next((e for e in st["episodes"] if e["date"] == day), None)
    if not ep or ep.get("stand_in"):
        return ""
    try:
        out = f"Episode {ep['number']}, " + _episode_text(Episode.model_validate({k: ep[k] for k in Episode.model_fields}))
        arc = st.get("arc") or {}
        if arc.get("made") == ep.get("arc") and arc.get("turning_point"):
            out += "\nTHE ARC it follows (a beat an episode):\n" + _arc_text(
                Arc.model_validate({k: arc[k] for k in Arc.model_fields}))
        return out
    except (KeyError, ValueError):             # saved in an older shape
        return f"Episode {ep.get('number')}, \"{ep.get('title')}\": {ep.get('summary', '')}"


def _cast_actors(world: World, series: Series) -> None:
    """The actors are residents (the characters never are), with their own voices."""
    for p in series.cast:
        person = world.ensure_person(p.actor, f"actor, plays {p.character} in {series.title} on Channel 8", "resident",
                                     gender=p.gender, age=p.age, accent="british")
        if person is not None and person.voice != p.voice:
            person.voice = p.voice


def booked(world: World, series: Series) -> dict:
    return tonight(world, series) or commission(world, series)


# ------------------------------------------------------------------ the scenes

def _which(brief: str) -> tuple[str, int] | None:
    m = TOKEN.search(brief or "")
    return (m.group(1), int(m.group(2)) - 1) if m else None


def _scene(ep: dict, series: Series, brief: str) -> tuple[dict, str, bool] | None:
    """The plan for this item: (its scene, its key in "written", whether it is the episode's last). A spare the
    plan has none left for is a quiet moment on one of the series' sets, so the loop never airs one twice."""
    w = _which(brief)
    if w is None:
        return None
    kind, n = w
    if kind == "s":
        return (ep["scenes"][n], str(n), n == len(ep["scenes"]) - 1) if n < len(ep["scenes"]) else None
    spares = ep.get("spares") or []
    if n < len(spares):
        return spares[n], f"x{n}", False
    # In turn, so the plan running out doesn't put the same two at the same bar three times (the first model run).
    sid, who, about = series.quiet[(n - len(spares)) % len(series.quiet)]
    return ({"set": sid, "characters": list(who), "knows": "", "ends_on": "", "beats": f"A quiet moment: {about}; "
             "nothing in the story changes or is given away"}, f"x{n}", False)


def brief_for(world: World, series: Series, brief: str) -> str:
    ep = booked(world, series)
    found = _scene(ep, series, brief)
    if found is None:
        return brief
    sc, key, last = found
    name, blurb, _ = series.sets[sc["set"]]
    head = (f"A SHORT SIDE SCENE (it changes nothing in the story and gives nothing away), at {name} ({blurb})"
            if key.startswith("x") else f"SCENE {int(key) + 1} of {len(ep['scenes'])}, at {name} ({blurb})")
    out = (f"{head}. In it: {', '.join(sc['characters'])}, in that order across the set. "
           + (f"As it starts: {sc['knows']} " if sc.get("knows") else "")
           + f"What happens: {sc['beats']}" + (f" It ends on: {sc['ends_on']}" if sc.get("ends_on") else ""))
    if last:
        out += (f" This is the LAST scene of the episode: it ends on the cliffhanger, {ep['said_by']} saying, "
                f"word for word, \"{ep['last_line']}\" as the very last line, with nothing after it")
    return out


def for_prompt(world: World, series: Series) -> str:
    ep = booked(world, series)
    plan = "\n".join(f"  {i + 1}. {series.sets[sc['set']][0]}: {', '.join(sc['characters'])}: {sc['beats']}"
                     for i, sc in enumerate(ep["scenes"]))
    done = "\n".join(f"  {'Side scene' if k.startswith('x') else 'Scene ' + str(int(k) + 1)}: {v}"
                     for k, v in ep["written"].items())
    return (f"THE SERIES: {series.bible}\n\nTHE CHARACTERS:\n{_people(series)}\n\n{_previously(world, series)}\n\n"
            f"TONIGHT'S EPISODE, \"{ep['title']}\" (episode {ep['number']}):\n{plan}\nIt ends on the cliffhanger: "
            f"{ep['cliffhanger']}"
            + (f"\n\nSCENES ALREADY WRITTEN TONIGHT (keep to what they say; don't repeat them):\n{done}" if done else ""))


def after(seg, world: World, series: Series) -> None:
    """The scene's set and its people in their places, and what it says for the scenes still to be written."""
    ep = tonight(world, series)
    found = _scene(ep, series, seg.brief) if ep else None
    if found is None:
        return
    sc, key, _ = found
    seg.work["set"] = sc["set"]
    seg.work["seats"] = list(sc["characters"])
    said = " / ".join(f"{l.guest_name}: {l.text}" for l in seg.lines if l.guest_name)
    with world.lock:
        ep["written"][key] = said[:WRITTEN_CHARS]


def check(seg, script, world: World, series: Series) -> None:
    """Every line is one of the scene's characters, and at least two of them speak."""
    ep = tonight(world, series)
    found = _scene(ep, series, seg.brief) if ep else None
    if found is None:
        return
    allowed = set(found[0]["characters"])
    names = [(l.guest_name or "").strip() for l in script.lines]
    if any(name not in allowed for name in names):
        raise llm.LLMError(f"a line in {seg.brief} is spoken by someone not in it: {set(names) - allowed}")
    if len(set(names)) < 2:
        raise llm.LLMError(f"{seg.brief} has only one character speaking")


_STAND_IN_LINES = ("I didn't think you'd come.", "I nearly didn't.", "Well, you're here now.",
                   "Don't start. Not tonight.", "Somebody has to say it.", "Then say it, and have done.")


def template(seg_type, world, rng: random.Random, part: str, work: dict, brief: str, series: Series):
    """A scene with no model: tonight's characters, a few lines, and the last scene's cliffhanger line as planned."""
    from newsroom.models import PanelLine, PanelScript

    if seg_type is not T.interview:
        return None
    ep = booked(world, series)
    sc, key, last = _scene(ep, series, brief) or (ep["scenes"][0], "0", False)
    who = sc["characters"]
    lines = [PanelLine(speaker="guest", guest_name=who[i % len(who)], text=t) for i, t in enumerate(_STAND_IN_LINES)]
    if last:
        lines.append(PanelLine(speaker="guest", guest_name=ep["said_by"], text=ep["last_line"]))
    return PanelScript(lines=lines, headline=f"{series.title}: {key}", lower_third=series.title, guest_name=who[0])


# ------------------------------------------------------------------ the show

def show(series: Series) -> Show:
    """Titles, the scenes, adverts for any spare minutes, and the cliffhanger scene last, at the end of the slot."""
    scenes = tuple(I(T.interview, brief="{s%d}" % (k + 1), target_s=170.0) for k in range(SCENES - 1))
    # The spare minutes: three side scenes, then a break, as a lap; each lap's spares are new ones (x1-x3, x4-x6,
    # then quiet moments), so the order never wraps onto a planned scene or airs a spare twice.
    spares = tuple(I(T.interview, brief=tuple("{x%d}" % (k + 1 + 3 * lap) for lap in range(4)), target_s=100.0)
                   for k in range(3))
    return Show(
        series.id, series.title.upper(), series.title.upper(), series.colour,
        pattern=(T.bumper, *scenes, *spares, T.ad_break),
        loop_from=SCENES,                 # the spares and the break
        closing=(I(T.interview, brief="{s%d}" % SCENES, target_s=170.0),),
        target_s={T.bumper: 10.0, T.interview: 170.0, T.ad_break: 60.0},
        cast=("guest",), lead="guest", cast_by_type={T.interview: ("guest",)},
        station=f"{series.title}, the soap on Channel 8, Port Wexley's second channel",
        tone=series.tone, light=False, repeats_overnight=False,
    )


_SCENE = """
This is a SCENE of {title}, a British soap, as THIS ITEM gives it: a drama, not a programme about one. Every line is
a character speaking in the scene, speaker "guest" with guest_name their exact name; only the characters THIS ITEM
names. No presenter, no narrator, no stage directions, no captions. Real dialogue: people interrupt, dodge, say less
than they mean and give themselves away; soap-sized feelings in everyday words; British, West Country where it
suits. Keep to what the scenes already written tonight say, and to the plan: start where THIS ITEM starts, and end
exactly on what it ends on. About 12 to 20 lines. These are characters played by actors: none of them is a resident
of the town, and the town's news is not their business unless THIS ITEM says so. The street has its own places (The
Mermaid, The Loft, the quay, the net loft): never name the town's real pubs, shops, clubs or people from the
briefing. A side scene keeps to its own beats, with no topical joke of its own: the side scenes are written at the
same time, and on the first run three of them made the same one. thread_id is null.
headline = what happens in the scene, under 10 words. lower_third = "{title}".
"""


def register(series: Series):
    """Put the series on air through the engine's registries. Returns an undo."""
    from newsroom import assets, continuity, locations, player, scenes, world as world_mod, workers, writers
    from newsroom.writers import _COMMON_RULES

    sh = show(series)
    saved_marks, saved_ids = dict(locations.MARKS), dict(locations.BY_ID)
    schedule.SHOWS[sh.id] = sh
    for sid, (name, blurb, marks) in series.sets.items():
        locations.BY_ID[sid] = locations.Location(sid, name, blurb, "studio", (40, 50, 80), (80, 60, 50))
        locations.MARKS[sid] = dict(marks)
    scenes.PINNED_LOOKS.update({p.character: p.look for p in series.cast})
    world_mod.PINNED_VOICES.update({p.character: (p.voice, 1.0, "b") for p in series.cast})
    player.SEATS[sh.id] = 3
    player.BARE_SHOWS.add(sh.id)
    assets.IDENTS[sh.id] = (assets.CONFIG.paths.assets / f"bumper_{sh.id}.wav", series.ident or series.title)
    assets.IDENT_MUSIC[sh.id] = "inquiry"                         # the cello in the minor, until it has its own theme
    assets.IDENT_VOICES[sh.id] = continuity.VOICE
    # The engine calls these with its own arguments, by position: the series goes in by closure.
    workers.IDLE_JOBS.append((lambda world, now=None: should_commission(world, series, now),
                              lambda world: commission(world, series)))
    writers.SHOW_SYSTEMS[sh.id] = {T.interview: _COMMON_RULES + _SCENE.format(title=series.title)}
    writers._PLACE[(sh.id, T.interview)] = {"": f"PLACE IN THE SHOW: one scene of tonight's {series.title}, cut "
                                                 "straight from the last: no greeting, no goodbye to camera."}
    writers.BRIEF_HOOKS[sh.id] = lambda world, brief: brief_for(world, series, brief)
    writers.PROMPT_HOOKS[sh.id] = lambda world: for_prompt(world, series)
    writers.TEMPLATE_HOOKS[sh.id] = lambda seg_type, world, rng, part, work, brief: template(
        seg_type, world, rng, part, work, brief, series)
    writers.CHECK_HOOKS[sh.id] = lambda seg, script, world: check(seg, script, world, series)
    writers.AFTER_HOOKS[sh.id] = lambda seg, world: after(seg, world, series)
    player.AIRED_HOOKS[sh.id] = lambda seg, world: stamp(seg, world, series)
    writers.LINE_CAPS[sh.id] = 24
    for reg in (writers.BOOKED_SHOWS, writers.DEBATE_SHOWS, writers.UNFILED_SHOWS, writers.FICTION_SHOWS):
        reg.add(sh.id)
    undo_creative = creative.register(
        sh.id, series.title, kind="fiction", vetted=True, airs_at=series.airs_at,
        brief=(f"{series.bible} Twenty minutes a Channel 8 night: six planned scenes written live from the plan, side "
               "scenes for the spare minutes, and a cliffhanger the town talks about the next day."),
        decides=("each scene's set and characters, who knows what as it starts, what happens and what it ends on; the "
                 "cliffhanger question and its closing line; the side scenes"),
        series_decides=f"the arc: two or three storylines, a beat for each of {ARC_EPISODES} episodes, and the turning point",
        digest=lambda world, day: digest(world, series, day),
        aired=lambda world: [ep["date"] for ep in state(world, series)["episodes"] if aired(world, series, ep)],
        books=lambda world: should_commission(world, series))

    def undo() -> None:
        undo_creative()
        schedule.SHOWS.pop(sh.id, None)
        locations.MARKS.clear(), locations.MARKS.update(saved_marks)
        locations.BY_ID.clear(), locations.BY_ID.update(saved_ids)
        for p in series.cast:
            scenes.PINNED_LOOKS.pop(p.character, None)
            world_mod.PINNED_VOICES.pop(p.character, None)
        for reg in (player.SEATS, assets.IDENTS, assets.IDENT_MUSIC, assets.IDENT_VOICES, writers.SHOW_SYSTEMS,
                    writers.BRIEF_HOOKS, writers.PROMPT_HOOKS, writers.TEMPLATE_HOOKS, writers.CHECK_HOOKS,
                    writers.AFTER_HOOKS, writers.LINE_CAPS, player.AIRED_HOOKS):
            reg.pop(sh.id, None)
        writers._PLACE.pop((sh.id, T.interview), None)
        for reg in (player.BARE_SHOWS, writers.BOOKED_SHOWS, writers.DEBATE_SHOWS, writers.UNFILED_SHOWS,
                    writers.FICTION_SHOWS):
            reg.discard(sh.id)
    return undo
