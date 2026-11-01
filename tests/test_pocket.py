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


def test_a_designed_voice_falls_back_to_its_kokoro_stand_in(monkeypatch, tmp_path):
    used = _engines(monkeypatch, tmp_path, pocket_fails=True)
    (Path(tmp_path) / "bm_thorne.b.wav").write_bytes(b"")
    (Path(tmp_path) / "voices.toml").write_text('[bm_thorne]\nperson = "Gerald Thorne"\nkokoro = "bm_lewis"\n',
                                                encoding="utf-8")
    tts.synthesize("Show me a costing.", "bm_thorne", tmp_path / "a.wav", lang="b")
    assert used == [("pocket", "bm_thorne.b.wav"), ("kokoro", "bm_lewis")]       # never Kokoro asked for "bm_thorne"


def test_the_council_and_the_recast_presenters_have_clips_of_their_own():
    """Every voice chosen on 2026-11-01 has its reference clip and a Kokoro stand-in that exists in Kokoro's
    naming, and the voice's own name keeps the gender a guest's look is drawn from."""
    from newsroom import council, world as world_mod

    cast = tts._cast()
    w = world_mod.seed()
    chosen = dict(council.VOICES) | {c.name: c.voice for c in w.characters
                                     if c.id in ("sport_reporter", "business", "travel")}
    assert len(chosen) == 10 and len(set(chosen.values())) == 10
    for name, voice in chosen.items():
        assert (tts.VOICES_DIR / f"{voice}.b.wav").exists(), name
        assert cast[voice]["person"] == name and cast[voice]["kokoro"][:3] in ("af_", "bf_", "am_", "bm_")
        assert "gender" not in cast[voice]                                           # never offered to a guest
    for name, _, gender, *_ in council.COUNCILLORS:
        p = w.person_by_name(name)
        assert p.voice == council.VOICES[name] and p.voice[1] == gender and w.lang_for("guest", name) == "b"
    assert w.person_by_name(council.CHAIR).voice == "bf_strand" and w.lang_for("guest", council.CHAIR) == "b"


def test_a_saved_world_takes_the_new_voices(tmp_path):
    """A town saved before 2026-11-01 (Gerald on a guest voice, Tamsin on af_sarah) is recast on load."""
    import json

    from newsroom import world as world_mod

    w = world_mod.seed()
    w.person_by_name("Gerald Thorne").voice = "bm_lewis"
    w.person_by_name("Helen Strand").voice, w.person_by_name("Helen Strand").accent = "bf_isabella", ""
    w.character("sport_reporter").voice = "af_sarah"
    path = tmp_path / "world.json"
    world_mod.save(w, path)
    back = world_mod._from_dict(json.loads(path.read_text(encoding="utf-8")))
    assert back.person_by_name("Gerald Thorne").voice == "bm_thorne"
    assert back.person_by_name("Helen Strand").voice == "bf_strand"
    assert back.character("sport_reporter").voice == "bf_jago"


def test_if_pocket_wont_load_it_is_tried_once_and_kokoro_speaks(monkeypatch, tmp_path):
    used = _engines(monkeypatch, tmp_path)
    monkeypatch.setattr(tts, "_POCKET", {"model": None})                 # the load failed earlier
    tts.synthesize("Fifty-one years.", "bm_lewis", tmp_path / "a.wav", lang="b")
    assert used == [("kokoro", "bm_lewis")]
