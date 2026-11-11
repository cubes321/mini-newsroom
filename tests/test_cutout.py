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


def test_only_a_prop_has_its_big_holes_cut_out():
    img = np.full((100, 100, 3), CREAM, np.float32)
    img[10:90, 10:90] = 0                                  # a ring, like a bucket's handle
    img[14:86, 14:86] = CREAM                              # its big middle is the background's own cream
    img[14:86, 14:86, 2] += 6                              # (as a character's near-cream white could be)
    _, kept = kitmod.cut(img, np.array(CREAM, np.float32))
    _, holed = kitmod.cut(img, np.array(CREAM, np.float32), cut_holes=True)
    assert kept[50, 50] == 1.0 and holed[50, 50] == 0.0 and holed[12, 50] == 1.0


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
    assert p["camera"][0] == p["camera"][20] and 8.0 <= p["camera"][47][2] < 8.5   # holds, then closes in
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
    assert "kraken" in caplog.text
    gull, bucket = lay_.actors[0], lay_.actors[-1]
    assert (gull.x, gull.y, gull.facing, gull.pose) == (-11.0, 12.0, "right", "normal")    # no "asleep"; hung (spin)
    assert bucket.on == "gull.hold" and [a.who for a in lay_.actors] == ["gull", "bucket"]  # once each, held
    assert [(b.do, b.value) for b in lay_.beats] == [("fly", "6.0,12.0"), ("walk", "-24.0"), ("spin", "180")]  # hung: swings at its height
    assert [(r.attach, r.up, r.path) for r in lay_.ropes] == [("gull.ankle", True, [])]   # hung: from a rope, upwards
    cam = lay_.camera                                    # hung: the whole of him and his rope, held
    assert (cam.start.size, cam.start.on, cam.start.zoom, cam.end) == ("medium", "gull", 0.8, None) and lay_.place == 3


def test_raised_is_a_spot_or_the_ground_and_a_row_stands_clear(tmp_path, caplog):
    from entertainment.cutout import writer

    series_dir, d = _series(tmp_path)
    kitmod.build(series_dir, "gull")
    k = kitmod.load(series_dir, "gull")
    assert abs(k.half - 14 * 10.0 / 64) < 0.1                                # the drawing's own width, not the card's
    st = writer.Stage.model_validate({
        "actors": [{"who": "gull", "mark": "left", "height": "raised"}, {"who": "bucket", "mark": "far_right", "height": "raised"},
                   {"who": "crate", "mark": "centre"}, {"who": "cat", "mark": "centre"}],
        "beats": [{"who": "crate", "do": "drop", "value": "off", "at": "1"},
                  {"who": "gull", "do": "fly", "to": "wall", "at": "2"}],
        "rope": {"attach": "gull.ankle", "to": "somewhere"},
        "camera": {"size": "close", "on": "gull.feet"}})
    kits = {w: k for w in ("gull", "bucket", "crate", "cat")}
    with caplog.at_level("WARNING"):
        lay_ = writer.stage(st, 1, kits, {"bucket", "crate"}, {"sill": (-4.0, 7.0), "wall": (1.0, 9.0)})
    by = {a.who: a for a in lay_.actors}
    assert by["gull"].spot == "sill" and (by["bucket"].spot, by["bucket"].y) == (None, 0.0)   # no spot in reach: the ground
    assert by["cat"].x - by["crate"].x >= 2 * k.half + writer.GAP - 0.01      # both were on centre
    assert [(b.do, b.value) for b in lay_.beats] == [("fly", "-28.0,0.0,1.0"), ("fly", "1.0,6.0,1.0")]   # flung off the ground; to the wall
    assert "somewhere" in caplog.text and lay_.ropes[0].path[-1][0] == 0.0 and not lay_.ropes[0].up
    assert (lay_.camera.start.size, lay_.camera.start.on) == ("medium", "gull")              # no close-up of feet


def test_a_far_spot_draws_small_a_walker_passes_behind_and_a_crash_makes_them_jump(tmp_path):
    from types import SimpleNamespace as NS

    from entertainment.cutout import writer

    series_dir, d = _series(tmp_path)
    kitmod.build(series_dir, "gull")
    k = kitmod.load(series_dir, "gull")
    w, h = 48 + 2 * kitmod.PAD, 64 + 2 * kitmod.PAD
    spots = {"sill": (-4.0, 7.0, 0.4)}
    st = writer.Stage.model_validate({
        "actors": [{"who": "gull", "mark": "left"}, {"who": "cat", "mark": "right"}, {"who": "dog", "mark": "far_left"}],
        "beats": [{"who": "gull", "do": "fly", "to": "sill", "at": "1", "until": "2"},
                  {"who": "dog", "do": "walk", "to": "far_right", "at": "0.2"}]})
    kits = {x: k for x in ("gull", "cat", "dog")}
    lay_ = writer.stage(st, 1, kits, set(), spots)
    assert [(b.do, b.value) for b in lay_.beats] == [("fly", "-4.0,4.0,0.4"), ("walk", "11.0,0.0,1.0")]
    assert [a.depth for a in lay_.actors] == [0, 0, 1]                        # the dog walks behind the other two
    p = lay.plan(lay_, kits, series_dir, 72, {}, [], d / "base.png", {x: (w, h) for x in kits}, spots, cues=[2.5])
    gull, cat, dog = (c["tf"] for c in p["cards"])
    assert gull[10][4] > 0.98 and abs(gull[60][4] - 0.4) < 0.01               # full size, then small on the sill
    assert abs(gull[60][1] + (h - (56 + kitmod.PAD)) * k.upp * 0.4 - 4.0) < 0.05   # its feet on it, at that size
    assert p["cards"][2]["z"] < p["cards"][1]["z"]
    still, jump = cat[56][1], max(t[1] for t in cat[60:68])
    assert jump - still > 0.2 and abs(cat[70][1] - still) < 0.02              # starts at the crash, settles
    shot = NS(action="Gully shoves the crate off the wall.", seen=["gull", "crate"], seconds=6.0)
    why = writer.problems(shot, st, {"crate", "bucket"}, {"gull", "cat", "dog"})
    assert len(why) == 1 and "crate" in why[0]
    st.beats.clear()
    assert any("nobody does anything" in x for x in writer.problems(shot, st, {"crate"}, {"gull"}))


def test_a_rope_follows_a_drop_bounces_and_no_neighbour_is_sliced(tmp_path):
    series_dir, d = _series(tmp_path)
    kj = json.loads((d / "kit.json").read_text(encoding="utf-8"))
    kj["pose_anchors"] = {"normal": {"hold": [40, 10]}}
    (d / "kit.json").write_text(json.dumps(kj), encoding="utf-8")
    kitmod.build(series_dir, "gull")
    k = kitmod.load(series_dir, "gull")
    assert k.anchor("hold") == (40, 10) and k.anchor("head") == (24, 16) and k.anchor("tail") is None
    w, h = 48 + 2 * kitmod.PAD, 64 + 2 * kitmod.PAD
    layout = lay.Layout.model_validate({
        "place": 1, "actors": [{"who": "gull", "x": 0.0}, {"who": "cat", "x": 4.5}, {"who": "crate", "x": -9.0, "y": 6.0}],
        "beats": [{"who": "gull", "do": "walk", "value": "-3", "at": "1", "until": "2"},
                  {"who": "crate", "do": "drop", "value": "0", "at": "0.5", "until": "1"}],
        "ropes": [{"attach": "gull.ankle", "path": [[-9, 0.1]]}, {"attach": "gull.ankle", "up": True}],
        "camera": {"start": {"size": "medium", "on": "gull"}}})
    kits = {x: k for x in ("gull", "cat", "crate")}
    p = lay.plan(layout, kits, series_dir, 72, {}, [], d / "base.png", {x: (w, h) for x in kits})
    along, up = p["ropes"]
    assert along["at"][0][0] - along["at"][60][0] == 3.0 and along["points"][-1] == [-9, 0.1] and not along["up"]
    assert up["up"] and up["points"][1][1] > 30 and "poses" not in p["cards"][0]
    crate = [t[1] + (h - (56 + kitmod.PAD)) * k.upp for t in p["cards"][2]["tf"]]
    assert abs(crate[0] - 6.0) < 0.02 and 0 < crate[18] < 6.0 and crate[28] > 0.3 and abs(crate[40]) < 0.02   # falls, bounces, rests
    x, y, width = p["camera"][0]
    assert width > 16.0 and x - width / 2 < -k.half and x + width / 2 > 4.5 + k.half     # the cat beside him, whole


def test_a_snatched_prop_waits_until_taken_and_the_camera_finds_a_hanging_puppet(tmp_path):
    from entertainment.cutout import writer

    series_dir, d = _series(tmp_path)
    kitmod.build(series_dir, "gull")
    k = kitmod.load(series_dir, "gull")
    w, h = 48 + 2 * kitmod.PAD, 64 + 2 * kitmod.PAD
    st = writer.Stage.model_validate({
        "actors": [{"who": "bucket", "mark": "right"}, {"who": "gull", "mark": "left"}],
        "beats": [{"who": "gull", "do": "take", "value": "bucket", "at": "1"}]})
    lay_ = writer.stage(st, 1, {"gull": k, "bucket": k}, {"bucket"})
    assert [(a.who, a.on, a.on_at) for a in lay_.actors] == [("gull", None, "0"), ("bucket", "gull.hold", "1")]
    p = lay.plan(lay_, {"gull": k, "bucket": k}, series_dir, 48, {}, [], d / "base.png", {"gull": (w, h), "bucket": (w, h)})
    bucket = p["cards"][1]["tf"]
    assert bucket[0][0] == 6.0 and bucket[30][0] != 6.0                     # on its mark, then in the beak
    assert bucket[22][0] == 6.0 and bucket[30][0] < bucket[26][0] < 6.0      # carried there over a few frames
    # Let go: by a spot it is set down there, and stays; with none it falls to the ground.
    put = lay_.model_copy(deep=True)
    put.actors[1].off_at = "1.5"
    for spots, y_end in (({"sill": (-7.0, 9.0)}, -3.0 + 9.0), (None, 0.0)):
        q = lay.plan(put, {"gull": k, "bucket": k}, series_dir, 72, {}, [], d / "base.png",
                     {"gull": (w, h), "bucket": (w, h)}, spots=spots)
        x, y = q["cards"][1]["tf"][70][:2]
        assert abs(y + (h - (56 + kitmod.PAD)) * k.upp - y_end) < 0.02 and (spots is None or x == -7.0)
    st.beats.append(writer.StageBeat(who="gull", do="drop", at="1.5"))
    dropped = writer.stage(st, 1, {"gull": k, "bucket": k}, {"bucket"})
    assert dropped.actors[1].off_at == "1.5" and [b.do for b in dropped.beats] == []   # he lets go; he doesn't fall
    hung = lay.Layout.model_validate({"place": 1, "actors": [{"who": "gull", "x": 0.0, "y": 12.0}],
                                      "beats": [{"who": "gull", "do": "spin", "value": "180", "at": "0"}],
                                      "camera": {"start": {"size": "medium", "on": "gull"}}})
    p = lay.plan(hung, {"gull": k}, series_dir, 48, {}, [], d / "base.png", {"gull": (w, h)})
    tf = p["cards"][0]["tf"][24]
    assert abs(abs(tf[2]) - 3.14159) < 0.01                                  # upside down by mid-shot
    assert p["camera"][0][1] < tf[1]                                          # the camera below his feet, on him


def test_times_are_read_against_the_lines_and_effects_land_on_the_track(monkeypatch, tmp_path):
    from entertainment import cartoons
    from entertainment.cutout import at_seconds

    spans = [(0.5, 1.0), (1.5, 2.2)]
    assert at_seconds("line2", spans, 4) == 1.5 and at_seconds("line1_end", spans, 4) == 1.0
    assert abs(at_seconds("line_end+0.2", spans, 4) - 2.4) < 1e-9 and at_seconds("end-0.5", spans, 4) == 3.5
    assert at_seconds("2", spans, 4) == 2.0 and at_seconds("bogus", spans, 4) == 0.5 and at_seconds("9", [], 4) == 4
    monkeypatch.setattr(cartoons, "ROOT", tmp_path)
    series = cartoons.SERIES["gully"]
    bang = np.zeros((4410, 2), np.float32)
    bang[:200] = 0.9
    series.sfx_path("a bucket clang").parent.mkdir(parents=True)
    sf.write(series.sfx_path("a bucket clang"), bang, 44100)
    scene = cartoons.Scene(place="nowhere", summary="Off screen.", shots=[{"at": 0, "action": "a"}], lines=[],
                           sounds="", seconds=3.0, sfx=[{"what": "a bucket clang", "at": "1.0"},
                                                        {"what": "a splash not made yet", "at": "2"}])
    folder = tmp_path / "gully" / "ep"
    folder.mkdir(parents=True)
    path, cues = cartoons.record(series, scene, folder, 1)
    a, sr = sf.read(path)
    loud = np.nonzero(np.abs(a).max(1) > 0.1)[0]
    assert cues == [] and abs(loud[0] / sr - 1.0) < 0.01 and abs(np.abs(a).max() - cartoons.SFX_PEAK) < 0.01


def test_an_effect_is_cut_to_its_moment_and_a_prop_stands_on_its_spot(tmp_path):
    from entertainment import sfx

    sr = 44100
    take = np.zeros((int(5.5 * sr), 2), np.float32)
    take[int(0.8 * sr):] = 0.5 * np.random.default_rng(3).normal(size=(len(take) - int(0.8 * sr), 2))
    sf.write(tmp_path / "thud.wav", take, sr)
    a, _ = sf.read(sfx.tidy(tmp_path / "thud.wav"), always_2d=True)
    assert len(a) == int(sfx.LONGEST * sr) and np.abs(a[: int(0.02 * sr)]).max() < 0.01   # starts on its cue
    assert np.abs(a[int(0.1 * sr): int(0.3 * sr)]).max() > 0.3 and np.abs(a[-10:]).max() < 0.01

    series_dir, d = _series(tmp_path)
    kitmod.build(series_dir, "gull")
    k = kitmod.load(series_dir, "gull")
    w, h = 48 + 2 * kitmod.PAD, 64 + 2 * kitmod.PAD
    layout = lay.Layout.model_validate({"place": 1, "actors": [{"who": "gull", "x": 9.0, "spot": "sill"}]})
    p = lay.plan(layout, {"gull": k}, series_dir, 24, {}, [], d / "base.png", {"gull": (w, h)},
                 spots={"sill": (-3.4, 7.8)})
    x, y = p["cards"][0]["tf"][0][:2]
    feet = y + (h - (56 + kitmod.PAD)) * k.upp
    assert abs(x - (-3.4)) < 1e-6 and abs(feet - (-3.0 + 7.8)) < 0.05      # on the sill of a wide shot's plate


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


def test_the_check_looks_at_a_shot_after_each_thing_in_it_has_landed():
    from entertainment.cutout import engine

    layout = lay.Layout.model_validate({"place": 1, "actors": [{"who": "gull", "enter": "left"}], "beats": [
        {"who": "gull", "do": "pose", "value": "wave", "at": "1", "until": "2"},
        {"who": "gull", "do": "hop", "at": "3"}, {"who": "gull", "do": "exit", "value": "left", "at": "4.5"}]})
    got = engine.moments(layout, 120, [])
    assert [f for f, _ in got] == [1, 21, 35, 83, 120]               # in, posed, hopped; the exit is the last frame
    assert "come in" in got[1][1] and "pose (wave)" in got[2][1]
    busy = lay.Layout.model_validate({"place": 1, "actors": [{"who": "gull"}], "beats": [
        {"who": "gull", "do": "hop", "at": str(k)} for k in range(1, 9)]})
    frames = [f for f, _ in engine.moments(busy, 240, [])]
    assert len(frames) == engine.LOOKS and frames[0] == 1 and frames[-1] == 240 and frames == sorted(set(frames))
    assert engine.moments(lay.Layout.model_validate({"place": 1, "actors": [{"who": "gull"}]}), 48, []) \
        == [(1, "the shot's first frame"), (48, "the shot's last frame")]


def _episode(tmp_path, monkeypatch):
    """Three shots of the gull at the first place, on disk as an episode the stager has staged."""
    from entertainment import cartoons
    from entertainment.cutout import engine, writer

    series_dir, _ = _series(tmp_path)
    kitmod.build(series_dir, "gull")
    kitmod.save_rgb(np.full((90, 160, 3), (40, 90, 200), np.float32), series_dir / "places" / "place1.png")
    folder = series_dir / "ep"
    folder.mkdir()
    place = cartoons.SERIES["gully"].places[0]
    scene = {"place": place, "summary": "The gull waits on the wall.", "shots": [{"at": 0, "action": "a"}],
             "lines": [], "sounds": "waves", "seconds": 4.0}
    (folder / "episode.json").write_text(json.dumps({"title": "T", "logline": "L", "scenes": [scene] * 3}), encoding="utf-8")
    st = writer.Stage.model_validate({"actors": [{"who": "gull", "mark": "left", "height": "raised"}]})
    writer.save(folder, [st] * 3, {})
    writer.relayout(folder)
    asked = []

    def looks(f, only=()):
        asked.append(tuple(only))
        return {i: [(f"Shot {i}:", f / "look" / f"scene{i:02d}.f0001.jpg")] for i in (only or (1, 2, 3))}
    (folder / "look").mkdir()
    monkeypatch.setattr(engine, "looks", looks)
    return folder, st, asked


def test_a_shot_nobody_looked_at_is_not_a_pass_and_a_look_changes_nothing(tmp_path, monkeypatch):
    from newsroom import llm
    from entertainment.cutout import writer

    folder, st, _ = _episode(tmp_path, monkeypatch)
    before = {p.name: p.read_text(encoding="utf-8") for p in folder.glob("scene*.json")}
    sent = {}

    def answer(task, schema, system, user, **kw):
        sent.update(user=user, images=kw["images"])
        return writer.Looked.model_validate({"shots": [{"shot": 1, "faults": ["The gull stands on the sand."]},
                                                       {"shot": 2, "faults": []}, {"shot": 9, "faults": ["x"]}]})
    monkeypatch.setattr(llm, "complete_json", answer)
    report = writer.look(folder)
    assert report[1] == {"looked": True, "faults": ["The gull stands on the sand."]}
    assert report[2] == {"looked": True, "faults": []} and report[3]["looked"] is False      # no answer for shot 3
    assert len(sent["images"]) == 3 and "1. at " in sent["user"] and "3. at " in sent["user"]
    assert before == {p.name: p.read_text(encoding="utf-8") for p in folder.glob("scene*.json")}
    assert not list(folder.glob("stages.*"))
    assert json.loads((folder / "look" / "report.json").read_text(encoding="utf-8"))["3"]["looked"] is False

    def down(*a, **kw):
        raise llm.LLMUnavailable("no key")
    monkeypatch.setattr(llm, "complete_json", down)
    report = writer.look(folder, fix=True)
    assert all(not r["looked"] and r["why"] == "no key" and not r["faults"] for r in report.values())
    assert before == {p.name: p.read_text(encoding="utf-8") for p in folder.glob("scene*.json")}


def test_a_mended_staging_is_kept_only_if_it_looks_better(tmp_path, monkeypatch):
    from newsroom import llm
    from entertainment.cutout import engine, writer

    folder, st, asked = _episode(tmp_path, monkeypatch)
    assert writer.came_out(st, engine.layout_of(folder, 1), set()) \
        == ["gull was staged raised and stands on the ground instead (it does not fit in the shot there, or there "
            "is no spot in reach)"]
    old = (folder / "scene02.stage.json").read_text(encoding="utf-8")
    looks = [{"shots": [{"shot": 1, "faults": ["The gull hangs in the air."]},
                        {"shot": 2, "faults": ["The gull is cut off."]}, {"shot": 3, "faults": []}]},
             {"shots": [{"shot": 1, "faults": []}, {"shot": 2, "faults": ["The gull is still cut off."]}]}]
    prompts = []

    def answer(task, schema, system, user, **kw):
        if schema is writer.Looked:
            return writer.Looked.model_validate(looks.pop(0))
        prompts.append(user)
        return writer.PStages.model_validate({"stages": [{"actors": [{"who": "gull", "mark": "right"}]},
                                                         {"actors": [{"who": "gull", "mark": "centre"}]}]})
    monkeypatch.setattr(llm, "complete_json", answer)
    report = writer.look(folder, fix=True)
    assert "WHAT THE STAGE COULD NOT DO WITH IT: gull was staged raised" in prompts[0]
    assert "PLAYED, IT LOOKED WRONG: The gull hangs in the air." in prompts[0] and "3. at" not in prompts[0]
    assert report[1]["mended"] == "restaged" and report[1]["left"] == []
    assert report[2]["mended"].endswith("put back") and report[2]["tried"] == ["The gull is still cut off."]
    assert "mended" not in report[3]
    assert writer.Stage.model_validate_json((folder / "scene01.stage.json").read_text(encoding="utf-8")).actors[0].mark == "right"
    assert engine.layout_of(folder, 1).actors[0].x == 6.0
    assert (folder / "scene02.stage.json").read_text(encoding="utf-8") == old            # shot 2 as it was
    assert engine.layout_of(folder, 2).actors[0].x == -6.0
    assert sorted(p.name for p in (folder / "stages.1").iterdir()) == ["scene01.stage.json", "scene02.stage.json"]
    assert asked == [(), (1, 2), (2,)]                         # all, the two restaged, the one put back
