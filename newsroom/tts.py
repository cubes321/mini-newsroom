"""Text-to-speech via Kokoro-82M, running on CPU.

Design points:
- torch/kokoro are imported lazily inside `_pipeline()` so the window can
  appear before the 3-10 s import cost is paid, and so this module can be
  imported by code that never synthesises (tests, the player).
- Output is always 24 kHz mono PCM_16 WAV, matching `pygame.mixer.pre_init`,
  so playback needs no resampling.
- A mouth envelope (RMS per 50 ms window, 0..1) is computed here, once, at
  generation time. The player indexes it by elapsed time; no live analysis.
- Files are written to a temp name then `os.replace`d so a reader never
  sees a half-written WAV.
"""
from __future__ import annotations

import logging
import os
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import soundfile as sf

from .config import CONFIG

log = logging.getLogger(__name__)

ENV_WINDOW_S = 0.05
_PIPELINES: dict[str, object] = {}
_PIPE_LOCK = threading.Lock()
_SYNTH_LOCK = threading.Lock()       # one synthesis at a time: workers share the Kokoro pipeline

# Kokoro loads weights from the HF cache; never stall on a network check.
os.environ.setdefault("HF_HUB_OFFLINE", "1")
_ESPEAK_DLL = Path(r"C:\Program Files\eSpeak NG\libespeak-ng.dll")
if _ESPEAK_DLL.exists():
    os.environ.setdefault("PHONEMIZER_ESPEAK_LIBRARY", str(_ESPEAK_DLL))


@dataclass
class SynthResult:
    wav_path: Path
    duration_s: float
    mouth_env: list[float] = field(default_factory=list)


def _pipeline(lang_code: str):
    """Return a cached KPipeline for the language, creating it on first use. A second language
    (British pronunciation for a guest with that accent) shares the first one's model weights."""
    with _PIPE_LOCK:
        if lang_code not in _PIPELINES:
            t0 = time.perf_counter()
            import torch  # noqa: F401  (ensures CPU build is importable before kokoro)
            from kokoro import KPipeline

            model = next((p.model for p in _PIPELINES.values()), True)
            _PIPELINES[lang_code] = KPipeline(
                lang_code=lang_code, repo_id="hexgrad/Kokoro-82M", device=CONFIG.tts.device, model=model
            )
            log.info("kokoro pipeline %r ready in %.1fs", lang_code, time.perf_counter() - t0)
        return _PIPELINES[lang_code]


def mouth_envelope(audio: np.ndarray, sr: int, window_s: float = ENV_WINDOW_S) -> list[float]:
    """RMS per window, normalised to 0..1. Short and cheap; stored on the Line."""
    n = max(1, int(sr * window_s))
    pad = (-len(audio)) % n
    frames = np.pad(audio, (0, pad)).reshape(-1, n)
    rms = np.sqrt((frames.astype(np.float32) ** 2).mean(axis=1))
    peak = float(rms.max()) or 1.0
    return [round(float(v / peak), 3) for v in rms]


def synthesize(text: str, voice: str, out_path: Path, speed: float = 1.0, lang: str | None = None) -> SynthResult:
    """Render `text` with `voice` to `out_path` (24 kHz mono PCM_16). `lang` is Kokoro's
    pronunciation ("a" American, "b" British); the station's own by default."""
    sr = CONFIG.tts.sample_rate
    pipe = _pipeline(lang or CONFIG.tts.lang_code)
    t0 = time.perf_counter()

    chunks: list[np.ndarray] = []
    gap = np.zeros(int(sr * 0.12), dtype=np.float32)
    with _SYNTH_LOCK:
        for result in pipe(text, voice=voice, speed=speed):
            audio = result.audio
            if audio is None:
                continue
            if hasattr(audio, "detach"):
                arr = audio.detach().cpu().numpy().astype(np.float32)
            else:
                arr = np.asarray(audio, dtype=np.float32)
            chunks.append(arr)
            chunks.append(gap)
    if not chunks:
        raise RuntimeError(f"kokoro produced no audio for: {text[:60]!r}")
    audio = np.concatenate(chunks[:-1])  # drop trailing gap
    audio = np.clip(audio, -1.0, 1.0)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    sf.write(tmp, audio, sr, format="WAV", subtype="PCM_16")
    os.replace(tmp, out_path)

    duration = len(audio) / sr
    log.debug("tts %5.2fs audio in %.2fs (%s, %d chars)",
              duration, time.perf_counter() - t0, voice, len(text))
    return SynthResult(out_path, duration, mouth_envelope(audio, sr))


def duration_of(wav_path: Path) -> float:
    """Duration from file frames, never estimated from text."""
    info = sf.info(str(wav_path))
    return info.frames / info.samplerate


def warmup() -> None:
    """First synth pays import + model-load cost; do it before the buffer needs us."""
    out = CONFIG.paths.cache / "_warmup.wav"
    synthesize("Standing by.", next(iter(CONFIG.tts.voices.values()), "af_heart"), out)


def _cli(argv: list[str]) -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m newsroom.tts")
    p.add_argument("text")
    p.add_argument("--voice", default=CONFIG.tts.voices.get("anchor", "af_heart"))
    p.add_argument("--out", type=Path, default=CONFIG.paths.cache / "tts_test.wav")
    p.add_argument("--no-play", action="store_true")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG, format="%(levelname)-5s %(name)s: %(message)s")

    res = synthesize(a.text, a.voice, a.out)
    info = sf.info(str(res.wav_path))
    print(f"wrote {res.wav_path}  {info.samplerate} Hz  ch={info.channels}  {info.subtype}  "
          f"{res.duration_s:.2f}s  env={len(res.mouth_env)} windows")
    if not a.no_play:
        os.environ["PYGAME_HIDE_SUPPORT_PROMPT"] = "1"
        import pygame

        pygame.mixer.pre_init(CONFIG.tts.sample_rate, -16, 1, 512)
        pygame.mixer.init()
        snd = pygame.mixer.Sound(str(res.wav_path))
        ch = snd.play()
        while ch.get_busy():
            time.sleep(0.05)
        pygame.mixer.quit()
        print("played ok")
    return 0


if __name__ == "__main__":
    sys.exit(_cli(sys.argv[1:]))
