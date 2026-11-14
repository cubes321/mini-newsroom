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

from entertainment.cutout import FPS, at_seconds
from entertainment.cutout.kit import PAD, Kit

WIDE = (32.0, 7.5)                 # the wide shot: ortho width, centre height (Gully a little over half its height)
SIZES = {"wide": 32.0, "medium": 16.0, "close": 8.0}
ASPECT = 1152 / 640
PLATE_W = 40.0
ENTER_S = 0.75
TAKE_F = 6                         # frames a taken prop travels into the beak or hand
PUT_REACH = 4.5                    # units: a prop let go this near a spot is set down on it; else it falls
FALL_F = 10
PROP_NEAR = 9.0                    # units: a prop this near a medium shot's subject is taken into the shot


class Beat(BaseModel):
    who: str
    do: Literal["pose", "face", "lean", "hop", "turn", "exit", "walk", "fly", "spin", "drop"]
    value: str = ""                # pose or face name; lean degrees (forward +); exit side "left"/"right";
                                   # walk: "x"; fly: "x,y" (where to, by `until`, else in 1.2 s); either
                                   # may add ",scale": how big it is drawn there (a far spot: smaller);
                                   # drop: the height it falls to ("0" lands with a bounce; "-25" out of shot)
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
    spot: str | None = None        # a named point of the backdrop ("sill"): stands exactly there, not at x, y
    off_at: str | None = None      # carried until then, and let go: set down on a spot within reach, or dropped
    off_out: bool = False          # let go for good: it falls out of the bottom of the shot (eaten, lost)


class Rope(BaseModel):
    attach: str | None = None      # "who.anchor": a loop round that point, and the rope starts there
    path: list[tuple[float, float]] = []
    up: bool = False               # hangs straight up out of the top of the shot from its attachment
    color: tuple[float, float, float] = (0.02, 0.07, 0.40)      # linear RGB: the Chip Lift's blue nylon
    width: float = 0.24
    loop: bool = True              # tied on with a loop round the point; a spider's thread just starts there


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
    """A time reference as a frame (1-based, clamped to the shot): seconds, or start / end / line / line_end /
    lineN / lineN_end with +/- seconds (spans: the lines as (who, start, end), in order)."""
    t = at_seconds(ref or "0", [(s[1], s[2]) for s in spans], n / FPS)
    return max(1, min(n, round(t * FPS) + 1))


class _Puppet:
    """An actor with its kit: where its card sits and where its named points are."""

    def __init__(self, a: Actor, kit: Kit, w_px: int, h_px: int):
        self.a, self.kit, self.w, self.h = a, kit, w_px, h_px
        self.upp = kit.upp * a.scale
        self.flip = kit.natural != "front" and a.facing != kit.natural
        self.card_y = a.y - (h_px - (kit.feet_y + PAD)) * self.upp     # the card's bottom, so feet are at a.y

    def point(self, name: str) -> tuple[float, float]:
        ax, ay = self.kit.anchor(name, self.a.pose) or (self.w / 2 - PAD, self.kit.feet_y)
        lx = (ax + PAD - self.w / 2) * self.upp * (-1 if self.flip else 1)
        return self.a.x + lx, self.card_y + (self.h - (ay + PAD)) * self.upp

    @property
    def tall(self) -> float:
        return self.kit.height * self.a.scale

    @property
    def half(self) -> float:
        return self.kit.half * self.a.scale

    def sides(self, mirrored: bool) -> tuple[float, float]:
        """How far the drawing reaches left and right of the card's middle, paper edge included."""
        box = self.kit._box
        if not box:
            return self.half + 0.3, self.half + 0.3
        mid = self.kit._w / 2
        left, right = (mid - box[0]) * self.upp + 0.3, (box[2] - mid) * self.upp + 0.3
        return (right, left) if mirrored else (left, right)


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
    upp = p.kit.upp                                       # sx, sy carry the frame's scale and its mirroring
    if point:
        pose = c["poses"][f]
        ax, ay = p.kit.anchor(point, pose) or p.kit.anchor("head", pose) or (p.w / 2 - PAD, 0)
        lx, ly = (ax + PAD - p.w / 2) * upp * sx, (p.h - (ay + PAD)) * upp * sy
    else:
        lx, ly = 0.0, p.h * upp * sy / 2
    return x + lx * math.cos(rot) - ly * math.sin(rot), y + lx * math.sin(rot) + ly * math.cos(rot)


def _ease(u: float) -> float:
    u = max(0.0, min(1.0, u))
    return u * u * (3 - 2 * u)


def plan(layout: Layout, kits: dict[str, Kit], series_dir: Path, n: int, speech: dict[str, list[str]],
         spans: list[tuple[str, float, float]], plate: Path, sizes: dict[str, tuple[int, int]],
         spots: dict[str, tuple] | None = None, cues: list[float] | None = None) -> dict:
    """Every frame of the shot: the plate, the camera, each card's piece and transform, the ropes.
    `speech` is lips.faces' per-frame faces by speaker; `sizes` each kit's piece size in pixels; `spots` the
    backdrop's named points, in stage units from the plate's bottom middle, each with how big a puppet is
    drawn there (x, y, scale; the scale may be left out: 1); `cues` the seconds at which something is heard
    from out of shot (a line, an effect): whoever is on stage and not speaking starts at it."""
    spots = {k: (v[0], v[1], v[2] if len(v) > 2 else 1.0) for k, v in (spots or {}).items()}
    jolts = [max(1, min(n, round(t * FPS) + 1)) for t in (cues or [])][:4]
    pup = {a.who: _Puppet(a, kits[a.who], *sizes[a.who]) for a in layout.actors}
    cam0 = _view(layout.camera.start, pup)              # first guess: rest spots (entrances start off its edges)
    spot_at = None
    if spots and any(a.spot in spots for a in layout.actors):
        # On the backdrop's sill, wherever the shot's camera puts the backdrop (it moves at half the camera's
        # speed): the cone sat loose on the quay when the writer could only say "far_right, raised".
        px, py = spot_at = 0.5 * cam0[0], -3.0 + 0.5 * (cam0[1] - WIDE[1])
        layout = layout.model_copy(update={"actors": [
            a.model_copy(update={"x": round(px + spots[a.spot][0], 3), "y": round(py + spots[a.spot][1], 3),
                                 "scale": max(0.21, round(a.scale * spots[a.spot][2], 3))})
            if a.spot in spots else a for a in layout.actors]})
        pup = {a.who: _Puppet(a, kits[a.who], *sizes[a.who]) for a in layout.actors}
        cam0 = _view(layout.camera.start, pup)
    m0, m1 = when(layout.camera.move_at, n, spans), when(layout.camera.move_until, n, spans)
    cards, by_who = [], {}
    for k, a in enumerate(layout.actors):
        c = _card(k, a, pup[a.who], kits[a.who], [b for b in layout.beats if b.who == a.who],
                  speech.get(a.who, ["closed"] * n), n, spans, cam0, series_dir, jolts)
        by_who[a.who] = (c, pup[a.who])
        cards.append(c)
    rest = {who: [list(t) for t in c["tf"]] for who, (c, _) in by_who.items()}
    guess = (0.5 * cam0[0], -3.0 + 0.5 * (cam0[1] - WIDE[1]))
    plate_at: list[list[float]] = []

    def plate_xy(f: int) -> tuple[float, float]:
        """Where the backdrop is at frame index f (before the camera is known: where it starts)."""
        return tuple(plate_at[min(f, n - 1)]) if plate_at else guess

    def carry(a: Actor):
        """A carried prop: its grip on the holder's point from when it is taken, travelling there over a few
        frames (a bucket that jumped from the ground to a hand in one frame read as a mistake)."""
        holder = (a.on or "").partition(".")[0]
        if holder not in by_who or holder == a.who:
            return
        (c, p), (hc, hp) = by_who[a.who], by_who[holder]
        point = a.on.partition(".")[2] or "hold"
        gx, gy = kits[a.who].anchor("grip") or (p.w / 2 - PAD, 0)
        t0 = when(a.on_at, n, spans) - 1
        t0 -= t0 % 2
        was = rest[a.who][t0]
        t1 = n
        if a.off_at:
            t1 = max(t0 + 2, when(a.off_at, n, spans) - 1)
            t1 -= t1 % 2
        for f in range(t0, min(n, t1)):
            g = f - f % 2                                         # on twos, like the holder
            wx, wy = _world(hc, hp, g, point)
            # As big as its holder is drawn, and it tips with him as he leans, its grip staying in his hand.
            s = a.scale * hc["scales"][g] / hp.a.scale
            rot = 0.5 * hc["tf"][g][2] if abs(hc["tf"][g][2]) < 0.6 else 0.0
            lx, ly = (gx + PAD - p.w / 2) * kits[a.who].upp * s, (p.h - (gy + PAD)) * kits[a.who].upp * s
            held = [wx - (lx * math.cos(rot) - ly * math.sin(rot)), wy - (lx * math.sin(rot) + ly * math.cos(rot)),
                    rot, s, s]
            u = _ease((g - t0 + 2) / TAKE_F) if t0 > 0 else 1.0
            c["tf"][f] = [round(r + (h - r) * u, 5) for r, h in zip(was, held)]
        c["z"] = round(hc["z"] + 0.02, 3)
        if t1 >= n:
            return
        # Let go: set down on a spot of the backdrop within reach (the chips on the sill), where it stays as the
        # backdrop moves; with none, it falls to the ground and bounces once.
        x0, y0, _, s0, _ = c["tf"][t1 - 1]
        feet_px = (p.h - (kits[a.who].feet_y + PAD)) * kits[a.who].upp      # card bottom to feet, at scale 1
        near = min(((abs(plate_xy(t1)[0] + v[0] - x0), k) for k, v in spots.items()), default=(99.0, ""))
        if a.off_out:
            near = (99.0, "")
        for f in range(t1, n):
            g = f - f % 2
            if near[0] <= PUT_REACH * max(0.5, hc["scales"][t1 - 1]) + 1.0:
                sx, sy, ss = spots[near[1]]
                u = _ease((g - t1 + 2) / TAKE_F)
                s = s0 + (a.scale * ss - s0) * u
                x, y = x0 + (plate_xy(g)[0] + sx - x0) * u, y0 + (plate_xy(g)[1] + sy - feet_px * s - y0) * u
            else:
                t, s = min(1.0, (g - t1 + 2) / FALL_F), s0
                x, y = x0, y0 + (-feet_px * s - (25.0 if a.off_out else 0.0) - y0) * t * t
                d = g - t1 + 2 - FALL_F
                if 0 <= d < 8 and not a.off_out:
                    y += 0.6 * math.sin(math.pi * d / 8)
            c["tf"][f] = [round(x, 5), round(y, 5), 0.0, round(s, 4), round(s, 4)]

    for a in layout.actors:
        carry(a)

    def view(fr: Framing, f: int) -> tuple[float, float, float]:
        """The camera on someone where their card is at frame f: upside down, flying, wherever. A medium or a
        close shot never cuts through a neighbour: whoever of the cast its edge would slice is taken in whole
        (Mr Trethewey's head was off the top of two shots he was half the joke of, 2026-11-09)."""
        width = SIZES[fr.size] / fr.zoom
        who, _, point = (fr.on or "").partition(".")
        if fr.size == "wide" or who not in by_who:
            return _view(fr, pup)
        c, p = by_who[who]
        width *= max(0.5, min(1.0, c["scales"][f - 1]))   # someone far off is framed as closely as someone near
        x, y = _world(c, p, f - 1, point or ("" if fr.size == "medium" else "head"))
        x, y = x + fr.dx, y + fr.dy
        lo, hi = x - width / 2, x + width / 2
        tops, lows = [], []                               # heads to keep in; the whole of anyone hanging

        def upright(oc, op) -> None:
            ox, oy, rot, _, sy = oc["tf"][f - 1]
            box = op.kit._box or (0, 0, op.w - 2 * PAD, op.kit.feet_y)
            top = (op.h - (box[1] + PAD)) * op.kit.upp * sy
            if abs(rot) < 0.5:
                tops.append(oy + top)
            elif abs(abs(rot) - math.pi) < 0.5:           # hung by the feet: the head is the bottom
                tops.append(oy)
                lows.append(oy - top)
        if fr.size == "medium" and not point:
            upright(c, p)
        own, tops, own_lows, lows = tops, [], lows, []
        for other, (oc, op) in by_who.items():
            if other == who or op.a.on:
                continue
            ox, _, _, osx, _ = oc["tf"][f - 1]
            reach = op.sides(osx < 0)
            left, right = ox - reach[0], ox + reach[1]
            if not op.kit.faces:                          # a prop beside them is what the shot is about
                if abs(ox - x) <= PROP_NEAR and fr.size == "medium":
                    lo, hi = min(lo, left - 0.5), max(hi, right + 0.5)
                continue
            if left < hi and right > lo:
                if not (left >= lo and right <= hi):
                    lo, hi = min(lo, left - 0.5), max(hi, right + 0.5)
                upright(oc, op)
        if hi - lo > width + 1e-6:
            wider = min(SIZES["wide"], hi - lo)
            u = (wider - width) / max(1e-6, SIZES["wide"] - width)
            x, y, width = (lo + hi) / 2, y + (WIDE[1] - y) * u, wider
        # Nobody in the shot loses their head off the top (centred on her middle, Dot's medium cut her off at
        # the eyebrows), and whoever hangs upside down is seen whole: his head is at the bottom.
        # A medium shot of someone taller than the shot loses their legs, not their head; a neighbour's head, or
        # anyone hanging by the feet, makes the shot as tall as it takes.
        tall = width / ASPECT
        if own:
            y = max(y, max(own) + 0.7 - tall / 2)
        low = min([y - tall / 2] + [v - 0.5 for v in lows + own_lows])
        high = max([y + tall / 2] + [v + 0.7 for v in tops])
        if high - low > tall + 1e-6:
            width = min(SIZES["wide"] * 1.1, (high - low) * ASPECT)
            y = low + width / ASPECT / 2
        return x, y, width

    def held(fr: Framing, first: int, last: int) -> tuple[float, float, float]:
        """The camera takes in where its subject is all through those frames, not at one of them: Gully walked
        out of the side of a medium shot framed on where he would be later (shot 3, 2026-11-09)."""
        views = [view(fr, f) for f in sorted({round(first + (last - first) * k / 4) for k in range(5)})]
        lo, hi = min(v[0] - v[2] / 2 for v in views), max(v[0] + v[2] / 2 for v in views)
        low, high = min(v[1] - v[2] / ASPECT / 2 for v in views), max(v[1] + v[2] / ASPECT / 2 for v in views)
        width = min(SIZES["wide"] * 1.1, max(hi - lo, (high - low) * ASPECT))
        return (lo + hi) / 2, low + width / ASPECT / 2, width
    def slices(v: tuple[float, float, float], f: int) -> bool:
        """Does this view's side cut through one of the cast at frame f?"""
        lo, hi = v[0] - v[2] / 2, v[0] + v[2] / 2
        for oc, op in by_who.values():
            if not op.kit.faces or op.a.on:
                continue
            ox, _, _, osx, _ = oc["tf"][f - 1]
            reach = op.sides(osx < 0)
            if ox - reach[0] < hi - 0.05 and ox + reach[1] > lo + 0.05 and not (ox - reach[0] >= lo and ox + reach[1] <= hi):
                return True
        return False

    if layout.camera.end:                                 # a move: each end frames its half of the shot
        half = (m0 + m1) // 2
        cam0, cam1 = held(layout.camera.start, m0, half), held(layout.camera.end, half, m1)
        # A move that would cut through a neighbour on the way (the push-in past Biscuit, shot 3) is made
        # inside the looser of its two framings instead: everyone it shows stays whole from end to end.
        steps = [(m0 + (m1 - m0) * k // 6, _ease(k / 6)) for k in range(7)]
        if any(slices(tuple(a + (b - a) * u for a, b in zip(cam0, cam1)), f) for f, u in steps):
            loose, pushing = max(cam0, cam1, key=lambda v: v[2]), cam1[2] < cam0[2]
            out = (loose[0], loose[1] + loose[2] * 0.06 / ASPECT, min(SIZES["wide"] * 1.1, loose[2] * 1.12))
            cam0, cam1 = (out, loose) if pushing else (loose, out)
    else:                                                 # held: the whole shot, once everyone has arrived
        cam0 = cam1 = held(layout.camera.start, max(1, n // 4), n)
    camera = []
    for f in range(1, n + 1):
        u = _ease((f - m0) / max(1, m1 - m0))
        x, y, w = (a + (b - a) * u for a, b in zip(cam0, cam1))
        camera.append([round(x, 4), round(y, 4), round(w, 4)])
    plate_at.extend([round(0.5 * x, 4), round(-3.0 + 0.5 * (y - WIDE[1]), 4)] for x, y, _ in camera)
    # Whatever stands on a spot is on the backdrop, so it rides the backdrop: placed from a first guess of the
    # camera, it goes wherever the camera really put the plate, every frame. What it carries, or whoever takes
    # it, follows from there.
    if spot_at:
        for a in layout.actors:
            if a.spot:
                for tfs in (rest[a.who], by_who[a.who][0]["tf"]):
                    for f in range(n):
                        tfs[f] = [round(tfs[f][0] + plate_at[f][0] - spot_at[0], 4),
                                  round(tfs[f][1] + plate_at[f][1] - spot_at[1], 4), *tfs[f][2:]]
    for a in layout.actors:                               # again, now the backdrop's place is known
        carry(a)
    ropes = []
    for r in layout.ropes:
        pts = [list(pt) for pt in r.path]
        loop = at = None
        who, _, point = (r.attach or "").partition(".")
        if who in by_who:
            # Tied on: the loop and the rope's end follow that point every frame (drawn once from where he
            # started, the loop was left hanging in the air when Gully flapped off, the Chip Lift's shot 12).
            c, p = by_who[who]
            point = next((x for x in (point, "ankle", "feet") if x and p.kit.anchor(x)), "")
            s = c["scales"][0]
            at = [[round(v, 4) for v in _world(c, p, f, point)] for f in range(n)]
            ax, ay = at[0]
            loop = [ax, ay, round(0.5 * s, 4), round(0.22 * s, 4)] if r.loop else None
            pts = [[ax, ay], [ax, ay + 40.0]] if r.up else [[round(ax - 0.4 * s, 4), round(ay - 0.05, 4)], *pts]
        ropes.append({"points": pts, "loop": loop, "at": at, "up": bool(r.up and at), "color": list(r.color),
                      "width": r.width})
    for c in cards:
        del c["poses"], c["scales"]
    return {"fps": FPS, "frames": n, "plate": {"path": str(plate), "width": PLATE_W, "at": plate_at},
            "camera": camera, "aspect": ASPECT, "cards": cards, "ropes": ropes}


def _target(b: Beat, x: float, y: float) -> tuple[float, float]:
    if b.do == "drop":
        try:
            return x, float(b.value or 0)
        except ValueError:
            return x, 0.0
    parts = [float(v) for v in b.value.replace(" ", "").split(",") if v]
    return (parts[0] if parts else x), (parts[1] if len(parts) > 1 else y)


def _scale_to(b: Beat, scale: float) -> float:
    parts = b.value.replace(" ", "").split(",") if b.do in ("walk", "fly") else []
    try:
        return float(parts[2]) if len(parts) > 2 and parts[2] else scale
    except ValueError:
        return scale


def _card(k, a: Actor, p: _Puppet, kit: Kit, mine: list[Beat], talk: list[str], n: int, spans, cam0,
          series_dir: Path, jolts: list[int] = ()) -> dict:
    """One actor's card for every frame: its piece and its transform, all on twos."""
    moves = sorted((b for b in mine if b.do in ("walk", "fly", "drop")), key=lambda b: when(b.at, n, spans))

    def ends(b):
        s = when(b.at, n, spans)
        return when(b.until, n, spans) if b.until else min(n, s + int((0.45 if b.do == "drop" else 1.2) * FPS))
    walker = bool(kit.walk)
    entering = when(f"{ENTER_S}", n, spans) if a.enter != "none" else 0
    exit_beat = next((b for b in mine if b.do == "exit"), None)
    exit_at = when(exit_beat.at, n, spans) if exit_beat else n + 1
    off = {side: cam0[0] + (cam0[2] / 2 + p.w * p.upp / 2) * (-1 if side == "left" else 1)
           for side in ("left", "right")}

    def where(f):
        """(x, y, how it is moving, which way, how far through): the rest spot, an entrance, a walk, a flight
        or a fall, an exit."""
        if f < entering:
            u = f / entering if walker else 1 - (1 - f / entering) ** 2
            x0 = off[a.enter]
            return x0 + (a.x - x0) * u, a.y, "enter", 1 if a.x > x0 else -1, u, a.scale
        x, y, sc = a.x, a.y, a.scale
        for b in moves:
            s, e = when(b.at, n, spans), ends(b)
            tx, ty = _target(b, x, y)
            ts = _scale_to(b, sc)
            if f < s:
                break
            if f >= e:
                x, y, sc = tx, ty, ts
                continue
            t = (f - s) / max(1, e - s)
            u = t if b.do == "walk" else t * t if b.do == "drop" else _ease(t)    # a fall gathers speed
            return (x + (tx - x) * u, y + (ty - y) * u, b.do, (1 if tx > x else -1 if tx < x else 0), t,
                    sc + (ts - sc) * u)
        if f >= exit_at:
            u = min(1.0, (f - exit_at) / (ENTER_S * FPS))
            u = u if walker else u * u
            x1 = off[exit_beat.value if exit_beat.value in off else "right"]
            return x + (x1 - x) * u, y, "exit", 1 if x1 > x else -1, u, sc
        return x, y, None, 0, 0.0, sc

    facing = a.facing
    pieces, tf, poses, scales = [], [], [], []
    busy = [when(b.at, n, spans) for b in mine if b.do in ("hop", "turn", "walk", "fly", "spin", "drop")]
    for f in range(1, n + 1):
        if f % 2 == 0:                                    # on twos: the piece and the pose held
            pieces.append(pieces[-1])
            tf.append(tf[-1])
            poses.append(poses[-1])
            scales.append(scales[-1])
            continue

        def active(b):
            return when(b.at, n, spans) <= f < (when(b.until, n, spans) if b.until else n + 1)
        x, y, how, way, through, sc = where(f)
        scales.append(sc)
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
        poses.append(pose)
        natural = kit.natural_of(pose)
        flip = natural != "front" and facing != natural
        fwd = (1 if not flip else -1) * (-1 if natural == "right" else 1)    # the turn that tips the top forward
        t = f / FPS
        cy = y - (p.h - (kit.feet_of(series_dir, pose) + PAD)) * kit.upp * sc
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
                turn = math.radians(float(b.value or 360)) * done * fwd
                rot += turn
                if not kit.faces:                         # a prop knocked over lies on its side, on the ground
                    cy += kit.half * sc * abs(math.sin(turn))
        # Something heard from out of shot (a shout, a crash): whoever stands there and isn't busy starts at it.
        if kit.faces and said == "closed" and how is None:
            for j in jolts:
                d = f - j - 2 * (k % 3)
                if 0 <= d < 6 and not any(abs(j - t) < 10 for t in busy):
                    cy += 0.28 * sc * math.sin(math.pi * d / 6)
                    sy *= 1.0 + 0.03 * math.sin(math.pi * d / 6)
        if how in ("enter", "exit", "walk"):
            if walker:                                    # a step: up on each stride
                cy += 0.12 if (f // 4) % 2 else 0.0
            else:                                         # no walk drawn: a waddle, rocking and bobbing
                rot += math.radians(5.0) * (1 if (f // 4) % 2 else -1)
                cy += 0.18 if (f // 2) % 2 else 0.0
        elif how == "fly" and kit.fly:                    # wings: a bob and a flap
            cy += 0.25 * math.sin(2 * math.pi * f / 12)
            sy *= 1.0 + 0.05 * math.sin(2 * math.pi * f / 6)
        elif how == "fly" and kit.hangs:                  # on a thread: a slow sway, never an arc
            rot += math.radians(3.0) * math.sin(math.pi * through)
        elif how == "fly":                                # no wings: thrown, in an arc
            cy += 2.0 * math.sin(math.pi * through)
        elif entering and 0 <= f - entering < 6:          # arriving: squash, stretch, settle
            s = (0.94, 0.94, 1.03, 1.03, 1.0, 1.0)[f - entering]
            sx, sy = 1 / s ** 0.5, s
        for b in mine:                                    # a fall that lands: one bounce, squashed as it hits
            if b.do == "drop" and _target(b, 0, 0)[1] > -3 and 0 <= f - ends(b) < 8:
                d = f - ends(b)
                cy += 0.7 * math.sin(math.pi * d / 8)
                if d < 2:
                    sx, sy = sx * 1.08, sy * 0.86
        tf.append([round(x, 4), round(cy, 4), round(rot, 5), round(sx * (-1 if flip else 1) * sc, 4),
                   round(sy * sc, 4)])
    # What is drawn smaller is further off, so it is behind whatever is drawn bigger.
    return {"name": a.who, "pieces": pieces, "poses": poses, "scales": scales, "w_px": p.w, "h_px": p.h,
            "upp": kit.upp, "z": round(0.1 * (3 - a.depth) + 0.01 * k - 0.25 * max(0.0, 1.0 - a.scale), 3), "tf": tf}
