"""Guest casting: the script's age and accent hints pick a guest's voice, speed, look and
pronunciation; someone already cast keeps theirs."""
import dataclasses

import pytest

from newsroom import world as world_mod
from newsroom.config import CONFIG
from newsroom.models import InterviewScript, VoxLine
from newsroom.sprites import GREYS, guest_look


@pytest.mark.parametrize("said, age", [
    ("elderly", "old"), ("in her 70s", "old"), ("mid-40s", "middle"), (34, "middle"), ("20s", "young"),
    ("teenager", "young"), ("retired", "old"), ("Middle-aged", "middle"), ("", None), ("unknown", None),
])
def test_an_age_hint_in_the_models_words_becomes_a_band(said, age):
    assert VoxLine(speaker="guest", text="Hi.", guest_name="A B", guest_age=said).guest_age == age


@pytest.mark.parametrize("said, accent", [
    ("local", "british"), ("Cornish", "british"), ("British", "british"), ("American", "american"),
    ("Canadian", "american"), ("Australian", None), ("", None),
])
def test_an_accent_hint_becomes_british_or_american(said, accent):
    assert VoxLine(speaker="guest", text="Hi.", guest_name="A B", guest_accent=said).guest_accent == accent


def test_the_hints_are_lifted_off_the_first_guest_line():
    s = InterviewScript.model_validate({"headline": "A long life", "lower_third": "Keeper", "lines": [
        {"speaker": "late_host", "text": "Welcome."},
        {"speaker": "guest", "text": "Thank you.", "guest_name": "Ada Lowe", "guest_age": "old", "guest_accent": "local"}]})
    assert (s.guest_name, s.guest_age, s.guest_accent) == ("Ada Lowe", "old", "british")


def test_an_old_guest_speaks_slower_and_looks_it():
    w = world_mod.seed()
    old = [w.ensure_person(f"Albert Tanner {i}", "fisherman", gender="m", age="old") for i in range(30)]
    young = [w.ensure_person(f"Kai Rowe {i}", "apprentice", gender="m", age="young") for i in range(30)]
    assert max(p.speed for p in old) < min(p.speed for p in young)
    assert not {p.voice for p in young} & set(world_mod.OLD_VOICES_M)
    assert not {p.voice for p in old + young} & {c.voice for c in w.characters}   # am_santa is Hugh's now
    p = old[0]
    assert guest_look(p.name, p.voice, "resident", p.age).hair in GREYS


def test_a_guest_is_cast_from_voices_of_their_gender_and_age():
    """Since 2026-11-01: 24 DramaBox clips, each with a clip and a Kokoro voice. Four for each gender and age, but
    since 2026-11-04 one young clip of each gender is a teenager's, for teenagers only."""
    from newsroom import tts

    cast = tts._cast()
    for g in ("f", "m"):
        for age, n in (("young", 3), ("middle", 4), ("old", 4)):
            pool = world_mod.guest_pool(g, age)
            assert len(pool) == n and all(cast[v]["gender"] == g and cast[v]["age"] == age for v in pool)
    for v in world_mod.GUEST_VOICES:
        assert (tts.VOICES_DIR / f"{v}.b.wav").exists(), v
        assert tts.kokoro_voice(v)[:3] in ("af_", "bf_", "am_", "bm_") and tts.kokoro_voice(v) in (
            v, *(c["kokoro"] for c in [cast[v]] if "kokoro" in c))
    w = world_mod.seed()
    old = {w.ensure_person(f"Jory Tonkin {i}", "net mender", gender="m", age="old").voice for i in range(40)}
    assert old == set(world_mod.guest_pool("m", "old"))


def test_only_a_teenager_gets_a_teenagers_voice():
    """On 2026-11-03 a market stall repairer, cast as "young", spoke as a sixteen-year-old girl."""
    from newsroom import tts

    teens = {v for v, c in tts._cast().items() if c.get("age") == "teen"}
    assert teens == {"af_sky", "bm_jowan"}
    w = world_mod.seed()
    grown = {w.ensure_person(f"Ellie Marr {i}", "market stall repairer", gender=g, age=a).voice
             for i in range(40) for g in ("f", "m") for a in ("young", None)}
    assert not grown & teens
    assert w.ensure_person("Kerra Hosking", "Year 11 pupil, Wexley Academy", gender="f", age="young").voice == "af_sky"
    assert w.ensure_person("Jago Rowe", "sixth former", gender="m").voice == "bm_jowan"
    assert not world_mod.is_teen("canteen cook") and world_mod.is_teen("teenage skater")


def test_grown_ups_on_a_teenagers_voice_move_once(monkeypatch):
    w = world_mod.seed()
    adult = w.ensure_person("Hollie Brannan", "runs the Thursday skate and stitch club", gender="f", age="young")
    pupil = w.ensure_person("Tamsin Vear", "pupil, Wexley Academy", gender="f", age="young")
    adult.voice = "af_sky"                                    # as the town had her on 2026-11-03
    world_mod._recast_teen_voices(w)
    assert adult.voice in world_mod.guest_pool("f", "young") and pupil.voice == "af_sky"
    moved = adult.voice
    world_mod._recast_teen_voices(w)
    assert adult.voice == moved


def test_a_town_cast_on_thirteen_voices_is_spread_once_and_nobody_changes_gender():
    w = world_mod.seed()
    people = [w.ensure_person(f"Wenna Pascoe {i}", "baker", gender="f", age="young") for i in range(40)]
    for i, p in enumerate(people):
        p.voice = "bf_isabella" if i < 3 else "af_kore"       # as a town saved before 2026-11-01 had them
    w.guest_cast = ""
    doyle = w.person_by_name("Raymond Doyle").voice           # a seeded figure keeps his voice
    world_mod._recast_guests(w)
    assert {p.voice for p in people} == set(world_mod.guest_pool("f", "young")) and w.guest_cast
    assert w.person_by_name("Raymond Doyle").voice == doyle
    people[0].voice = "af_kore"
    world_mod._recast_guests(w)                               # once only: a later change is left alone
    assert people[0].voice == "af_kore"
    assert all(p.voice[1] == "f" for p in people)              # the look's gender comes from the voice


def test_the_continuity_announcer_is_never_a_guest():
    assert "bf_isabella" not in world_mod.GUEST_VOICES


def test_a_known_guest_keeps_their_voice_and_gets_an_age_if_they_had_none():
    w = world_mod.seed()
    p = w.ensure_person("Nell Hart", "baker", gender="f")
    voice, speed = p.voice, p.speed
    again = w.ensure_person("Nell Hart", "baker", gender="m", age="old", accent="american")
    assert again is p and (p.voice, p.speed, p.accent) == (voice, speed, "") and p.age == "old"


def test_british_pronunciation_only_when_switched_on_and_only_for_british_guests():
    w = world_mod.seed()
    w.ensure_person("Morag Penrose", "harbour pilot", gender="f", accent="british")
    w.ensure_person("Dwight Calder", "tourist", gender="m", accent="american")
    old = CONFIG.tts
    try:
        object.__setattr__(CONFIG, "tts", dataclasses.replace(old, british_guests=False))   # CONFIG is frozen
        assert w.lang_for("guest", "Morag Penrose") is None
        object.__setattr__(CONFIG, "tts", dataclasses.replace(old, british_guests=True))
        assert w.lang_for("guest", "Morag Penrose") == "b"
        assert w.lang_for("guest", "Dwight Calder") is None
        assert w.lang_for("anchor") is None
    finally:
        object.__setattr__(CONFIG, "tts", old)
