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

from entertainment.cutout import BLENDER, FPS, at_seconds, kit as kitmod, lips
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
    # What is heard from out of shot, for whoever is on stage to start at: a line by somebody not seen, an effect.
    here = {a.who for a in lay.actors}
    lines = [(s, e) for _, s, e in spans]
    cues = [s for who, s, _ in spans if who not in here]
    cues += [at_seconds(e.at, lines, n / FPS) for e in scene.sfx]
    return plan(lay, kits, series_dir, n, speech, spans, plate, sizes, spots_of(series_dir, lay.place, plate),
                sorted(cues))


def spots_of(series_dir: Path, place: int, plate: Path | None = None) -> dict[str, tuple[float, float, float]]:
    """The place's named points (places/spots.json: {"3": {"sill": [x, y, scale]}} in the plate's pixels), in
    stage units from the plate's bottom middle (it is PLATE_W wide), each with how big a puppet is drawn there
    (the sill is across the road: Gully at full size on it was as tall as the shop front); {} for a place
    with none."""
    from entertainment.cutout.layout import PLATE_W

    path = series_dir / "places" / "spots.json"
    if not path.exists():
        return {}
    named = json.loads(path.read_text(encoding="utf-8")).get(str(place), {})
    if not named or plate is None:
        return {k: (0.0, 0.0, float(v[2]) if len(v) > 2 else 1.0) for k, v in named.items()}
    import pygame

    w, h = pygame.image.load(str(plate)).get_size()
    u = PLATE_W / w
    return {k: (round((v[0] - w / 2) * u, 3), round((h - v[1]) * u, 3), float(v[2]) if len(v) > 2 else 1.0)
            for k, v in named.items()}


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


LOOKS = 5                                      # frames of a shot the picture check is shown, at most


def moments(lay: Layout, n: int, spans: list[tuple[str, float, float]]) -> list[tuple[int, str]]:
    """The frames of a shot worth looking at, each with what has just happened: its first, its last, and one
    just after each thing that happens in it has landed (an entrance, a beat, a prop taken or let go). Frame 1
    alone showed nobody who walks in, and no pose a beat puts on."""
    from entertainment.cutout.layout import ENTER_S, FALL_F, TAKE_F, when

    seen = []
    for a in lay.actors:
        if a.enter != "none":
            seen.append((round(ENTER_S * FPS) + 3, f"{a.who} has come in"))
        if a.on and a.on_at not in ("", "0"):
            seen.append((when(a.on_at, n, spans) + TAKE_F + 2, f"{a.on.partition('.')[0]} has taken the {a.who}"))
        if a.off_at:
            seen.append((when(a.off_at, n, spans) + FALL_F + 8, f"the {a.who} has been let go"))
    for b in lay.beats:
        if b.do == "exit":
            continue
        if b.do in ("walk", "fly"):                    # where it has got to
            after = when(b.until, n, spans) + 2 if b.until else when(b.at, n, spans) + round(1.3 * FPS)
        else:
            after = when(b.at, n, spans) + (FALL_F + 8 if b.do == "drop" else 10)
        seen.append((after, f"after {b.who}'s {b.do}" + (f" ({b.value})" if b.do in ("pose", "face") else "")))
    mid, last = [], 1
    for f, what in sorted((max(1, min(n, f)), w) for f, w in seen):
        if f - last >= 8 and n - f >= 8:               # not the same moment as the one before, or as the end
            mid.append((f, what))
            last = f
    if len(mid) > LOOKS - 2:                           # spread through the shot
        mid = [mid[round(k * (len(mid) - 1) / (LOOKS - 3))] for k in range(LOOKS - 2)]
    return [(1, "the shot's first frame")] + mid + ([(n, "the shot's last frame")] if n > 1 else [])


def looks(folder: Path, only: tuple[int, ...] = ()) -> dict[int, list[tuple[str, Path]]]:
    """A few frames of every laid-out shot (`moments`), for the picture check: look/sceneNN.fFFFF.jpg, each
    with its caption. They are the check's own: the start stills the user approves are left alone."""
    folder = folder.resolve()
    out_dir = folder / "look"
    out_dir.mkdir(exist_ok=True)
    shots, out = [], {}
    for i in laid_out(folder):
        if only and i not in only:
            continue
        for old in out_dir.glob(f"scene{i:02d}.f*.jpg"):
            old.unlink()
        p = shot_plan(folder, i)
        n = p["frames"]
        spans = lips.faces(folder, i)[2] if (folder / f"scene{i:02d}.dialogue.wav").exists() else []
        out[i] = []
        for f, what in moments(layout_of(folder, i), n, spans):
            path = out_dir / f"scene{i:02d}.f{f:04d}.jpg"
            shots.append({"plan": p, "out": str(path), "still": True, "frame": f})
            out[i].append((f"Shot {i}, at {(f - 1) / FPS:.1f} of {n / FPS:.1f} seconds ({what}):", path))
    if shots:
        play(shots, out_dir / "blender.log")
    return out


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
