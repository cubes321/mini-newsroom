"""Marina Row, Channel 8's soap (entertainment/marina_row.py, docs/MARINA_ROW.md): the cast so far and its sets.
The engine is still to build."""
from __future__ import annotations

import pytest

from entertainment import marina_row
from newsroom import backdrops, locations, tts, world as world_mod


@pytest.fixture
def sets():
    by_id, marks = dict(locations.BY_ID), dict(locations.MARKS)
    marina_row.register_sets()
    yield
    locations.BY_ID.clear(), locations.BY_ID.update(by_id)
    locations.MARKS.clear(), locations.MARKS.update(marks)


def test_the_cast_is_six_characters_none_of_them_a_resident():
    w = world_mod.seed()
    assert len(marina_row.CAST) == 6 and len({p.actor for p in marina_row.CAST}) == 6
    for p in marina_row.CAST:
        assert w.person_by_name(p.character) is None                 # fiction: never in the town's people
        assert tts.clip_for(p.voice, "b") is None or tts.clip_for(p.voice, "b").exists()


def test_the_sets_are_drawn_from_their_art_and_kept_out_of_the_writers_places(sets):
    for sid, (_, _, marks) in marina_row.SETS.items():
        assert locations.get(sid).id == sid and locations.get(sid).kind == "studio"
        assert sid not in locations.BACKDROP_IDS and sid not in {l.id for l in locations.LOCATIONS}
        assert (backdrops.ART_DIR / f"{sid}.png").exists()
        assert backdrops.surface(sid).get_size() == (320, 180)
        assert set(marks) == {"a", "b", "c"} and locations.MARKS[sid] == marks


def test_without_registering_a_set_is_nobodys_place():
    assert "marina_row" not in locations.BY_ID and locations.get("marina_row").id == locations.DEFAULT_BACKDROP
