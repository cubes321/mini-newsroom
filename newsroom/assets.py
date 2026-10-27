"""Placeholder audio assets, generated on first run.

Nothing here is art. It exists so the pipeline can be proven before any real
jingle or music exists:
- bumper.wav: a four-note synth sting followed by a Kokoro station ident;
  bumper_<show>.wav is the same for another show (Morning Tide's is brighter).
- music_bed.wav: a slow, quiet chord loop used under filler.

Both are 24 kHz mono PCM_16 like everything else. Drop real files with the
same names into assets/ to replace them.

Station music (the Channel 7 tune, tools/station_audio.py) lives in assets/music/ as stems:
ident_<show>.wav, breaking.wav and bed.wav. When a stem exists it is used instead of the
placeholder tones, and a baked file older than its stem is rebuilt.
"""
from __future__ import annotations

import logging
import os
from pathlib import Path

import numpy as np
import soundfile as sf

from .config import CONFIG
from .models import Line, Segment, SegmentState

log = logging.getLogger(__name__)

SR = CONFIG.tts.sample_rate
BUMPER = CONFIG.paths.assets / "bumper.wav"
MUSIC_BED = CONFIG.paths.assets / "music_bed.wav"
IDENT_TEXT = "You're watching Port Wexley News, on channel seven."
# Per-show idents: (file, text). The show's lead voices it. News keeps the original file.
IDENTS: dict[str, tuple[Path, str]] = {
    "news": (BUMPER, IDENT_TEXT),
    "breakfast": (CONFIG.paths.assets / "bumper_breakfast.wav",
                  "Good morning! You're watching Morning Tide, on channel seven."),
    "magazine": (CONFIG.paths.assets / "bumper_magazine.wav",
                 "This is Coastwide, your evening on the Greymouth coast, on channel seven."),
    "late": (CONFIG.paths.assets / "bumper_late.wav",
             "Channel seven, late. This is The Last Ferry."),
}


def _tone(freq: float, dur: float, vol: float = 0.3, harmonics: int = 3) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    sig = sum(np.sin(2 * np.pi * freq * (k + 1) * t) / (k + 1) ** 1.5 for k in range(harmonics))
    env = np.minimum(1.0, t / 0.02) * np.exp(-3.0 * t / dur)
    return (sig * env * vol).astype(np.float32)


def _write(path: Path, audio: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".wav.tmp")
    sf.write(tmp, np.clip(audio, -1, 1), SR, format="WAV", subtype="PCM_16")
    os.replace(tmp, path)


MUSIC = CONFIG.paths.assets / "music"
VOICE_AFTER_S = 1.0     # the spoken ident starts this long after the tune's held note
DUCK = 0.35             # music level under the spoken ident


def _stem(name: str) -> Path | None:
    path = MUSIC / f"{name}.wav"
    return path if path.exists() else None


def _stale(out: Path, stem: Path | None) -> bool:
    """Bake `out` if it is missing, or older than the stem it is made from."""
    if not out.exists():
        return True
    return stem is not None and stem.stat().st_mtime > out.stat().st_mtime


def _load(path: Path) -> np.ndarray:
    """Any WAV as mono float32 at SR (stems may come in at 44.1 kHz stereo)."""
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return _load_array(audio, sr)


def _load_array(audio: np.ndarray, sr: int) -> np.ndarray:
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    if sr != SR:
        n = int(round(len(mono) * SR / sr))
        mono = np.interp(np.arange(n) * sr / SR, np.arange(len(mono)), mono).astype(np.float32)
    return mono


def _ident_mix(music: np.ndarray, voice: np.ndarray, voice_at: float) -> np.ndarray:
    """The tune, then the spoken ident over its tail with the music ducked under the voice."""
    start = int(SR * voice_at)
    total = max(len(music), start + len(voice) + int(SR * 0.4))
    out = np.zeros(total, dtype=np.float32)
    duck = np.ones(total, dtype=np.float32)
    ramp = int(SR * 0.15)
    duck[start:] = DUCK
    duck[max(0, start - ramp):start] = np.linspace(1.0, DUCK, min(ramp, start))
    out[:len(music)] = music * duck[:len(music)]
    out[start:start + len(voice)] += voice
    return out


def ensure_bumper(show: str = "news") -> Path:
    from . import schedule

    key = show if show in IDENTS else "news"
    path, text = IDENTS[key]
    stem = _stem(f"ident_{key}")
    if not _stale(path, stem):
        return path
    from . import tts

    if stem is not None:
        from . import jingle

        log.info("baking bumper from %s -> %s", stem.name, path.name)
        lead = schedule.get(show).lead
        ident = tts.synthesize(text, CONFIG.tts.voices.get(lead, "af_heart"), CONFIG.paths.cache / f"_ident_{key}.wav")
        voice, _ = sf.read(str(ident.wav_path), dtype="float32")
        voicing = key if key in jingle.VOICINGS else "news"
        _write(path, _ident_mix(_load(stem), voice, jingle.onsets(voicing=voicing)[-1] + VOICE_AFTER_S))
        return path

    log.info("baking placeholder bumper -> %s", path.name)
    notes = [392.0, 523.25, 659.25, 783.99]        # G4 C5 E5 G5
    if show == "breakfast":
        notes = [523.25, 659.25, 783.99, 1046.5]   # C5 E5 G5 C6: up an octave, for the morning
    elif show == "magazine":
        notes = [392.0, 493.88, 587.33, 739.99]    # G B D F#: a brighter, jauntier rise
    elif show == "late":
        notes = [220.0, 261.63, 329.63, 311.13]    # A C E E-flat: low, with a bluesy turn
    sting = np.concatenate([_tone(f, 0.22) for f in notes] + [_tone(notes[-1], 0.9, 0.25)])
    lead = schedule.get(show).lead
    ident = tts.synthesize(text, CONFIG.tts.voices.get(lead, "af_heart"), CONFIG.paths.cache / f"_ident_{show}.wav")
    voice, _ = sf.read(str(ident.wav_path), dtype="float32")
    gap = np.zeros(int(SR * 0.25), dtype=np.float32)
    _write(path, np.concatenate([sting, gap, voice, gap]))
    return path


BREAKING_STING = CONFIG.paths.assets / "breaking_sting.wav"


def ensure_breaking_sting() -> Path:
    """Urgent pulses and a low hit, about 2.5 s; tones only, so it never waits on TTS."""
    stem = _stem("breaking")
    if not _stale(BREAKING_STING, stem):
        return BREAKING_STING
    if stem is not None:
        log.info("baking breaking sting from %s", stem.name)
        _write(BREAKING_STING, _load(stem))
        return BREAKING_STING
    log.info("baking placeholder breaking sting -> %s", BREAKING_STING.name)
    pulses = [_tone(f, 0.12, 0.32, harmonics=4) for f in (880.0, 659.25) * 4]
    hit = _tone(110.0, 1.2, 0.45, harmonics=5) + _tone(220.0, 1.2, 0.2)
    gap = np.zeros(int(SR * 0.3), dtype=np.float32)
    _write(BREAKING_STING, np.concatenate(pulses + [hit, gap]))
    return BREAKING_STING


def sting_line() -> Line:
    """The breaking sting as a silent first line (the scenes show the BREAKING NEWS card over it)."""
    path = ensure_breaking_sting()
    info = sf.info(str(path))
    return Line(speaker="anchor", text="", wav_path=path, duration_s=info.frames / info.samplerate, mouth_env=[])


# The Last Ferry's house band (jingle.band): it plays each new guest on, and the show back from a break.
BAND: dict[str, Path] = {kind: CONFIG.paths.assets / f"band_{kind}.wav" for kind in ("walkon", "button")}
BAND_STYLE = {"walkon": "walkon", "button": "button"}          # the jingle.band take each one plays


def ensure_band(kind: str) -> Path:
    from . import jingle

    path, stem = BAND[kind], _stem(f"band_{kind}")
    if not _stale(path, stem):
        return path
    log.info("baking house band %s from %s", kind, stem.name if stem else "the code render")
    audio = _load(stem) if stem else _load_array(jingle.band(BAND_STYLE[kind]), jingle.SR)
    fade = int(SR * 0.3)
    audio = audio.copy()
    audio[-fade:] *= np.linspace(1, 0, fade)
    _write(path, audio)
    return path


def band_line(kind: str, speaker: str = "late_host") -> Line:
    """The house band as a silent first line: the set, nobody talking, the band playing."""
    path = ensure_band(kind)
    info = sf.info(str(path))
    return Line(speaker=speaker, text="", wav_path=path, duration_s=info.frames / info.samplerate, mouth_env=[])


def ensure_music_bed(seconds: float = 24.0) -> Path:
    stem = _stem("bed")
    if not _stale(MUSIC_BED, stem):
        return MUSIC_BED
    if stem is not None:
        log.info("baking music bed from %s", stem.name)
        _write(MUSIC_BED, _load(stem))
        return MUSIC_BED
    log.info("baking placeholder music bed -> %s", MUSIC_BED.name)
    chords = [(261.63, 329.63, 392.0), (220.0, 261.63, 329.63), (174.61, 220.0, 261.63), (196.0, 246.94, 293.66)]
    per = seconds / len(chords)
    parts = []
    for chord in chords:
        t = np.linspace(0, per, int(SR * per), endpoint=False)
        pad = sum(np.sin(2 * np.pi * f * t) * (1 + 0.15 * np.sin(2 * np.pi * 0.3 * t)) for f in chord) / len(chord)
        env = np.minimum(1.0, t / 0.6) * np.minimum(1.0, (per - t) / 0.6)
        parts.append((pad * env * 0.12).astype(np.float32))
    _write(MUSIC_BED, np.concatenate(parts))
    return MUSIC_BED


def ensure_all() -> None:
    ensure_music_bed()
    ensure_bumper()


def bumper_segment(seg: Segment) -> Segment:
    """Turn a planned bumper slot into a ready one backed by the baked asset."""
    from . import schedule, tts

    path = ensure_bumper(seg.show)
    text = IDENTS.get(seg.show, IDENTS["news"])[1]
    audio, sr = sf.read(str(path), dtype="float32")
    seg.lines = [Line(speaker=schedule.get(seg.show).lead, text=text, wav_path=path,
                      duration_s=len(audio) / sr, mouth_env=tts.mouth_envelope(audio, sr))]
    seg.headline = None
    seg.state = SegmentState.ready
    return seg


def testcard_segment(seg: Segment) -> Segment:
    """The overnight card: one silent line of `target_s`, so playout timing works as usual.

    The music bed plays under it (player.py turns it up for test cards).
    """
    secs = max(5, int(round(seg.target_s)))
    path = CONFIG.paths.cache / f"_silence_{secs}s.wav"
    if not path.exists():
        _write(path, np.zeros(SR * secs, dtype=np.float32))
    seg.lines = [Line(speaker="anchor", text="", wav_path=path, duration_s=float(secs), mouth_env=[])]
    seg.headline = None
    seg.state = SegmentState.ready
    return seg
