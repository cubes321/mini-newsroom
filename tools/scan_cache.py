"""Look through everything already voiced for words that mustn't go on air (newsroom/safety.py).

Cached segments, overnight repeats, adverts and continuity items replay their wavs as they are,
so the check in tts.synthesize never sees them again. Run this once before going public, and
after adding terms to the list.

    uv run python tools/scan_cache.py            # list what would be kept off air
    uv run python tools/scan_cache.py --move     # move it (json and wavs) to data/quarantine/

The folders follow config.toml and the NEWSROOM_* overrides, so a scratch copy can be scanned too.
"""
from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from newsroom import safety  # noqa: E402
from newsroom.config import CONFIG  # noqa: E402


def companions(js: Path, data: dict) -> list[Path]:
    """The json's wavs: the ones it names, and any beside it under its own name."""
    named = {Path(p) for p in _wav_paths(data)}
    beside = set(js.parent.glob(f"{js.stem}_*.wav"))
    return sorted(p for p in named | beside if p.exists() and p.parent == js.parent)


def _wav_paths(obj) -> list[str]:
    if isinstance(obj, dict):
        return [v for k, v in obj.items() if k == "wav_path" and isinstance(v, str)] + \
               [p for v in obj.values() for p in _wav_paths(v)]
    if isinstance(obj, list):
        return [p for v in obj for p in _wav_paths(v)]
    return []


def scan(folders: list[Path]) -> list[tuple[Path, str, str]]:
    """(json, term, the text it was in) for every blocked item in `folders`."""
    hits = []
    for folder in folders:
        for js in sorted(folder.glob("*.json")) if folder.exists() else []:
            try:
                data = json.loads(js.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                continue
            for text in safety.strings(data):
                if bad := safety.check(text):
                    hits.append((js, bad, text))
                    break
    return hits


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--move", action="store_true", help="move each hit and its wavs to data/quarantine/")
    args = ap.parse_args(argv)
    folders = [CONFIG.paths.cache, CONFIG.paths.ads, CONFIG.paths.continuity]
    hits = scan(folders)
    for js, bad, text in hits:
        print(f"{js}: {bad!r} in {text[:100]!r}")
    print(f"{len(hits)} item(s) with a blocked word in {', '.join(str(f) for f in folders)}")
    if args.move and hits:
        for js, _, _ in hits:
            dest = CONFIG.paths.data / "quarantine" / js.parent.name
            dest.mkdir(parents=True, exist_ok=True)
            data = json.loads(js.read_text(encoding="utf-8"))
            for f in [js, *companions(js, data)]:
                shutil.move(str(f), dest / f.name)
        print(f"moved to {CONFIG.paths.data / 'quarantine'}")
    return 1 if hits and not args.move else 0


if __name__ == "__main__":
    sys.exit(main())
