"""What documentaries establish reaches the rest of the station, and the night's documentary
repeats overnight at 02:00.
"""
import time

from newsroom import documentary, world as world_mod
from newsroom.config import CONFIG
from newsroom.models import Line, Segment, SegmentState, SegmentType

DOC = {"title": "One Engine, One Harbour", "date": "2026-10-27", "thread_id": "t058", "subject": "thread",
       "standfirst": "Can one engine protect the harbour?",
       "timeline": [{"date": "1871", "event": "Port Wexley is founded on the Greymouth coast.", "on_record": False},
                    {"date": "2026-10-26", "event": "The thread opens.", "on_record": True},
                    {"date": "Thursday 2026-10-29", "event": "Scheduled: the costing goes to committee.",
                     "on_record": False}]}


def _town():
    w = world_mod.seed()
    w.record_documentary(dict(DOC))
    return w


def test_writers_hear_the_history_and_not_what_the_documentary_expected():
    brief = _town().summary_for_prompt()
    assert "1871: Port Wexley is founded" in brief
    assert "Scheduled" not in brief and "The thread opens" not in brief


def test_the_desk_and_editors_get_each_documentary_in_full():
    ed = _town().summary_for_editor()
    assert "One Engine, One Harbour: Can one engine protect the harbour?" in ed
    assert "established: 1871" in ed and "established: Thursday 2026-10-29" in ed


def test_no_history_line_before_the_first_documentary():
    assert "Town history" not in world_mod.seed().summary_for_prompt()


def _at(hh: int, mm: int) -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hh, mm, 0, 0, 0, -1))


def test_the_night_documentary_repeats_once_after_two():
    w = _town()
    w.last_documentary_hash, w.last_documentary_aired_ts = "doc0001", _at(2, 5) - 5 * 3600
    assert not documentary.repeat_due(w, _at(1, 55))
    assert documentary.repeat_due(w, _at(2, 5))
    wav = CONFIG.paths.cache / "doc0001_00.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    wav.write_bytes(b"RIFF")
    seg = Segment(slot_id=1_000_001, type=SegmentType.documentary, state=SegmentState.ready, headline="One Engine",
                  lines=[Line(speaker="reporter", text="The harbour at night.", wav_path=str(wav), duration_s=2.0)],
                  work={"format": "documentary", "strand": "PORT WEXLEY STORIES"})
    (CONFIG.paths.cache / "doc0001.json").write_text(seg.model_dump_json(), encoding="utf-8")
    rep = documentary.load_repeat(w)
    assert rep.repeat and rep.work["strand"].endswith("REPEAT") and rep.content_hash == "doc0001"
    assert not documentary.repeat_due(w, _at(2, 10))          # once a night


def test_an_old_documentary_or_a_missing_file_isnt_repeated():
    w = _town()
    w.last_documentary_hash, w.last_documentary_aired_ts = "gone", _at(2, 5) - 30 * 3600
    assert not documentary.repeat_due(w, _at(2, 5))           # aired the night before last
    w.last_documentary_aired_ts = _at(2, 5) - 5 * 3600
    assert documentary.load_repeat(w) is None and not documentary.repeat_due(w, _at(2, 5))
