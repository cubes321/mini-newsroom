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
