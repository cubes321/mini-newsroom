"""Recording the programmes in OBS: when a file starts and stops, the station's own feed (--obs), and
the sound output the station plays into."""
import logging
import time

import pytest

from newsroom import obs
from newsroom import __main__ as station
from newsroom.special import REPEAT_SLOT


class Fake:
    """A Recorder that writes down what it was told."""

    def __init__(self):
        self.now, self.calls = None, []

    def start(self, name):
        self.now = name
        self.calls.append(("start", name))

    def stop(self):
        self.calls.append(("stop", self.now))
        self.now = None


def line(slot, seg_type, show):
    return f"12:00:00 INFO  newsroom.player: playing slot {slot} {seg_type} (30.0s, 4 lines) [{show}]"


def run(*segments, teletext=2):
    rec = Fake()
    d = obs.Director(rec, teletext)
    for s in segments:
        d.line(line(*s))
    d.close()
    return rec.calls


def test_a_programme_runs_from_its_bumper_to_the_news():
    calls = run((1, "bumper", "quayside"), (2, "feature", "quayside"), (3, "advert", "-"),
                (4, "feature", "quayside"), (5, "headlines", "news"), (6, "headlines", "news"))
    assert calls == [("start", "Quayside"), ("stop", "Quayside")]


def test_the_next_show_starts_a_new_file():
    calls = run((1, "bumper", "quayside"), (2, "feature", "quayside"), (3, "bumper", "rockpool"))
    assert calls[:2] == [("start", "Quayside"), ("stop", "Quayside")]
    assert calls[2][0] == "start" and calls[2][1] != "Quayside"


def test_overnight_leftovers_and_the_documentary_repeat_are_not_recorded():
    assert run((1, "feature", "quayside"), (REPEAT_SLOT, "documentary", "news")) == []


def test_the_documentary_is_a_programme_of_its_own():
    assert run((1, "headlines", "news"), (7, "documentary", "news"), (8, "headlines", "news")) == [
        ("start", obs.DOCUMENTARY), ("stop", obs.DOCUMENTARY)]


def test_teletext_records_only_its_first_blocks():
    calls = run((1, "teletext", "overnight"), (2, "card", "overnight"), (3, "teletext", "overnight"),
                (4, "card", "overnight"), (5, "teletext", "overnight"), teletext=2)
    assert calls == [("start", obs.TELETEXT), ("stop", obs.TELETEXT)] * 2


@pytest.fixture
def fake_obs(monkeypatch):
    made = []

    def recorder(dry, say):
        made.append(Fake())
        return made[-1]

    monkeypatch.setattr(obs, "Recorder", recorder)
    yield made
    obs.detach(wait_s=5)


def test_the_station_feeds_its_own_recorder(fake_obs, caplog):
    caplog.set_level(logging.INFO, "newsroom.player")  # as the station's own logging is
    obs.attach()
    player = logging.getLogger("newsroom.player")
    player.info("%s slot %d %s (%.1fs, %d lines) [%s]%s", "playing", 1, "bumper", 30.0, 4, "quayside", "")
    player.info("buffer is fine")                   # not a cue
    obs.detach(wait_s=5)
    assert fake_obs[0].calls == [("start", "Quayside"), ("stop", "Quayside")]
    assert obs._handler is None and not any(isinstance(h, obs._Feed) for h in player.handlers)


def test_obs_being_off_never_stops_the_station(monkeypatch, caplog):
    def off(dry, say):
        raise obs.Off("OBS isn't answering")

    monkeypatch.setattr(obs, "Recorder", off)
    caplog.set_level(logging.INFO)
    obs.attach()
    logging.getLogger("newsroom.player").info("playing slot 1 bumper (30.0s, 4 lines) [quayside]")
    t0 = time.monotonic()
    obs.detach(wait_s=5)
    assert time.monotonic() - t0 < 5
    assert "not recording" in caplog.text


def test_obs_opened_after_the_station_is_found_at_a_later_break(monkeypatch, caplog):
    """The first look failing was final: OBS opened a minute late and nothing was recorded all night."""
    made, looks = [], []

    def recorder(dry, say):
        looks.append(1)
        if len(looks) < 3:
            raise obs.Off("OBS isn't answering")
        made.append(Fake())
        return made[-1]

    monkeypatch.setattr(obs, "Recorder", recorder)
    monkeypatch.setattr(obs, "RETRY_S", 0.0)
    monkeypatch.setattr(obs, "obs_client", lambda: (_ for _ in ()).throw(obs.Off("no OBS in a test")))
    caplog.set_level(logging.INFO)
    obs.attach()
    player = logging.getLogger("newsroom.player")
    player.info("playing slot 1 bulletin (30.0s, 4 lines) [news]")       # not a break: no look
    player.info("playing slot 2 bumper (30.0s, 4 lines) [quayside]")     # looks, still off
    player.info("playing slot 3 bulletin (30.0s, 4 lines) [quayside]")
    player.info("playing slot 4 bumper (30.0s, 4 lines) [outabout]")     # found: recording from this bumper
    obs.detach(wait_s=5)
    assert len(looks) == 3 and "not recording yet" in caplog.text
    assert made[0].calls == [("start", "Out And About"), ("stop", "Out And About")]


def test_the_obs_password_never_reaches_the_log(monkeypatch, tmp_path, caplog):
    import obsws_python

    cfg = tmp_path / "obs-studio" / "plugin_config" / "obs-websocket" / "config.json"
    cfg.parent.mkdir(parents=True)
    cfg.write_text('{"server_enabled": true, "auth_required": true, "server_password": "s3cret-pw"}')
    monkeypatch.setenv("APPDATA", str(tmp_path))

    def client(host, port, password, timeout):     # as the library does on connecting
        logging.getLogger("obsws_python.baseclient.ObsClient").info(
            f"Connecting with parameters: host='{host}' port={port} password='{password}'")
        return object()

    monkeypatch.setattr(obsws_python, "ReqClient", client)
    caplog.set_level(logging.INFO)
    obs.obs_client()
    assert "s3cret-pw" not in caplog.text


def test_an_output_is_picked_by_part_of_its_name():
    names = ["Headphones (Realtek USB Audio)", "CABLE Input (VB-Audio Virtual Cable)"]
    assert station.pick_output("CABLE Input", names) == names[1]
    assert station.pick_output("cable", names) == names[1]
    assert station.pick_output(names[0], names) == names[0]
    assert station.pick_output("Speakers", names) is None
