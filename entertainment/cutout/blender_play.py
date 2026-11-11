"""Plays cut-out plans in Blender: run as `blender -b -P blender_play.py -- <batch.json>`.

Runs inside Blender's own Python, so it imports nothing of the project (no pydantic, no numpy needed): the plan
(layout.plan, as JSON) already holds every frame. A batch is {"shots": [{"plan": {...}, "out": path,
"still": bool}]}: a still renders frame 1 (or the shot's "frame") to `out` (a .png or .jpg); otherwise every
frame goes to `out`/f_####.png.

Everything is an unlit card or strip (an emission shader, the Standard view transform: the colours are the
pictures' own). Cards blend (alpha: the paper's edge and shadow) and sort by their depth; the rope is solid,
so it sorts by depth too, not by its origin (two blended strips at one origin drew in the wrong order).
"""
import json
import math
import os
import shutil
import sys
from pathlib import Path

import bpy

batch = json.loads(Path(sys.argv[sys.argv.index("--") + 1]).read_text(encoding="utf-8"))


def scene_for(plan):
    bpy.ops.wm.read_factory_settings(use_empty=True)
    sc = bpy.context.scene
    for eng in ("BLENDER_EEVEE", "BLENDER_EEVEE_NEXT"):
        try:
            sc.render.engine = eng
            break
        except TypeError:
            pass
    sc.render.resolution_x, sc.render.resolution_y = 1152, 640
    sc.render.fps = plan["fps"]
    sc.frame_start, sc.frame_end = 1, plan["frames"]
    sc.view_settings.view_transform = "Standard"
    sc.render.image_settings.file_format = "PNG"
    sc.world = bpy.data.worlds.new("w")
    bpy.context.preferences.edit.keyframe_new_interpolation_type = "CONSTANT"
    return sc


def material(name, image=None, color=None, seq=0):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    emit = nt.nodes.new("ShaderNodeEmission")
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    if image is None:
        try:
            mat.surface_render_method = "DITHERED"
        except AttributeError:
            mat.blend_method = "OPAQUE"
        emit.inputs["Color"].default_value = (*color, 1.0)
        nt.links.new(emit.outputs[0], out.inputs["Surface"])
        return mat
    try:
        mat.surface_render_method = "BLENDED"
    except AttributeError:
        mat.blend_method = "BLEND"
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = image
    tex.interpolation = "Cubic"
    if seq:
        image.source = "SEQUENCE"
        tex.image_user.frame_duration = seq
        tex.image_user.frame_start = 1
        tex.image_user.use_auto_refresh = True
    clear = nt.nodes.new("ShaderNodeBsdfTransparent")
    mix = nt.nodes.new("ShaderNodeMixShader")
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    nt.links.new(tex.outputs["Alpha"], mix.inputs["Fac"])
    nt.links.new(clear.outputs[0], mix.inputs[1])
    nt.links.new(emit.outputs[0], mix.inputs[2])
    nt.links.new(mix.outputs[0], out.inputs["Surface"])
    return mat


def card(name, image_path, width, height, z, seq=0):
    """A card `width` x `height` units, its origin at its bottom middle."""
    img = bpy.data.images.load(str(image_path))
    bpy.ops.mesh.primitive_plane_add(size=1)
    ob = bpy.context.object
    ob.name = name
    for v in ob.data.vertices:
        v.co.x *= width
        v.co.y = (v.co.y + 0.5) * height
    ob.location.z = z
    ob.data.materials.append(material(name, image=img, seq=seq))
    return ob


def strip(name, points, z, width, color):
    cu = bpy.data.curves.new(name, "CURVE")
    cu.dimensions = "3D"
    cu.bevel_depth = width / 2
    cu.bevel_resolution = 0
    cu.use_fill_caps = True
    sp = cu.splines.new("POLY")
    sp.points.add(len(points) - 1)
    for p, (x, y) in zip(sp.points, points):
        p.co = (x, y, z, 1.0)
    ob = bpy.data.objects.new(name, cu)
    ob.data.materials.append(material(name, color=color))
    bpy.context.scene.collection.objects.link(ob)
    return ob


def rope(k, r, frames):
    """A strip of the rope's colour over a wider black one, lifted clear of it (they are round tubes). Tied to
    someone (`at`: that point, every frame), its loop goes with them, and so does a rope that hangs from above;
    one that lies along the ground keeps its far end and only its tied end follows."""
    at = r.get("at")
    runs = [(r["points"], False)]
    if r["loop"]:
        x, y, rx, ry = r["loop"]
        runs.append(([(x + rx * math.cos(a), y + ry * math.sin(a)) for a in (i * math.pi / 12 for i in range(25))], True))
    for j, (pts, loop) in enumerate(runs):
        z = 0.45 if loop else -0.6                    # the loop in front of the leg, the run behind everyone
        obs = [strip(f"rope{k}_{j}_edge", pts, z, r["width"] * 1.65, (0.01, 0.01, 0.02)),
               strip(f"rope{k}_{j}", pts, z + 0.2, r["width"], tuple(r["color"]))]
        if not at:
            continue
        last = None
        for f in frames:
            dx, dy = at[f - 1][0] - at[0][0], at[f - 1][1] - at[0][1]
            if (dx, dy) == last:
                continue
            last = (dx, dy)
            for ob in obs:
                if loop or r.get("up"):
                    ob.location = (dx, dy, 0.0)
                    ob.keyframe_insert("location", frame=f)
                else:
                    end = ob.data.splines[0].points[0]
                    end.co = (pts[0][0] + dx, pts[0][1] + dy, end.co[2], 1.0)
                    end.keyframe_insert("co", frame=f)


def sequence(folder, name, pieces):
    """The card's per-frame pieces as a numbered image sequence (hard links where the disk allows)."""
    d = Path(folder) / f"seq_{name}"
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    for f, src in enumerate(pieces, start=1):
        dst = d / f"{name}_{f:04d}.png"
        try:
            os.link(src, dst)
        except OSError:
            shutil.copy2(src, dst)
    return d / f"{name}_0001.png"


def build(plan, out, still, frame=1):
    sc = scene_for(plan)
    n = plan["frames"]
    frame = max(1, min(n, frame))
    work = Path(out).parent if still else Path(out)
    pl = plan["plate"]
    img = bpy.data.images.load(pl["path"])
    plate = card("plate", pl["path"], pl["width"], pl["width"] * img.size[1] / img.size[0], -5.0)
    cam_data = bpy.data.cameras.new("cam")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("cam", cam_data)
    sc.collection.objects.link(cam)
    sc.camera = cam
    cards = []
    for c in plan["cards"]:
        first = c["pieces"][frame - 1] if still else sequence(work, c["name"], c["pieces"])
        ob = card(c["name"], first, c["w_px"] * c["upp"], c["h_px"] * c["upp"], c["z"], seq=0 if still else n)
        cards.append((ob, c))
    frames = [frame] if still else range(1, n + 1)
    for k, r in enumerate(plan["ropes"]):
        rope(k, r, frames)
    for f in frames:
        x, y, w = plan["camera"][f - 1]
        cam.location = (x, y, 20.0)
        cam.keyframe_insert("location", frame=f)
        cam_data.ortho_scale = w
        cam_data.keyframe_insert("ortho_scale", frame=f)
        px, py = plan["plate"]["at"][f - 1]
        plate.location = (px, py, -5.0)
        plate.keyframe_insert("location", frame=f)
        for ob, c in cards:
            x, y, rot, sx, sy = c["tf"][f - 1]
            ob.location = (x, y, c["z"])
            ob.rotation_euler = (0.0, 0.0, rot)
            ob.scale = (sx, sy, 1.0)
            for attr in ("location", "rotation_euler", "scale"):
                ob.keyframe_insert(attr, frame=f)
    if still:
        sc.frame_set(frame)
        if str(out).lower().endswith(".jpg"):
            sc.render.image_settings.file_format = "JPEG"
            sc.render.image_settings.quality = 88
        sc.render.filepath = str(out)
        bpy.ops.render.render(write_still=True)
    else:
        sc.render.filepath = str(Path(out) / "f_")
        bpy.ops.render.render(animation=True)


for shot in batch["shots"]:
    build(shot["plan"], shot["out"], shot.get("still", False), shot.get("frame", 1))
    print("cutout: played", shot["out"], flush=True)
