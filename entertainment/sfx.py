"""Sound effects for the cartoons, made with the Stable Audio 3 Pinokio app (its small-sfx model): the user's
idea for the puppets (2026-11-09), "some of it should happen off-screen with another character looking at it
and sound effects". A shot names its effects in a few words ("a metal bucket clanging off a wall"); each is
made once into the series' sound/sfx/ and shared by every episode after.

    python -m entertainment.cartoons sfx data/cartoons/gully/<ep> [--url http://127.0.0.1:7860]

GPU, and the app must be running (the user starts it). Each take is asked for two seconds longer than
needed (the model fades out early) and trimmed of its trailing quiet.
"""
from __future__ import annotations

import json
import logging
import shutil
import urllib.request
from pathlib import Path

log = logging.getLogger(__name__)

URL = "http://127.0.0.1:7860"
NEGATIVE = "music, melody, singing, speech, voice, talking"


def _get(url: str, timeout: float = 30):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return r.read()


def generate(url: str, what: str, out: Path, seconds: int = 4, seed: int = 7) -> Path:
    """One effect: the Gradio /generate call (28 listed inputs and a hidden 29th), the take trimmed."""
    import numpy as np
    import soundfile as sf

    api = url.rstrip("/") + "/gradio_api"
    params = json.loads(_get(api + "/info"))["named_endpoints"]["/generate"]["parameters"]
    prompt = f"{what}, a single cartoon sound effect, close and clean, no music"
    over = {"prompt": prompt, "negative_prompt": NEGATIVE, "seconds_total": int(seconds) + 2, "seed": seed,
            "file_format": "wav", "file_naming": "output.wav", "batch_size": 1}
    data = [over.get(p["parameter_name"], p.get("parameter_default")) for p in params] + [None]
    req = urllib.request.Request(api + "/call/generate", data=json.dumps({"data": data}).encode(),
                                 headers={"Content-Type": "application/json"})
    eid = json.loads(urllib.request.urlopen(req, timeout=30).read())["event_id"]
    ev = res = None
    with urllib.request.urlopen(f"{api}/call/generate/{eid}", timeout=600) as s:
        for raw in s:
            line = raw.decode("utf-8", "replace").strip()
            if line.startswith("event:"):
                ev = line[6:].strip()
            elif line.startswith("data:"):
                res = line[5:].strip()
                if ev in ("complete", "error"):
                    break
    if ev != "complete":
        raise RuntimeError(f"sound effect {what!r} failed: {ev} {res}")
    audio = json.loads(res)[0]
    src = audio.get("path") if isinstance(audio, dict) else audio
    out.parent.mkdir(parents=True, exist_ok=True)
    if src and Path(src).exists():
        shutil.copy(src, out)
    else:
        out.write_bytes(_get(audio["url"], 300))
    a, sr = sf.read(out, dtype="float32", always_2d=True)
    loud = np.nonzero(np.abs(a).max(1) > 0.02 * np.abs(a).max())[0]
    if len(loud):
        a = a[: min(len(a), loud[-1] + int(0.15 * sr))]
    fade = min(len(a), int(0.05 * sr))
    a[-fade:] *= np.linspace(1, 0, fade)[:, None]
    sf.write(out, a, sr)
    return out


def make(folder: Path, url: str = URL) -> list[Path]:
    """Every effect the episode names that the series doesn't have yet; then every shot with effects is
    recorded again (its lines are kept), so the next render takes it with its sound."""
    from entertainment import cartoons

    series = cartoons.SERIES[folder.parent.name]
    ep = cartoons.Episode.model_validate_json((folder / "episode.json").read_text(encoding="utf-8"))
    made = []
    for what in dict.fromkeys(e.what for s in ep.scenes for e in s.sfx):
        if series.sfx(what) is None:
            made.append(generate(url, what, series.sfx_path(what)))
            log.info("sfx: %s", what)
    for i, scene in enumerate(ep.scenes, start=1):
        if scene.sfx:
            cartoons.record(series, scene, folder, i, cartoons._start(ep, i, folder))
    return made
