"""The TV movie's writer (entertainment/movies.py): a film written ahead in three levels, saved as it goes, and
script.md, which the user reads and edits. The model is stubbed: no network."""
from __future__ import annotations

import json
import re

import numpy as np
import pytest

from entertainment import movies as M
from newsroom import llm, world as world_mod

PARTS = [("Maud Penrose", "f", "old"), ("Tom Keast", "m", "middle"), ("Jenna Rowe", "f", "young")]
NAMES = [p[0] for p in PARTS]
SETS = ["harbour", "tea_room", "lighthouse", "pub", "church", "seafront", "woods", "main_street"]


def _outline(names=NAMES):
    return M.Outline.model_validate({
        "title": "The Keeper's Daughter", "genre": "mystery",
        "logline": "A retired lighthouse keeper's daughter comes home to find her father's logbook missing.",
        "tone": "quiet, salty, a little eerie",
        "parts": [{"name": n, "gender": g, "age": a, "who": f"{n}, who matters to the story",
                   "wants": "the truth, and to be left alone"} for n, (_, g, a) in zip(names, PARTS)],
        "acts": [{"name": f"Act {i + 1}", "happens": f"In act {i + 1} the logbook trail goes on and on.",
                  "ends_on": f"the end of act {i + 1}"} for i in range(M.ACTS)],
        "ending": "Maud finds the logbook in the church; Jenna says: 'He kept it for you.'"})


def _act(set_id=None):
    return M.ActPlan.model_validate({"scenes": [
        {"set": set_id or SETS[i % len(SETS)], "when": "day", "characters": [NAMES[i % 3], NAMES[(i + 1) % 3]],
         "knows": "nobody knows yet", "beats": f"they talk about the log, beat {i + 1}", "ends_on": "a look"}
        for i in range(M.SCENES_PER_ACT)]})


def _dialogue(user, words=8):
    who = re.search(r"In it: (.+?)\. As it starts", user).group(1).split(", ")
    return M.Dialogue.model_validate({"lines": [
        {"character": who[i % len(who)], "mood": "worried" if i == 0 else "", "text": " ".join(["word"] * words)}
        for i in range(12)]})


def _stub(monkeypatch, fail_at=None, outline=None, act=None):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, schema, system, user))
        if schema is M.Outline:
            return outline() if outline else _outline()
        if schema is M.ActPlan:
            return act(user) if act else _act()
        if schema is M.Dialogue:
            if fail_at is not None and sum(s is M.Dialogue for _, s, _, _ in seen) == fail_at:
                raise llm.LLMError("down")
            return _dialogue(user)
        raise AssertionError(schema)
    monkeypatch.setattr(llm, "complete_json", complete_json)
    return seen


@pytest.fixture
def film(tmp_path):
    return M.start({"title": "The Keeper's Daughter", "genre": "mystery", "logline": "a logbook goes missing",
                    "hook": "who took it"}, bank=tmp_path)


def test_a_film_is_written_outline_acts_then_every_scene_and_script_md_reads_back(monkeypatch, film):
    seen = _stub(monkeypatch)
    done = M.write(film, world_mod.seed(), say=lambda s: None)
    n = M.ACTS * M.SCENES_PER_ACT
    assert len(done["acts"]) == M.ACTS and len(done["scenes"]) == n
    assert [s for _, s, _, _ in seen].count(M.Dialogue) == n
    cast, scenes = M.parse(film / "script.md")
    assert cast == NAMES and len(scenes) == n and [s.number for s in scenes] == list(range(1, n + 1))
    assert scenes[0].set == "harbour" and scenes[0].characters == NAMES[:2]
    assert scenes[0].lines[0] == ("Maud Penrose", " ".join(["word"] * 8), "worried")
    assert M.estimate(film / "script.md") == pytest.approx(n * 12 * 8 / M.WORDS_PER_S)


def test_each_scene_is_given_the_whole_script_so_far_and_the_last_is_told_it_ends_the_film(monkeypatch, film):
    seen = _stub(monkeypatch)
    M.write(film, world_mod.seed(), say=lambda s: None)
    asked = [u for _, s, _, u in seen if s is M.Dialogue]
    assert "nothing yet: this is the opening scene" in asked[0]
    assert "[Scene 1.1, the harbour, day]" in asked[1] and "[Scene 1.1," in asked[-1] and f"[Scene {M.ACTS}.{M.SCENES_PER_ACT - 1}," in asked[-1]
    assert "LAST scene of the film" in asked[-1] and "last scene before the ad break" in asked[M.SCENES_PER_ACT - 1]


def test_a_failure_keeps_everything_so_far_and_write_goes_on_from_there(monkeypatch, film):
    _stub(monkeypatch, fail_at=5)
    with pytest.raises(llm.LLMError):
        M.write(film, world_mod.seed(), say=lambda s: None)
    kept = M.load(film)
    assert kept["outline"] and len(kept["acts"]) == M.ACTS and len(kept["scenes"]) == 4
    seen = _stub(monkeypatch)
    M.write(film, world_mod.seed(), say=lambda s: None)
    assert [s for _, s, _, _ in seen].count(M.Outline) == 0 and [s for _, s, _, _ in seen].count(M.ActPlan) == 0
    assert len(M.load(film)["scenes"]) == M.ACTS * M.SCENES_PER_ACT


def test_a_part_named_for_a_resident_is_asked_again(monkeypatch, film):
    w = world_mod.seed()
    resident = w.people[0].name
    drafts = iter([_outline([resident, *NAMES[1:]]), _outline()])
    seen = _stub(monkeypatch, outline=lambda: next(drafts))
    M.write(film, w, say=lambda s: None)
    asked = [u for _, s, _, u in seen if s is M.Outline]
    assert len(asked) == 2 and "is a resident of the town" in asked[1]
    assert M.load(film)["outline"]["parts"][0]["name"] == "Maud Penrose"


def test_an_act_on_a_set_that_isnt_one_is_asked_again(monkeypatch, film):
    drafts = iter([_act("marina_kitchen")] + [_act()] * M.ACTS)
    seen = _stub(monkeypatch, act=lambda user: next(drafts))
    M.write(film, world_mod.seed(), say=lambda s: None)
    asked = [u for _, s, _, u in seen if s is M.ActPlan]
    assert "'marina_kitchen', which is not one of THE SETS" in asked[1]


def _night_on(set_id):
    plan = _act().model_dump()
    plan["scenes"][2].update(set=set_id, when="night")
    return M.ActPlan.model_validate(plan)


def test_a_night_scene_on_a_set_with_no_night_picture_is_asked_again(monkeypatch, film):
    """2026-11-24: Dead Reckoning's fish quay, coast road and slipway at night aired as a blue-tinted day."""
    assert {"fish_quay", "slipway", "coast_road"} <= M.by_day_only() and "harbour" not in M.by_day_only()
    assert "fish_quay: the fish quay: fish boxes on ice, the auction floor, the boats tied up (day or evening only"         in M._sets_text()
    drafts = iter([_night_on("fish_quay")] + [_act()] * M.ACTS)
    seen = _stub(monkeypatch, act=lambda user: next(drafts))
    M.write(film, world_mod.seed(), say=lambda s: None)
    asked = [u for _, s, _, u in seen if s is M.ActPlan]
    assert "scene 3 is at night on 'fish_quay', which is day or evening only" in asked[1]


def test_night_on_a_set_with_its_own_night_picture_or_indoors_is_fine():
    for set_id in ("harbour", "pub"):
        M._check_act(_night_on(set_id), _outline())


def test_a_scene_is_tidied_and_checked():
    sc = {"characters": NAMES[:2]}
    d = M.Dialogue.model_validate({"lines": [
        {"character": NAMES[i % 2], "text": "Maud: Morning, Tom." if i == 0 else "Fine words, these."}
        for i in range(8)]})
    M.check_scene(d, sc, NAMES)
    assert d.lines[0].text == "Morning, Tom."           # the name in front goes
    stray = M.Dialogue.model_validate({"lines": [{"character": NAMES[i % 3], "text": "Hello there."} for i in range(8)]})
    with pytest.raises(llm.AskAgain, match="not in this scene"):
        M.check_scene(stray, sc, NAMES)
    alone = M.Dialogue.model_validate({"lines": [{"character": NAMES[0], "text": "Hello there."} for _ in range(8)]})
    with pytest.raises(llm.AskAgain, match="only one"):
        M.check_scene(alone, sc, NAMES)


def test_an_unknown_mood_is_dropped_not_failed():
    assert M.FilmLine(character="Maud Penrose", mood="Pensive", text="Well.").mood == ""
    assert M.FilmLine(character="Maud Penrose", mood="Worried", text="Well.").mood == "worried"


def test_a_hand_edited_script_is_never_overwritten(monkeypatch, film):
    _stub(monkeypatch)
    done = M.write(film, world_mod.seed(), say=lambda s: None)
    path = film / "script.md"
    path.write_text(path.read_text(encoding="utf-8").replace("word word", "a new line", 1), encoding="utf-8")
    M.render(film, done, say=lambda s: None)
    assert "a new line" in path.read_text(encoding="utf-8") and (film / "script.new.md").exists()


def test_parse_refuses_a_speaker_or_mood_not_in_the_script(monkeypatch, film):
    _stub(monkeypatch)
    M.write(film, world_mod.seed(), say=lambda s: None)
    path = film / "script.md"
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("MAUD PENROSE (worried)", "GORDON PELL", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="not in the cast"):
        M.parse(path)
    path.write_text(text.replace("(worried)", "(pensive)", 1), encoding="utf-8")
    with pytest.raises(ValueError, match="not a mood"):
        M.parse(path)


def test_no_film_is_written_with_the_models_off():
    assert "off" in M._models_on()


def test_the_bank_lists_its_films_and_a_title_is_only_started_once(tmp_path):
    M.start({"title": "Low Water", "genre": "thriller", "logline": "x" * 20, "hook": "y"}, bank=tmp_path)
    with pytest.raises(FileExistsError):
        M.start({"title": "Low Water", "genre": "thriller", "logline": "x" * 20, "hook": "y"}, bank=tmp_path)
    assert [(p.name, f["pitch"]["genre"]) for p, f in M.films(tmp_path)] == [("low-water", "thriller")]
    assert json.loads((tmp_path / "low-water" / "film.json").read_text(encoding="utf-8"))["approved"] is None


def test_the_cast_takes_pool_voices_by_gender_none_twice_and_nobody_joins_the_town(monkeypatch, film):
    from newsroom import world as W
    _stub(monkeypatch)
    done = M.write(film, world_mod.seed(), say=lambda s: None)
    cast = M.cast(done)
    assert list(cast) == NAMES and len({c["voice"] for c in cast.values()}) == len(cast)
    for name, (_, g, a) in zip(NAMES, PARTS):
        assert cast[name]["voice"] in W.guest_pool(g, a) + W.guest_pool(g, None)
    (film / "cast.toml").write_text(M.cast_toml(cast), encoding="utf-8")
    assert M.load_cast(film)["Maud Penrose"]["voice"] == cast["Maud Penrose"]["voice"]


def test_a_film_registers_bare_with_pinned_voices_and_looks_and_undoes_cleanly(monkeypatch, film):
    from newsroom import channel, locations, player, scenes, world as W
    _stub(monkeypatch)
    done = M.write(film, world_mod.seed(), say=lambda s: None)
    cast = M.cast(done)
    marks, chan = dict(locations.MARKS), channel.CURRENT
    undo = M.register_film(cast, "The Keeper's Daughter")
    try:
        assert M.SHOW in player.BARE_SHOWS and locations.MARKS["harbour"]["a"] == M.FILM_MARKS["a"]
        assert W.PINNED_VOICES["Tom Keast"][0] == cast["Tom Keast"]["voice"] and "Tom Keast" in scenes.PINNED_LOOKS
        assert channel.CURRENT.number == "8"
        seg = M.scene_segment(0, {"number": 3, "set": "harbour", "when": "evening", "characters": NAMES[:2]}, [])
        assert seg.work == {"set": "harbour", "seats": NAMES[:2], "tod": "dusk"}
    finally:
        undo()
    assert M.SHOW not in player.BARE_SHOWS and dict(locations.MARKS) == marks and channel.CURRENT is chan
    assert "Tom Keast" not in W.PINNED_VOICES and "Tom Keast" not in scenes.PINNED_LOOKS


def test_the_titles_and_credits_are_cards_of_their_own_with_the_films_music(monkeypatch, film, tmp_path):
    import pygame

    from entertainment import movie_cards as C
    from newsroom import player, scenes
    from newsroom.models import SegmentType
    pygame.font.init()
    _stub(monkeypatch)
    done = M.write(film, world_mod.seed(), say=lambda s: None)
    cast = M.cast(done)
    from newsroom import jingle
    monkeypatch.setattr(C, "_pass_s", lambda: 2.0)       # two seconds a pass, not twenty-two
    monkeypatch.setattr(jingle, "bed", lambda style, passes: np.full((int(8.0 * jingle.SR), 2), 0.1, np.float32))
    undo = M.register_film(cast, "The Keeper's Daughter")
    try:
        first = {"number": 1, "set": "harbour", "when": "night", "characters": NAMES[:2]}
        titles = C.titles_segment(0, M.SHOW, "The Keeper's Daughter", first, tmp_path)
        credits = C.credits_segment(5, M.SHOW, "The Keeper's Daughter", cast, ["harbour", "tea_room", "harbour"],
                                    tmp_path, year=2026)
        assert titles.type is SegmentType.bumper and titles.lines[0].duration_s == pytest.approx(2.0, abs=0.05)
        assert credits.lines[0].duration_s == pytest.approx(4.0, abs=0.05)
        card = credits.work["card"]
        assert card["places"] == ["Harbour", "Tea room"] and [n for n, _ in card["cast"]] == NAMES
        assert scenes.SCENES[C.CREDITS_MODE] is C.draw_credits and C.TITLES_MODE in scenes.NO_CLOCK
        for seg, mode in ((titles, C.TITLES_MODE), (credits, C.CREDITS_MODE)):
            v = player.View(slot_id=seg.slot_id, show=M.SHOW)
            M._view(seg, v, 0)
            assert v.mode == mode and v.scene is seg.work["card"]
            canvas = pygame.Surface(scenes.CANVAS)
            for t in (0.0, 1.0, 12.0):
                scenes.render(canvas, v, t)             # draws, and never the clock
    finally:
        undo()
    assert C.TITLES_MODE not in scenes.SCENES and not scenes.NO_CLOCK


def test_a_part_is_credited_in_a_few_words():
    from entertainment.movie_cards import role
    assert role("The young auctioneer, who took the rostrum when her father died.") == "the young auctioneer"
    assert role("A retired net-mender who runs the tea room over the quay.") == "a retired net-mender"
    assert role("Jago's deckhand and Bryony's nephew. Loyal.") == "Jago's deckhand and Bryony's nephew"


def test_what_leaks_into_a_line_is_scrubbed_and_the_leaked_mood_kept():
    rq, lq = chr(0x201D), chr(0x201C)
    cases = {
        "It plays havoc with the icing.','mood':'smug": ("It plays havoc with the icing.", "smug"),
        f"Nobody could object to that.{rq},{lq}mood{rq}:{lq}worried": ("Nobody could object to that.", "worried"),
        "He never budged.Mood: nothing, flat.": ("He never budged.", ""),
        "As tight as a drum.</br>": ("As tight as a drum.", ""),
        "I've lost my place.com": ("I've lost my place.", ""),
        f"Nothing else.Whoever's name is on the front.{chr(0x200B)}": ("Nothing else. Whoever's name is on the front.", ""),
        f"Don't mind him. {chr(0xB6)}": ("Don't mind him.", ""),
        f"A draughtier rock, Mr Skerritt.{rq},": ("A draughtier rock, Mr Skerritt.", ""),
        f"She said {lq}go{rq}": (f"She said {lq}go{rq}", ""),                  # a closed quote stays
        '"I must go."': ('"I must go."', ""),
        "I'm in no mood. It cost £2,000 at 8.20.": ("I'm in no mood. It cost £2,000 at 8.20.", ""),
    }
    for raw, want in cases.items():
        assert M.scrub(raw) == want, raw
    assert M.scrub("Go on.mood: worried", "cross") == ("Go on.", "cross")    # its own mood wins


def test_a_scene_with_markup_left_in_a_line_is_asked_again():
    sc = {"characters": NAMES[:2]}
    d = M.Dialogue.model_validate({"lines": [
        {"character": NAMES[i % 2], "text": "Nobody reaches him by boat.of course.mrk" if i == 3 else "Fine words."}
        for i in range(8)]})
    with pytest.raises(llm.AskAgain, match="read aloud"):
        M.check_scene(d, sc, NAMES)
    ok = M.Dialogue.model_validate({"lines": [
        {"character": NAMES[i % 2], "text": "Fine words.','mood':'happy" if i == 3 else "Fine words."}
        for i in range(8)]})
    M.check_scene(ok, sc, NAMES)
    assert (ok.lines[3].text, ok.lines[3].mood) == ("Fine words.", "happy")


def test_a_one_word_lead_in_is_skipped_in_a_credit():
    from entertainment.movie_cards import role
    assert role("Twenty-three, the Wren's barmaid, working her last shift. Quick-witted.") == "the Wren's barmaid"


def test_a_cut_scene_stays_in_film_json_but_is_never_written_rendered_or_counted(monkeypatch, film):
    _stub(monkeypatch)
    done = M.write(film, world_mod.seed(), say=lambda s: None)
    done["cut"] = ["1.2", "2.3"]
    M.save(film, done)
    path = M.render(film, done, say=lambda s: None)
    cast, scenes = M.parse(path)
    n = M.ACTS * M.SCENES_PER_ACT - 2
    assert [s.number for s in scenes] == list(range(1, n + 1))           # numbered on, with no gaps
    assert "2 cut" in path.read_text(encoding="utf-8") and M.finished(M.load(film))
    del done["scenes"]["1.2"]                                            # a cut scene is never written again
    M.save(film, done)
    seen = _stub(monkeypatch)
    M.write(film, world_mod.seed(), say=lambda s: None)
    assert [s for _, s, _, _ in seen].count(M.Dialogue) == 0
