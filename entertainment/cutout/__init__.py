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
from pathlib import Path

BLENDER = Path(os.environ.get("BLENDER", "C:/Program Files/Blender Foundation/Blender 5.2/blender.exe"))
FPS = 24
