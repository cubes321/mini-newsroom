"""The content bank: finished films made ahead and kept, aired from a shelf with rules for how soon one repeats.

docs/ENGINE.md's idea (2026-10-28), built for the entertainment channel's cartoons (2026-11-07): the advert
pool, the continuity pool and the overnight repeats are each a one-off version of the same pattern. An item
is a video file with its soundtrack beside it as a WAV (the mixer plays the sound; the player draws the
frames, film.py), in a collection ("cartoons") and a series ("gully"), with a title and a length.

The shelf (data/bank/index.jsonl and the files) is made offline and only read on air. When each item aired
is the world's (World.bank_aired), so a scratch run's airings stay with its copy of the town.

    python -m newsroom.bank list
    python -m newsroom.bank ingest FILM.mp4 --collection cartoons --series gully --title "Gully's Kite"
"""
from __future__ import annotations

import json
import logging
import os
import random
import shutil
import subprocess
import zlib
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from pathlib import Path

log = logging.getLogger(__name__)

REST_DAYS = 7                  # an item doesn't come back within this many days, while another one can air
SOUND_RATE = 44100             # the soundtrack beside each film, at the mixer's rate (assets.MUSIC_SR)


@dataclass
class Item:
    id: str
    collection: str
    series: str
    title: str
    file: str                  # the video, relative to the bank's folder
    audio: str                 # its soundtrack as a WAV, likewise
    seconds: float
    made: str                  # YYYY-MM-DD
    episode: int = 0


def root() -> Path:
    """The project's data/bank (a scratch run's world is a copy elsewhere, but it airs the same shelf)."""
    return Path(os.environ.get("NEWSROOM_BANK") or Path(__file__).resolve().parent.parent / "data" / "bank")


def items(collection: str | None = None, series: str | None = None) -> list[Item]:
    """What's on the shelf, oldest first."""
    try:
        rows = [json.loads(l) for l in (root() / "index.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    except FileNotFoundError:
        return []
    return [Item(**r) for r in rows if (collection is None or r["collection"] == collection)
            and (not series or r["series"] == series)]


def pick(world, collection: str, series: str = "", now: float | None = None) -> Item | None:
    """The item to air next and its airing recorded: one not aired in REST_DAYS, the one aired longest ago
    (never first), the order among equals a draw on the day; None if the shelf is empty."""
    from . import schedule

    today = date.fromtimestamp(now or schedule.now())
    shelf = [i for i in items(collection, series) if (root() / i.file).exists() and (root() / i.audio).exists()]
    if not shelf:
        return None
    with world.lock:
        aired = {i.id: max(world.bank_aired.get(i.id, [""])) for i in shelf}
    rested = (today - timedelta(days=REST_DAYS)).isoformat()
    fresh = [i for i in shelf if aired[i.id] < rested] or shelf
    rng = random.Random(f"bank-{collection}-{today}")
    rng.shuffle(fresh)
    chosen = min(fresh, key=lambda i: aired[i.id])
    with world.lock:
        world.bank_aired[chosen.id] = (world.bank_aired.get(chosen.id, []) + [today.isoformat()])[-20:]
    log.info("bank: %s from %s (%s, %.0f s)", chosen.title, collection, chosen.series, chosen.seconds)
    return chosen


def path(item: Item, which: str = "file") -> Path:
    return root() / getattr(item, which)


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)


def seconds_of(video: Path) -> float:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                         capture_output=True, text=True, check=True).stdout.strip()
    return float(out)


def ingest(video: Path, collection: str, series: str, title: str, episode: int = 0) -> Item:
    """Put a finished film on the shelf: the video copied in, its soundtrack beside it at the mixer's rate."""
    key = f"{collection}/{series}/{title}"
    item_id = f"{collection}-{series}-{zlib.crc32(key.encode()) & 0xffffff:06x}"
    folder = root() / collection / series
    folder.mkdir(parents=True, exist_ok=True)
    film = folder / f"{item_id}{video.suffix}"
    shutil.copy2(video, film)
    sound = folder / f"{item_id}.wav"
    _ffmpeg("-i", str(film), "-vn", "-ac", "2", "-ar", str(SOUND_RATE), "-c:a", "pcm_s16le", str(sound))
    item = Item(id=item_id, collection=collection, series=series, title=title,
                file=film.relative_to(root()).as_posix(), audio=sound.relative_to(root()).as_posix(),
                seconds=round(seconds_of(film), 2), made=date.today().isoformat(), episode=episode)
    rows = [asdict(i) for i in items() if i.id != item_id] + [asdict(item)]
    (root() / "index.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    log.info("bank: on the shelf, %s (%s/%s, %.0f s)", title, collection, series, item.seconds)
    return item


def segment(seg, world):
    """A planned film slot made ready: an item from its collection (the show's) and series (the item's brief),
    the soundtrack as its one line and the film in its work for the player; the test card if the shelf is
    empty, so the slot is never dead air."""
    from .assets import testcard_segment
    from .models import Line, SegmentState, SegmentType

    collection = seg.work.get("collection") or "cartoons"
    item = (pick(world, collection, seg.brief or "", seg.nominal_start_ts)       # this series, else any
            or (pick(world, collection, "", seg.nominal_start_ts) if seg.brief else None))
    if item is None:
        log.info("bank: nothing in %s yet; the test card", collection)
        seg.type = SegmentType.testcard
        return testcard_segment(seg)
    seg.lines = [Line(speaker="anchor", text="", wav_path=path(item, "audio"), duration_s=item.seconds, mouth_env=[])]
    seg.work["film"] = str(path(item))
    seg.headline = item.title
    seg.state = SegmentState.ready
    return seg


def _cli() -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m newsroom.bank")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    i = sub.add_parser("ingest")
    i.add_argument("video", type=Path)
    i.add_argument("--collection", default="cartoons")
    i.add_argument("--series", required=True)
    i.add_argument("--title", required=True)
    i.add_argument("--episode", type=int, default=0)
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if a.cmd == "ingest":
        print(ingest(a.video, a.collection, a.series, a.title, a.episode))
    else:
        for it in items():
            print(f"{it.id}  {it.collection}/{it.series}  {it.seconds:6.1f}s  {it.made}  {it.title}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
