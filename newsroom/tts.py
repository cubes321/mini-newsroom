"""Text-to-speech via Pocket TTS (Kyutai) cloning reference clips, and Kokoro-82M for the rest, on CPU.

Design points:
- With [tts] backend = "pocket", a voice that has a reference clip in assets/voices
  ("<kokoro voice>.<lang>.wav", designed with Qwen3-TTS VoiceDesign) is cloned from it by
  Pocket TTS; every other voice, and any line Pocket fails on, is Kokoro's as before.
  backend = "kokoro" puts everyone back on Kokoro.
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
import zlib
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
_POCKET: dict[str, object] = {}      # "model", then one voice state per reference clip
_KOKORO_THREADS: list[int] = []      # torch's thread count before Pocket set it to one, for Kokoro

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


VOICES_DIR = CONFIG.paths.assets / "voices"
POCKET_RMS = 0.085               # Pocket's level varies with its reference: Kokoro's lines sit at 0.08-0.09
                                 # RMS (speech above a whisper), so Pocket's are brought to the same


def _cast() -> dict[str, dict]:
    """voices.toml: each reference clip's gender and age (and the description it was designed from)."""
    key = f"cast:{VOICES_DIR}"
    if key not in _POCKET:
        import tomllib

        f = VOICES_DIR / "voices.toml"
        _POCKET[key] = tomllib.loads(f.read_text(encoding="utf-8")) if f.exists() else {}
    return _POCKET[key]


def clip_for(voice: str, lang: str, age: str | None = None) -> Path | None:
    """The reference clip Pocket clones `voice` from when it speaks with pronunciation `lang`, if
    Pocket is the backend and the voice has one (the presenters and the local guests do; visitors not yet).
    Kokoro's guest voices were cast without an age, but a designed clip has one: a guest whose own
    clip is the wrong age gets one of their gender and age instead, the same one every time."""
    if CONFIG.tts.backend != "pocket":
        return None
    clip = VOICES_DIR / f"{voice}.{lang}.wav"
    if not clip.exists():
        return None
    cast = _cast()
    own = cast.get(voice, {})
    if age and own.get("age") and own["age"] != age:
        like = sorted(v for v, c in cast.items() if c.get("gender") == own.get("gender") and c.get("age") == age
                      and (VOICES_DIR / f"{v}.{lang}.wav").exists())
        if like:
            clip = VOICES_DIR / f"{like[zlib.crc32(voice.encode()) % len(like)]}.{lang}.wav"
    return clip


def _pocket():
    """Pocket TTS's model, loaded once. Importing it sets torch to one thread for the whole process,
    which suits Pocket and starves Kokoro, so the count before is kept and given back per call."""
    with _PIPE_LOCK:
        if "model" not in _POCKET:
            t0 = time.perf_counter()
            import torch

            _KOKORO_THREADS.append(torch.get_num_threads())
            try:
                from pocket_tts import TTSModel

                _POCKET["model"] = TTSModel.load_model()
                log.info("pocket tts ready in %.1fs", time.perf_counter() - t0)
            except Exception:  # noqa: BLE001
                _POCKET["model"] = None             # tried once: Kokoro has every line from now on
                log.exception("pocket tts didn't load (weights gated? `hf auth login`); Kokoro speaks for all")
            torch.set_num_threads(_KOKORO_THREADS[0])
        if _POCKET["model"] is None:
            raise RuntimeError("pocket tts unavailable")
        return _POCKET["model"]


def _pocket_voice(clip: Path):
    model = _pocket()
    key = str(clip)
    if key not in _POCKET:
        _POCKET[key] = model.get_state_for_audio_prompt(key)
    return model, _POCKET[key]


def _pocket_speak(text: str, clip: Path) -> np.ndarray:
    """One line in the voice cloned from `clip`, at the station's rate. Caller holds _SYNTH_LOCK."""
    import torch

    model, state = _pocket_voice(clip)
    torch.set_num_threads(1)
    try:
        audio = model.generate_audio(state, text).numpy().astype(np.float32)
    finally:
        torch.set_num_threads(_KOKORO_THREADS[0])
    if model.sample_rate != CONFIG.tts.sample_rate:
        sr = CONFIG.tts.sample_rate
        n = int(len(audio) * sr / model.sample_rate)
        audio = np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)
    speech = audio[np.abs(audio) > 0.02 * (float(np.abs(audio).max()) or 1.0)]
    rms = float(np.sqrt((speech ** 2).mean())) if len(speech) else 0.0
    return audio * (POCKET_RMS / rms) if rms else audio


def preload() -> None:
    """Load Pocket and every reference clip's voice in the background, so the first guest of the
    night doesn't wait ~15 s for them. Nothing to do on Kokoro alone."""
    if CONFIG.tts.backend != "pocket":
        return

    def run():
        try:
            for clip in sorted(VOICES_DIR.glob("*.wav")):
                with _SYNTH_LOCK:                   # a second at a time, between lines
                    _pocket_voice(clip)
            log.info("pocket voices ready: %d", sum(k.endswith(".wav") for k in _POCKET))
        except Exception:  # noqa: BLE001
            log.exception("pocket preload failed; its voices will fall back to Kokoro")
    threading.Thread(target=run, name="pocket-preload", daemon=True).start()


def mouth_envelope(audio: np.ndarray, sr: int, window_s: float = ENV_WINDOW_S) -> list[float]:
    """RMS per window, normalised to 0..1. Short and cheap; stored on the Line."""
    n = max(1, int(sr * window_s))
    pad = (-len(audio)) % n
    frames = np.pad(audio, (0, pad)).reshape(-1, n)
    rms = np.sqrt((frames.astype(np.float32) ** 2).mean(axis=1))
    peak = float(rms.max()) or 1.0
    return [round(float(v / peak), 3) for v in rms]


PHONE_BAND = (300.0, 3400.0)     # Hz: what a telephone line carries


def telephone(audio: np.ndarray, sr: int) -> np.ndarray:
    """A voice down a phone line: only the telephone band, softly squashed, as a phone-in caller sounds.
    Done in one FFT (no filter design to depend on), with gentle shoulders so the cut doesn't ring."""
    spec = np.fft.rfft(audio)
    f = np.fft.rfftfreq(len(audio), 1 / sr)
    lo, hi = PHONE_BAND
    gain = np.clip((f - lo * 0.7) / (lo * 0.3), 0, 1) * np.clip((hi * 1.15 - f) / (hi * 0.15), 0, 1)
    band = np.fft.irfft(spec * gain, n=len(audio)).astype(np.float32)
    peak = float(np.abs(band).max()) or 1.0
    return (np.tanh(band / peak * 1.8) / np.tanh(1.8) * min(peak * 1.3, 0.9)).astype(np.float32)


PUPPET = 1.33                   # "voice@puppet": raised a third, as Gully was chosen by ear (2026-10-30)


def raise_pitch(audio: np.ndarray, by: float) -> np.ndarray:
    """Play `audio` back `by` times faster: the pitch rises, and speech spoken `by` times slower
    comes back to its own pace. Linear interpolation is plenty for a puppet."""
    n = int(len(audio) / by)
    return np.interp(np.linspace(0, len(audio) - 1, n), np.arange(len(audio)), audio).astype(np.float32)


def _kokoro(text: str, voice: str, speed: float, lang: str) -> np.ndarray:
    """One line from Kokoro, its sentences joined with short gaps. Caller holds _SYNTH_LOCK."""
    pipe = _pipeline(lang)
    chunks: list[np.ndarray] = []
    gap = np.zeros(int(CONFIG.tts.sample_rate * 0.12), dtype=np.float32)
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
    return np.concatenate(chunks[:-1])  # drop trailing gap


def synthesize(text: str, voice: str, out_path: Path, speed: float = 1.0, lang: str | None = None,
               phone: bool = False, age: str | None = None) -> SynthResult:
    """Render `text` with `voice` to `out_path` (24 kHz mono PCM_16). `lang` is Kokoro's
    pronunciation ("a" American, "b" British); the station's own by default. `phone`: through
    the telephone band, for a caller on the line. `age`: a guest's, for Pocket's clips. A voice
    written "bm_fable@puppet" is that voice raised a third, spoken slower to keep its pace: a puppet's, and nobody else's. A voice with a
    reference clip (`clip_for`) is Pocket's, unless it carries an effect; Kokoro takes the line if
    Pocket fails, so a bad line costs a voice, never the air."""
    voice, _, effect = voice.partition("@")
    pitch = PUPPET if effect == "puppet" else 1.0
    speed /= pitch
    sr = CONFIG.tts.sample_rate
    lang = lang or CONFIG.tts.lang_code
    clip = None if effect or _POCKET.get("model", True) is None else clip_for(voice, lang, age)
    t0 = time.perf_counter()

    audio, engine = None, "pocket"
    with _SYNTH_LOCK:
        if clip:
            try:
                audio = _pocket_speak(text, clip)
            except Exception:  # noqa: BLE001
                log.exception("pocket failed on %s; Kokoro takes the line", clip.name)
        if audio is None:
            audio, engine = _kokoro(text, voice, speed, lang), "kokoro"
    if pitch != 1.0:
        audio = raise_pitch(audio, pitch)
    if phone:
        audio = telephone(audio, sr)
    audio = np.clip(audio, -1.0, 1.0)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    tmp = out_path.with_suffix(out_path.suffix + ".tmp")
    sf.write(tmp, audio, sr, format="WAV", subtype="PCM_16")
    os.replace(tmp, out_path)

    duration = len(audio) / sr
    log.debug("tts %5.2fs audio in %.2fs (%s %s.%s, %d chars)",
              duration, time.perf_counter() - t0, engine, voice, lang, len(text))
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
