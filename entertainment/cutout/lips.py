"""Who is speaking, and how loudly, in every frame of a shot: from the recorded lines themselves (the scene's
lines/NN_who.wav), each found in the shot's track by cross-correlation. A frame of a line is "closed" under
12% of that line's loudest, "loud" from 42% (Gully's squawk on "Bis-cuit", "To-day", "ME!" in the probe), else
"talk"; no face lasts a single frame. The kit says what "loud" looks like (Biscuit has no squawk: she talks).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import soundfile as sf
from scipy import ndimage, signal

from entertainment.cutout import FPS

QUIET, LOUD = 0.12, 0.42


def faces(folder: Path, i: int) -> tuple[int, dict[str, list[str]], list[tuple[str, float, float]]]:
    """The shot's frame count, each speaker's face per frame ("closed", "talk", "loud"), and the lines as
    (who, start s, end s)."""
    track, sr = sf.read(folder / f"scene{i:02d}.dialogue.wav", dtype="float32")
    if track.ndim > 1:
        track = track.mean(1)
    n = round(len(track) / sr * FPS)
    hop = sr // FPS
    out: dict[str, list[str]] = {}
    spans = []
    for wav in sorted((folder / f"scene{i:02d}" / "lines").glob("*.wav")):
        who = wav.stem.split("_", 1)[1]
        line, lsr = sf.read(wav, dtype="float32")
        if line.ndim > 1:
            line = line.mean(1)
        if lsr != sr:
            line = signal.resample_poly(line, sr, lsr)
        at = int(np.argmax(signal.fftconvolve(track, line[::-1], mode="valid"))) / sr
        env = np.zeros(n)
        for f in range(n):
            k = round((f / FPS - at) * sr)
            seg = line[max(k, 0): max(k + hop, 0)]
            env[f] = np.sqrt((seg ** 2).mean()) if len(seg) else 0.0
        env = ndimage.uniform_filter1d(env, 2) / max(env.max(), 1e-9)
        face = np.where(env < QUIET, "closed", np.where(env < LOUD, "talk", "loud")).astype(object)
        for f in range(1, n - 1):                        # no single-frame flicker
            if face[f] != face[f - 1] and face[f] != face[f + 1]:
                face[f] = face[f - 1]
        mine = out.setdefault(who, ["closed"] * n)
        for f in range(n):
            if face[f] != "closed":
                mine[f] = face[f]
        spans.append((who, round(at, 3), round(at + len(line) / sr, 3)))
    return n, out, spans
