"""Station music stems (assets/music/) replace the placeholder tones and are rebuilt when newer.

Kokoro is stubbed: the spoken ident is a fixed second of quiet tone.
"""
import os

import numpy as np
import pytest
import soundfile as sf

from newsroom import assets, jingle, tts
from newsroom.tts import SynthResult


@pytest.fixture
def music(tmp_path, monkeypatch):
    folder = tmp_path / "music"
    folder.mkdir()
    monkeypatch.setattr(assets, "MUSIC", folder)
    monkeypatch.setattr(assets, "IDENTS", {k: (tmp_path / p.name, t) for k, (p, t) in assets.IDENTS.items()})
    monkeypatch.setattr(assets, "BREAKING_STING", tmp_path / "breaking_sting.wav")
    monkeypatch.setattr(assets, "MUSIC_BED", tmp_path / "music_bed.wav")

    def synth(text, voice, out, speed=1.0, lang=None):
        sf.write(out, np.full(assets.SR, 0.1, dtype=np.float32), assets.SR, subtype="PCM_16")
        return SynthResult(wav_path=out, duration_s=1.0, mouth_env=[0.5])
    monkeypatch.setattr(tts, "synthesize", synth)
    return folder


def _stem(path, seconds, sr=44100, channels=2):
    t = np.arange(int(sr * seconds)) / sr
    tone = (0.5 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    sf.write(path, np.stack([tone] * channels, axis=1) if channels > 1 else tone, sr, subtype="PCM_16")


def test_bumper_is_the_stem_then_the_spoken_ident(music):
    _stem(music / "ident_news.wav", 2.0)
    path = assets.ensure_bumper("news")
    audio, sr = sf.read(str(path))
    assert sr == assets.MUSIC_SR and audio.ndim == 2                 # 44.1 kHz stereo in and out since 2026-11-07
    audio = audio.mean(axis=1)
    voice_at = jingle.onsets(voicing="news")[-1] + assets.VOICE_AFTER_S
    assert len(audio) / sr == pytest.approx(voice_at + 1.0 + 0.4, abs=0.05)
    before = audio[: int(sr * (voice_at - 0.2))]
    under = audio[int(sr * (voice_at + 0.2)): int(sr * (voice_at + 0.8))]
    assert np.abs(before).max() > 0.45 and np.abs(under - 0.1).max() < 0.5 * assets.DUCK + 0.01


def test_the_music_keeps_its_top_end_and_a_voice_is_mixed_in_the_middle(music):
    """Until 2026-11-07 the stems were cut to 24 kHz mono, and nothing above 12 kHz played."""
    from newsroom import station_audio
    t = np.arange(44100) / 44100
    hi = np.stack([np.sin(2 * np.pi * 15000 * t), np.sin(2 * np.pi * 440 * t)], axis=1)
    stem = station_audio.to_stem(hi, 44100, fade=False)
    assert stem.shape == (44100, 2) and np.abs(stem[:, 0]).max() > 0.8          # 15 kHz kept, left and right apart
    mix = assets._ident_mix(stem, np.full(assets.SR, 0.1, dtype=np.float32), 0.2)
    assert mix.ndim == 2 and np.allclose(mix[int(0.5 * 44100):int(0.9 * 44100), 0] - stem[int(0.5 * 44100):int(0.9 * 44100), 0] * assets.DUCK, 0.1, atol=0.02)


def test_a_newer_stem_rebuilds_the_bumper_and_an_older_one_does_not(music):
    stem = music / "ident_late.wav"
    _stem(stem, 3.0)
    path = assets.ensure_bumper("late")
    first = path.stat().st_mtime
    old = first - 100
    os.utime(stem, (old, old))
    assert assets.ensure_bumper("late").stat().st_mtime == first
    _stem(stem, 5.0)
    os.utime(stem, (first + 100, first + 100))
    assets.ensure_bumper("late")
    assert sf.info(str(path)).duration == pytest.approx(5.0, abs=0.01)


def test_without_stems_the_placeholders_are_kept(music):
    sf.write(assets.MUSIC_BED, np.zeros(assets.SR, dtype=np.float32), assets.SR)
    assert assets.ensure_music_bed() == assets.MUSIC_BED
    assert sf.info(str(assets.MUSIC_BED)).duration == pytest.approx(1.0)


def test_sting_and_bed_come_from_their_stems(music):
    _stem(music / "breaking.wav", 3.0, sr=24000, channels=1)
    _stem(music / "bed.wav", 10.0)
    assert sf.info(str(assets.ensure_breaking_sting())).duration == pytest.approx(3.0, abs=0.01)
    assert sf.info(str(assets.ensure_music_bed())).duration == pytest.approx(10.0, abs=0.01)


def test_every_motif_renders_and_has_onsets_for_every_voicing():
    for name in jingle.MOTIFS:
        for voicing in jingle.VOICINGS:
            ons = jingle.onsets(name, voicing)
            assert ons[0] == 0.0 and ons == sorted(ons)
    audio = jingle.render(jingle.DEFAULT, "news")
    assert audio.shape[1] == 2 and np.abs(audio).max() <= 0.9


def test_every_style_renders_and_the_chosen_one_is_the_default():
    for voicing, styles in (("news", jingle.NEWS_STYLES), ("sport", jingle.SPORT_STYLES),
                            ("breaking", jingle.BREAKING_STYLES)):
        assert jingle.STYLES[voicing] in styles
        for style in styles:
            audio = jingle.render(voicing=voicing, style=style)
            assert audio.shape[1] == 2 and 0.5 < np.abs(audio).max() <= 0.9
    assert jingle.render(voicing="sport") is jingle.render(voicing="sport", style=jingle.SPORT_STYLE)


NEWER = ("quayside", "phonein", "outabout", "rockpool", "panel", "chamber", "inquiry")


def test_the_newer_shows_have_their_own_idents_and_chosen_styles():
    """Until 2026-11-04 they borrowed the news's ident, words and all."""
    for show in NEWER:
        path, text = assets.IDENTS[show]
        assert path.name == f"bumper_{show}.wav" and "Port Wexley News" not in text
        assert jingle.STYLES[show] in jingle.SHOW_STYLES[show]
        for style in jingle.SHOW_STYLES[show]:
            audio = jingle.render(voicing=show, style=style)
            assert audio.shape[1] == 2 and 0.5 < np.abs(audio).max() <= 0.9
        assert (assets.MUSIC / f"ident_{show}.wav").exists()


def test_a_newer_shows_bumper_is_its_own_stem_and_line(music):
    _stem(music / "ident_inquiry.wav", 5.0)
    path = assets.ensure_bumper("inquiry")
    assert path.name == "bumper_inquiry.wav" and sf.info(str(path)).duration == pytest.approx(5.0, abs=0.05)
    voice_at = jingle.onsets(voicing="inquiry")[-1] + assets.VOICE_AFTER_S
    assert voice_at < 5.0                                    # the line comes in over the held chord


def test_a_bumper_speaks_in_its_presenters_own_pronunciation(music, monkeypatch):
    """Howard, Meg and Poppy speak British, with British clips only: without their lang, Kokoro's stand-ins voiced
    Quayside's, Out and About's and Rock Pool's idents (found 2026-11-07)."""
    said = {}

    def synth(text, voice, out, speed=1.0, lang=None):
        said[voice] = lang
        sf.write(out, np.full(assets.SR, 0.1, dtype=np.float32), assets.SR, subtype="PCM_16")
        return SynthResult(wav_path=out, duration_s=1.0, mouth_env=[0.5])
    monkeypatch.setattr(tts, "synthesize", synth)
    for show in ("quayside", "news"):
        _stem(music / f"ident_{show}.wav", 2.0)
        assets.ensure_bumper(show)
    assert said == {"bm_lanyon": "b", "af_heart": None}
