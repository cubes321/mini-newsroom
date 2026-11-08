"""tools/shorts.py: trimming a segment to some of its lines, and timing the captions. No ffmpeg, no pygame."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import pytest

from newsroom.models import Line, Segment, SegmentType, VisualCue

_spec = importlib.util.spec_from_file_location("shorts", Path(__file__).resolve().parent.parent / "tools" / "shorts.py")
shorts = importlib.util.module_from_spec(_spec)
sys.modules["shorts"] = shorts                         # @dataclass looks its module up there
_spec.loader.exec_module(shorts)


def seg(durations, cues=()):
    lines = [Line(speaker="mag_a" if i % 2 == 0 else "mag_b", text=f"line {i} " + "word " * 5, duration_s=d)
             for i, d in enumerate(durations)]
    return Segment(slot_id=3, type=SegmentType.interview, lines=lines,
                   cues=[VisualCue(at_s=a, kind=k, payload=p) for a, k, p in cues])


def test_trim_keeps_the_lines_asked_for():
    s = shorts.trim(seg([2.0, 3.0, 4.0, 5.0]), 1, 2)
    assert [l.text.split()[1] for l in s.lines] == ["1", "2"]
    assert s.duration_s == 7.0


def test_trim_shifts_cues_and_carries_state_in():
    s = seg([2.0, 3.0, 4.0, 5.0], cues=[
        (0.0, "backdrop", {"backdrop": "harbour"}),        # before the cut: carried in at 0
        (0.0, "lower_third", {"title": "Pat"}),
        (1.5, "lower_third", {}),                          # the later one of its kind wins
        (6.0, "lower_third", {"title": "Ruby"}),           # inside: moved back by 2.0
        (9.5, "map_state", {"state": "rain"}),             # after the clip (ends at 9.0): dropped
    ])
    t = shorts.trim(s, 1, 2)
    got = sorted((c.at_s, c.kind, c.payload) for c in t.cues)
    assert got == [(0.0, "backdrop", {"backdrop": "harbour"}), (0.0, "lower_third", {}),
                   (4.0, "lower_third", {"title": "Ruby"})]
    assert len(s.cues) == 5                                # the original is untouched


def test_trim_a_cue_on_the_cut_belongs_to_the_clip():
    t = shorts.trim(seg([2.0, 3.0], cues=[(2.0, "backdrop", {"backdrop": "quay"})]), 1, 1)
    assert [(c.at_s, c.payload) for c in t.cues] == [(0.0, {"backdrop": "quay"})]


def test_trim_from_the_start_moves_nothing():
    t = shorts.trim(seg([2.0, 3.0, 4.0], cues=[(0.0, "backdrop", {"backdrop": "a"}), (2.5, "chapter", {})]), 0, 1)
    assert sorted((c.at_s, c.kind) for c in t.cues) == [(0.0, "backdrop"), (2.5, "chapter")]


@pytest.mark.parametrize("first, last", [(-1, 1), (2, 1), (0, 4)])
def test_trim_refuses_lines_that_arent_there(first, last):
    with pytest.raises(ValueError):
        shorts.trim(seg([1.0, 1.0, 1.0]), first, last)


def test_lines_play_back_to_back():
    lines = seg([2.0, 3.0, 4.0]).lines
    starts = shorts.line_starts(lines)
    assert starts == [0.0, 2.0, 5.0]
    assert [shorts.line_at(starts, t) for t in (0.0, 1.99, 2.0, 4.9, 5.0, 8.9)] == [0, 0, 1, 1, 2, 2]


measure = len                                              # a character is a pixel


def test_wrap_fills_rows_greedily():
    assert shorts.wrap("aa bb cc dd", 5, measure) == ["aa bb", "cc dd"]
    assert shorts.wrap("supercalifragilistic is long", 6, measure) == ["supercalifragilistic", "is", "long"]


def test_pages_split_evenly():
    rows = [f"r{i}" for i in range(5)]
    assert shorts.pages(rows, 4) == [["r0", "r1", "r2"], ["r3", "r4"]]
    assert shorts.pages(rows[:3], 4) == [rows[:3]]


def test_captions_follow_the_lines():
    lines = [Line(speaker="mag_a", text="short one", duration_s=2.0),
             Line(speaker="mag_b", text="and another", duration_s=3.0)]
    caps = shorts.captions(lines, ["Pat", "Clive"], 40, measure)
    assert [(c.start, c.end, c.name, c.rows) for c in caps] == [
        (0.0, 2.0, "Pat", ["short one"]), (2.0, 5.0, "Clive", ["and another"])]
    assert shorts.caption_at(caps, 1.0).name == "Pat"
    assert shorts.caption_at(caps, 2.0).name == "Clive"
    assert shorts.caption_at(caps, 5.0) is None            # the slate has none


def test_a_long_line_pages_by_its_words():
    # 9 rows of 1 word at 2 rows a page: pages of 2,2,2,2,1 words, over 9 seconds
    words = " ".join(f"w{i}" for i in range(9))
    lines = [Line(speaker="guest", guest_name="Ruby Hollins", text=words, duration_s=9.0)]
    caps = shorts.captions(lines, ["Ruby Hollins"], 3, measure, max_rows=2)
    assert [len(c.rows) for c in caps] == [2, 2, 2, 2, 1]
    assert [round(c.end - c.start, 6) for c in caps] == [2.0, 2.0, 2.0, 2.0, 1.0]
    assert caps[0].start == 0.0 and caps[-1].end == 9.0


def test_speakers_get_colours_in_order_and_guests_by_name():
    lines = [Line(speaker="host_b", text="a"), Line(speaker="guest", guest_name="Lorna", text="b"),
             Line(speaker="guest", guest_name="Tam", text="c"), Line(speaker="host_b", text="d")]
    c = shorts.speaker_colours(lines)
    assert list(c) == ["host_b", "guest:Lorna", "guest:Tam"]
    assert len(set(c.values())) == 3
