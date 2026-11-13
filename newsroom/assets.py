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

SR = CONFIG.tts.sample_rate          # the voices': 24 kHz mono, as TTS makes them
# The mixer's, and the music's: 44.1 kHz stereo since 2026-11-07. Until then everything played at 24 kHz mono,
# so the music stems were cut to that and lost everything above 12 kHz; SDL converts each voice as it loads.
MUSIC_SR = 44100
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
    "sport": (CONFIG.paths.assets / "bumper_sport.wav",
              "This is Full Time, the sport from the Greymouth coast, on channel seven."),
    # The shows built since, each with its own arrangement (chosen by ear 2026-11-04, jingle.SHOW_STYLE).
    # Until then they borrowed the news's: The Inquiry opened on Dana saying "Port Wexley News".
    "quayside": (CONFIG.paths.assets / "bumper_quayside.wav",
                 "This is Quayside, the money and the harbour trade, on channel seven."),
    "phonein": (CONFIG.paths.assets / "bumper_phonein.wav",
                "You're on Have Your Say, on channel seven. The lines are open."),
    "outabout": (CONFIG.paths.assets / "bumper_outabout.wav",
                 "This is Out and About, on the Greymouth coast, on channel seven."),
    "rockpool": (CONFIG.paths.assets / "bumper_rockpool.wav", "Hello! It's Rock Pool, on channel seven!"),
    "panel": (CONFIG.paths.assets / "bumper_panel.wav", "This is The Panel, on channel seven."),
    "chamber": (CONFIG.paths.assets / "bumper_chamber.wav",
                "From the council chamber, this is The Chamber, on channel seven."),
    "inquiry": (CONFIG.paths.assets / "bumper_inquiry.wav", "This is The Inquiry, on channel seven."),
}


def _tone(freq: float, dur: float, vol: float = 0.3, harmonics: int = 3) -> np.ndarray:
    t = np.linspace(0, dur, int(SR * dur), endpoint=False)
    sig = sum(np.sin(2 * np.pi * freq * (k + 1) * t) / (k + 1) ** 1.5 for k in range(harmonics))
    env = np.minimum(1.0, t / 0.02) * np.exp(-3.0 * t / dur)
    return (sig * env * vol).astype(np.float32)


def _write(path: Path, audio: np.ndarray) -> None:
    """Stereo (frames, 2) is music, at MUSIC_SR; mono is a voice or a placeholder tone, at SR."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".wav.tmp")
    sf.write(tmp, np.clip(audio, -1, 1), MUSIC_SR if audio.ndim == 2 else SR, format="WAV", subtype="PCM_16")
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
    """Any WAV as stereo float32 at MUSIC_SR, shape (frames, 2): a mono file in both channels."""
    audio, sr = sf.read(str(path), dtype="float32", always_2d=True)
    return _load_array(audio, sr)


def _load_array(audio: np.ndarray, sr: int) -> np.ndarray:
    """Audio at `sr` (mono, or stereo as (frames, channels)) as stereo float32 at MUSIC_SR."""
    a = audio[:, None] if audio.ndim == 1 else audio
    a = np.repeat(a[:, :1], 2, axis=1) if a.shape[1] == 1 else a[:, :2]
    if sr != MUSIC_SR:
        n = int(round(len(a) * MUSIC_SR / sr))
        at = np.arange(n) * sr / MUSIC_SR
        a = np.stack([np.interp(at, np.arange(len(a)), a[:, c]) for c in range(2)], axis=1)
    return a.astype(np.float32)


def _ident_mix(music: np.ndarray, voice: np.ndarray, voice_at: float, voice_sr: int = SR) -> np.ndarray:
    """The tune, then the spoken ident over its tail with the music ducked under the voice: stereo at MUSIC_SR,
    the voice (TTS's, at `voice_sr`) in the middle."""
    music, voice = _load_array(music, MUSIC_SR), _load_array(voice, voice_sr)
    start = int(MUSIC_SR * voice_at)
    total = max(len(music), start + len(voice) + int(MUSIC_SR * 0.4))
    out = np.zeros((total, 2), dtype=np.float32)
    duck = np.ones(total, dtype=np.float32)
    ramp = int(MUSIC_SR * 0.15)
    duck[start:] = DUCK
    duck[max(0, start - ramp):start] = np.linspace(1.0, DUCK, min(ramp, start))
    out[:len(music)] = music * duck[:len(music), None]
    out[start:start + len(voice)] += voice
    return out


def _lang(speaker: str) -> str | None:
    """A presenter's own pronunciation, as on air: Howard, Meg and Poppy speak British, and their Pocket clips
    are British. Without it their bumpers asked for American clips they don't have, and Kokoro's stand-ins
    voiced Quayside's, Out and About's and Rock Pool's idents (found 2026-11-07)."""
    from .world import seed_characters

    return next((c.lang or None for c in seed_characters() if c.id == speaker), None)


def ensure_bumper(show: str = "news") -> Path:
    from . import schedule

    key = show if show in IDENTS else "news"
    path, text = IDENTS[key]
    music = IDENT_MUSIC.get(key, key)          # a programme with no music of its own borrows a show's
    lead = schedule.get(show).lead
    voice_id = IDENT_VOICES.get(key) or CONFIG.tts.voices.get(lead, "af_heart")
    stem = _stem(f"ident_{music}")
    if not _stale(path, stem):
        return path
    from . import tts

    if stem is not None:
        from . import jingle

        log.info("baking bumper from %s -> %s", stem.name, path.name)
        ident = tts.synthesize(text, voice_id, CONFIG.paths.cache / f"_ident_{key}.wav",
                               lang=None if key in IDENT_VOICES else _lang(lead))
        voice, _ = sf.read(str(ident.wav_path), dtype="float32")
        voicing = music if music in jingle.VOICINGS else "news"
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
    ident = tts.synthesize(text, voice_id, CONFIG.paths.cache / f"_ident_{show}.wav",
                           lang=None if key in IDENT_VOICES else _lang(lead))
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
    fade = int(MUSIC_SR * 0.3)
    audio = audio.copy()
    audio[-fade:] *= np.linspace(1, 0, fade)[:, None]
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


# The Christmas programmes' idents: their own words over a show's music (christmas.py).
from . import christmas as _christmas  # noqa: E402

IDENT_MUSIC: dict[str, str] = {}
# A bumper read by someone other than its show's lead: Channel 8's closedown is the continuity announcer's.
IDENT_VOICES: dict[str, str] = {}
for _show, (_text, _music) in _christmas.IDENTS.items():
    IDENTS[_show] = (CONFIG.paths.assets / f"bumper_{_show}.wav", _text)
    IDENT_MUSIC[_show] = _music
