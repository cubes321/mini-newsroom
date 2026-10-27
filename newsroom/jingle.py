"""Channel 7's sonic logo: a few notes written down here, rendered in numpy.

The notes are the station's tune, so they live in code rather than in a generated file:
every show's ident, the breaking sting and the music bed are arrangements of the same
motif, and the logo animation (logo.py) keys its reveal off `onsets()`.

- `MOTIFS`: candidate tunes as (MIDI note, beats) pairs; None is a rest. The last note is
  the held one, and `chord` is the chord under it.
- `render(name, voicing)`: 44.1 kHz stereo float32. Voicings: news (a brass fanfare),
  breakfast (glockenspiel and marimba, a third up), magazine (strings and funk bass),
  late (lounge piano, slower), breaking (the opening notes in minor, urgent).
- `python -m newsroom.jingle --audition DIR` writes every candidate in every voicing.

The synthesis is deliberately simple (FM brass, additive partials, FFT filters and a
noise reverb); Stable Audio 3 restyles these renders in tools/station_audio.py.
"""
from __future__ import annotations

import argparse
import subprocess
from functools import lru_cache
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

SR = 44100
RNG = np.random.default_rng(7)


@dataclass(frozen=True)
class Motif:
    title: str
    notes: list[tuple[int | None, float]]
    chord: list[int]                       # the chord under the held last note
    bpm: float = 128.0
    minor: dict[int, int] = field(default_factory=lambda: {64: 63, 76: 75, 88: 87, 69: 68, 81: 80})


# All in C, so they compare like for like; arrangements transpose.
MOTIFS: dict[str, Motif] = {
    "beacon": Motif("Beacon", [(72, .5), (67, .5), (72, .5), (76, .5), (79, 2.5)],
                    [48, 55, 60, 64, 67], bpm=112),
    "turn": Motif("The Turn", [(67, .5), (72, .75), (71, .25), (72, .5), (79, 2.5)],
                  [48, 55, 60, 64, 67], bpm=112),
    "seven": Motif("Seven Notes", [(72, .25), (74, .25), (76, .25), (79, .75), (76, .25), (79, .25), (84, 2.5)],
                   [48, 55, 60, 64, 67], bpm=104),
    "sixth": Motif("Seaside Sixth", [(72, .75), (76, .25), (79, .5), (81, 1.0), (79, 2.5)],
                   [48, 55, 60, 64, 69], bpm=112),
}
DEFAULT = "beacon"

# How each show plays the tune: transpose (semitones), tempo factor.
VOICINGS: dict[str, tuple[int, float]] = {
    "news": (0, 1.0),
    "breakfast": (4, 1.08),
    "magazine": (-3, 1.0),
    "late": (-5, 0.78),
    "breaking": (0, 1.35),
}


def _hz(n: float) -> float:
    return 440.0 * 2 ** ((n - 69) / 12)


def _t(dur: float) -> np.ndarray:
    return np.arange(int(SR * dur)) / SR


def _filter(x: np.ndarray, lo: float | None = None, hi: float | None = None, order: int = 2) -> np.ndarray:
    """Smooth FFT band filter: `hi` is a low-pass corner, `lo` a high-pass one."""
    spec = np.fft.rfft(x)
    f = np.fft.rfftfreq(len(x), 1 / SR) + 1e-9
    gain = np.ones_like(f)
    if hi:
        gain /= np.sqrt(1 + (f / hi) ** (2 * order))
    if lo:
        gain /= np.sqrt(1 + (lo / f) ** (2 * order))
    return np.fft.irfft(spec * gain, len(x))


def _env(n: int, a: float, r: float, hold_s: float, decay: float = 0.0) -> np.ndarray:
    t = np.arange(n) / SR
    env = np.minimum(1.0, t / max(a, 1e-4)) * np.exp(-decay * t)
    rel = np.clip(1 - (t - hold_s) / max(r, 1e-4), 0, 1)
    return env * np.where(t > hold_s, rel, 1.0)


# --- instruments: each returns a mono note of `dur` (plus its own release) ---

def brass(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    t = _t(dur + 0.25)
    amp = _env(len(t), 0.05, 0.2, dur) * (1 - 0.15 * np.minimum(1, t / 0.3))
    vib = 1 + 0.004 * np.sin(2 * np.pi * 5.5 * t) * np.minimum(1, t / 0.4)
    phi = 2 * np.pi * np.cumsum(f * vib) / SR
    y = np.sin(phi + (0.6 + 3.2 * amp) * np.sin(phi))
    return y * amp * vel


def section(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """Three detuned brass players and one an octave down, as one mono line."""
    out = sum(brass(f * 2 ** (c / 1200), dur, vel) for c in (-7, 0, 6)) / 3
    return out + 0.45 * brass(f / 2, dur, vel)


def timpani(f: float, vel: float = 1.0) -> np.ndarray:
    t = _t(2.2)
    sweep = f * (1 + 0.03 * np.exp(-t * 20))
    phi = 2 * np.pi * np.cumsum(sweep) / SR
    y = np.sin(phi) + 0.5 * np.sin(1.5 * phi) * np.exp(-t * 4) + 0.3 * np.sin(1.99 * phi) * np.exp(-t * 6)
    thud = _filter(RNG.standard_normal(len(t)), hi=300) * np.exp(-t * 30) * 0.6
    return (y * np.exp(-t * 2.2) + thud) * vel * 0.9


def cymbal_swell(dur: float, vel: float = 1.0) -> np.ndarray:
    """Noise that rises over `dur` and rings on after it."""
    n = int(SR * (dur + 2.0))
    t = np.arange(n) / SR
    noise = _filter(RNG.standard_normal(n), lo=3000)
    env = np.where(t < dur, (t / dur) ** 2, np.exp(-(t - dur) * 2.5))
    return noise * env * 0.12 * vel


def glock(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    t = _t(max(dur, 1.6))
    parts = [(1, 1, 2.2), (2.76, .35, 6), (5.4, .18, 11), (8.93, .08, 16)]
    return sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-d * t) for r, a, d in parts) * vel * 0.6


def marimba(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    t = _t(max(dur, 1.0))
    parts = [(1, 1, 5), (4.0, .3, 16), (9.2, .1, 30)]
    return sum(a * np.sin(2 * np.pi * f * r * t) * np.exp(-d * t) for r, a, d in parts) * vel * 0.7


def _saw(f: float, t: np.ndarray) -> np.ndarray:
    k = np.arange(1, int(min(40, (SR / 2) / f)) + 1)
    return (np.sin(2 * np.pi * f * np.outer(t, k)) / k).sum(axis=1)


def strings(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    t = _t(dur + 0.5)
    y = sum(_saw(f * 2 ** (c / 1200), t) for c in (-9, 0, 8)) / 3
    y = _filter(y, hi=2600)
    return y * _env(len(t), 0.12, 0.45, dur) * vel * 0.5


def bass(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    t = _t(dur + 0.05)
    y = _filter(_saw(f, t), hi=900)
    return y * _env(len(t), 0.005, 0.05, dur, decay=3.0) * vel * 0.8


def piano(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    t = _t(max(dur, 0.6) + 1.2)
    y = np.zeros_like(t)
    for k in range(1, 11):
        fk = f * k * np.sqrt(1 + 0.0004 * k * k)
        if fk > SR / 2:
            break
        y += np.sin(2 * np.pi * fk * t) / k ** 1.3 * np.exp(-(1.2 + 0.7 * k) * t)
    damp = np.where(t > dur + 0.6, np.exp(-(t - dur - 0.6) * 8), 1.0)
    hammer = _filter(RNG.standard_normal(len(t)), lo=1500) * np.exp(-t * 80) * 0.05
    return (y * damp + hammer) * vel * 0.55


def analog(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """A 70s mono-synth lead: two detuned saws and a square sub, with a filter that opens on each note."""
    t = _t(dur + 0.3)
    raw = _saw(f * 2 ** (-6 / 1200), t) + _saw(f * 2 ** (6 / 1200), t) + 0.5 * np.sign(np.sin(np.pi * f * t))
    dark, bright = _filter(raw, hi=700), _filter(raw, hi=5000)
    sweep = np.exp(-t * 5)
    return (dark + sweep * (bright - dark)) * _env(len(t), 0.01, 0.25, dur) * vel * 0.35


def synth_pad(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """An ARP string-ensemble pad: detuned saws with a slow chorus wobble."""
    t = _t(dur + 0.8)
    y = sum(_saw(f * 2 ** (c / 1200), t) for c in (-12, 0, 11))
    wob = 1 + 0.15 * np.sin(2 * np.pi * 0.6 * t)
    return _filter(y, hi=1800) * wob * _env(len(t), 0.25, 0.8, dur) * vel * 0.25


def vibes(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    t = _t(max(dur, 1.2) + 1.0)
    trem = 1 + 0.35 * np.sin(2 * np.pi * 5.0 * t)
    y = np.sin(2 * np.pi * f * t) * np.exp(-t * 1.2) + 0.25 * np.sin(2 * np.pi * f * 4 * t) * np.exp(-t * 8)
    return y * trem * vel * 0.6


def rhodes(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """An electric piano: soft FM bell with a tine at fourteen times the pitch."""
    t = _t(max(dur, 0.5) + 1.0)
    idx = 1.2 * np.exp(-t * 3)
    y = np.sin(2 * np.pi * f * t + idx * np.sin(2 * np.pi * f * t))
    tine = 0.15 * np.sin(2 * np.pi * f * 14 * t) * np.exp(-t * 25)
    damp = np.where(t > dur + 0.3, np.exp(-(t - dur - 0.3) * 6), 1.0)
    return (y * np.exp(-t * 0.9) + tine) * damp * vel * 0.5


def harp(f: float, vel: float = 1.0) -> np.ndarray:
    t = _t(1.6)
    y = sum(np.sin(2 * np.pi * f * k * t) / k ** 1.6 * np.exp(-(2.0 + k) * t) for k in range(1, 7))
    return y * np.minimum(1, t / 0.003) * vel * 0.5


def tick(vel: float = 1.0) -> np.ndarray:
    t = _t(0.06)
    return _filter(RNG.standard_normal(len(t)), lo=7000) * np.exp(-t * 90) * 0.25 * vel


# --- arranging ---

class _Mix:
    def __init__(self, seconds: float):
        self.buf = np.zeros((int(SR * seconds), 2), dtype=np.float64)

    def add(self, at_s: float, mono: np.ndarray, gain: float = 1.0, pan: float = 0.0) -> None:
        i = int(at_s * SR)
        if i >= len(self.buf):
            return
        seg = mono[: len(self.buf) - i] * gain
        self.buf[i:i + len(seg), 0] += seg * np.sqrt((1 - pan) / 2)
        self.buf[i:i + len(seg), 1] += seg * np.sqrt((1 + pan) / 2)


def _reverb(buf: np.ndarray, seconds: float, mix: float) -> np.ndarray:
    n = int(SR * seconds)
    t = np.arange(n) / SR
    out = buf.copy()
    for ch in (0, 1):
        ir = RNG.standard_normal(n) * np.exp(-6.9 * t / seconds)
        ir = _filter(ir, hi=6000) * 0.02
        size = len(buf) + n
        wet = np.fft.irfft(np.fft.rfft(buf[:, ch], size) * np.fft.rfft(ir, size), size)[: len(buf)]
        out[:, ch] = buf[:, ch] * (1 - mix) + wet * mix * 3
    return out


def _events(m: Motif, transpose: int, tempo: float, minor: bool) -> list[tuple[float, float, int]]:
    """(start_s, dur_s, midi) for each sounding note."""
    beat = 60.0 / (m.bpm * tempo)
    out, at = [], 0.0
    for note, beats in m.notes:
        if note is not None:
            n = m.minor.get(note, note) if minor else note
            out.append((at, beats * beat, n + transpose))
        at += beats * beat
    return out


def onsets(name: str = DEFAULT, voicing: str = "news") -> list[float]:
    """When each note of the tune starts, in seconds: the logo reveals one piece per onset."""
    transpose, tempo = VOICINGS[voicing]
    return [s for s, _, _ in _events(MOTIFS[name], transpose, tempo, voicing == "breaking")]


# The news ident's sound; the others are kept for auditions. "breaking" is always brass.
NEWS_STYLES = ("brass", "synth", "vibes", "strings")
NEWS_STYLE = "vibes"            # chosen by ear 2026-10-27 (code render, vibes-A)


def render(name: str = DEFAULT, voicing: str = "news", tail_s: float = 1.8, style: str | None = None) -> np.ndarray:
    """The tune in a show's arrangement, 44.1 kHz stereo float32. Cached: don't change the array."""
    return _render(name, voicing, tail_s, style or NEWS_STYLE)


@lru_cache(maxsize=16)
def _render(name: str, voicing: str, tail_s: float, style: str) -> np.ndarray:
    m = MOTIFS[name]
    transpose, tempo = VOICINGS[voicing]
    minor = voicing == "breaking"
    ev = _events(m, transpose, tempo, minor)
    if minor:
        ev = ev[:3]
    last_at, last_dur, _ = ev[-1]
    end = last_at + last_dur
    mix = _Mix(end + tail_s + 0.5)
    chord = [(m.minor.get(c, c) if minor else c) + transpose for c in m.chord]
    root = chord[0]
    beat = 60.0 / (m.bpm * tempo)

    if voicing == "news" and style == "synth":
        for at, dur, n in ev:
            mix.add(at, analog(_hz(n), dur * 0.95), 0.55)
            mix.add(at + 0.012, analog(_hz(n + 12), dur * 0.95, 0.4), 0.2, pan=0.4)
        for j, c in enumerate(chord[1:]):
            mix.add(last_at, synth_pad(_hz(c), end - last_at + 1.0), 0.35, pan=(-0.5, -0.2, 0.2, 0.5)[j % 4])
        mix.add(last_at, analog(_hz(root - 12), end - last_at + 0.6, 0.8), 0.35)
        mix.add(max(0.0, last_at - 1.0), cymbal_swell(min(1.0, last_at), 0.6), 0.6)
        out = _reverb(mix.buf, 1.6, 0.25)
    elif voicing == "news" and style == "vibes":
        for at, dur, n in ev:
            mix.add(at, vibes(_hz(n), dur), 0.5, pan=0.2)
            mix.add(at, rhodes(_hz(n - 12), dur * 0.9), 0.35, pan=-0.2)
        for j, c in enumerate(chord):
            mix.add(last_at + 0.03 * j, rhodes(_hz(c), end - last_at + 0.8, 0.7), 0.25, pan=-0.3 + 0.15 * j)
        mix.add(last_at, bass(_hz(root - 12), end - last_at + 0.5, 0.7), 0.35)
        out = _reverb(mix.buf, 1.6, 0.25)
    elif voicing == "news" and style == "strings":
        for at, dur, n in ev:
            mix.add(at, strings(_hz(n), dur * 0.98), 0.4, pan=-0.15)
            mix.add(at, strings(_hz(n + 12), dur * 0.98, 0.7), 0.22, pan=0.15)
        gliss = [c + o for o in (0, 12, 24) for c in chord[1:]]
        step = min(0.045, max(0.02, (last_at - 0.1) / len(gliss)))
        for k, c in enumerate(gliss):
            mix.add(max(0.0, last_at - step * (len(gliss) - k)), harp(_hz(c), 0.8), 0.3, pan=-0.6 + 1.2 * k / len(gliss))
        for j, c in enumerate(chord):
            mix.add(last_at, strings(_hz(c), end - last_at + 1.0, 0.8), 0.2, pan=(-0.6, -0.3, 0, 0.3, 0.6)[j % 5])
        mix.add(last_at, harp(_hz(chord[-1] + 12)), 0.4)
        out = _reverb(mix.buf, 2.0, 0.3)
    elif voicing in ("news", "breaking"):
        for i, (at, dur, n) in enumerate(ev):
            mix.add(at, section(_hz(n), dur * 0.92), 0.5)
        hold = end - last_at + (0.4 if minor else 1.0)
        for j, c in enumerate(chord[1:]):
            mix.add(last_at, section(_hz(c), hold, 0.7), 0.22, pan=(-0.6, -0.2, 0.2, 0.6)[j % 4])
        mix.add(0.0, timpani(_hz(root - 12)), 0.7)
        mix.add(last_at, timpani(_hz(root - 12)), 0.9)
        if minor:
            for k in range(6):
                mix.add(k * beat / 2, timpani(_hz(root - 12), 0.5), 0.35)
        mix.add(max(0.0, last_at - 1.2), cymbal_swell(min(1.2, last_at)), 0.9)
        out = _reverb(mix.buf, 1.8, 0.25)
    elif voicing == "breakfast":
        for at, dur, n in ev:
            mix.add(at, glock(_hz(n + 12), dur), 0.45, pan=0.25)
            mix.add(at, marimba(_hz(n), dur), 0.5, pan=-0.25)
        for j, c in enumerate(chord[1:]):
            mix.add(last_at + j * 0.07, glock(_hz(c + 12), 1.4, 0.6), 0.2, pan=(-0.5, 0.5)[j % 2])
            mix.add(last_at, strings(_hz(c), end - last_at + 0.8, 0.6), 0.12)
        out = _reverb(mix.buf, 1.2, 0.2)
    elif voicing == "magazine":
        for at, dur, n in ev:
            mix.add(at, strings(_hz(n), dur * 0.95), 0.35, pan=-0.2)
            mix.add(at, strings(_hz(n + 12), dur * 0.95, 0.6), 0.2, pan=0.2)
        steps = int((end + 0.5) / (beat / 2))
        for k in range(steps):
            at = k * beat / 2
            mix.add(at, tick(1.0 if k % 2 else 0.6), 1.0, pan=0.4)
            if at < last_at:
                f = _hz(root - 12 + (12 if k % 4 == 3 else 0) + (7 if k % 8 == 6 else 0))
                mix.add(at, bass(f, beat / 2 * 0.8), 0.45)
        mix.add(last_at, bass(_hz(root - 12), end - last_at), 0.5)
        for j, c in enumerate(chord[1:]):
            mix.add(last_at, strings(_hz(c), end - last_at + 0.6, 0.7), 0.16, pan=(-0.5, 0.5)[j % 2])
        mix.add(last_at, section(_hz(chord[-1]), 0.18), 0.25)
        out = _reverb(mix.buf, 1.4, 0.2)
    elif voicing == "late":
        for at, dur, n in ev:
            mix.add(at, piano(_hz(n), dur), 0.6, pan=0.1)
        lush = chord + [chord[2] + 11, chord[2] + 14]          # add the major seventh and ninth
        for j, c in enumerate(lush):
            mix.add(last_at + 0.05 * j, piano(_hz(c), end - last_at + 0.8, 0.55), 0.3, pan=-0.3 + 0.12 * j)
        mix.add(last_at, bass(_hz(root - 12), end - last_at + 0.6, 0.7), 0.4)
        mix.add(max(0.0, last_at - 0.8), cymbal_swell(min(0.8, last_at), 0.5), 0.6)
        out = _reverb(mix.buf, 2.4, 0.3)
    else:
        raise ValueError(f"unknown voicing {voicing!r}")

    peak = np.max(np.abs(out)) or 1.0
    return (out / peak * 0.89).astype(np.float32)


# --- The Last Ferry's house band: a jazz trio (piano, upright bass, brushes) swinging the tune ---

def brush(dur: float = 0.18, vel: float = 1.0) -> np.ndarray:
    """A brush swept across the snare: soft noise that swells and fades."""
    t = _t(dur + 0.15)
    noise = _filter(RNG.standard_normal(len(t)), lo=1800, hi=8000)
    env = np.minimum(1.0, t / (dur * 0.5)) * np.exp(-np.maximum(0.0, t - dur * 0.5) * 18)
    return noise * env * 0.18 * vel


def ride(vel: float = 1.0) -> np.ndarray:
    t = _t(0.7)
    wash = _filter(RNG.standard_normal(len(t)), lo=5000) * np.exp(-t * 9) * 0.12
    bell = sum(np.sin(2 * np.pi * f * t) for f in (3150, 4270, 5610)) / 3 * np.exp(-t * 14) * 0.05
    return (wash + bell) * vel


def upright(f: float, dur: float, vel: float = 1.0) -> np.ndarray:
    """A plucked upright bass: a round low tone with a thump and a fast decay."""
    t = _t(dur + 0.15)
    y = np.sin(2 * np.pi * f * t) + 0.35 * np.sin(4 * np.pi * f * t) * np.exp(-t * 6)
    thump = _filter(RNG.standard_normal(len(t)), hi=400) * np.exp(-t * 60) * 0.4
    return (y * _env(len(t), 0.004, 0.08, dur, decay=2.5) + thump) * vel * 0.8


BAND_STYLES = ("walkon", "button", "lounge")
BAND_STYLE = "walkon"           # the house band's sting on The Last Ferry


def band(style: str = BAND_STYLE, name: str = DEFAULT) -> np.ndarray:
    """The house band's sting, 44.1 kHz stereo float32. walkon: the tune swung, about three
    seconds, playing a guest on; button: just the end of it, a quick flourish into the chord;
    lounge: walkon on Rhodes and vibes instead of the piano."""
    m = MOTIFS[name]
    transpose = VOICINGS["late"][0]
    beat = 60.0 / (m.bpm * 1.12)
    swing = (0.0, beat * 2 / 3)                        # long-short eighths
    notes = [(n + transpose, b) for n, b in m.notes if n is not None]
    if style == "button":
        notes = notes[-3:]
    ev, at, k = [], beat * 0.5, 0                      # a brush pickup before the first note
    for n, b in notes:
        ev.append((at, n, b))
        if b == 0.5:
            at += swing[1] if k % 2 == 0 else beat - swing[1]
            k += 1
        else:
            at += b * beat
    last_at, last_n, _ = ev[-1]
    hold = beat * 1.5
    mix = _Mix(last_at + hold + 1.2)
    chord = [c + transpose for c in m.chord]
    root = chord[0]
    lush = chord + [chord[2] + 11, chord[2] + 14]      # the major seventh and ninth, as the late ident

    mix.add(0.0, brush(beat * 0.5), 0.9, pan=-0.3)
    for at, n, _ in ev[:-1]:
        if style == "lounge":
            mix.add(at, vibes(_hz(n), beat * 0.6), 0.45, pan=0.25)
            mix.add(at, rhodes(_hz(n - 12), beat * 0.5), 0.35, pan=-0.2)
        else:
            mix.add(at, piano(_hz(n), beat * 0.5), 0.5, pan=0.15)
            mix.add(at, piano(_hz(n - 12), beat * 0.5, 0.6), 0.3, pan=0.05)
    walk = [root - 12, root - 12 + 4, root - 12 + 7, root - 12 + 9]   # a walking line up to the chord
    b0 = ev[0][0]
    for j in range(int((last_at - b0) / beat + 0.5)):
        mix.add(b0 + j * beat, upright(_hz(walk[j % 4]), beat * 0.9), 0.55)
    t, j = b0, 0
    while t < last_at:                                 # ride on the swung eighths, brushes on two and four
        mix.add(t, ride(1.0 if j % 2 == 0 else 0.6), 0.6, pan=0.4)
        if j % 4 == 2:
            mix.add(t, brush(), 0.7, pan=-0.3)
        t += swing[1] if j % 2 == 0 else beat - swing[1]
        j += 1
    inst = rhodes if style == "lounge" else piano
    for i, c in enumerate(lush):                        # the last note lands on the full chord, rolled
        mix.add(last_at + 0.025 * i, inst(_hz(c), hold, 0.6), 0.28, pan=-0.3 + 0.12 * i)
    mix.add(last_at, inst(_hz(last_n + 12), hold, 0.8), 0.35, pan=0.2)
    mix.add(last_at, upright(_hz(root - 12), hold), 0.7)
    mix.add(last_at, cymbal_swell(0.02, 0.7), 1.0, pan=0.4)
    out = _reverb(mix.buf, 1.6, 0.22)
    peak = np.max(np.abs(out)) or 1.0
    return (out / peak * 0.89).astype(np.float32)


def _write(path: Path, audio: np.ndarray, sr: int = SR) -> None:
    import soundfile as sf

    path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(path, audio, sr, subtype="PCM_16")


def _mp3(wav: Path) -> Path | None:
    mp3 = wav.with_suffix(".mp3")
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(wav), "-b:a", "160k", str(mp3)], check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return mp3


def audition(out: Path, names: list[str] | None = None) -> list[Path]:
    """Every candidate in the news voicing, plus a four-show medley of each."""
    written = []
    gap = np.zeros((int(SR * 0.7), 2), dtype=np.float32)
    for name in names or list(MOTIFS):
        news = render(name, "news")
        p = out / f"{name}_news.wav"
        _write(p, news)
        written.append(p)
        medley = np.concatenate([x for v in ("news", "breakfast", "magazine", "late", "breaking")
                                 for x in (render(name, v), gap)])
        p = out / f"{name}_medley.wav"
        _write(p, medley)
        written.append(p)
    for p in written:
        _mp3(p)
    return written


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--audition", type=Path, help="write every candidate to this folder")
    ap.add_argument("--motif", choices=list(MOTIFS), help="only this one")
    args = ap.parse_args()
    if args.audition:
        for p in audition(args.audition, [args.motif] if args.motif else None):
            print(p)
    else:
        for name, m in MOTIFS.items():
            print(f"{name:8} {m.title:16} onsets {[round(s, 2) for s in onsets(name)]}")


if __name__ == "__main__":
    main()
