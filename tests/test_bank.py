"""The content bank and films on air (bank.py, film.py), and the cartoons' production tool (entertainment/
cartoons.py). A two-second test film is made with ffmpeg; the model is stubbed; nothing is rendered."""
from __future__ import annotations

import json
import subprocess
import time
from datetime import date, timedelta

import pygame
import pytest

from newsroom import bank, film, world as world_mod
from newsroom.models import Segment, SegmentType as T


def _film(path, seconds=2, colour="red"):
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={colour}:s=320x180:r=24:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}", "-shortest",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(path)], check=True)
    return path


@pytest.fixture
def shelf(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWSROOM_BANK", str(tmp_path / "bank"))
    return tmp_path


def test_a_film_goes_on_the_shelf_with_its_sound_and_airs_in_turn(shelf):
    w = world_mod.seed()
    a = bank.ingest(_film(shelf / "a.mp4"), "cartoons", "gully", "Gully's Kite")
    b = bank.ingest(_film(shelf / "b.mp4", colour="blue"), "cartoons", "gully", "Gully's Chips")
    assert {i.title for i in bank.items("cartoons")} == {"Gully's Kite", "Gully's Chips"}
    assert abs(a.seconds - 2.0) < 0.2 and bank.path(a, "audio").exists()
    assert bank.ingest(_film(shelf / "a2.mp4"), "cartoons", "gully", "Gully's Kite").id == a.id   # replaced, not doubled
    assert len(bank.items()) == 2
    first = bank.pick(w, "cartoons")
    second = bank.pick(w, "cartoons")
    assert {first.id, second.id} == {a.id, b.id}                   # the other one before a repeat
    assert bank.pick(w, "cartoons", "inventor") is None            # nothing in that series


def test_a_film_slot_airs_from_the_shelf_or_another_series_or_the_test_card(shelf):
    w = world_mod.seed()
    seg = Segment(slot_id=1, type=T.film, show="cartoons", brief="inventor", target_s=120)
    assert bank.segment(seg, w).type is T.testcard                 # the shelf is empty: never dead air
    bank.ingest(_film(shelf / "a.mp4"), "cartoons", "gully", "Gully's Kite")
    seg = Segment(slot_id=2, type=T.film, show="cartoons", brief="inventor", target_s=120)
    ready = bank.segment(seg, w)
    assert ready.type is T.film and ready.headline == "Gully's Kite" and ready.work["film"].endswith(".mp4")
    assert ready.lines[0].wav_path.suffix == ".wav" and abs(ready.lines[0].duration_s - 2.0) < 0.2
    assert list(w.bank_aired.values()) == [[date.fromtimestamp(time.time()).isoformat()]]


def test_the_film_is_decoded_at_the_windows_size(shelf):
    path = str(_film(shelf / "a.mp4"))
    f = None
    for _ in range(200):                                           # the reader thread starts up
        f = film.frame(path, 0.5, (96, 54))
        if f is not None:
            break
        time.sleep(0.01)
    assert f is not None and f.get_size() == (96, 54) and f.get_at((48, 27))[:3][0] > 200   # red
    film.stop()


def test_an_episode_is_written_as_h3_scenes_with_its_cast(monkeypatch, tmp_path):
    from entertainment import cartoons
    from newsroom import llm

    monkeypatch.setattr(cartoons, "ROOT", tmp_path)                # no designs on this shelf
    series = cartoons.SERIES["gully"]
    reply = cartoons.Episode.model_validate({"title": "Gully's Kite", "logline": "Gully flies a chip bag.", "scenes": [
        {"place": "the harbour wall at low tide", "summary": "Gully finds a chip bag and has an idea.",
         "shots": [{"at": 3, "action": "wide on the wall, Gully lands"}, {"at": 0, "action": "close on the bag"}],
         "lines": [{"who": "gully", "words": "Chips. Or the bag of chips. Close enough."},
                   {"who": "nobody", "words": "Dropped."}],
         "sounds": "waves and gulls"},
        {"place": "the chip shop on the quay", "summary": "Biscuit watches a kite go up and come down.",
         "shots": [{"at": 0, "action": "Biscuit on the sill, unimpressed"}], "lines": [], "sounds": "a breeze"}]})
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: reply.model_copy(deep=True))
    ep = cartoons.write(series, 2)
    assert [s.at for s in ep.scenes[0].shots] == [0.0, 3]           # in order, the first at 0
    assert [l.who for l in ep.scenes[0].lines] == ["gully"]        # nobody else speaks
    text, pics, voices = cartoons.prompt(series, ep.scenes[0])
    for section in ("subject_definitions:", "summary: [reference generation]", "retention_analysis:",
                    "detailed_description: The target video is hand-drawn 2D cartoon", "overall_soundscape:",
                    "non_diegetic_music:"):
        assert section in text
    assert "(S1) <d>[English] Chips." in text and "Only the dialogue above." in text
    assert "background is not retained" in text and "[Shot 2] At 00:03.000" in text
    assert [p.name for p in pics] == ["gully_full.png", "gully_face.png"]
    biscuit_scene, b_pics, _ = cartoons.prompt(series, ep.scenes[1])
    assert "Nobody speaks." in biscuit_scene and [p.name for p in b_pics] == ["biscuit_full.png", "biscuit_face.png"]
    assert cartoons.frames(15) == 362 and cartoons.frames(5) == 124
    with pytest.raises(FileNotFoundError, match="design stage"):        # no pictures yet: no render
        cartoons.settings(series, ep.scenes[0], seed=1)


def test_both_voices_reach_wan2gp_in_the_prompts_order(monkeypatch, tmp_path):
    from entertainment import cartoons

    monkeypatch.setattr(cartoons, "ROOT", tmp_path)
    series = cartoons.SERIES["gully"]
    series.refs().mkdir(parents=True)
    for name in ("gully_full.png", "gully_face.png", "biscuit_full.png", "biscuit_face.png", "gully_voice.wav",
                 "biscuit_voice.wav"):
        (series.refs() / name).write_bytes(b"x")
    scene = cartoons.Scene(place="the harbour wall", summary="Gully asks; Biscuit says no.",
                           shots=[{"at": 0, "action": "Gully and Biscuit on the wall"}],
                           lines=[{"who": "gully", "words": "Chips?"}, {"who": "biscuit", "words": "No."}], sounds="waves")
    text, _, voices = cartoons.prompt(series, scene)
    s = cartoons.settings(series, scene, seed=1)
    assert s["audio_prompt_type"] == "AB" and len(s["image_refs"]) == 4
    assert [s["audio_guide"], s["audio_guide2"]] == [str(v) for v in voices]
    assert s["audio_guide"].endswith("gully_voice.wav") and "exactly the voice heard in <Audio 2>" in text


def test_the_comfyui_graph_is_h3_ref2va_with_the_turbo_lora():
    from entertainment import cartoons

    g = cartoons.comfy_graph("the prompt", ["a.png", "b.png"], ["v.wav"], seed=5, length=362, prefix="gully_x_scene01")
    h3 = g["9"]["inputs"]
    assert g["9"]["class_type"] == "MiniMaxH3ReferenceToVideo" and h3["length"] == 362 and h3["prompt"] == "the prompt"
    assert [g[h3[f"ref_images.ref_image_{i}"][0]]["inputs"]["image"] for i in range(2)] == ["a.png", "b.png"]
    assert g[h3["ref_audios.ref_audio_0"][0]]["inputs"]["audio"] == "v.wav"
    assert g["2"]["inputs"]["lora_name"] == cartoons.H3["turbo"] and g["12"]["inputs"]["steps"] == 4
    assert g["12"]["inputs"]["model"] == ["2", 0] and g["13"]["inputs"]["model"] == ["2", 0]
    full = cartoons.comfy_graph("p", ["a.png"], [], seed=5, length=124, prefix="x", steps=20)
    assert "2" not in full and full["12"]["inputs"]["model"] == ["1", 0] and full["12"]["inputs"]["steps"] == 20


def test_a_dry_run_writes_each_scenes_graph_and_a_rendered_scene_is_kept(monkeypatch, tmp_path):
    from entertainment import cartoons

    monkeypatch.setattr(cartoons, "ROOT", tmp_path)
    monkeypatch.setattr(cartoons, "_comfy", lambda *a, **k: pytest.fail("a dry run never calls ComfyUI"))
    monkeypatch.setattr(cartoons, "DIALOGUE", "h3")                  # H3 voices the lines (no voice clips here)
    series = cartoons.SERIES["gully"]
    series.refs().mkdir(parents=True)
    for name in ("gully_full.png", "gully_face.png", "biscuit_full.png", "biscuit_face.png"):
        (series.refs() / name).write_bytes(b"x")
    ep = cartoons.Episode.model_validate({"title": "Gully's Kite", "logline": "A kite.", "scenes": [
        {"place": "the harbour wall", "summary": "Gully finds a bag.", "shots": [{"at": 0, "action": "Gully lands"}],
         "lines": [{"who": "gully", "words": "Chips!"}], "sounds": "waves"},
        {"place": "the quay", "summary": "Biscuit watches.", "shots": [{"at": 0, "action": "Biscuit sits"}],
         "lines": [], "sounds": "a breeze"}]})
    folder = tmp_path / "gully" / "gullys-kite"
    (folder / "scene01").mkdir(parents=True)
    (folder / "episode.json").write_text(ep.model_dump_json(), encoding="utf-8")
    (folder / "scene01" / "done.mp4").write_bytes(b"x")                 # rendered on an earlier night
    assert cartoons.render(folder, dry_run=True, engine="comfy") == [folder / "scene01" / "done.mp4"]
    assert not (folder / "scene01.comfy.json").exists()
    g = json.loads((folder / "scene02.comfy.json").read_text(encoding="utf-8"))
    assert g["9"]["inputs"]["length"] == 362 and g["10"]["inputs"]["noise_seed"] == 1002
    assert g["18"]["inputs"]["filename_prefix"] == "cartoons/gully_gullys-kite_scene02"
    assert "Biscuit" in g["9"]["inputs"]["prompt"] and g["100"]["inputs"]["image"] == "biscuit_full.png"


def test_the_recorded_dialogue_is_laid_on_the_scene_and_given_to_h3_as_audio_1(monkeypatch, tmp_path):
    import numpy as np
    import soundfile as sf
    from entertainment import cartoons

    monkeypatch.setattr(cartoons, "ROOT", tmp_path)
    said = []

    def speak(series, who, words):                                 # a tone a second long per line, at 24 kHz
        said.append((who, words))
        t = np.arange(24000) / 24000
        return (0.3 * np.sin(2 * np.pi * (220 if who == "gully" else 150) * t)).astype(np.float32)

    monkeypatch.setattr(cartoons, "_speak", speak)
    series = cartoons.SERIES["inventor"]
    scene = cartoons.Scene(place="the shed", summary="Morwenna explains; Ballast waits.",
                           shots=[{"at": 0, "action": "Morwenna at the bench, Ballast on the floor"}],
                           lines=[{"who": "morwenna", "words": "It nearly works!"},
                                  {"who": "morwenna", "words": "Pass the spanner, Ballast."}], sounds="clanks")
    folder = tmp_path / "inventor" / "ep"
    folder.mkdir(parents=True)
    track, cues = cartoons.record(series, scene, folder, 1)
    assert [c.words for c in cues] == ["It nearly works!", "Pass the spanner, Ballast."] and len(said) == 2
    a, sr = sf.read(track)
    assert sr == cartoons.TRACK_SR and a.shape == (round(362 / 24 * sr), 2)    # the scene's exact length, stereo
    first, second = cues
    assert cartoons.LEAD_S <= first.at < 2.0 and second.at - first.at >= 1.0 + cartoons.GAP_S - 0.05
    loud = np.flatnonzero(np.abs(a[:, 0]) > 0.05) / sr
    assert abs(loud[0] - first.at) < 0.05 and loud[-1] < 362 / 24 - cartoons.TAIL_S + 0.05
    cartoons.record(series, scene, folder, 1)
    assert len(said) == 2                                           # recorded once: kept in scene01/lines
    text, pics, voices = cartoons.prompt(series, scene, cues)
    assert voices == [] and "her lines are heard in <Audio 1>" in text and "Ballast" in text
    assert f'at 00:{first.at:06.3f} (S1) Morwenna says "It nearly works!"' in text and "<d>" not in text
    assert "Everything heard is <Audio 1> reproduced exactly, in time with it" in text
    assert "Under the dialogue, clanks, as heard in <Audio 1>. No other speech" in text
    nobody = cartoons.Scene(place="the shed", summary="Ballast crawls.", shots=[{"at": 0, "action": "Ballast"}],
                            lines=[], sounds="ticking")
    assert cartoons.record(series, nobody, folder, 2) is None       # nothing to record: H3 makes the sound


def test_a_series_never_speaks_for_its_silent_partner():
    from entertainment import cartoons

    ballast = next(c for c in cartoons.SERIES["inventor"].cast if c.key == "ballast")
    assert ballast.voice == ""
    scene = cartoons.Scene(place="the harbour wall", summary="Ballast saves the day while Morwenna talks.",
                           shots=[{"at": 0, "action": "Ballast crawls along the wall"}],
                           lines=[{"who": "morwenna", "words": "Nearly there!"}], sounds="seagulls")
    text, pics, _ = cartoons.prompt(cartoons.SERIES["inventor"], scene)
    assert "Ballast" in text and "never speaks" in text and len(pics) == 4


def test_cartoon_time_airs_films_at_seven_on_the_entertainment_channel():
    import entertainment
    from newsroom import schedule

    undo = entertainment.use()
    try:
        lt = time.localtime()
        at = lambda h, m=0: time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
        show = schedule.show_at(at(19, 15))
        assert show.id == "cartoons" and {schedule.as_item(e).type for e in show.pattern} == {T.bumper, T.film}
        assert schedule.show_at(at(20, 5)).id == "wits"
    finally:
        undo()
