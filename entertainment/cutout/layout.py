"""A shot laid out for the puppets, and its plan for every frame.

The stage: units where Gully stands 10 tall, x = 0 in the middle and about ±12 at a wide shot's edges, the
ground at y = 0. A Layout says who stands where (feet at x, y), facing which way, in which pose, the beats
they play (a pose or a face for a while, a lean, a hop, a turn, an exit), any rope, and the camera. Times are
written against the shot's lines, so a beat stays on its words: "0.4", "line", "line+0.2", "line_end-0.1",
"end-0.5" ("line" is the first line's start, "line_end" the last one's end).

The plan is plain JSON for blender_play.py: per frame, each card's piece and transform (stepped on twos),
the camera (smooth) and the plate (half the camera's move: a little depth). Speaking is automatic: the
speaker's face follows lips.py, he leans into the line and bobs on a loud syllable; everyone blinks now and
then while their face is free.
"""
from __future__ import annotations

import math
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

from entertainment.cutout import FPS
from entertainment.cutout.kit import PAD, Kit

WIDE = (32.0, 7.5)                 # the wide shot: ortho width, centre height (Gully a little over half its height)
SIZES = {"wide": 32.0, "medium": 16.0, "close": 8.0}
ASPECT = 1152 / 640
PLATE_W = 40.0
ENTER_S = 0.75


class Beat(BaseModel):
    who: str
    do: Literal["pose", "face", "lean", "hop", "turn", "exit", "walk", "fly", "spin"]
    value: str = ""                # pose or face name; lean degrees (forward +); exit side "left"/"right";
                                   # walk: "x"; fly: "x,y" (where to, by `until`, else in 1.2 s)
    at: str = "0"
    until: str | None = None       # pose/face/lean: when it ends (None: the shot's end)


class Actor(BaseModel):
    who: str
    x: float = 0.0
    y: float = 0.0
    depth: int = Field(0, ge=0, le=3)              # 0 in front
    facing: Literal["left", "right"] = "left"
    pose: str = "normal"
    enter: Literal["none", "left", "right"] = "none"
    scale: float = Field(1.0, gt=0.2, le=3.0)
    on: str | None = None          # "gully.hold": carried, its grip on that point of the holder every frame
    on_at: str = "0"               # from when (a snatched bucket sits where it is until it's taken)


class Rope(BaseModel):
    attach: str | None = None      # "who.anchor": a loop round that point, and the rope starts there
    path: list[tuple[float, float]] = []
    color: tuple[float, float, float] = (0.02, 0.07, 0.40)      # linear RGB: the Chip Lift's blue nylon
    width: float = 0.24


class Framing(BaseModel):
    size: Literal["wide", "medium", "close"] = "wide"
    on: str | None = None          # "gully" (medium: the whole of him; close: his head) or "gully.ankle"
    dx: float = 0.0
    dy: float = 0.0
    zoom: float = Field(1.0, gt=0.3, le=3.0)       # above 1 closer in (a push-in ends higher than it starts)


class Camera(BaseModel):
    start: Framing = Framing()
    end: Framing | None = None
    move_at: str = "0"
    move_until: str = "end"


class Layout(BaseModel):
    place: int = Field(ge=1)       # the series' place number: its plate
    actors: list[Actor] = []
    beats: list[Beat] = []
    ropes: list[Rope] = []
    camera: Camera = Camera()


# ------------------------------------------------------------------ the plan


def when(ref: str, n: int, spans: list[tuple[str, float, float]]) -> int:
    """A time reference as a frame (1-based, clamped to the shot)."""
    ref = ref.replace(" ", "")
    base, off = ref, 0.0
    for sign in ("+", "-"):
        if sign in ref[1:]:
            k = ref.rindex(sign)
            base, off = ref[:k], float(ref[k:])
            break
    t = {"start": 0.0, "line": min((s[1] for s in spans), default=0.0),
         "line_end": max((s[2] for s in spans), default=0.0), "end": n / FPS}.get(base)
    if t is None:
        t, off = float(ref), 0.0
    return max(1, min(n, round((t + off) * FPS) + 1))


class _Puppet:
    """An actor with its kit: where its card sits and where its named points are."""

    def __init__(self, a: Actor, kit: Kit, w_px: int, h_px: int):
        self.a, self.kit, self.w, self.h = a, kit, w_px, h_px
        self.upp = kit.upp * a.scale
        self.flip = kit.natural != "front" and a.facing != kit.natural
        self.card_y = a.y - (h_px - (kit.feet_y + PAD)) * self.upp     # the card's bottom, so feet are at a.y

    def point(self, name: str) -> tuple[float, float]:
        ax, ay = self.kit.anchors.get(name, (self.w / 2 - PAD, self.kit.feet_y))
        lx = (ax + PAD - self.w / 2) * self.upp * (-1 if self.flip else 1)
        return self.a.x + lx, self.card_y + (self.h - (ay + PAD)) * self.upp

    @property
    def tall(self) -> float:
        return self.kit.height * self.a.scale


def _view(fr: Framing, pup: dict[str, _Puppet]) -> tuple[float, float, float]:
    width = SIZES[fr.size] / fr.zoom
    if fr.on is None or fr.size == "wide":
        return fr.dx, WIDE[1] + fr.dy, width
    who, _, point = fr.on.partition(".")
    p = pup[who]
    if fr.size == "medium" and not point:
        return p.a.x + fr.dx, p.a.y + p.tall * 0.5 + fr.dy, width
    x, y = p.point(point or "head")
    return x + fr.dx, y + fr.dy, width


def _world(c: dict, p: "_Puppet", f: int, point: str) -> tuple[float, float]:
    """A point of a card at frame index f, in stage units: a named anchor, or (no name) the card's middle."""
    x, y, rot, sx, sy = c["tf"][f]
    upp = p.upp / p.a.scale                               # sx, sy carry the actor's scale and its mirroring
    if point:
        ax, ay = p.kit.anchors.get(point, p.kit.anchors.get("head", (p.w / 2 - PAD, 0)))
        lx, ly = (ax + PAD - p.w / 2) * upp * sx, (p.h - (ay + PAD)) * upp * sy
    else:
        lx, ly = 0.0, p.h * upp * sy / 2
    return x + lx * math.cos(rot) - ly * math.sin(rot), y + lx * math.sin(rot) + ly * math.cos(rot)


def _ease(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def plan(layout: Layout, kits: dict[str, Kit], series_dir: Path, n: int, speech: dict[str, list[str]],
         spans: list[tuple[str, float, float]], plate: Path, sizes: dict[str, tuple[int, int]]) -> dict:
    """Every frame of the shot: the plate, the camera, each card's piece and transform, the ropes.
    `speech` is lips.faces' per-frame faces by speaker; `sizes` each kit's piece size in pixels."""
    pup = {a.who: _Puppet(a, kits[a.who], *sizes[a.who]) for a in layout.actors}
    cam0 = _view(layout.camera.start, pup)              # first guess: rest spots (entrances start off its edges)
    m0, m1 = when(layout.camera.move_at, n, spans), when(layout.camera.move_until, n, spans)
    cards, by_who = [], {}
    for k, a in enumerate(layout.actors):
        c = _card(k, a, pup[a.who], kits[a.who], [b for b in layout.beats if b.who == a.who],
                  speech.get(a.who, ["closed"] * n), n, spans, cam0, series_dir)
        holder = (a.on or "").partition(".")[0]
        if holder in by_who:                              # carried: its grip on the holder's point, once taken
            hc, hp = by_who[holder]
            point = a.on.partition(".")[2] or "hold"
            p = pup[a.who]
            gx, gy = kits[a.who].anchors.get("grip", (p.w / 2 - PAD, 0))
            for f in range(when(a.on_at, n, spans) - 1, n):
                wx, wy = _world(hc, hp, f, point)
                c["tf"][f] = [round(wx - (gx + PAD - p.w / 2) * p.upp, 4),
                              round(wy - (p.h - (gy + PAD)) * p.upp, 4), 0.0, round(a.scale, 4), round(a.scale, 4)]
            c["z"] = round(hc["z"] + 0.02, 3)
        by_who[a.who] = (c, pup[a.who])
        cards.append(c)

    def view(fr: Framing, f: int) -> tuple[float, float, float]:
        """The camera on someone where their card is at frame f: upside down, flying, wherever."""
        width = SIZES[fr.size] / fr.zoom
        who, _, point = (fr.on or "").partition(".")
        if fr.size == "wide" or who not in by_who:
            return _view(fr, pup)
        c, p = by_who[who]
        x, y = _world(c, p, f - 1, point or ("" if fr.size == "medium" else "head"))
        return x + fr.dx, y + fr.dy, width
    mid = m1 if layout.camera.end else (n + 1) // 2      # a held camera frames the shot's middle, after arrivals
    cam0 = view(layout.camera.start, m0 if layout.camera.end else mid)
    cam1 = view(layout.camera.end, m1) if layout.camera.end else cam0
    camera, plate_at = [], []
    for f in range(1, n + 1):
        u = _ease((f - m0) / max(1, m1 - m0))
        x, y, w = (a + (b - a) * u for a, b in zip(cam0, cam1))
        camera.append([round(x, 4), round(y, 4), round(w, 4)])
        plate_at.append([round(0.5 * x, 4), round(-3.0 + 0.5 * (y - WIDE[1]), 4)])
    ropes = []
    for r in layout.ropes:
        pts = [list(pt) for pt in r.path]
        loop = None
        if r.attach:
            who, _, point = r.attach.partition(".")
            ax, ay = pup[who].point(point)
            s = pup[who].a.scale
            loop = [round(ax, 4), round(ay, 4), round(0.5 * s, 4), round(0.22 * s, 4)]
            pts = [[ax - 0.4 * s, ay - 0.05], *pts]
        ropes.append({"points": pts, "loop": loop, "color": list(r.color), "width": r.width})
    return {"fps": FPS, "frames": n, "plate": {"path": str(plate), "width": PLATE_W, "at": plate_at},
            "camera": camera, "aspect": ASPECT, "cards": cards, "ropes": ropes}


def _target(b: Beat, x: float, y: float) -> tuple[float, float]:
    parts = [float(v) for v in b.value.replace(" ", "").split(",") if v]
    return (parts[0] if parts else x), (parts[1] if len(parts) > 1 else y)


def _card(k, a: Actor, p: _Puppet, kit: Kit, mine: list[Beat], talk: list[str], n: int, spans, cam0,
          series_dir: Path) -> dict:
    """One actor's card for every frame: its piece and its transform, all on twos."""
    moves = sorted((b for b in mine if b.do in ("walk", "fly")), key=lambda b: when(b.at, n, spans))
    walker = bool(kit.walk)
    entering = when(f"{ENTER_S}", n, spans) if a.enter != "none" else 0
    exit_beat = next((b for b in mine if b.do == "exit"), None)
    exit_at = when(exit_beat.at, n, spans) if exit_beat else n + 1
    off = {side: cam0[0] + (cam0[2] / 2 + p.w * p.upp / 2) * (-1 if side == "left" else 1)
           for side in ("left", "right")}

    def where(f):
        """(x, y, how it is moving, which way): the rest spot, an entrance, a walk or flight, an exit."""
        if f < entering:
            u = f / entering if walker else 1 - (1 - f / entering) ** 2
            x0 = off[a.enter]
            return x0 + (a.x - x0) * u, a.y, "enter", 1 if a.x > x0 else -1
        x, y = a.x, a.y
        for b in moves:
            s = when(b.at, n, spans)
            e = when(b.until, n, spans) if b.until else min(n, s + int(1.2 * FPS))
            tx, ty = _target(b, x, y)
            if f < s:
                break
            if f >= e:
                x, y = tx, ty
                continue
            u = (f - s) / max(1, e - s)
            u = u if b.do == "walk" else _ease(u)
            return x + (tx - x) * u, y + (ty - y) * u, b.do, (1 if tx > x else -1 if tx < x else 0)
        if f >= exit_at:
            u = min(1.0, (f - exit_at) / (ENTER_S * FPS))
            u = u if walker else u * u
            x1 = off[exit_beat.value if exit_beat.value in off else "right"]
            return x + (x1 - x) * u, y, "exit", 1 if x1 > x else -1
        return x, y, None, 0

    facing = a.facing
    pieces, tf = [], []
    for f in range(1, n + 1):
        if f % 2 == 0:                                    # on twos: the piece and the pose held
            pieces.append(pieces[-1])
            tf.append(tf[-1])
            continue

        def active(b):
            return when(b.at, n, spans) <= f < (when(b.until, n, spans) if b.until else n + 1)
        x, y, how, way = where(f)
        if way:
            facing = "right" if way > 0 else "left"
        for b in mine:
            if b.do == "turn" and when(b.at, n, spans) in (f, f + 1):
                facing = "left" if facing == "right" else "right"
        if how in ("walk", "enter", "exit") and walker:
            pose = kit.walk[(f // 4) % len(kit.walk)]
        elif how == "fly" and kit.fly:
            pose = kit.fly
        else:
            pose = next((b.value for b in reversed(mine) if b.do == "pose" and active(b)), a.pose)
            pose = pose if pose in kit.poses else "normal"
        said = talk[f - 1]
        face = {"talk": "talk", "loud": kit.loud}.get(said)
        if face is None:
            face = next((b.value for b in reversed(mine) if b.do == "face" and active(b)), None)
        if face is None:                                  # a blink about every three seconds, two frames
            face = "blink" if (f + 23 * k) % 74 in (0, 1) and f > entering + 4 else "closed"
        pieces.append(str(kit.piece(series_dir, pose, face)))
        natural = kit.natural_of(pose)
        flip = natural != "front" and facing != natural
        fwd = (1 if not flip else -1) * (-1 if natural == "right" else 1)    # the turn that tips the top forward
        t = f / FPS
        cy = y - (p.h - (kit.feet_of(series_dir, pose) + PAD)) * p.upp
        rot, sx = 0.0, 1.0
        sy = 1.0 + 0.01 * math.sin(2 * math.pi * 0.5 * t + k)
        if said != "closed":
            rot += math.radians(2.0) * fwd
        if said == "loud":
            rot += math.radians(1.5) * fwd
            cy += 0.06
        lean = next((b for b in reversed(mine) if b.do == "lean" and active(b)), None)
        if lean:
            rot += math.radians(float(lean.value or 0)) * fwd
        for b in mine:                                    # a hop: eight frames up and down
            if b.do == "hop" and 0 <= f - when(b.at, n, spans) < 8:
                cy += 0.8 * math.sin(math.pi * (f - when(b.at, n, spans)) / 8)
            if b.do == "spin" and f >= when(b.at, n, spans):  # round its base: 180 hangs it from there
                s = when(b.at, n, spans)
                e = when(b.until, n, spans) if b.until else min(n, s + 8)
                done = 1.0 if s <= 1 else min(1.0, (f - s + 1) / max(1, e - s))   # at 0: already so
                rot += math.radians(float(b.value or 360)) * done * fwd
        if how in ("enter", "exit", "walk"):
            if walker:                                    # a step: up on each stride
                cy += 0.12 if (f // 4) % 2 else 0.0
            else:                                         # no walk drawn: a waddle, rocking and bobbing
                rot += math.radians(5.0) * (1 if (f // 4) % 2 else -1)
                cy += 0.18 if (f // 2) % 2 else 0.0
        elif how == "fly" and kit.fly:                    # wings: a bob and a flap (a flung bucket just flies)
            cy += 0.25 * math.sin(2 * math.pi * f / 12)
            sy *= 1.0 + 0.05 * math.sin(2 * math.pi * f / 6)
        elif entering and 0 <= f - entering < 6:          # arriving: squash, stretch, settle
            s = (0.94, 0.94, 1.03, 1.03, 1.0, 1.0)[f - entering]
            sx, sy = 1 / s ** 0.5, s
        tf.append([round(x, 4), round(cy, 4), round(rot, 5), round(sx * (-1 if flip else 1) * a.scale, 4),
                   round(sy * a.scale, 4)])
    return {"name": a.who, "pieces": pieces, "w_px": p.w, "h_px": p.h, "upp": kit.upp,
            "z": round(0.1 * (3 - a.depth) + 0.01 * k, 3), "tf": tf}
