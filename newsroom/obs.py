"""Record the programmes, not the rolling news: drive OBS over its WebSocket, one file per programme,
named after it.

Two ways in:
- `python -m newsroom --obs`: the station feeds its own log lines to a recorder on a thread of its own
  (`attach`, `detach`), so a night needs one window.
- `tools/obs_record.py LOG`: follows a run's log file from another window, for a station that is
  already running.

A programme starts recording at its first segment (its own bumper) and stops at the next show's first,
so the news between programmes isn't recorded. Overnight, a programme's leftover segments fill the loop
between test cards; only a bumper (or a documentary) starts a recording, so those aren't recorded.
Adverts, ad breaks, continuity and a breaking-news interruption leave the recording as it is, so a
programme stays in one file. The documentary (Port Wexley Stories, which airs inside the news) is
recorded as a programme of its own, but not its overnight repeat, which made a second file of the same
film on 2026-11-01. SEVENTEXT, the overnight teletext pages, is recorded a little: the night's first
blocks (two by default, about four minutes), each a file of its own that ends at the next repeat or
test card. OBS's connection (port, password) is read from its own obs-websocket config; turn the
WebSocket server on in OBS.

The live stream is restarted at the times in config.toml's [stream] restart_at (StreamDirector), on
the first bumper, test card or teletext page at or after each: YouTube doesn't keep a stream longer
than 12 hours as a video, and an unkept stream's watch time doesn't count. Only OBS's own stream is
restarted; a second service sent by a plugin (Twitch, docs/STREAMING.md) carries on.
"""
from __future__ import annotations

import json
import logging
import os
import queue
import re
import threading
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import schedule
from .special import REPEAT_SLOT

log = logging.getLogger(__name__)

PLAYING = re.compile(r"(?:playing|replaying) slot (-?\d+) (\w+) \([^)]*\) \[([\w-]+)\]")
KEEP = {"advert", "ad_break", "continuity", "breaking", "filler"}      # never start or stop a recording
OPENERS = {"bumper", "documentary", "teletext"}    # a programme starts at its bumper; these have none
NOT_PROGRAMMES = {"news", "overnight"}
DOCUMENTARY = "Port Wexley Stories"
TELETEXT = "Seventext"


class Off(Exception):
    """OBS can't be reached: not running, or its WebSocket server is off."""


def programme(seg_type: str, show: str) -> str | None:
    """The programme a segment belongs to, or None for the rolling news (and the overnight repeats)."""
    if seg_type == "documentary":
        return DOCUMENTARY
    if seg_type == "teletext":
        return TELETEXT
    if show in NOT_PROGRAMMES or show == "-":
        return None
    try:
        return schedule.get(show).title.title()
    except Exception:  # noqa: BLE001
        return show


def obs_client():
    """A connection to OBS, from its own obs-websocket config (the password never leaves it)."""
    import obsws_python as obs

    cfg = Path(os.environ["APPDATA"]) / "obs-studio" / "plugin_config" / "obs-websocket" / "config.json"
    try:
        c = json.loads(cfg.read_text(encoding="utf-8"))
    except OSError as e:
        raise Off(f"no obs-websocket config at {cfg}") from e
    if not c.get("server_enabled"):
        raise Off("OBS's WebSocket server is off: Tools > WebSocket Server Settings > Enable")
    # obsws_python logs its connection parameters, password and all, at INFO (the 2026-11-03 night log)
    logging.getLogger("obsws_python").setLevel(logging.WARNING)
    try:
        return obs.ReqClient(host="localhost", port=c.get("server_port", 4455),
                             password=c.get("server_password", "") if c.get("auth_required") else "", timeout=10)
    except Exception as e:  # noqa: BLE001
        raise Off(f"OBS isn't answering on port {c.get('server_port', 4455)}: is it running?") from e


class Recorder:
    """Starts and stops OBS's recording and names each file; `dry` only says what it would do."""

    def __init__(self, dry: bool, say=print):
        self.dry, self.say, self.now, self.since = dry, say, None, datetime.now()
        self.ws = None if dry else obs_client()
        if self.ws:
            v = self.ws.get_version()
            self.say(f"OBS {v.obs_version}, recording to {self.ws.get_record_directory().record_directory}")

    def _connected(self):
        if self.ws is None and not self.dry:
            self.ws = obs_client()
        return self.ws

    def start(self, name: str) -> None:
        self.say(f"{datetime.now():%H:%M:%S} START {name}")
        self.now, self.since = name, datetime.now()
        if not self.dry:
            if self._connected().get_record_status().output_active:
                self.stop()
                self.now = name
            self.ws.start_record()

    def stop(self) -> None:
        name, self.now = self.now, None
        self.say(f"{datetime.now():%H:%M:%S} STOP  {name}")
        if self.dry:
            return
        out = self._connected().stop_record().output_path
        rename(Path(out), name, self.since, self.say)


def rename(path: Path, name: str, since: datetime, say=print) -> None:
    """'2026-10-30 21-30-02.mp4' -> '2026-10-30 21-30 Coastwide.mp4' (when it started), once OBS lets go."""
    safe = re.sub(r'[<>"/\\|?*]', "", re.sub(r"\s*:\s*", " - ", name))      # "Preview: São Paulo" -> "Preview - São Paulo"
    target = path.with_name(f"{since:%Y-%m-%d %H-%M} {safe}{path.suffix}")
    for _ in range(30):
        try:
            path.rename(target)
            say(f"          saved {target.name}")
            return
        except OSError:
            time.sleep(1)
    say(f"          left as {path.name} (couldn't rename)")


class Director:
    """Decides, segment by segment, when a programme's recording starts and stops."""

    def __init__(self, rec: Recorder, teletext: int = 2):
        self.rec, self.teletext_left = rec, teletext

    def line(self, text: str) -> None:
        """One log line (or message): acts on the "playing slot" ones."""
        m = PLAYING.search(text)
        if m:
            self.segment(int(m.group(1)), m.group(2), m.group(3))

    def segment(self, slot: int, seg_type: str, show: str) -> None:
        rec = self.rec
        if seg_type in KEEP:
            return
        if seg_type == "documentary" and slot == REPEAT_SLOT:   # last night's again: recorded when it first aired
            return
        if rec.now == TELETEXT and seg_type != "teletext":
            rec.stop()                                  # the pages end at the next repeat or card
        if seg_type == "teletext":
            if rec.now == TELETEXT or self.teletext_left <= 0:
                return
            self.teletext_left -= 1
        prog = programme(seg_type, show)
        if prog != rec.now:
            if prog and seg_type not in OPENERS:        # a leftover filling the overnight loop, not on air
                return
            if rec.now:
                rec.stop()
            if prog:
                rec.start(prog)

    def close(self) -> None:
        if self.rec.now:
            self.rec.stop()


BREAKS = {"bumper", "testcard", "teletext"}     # a restart's few seconds of nothing fall on one of these


class StreamDirector:
    """Restarts OBS's live stream at the configured times, on the next break in the programmes.

    `restart_at` is "HH:MM" on the broadcast clock (schedule.now, so --clock tests it). A time
    passed while nothing was a break is caught at the next one; several passed together make one
    restart. Times before the station started never count."""

    def __init__(self, ws, restart_at: list[str], gap_s: float = 5.0, say=print, clock=None, sleep=time.sleep):
        self.ws, self.say, self.gap_s, self.sleep = ws, say, gap_s, sleep
        self.clock = clock or schedule.now
        self.marks = sorted((int(h), int(m)) for h, m in (t.split(":") for t in restart_at))
        self.last = self.clock()

    def _due(self, now: float) -> bool:
        day = datetime.fromtimestamp(now).date()
        for d in (day - timedelta(days=1), day):
            for h, m in self.marks:
                at = datetime(d.year, d.month, d.day, h, m).timestamp()
                if self.last < at <= now:
                    return True
        return False

    def segment(self, slot: int, seg_type: str, show: str) -> None:
        if not self.marks or seg_type not in BREAKS:
            return
        now = self.clock()
        if self._due(now):
            self.last = now
            self.restart()

    def restart(self) -> None:
        ws = self.ws()
        if not ws.get_stream_status().output_active:
            self.say(f"{datetime.now():%H:%M:%S} stream restart due, but OBS isn't streaming; left alone")
            return
        self.say(f"{datetime.now():%H:%M:%S} RESTART the stream (YouTube keeps each part as a video)")
        ws.stop_stream()
        for _ in range(30):                         # OBS takes a moment to let go of the connection
            if not ws.get_stream_status().output_active:
                break
            self.sleep(1)
        self.sleep(self.gap_s)
        ws.start_stream()
        self.say(f"{datetime.now():%H:%M:%S} streaming again")


# --- the station's own recorder (`--obs`) ----------------------------------------------------------

_STOP = object()
_thread: threading.Thread | None = None
_queue: queue.Queue | None = None
_handler: logging.Handler | None = None


class _Feed(logging.Handler):
    """Passes the player's "playing slot" messages to the recorder's thread; never blocks the frame."""

    def emit(self, record: logging.LogRecord) -> None:
        msg = record.getMessage()
        if PLAYING.search(msg):
            _queue.put(msg)


def _run(q: queue.Queue, teletext: int, dry: bool) -> None:
    from .config import CONFIG

    say = lambda s: log.info("obs: %s", s.strip())      # noqa: E731
    try:
        director = Director(Recorder(dry, say), teletext)
    except Exception as e:  # noqa: BLE001
        log.warning("obs: not recording: %s", e)
        while q.get() is not _STOP:                     # drain until the station stops
            pass
        return
    stream = None
    if CONFIG.stream.restart_at and not dry:
        conn = {}                                       # its own connection, made when a restart is due
        stream = StreamDirector(lambda: conn.get("ws") or conn.setdefault("ws", obs_client()),
                                CONFIG.stream.restart_at, CONFIG.stream.gap_s, say)
        say(f"the stream restarts at the first break after {', '.join(CONFIG.stream.restart_at)}")
    while True:
        item = q.get()
        try:
            if item is _STOP:
                director.close()
                return
            director.line(item)
            if stream and (m := PLAYING.search(item)):
                stream.segment(int(m.group(1)), m.group(2), m.group(3))
        except Exception as e:  # noqa: BLE001
            log.warning("obs: %s (%s); carrying on", e, type(e).__name__)
            director.rec.ws = None                      # reconnect on the next start or stop
            if stream:
                conn.clear()


def attach(teletext: int = 2, dry: bool = False) -> None:
    """Record the programmes as the station plays them (the player's log is the cue)."""
    global _thread, _queue, _handler
    _queue = queue.Queue()
    _handler = _Feed()
    logging.getLogger("newsroom.player").addHandler(_handler)
    _thread = threading.Thread(target=_run, args=(_queue, teletext, dry), name="obs", daemon=True)
    _thread.start()


def detach(wait_s: float = 45.0) -> None:
    """Stop the programme being recorded and wait for OBS to save and the file to be renamed."""
    global _thread, _handler
    if _thread is None:
        return
    logging.getLogger("newsroom.player").removeHandler(_handler)
    _queue.put(_STOP)
    _thread.join(wait_s)
    _thread = _handler = None
