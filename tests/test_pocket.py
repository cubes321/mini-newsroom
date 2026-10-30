"""Pocket TTS for the town's voices: a local guest whose Kokoro voice has a designed reference clip is cloned
by Pocket; presenters, visitors and the puppet stay Kokoro's, and a Pocket failure costs the voice, never the
line. Both engines are stubbed: no model loads."""
from __future__ import annotations

import dataclasses
from pathlib import Path

import numpy as np

from newsroom import tts


def _engines(monkeypatch, tmp_path, backend="pocket", pocket_fails=False):
    cfg = dataclasses.replace(tts.CONFIG, tts=dataclasses.replace(tts.CONFIG.tts, backend=backend))
    monkeypatch.setattr(tts, "CONFIG", cfg)
    monkeypatch.setattr(tts, "VOICES_DIR", Path(tmp_path))
    (Path(tmp_path) / "bm_lewis.b.wav").write_bytes(b"")
    used = []

    def pocket(text, clip):
        used.append(("pocket", clip.name))
        if pocket_fails:
            raise RuntimeError("stub")
        return np.full(2400, 0.5, np.float32)

    def kokoro(text, voice, speed, lang):
        used.append(("kokoro", voice))
        return np.full(2400, 0.5, np.float32)
    monkeypatch.setattr(tts, "_pocket_speak", pocket)
    monkeypatch.setattr(tts, "_kokoro", kokoro)
    return used


def test_a_local_guest_with_a_clip_is_cloned_by_pocket(monkeypatch, tmp_path):
    used = _engines(monkeypatch, tmp_path)
    tts.synthesize("Fifty-one years.", "bm_lewis", tmp_path / "a.wav", lang="b")
    tts.synthesize("Howdy.", "bm_lewis", tmp_path / "b.wav", lang="a")            # a visitor: no clip yet
    tts.synthesize("Good evening.", "af_heart", tmp_path / "c.wav")                # a presenter
    tts.synthesize("Chips!", "bm_lewis@puppet", tmp_path / "d.wav", lang="b")     # an effect stays Kokoro's
    assert used == [("pocket", "bm_lewis.b.wav"), ("kokoro", "bm_lewis"), ("kokoro", "af_heart"),
                    ("kokoro", "bm_lewis")]


def test_kokoro_takes_the_line_when_pocket_fails_or_is_off(monkeypatch, tmp_path):
    used = _engines(monkeypatch, tmp_path, pocket_fails=True)
    res = tts.synthesize("Fifty-one years.", "bm_lewis", tmp_path / "a.wav", lang="b")
    assert used == [("pocket", "bm_lewis.b.wav"), ("kokoro", "bm_lewis")] and res.duration_s > 0
    used = _engines(monkeypatch, tmp_path, backend="kokoro")
    tts.synthesize("Fifty-one years.", "bm_lewis", tmp_path / "b.wav", lang="b")
    assert used == [("kokoro", "bm_lewis")]


def test_a_phone_caller_on_pocket_still_comes_down_the_line(monkeypatch, tmp_path):
    used = _engines(monkeypatch, tmp_path)
    called = []
    monkeypatch.setattr(tts, "telephone", lambda a, sr: called.append(1) or a)
    tts.synthesize("Hello, Jonah?", "bm_lewis", tmp_path / "a.wav", lang="b", phone=True)
    assert used == [("pocket", "bm_lewis.b.wav")] and called


def test_a_guest_gets_a_clip_of_their_own_age(monkeypatch, tmp_path):
    used = _engines(monkeypatch, tmp_path)
    for v in ("af_kore", "af_nova", "af_sky"):
        (Path(tmp_path) / f"{v}.b.wav").write_bytes(b"")
    (Path(tmp_path) / "voices.toml").write_text('[af_kore]\ngender = "f"\nage = "old"\n'
                                                '[af_nova]\ngender = "f"\nage = "young"\n'
                                                '[af_sky]\ngender = "f"\nage = "young"\n', encoding="utf-8")
    tts.synthesize("Hiya.", "af_kore", tmp_path / "a.wav", lang="b", age="young")       # young Nell, an old clip
    tts.synthesize("Hiya.", "af_kore", tmp_path / "b.wav", lang="b", age="young")
    tts.synthesize("Dear me.", "af_kore", tmp_path / "c.wav", lang="b", age="old")
    tts.synthesize("Dear me.", "af_kore", tmp_path / "d.wav", lang="b")                  # age not known: her own
    young = used[0][1]
    assert young in ("af_nova.b.wav", "af_sky.b.wav") and used[1][1] == young
    assert used[2][1] == used[3][1] == "af_kore.b.wav"


def test_if_pocket_wont_load_it_is_tried_once_and_kokoro_speaks(monkeypatch, tmp_path):
    used = _engines(monkeypatch, tmp_path)
    monkeypatch.setattr(tts, "_POCKET", {"model": None})                 # the load failed earlier
    tts.synthesize("Fifty-one years.", "bm_lewis", tmp_path / "a.wav", lang="b")
    assert used == [("kokoro", "bm_lewis")]
