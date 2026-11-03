"""Record the programmes from another window: follow a run's log and drive OBS, one file per programme.

    uv run python tools/obs_record.py data/night-2026-10-30.log

The station can do this itself with `python -m newsroom --obs`; this is for one that's already running.
Start it before (or after) the run; it follows the log from its end, waiting for the file to appear, and
stops when the run ends. What it records, and how, is in `newsroom/obs.py`. `--dry-run` prints what it
would do without touching OBS; `--from-start` reads the log from the top.
"""
from __future__ import annotations

import argparse
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from newsroom.obs import Director, Off, Recorder, obs_client  # noqa: E402,F401  (obs_client: for scripts)

say = lambda s: print(s, flush=True)                    # noqa: E731


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
    ap.add_argument("--teletext", type=int, default=2, help="record this many blocks of SEVENTEXT (default 2)")
    a = ap.parse_args()
    try:
        director = Director(Recorder(a.dry_run, say), a.teletext)
    except Off as e:
        sys.exit(str(e))
    say(f"following {a.log}")
    try:
        for line in follow(a.log, a.from_start):
            if "exit: worst p99" in line:                   # the run has ended
                break
            director.line(line)
    except KeyboardInterrupt:
        pass
    finally:
        director.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
