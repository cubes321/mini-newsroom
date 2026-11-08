"""The cut-out engine behind `stills` and `render` (CARTOON_ENGINE=cutout or --engine cutout).

A shot is cut out when it has a layout (sceneNN.layout.json). `stills` plays frame 1 of every laid-out shot as
its start still (sceneNN.start.png), so the user approves layouts on the same sheet and draft as before;
`render` plays every frame of each shot whose video is missing or older than its layout, its track or its
kits' pieces, into sceneNN/cutout.mp4 (silent: assemble lays our track under it, as for H3). One Blender
process takes the whole batch.
"""
from __future__ import annotations

import json
import logging
import shutil
import subprocess
from pathlib import Path

from entertainment.cutout import BLENDER, FPS, kit as kitmod, lips
from entertainment.cutout.layout import Layout, plan

log = logging.getLogger(__name__)
PLAYER = Path(__file__).with_name("blender_play.py")


def layout_of(folder: Path, i: int) -> Layout | None:
    path = folder / f"scene{i:02d}.layout.json"
    return Layout.model_validate_json(path.read_text(encoding="utf-8")) if path.exists() else None


def shot_plan(folder: Path, i: int) -> dict:
    from entertainment import cartoons

    series = cartoons.SERIES[folder.parent.name]
    series_dir = folder.parent
    ep = cartoons.Episode.model_validate_json((folder / "episode.json").read_text(encoding="utf-8"))
    scene = ep.scenes[i - 1]
    lay = layout_of(folder, i)
    if not (folder / f"scene{i:02d}.dialogue.wav").exists():
        cartoons.record(series, scene, folder, i, cartoons._start(ep, i, folder))
    if (folder / f"scene{i:02d}.dialogue.wav").exists():
        n, speech, spans = lips.faces(folder, i)
    else:
        n, speech, spans = cartoons.frames(scene.seconds), {}, []
    kits = {a.who: kitmod.load(series_dir, a.who) for a in lay.actors}
    sizes = {}
    import pygame

    for who, k in kits.items():
        sizes[who] = pygame.image.load(str(k.piece(series_dir, "normal", "closed"))).get_size()
    plate = kitmod.plate(series_dir, lay.place)
    return plan(lay, kits, series_dir, n, speech, spans, plate, sizes, spots_of(series_dir, lay.place, plate))


def spots_of(series_dir: Path, place: int, plate: Path | None = None) -> dict[str, tuple[float, float]]:
    """The place's named points (places/spots.json: {"3": {"sill": [x, y]}} in the plate's pixels), in stage
    units from the plate's bottom middle (it is PLATE_W wide); {} for a place with none."""
    from entertainment.cutout.layout import PLATE_W

    path = series_dir / "places" / "spots.json"
    if not path.exists():
        return {}
    named = json.loads(path.read_text(encoding="utf-8")).get(str(place), {})
    if not named or plate is None:
        return {k: (0.0, 0.0) for k in named}
    import pygame

    w, h = pygame.image.load(str(plate)).get_size()
    u = PLATE_W / w
    return {k: (round((x - w / 2) * u, 3), round((h - y) * u, 3)) for k, (x, y) in named.items()}


def play(shots: list[dict], log_to: Path) -> None:
    """One Blender process for the batch."""
    batch = log_to.with_suffix(".json")
    batch.write_text(json.dumps({"shots": shots}), encoding="utf-8")
    with log_to.open("w", encoding="utf-8") as fh:
        r = subprocess.run([str(BLENDER), "-b", "--factory-startup", "--python-exit-code", "1", "-P", str(PLAYER),
                            "--", str(batch)], stdout=fh, stderr=subprocess.STDOUT)
    if r.returncode:
        raise RuntimeError(f"Blender failed (exit {r.returncode}); see {log_to}")


def laid_out(folder: Path) -> list[int]:
    return sorted(int(p.name[5:7]) for p in folder.glob("scene[0-9][0-9].layout.json"))


def stills(folder: Path) -> list[Path]:
    """Frame 1 of every laid-out shot, as its start still. A still drawn another way (Qwen's, for H3) is kept
    as a take (sceneNN.start.K.png) the first time a cut-out one replaces it."""
    folder = folder.resolve()
    shots = []
    for i in laid_out(folder):
        still, mark = folder / f"scene{i:02d}.start.png", folder / f"scene{i:02d}.start.cutout"
        if still.exists() and not mark.exists():
            still.rename(folder / f"scene{i:02d}.start.{len(list(folder.glob(f'scene{i:02d}.start.*.png'))) + 1}.png")
        mark.touch()
        shots.append({"plan": shot_plan(folder, i), "out": str(still), "still": True})
    if shots:
        play(shots, folder / "cutout_stills.log")
    return [Path(s["out"]) for s in shots]


def _stale(folder: Path, i: int, video: Path) -> bool:
    if not video.exists():
        return True
    lay = layout_of(folder, i)
    newer = [folder / f"scene{i:02d}.layout.json", folder / f"scene{i:02d}.dialogue.wav"]
    for a in lay.actors:
        newer += list((folder.parent / "puppets" / a.who / "pieces").glob("*.png"))[:1]
    return any(p.exists() and p.stat().st_mtime > video.stat().st_mtime for p in newer)


def render(folder: Path) -> list[Path]:
    """Every laid-out shot whose video is missing or stale, in one Blender run, then each encoded."""
    folder = folder.resolve()
    todo = [i for i in laid_out(folder) if _stale(folder, i, folder / f"scene{i:02d}" / "cutout.mp4")]
    shots = []
    for i in todo:
        frames = folder / f"scene{i:02d}" / "cutout_frames"
        shutil.rmtree(frames, ignore_errors=True)
        frames.mkdir(parents=True)
        shots.append({"plan": shot_plan(folder, i), "out": str(frames), "still": False})
    if shots:
        log.info("cutout: playing %d shots in Blender", len(shots))
        play(shots, folder / "cutout_render.log")
    out = []
    for i in todo:
        d = folder / f"scene{i:02d}"
        video = d / "cutout.mp4"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-framerate", str(FPS), "-i",
                        str(d / "cutout_frames" / "f_%04d.png"), "-c:v", "libx264", "-pix_fmt", "yuv420p", "-crf",
                        "16", str(video)], check=True)
        shutil.rmtree(d / "cutout_frames", ignore_errors=True)
        out.append(video)
        log.info("cutout: shot %d rendered", i)
    return out
