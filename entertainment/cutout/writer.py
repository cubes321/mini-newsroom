"""An episode written for the puppets: the user's "re-plan for puppets" (2026-11-08), after the cut-out engine
was chosen. The H3 writer described pictures for a model to draw; this one stages each shot on the puppets'
stage with what the kits can actually do, and the code places it.

The writer never does geometry. It puts people on named marks (far_left ... far_right, off_left/off_right to
start out of shot, raised for a sill or a rail), says which way they face, which pose of theirs, what they do
and when (against the line: "line", "line_end+0.3"), and where the camera is; stage() turns that into a
Layout in stage units. The brief lists each character's real poses, faces and moves from their kits, so the
writer can't ask for a pose nobody drew; a slip (a mark, a character or a pose it made up) is mended and
logged, never fatal. A prop is a kit too, drawn after the script from its one fixed look; a rope is a line
Blender draws, not a prop.
"""
from __future__ import annotations

import difflib
import json
import logging
import re
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from entertainment.cutout.kit import Kit
from entertainment.cutout.layout import Actor, Beat as LBeat, Camera, Framing, Layout, Rope

log = logging.getLogger(__name__)

MARKS = {"off_left": -24.0, "far_left": -11.0, "left": -6.0, "centre": 0.0, "right": 6.0, "far_right": 11.0,
         "off_right": 24.0}
HEIGHTS = {"ground": 0.0, "raised": 3.0, "air": 7.0}


class Said(BaseModel):
    who: str
    words: str = Field(max_length=120)
    offscreen: bool = Field(False, description="heard, not seen: a shout or a yelp from out of shot")


class PSfx(BaseModel):
    what: str = Field(max_length=80, description="the sound in a few words: 'a metal bucket clanging off a wall'")
    at: str = Field("0.5", description="seconds, or against the lines: line_end+0.2, line2, end-0.5")


class StageActor(BaseModel):
    who: str = Field(description="a key of THE CAST or of the shot's PROPS")
    mark: str = Field("centre", description="far_left, left, centre, right, far_right (off_left / off_right: "
                                            "out of shot, to come in by walk or fly)")
    height: Literal["ground", "raised", "air"] = "ground"
    facing: Literal["left", "right"] = "left"
    pose: str = Field("normal", description="one of the character's POSES")
    enter: Literal["none", "left", "right"] = "none"
    holds: str | None = Field(None, description="a prop key this character carries (beak, mouth or hand)")


class StageBeat(BaseModel):
    who: str
    do: Literal["pose", "face", "lean", "hop", "turn", "exit", "walk", "fly", "spin", "take"]
    value: str = Field("", description="pose: a POSE; face: a FACE; lean: degrees forward, 3 to 8; spin: "
                                       "degrees (180 hangs it upside down, 360 a full turn); exit: left or right; "
                                       "take: the prop key picked up (carried from then on)")
    to: str | None = Field(None, description="walk or fly: the mark to go to")
    height: Literal["ground", "raised", "air"] = "ground"
    at: str = Field("0", description="seconds, or line / line_end / end with +/- seconds")
    until: str | None = None


class StageCamera(BaseModel):
    size: Literal["wide", "medium", "close"] = "wide"
    on: str | None = Field(None, description="medium/close: who; close on a part: who.head or who.feet")
    move: Literal["hold", "push_in", "pull_out", "tilt_up", "tilt_down"] = "hold"


class RopeLine(BaseModel):
    attach: str = Field(description="who.part the rope is tied to: who.ankle, or a prop key")
    to: str = Field("off_left", description="the mark its other end runs to along the ground")


class Stage(BaseModel):
    actors: list[StageActor] = Field(max_length=5)
    beats: list[StageBeat] = Field(default_factory=list, max_length=8)
    rope: RopeLine | None = None
    camera: StageCamera = StageCamera()


class PProp(BaseModel):
    key: str = Field(max_length=24, description="short lowercase key: bucket, crate, cone")
    looks: str = Field(max_length=160, description="one fixed look: colour, material, size in plain words")


class PShot(BaseModel):
    place: str = Field(max_length=120, description="one of THE PLACES, copied exactly")
    seen: list[str] = Field(default_factory=list, max_length=4, description="keys of who and what is seen")
    action: str = Field(max_length=200, description="what we see happen, in one sentence")
    lines: list[Said] = Field(default_factory=list, max_length=3)
    sfx: list[PSfx] = Field(default_factory=list, max_length=3)
    seconds: float = Field(4.0, ge=2.5, le=10)
    sounds: str = Field(max_length=120, description="the place's own sound under it")


class PScript(BaseModel):
    title: str = Field(max_length=60)
    logline: str = Field(max_length=200)
    props: list[PProp] = Field(default_factory=list, max_length=6)
    shots: list[PShot] = Field(min_length=8, max_length=60)


class PStages(BaseModel):
    stages: list[Stage]


# Two calls, not one (2026-11-09): the talking script and every shot's stage in one reply ran past Sonnet's
# 16,000 output tokens twice, its thinking included. The writer writes the talk; the stager, eight shots a
# call, puts it on the puppets' stage.
SYSTEM = """\
You write one episode of {title}, a PAPER CUT-OUT cartoon on a small-town TV station's second channel, set in
the FICTIONAL fishing town of Port Wexley. {premise} Tone: {tone}.
It is animated with paper puppets on a flat stage, like classic British cut-out cartoons: each character is a
few drawings (poses and faces) that slide, hop, turn, tilt and swap.
THE COMEDY IS IN THE TALK. Most of the humour is the interplay between the characters: banter, bluster and
deadpan replies, a running joke, a scheme explained and picked apart, one line topping another. Write a
talking cartoon: most shots have lines, often two or three as a quick exchange in a two-shot.
KEEP THE ACTION SIMPLE ON SCREEN. Puppets slide, hop, walk, fly and turn; they don't do fiddly things. The big
physical business happens OFF SCREEN: we watch a character watching it, wincing, and hear it: a sound effect
and a yelp or a shout from out of shot ("Ow!", "Oof!", "Not the bucket!"). A crash we only hear is funnier
than one we see done badly. Original jokes only; no famous characters, catchphrases or brands.
Write about {n} SHOTS, each 2.5 to 10 seconds, with a beginning, a turn and a payoff.
- PLACE is one of THE PLACES copied exactly. Each place is one painted backdrop.
- SEEN: who and what is in shot (cast keys and prop keys).
- ACTION: what we see, simply (who comes in, who turns, who hops, who stares); never fiddly handiwork.
- LINES: up to three short lines per shot (about ten words each), in order, each by a character who speaks.
  A line's speaker is seen, unless it is OFFSCREEN: heard, not seen (a shout or a yelp from what is
  happening out of shot). Others may be seen too: only the speaker's mouth moves.
- SFX: up to three sound effects per shot, each a few words ("a metal bucket clanging off a wall", "a heavy
  splash into mud", "a rope going twang") and when (seconds, or against the lines: "line_end+0.2", "line2").
  Off-screen business is mostly SFX plus an OFFSCREEN line, played on someone's face.
- PROPS: as few as the story can manage (at most three), each once with one fixed look (colour, material,
  size in plain words, never "the size of" another object); a prop's key is how SEEN names it. Props are
  small beside the cast and drawn as one object: "a few chips", not "a heap of chips". A contraption is
  talked about and heard, not built on screen.
- No written words anywhere.
Return ONLY JSON.
"""

STAGER = """\
You stage shots of a PAPER CUT-OUT cartoon on the puppets' flat stage. For each numbered shot, in order,
return its STAGE (as many stages as shots):
- ACTORS: everyone and everything SEEN, each on a MARK: far_left, left, centre, right, far_right (off_left /
  off_right to start out of shot and come in), at a HEIGHT (ground; raised: a sill, a rail, a wall top; air),
  FACING left or right, in one of their POSES. ENTER left/right walks (or waddles) them in at the start.
  HOLDS: a prop they carry all shot (in beak, mouth or hand): whenever someone carries something, say so with
  HOLDS or a TAKE beat, or it stays where it was put. Two who talk face each other.
  A MARK can also be one of the place's SPOTS, where the shot lists them (the chip shop's sill): it stands
  exactly there on the backdrop. Put a prop that rests on something (a cone on a sill) on its spot.
- BEATS, timed in seconds or against the lines ("line", "line2", "line_end+0.3"): pose X until T, face X
  until T, lean (degrees forward), hop, turn (face the other way), walk to a mark, fly to a mark and height
  (only those who CAN FLY), take a prop (carried from then on), spin (degrees: 180 hangs it upside down by its
  feet, and the stage lifts it high enough to hang; 360 a full flip), exit left/right. A prop can fly too.
  Keep it simple: a reaction (a turn, a hop, a lean, a look) sells off-screen business.
- ROPE: a rope tied to who.part (or to a prop) running along the ground to a mark, if the shot shows one.
- CAMERA: wide (the whole stage), medium on someone, or close on someone or on who.head / who.feet; hold,
  push_in, pull_out, tilt_up (from feet to head) or tilt_down. A two-shot exchange is wide or medium.
- There is no swinging and no rope physics: a swing is a fly; a dangle is a spin of 180.
- Use ONLY the POSES and FACES each character has (listed below); "normal" always exists. Faces for talking
  and blinking are automatic: never write them.
Return ONLY JSON: {"stages": [...]}.
"""


def brief(series, kits: dict[str, Kit], places: list[str]) -> str:
    """The cast with what their puppets can do, and the places."""
    rows = []
    for c in series.cast:
        k = kits.get(c.key)
        if k is None:
            continue
        poses = [p for p in k.poses if p not in k.walk and p != k.fly]
        faces = [f for f in k.faces if f not in ("talk", "squawk", "blink")]
        can = (["walks"] if k.walk else ["waddles"]) + (["CAN FLY"] if k.fly else [])
        rows.append(f"  - {c.key}: {c.name}, {c.looks}; " + (f"speaks: {c.voice}" if c.voice else "NEVER SPEAKS")
                    + f". POSES: {', '.join(poses)}. FACES: {', '.join(faces) or 'none'}. {', '.join(can)}.")
    return "THE CAST (their puppets):\n" + "\n".join(rows) + "\n\nTHE PLACES:\n" + "\n".join(f"  - {p}" for p in places)


def _mark(m: str | None) -> float:
    m = (m or "centre").strip().lower().replace(" ", "_").replace("center", "centre")
    if m in MARKS:
        return MARKS[m]
    log.warning("cutout writer: unknown mark %r, taken as centre", m)
    return 0.0


def stage(st: Stage, place: int, kits: dict[str, Kit], props: set[str], spots: set[str] = frozenset()) -> Layout:
    """A writer's stage as a Layout in stage units. Unknown characters and props are dropped (logged). A mark
    that names one of the place's spots (its sill) puts them exactly there on the backdrop."""
    known = set(kits)
    actors, held = [], {}
    for a in st.actors:
        who = a.who.strip().lower()
        if who not in known:                              # a prop not drawn yet is staged once it is (props)
            (log.debug if who in props else log.warning)("cutout writer: %r has no puppet; left out", a.who)
            continue
        if any(x.who == who for x in actors):             # listed twice: one puppet, the first place it was put
            continue
        k = kits[who]
        pose = a.pose if a.pose in k.poses else "normal"
        spot = a.mark.strip().lower() if a.mark.strip().lower() in spots else None
        actors.append(Actor(who=who, x=0.0 if spot else _mark(a.mark), y=0.0 if spot else HEIGHTS[a.height],
                            facing=a.facing, pose=pose, enter=a.enter, spot=spot))
        if a.holds and a.holds.strip().lower() in known:
            held[a.holds.strip().lower()] = who
    for prop, holder in held.items():
        actors = [x for x in actors if x.who != prop]
        actors.append(Actor(who=prop, on=f"{holder}.hold"))
    names = {x.who for x in actors}
    for b in st.beats:                                    # a prop taken mid-shot sits where it is until then
        who, prop = b.who.strip().lower(), b.value.strip().lower()
        if b.do == "take" and who in names and prop in names and prop != who:
            a = next(x for x in actors if x.who == prop)
            actors = [x for x in actors if x.who != prop] + [a.model_copy(update={"on": f"{who}.hold", "on_at": b.at or "0"})]
    for a in actors:
        # Hung upside down: a spin turns a card round its feet, so from the writer's "air" Gully's body hung
        # below the ground (the Chip Lift, 2026-11-08). He hangs from a height he fits under, and whatever is
        # on his mark up there (the hook) goes up with him.
        if any(b.who.strip().lower() == a.who and b.do == "spin" and abs(float(re.sub(r"[^0-9.\-]", "", b.value) or 0)) >= 150
               for b in st.beats):
            hang = round(kits[a.who].height * 1.1 + 1.0, 2)
            for x in actors:
                if x is a or (x.who in props and x.x == a.x and x.y > 0 and not x.on):
                    x.y = hang
    hung = {a.who: a.y for a in actors if any(b.who.strip().lower() == a.who and b.do == "spin"
            and abs(float(re.sub(r"[^0-9.\-]", "", b.value) or 0)) >= 150 for b in st.beats)}
    beats = []
    for b in st.beats:
        who = b.who.strip().lower()
        if who not in names or b.do == "take":
            continue
        value = b.value
        if b.do in ("walk", "fly"):
            x = _mark(b.to)
            # A hanging puppet's move is a swing: along at its height (a fly "to the ground" dragged the
            # upside-down Gully's head under it, the talking Chip Lift's shot 19).
            y = hung.get(who, HEIGHTS[b.height])
            value = f"{x}" if b.do == "walk" else f"{x},{y}"
        elif b.do == "spin":
            value = re.sub(r"[^0-9.\-]", "", value) or "360"
        elif b.do == "lean":
            value = re.sub(r"[^0-9.\-]", "", value) or "4"
        beats.append(LBeat(who=who, do=b.do, value=value, at=b.at or "0", until=b.until))
    ropes = []
    if st.rope:
        who, _, part = st.rope.attach.strip().lower().partition(".")
        if who in names:
            x0 = next(a.x for a in actors if a.who == who)
            x1 = _mark(st.rope.to)
            pts = [(x0 + (x1 - x0) * u, 0.1 + 0.12 * ((i % 2) - 0.5)) for i, u in enumerate((0.1, 0.35, 0.6, 0.85, 1.0))]
            ropes.append(Rope(attach=f"{who}.{part or 'ankle'}", path=pts))
    c = st.camera
    on = (c.on or "").strip().lower() or None
    if on and on.partition(".")[0] not in names:
        on = None
    size = c.size if on or c.size == "wide" else "wide"
    start = Framing(size=size, on=on)
    end = None
    if c.move == "push_in":
        start, end = Framing(size=size, on=on, zoom=0.85), Framing(size=size, on=on, zoom=1.0)
    elif c.move == "pull_out":
        start, end = Framing(size=size, on=on, zoom=1.0), Framing(size=size, on=on, zoom=0.85)
    elif c.move in ("tilt_up", "tilt_down") and on:
        who = on.partition(".")[0]
        lo, hi = Framing(size="close", on=f"{who}.feet"), Framing(size="close", on=f"{who}.head", zoom=0.84)
        start, end = (lo, hi) if c.move == "tilt_up" else (hi, lo)
    return Layout(place=place, actors=actors, beats=beats, ropes=ropes,
                  camera=Camera(start=start, end=end, move_at="0.2" if end else "0", move_until="end-0.3" if end else "end"))


BATCH = 8                                      # shots staged per call
ROOM = 32000                                   # output tokens: Sonnet thinks hard about a talking cartoon


def staged(series, kits: dict[str, Kit], script: PScript) -> list[Stage]:
    """Every shot's stage, eight shots a call. A batch that comes back short is filled with the plain stage:
    who is seen, standing in a row, a wide shot."""
    from newsroom import llm
    from entertainment import cartoons

    from entertainment.cutout import engine

    props = "\n".join(f"  - {p.key}: {p.looks}" for p in script.props) or "  (none)"
    places_spots = {pl: list(engine.spots_of(cartoons.ROOT / series.id, k + 1)) for k, pl in enumerate(series.places)}
    out: list[Stage] = []
    for b0 in range(0, len(script.shots), BATCH):
        batch = script.shots[b0:b0 + BATCH]
        rows = []
        for k, s in enumerate(batch, start=1):
            said = " / ".join(f"{l.who}{' (off screen)' if l.offscreen else ''}: \"{l.words}\"" for l in s.lines)
            here = places_spots.get(s.place, [])
            rows.append(f"{k}. at {s.place}" + (f" (its SPOTS: {', '.join(here)})" if here else "")
                        + f"; seen: {', '.join(s.seen) or 'nobody'}; {s.action}"
                        + (f" Lines: {said}" if said else ""))
        user = (brief(series, kits, list(series.places)) + f"\n\nTHE PROPS:\n{props}\n\nTHE SHOTS:\n"
                + "\n".join(rows))
        try:
            got = llm.complete_json(cartoons.TASK, PStages, STAGER, user, max_tokens=ROOM, timeout_s=600).stages
        except llm.LLMError as e:
            log.warning("cutout writer: staging shots %d-%d failed (%s); plain stages", b0 + 1, b0 + len(batch), e)
            got = []
        for k, s in enumerate(batch):
            if k < len(got):
                out.append(got[k])
            else:
                marks = ["left", "right", "centre", "far_left"]
                out.append(Stage(actors=[StageActor(who=w, mark=marks[j % 4]) for j, w in enumerate(s.seen)]))
    return out


def write(series, kits: dict[str, Kit], n: int = 40, idea: str = "", remake: bool = False):
    """The episode (cartoons.Episode, one shot a scene), each shot's stage, and the props to draw: the talk
    written first, then staged. A remake retells an episode made before (the idea says which), so the list
    of episodes not to repeat is left out."""
    from newsroom import llm
    from entertainment import cartoons

    user = brief(series, kits, list(series.places)) + (f"\n\nTHIS EPISODE'S IDEA: {idea}" if idea else "") \
        + ("" if remake else cartoons._done(series))
    script = llm.complete_json(cartoons.TASK, PScript, SYSTEM.format(title=series.title, premise=series.premise,
                                                                     tone=series.tone, n=n), user,
                               max_tokens=ROOM, timeout_s=600)
    stages = staged(series, kits, script)
    talkers = {c.key for c in series.cast if c.voice}
    props = {p.key.strip().lower(): p.looks for p in script.props}
    scenes, layouts = [], []
    for k, (s, st) in enumerate(zip(script.shots, stages), start=1):
        for l in s.lines:
            l.who = l.who.strip().lower()
        s.lines = [l for l in s.lines if l.who in talkers]
        if s.place not in series.places:
            s.place = (difflib.get_close_matches(s.place, series.places, n=1, cutoff=0.0) or [s.place])[0]
        on_stage = {a.who.strip().lower() for a in st.actors}
        for l in s.lines:
            if not l.offscreen and l.who not in on_stage:
                st.actors.append(StageActor(who=l.who))               # a speaker seen is on stage
                on_stage.add(l.who)
                log.warning("cutout writer: shot %d's speaker %s was not on stage; put at centre", k, l.who)
            elif l.offscreen and l.who in on_stage:
                l.offscreen = False                                    # on stage after all: his mouth moves
        cast_here = [a.who.strip().lower() for a in st.actors if a.who.strip().lower() in {c.key for c in series.cast}]
        props_here = [a.who.strip().lower() for a in st.actors if a.who.strip().lower() in props]
        scenes.append(cartoons.Scene(
            place=s.place, on_screen=cast_here[:3], summary=s.action[:200],
            shots=[cartoons.Shot(at=0.0, action=f"{st.camera.size} shot: {s.action}"[:300])],
            lines=[cartoons.Said(who=l.who, words=l.words, offscreen=l.offscreen) for l in s.lines],
            sounds=s.sounds, seconds=min(cartoons.SCENE_S, s.seconds),
            props=[f"{p}: {props[p]}" for p in props_here],
            sfx=[cartoons.Sfx(what=e.what, at=e.at) for e in s.sfx]))
        layouts.append(st)
    ep = cartoons.Episode(title=script.title, logline=script.logline, scenes=scenes)
    return ep, layouts, props


def place_number(series, place: str) -> int:
    return list(series.places).index(place) + 1 if place in series.places else 1


def save(folder: Path, stages: list[Stage], props: dict[str, str]):
    """Each shot's stage as the writer wrote it (sceneNN.stage.json) and the episode's props (props.json)."""
    import json

    for i, st in enumerate(stages, start=1):
        (folder / f"scene{i:02d}.stage.json").write_text(st.model_dump_json(indent=1), encoding="utf-8")
    (folder / "props.json").write_text(json.dumps(props, indent=1), encoding="utf-8")


def relayout(folder: Path) -> int:
    """sceneNN.layout.json from every sceneNN.stage.json, with the kits as they are now (a prop drawn since is
    staged; one still missing is left out, logged). Returns how many."""
    from entertainment import cartoons
    from entertainment.cutout import engine, kit as kitmod

    series = cartoons.SERIES[folder.parent.name]
    ep = cartoons.Episode.model_validate_json((folder / "episode.json").read_text(encoding="utf-8"))
    kits = kitmod.kits(folder.parent)
    props = set(json.loads((folder / "props.json").read_text(encoding="utf-8"))) if (folder / "props.json").exists() else set()
    done = 0
    for i, scene in enumerate(ep.scenes, start=1):
        src = folder / f"scene{i:02d}.stage.json"
        if not src.exists():
            continue
        n = place_number(series, scene.place)
        lay = stage(Stage.model_validate_json(src.read_text(encoding="utf-8")), n, kits, props,
                    set(engine.spots_of(folder.parent, n)))
        (folder / f"scene{i:02d}.layout.json").write_text(lay.model_dump_json(indent=1), encoding="utf-8")
        done += 1
    return done
