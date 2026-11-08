"""The cut-out engine (entertainment/cutout): a kit's pieces, the lines' faces, a layout's plan. Pure Python;
one Blender smoke test plays a still when Blender is installed."""
from __future__ import annotations

import json
import os
import subprocess

import numpy as np
import pytest
import soundfile as sf

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")

from entertainment.cutout import BLENDER, FPS, kit as kitmod, layout as lay, lips  # noqa: E402

CREAM = (248, 233, 214)


def _design(h=64, w=48):
    """A figure: a black-outlined white body on cream, with a cream hole inside it and a beak box."""
    img = np.full((h, w, 3), CREAM, np.float32)
    img[8:56, 10:38] = 0                                   # outline
    img[10:54, 12:36] = 250                                # body
    img[30:36, 20:28] = CREAM                              # an enclosed gap
    return img


def _series(tmp_path):
    d = tmp_path / "gully" / "puppets" / "gull"
    base = _design()
    kitmod.save_rgb(base, d / "base.png")
    talk = base.copy()
    talk[14:20, 14:22] = (200, 0, 0)                       # the beak opens (red), inside its region
    talk[40:44, 14:30] = (0, 200, 0)                       # and Qwen changed the chest too: outside the region
    kitmod.save_rgb(talk, d / "variants" / "talk.png")
    (d / "kit.json").write_text(json.dumps({
        "who": "gull", "design": "refs/gull.png", "natural": "left", "height": 10.0, "feet_y": 56,
        "anchors": {"head": [24, 16], "ankle": [30, 54]}, "regions": {"beak": [[12, 12, 24, 22]]},
        "variants": {"talk": {"prompt": "open the beak"}}, "faces": {"talk": {"variant": "talk", "region": "beak"}},
        "loud": "talk"}), encoding="utf-8")
    return tmp_path / "gully", d


def test_a_kit_is_cut_out_on_paper_and_a_face_changes_only_its_region(tmp_path):
    series_dir, d = _series(tmp_path)
    pieces = kitmod.build(series_dir, "gull")
    assert sorted(p.name for p in pieces) == ["normal_closed.png", "normal_talk.png"] and (d / "sheet.png").exists()
    import pygame

    def rgba(p):
        s = pygame.image.load(str(p))
        return np.dstack([pygame.surfarray.array3d(s).swapaxes(0, 1), pygame.surfarray.array_alpha(s).T])

    closed, talk = rgba(d / "pieces" / "normal_closed.png"), rgba(d / "pieces" / "normal_talk.png")
    P = kitmod.PAD
    assert closed.shape[:2] == (64 + 2 * P, 48 + 2 * P)                 # padded for the edge and the shadow
    assert closed[2, 2, 3] == 0                                         # the cream is gone
    assert closed[P + 33, P + 24, 3] == 255 and closed[P + 33, P + 24, :3].mean() > 220    # the gap: uncut paper
    assert closed[P + 30, P + 6, 3] > 200 and closed[P + 30, P + 6, :3].mean() > 220       # the paper's cut edge
    assert closed[P + 30 + 15, P + 38 + 14, 3] > 0                      # its shadow, down and to the right
    assert talk[P + 16, P + 17, 0] > 150 and talk[P + 16, P + 17, 1] < 80                  # the beak opened
    assert np.abs(talk[P + 42, P + 20, :3].astype(int) - closed[P + 42, P + 20, :3]).max() < 20   # the chest didn't
    k = kitmod.load(series_dir, "gull")
    assert k.piece(series_dir, "normal", "squawk").name == "normal_talk.png"            # no squawk: talks
    assert k.piece(series_dir, "normal", "down").name == "normal_closed.png"
    assert abs(k.upp - 10.0 / 64) < 1e-9


def test_a_lines_faces_follow_its_loudness_in_the_track(tmp_path):
    folder = tmp_path / "ep"
    (folder / "scene03" / "lines").mkdir(parents=True)
    sr = 44100
    t = np.arange(int(0.6 * sr)) / sr
    word = 0.3 * np.sin(2 * np.pi * 220 * t) * np.r_[np.full(len(t) // 2, 0.3), np.ones(len(t) - len(t) // 2)]
    sf.write(folder / "scene03" / "lines" / "01_gull.wav", word.astype(np.float32), sr)
    track = np.zeros(int(2.0 * sr), np.float32)
    track[int(0.5 * sr): int(0.5 * sr) + len(word)] += word
    track += 0.002 * np.random.default_rng(1).normal(size=len(track)).astype(np.float32)   # the bed, quiet
    sf.write(folder / "scene03.dialogue.wav", np.stack([track, track], 1), sr)
    n, speech, spans = lips.faces(folder, 3)
    assert n == 48 and spans[0][0] == "gull" and abs(spans[0][1] - 0.5) < 0.01 and abs(spans[0][2] - 1.1) < 0.01
    f = speech["gull"]
    assert set(f[:11]) == {"closed"} and set(f[28:]) == {"closed"}
    assert "talk" in f[12:18] and "loud" in f[19:26]                      # quiet first half, loud second


def test_a_layout_plans_every_frame_on_twos_with_its_beats_and_its_rope(tmp_path):
    series_dir, d = _series(tmp_path)
    kitmod.build(series_dir, "gull")
    k = kitmod.load(series_dir, "gull")
    w, h = 48 + 2 * kitmod.PAD, 64 + 2 * kitmod.PAD
    assert lay.when("line+0.5", 48, [("gull", 0.5, 1.1)]) == round(1.0 * FPS) + 1
    assert lay.when("end-0.25", 48, []) == 43 and lay.when("0", 48, []) == 1 and lay.when("9", 48, []) == 48
    layout = lay.Layout.model_validate({
        "place": 1,
        "actors": [{"who": "gull", "x": 3.0, "facing": "right", "enter": "left"}],
        "beats": [{"who": "gull", "do": "face", "value": "talk", "at": "1.5", "until": "1.7"}],
        "ropes": [{"attach": "gull.ankle", "path": [[0, 0.2], [-9, 0.1]]}],
        "camera": {"start": {"size": "wide"}, "end": {"size": "close", "on": "gull"}, "move_at": "1.0",
                   "move_until": "end"}})
    speech = {"gull": ["closed"] * 12 + ["talk"] * 6 + ["loud"] * 4 + ["closed"] * 26}
    p = lay.plan(layout, {"gull": k}, series_dir, 48, speech, [("gull", 0.5, 0.9)], d / "base.png",
                 {"gull": (w, h)})
    c = p["cards"][0]
    assert len(c["pieces"]) == len(c["tf"]) == len(p["camera"]) == 48
    names = [os.path.basename(x) for x in c["pieces"]]
    assert names[13] == "normal_talk.png" and names[19] == "normal_talk.png"     # loud: this kit just talks
    assert names[36] == "normal_talk.png" and names[42] == "normal_closed.png"   # the face beat, then not
    assert all(c["tf"][f] == c["tf"][f - 1] for f in range(1, 48, 2))           # on twos
    assert c["tf"][0][0] < -12 and c["tf"][24][0] == 3.0                        # waddled in from off the left
    assert c["tf"][30][3] < 0                                                   # facing right: mirrored
    assert p["camera"][0] == p["camera"][20] and p["camera"][47][2] == 8.0      # holds, then closes in
    feet = c["tf"][30][1] + (h - (56 + kitmod.PAD)) * k.upp
    assert abs(feet - 0.0) < 0.02                                               # the feet on the ground
    loop = p["ropes"][0]["loop"]
    assert loop[0] < 3.0                                                        # the ankle, mirrored to the left
    assert p["ropes"][0]["points"][1] == [0, 0.2]


def test_a_walk_alternates_its_strides_and_a_flight_faces_the_way_it_goes(tmp_path):
    series_dir, d = _series(tmp_path)
    for v, shift in (("step1", 0), ("step2", 2), ("fly", 4)):
        img = np.full((64, 48, 3), CREAM, np.float32)
        img[20 + shift:50 + shift, 6:40] = 0
        img[22 + shift:48 + shift, 8:38] = 250
        kitmod.save_rgb(img, d / "variants" / f"{v}.png")
    k = json.loads((d / "kit.json").read_text(encoding="utf-8"))
    for v in ("step1", "step2", "fly"):
        k["variants"][v] = {"prompt": v, "new_pose": True}
        k.setdefault("poses", {"normal": None})[v] = v
    k.update({"walk": ["step1", "step2"], "fly": "fly", "facing": {"step1": "right", "step2": "right"}})
    (d / "kit.json").write_text(json.dumps(k), encoding="utf-8")
    kitmod.build(series_dir, "gull")
    kit = kitmod.load(series_dir, "gull")
    assert kit.feet_of(series_dir, "step1") == 49 and kit.feet_of(series_dir, "step2") == 51   # each drawing's own
    assert not (d / "pieces" / "step1_talk.png").exists() and kit.piece(series_dir, "step1", "talk").name == "step1_closed.png"
    layout = lay.Layout.model_validate({
        "place": 1, "actors": [{"who": "gull", "x": 0.0}],
        "beats": [{"who": "gull", "do": "walk", "value": "-6", "at": "0", "until": "1"},
                  {"who": "gull", "do": "fly", "value": "4,5", "at": "1", "until": "2"}]})
    w, h = 48 + 2 * kitmod.PAD, 64 + 2 * kitmod.PAD
    p = lay.plan(layout, {"gull": kit}, series_dir, 60, {}, [], d / "base.png", {"gull": (w, h)})
    c = p["cards"][0]
    names = [os.path.basename(x) for x in c["pieces"]]
    assert {names[1], names[5]} == {"step1_closed.png", "step2_closed.png"}     # two strides, four frames each
    assert c["tf"][10][3] < 0                                                 # walking left: the right-facing drawing mirrored
    assert names[30] == "fly_closed.png" and c["tf"][34][3] < 0              # flying right, the left-facing gull mirrored
    assert c["tf"][24][0] < -5.5 and names[58] == "normal_closed.png" and c["tf"][58][0] == 4.0


def test_the_writers_stage_becomes_a_layout_and_its_slips_are_mended(tmp_path, caplog):
    import logging

    from entertainment.cutout import writer

    series_dir, d = _series(tmp_path)
    kitmod.build(series_dir, "gull")
    k = kitmod.load(series_dir, "gull")
    st = writer.Stage.model_validate({
        "actors": [{"who": "Gull", "mark": "far_left", "height": "raised", "facing": "right", "pose": "asleep",
                    "holds": "bucket"},
                   {"who": "bucket", "mark": "centre"},
                   {"who": "kraken", "mark": "right"},
                   {"who": "gull", "mark": "centre"}],
        "beats": [{"who": "gull", "do": "fly", "to": "right", "height": "air", "at": "line"},
                  {"who": "gull", "do": "walk", "to": "off_left", "at": "2"},
                  {"who": "gull", "do": "spin", "value": "180 degrees", "at": "1"},
                  {"who": "kraken", "do": "hop"}],
        "rope": {"attach": "gull.ankle", "to": "somewhere"},
        "camera": {"size": "close", "on": "gull", "move": "tilt_up"}})
    with caplog.at_level(logging.WARNING):
        lay_ = writer.stage(st, 3, {"gull": k, "bucket": k}, {"bucket"})
    assert "kraken" in caplog.text and "somewhere" in caplog.text
    gull, bucket = lay_.actors[0], lay_.actors[-1]
    assert (gull.x, gull.y, gull.facing, gull.pose) == (-11.0, 3.0, "right", "normal")     # no "asleep": normal
    assert bucket.on == "gull.hold" and [a.who for a in lay_.actors] == ["gull", "bucket"]  # once each, held
    assert [(b.do, b.value) for b in lay_.beats] == [("fly", "6.0,7.0"), ("walk", "-24.0"), ("spin", "180")]
    assert lay_.ropes[0].attach == "gull.ankle" and lay_.ropes[0].path[-1][0] == 0.0    # unknown mark: centre
    assert lay_.camera.start.on == "gull.feet" and lay_.camera.end.on == "gull.head" and lay_.place == 3


def test_the_newest_video_is_the_scenes_whichever_engine_made_it(monkeypatch, tmp_path):
    from entertainment import cartoons

    d = tmp_path / "ep" / "scene01"
    d.mkdir(parents=True)
    (d / "gully_ep_scene01_00002_.mp4").write_bytes(b"h3")
    (d / "cutout.mp4").write_bytes(b"cut")
    os.utime(d / "gully_ep_scene01_00002_.mp4", (1000, 1000))
    assert cartoons._rendered(tmp_path / "ep", 1).name == "cutout.mp4"       # by name it would be H3's


@pytest.mark.skipif(not BLENDER.exists(), reason="Blender is not installed")
def test_blender_plays_a_plan_as_a_still(tmp_path):
    series_dir, d = _series(tmp_path)
    kitmod.build(series_dir, "gull")
    plate = tmp_path / "plate.png"
    kitmod.save_rgb(np.full((90, 160, 3), (40, 90, 200), np.float32), plate)
    layout = lay.Layout.model_validate({"place": 1, "actors": [{"who": "gull", "x": 0.0}],
                                        "camera": {"start": {"size": "medium", "on": "gull"}}})
    k = kitmod.load(series_dir, "gull")
    p = lay.plan(layout, {"gull": k}, series_dir, 2, {}, [], plate, {"gull": (48 + 2 * kitmod.PAD, 64 + 2 * kitmod.PAD)})
    batch = tmp_path / "batch.json"
    out = tmp_path / "still.png"
    batch.write_text(json.dumps({"shots": [{"plan": p, "out": str(out), "still": True}]}), encoding="utf-8")
    from entertainment.cutout.engine import PLAYER

    r = subprocess.run([str(BLENDER), "-b", "--factory-startup", "--python-exit-code", "1", "-P", str(PLAYER), "--",
                        str(batch)], capture_output=True, text=True, timeout=300)
    assert r.returncode == 0, r.stdout[-2000:]
    import pygame

    s = pygame.surfarray.array3d(pygame.image.load(str(out))).swapaxes(0, 1)
    assert s.shape == (640, 1152, 3)
    assert tuple(s[5, 5]) == (40, 90, 200) or abs(int(s[5, 5][2]) - 200) < 30      # the plate behind
    assert (s[300:340, 560:600].mean(axis=(0, 1)) > 200).all()                     # the gull's white body
