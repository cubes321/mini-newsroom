"""Restarting OBS's live stream at the configured times, on a break (obs.StreamDirector).

OBS is a stub: no WebSocket, no sleeping.
"""
from datetime import datetime
from types import SimpleNamespace

from newsroom import obs


class FakeOBS:
    def __init__(self, live=True):
        self.live, self.calls = live, []

    def get_stream_status(self):
        return SimpleNamespace(output_active=self.live)

    def stop_stream(self):
        self.calls.append("stop")
        self.live = False

    def start_stream(self):
        self.calls.append("start")
        self.live = True


def _at(hh, mm, day=8):
    return datetime(2026, 11, day, hh, mm).timestamp()


def _director(fake, clock):
    return obs.StreamDirector(lambda: fake, ["00:00", "09:00", "19:00"], gap_s=5, say=lambda s: None,
                              clock=lambda: clock[0], sleep=lambda s: None)


def test_it_restarts_on_the_first_break_after_the_time_once():
    fake, clock = FakeOBS(), [_at(8, 30)]
    d = _director(fake, clock)
    clock[0] = _at(8, 59)
    d.segment(1, "bumper", "news")
    assert fake.calls == []                               # not yet 09:00
    clock[0] = _at(9, 1)
    d.segment(2, "bulletin", "news")
    assert fake.calls == []                               # not a break
    d.segment(3, "bumper", "phonein")
    assert fake.calls == ["stop", "start"]
    clock[0] = _at(9, 30)
    d.segment(4, "bumper", "news")
    assert fake.calls == ["stop", "start"]                # once per time


def test_across_midnight_and_never_for_a_time_before_the_start():
    fake, clock = FakeOBS(), [_at(19, 30)]
    d = _director(fake, clock)                            # started after 19:00: that one doesn't count
    d.segment(1, "bumper", "late")
    assert fake.calls == []
    clock[0] = _at(0, 2, day=9)
    d.segment(2, "testcard", "overnight")
    assert fake.calls == ["stop", "start"]


def test_not_streaming_is_left_alone():
    fake, clock = FakeOBS(live=False), [_at(18, 0)]
    d = _director(fake, clock)
    clock[0] = _at(19, 5)
    d.segment(1, "bumper", "coastwide")
    assert fake.calls == []


class Flaky(FakeOBS):
    """OBS that fails where it is told to, once."""

    def __init__(self, fail, live=True):
        super().__init__(live)
        self.fail = fail

    def _maybe(self, what):
        if self.fail == what:
            self.fail = None
            raise ConnectionError(f"{what}: no answer")

    def get_stream_status(self):
        self._maybe("status")
        return super().get_stream_status()

    def start_stream(self):
        self._maybe("start")
        super().start_stream()


def test_a_restart_that_fails_is_tried_again_at_the_next_break():
    """self.last was set before the attempt: one refused connection at 09:00 and the stream ran on to
    19:00, past the twelve hours YouTube keeps."""
    import pytest

    fake, clock = Flaky("status"), [_at(8, 30)]
    d = _director(fake, clock)
    clock[0] = _at(9, 1)
    with pytest.raises(ConnectionError):
        d.segment(1, "bumper", "phonein")
    assert fake.calls == []
    clock[0] = _at(9, 6)
    d.segment(2, "bumper", "news")
    assert fake.calls == ["stop", "start"]
    clock[0] = _at(9, 30)
    d.segment(3, "bumper", "news")
    assert fake.calls == ["stop", "start"]                # and then once, as before


def test_a_stream_it_stopped_and_couldnt_start_is_started_at_the_next_break():
    import pytest

    fake, clock = Flaky("start"), [_at(8, 30)]
    d = _director(fake, clock)
    clock[0] = _at(9, 1)
    with pytest.raises(ConnectionError):
        d.segment(1, "bumper", "phonein")
    assert fake.calls == ["stop"] and not fake.live and d.ours
    clock[0] = _at(9, 6)
    d.segment(2, "bumper", "news")
    assert fake.calls == ["stop", "start"] and fake.live and not d.ours     # not "left alone": it was ours
    clock[0] = _at(9, 12)
    d.segment(3, "bumper", "news")
    assert fake.calls == ["stop", "start"]


def test_keep_alive_starts_a_stream_found_stopped_at_any_break():
    fake, clock = FakeOBS(live=False), [_at(10, 0)]
    d = obs.StreamDirector(lambda: fake, [], say=lambda s: None, clock=lambda: clock[0], sleep=lambda s: None,
                           keep_alive=True)
    d.segment(1, "bulletin", "news")
    assert fake.calls == []                               # not on a programme: at a break
    d.segment(2, "bumper", "news")
    assert fake.calls == ["start"]
    d.segment(3, "bumper", "news")
    assert fake.calls == ["start"]                        # streaming: nothing to do
