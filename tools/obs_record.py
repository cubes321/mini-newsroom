"""Record the programmes, not the rolling news: follow a run's log and drive OBS over its WebSocket, one file
per programme, named after it.

    uv run --with obsws-python python tools/obs_record.py data/night-2026-10-30.log

Start it before (or after) the run; it follows the log from its end, waiting for the file to appear. A
programme starts recording at its first segment (its own bumper) and stops at the next show's first,
so the news between programmes isn't recorded. Overnight, a programme's leftover segments fill the loop
between test cards; only a bumper (or a documentary) starts a recording, so those aren't recorded. Adverts, ad breaks, continuity and a breaking-news
interruption leave the recording as it is, so a programme stays in one file. The documentary (Port
Wexley Stories, which airs inside the news) is recorded as a programme of its own. OBS's connection
(port, password) is read from its own obs-websocket config; turn the WebSocket server on in OBS.
`--dry-run` prints what it would do without touching OBS; `--from-start` reads the log from the top.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from newsroom import schedule  # noqa: E402

PLAYING = re.compile(r"(?:playing|replaying) slot -?\d+ (\w+) \([^)]*\) \[([\w-]+)\]")
KEEP = {"advert", "ad_break", "continuity", "breaking", "filler"}      # never start or stop a recording
OPENERS = {"bumper", "documentary"}      # a programme starts at its bumper; the documentary has none
NOT_PROGRAMMES = {"news", "overnight"}
DOCUMENTARY = "Port Wexley Stories"


def programme(seg_type: str, show: str) -> str | None:
    """The programme a segment belongs to, or None for the rolling news (and the overnight repeats)."""
    if seg_type == "documentary":
        return DOCUMENTARY
    if show in NOT_PROGRAMMES or show == "-":
        return None
    try:
        return schedule.get(show).title.title()
    except Exception:  # noqa: BLE001
        return show


def obs_client():
    import obsws_python as obs

    cfg = Path(os.environ["APPDATA"]) / "obs-studio" / "plugin_config" / "obs-websocket" / "config.json"
    c = json.loads(cfg.read_text(encoding="utf-8"))
    if not c.get("server_enabled"):
        sys.exit("OBS's WebSocket server is off: Tools > WebSocket Server Settings > Enable")
    return obs.ReqClient(host="localhost", port=c.get("server_port", 4455),
                         password=c.get("server_password", "") if c.get("auth_required") else "", timeout=10)


class Recorder:
    def __init__(self, dry: bool):
        self.dry, self.now, self.since = dry, None, datetime.now()
        self.ws = None if dry else obs_client()
        if self.ws:
            v = self.ws.get_version()
            print(f"OBS {v.obs_version}, recording to {self.ws.get_record_directory().record_directory}", flush=True)

    def _connected(self):
        if self.ws is None and not self.dry:
            self.ws = obs_client()
        return self.ws

    def start(self, name: str) -> None:
        print(f"{datetime.now():%H:%M:%S} START {name}", flush=True)
        self.now, self.since = name, datetime.now()
        if not self.dry:
            if self._connected().get_record_status().output_active:
                self.stop()
                self.now = name
            self.ws.start_record()

    def stop(self) -> None:
        name, self.now = self.now, None
        print(f"{datetime.now():%H:%M:%S} STOP  {name}", flush=True)
        if self.dry:
            return
        out = self._connected().stop_record().output_path
        rename(Path(out), name, self.since)


def rename(path: Path, name: str, since: datetime) -> None:
    """'2026-10-30 21-30-02.mp4' -> '2026-10-30 21-30 Coastwide.mp4' (when it started), once OBS lets go."""
    target = path.with_name(f"{since:%Y-%m-%d %H-%M} {name}{path.suffix}")
    for _ in range(30):
        try:
            path.rename(target)
            print(f"          saved {target.name}", flush=True)
            return
        except OSError:
            time.sleep(1)
    print(f"          left as {path.name} (couldn't rename)", flush=True)


def follow(log: Path, from_start: bool):
    """Each new line of the log as it is written; waits for the file to exist."""
    while not log.exists():
        time.sleep(2)
    with log.open("r", encoding="utf-8", errors="replace") as f:
        if not from_start:
            f.seek(0, os.SEEK_END)
        while True:
            line = f.readline()
            if line:
                yield line
            else:
                time.sleep(0.5)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("log", type=Path)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--from-start", action="store_true")
    a = ap.parse_args()
    rec = Recorder(a.dry_run)
    print(f"following {a.log}", flush=True)
    try:
        for line in follow(a.log, a.from_start):
            if "exit: worst p99" in line:                   # the run has ended
                break
            m = PLAYING.search(line)
            if not m or m.group(1) in KEEP:
                continue
            prog = programme(m.group(1), m.group(2))
            if prog != rec.now:
                if prog and m.group(1) not in OPENERS:      # a leftover filling the overnight loop, not on air
                    continue
                if rec.now:
                    rec.stop()
                if prog:
                    rec.start(prog)
    except KeyboardInterrupt:
        pass
    finally:
        if rec.now:
            rec.stop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
