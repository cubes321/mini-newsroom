"""The archive is history only once a segment airs.

The writers' entry is made when the script is written, so the next writers see what is about to
air; the player's confirm makes it history. One that never airs (a failed voice, a skipped slot,
the buffer at shutdown) is dropped. PROJECT_REVIEW.md, finding 1.
"""
from newsroom import world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentState, SegmentType
from newsroom.player import Player

SAID = "Marjorie Pell said the harbour wall must come first."


def _written(w, h="h1", show="news"):
    w.record_aired("bulletin", "Harbour wall first", None, SAID, show=show, content_hash=h, aired=False)


def _pell(w):
    return w.person_by_name("Marjorie Pell")


def test_a_written_segment_is_not_yet_history_but_the_writers_see_it():
    w = world_mod.seed()
    before = _pell(w).appearances
    _written(w)
    assert w.archive[-1]["aired"] is False
    assert w.aired_today("bulletin", "news")[-1]["headline"] == "Harbour wall first"   # the next writer's memory
    assert all(e.get("hash") != "h1" for e in w.aired_archive())
    assert not w.search_archive("harbour wall first")                                 # the documentary's research
    assert _pell(w).appearances == before


def test_the_players_confirm_makes_it_history_once():
    w = world_mod.seed()
    before = _pell(w).appearances
    _written(w)
    for _ in range(2):
        w.confirm_aired("bulletin", "Harbour wall first", None, SAID, show="news", content_hash="h1")
    entries = [e for e in w.archive if e.get("hash") == "h1"]
    assert len(entries) == 1 and "aired" not in entries[0] and "ts" not in entries[0]
    assert _pell(w).appearances == before + 1


def test_a_segment_from_the_cache_gets_its_entry_when_it_airs():
    w = world_mod.seed()
    n = len(w.archive)
    w.confirm_aired("bulletin", "From the cache", None, "Words.", show="news", content_hash="cached")
    assert len(w.archive) == n + 1 and w.archive[-1]["headline"] == "From the cache"


def test_what_never_aired_is_dropped_after_the_hour_and_all_of_it_at_load():
    w = world_mod.seed()
    _written(w, "old")
    w.archive[-1]["ts"] -= world_mod.UNAIRED_KEEP_S + 1
    _written(w, "new")
    assert w.drop_unaired(older_than_s=world_mod.UNAIRED_KEEP_S) == 1
    assert [e["hash"] for e in w.archive if e.get("aired") is False] == ["new"]
    w.archive[-1]["ts"] += 86400                      # a later --clock in the last run: still dropped at load
    assert w.drop_unaired() == 1
    assert all(e.get("aired", True) for e in w.archive)


def test_an_unaired_entry_survives_a_save_and_goes_at_the_next_load(tmp_path, monkeypatch):
    w = world_mod.seed()
    _written(w)
    path = tmp_path / "w.json"
    world_mod.save(w, path)
    monkeypatch.setattr(world_mod, "_WORLD", None)
    back = world_mod.load(path)
    assert all(e.get("hash") != "h1" for e in back.archive)


def _bulletin(slot, h, **kw):
    return Segment(slot_id=slot, type=SegmentType.bulletin, show="news", headline="Harbour wall first",
                   content_hash=h, state=SegmentState.playing,
                   lines=[Line(speaker="anchor", text=SAID, duration_s=3.0)], **kw)


def test_the_player_confirms_what_it_finishes_but_not_a_repeat_or_a_break():
    w = world_mod.seed()
    _written(w)
    pl = Player(Buffer(), w, producer=None, audio=False)
    pl.current = _bulletin(5, "h1")
    pl._finish(0.0)
    assert all(e.get("aired", True) for e in w.archive if e.get("hash") == "h1")
    n = len(w.archive)
    pl.current = _bulletin(6, "elsewhere", repeat=True)
    pl._finish(0.0)
    pl.current = Segment(slot_id=7, type=SegmentType.ad_break, content_hash="brk", state=SegmentState.playing,
                         lines=[Line(speaker="anchor", text="Adverts.", duration_s=1.0)])
    pl._finish(0.0)
    assert len(w.archive) == n
