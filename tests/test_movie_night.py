"""Channel 8's TV movie at 21:00 (entertainment/movie_night.py): which film airs, the slot's whole order planned by the
producer, and the items made ahead. The films are built here, voiced with silence: no model, no TTS."""
from __future__ import annotations

import json
import time
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pytest
import soundfile as sf

from entertainment import movie_cards, movie_night as N, movies as M
from newsroom.models import Line, Segment, SegmentType as T

DAY = date(2026, 11, 25)
SETS = ["harbour", "tea_room", "pub", "church"]


def _ts(hh: int, mm: int, day: date = DAY) -> float:
    return time.mktime(datetime(day.year, day.month, day.day, hh, mm).timetuple())


def _wav(path: Path, seconds: float) -> Path:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        sf.write(path, np.zeros(int(8000 * seconds), dtype=np.float32), 8000)
    return path


def make_film(title: str, scene_s: float, cut: tuple[str, ...] = ()) -> Path:
    """A finished, approved film in the tests' bank, voiced: every scene `scene_s` long, in two lines."""
    names = [f"{title.split()[0]} Penrose", f"{title.split()[0]} Keast"]
    film = {
        "pitch": {"title": title, "genre": "mystery", "logline": "x" * 20, "hook": "y"},
        "outline": {"title": title, "genre": "mystery", "logline": "x" * 20, "tone": "quiet",
                    "parts": [{"name": n, "gender": g, "age": "middle", "who": f"The {w}, who matters.", "wants": "w"}
                              for n, g, w in zip(names, "fm", ("harbourmaster", "clerk"))],
                    "acts": [{"name": f"Act {a}", "happens": "x" * 20, "ends_on": "y"} for a in range(M.ACTS)],
                    "ending": "the end"},
        "acts": [{"scenes": [{"set": SETS[s % 4], "when": "night" if s == 0 else "day", "characters": names,
                              "knows": "k", "beats": "b" * 10, "ends_on": "e"} for s in range(M.SCENES_PER_ACT)]}
                 for _ in range(M.ACTS)],
        "scenes": {}, "cut": list(cut), "approved": "2026-11-23",
    }
    for a in range(M.ACTS):
        for s in range(M.SCENES_PER_ACT):
            film["scenes"][f"{a + 1}.{s + 1}"] = [{"character": names[i % 2], "mood": "", "text": f"Line {i} of {a}.{s}."}
                                                  for i in range(2)]
    folder = M.start(film["pitch"], bank=M.bank_dir())
    M.save(folder, film)
    M.render(folder, film, say=lambda s: None)
    cast = M.cast(film)
    (folder / "cast.toml").write_text(M.cast_toml(cast), encoding="utf-8")
    clip = _wav(folder / "cache" / "half.wav", 0.1)
    out = []
    for n, (k, sc) in enumerate(M._live_rows(film), 1):
        lines = [Line(speaker="guest", text=l["text"], guest_name=l["character"], wav_path=clip, duration_s=scene_s / 2)
                 for l in film["scenes"][k]]
        out.append({"number": n, "set": sc["set"], "when": sc["when"], "characters": sc["characters"],
                    "keys": ["k"] * len(lines), "lines": [json.loads(l.model_dump_json()) for l in lines]})
    (folder / "segments.json").write_text(json.dumps({"script": M.voice_hash(folder), "scenes": out}), encoding="utf-8")
    return folder


@pytest.fixture
def channel8(monkeypatch, tmp_path):
    """Channel 8 on, a world of its own loaded, the tests' bank empty to start; the theme music made of silence."""
    import shutil

    import entertainment
    from newsroom import world as world_mod

    shutil.rmtree(M.bank_dir(), ignore_errors=True)
    theme = (_wav(tmp_path / "t.wav", 21.8), _wav(tmp_path / "c.wav", 43.6))
    monkeypatch.setattr(movie_cards, "ensure_theme", lambda cache=None: theme)
    w = world_mod.load()
    w.bank_aired.clear()
    undo = entertainment.use()
    yield w
    undo()
    shutil.rmtree(M.bank_dir(), ignore_errors=True)


def test_a_film_too_short_for_the_slot_is_held_out_and_with_none_the_slot_is_the_closedown(channel8):
    from newsroom import schedule

    make_film("Short Night", 85.0)                    # 40 scenes, 57 minutes, as The Last Lot
    assert N.fit_to_air() == {}
    assert schedule.show_at(_ts(21, 5)).id == "closedown"
    assert schedule.next_start("closedown", _ts(21, 5)) == "18:00"


def test_the_nights_film_is_picked_once_kept_in_the_world_and_another_airs_the_next_night(channel8):
    from newsroom import schedule

    make_film("Low Water", 120.0)                     # 80 minutes of scenes
    make_film("High Tide", 118.0)
    first = schedule.show_at(_ts(21, 5)).id
    assert first in ("movie-low-water", "movie-high-tide")
    assert schedule.show_at(_ts(22, 0)).id == first and schedule.show_at(_ts(22, 35)).id == "closedown"
    assert channel8.bank_aired[first] == [DAY.isoformat()]
    N._picked.clear()                                 # a restart: the world's record holds the night
    assert schedule.show_at(_ts(21, 5)).id == first
    nxt = date(2026, 11, 27)
    assert schedule.show_at(_ts(21, 5, nxt)).id != first          # the one not aired yet


def _plan(start: float, stop_show: str = "closedown"):
    from newsroom.buffer import Buffer
    from newsroom.producer import Producer

    p = Producer(Buffer(), horizon_s=10 ** 6, start_ts=start)
    out = []
    for _ in range(200):
        seg = p.plan_one()
        out.append(seg)
        if seg.show == stop_show and len(out) > 2:
            break
    return out


def test_the_slot_plans_the_whole_film_with_a_break_at_each_act_end_then_closes_on_time(channel8):
    folder = make_film("Low Water", 120.0, cut=("2.3", "3.10"))
    segs = [s for s in _plan(_ts(21, 0)) if s.show.startswith("movie-")]
    briefs = [s.brief for s in segs]
    assert briefs[:3] == ["ident", "titles", "scene 1"] and briefs.count("credits") == 1
    scenes = [b for b in briefs if b.startswith("scene ")]
    assert scenes == [f"scene {n}" for n in range(1, 39)]          # every scene left after the cuts, in order
    assert briefs.count("break") == N.BREAKS and briefs[-1] == "close" and briefs.count("close") == 1
    # The breaks fall at the acts' ends: act 2 lost a scene and act 3 its last, so they come after 10, 19 and 28.
    before = [briefs[i - 1] for i, b in enumerate(briefs) if b == "break"]
    assert before == ["scene 10", "scene 19", "scene 28"]
    end = segs[-1].nominal_start_ts + segs[-1].target_s
    assert abs(end - _ts(22, 30)) < 3 * 60                           # the breaks take up what's left
    assert segs[-1].type is T.ad_break
    assert folder.name in N._films


def test_a_film_that_starts_late_is_never_cut_and_the_closedown_follows_it(channel8):
    make_film("Low Water", 120.0)
    plan = _plan(_ts(21, 40))
    film = [s for s in plan if s.show.startswith("movie-")]
    assert len([s for s in film if s.brief.startswith("scene ")]) == M.ACTS * M.SCENES_PER_ACT
    assert film[-1].brief == "close" and plan[-1].show == "closedown"
    assert plan[-1].nominal_start_ts > _ts(22, 30)                   # it ran over, and finished


def test_the_scenes_titles_and_credits_are_made_ahead_the_ident_and_breaks_by_the_station(channel8):
    from newsroom import workers

    make_film("Low Water", 120.0)
    segs = {s.brief: s for s in _plan(_ts(21, 0)) if s.show.startswith("movie-")}
    hook = workers.READY_HOOKS[segs["scene 1"].show]
    scene = hook(segs["scene 1"], channel8)
    assert scene.state.value == "ready" and len(scene.lines) == 2 and scene.lines[0].wav_path.exists()
    assert scene.work["set"] == "harbour" and scene.work["tod"] == "night" and scene.headline == "Low Water, scene 1"
    titles = hook(segs["titles"], channel8)
    assert titles.work["card"]["card"] == "titles" and titles.work["card"]["tod"] == "night"
    credits = hook(segs["credits"], channel8)
    assert [n for n, _ in credits.work["card"]["cast"]] == ["Low Penrose", "Low Keast"]
    assert credits.work["card"]["cast"][0][1] == "the harbourmaster"
    for brief in ("ident", "break", "close"):
        assert hook(segs[brief], channel8) is None


def test_the_films_light_is_only_the_scenes_and_cards_not_an_advert_in_its_break():
    from newsroom.player import View

    v = View(tod="night")
    M._view(Segment(slot_id=1, type=T.ad_break, show="movie-x"), v, 0)
    assert v.tod == "night"
    M._view(Segment(slot_id=2, type=T.interview, show="movie-x", work={"set": "pub", "tod": "dusk"}), v, 0)
    assert v.tod == "dusk"
