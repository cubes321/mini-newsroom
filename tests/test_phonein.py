"""Have Your Say: Jonah Pike's news phone-in at 10:00. The question and the studio guest are booked in
the morning; callers are on the phone, not on the set, and sound like it. The model is stubbed: no
network."""
from __future__ import annotations

import time
from datetime import date, timedelta

import numpy as np
import pytest
from pydantic import ValidationError

from newsroom import phonein, schedule, tts, workers, world as world_mod, writers
from newsroom.buffer import Buffer
from newsroom.models import Line, PhoneInBooking, Segment, SegmentType as T, script_schema
from newsroom.player import Player
from newsroom.tts import SynthResult


def _town():
    w = world_mod.seed()
    w.threads = []
    for title, n in (("Coast road closed to lorries", 9), ("Harbour wall report due Friday", 7),
                     ("Coffee stall wants a pitch", 4)):
        w.thread(w.update_thread(None, title, "so far")).mentions = n
    return w


def _stub(monkeypatch, reply):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, user))
        if isinstance(reply, Exception):
            raise reply
        return reply
    monkeypatch.setattr(phonein.llm, "complete_json", complete_json)
    return seen


def _booking(w, guest="Helen Strand", **kw):
    return PhoneInBooking(**{"thread_id": w.threads[0].id, "question": "Should the lorry ban stay?",
                             "guest": guest, "guest_stance": "for keeping it until the slates are fixed",
                             "callers": ["a haulier", "a parent on the coast road", "a shopkeeper", "a cyclist"],
                             **kw})


def test_the_question_and_guest_are_booked_and_given_to_every_item(monkeypatch):
    w = _town()
    seen = _stub(monkeypatch, _booking(w))
    entry = phonein.commission(w)
    task, user = seen[0]
    assert task == "phonein" and "Coast road closed to lorries" in user.split("STORIES:")[1]
    assert "  - Helen Strand," in user.split("PEOPLE:")[1]
    assert phonein.today(w) == entry and not entry.get("stand_in")
    brief = phonein.for_prompt(w, T.interview)
    assert "TODAY'S QUESTION: \"Should the lorry ban stay?\"" in brief and "THE STUDIO GUEST" in brief
    assert "Helen Strand" in brief and phonein.NUMBER in brief and "THIS CALLER" not in brief
    assert "THIS CALLER (call 1 of the morning): a haulier." in phonein.for_prompt(w, T.call)


def test_each_call_takes_the_next_kind_of_caller(monkeypatch):
    w = _town()
    _stub(monkeypatch, _booking(w))
    phonein.commission(w)
    for n in range(5):
        brief = phonein.for_prompt(w, T.call)
        assert brief.count("THIS CALLER") == 1 and ("SOMEONE ELSE" in brief) == (n >= 4)   # the second lap
        w.record_aired(T.call.value, f"Caller {n}", w.threads[0].id, "I rang.", show=phonein.SHOW)
    assert "THIS CALLER (call 6 of the morning): a parent on the coast road." in phonein.for_prompt(w, T.call)


def test_a_failed_or_wrong_booking_gets_a_stand_in(monkeypatch):
    w = _town()
    _stub(monkeypatch, phonein.llm.LLMError("down"))
    entry = phonein.commission(w)
    assert entry["stand_in"] and entry["thread_id"] == w.threads[0].id and entry["guest"]
    assert w.person_by_name(entry["guest"]).kind == "official" and len(entry["callers"]) >= 4
    for bad in (_booking(w, guest="Nobody Known"), _booking(w, thread_id="t999")):
        w.phone_ins = []
        _stub(monkeypatch, bad)
        assert phonein.commission(w)["stand_in"]


def test_nothing_booked_by_ten_the_show_takes_the_stand_in_without_a_call(monkeypatch):
    w = _town()
    seen = _stub(monkeypatch, phonein.llm.LLMError("should not be called"))
    assert "TODAY'S QUESTION" in phonein.for_prompt(w) and not seen
    phonein.for_prompt(w, T.call)
    assert len(w.phone_ins) == 1


def test_it_is_booked_after_breakfast_and_airs_from_ten_to_eleven():
    w = _town()
    lt = time.localtime()

    def at(h, m):
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
    assert not phonein.should_commission(w, at(8, 0)) and phonein.should_commission(w, at(9, 15))
    assert not phonein.should_commission(w, at(10, 5))
    assert schedule.show_at(at(10, 30)).id == "phonein" and schedule.show_end(at(10, 30)) == at(11, 0)
    assert schedule.show_at(at(11, 5)).id == "news"


def _call(w, schema, lines, **kw):
    return schema.model_validate({"headline": "Cross about the lorries", "lower_third": "Have Your Say",
                                  "caller_name": "Sandra Polglase", "caller_from": "Fore Street",
                                  "caller_gender": "f", "caller_age": "middle", "caller_accent": "british",
                                  "thread_id": w.threads[0].id, "caller_memory": "runs the launderette; wants the ban kept",
                                  "lines": lines, **kw})


def test_a_call_needs_its_caller_to_speak():
    w = _town()
    schema = script_schema(T.call, schedule.get("phonein").cast_for(T.call))
    with pytest.raises(ValidationError):
        _call(w, schema, [{"speaker": "host_b", "text": "Line one?"},
                          {"speaker": "guest", "text": "It stays.", "guest_name": "Helen Strand"},
                          {"speaker": "host_b", "text": "Thanks."}])


def test_a_call_keeps_the_caller_on_the_phone_and_the_story_where_it_was(monkeypatch):
    w = _town()
    _stub(monkeypatch, _booking(w))
    phonein.commission(w)
    story = w.threads[0]
    mentions, opened = story.mentions, len(w.threads)
    schema = script_schema(T.call, schedule.get("phonein").cast_for(T.call))
    script = _call(w, schema, [
        {"speaker": "host_b", "text": "Line two, Sandra on Fore Street, you're on Have Your Say."},
        {"speaker": "guest", "text": "Morning Jonah. Keep the ban, the shop windows have stopped rattling."},
        {"speaker": "guest", "text": "We'll review it in the spring.", "guest_name": "Helen"},   # first name alone
        {"speaker": "guest", "text": "Spring? That's what you said about the bins.", "guest_name": "Sandra Polglase"},
        {"speaker": "host_b", "text": "Thanks for ringing, Sandra."}])
    monkeypatch.setattr(writers.llm, "complete_json", lambda *a, **k: script)
    seg = Segment(slot_id=4, type=T.call, show="phonein", target_s=100)
    writers.script_segment(seg, w)
    guests = [(l.guest_name, l.guest_role) for l in seg.lines if l.speaker == "guest"]
    helen = w.person_by_name("Helen Strand").role
    assert guests == [("Sandra Polglase", "On the line from Fore Street"), ("Helen Strand", helen),
                      ("Sandra Polglase", "On the line from Fore Street")]
    assert seg.work["caller"] == "Sandra Polglase" and seg.work["studio_guest"] == "Helen Strand"
    assert seg.thread_id == story.id and story.mentions == mentions and len(w.threads) == opened
    sandra = w.person_by_name("Sandra Polglase")
    assert sandra.kind == "resident" and sandra.memories[-1]["show"] == phonein.CALLED


def test_someone_who_rang_before_may_ring_again(monkeypatch):
    w = _town()
    _stub(monkeypatch, _booking(w))
    phonein.commission(w)
    p = w.ensure_person("Sandra Polglase", "resident", gender="f")
    yesterday = (date.fromisoformat(w.last_date) - timedelta(days=1)).isoformat()
    p.memories = [{"date": yesterday, "show": phonein.CALLED, "said": "wants the ban kept"}]
    assert "Sandra Polglase: wants the ban kept" in phonein.for_prompt(w, T.call)
    p.memories.append({"date": w.last_date, "show": phonein.CALLED, "said": "rang again"})
    brief = phonein.for_prompt(w, T.call)
    assert "Sandra Polglase:" not in brief                               # not offered twice in a morning,
    assert "RUNG ALREADY THIS MORNING: Sandra Polglase." in brief        # and no new caller named like her


def test_a_call_has_a_canned_script_when_the_model_is_down(monkeypatch):
    w = _town()
    _stub(monkeypatch, _booking(w))
    phonein.commission(w)
    monkeypatch.setattr(writers.llm, "complete_json", lambda *a, **k: (_ for _ in ()).throw(writers.llm.LLMError("x")))
    seg = Segment(slot_id=5, type=T.call, show="phonein", target_s=100)
    writers.script_segment(seg, w)
    assert seg.lines[0].speaker == "host_b" and seg.work["caller"] == "Pam Rowe"
    assert any(l.guest_name == "Helen Strand" for l in seg.lines)


def _on_air(w):
    pl = Player(Buffer(), w, producer=None, audio=False)
    seg = Segment(slot_id=6, type=T.call, show="phonein", target_s=100,
                  work={"caller": "Sandra Polglase", "caller_from": "Fore Street", "studio_guest": "Helen Strand"},
                  lines=[Line(speaker="host_b", text="Line two?", duration_s=2.0, mouth_env=[0.5] * 40),
                         Line(speaker="guest", text="Keep it.", guest_name="Sandra Polglase",
                              guest_role="On the line from Fore Street", duration_s=2.0, mouth_env=[0.9] * 40),
                         Line(speaker="guest", text="Spring.", guest_name="Helen Strand", guest_role="Leader",
                              duration_s=2.0, mouth_env=[0.5] * 40)])
    pl.current, pl.line_idx = seg, 1
    pl.seg_start = pl.line_start = schedule.now() - 0.5
    return pl, seg


def test_the_caller_is_a_box_and_a_waveform_and_the_guest_stays_in_the_armchair():
    w = _town()
    pl, seg = _on_air(w)
    assert pl._people(seg) == [("host_b", None), ("guest", "Helen Strand")]
    v = pl.view()
    assert v.set == "interview" and v.caller == ("Sandra Polglase", "Fore Street")
    assert v.wave and len(v.wave) <= 24 and v.lower_third == ("Sandra Polglase", "On the line from Fore Street")
    pl.line_idx = 2                                   # the guest answers: the caller listens, the wave is flat
    v = pl.view()
    assert v.caller and not v.wave


def test_the_scene_draws_the_caller_box():
    import pygame

    from newsroom import scenes

    w = _town()
    pl, _ = _on_air(w)
    pygame.font.init()
    canvas = pygame.Surface(scenes.CANVAS)
    scenes.render(canvas, pl.view(), 1.0)
    box = scenes.CALLER_BOX
    assert canvas.get_at((box.x + 2, box.bottom - 4))[:3] == (26, 34, 56)   # the box is up


def test_only_the_caller_goes_down_the_phone_line(monkeypatch, tmp_path):
    w = _town()
    seen = []

    def synth(text, voice, out, speed=1.0, lang=None, phone=False):
        seen.append(phone)
        return SynthResult(wav_path=out, duration_s=1.0, mouth_env=[0.5])
    monkeypatch.setattr(tts, "synthesize", synth)
    _, seg = _on_air(w)
    workers.voice_segment(seg, w, "test")
    assert seen == [False, True, False]


def test_the_telephone_keeps_the_voice_band_and_drops_the_rest():
    sr = 24000
    t = np.arange(sr) / sr
    low, voice = np.sin(2 * np.pi * 100 * t), np.sin(2 * np.pi * 1000 * t)
    out = tts.telephone((0.3 * low + 0.3 * voice).astype(np.float32), sr)
    spec = np.abs(np.fft.rfft(out))
    assert len(out) == sr and np.abs(out).max() <= 0.9
    assert spec[100] < 0.01 * spec[1000]
