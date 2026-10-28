"""The Last Ferry: a main guest in two parts, then a shorter second guest in one; the house
band plays each new guest on and the show back from a break.

Kokoro is stubbed and the model is off (conftest), so scripts come from the templates.
"""
import time

import numpy as np
import soundfile as sf

from newsroom import assets, schedule, tts, workers, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Segment, SegmentType as T
from newsroom.producer import Producer
from newsroom.tts import SynthResult

LATE = schedule.SHOWS["late"]


def _hour() -> list[Segment]:
    lt = time.localtime()
    p = Producer(Buffer(), 600, start_ts=time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 22, 0, 30, 0, 0, -1)))
    out = []
    while not out or out[-1].show == "late":
        out.append(p.plan_one())
    return out[:-1]


def test_the_main_guest_has_two_parts_then_a_shorter_guest_has_one():
    hour = _hour()
    order = [(s.type, s.part) for s in hour[:7]]
    assert order == [(T.bumper, ""), (T.monologue, "open"), (T.interview, ""), (T.ad_break, ""),
                     (T.interview, "cont"), (T.interview, "couch"), (T.vox_pop, "")]
    short = hour[5]
    assert short.work["first_part"] == hour[4].slot_id            # the main guest's second part
    assert hour[4].work.get("stays_on") and not hour[2].work.get("stays_on")   # part two: no goodbye yet
    assert short.target_s == schedule.SHORT_GUEST_S < LATE.target_s[T.interview]
    assert short.brief.startswith("a SHORTER SECOND GUEST")
    assert hour[-1].part == "close"
    assert sum(s.target_s for s in hour) < 3600 + 240                 # the hour still ends near the hour


def test_the_order_never_runs_two_desk_pieces_together_when_it_wraps():
    items = [LATE.item(i) for i in range(len(LATE.pattern) * 3)]
    assert not any(a.type is b.type is T.links for a, b in zip(items, items[1:]))


def test_the_house_band_plays_a_guest_on_and_back_from_the_break(tmp_path, monkeypatch):
    def synth(text, voice, out, speed=1.0, lang=None):
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(out, np.zeros(assets.SR // 2, dtype=np.float32), assets.SR, subtype="PCM_16")
        return SynthResult(wav_path=out, duration_s=0.5, mouth_env=[0.0])
    monkeypatch.setattr(tts, "synthesize", synth)
    monkeypatch.setattr(assets, "MUSIC", tmp_path / "music")             # no stems: the code renders
    monkeypatch.setattr(assets, "BAND", {k: tmp_path / f"band_{k}.wav" for k in assets.BAND})
    w = world_mod.seed()
    first = workers.generate(Segment(slot_id=900, type=T.interview, show="late", target_s=180), w)
    again = workers.generate(Segment(slot_id=902, type=T.interview, show="late", part="cont", target_s=180), w)
    news = workers.generate(Segment(slot_id=903, type=T.interview, show="news", target_s=90), w)
    assert first.lines[0].text == "" and first.lines[0].wav_path == tmp_path / "band_walkon.wav"
    assert again.lines[0].wav_path == tmp_path / "band_button.wav"
    assert 1.5 < first.lines[0].duration_s < 4.0 and not first.lines[0].mouth_env
    assert news.lines[0].text                                            # only the late show has a band


def test_the_main_guest_stays_on_the_couch_for_the_second(monkeypatch):
    from newsroom import llm, writers
    from newsroom.player import Player
    from newsroom.scenes import _interview_marks
    from newsroom.locations import MARKS

    seen = {}

    def write(task, schema, system, user):
        seen["user"], seen["schema"] = user, schema
        return schema.model_validate({
            "headline": "Two guests and a gull", "lower_third": "The Last Ferry",
            "guest_name": "Tam Buchanan", "guest_role": "boatbuilder", "guest_gender": "m",
            "lines": [{"speaker": "late_host", "text": "Please welcome Tam Buchanan."},
                      {"speaker": "guest", "guest_name": "Tam Buchanan", "text": "Evening, Vincent."},
                      {"speaker": "guest", "guest_name": "marjorie pell", "text": "Tam built my dinghy."},
                      {"speaker": "guest", "text": "And she still owes me for the oars."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    monkeypatch.setitem(writers._last_interview, "late",
                        {"slot": 4, "name": "Marjorie Pell", "role": "retired lighthouse keeper", "asked": "  ..."})
    w = world_mod.seed()
    seg = Segment(slot_id=5, type=T.interview, show="late", part="couch", target_s=100, work={"first_part": 4})
    writers.script_segment(seg, w)
    assert "ON THE COUCH: Marjorie Pell (retired lighthouse keeper)" in seen["user"]
    assert "guest_name" in seen["schema"].model_fields["lines"].annotation.__args__[0].model_fields
    names = [(l.guest_name, l.guest_role) for l in seg.lines if l.speaker == "guest"]
    assert names == [("Tam Buchanan", "boatbuilder"), ("Marjorie Pell", "retired lighthouse keeper"),
                     ("Tam Buchanan", "boatbuilder")]
    assert seg.work["couch"] == "Marjorie Pell"
    assert writers._last_interview["late"]["name"] == "Tam Buchanan"     # now the last interview

    pl = Player(Buffer(), w, producer=None, audio=False)
    people = pl._people(seg)
    assert people == [("late_host", None), ("guest", "Tam Buchanan"), ("guest", "Marjorie Pell")]

    class V:
        show, speaker, guest_name, set = "late", "guest", "Marjorie Pell", "interview"
    V.people = people
    marks = {name: m for _, name, m in _interview_marks(V)}
    assert marks["Tam Buchanan"] == MARKS["studio_late"]["guest_near"]
    assert marks["Marjorie Pell"] == MARKS["studio_late"]["guest_far"]


def test_without_the_guest_before_the_couch_is_an_ordinary_short_interview(monkeypatch):
    from newsroom import writers

    monkeypatch.setitem(writers._last_interview, "late", {"slot": 1, "name": "X", "role": "y", "asked": ""})
    seg = Segment(slot_id=5, type=T.interview, show="late", part="couch", target_s=100, work={"first_part": 4})
    writers.script_segment(seg, world_mod.seed())                       # the template: one guest
    assert "couch" not in seg.work
