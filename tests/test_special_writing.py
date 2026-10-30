"""What a special's section writer is told, from reading Flash's first night of specials (2026-10-30):
planned steps are marked as not yet happened, each section sees what the piece has already said, the
location is a note, and a speaker label written into the text is not read out.

No model or TTS calls: the writers are stubbed.
"""
from __future__ import annotations

from newsroom import documentary, special
from newsroom.models import Line, ScriptLine, SpecialSection
from test_special import _commission, _outline, _story, tmp_paths, world  # noqa: F401  (fixtures)


def test_the_planned_step_is_marked_as_not_yet_happened(world):
    tid = _story(world)
    world.thread(tid).next_development = "On Saturday Marjorie collects the shoebox."
    record = special.story_so_far(world, tid)
    assert "Planned next (has NOT happened" in record and "On Saturday Marjorie collects the shoebox." in record
    for system in (special._SECTION_SYSTEM, documentary.SECTION_SYSTEM):
        assert "WHAT HAS NOT HAPPENED" in system and "ALREADY SAID" in system and "LOCATION" in system


def test_a_section_sees_what_the_piece_has_said(world, monkeypatch):
    seg = _commission(world)
    seg.lines = [Line(speaker="anchor", text="Tonight, a petition."),
                 Line(speaker="reporter", text="Eighty-one years on Harbour Row."),
                 Line(speaker="guest", text="My mother danced.", guest_name="Winifred Cobb"),
                 Line(speaker="reporter", text="", archive="Archive · 1952")]
    seen = []
    monkeypatch.setattr(special.llm, "complete_json", lambda task, schema, system, user: seen.append(user) or
                        SpecialSection(lines=[ScriptLine(speaker="reporter", text="On the quay.")]))
    special.write_section(seg, world, _outline(), 1, 120)
    said = seen[0].split("ALREADY SAID in this piece, oldest first:\n")[1]
    assert said.splitlines() == ["  Dana Ferris: Tonight, a petition.", "  Miles Okafor: Eighty-one years on Harbour Row.",
                                 "  Winifred Cobb: My mother danced."]
    assert "Location: Harrow Street market." in seen[0] and "striped stalls" not in seen[0]


def test_a_long_piece_keeps_the_newest_of_what_it_said(world, monkeypatch):
    seg = _commission(world)
    seg.lines = [Line(speaker="reporter", text=f"line {i} " + "word " * 200) for i in range(20)]
    said = special._already_said(seg, world)
    assert "line 19 " in said and "line 0 " not in said
    assert len(said.split()) < special.ALREADY_SAID_WORDS + 200


def test_the_first_section_has_nothing_already_said(world):
    seg = _commission(world)
    seg.lines = []
    assert special._already_said(seg, world) == ""


def test_a_speaker_label_is_not_read_out(world):
    assert special.spoken("Dana: Tonight, a small story.", world) == "Tonight, a small story."
    assert special.spoken("Miles Okafor: On the quay.", world) == "On the quay."
    assert special.spoken("Anchor: Good evening.", world) == special.spoken("ANCHOR: Good evening.", world) == "Good evening."
    assert special.spoken("Winifred: Eighty-one years.", world, "Winifred Cobb") == "Eighty-one years."
    assert special.spoken("Look: the wall is moving.", world) == "Look: the wall is moving."
    assert special.spoken("Monday: the council sits.", world) == "Monday: the council sits."


def test_labels_come_off_the_intro_outro_and_lines(world, monkeypatch):
    seg = _commission(world)
    o = _outline().model_copy(update={"intro": "Dana: Tonight, a petition.", "outro": "Dana: Good night."})
    monkeypatch.setattr(special, "write_outline", lambda s, w: o)
    special.advance(seg, world)                       # outline
    monkeypatch.setattr(special, "write_section", lambda s, w, outline, i, words: SpecialSection(
        lines=[ScriptLine(speaker="reporter", text="Miles: On the quay.")]))
    for _ in range(3):
        special.advance(seg, world)
    assert [l.text for l in seg.lines] == ["Tonight, a petition.", "On the quay.", "On the quay.", "On the quay.",
                                           "Good night."]
