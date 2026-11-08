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
    action: str = Field(max_length=200, description="what happens, in one sentence")
    line: Said | None = None
    seconds: float = Field(4.0, ge=2.5, le=8)
    sounds: str = Field(max_length=120)
    stage: Stage


class PScript(BaseModel):
    title: str = Field(max_length=60)
    logline: str = Field(max_length=200)
    props: list[PProp] = Field(default_factory=list, max_length=6)
    shots: list[PShot] = Field(min_length=8, max_length=60)


SYSTEM = """\
You write one episode of {title}, a PAPER CUT-OUT cartoon on a small-town TV station's second channel, set in
the FICTIONAL fishing town of Port Wexley. {premise} Tone: {tone}.
It is animated with paper puppets on a flat stage, like classic British cut-out cartoons: each character is a
few drawings (poses and faces) that slide, hop, turn, tilt and swap. Write for that: big clear poses, things
sliding in and out of shot, hops, spins, falls, and a deadpan face at the end. Comedy from timing, not from
detailed motion. Original jokes only; no famous characters, catchphrases or brands.
Write about {n} SHOTS, each 2.5 to 8 seconds, with a beginning, a turn and a payoff.
- PLACE is one of THE PLACES copied exactly. Each place is one painted backdrop.
- LINE: at most one short line per shot (about ten words), by a character who speaks. Others may be in the
  shot (a two-shot is fine: only the speaker's mouth moves).
- STAGE puts the shot on the puppet stage:
  - ACTORS: who is in shot (characters and props), each on a MARK: far_left, left, centre, right, far_right
    (off_left / off_right to start out of shot and come in), at a HEIGHT (ground; raised: a sill, a rail, a
    wall top; air), FACING left or right, in one of their POSES. ENTER left/right walks (or waddles) them in at
    the start. HOLDS: a prop they carry all shot (in beak, mouth or hand): whenever the story has someone
    carrying something, say so with HOLDS or TAKE, or it stays where it was put.
  - BEATS, timed in seconds or against the line ("line", "line_end+0.3"): pose X until T, face X until T,
    lean (degrees forward), hop, turn (face the other way), walk to a mark, fly to a mark and height (only
    those who CAN FLY), take a prop (carried from then on: a snatch is a fly to the prop's mark, then take),
    spin (degrees: 180 hangs it upside down by its feet, and the stage lifts it high enough to hang; 360 a
    full flip), exit left/right. A prop can fly too: that is how things fall, are flung or shoot up.
  - ROPE: a rope tied to who.part (or to a prop) running along the ground to a mark.
  - CAMERA: wide (the whole stage), medium on someone, or close on someone or on who.head / who.feet; it can
    hold, push_in, pull_out, tilt_up (from feet to head) or tilt_down.
  - There is no swinging and no rope physics: a swing is a fly; a dangle is a spin of 180.
- Use ONLY the POSES and FACES each character has (listed below); "normal" always exists. Faces for talking
  and blinking are automatic: never write them.
- PROPS: every object the story needs, once, with one fixed look (colour, material, size in plain words, never
  "the size of" another object); a prop's key is how the stage names it. At most six. Props are small beside
  the cast and drawn as one object: "a few chips", not "a heap of chips".
- No written words anywhere.
Return ONLY JSON.
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


def stage(st: Stage, place: int, kits: dict[str, Kit], props: set[str]) -> Layout:
    """A writer's stage as a Layout in stage units. Unknown characters and props are dropped (logged)."""
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
        actors.append(Actor(who=who, x=_mark(a.mark), y=HEIGHTS[a.height], facing=a.facing, pose=pose,
                            enter=a.enter, depth=0 if who not in props else 0))
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
    beats = []
    for b in st.beats:
        who = b.who.strip().lower()
        if who not in names or b.do == "take":
            continue
        value = b.value
        if b.do in ("walk", "fly"):
            x = _mark(b.to)
            value = f"{x}" if b.do == "walk" else f"{x},{HEIGHTS[b.height]}"
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


def write(series, kits: dict[str, Kit], n: int = 40, idea: str = "", remake: bool = False):
    """The episode (cartoons.Episode, one shot a scene) and each shot's Layout; and the props to draw. A remake
    retells an episode made before (the idea says which), so the list of episodes not to repeat is left out."""
    from newsroom import llm
    from entertainment import cartoons

    user = brief(series, kits, list(series.places)) + (f"\n\nTHIS EPISODE'S IDEA: {idea}" if idea else "") \
        + ("" if remake else cartoons._done(series))
    script = llm.complete_json(cartoons.TASK, PScript, SYSTEM.format(title=series.title, premise=series.premise,
                                                                     tone=series.tone, n=n), user)
    talkers = {c.key for c in series.cast if c.voice}
    props = {p.key.strip().lower(): p.looks for p in script.props}
    scenes, layouts = [], []
    for k, s in enumerate(script.shots, start=1):
        if s.line and s.line.who not in talkers:
            s.line = None
        if s.place not in series.places:
            s.place = (difflib.get_close_matches(s.place, series.places, n=1, cutoff=0.0) or [s.place])[0]
        if s.line and s.line.who not in {a.who.strip().lower() for a in s.stage.actors}:
            s.stage.actors.append(StageActor(who=s.line.who))        # the speaker is in his own shot
            log.warning("cutout writer: shot %d's speaker %s was not on stage; put at centre", k, s.line.who)
        cast_here = [a.who.strip().lower() for a in s.stage.actors if a.who.strip().lower() in {c.key for c in series.cast}]
        props_here = [a.who.strip().lower() for a in s.stage.actors if a.who.strip().lower() in props]
        scenes.append(cartoons.Scene(
            place=s.place, on_screen=cast_here[:3], summary=s.action[:200],
            shots=[cartoons.Shot(at=0.0, action=f"{s.stage.camera.size} shot: {s.action}"[:300])],
            lines=[cartoons.Said(who=s.line.who, words=s.line.words)] if s.line else [], sounds=s.sounds,
            seconds=s.seconds, props=[f"{p}: {props[p]}" for p in props_here]))
        layouts.append(s.stage)
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
    from entertainment.cutout import kit as kitmod

    series = cartoons.SERIES[folder.parent.name]
    ep = cartoons.Episode.model_validate_json((folder / "episode.json").read_text(encoding="utf-8"))
    kits = kitmod.kits(folder.parent)
    props = set(json.loads((folder / "props.json").read_text(encoding="utf-8"))) if (folder / "props.json").exists() else set()
    done = 0
    for i, scene in enumerate(ep.scenes, start=1):
        src = folder / f"scene{i:02d}.stage.json"
        if not src.exists():
            continue
        lay = stage(Stage.model_validate_json(src.read_text(encoding="utf-8")), place_number(series, scene.place),
                    kits, props)
        (folder / f"scene{i:02d}.layout.json").write_text(lay.model_dump_json(indent=1), encoding="utf-8")
        done += 1
    return done
