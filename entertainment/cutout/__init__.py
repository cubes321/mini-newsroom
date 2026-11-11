"""Cartoons as paper cut-out animation, rendered in Blender: the user's pick on 2026-11-08 ("that style of
animation is more forgiving"), after probes of the Chip Lift's shots 4 and 16-17 beside H3's takes.

Three layers, with a hard line at Blender:
- kit.py: each character's puppet, a kit of paper pieces (a pose with a face, pose_face.png) cut from the
  approved design and from variants Qwen-Image-Edit draws of it, aligned pixel for pixel. Each piece has an
  off-white cut edge, a lifted shadow and paper grain. The user approves a kit on its sheet.
- layout.py: a shot's Layout (who stands where, facing which way, the beats they play, the camera, the rope)
  and the planner that turns it, with the lines' timing from lips.py, into a plan for every frame. Pure
  Python, tested without Blender.
- blender_play.py: run inside Blender (`blender -b -P`), imports nothing of ours; it places the cards a plan
  names, frame by frame, and renders. One Blender process takes every shot of a batch (its start-up is most
  of the time).

The puppets move on twos (each pose held two frames), the cut-out stutter; the camera is a flat rostrum that
moves smoothly, with the plate behind at half its speed.
"""
from __future__ import annotations

import os
import re
from pathlib import Path

BLENDER = Path(os.environ.get("BLENDER", "C:/Program Files/Blender Foundation/Blender 5.3/blender.exe"))
FPS = 24


def at_seconds(ref: str, spans: list[tuple[float, float]], total: float) -> float:
    """A time in a shot: seconds, or start / end / line / line_end / lineN / lineN_end, +/- seconds."""
    ref = ref.replace(" ", "").lower() or "0"
    base, off = ref, 0.0
    m = re.match(r"^([a-z_0-9]+?)([+-][0-9.]+)?$", ref)
    if m and not re.fullmatch(r"[0-9.]+", m.group(1)):
        base, off = m.group(1), float(m.group(2) or 0)
    else:
        try:
            return max(0.0, min(total, float(ref)))
        except ValueError:
            return 0.5
    k = re.fullmatch(r"line(\d*)(_end)?", base)
    if k and spans:
        s = spans[min(len(spans), int(k.group(1) or (len(spans) if k.group(2) else 1))) - 1]
        t = s[1] if k.group(2) else s[0]
    else:
        t = {"start": 0.0, "end": total}.get(base, 0.5)
    return max(0.0, min(total, t + off))
