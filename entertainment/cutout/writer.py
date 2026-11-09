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
REACH = 9.0                                    # units: how far from its mark a "raised" puppet looks for a spot
GAP = 0.5                                      # units of air between two who stand side by side
EDGE_X = 14.0                                  # a wide shot's edge is 16: nobody is spread past this
TOP = 16.2                                     # a wide shot's top edge, in stage units


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
    do: Literal["pose", "face", "lean", "hop", "turn", "exit", "walk", "fly", "spin", "take", "drop"]
    value: str = Field("", description="pose: a POSE; face: a FACE; lean: degrees forward, 3 to 8; spin: "
                                       "degrees (180 hangs it upside down, 360 a full turn); exit: left or right; "
                                       "take: the prop key picked up (carried from then on); drop: 'ground' "
                                       "(lands with a bounce) or 'off' (falls out of the bottom of the shot)")
    to: str | None = Field(None, description="walk or fly: the mark or SPOT to go to")
    height: Literal["ground", "raised", "air"] = "ground"
    at: str = Field("0", description="seconds, or line / line_end / end with +/- seconds")
    until: str | None = None


class StageCamera(BaseModel):
    size: Literal["wide", "medium", "close"] = "wide"
    on: str | None = Field(None, description="medium/close: who (a close shot is of their head)")
    move: Literal["hold", "push_in", "pull_out", "tilt_up", "tilt_down"] = "hold"   # tilts: old stages only


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
- ACTION: what we see, simply (who comes in, who turns, who hops, who stares, who picks a thing up, what
  drops); never fiddly handiwork, and nothing a paper puppet has no drawing for (no sniffing, nibbling,
  pointing, rubbing wings, tying knots): that is said in a line or heard, not seen.
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
  off_right to start out of shot and come in), at a HEIGHT (ground or air), FACING left or right, in one of
  their POSES. ENTER left/right walks (or waddles) them in at the start. Two who talk face each other, on
  marks next to each other but not the same mark; nobody shares a mark with anybody or anything.
  A MARK can instead be one of the place's SPOTS, where the shot lists them (a sill, a wall top, a rail): it
  stands exactly there on the backdrop. Anything that is ON something (a parcel on a sill, a gull on a wall)
  goes on a SPOT; there is nothing else to stand on, so with no fitting spot it is on the ground. Spots are
  perches for props, the gull and the cat; people stand on the ground on a mark, never on a spot.
  HOLDS: a prop they carry all shot (in beak, mouth or hand): whenever someone carries something, say so with
  HOLDS or a TAKE beat, or it stays where it was put. A prop offered or shown is HELD by whoever offers it.
- BEATS, timed in seconds or against the lines ("line", "line2", "line_end+0.3"): pose X until T, face X
  until T, lean (degrees forward), hop, turn (face the other way), walk to a mark, fly to a mark or a SPOT
  (only those who CAN FLY; a thrown prop can fly too, in an arc), take a prop (it travels to the beak or hand
  and is carried from then on), drop (WHO is the prop: value "ground", it falls and lands with a bounce, or
  "off", it falls out of the bottom of the shot; WHO is whoever carries a prop: they let go of it, and it is
  set down on the SPOT they stand by, or with none it falls to the ground; with value "off" it is gone for
  good, eaten or lost), spin (degrees: 180 hangs it upside down by its feet from a rope the stage
  draws, lifted high enough to hang; 360 a full flip), exit left/right.
  Stage ONLY what these beats can show. Business a puppet has no beat or pose for (sniffing, nibbling,
  pointing, tying) is played as a lean, a hop, a turn or a look, never left as nothing: every shot longer than
  four seconds has at least two beats, so nobody stands frozen through a long line.
- ROPE: a rope tied to who.part (or to a prop) running along the ground to a mark, if the shot shows one. It
  follows whoever it is tied to.
- CAMERA: wide (the whole stage), medium on someone, or close on someone (their head); hold, push_in or
  pull_out. The shot shows what its action is about: a prop that matters in the shot is in a wide shot, or
  held by whoever the camera is on. VARY IT: shots that follow each other at one place
  never have the same framing twice running. Cut between the wide two-shot, a medium on whoever speaks, and a
  close on whoever listens and reacts; a medium or close on one of two who talk is the usual shot.
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


def _spread(actors: list[Actor], kits: dict[str, Kit]) -> None:
    """Whoever stands in a row on the ground stands clear of their neighbours. The marks are six units apart and
    Gully is eight wide: on left, centre and right three puppets overlapped, and a parcel in Mr Trethewey's
    hand sat on Gully's chest (the Chip Lift's shot 24, 2026-11-09)."""
    row = sorted((a for a in actors if not a.on and not a.spot and a.y == 0 and abs(a.x) <= EDGE_X),
                 key=lambda a: a.x)
    half = {a.who: kits[a.who].half * a.scale for a in row}
    for _ in range(12):
        moved = False
        for l, r in zip(row, row[1:]):
            short = GAP - ((r.x - half[r.who]) - (l.x + half[l.who]))
            if short > 1e-3:
                l.x, r.x, moved = l.x - short / 2, r.x + short / 2, True
        if not moved:
            break
    if row:                                               # the whole row back inside the shot, if it fits
        over = max(0.0, row[-1].x + half[row[-1].who] - EDGE_X) - max(0.0, -EDGE_X - (row[0].x - half[row[0].who]))
        for a in row:
            a.x = round(a.x - over, 3)


def stage(st: Stage, place: int, kits: dict[str, Kit], props: set[str],
          spots: dict[str, tuple[float, float]] | set[str] = frozenset()) -> Layout:
    """A writer's stage as a Layout in stage units. Unknown characters and props are dropped (logged). A mark
    that names one of the place's spots (its sill) puts them exactly there on the backdrop. `spots` with their
    places (stage units from the plate's bottom middle, engine.spots_of) lets "raised" find the nearest one:
    raised with nothing under it stood Gully in mid-air in front of the chip shop, so without a spot in reach
    it is the ground."""
    known = set(kits)
    where = spots if isinstance(spots, dict) else {}
    at_wide = {k: (x, y - 3.0) for k, (x, y) in where.items()}       # where a spot is in a wide shot

    def nearest(x: float, taken: set[str], who: str = "") -> str | None:
        near = sorted((abs(sx - x), k) for k, (sx, _) in where.items()
                      if k not in taken and abs(sx - x) <= REACH and fits(k, who))
        return near[0][1] if near else None

    def fits(spot: str, who: str) -> bool:
        """A spot someone would stand out of the top or the side of a wide shot on is no place for them (Dot
        "at her stall" stood on its table, half out of the left of the shot)."""
        if who not in kits or spot not in at_wide:
            return True
        x, y = at_wide[spot]
        return y + kits[who].height * 0.85 <= TOP and abs(x) + kits[who].half <= EDGE_X + 1.5

    actors, held, used = [], {}, set()
    for a in st.actors:
        who = a.who.strip().lower()
        if who not in known:                              # a prop not drawn yet is staged once it is (props)
            (log.debug if who in props else log.warning)("cutout writer: %r has no puppet; left out", a.who)
            continue
        if any(x.who == who for x in actors):             # listed twice: one puppet, the first place it was put
            continue
        k = kits[who]
        pose = a.pose if a.pose in k.poses else "normal"
        mark = a.mark.strip().lower().replace(" ", "_")
        spot = mark if mark in spots and fits(mark, who) else None
        y = HEIGHTS[a.height]
        if mark in spots and spot is None:                # too high for them: under it, on the ground
            x = at_wide.get(mark, (0.0, 0.0))[0]
            reach = EDGE_X - k.half
            actors.append(Actor(who=who, x=round(max(-reach, min(reach, x)), 3), facing=a.facing, pose=pose,
                                enter=a.enter))
            continue
        if spot is None and a.height == "raised":
            spot = nearest(_mark(a.mark), used, who)
            if spot is None:
                y = 0.0
        if spot:
            used.add(spot)
        actors.append(Actor(who=who, x=0.0 if spot else _mark(a.mark), y=0.0 if spot else y,
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

    def spins(who: str) -> bool:
        return any(b.who.strip().lower() == who and b.do == "spin"
                   and abs(float(re.sub(r"[^0-9.\-]", "", b.value) or 0)) >= 150 for b in st.beats)
    for a in actors:
        # Hung upside down: a spin turns a card round its feet, so from the writer's "air" Gully's body hung
        # below the ground (the Chip Lift, 2026-11-08). He hangs from a height he fits under, and whatever is
        # on his mark up there (the hook) goes up with him.
        if spins(a.who):
            hang = round(kits[a.who].height * 1.1 + 1.0, 2)
            if a.spot:
                a.x, a.spot = at_wide.get(a.spot, (0.0, 0.0))[0], None
            for x in actors:
                if x is a or (x.who in props and x.x == a.x and x.y > 0 and not x.on):
                    x.y = hang
    hung = {a.who: a.y for a in actors if spins(a.who)}
    _spread(actors, kits)
    carried = {a.on.partition(".")[0]: a for a in actors if a.on}
    beats = []
    for b in st.beats:
        who = b.who.strip().lower()
        if who not in names or b.do == "take":
            continue
        if b.do == "drop" and (who in carried or any(a.who == who and a.on for a in actors)):
            # Whoever carries something and drops lets go of it; they don't fall themselves (the stager's
            # "trethewey: drop" for setting the chips down). The stage sets it on a spot in reach, or drops it.
            prop = carried.get(who) or next(a for a in actors if a.who == who)
            prop.off_at = b.at or "0"
            prop.off_out = "off" in f"{b.value} {b.to or ''}".lower()
            continue
        if b.do == "drop" and who not in props:           # nothing in hand: nobody falls through the floor
            continue
        value = b.value
        if b.do in ("walk", "fly"):
            to = (b.to or "").strip().lower().replace(" ", "_")
            if to in at_wide:                             # to a spot: onto the sill, the wall (a walk: up to it)
                x, y = at_wide[to] if b.do == "fly" else (at_wide[to][0], 0.0)
            else:
                x, y = _mark(b.to), HEIGHTS[b.height]
                if b.height == "raised":                  # raised is a spot, or it is the ground
                    near = nearest(x, set(), who)
                    x, y = at_wide[near] if near and b.do == "fly" else (x, 0.0)
            # A hanging puppet's move is a swing: along at its height (a fly "to the ground" dragged the
            # upside-down Gully's head under it, the talking Chip Lift's shot 19).
            y = hung.get(who, y)
            value = f"{x}" if b.do == "walk" else f"{x},{y}"
        elif b.do == "drop":
            value = "-25" if "off" in f"{b.value} {b.to or ''}".lower() else "0"
        elif b.do == "spin":
            value = re.sub(r"[^0-9.\-]", "", value) or "360"
        elif b.do == "lean":
            value = re.sub(r"[^0-9.\-]", "", value) or "4"
        beats.append(LBeat(who=who, do=b.do, value=value, at=b.at or "0", until=b.until))
    ropes = []
    if st.rope:
        who, _, part = st.rope.attach.strip().lower().partition(".")
        if who in names and who not in hung:
            x0 = next(a.x for a in actors if a.who == who)
            x1 = _mark(st.rope.to)
            pts = [(x0 + (x1 - x0) * u, 0.1 + 0.12 * ((i % 2) - 0.5)) for i, u in enumerate((0.1, 0.35, 0.6, 0.85, 1.0))]
            ropes.append(Rope(attach=f"{who}.{part or 'ankle'}", path=pts))
    for who in hung:
        # Hung from something: a rope from the ankle up out of the top of the shot. The script said "from the
        # hook" and the stage drew nothing, so Gully hung from thin air (shots 18, 19 and 21).
        ropes.append(Rope(attach=f"{who}.ankle", up=True))
    c = st.camera
    on = (c.on or "").strip().lower() or None
    if on and on.partition(".")[0] not in names:
        on = None
    size = c.size if on or c.size == "wide" else "wide"
    move = {"tilt_up": "push_in", "tilt_down": "pull_out"}.get(c.move, c.move)   # a tilt began on feet: no more
    if on:
        who = on.partition(".")[0]
        # A close shot is of a face: one of somebody's feet, or of the chin of somebody hanging upside down,
        # showed nothing (shots 15 and 19). The whole of them instead.
        if on.endswith(".feet") or (who in hung and size == "close"):
            on, size = who, "medium"
        elif on.partition(".")[2] not in ("", "head"):
            on = who
    wide_enough = 0.8 if on and on.partition(".")[0] in hung else None   # room for the rope he hangs from
    start = Framing(size=size, on=on, zoom=wide_enough or 1.0)
    end = None
    if wide_enough:
        pass
    elif move == "push_in":
        start, end = Framing(size=size, on=on, zoom=0.85), Framing(size=size, on=on, zoom=1.0)
    elif move == "pull_out":
        start, end = Framing(size=size, on=on, zoom=1.0), Framing(size=size, on=on, zoom=0.85)
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
    cast = {c.key for c in series.cast}
    out: list[Stage] = []
    for b0 in range(0, len(script.shots), BATCH):
        batch = script.shots[b0:b0 + BATCH]
        rows = []
        for k, s in enumerate(batch, start=1):
            said = " / ".join(f"{l.who}{' (off screen)' if l.offscreen else ''}: \"{l.words}\"" for l in s.lines)
            here = places_spots.get(s.place, [])
            rows.append(f"{k}. at {s.place}" + (f" (its SPOTS: {', '.join(here)})" if here else "")
                        + f"; {s.seconds:.0f} seconds; seen: {', '.join(s.seen) or 'nobody'}; {s.action}"
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


def restage(folder: Path) -> int:
    """Stage an episode's shots again from its script as it stands: the talk, its recorded sound and the props
    are kept; only where everyone stands, what they do and the camera are written afresh (after the stager's
    brief or the stage itself has learned something). The old stages are kept in stages.K/. Returns how many
    shots were laid out."""
    from entertainment import cartoons
    from entertainment.cutout import kit as kitmod

    series = cartoons.SERIES[folder.parent.name]
    ep = cartoons.Episode.model_validate_json((folder / "episode.json").read_text(encoding="utf-8"))
    kits = kitmod.kits(folder.parent)
    props = json.loads((folder / "props.json").read_text(encoding="utf-8")) if (folder / "props.json").exists() else {}
    shots = []
    for i, sc in enumerate(ep.scenes, start=1):
        old = folder / f"scene{i:02d}.stage.json"
        seen = [a.who for a in Stage.model_validate_json(old.read_text(encoding="utf-8")).actors] if old.exists() \
            else list(sc.on_screen)
        shots.append(PShot.model_construct(
            place=sc.place, seen=seen, action=sc.summary, seconds=sc.seconds, sounds=sc.sounds, sfx=[],
            lines=[Said.model_construct(who=l.who, words=l.words, offscreen=l.offscreen) for l in sc.lines]))
    script = PScript.model_construct(title=ep.title, logline=ep.logline, shots=shots,
                                     props=[PProp.model_construct(key=k, looks=v) for k, v in props.items()])
    stages = staged(series, kits, script)
    for sc, st in zip(ep.scenes, stages):                 # a speaker seen is on stage
        on_stage = {a.who.strip().lower() for a in st.actors}
        for l in sc.lines:
            if not l.offscreen and l.who not in on_stage:
                st.actors.append(StageActor(who=l.who))
                on_stage.add(l.who)
    keep = folder / f"stages.{len(list(folder.glob('stages.*'))) + 1}"
    keep.mkdir()
    for old in folder.glob("scene[0-9][0-9].stage.json"):
        old.replace(keep / old.name)
    save(folder, stages, props)
    return relayout(folder)


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
                    engine.spots_of(folder.parent, n, kitmod.plate(folder.parent, n)))
        (folder / f"scene{i:02d}.layout.json").write_text(lay.model_dump_json(indent=1), encoding="utf-8")
        done += 1
    return done
