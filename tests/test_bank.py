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


def test_an_episode_is_written_as_h3_scenes_with_its_cast(monkeypatch):
    from entertainment import cartoons
    from newsroom import llm

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
