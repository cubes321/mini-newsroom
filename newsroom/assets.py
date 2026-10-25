"""Placeholder audio assets, generated on first run.

Nothing here is art. It exists so the pipeline can be proven before any real
jingle or music exists:
- bumper.wav: a four-note synth sting followed by a Kokoro station ident;
  bumper_<show>.wav is the same for another show (Morning Tide's is brighter).
- music_bed.wav: a slow, quiet chord loop used under filler.

Both are 24 kHz mono PCM_16 like everything else. Drop real files with the
same names into assets/ to replace them.
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


def ensure_bumper(show: str = "news") -> Path:
    from . import schedule

    path, text = IDENTS.get(show, IDENTS["news"])
    if path.exists():
        return path
    from . import tts

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


def ensure_music_bed(seconds: float = 24.0) -> Path:
    if MUSIC_BED.exists():
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
