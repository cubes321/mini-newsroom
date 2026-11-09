"""The frame loop's guard (__main__.Guard): one part of a frame failing is logged and the station carries
on; a part that keeps failing has the player drop what it is stuck on. And the last jobs at exit each run
whatever happened to the one before.

No window, no audio, no model: the parts are plain functions.
"""
from newsroom import __main__ as main
from newsroom import adverts, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentState, SegmentType
from newsroom.player import Player
from newsroom.producer import Producer


def _boom(*_):
    raise RuntimeError("a bad frame")


class _Player:
    def __init__(self):
        self.drops = []

    def drop(self, now, why, *, or_skip=False):
        self.drops.append(or_skip)


def test_a_failed_part_is_logged_and_the_next_frame_runs(caplog):
    g = main.Guard()
    assert g.run("player", _boom, 1.0) is None
    assert "the player failed" in caplog.text and "a bad frame" in caplog.text      # with its traceback
    assert g.run("player", lambda now: now * 2, 2.0) == 4.0
    assert g.errors == 1 and g.fails["player"] == 0
    assert "working again" in caplog.text


def test_a_run_of_failures_is_logged_once_not_every_frame(caplog):
    g = main.Guard()
    for _ in range(20):
        g.run("producer", _boom)
    assert caplog.text.count("the producer failed") == 1 and g.fails["producer"] == 20


def test_a_stuck_player_drops_what_is_on_then_asks_less_often():
    p = _Player()
    g = main.Guard(p)
    for _ in range(main.Guard.DROP_AFTER - 1):
        g.run("player", _boom)
    assert p.drops == []
    for _ in range(main.Guard.DROP_AFTER * 3 + 6):       # failures 30..125: dropped at 30, 60 and 120
        g.run("player", _boom)
    assert p.drops == [True, True, True]
    g.run("player", lambda: None)                        # working again: the count starts afresh
    for _ in range(main.Guard.DROP_AFTER):
        g.run("player", _boom)
    assert len(p.drops) == 4


def test_a_picture_that_wont_draw_drops_the_segment_once_and_the_sound_carries_on():
    p = _Player()
    g = main.Guard(p)
    for _ in range(main.Guard.DROP_AFTER * 10):
        g.run("picture", _boom)
    assert p.drops == [False]                            # never the next slot: it isn't the rundown's fault
    for _ in range(main.Guard.DROP_AFTER * 10):
        g.run("producer", _boom)
    assert p.drops == [False]                            # the producer has nothing on air to drop


def test_a_drop_that_fails_is_logged_too(caplog):
    class Broken:
        def drop(self, *a, **k):
            raise RuntimeError("no way out")

    g = main.Guard(Broken())
    for _ in range(main.Guard.DROP_AFTER):
        assert g.run("player", _boom) is None
    assert "could not drop" in caplog.text


def test_the_last_jobs_each_run_whatever_happened_before(caplog):
    done = []
    main.shut_down([("the recorder", _boom), ("the workers", lambda: done.append("workers")),
                    ("the world's save", lambda: done.append("save"))])
    assert done == ["workers", "save"] and "exit: the recorder failed" in caplog.text


# --- the player's side: what dropping does -----------------------------------------------------------


def _segment(buf, slot, state=SegmentState.ready):
    seg = Segment(slot_id=slot, type=SegmentType.bulletin, headline=f"Story {slot}",
                  lines=[Line(speaker="anchor", text="Good evening.", duration_s=4.0)])
    buf.submit(seg)
    if state is not SegmentState.planned:
        buf.mark(seg, state)
    return seg


def _player(tmp_path):
    buf = Buffer()
    return buf, Player(buf, world_mod.seed(), Producer(buf, 600), audio=False, ads=adverts.AdPool(tmp_path / "ads"))


def test_dropping_takes_the_segment_off_and_the_next_slot_follows(tmp_path):
    buf, pl = _player(tmp_path)
    first, second = _segment(buf, 0), _segment(buf, 1)
    now = 1_000_000.0
    pl.update(now)
    assert pl.current is first
    pl.drop(now + 1, "the player failed 30 frames in a row", or_skip=True)
    assert pl.current is None and pl.next_slot == 1 and buf.state_of(0) is SegmentState.done
    assert buf.state_of(1) is SegmentState.ready         # only what was on air: the next slot isn't skipped too
    pl.update(now + 2)
    assert pl.current is second


def test_with_nothing_on_air_it_is_the_slot_that_wont_start_that_is_skipped(tmp_path):
    buf, pl = _player(tmp_path)
    _segment(buf, 0)
    second = _segment(buf, 1)
    now = 1_000_000.0
    pl.drop(now, "the picture failed", or_skip=False)    # the picture's fault: the rundown is left alone
    assert buf.state_of(0) is SegmentState.ready
    pl.drop(now, "the player failed 30 frames in a row", or_skip=True)
    assert buf.state_of(0) is SegmentState.failed
    pl.update(now + 1)                                   # skips the failed slot
    pl.update(now + 2)
    assert pl.current is second
