"""The nightly documentary: commissioned once a day, researched from the archive, made in stages
between live slots, kept apart from specials, and aired only in its slot.

No model or TTS calls: the model and Kokoro are stubbed, and the cache lives in a temporary directory.
"""
from __future__ import annotations

import dataclasses
import time

import pytest

from newsroom import documentary, special, workers
from newsroom import world as world_mod
from newsroom.buffer import Buffer
from newsroom.config import CONFIG
from newsroom.models import (
    DocumentaryCommission,
    DocumentaryOutline,
    DocumentaryResearch,
    Line,
    ScriptLine,
    SectionPlan,
    Segment,
    SegmentState,
    SegmentType,
    SpecialSection,
    TimelineEntry,
)
from newsroom.player import Player
from newsroom.tts import SynthResult


@pytest.fixture(autouse=True)
def tmp_paths(tmp_path, monkeypatch):
    old = CONFIG.paths
    object.__setattr__(CONFIG, "paths", dataclasses.replace(old, cache=tmp_path, world=tmp_path / "world.json"))
    monkeypatch.setattr(world_mod, "save", lambda *a, **k: None)
    monkeypatch.setattr(documentary, "_force", False)
    yield tmp_path
    object.__setattr__(CONFIG, "paths", old)


@pytest.fixture
def world():
    w = world_mod.seed()
    t = w.update_thread(None, "Second fire engine petition", "the petition reaches the station")
    w.record_aired("bulletin", "Petition for a second engine reaches 2,000 names", t, "Bea Kowalczyk thanked them")
    w.record_aired("field_report", "Market traders back the engine petition", t, "Dev Ramachandran signed first")
    w.record_aired("weather", "Squalls on Tuesday", None, "Gordon Pell on the front")
    return w


def _at(hhmm: str) -> float:
    lt = time.localtime()
    h, m = (int(x) for x in hhmm.split(":"))
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


def _decision(w) -> DocumentaryCommission:
    return DocumentaryCommission(subject="thread", thread_id=w.open_threads()[0].id,
                                 working_title="One Engine, One Town", angle="Does the town need it?",
                                 search_terms=["engine", "petition"])


# ------------------------------------------------------------ commissioning


def test_one_a_day_between_commission_time_and_the_slot(world):
    buf = Buffer()
    assert not documentary.should_commission(world, buf, _at("14:00"))      # before commission_from
    assert documentary.should_commission(world, buf, _at("19:00"))
    assert not documentary.should_commission(world, buf, _at("21:30"))      # the slot has passed
    world.last_documentary_date = world.last_date
    assert not documentary.should_commission(world, buf, _at("19:00"))      # already one today


def test_it_waits_while_a_special_is_in_hand(world):
    buf = Buffer()
    buf.submit_special(Segment(slot_id=special.SPECIAL_SLOT_BASE + 1, type=SegmentType.documentary, headline="x"))
    assert not documentary.should_commission(world, buf, _at("19:00"))


def test_the_editor_still_commissions_specials_while_a_documentary_waits(world, monkeypatch):
    from newsroom import adverts, continuity, desk, inquiry, panel, phonein, senior
    from newsroom.models import EditorDecision

    buf = Buffer()
    doc = documentary.commission(world, _decision(world))
    buf.mark(doc, SegmentState.ready)                  # made, waiting for 21:00
    pool = workers.WorkerPool(buf, world)
    asked = []
    monkeypatch.setattr(adverts, "seed_one", lambda w: False)
    monkeypatch.setattr(continuity, "bake_one", lambda w: False)
    monkeypatch.setattr(continuity, "should_make", lambda w, b: False)   # the waiting documentary's trail
    monkeypatch.setattr(adverts, "should_make", lambda: False)
    monkeypatch.setattr(desk, "should_plan", lambda w: False)
    monkeypatch.setattr(senior, "should_review", lambda w: False)
    monkeypatch.setattr(documentary, "should_commission", lambda w, b: False)
    for show in (phonein, inquiry, panel):           # their booking windows would come first at their hours
        monkeypatch.setattr(show, "should_commission", lambda w: False)
    monkeypatch.setattr(special, "should_check", lambda w: True)
    monkeypatch.setattr(special, "decide", lambda w, force=False: asked.append(1) or EditorDecision(commission=False))
    monkeypatch.setattr(pool, "_buffer_healthy", lambda: True)
    pool._idle_work()
    assert asked == [1]


def test_an_unknown_thread_becomes_a_history_piece(world, monkeypatch):
    d = DocumentaryCommission(subject="thread", thread_id="t999", working_title="Lost", angle="?")
    monkeypatch.setattr(documentary.llm, "complete_json", lambda *a, **k: d)
    out = documentary.decide(world)
    assert out.subject == "history" and out.thread_id is None
    assert world.last_documentary_date == world.last_date


# ------------------------------------------------------------------ research


def test_research_reads_every_piece_on_the_thread(world, monkeypatch):
    seg = documentary.commission(world, _decision(world))
    seen = {}

    def complete_json(task, schema, system, user, **k):
        seen["task"], seen["user"] = task, user
        return DocumentaryResearch(timeline=[TimelineEntry(date="2026-10-25", event="2,000 names", on_record=True)])
    monkeypatch.setattr(documentary.llm, "complete_json", complete_json)
    documentary.research(seg, world)
    assert seen["task"] == "documentary_research"
    pieces = seen["user"].split("ARCHIVE: a search")[0]
    assert "2,000 names" in pieces and "Market traders" in pieces and "Squalls" not in pieces


# --------------------------------------------------------------- making it


def _stub_model_and_voice(monkeypatch, n_sections=8, lines_per_section=3):
    notes = DocumentaryResearch(
        timeline=[TimelineEntry(date="2026-10-25", event="The petition passes 2,000 names", on_record=True),
                  TimelineEntry(date="1923", event="The old engine house opens", on_record=False)])
    outline = DocumentaryOutline(
        title="One Engine, One Town", standfirst="A petition and a fire station", intro="Tonight.", outro="Goodnight.",
        sections=[SectionPlan(heading=f"Part {i}", beats=["a beat"], backdrop="fire_station") for i in range(n_sections)])
    prompts = []

    def research(seg, w):
        return notes

    def section(seg, w, o, i, words):
        prompts.append(documentary.notes_for_prompt(seg))
        return SpecialSection(lines=[ScriptLine(speaker="reporter", text=f"Line {k}.") for k in range(lines_per_section)])

    def synth(text, voice, out, speed=1.0, lang=None, phone=False, age=None):
        out.write_bytes(b"RIFF")
        return SynthResult(wav_path=out, duration_s=2.0, mouth_env=[0.5])

    monkeypatch.setattr(documentary, "research", research)
    monkeypatch.setattr(special, "write_outline", lambda s, w: outline)
    monkeypatch.setattr(special, "write_section", section)
    monkeypatch.setattr(workers.tts, "synthesize", synth)
    return prompts


def test_a_documentary_is_researched_outlined_written_and_voiced_in_turns(world, monkeypatch):
    prompts = _stub_model_and_voice(monkeypatch)
    buf = Buffer()
    seg = documentary.commission(world, _decision(world))
    stages = []
    while seg.state is not SegmentState.ready:
        stages.append(seg.stage)
        seg = special.advance(seg, world, buf)
    assert stages[:2] == ["research", "outline"] and stages.count("sections") == 8
    assert stages.count("voice") == 3                  # 26 lines, ten a turn
    assert "[background]" in prompts[0] and "2,000 names" in prompts[0]
    assert seg.cues[0].payload["text"].startswith(CONFIG.documentary.title)
    assert world.documentaries[-1]["title"] == "One Engine, One Town"
    assert world.last_special_ts == 0                  # no special cooldown: it has its own slot
    assert buf.pop_special("special") is None          # it never airs at a special's break
    assert buf.pop_special("documentary") is seg


# ------------------------------------------------------------ where it airs


def _player_with_ready_documentary(world, last_type):
    buf = Buffer()
    seg = Segment(slot_id=special.SPECIAL_SLOT_BASE + 7, type=SegmentType.documentary, headline="One Engine",
                  work={"format": "documentary", "strand": CONFIG.documentary.title},
                  lines=[Line(speaker="anchor", text="Tonight.", duration_s=900.0)])
    buf.mark(seg, SegmentState.ready)
    player = Player(buf, world, producer=None, audio=False)
    player.last_type = last_type
    return player, seg


@pytest.mark.parametrize("hhmm, last_type, airs", [
    ("21:04", SegmentType.bumper, True),      # the slot: the first news bumper from 21:00
    ("20:58", SegmentType.bumper, False),     # not before it
    ("21:04", SegmentType.weather, False),    # only at a bumper
    ("23:05", SegmentType.bumper, False),     # the late news is outside the window
    ("01:05", SegmentType.testcard, False),   # never at the overnight test card, where specials go
])
def test_where_a_ready_documentary_airs(world, hhmm, last_type, airs):
    player, seg = _player_with_ready_documentary(world, last_type)
    player.update(_at(hhmm))
    assert (player.current is seg) is airs


def test_it_airs_once_a_day_and_is_archived_then(world, monkeypatch):
    monkeypatch.setattr(special.schedule, "now", lambda: _at("21:20"))
    player, seg = _player_with_ready_documentary(world, SegmentType.bumper)
    player.update(_at("21:04"))
    assert player.current is seg
    player._finish(_at("21:19"))
    assert world.archive[-1]["type"] == "documentary"
    assert not documentary.due(world, _at("21:30"))     # tonight's has aired


# ------------------------------------------------------------ archive footage


def _cached(tmp, h, lines, archive_text=None):
    """A voiced segment in the cache under `h`, as an earlier run left it."""
    for i, (speaker, text, name) in enumerate(lines):
        (tmp / f"{h}_{i:02d}.wav").write_bytes(b"RIFF")
    seg = Segment(slot_id=3, type=SegmentType.field_report, headline="Engine petition", state=SegmentState.ready,
                  content_hash=h, lines=[Line(speaker=s, text=t, guest_name=n, guest_role="Station Officer" if n else None,
                                              wav_path=tmp / f"{h}_{i:02d}.wav", duration_s=8.0)
                                         for i, (s, t, n) in enumerate(lines)])
    (tmp / f"{h}.json").write_text(seg.model_dump_json(), encoding="utf-8")
    return seg


QUOTE = "We cover the whole coast with one engine, and on a bad night that is not enough."


def test_clips_are_found_by_cache_key_or_by_text(world, tmp_paths):
    seg = _cached(tmp_paths, "aaaa1111", [("reporter", "Miles at the station tonight, with the petition.", None),
                                           ("guest", QUOTE, "Bea Kowalczyk")])
    _cached(tmp_paths, "bbbb2222", [("anchor", "Good evening, here is the news from the harbour tonight.", None)])
    text = " ".join(l.text for l in seg.lines)[:400]
    by_text = {"date": "2026-10-25", "type": "field_report", "headline": "Engine petition", "text": text}
    by_key = {**by_text, "text": "anything", "hash": "aaaa1111"}
    news = {"date": "2026-10-25", "type": "bulletin", "headline": "News", "hash": "bbbb2222",
            "text": "Good evening, here is the news from the harbour tonight."}
    for entry in (by_text, by_key):
        clips = documentary.find_clips(world, [entry, news])
        assert len(clips) == 1 and clips[0]["who"] == "Bea Kowalczyk" and clips[0]["text"] == QUOTE   # the quote
    assert documentary.find_clips(world, [news]) == []                    # an anchor reading the news isn't footage


def test_a_placed_clip_is_spliced_in_with_its_own_audio(world, tmp_paths, monkeypatch):
    _stub_model_and_voice(monkeypatch)
    src = _cached(tmp_paths, "aaaa1111", [("guest", QUOTE, "Bea Kowalczyk")])
    entry = {"date": "2026-10-25", "type": "field_report", "headline": "Engine petition", "hash": "aaaa1111",
             "text": QUOTE}
    research = documentary.research

    def research_with_clips(seg, w):
        seg.work["clips"] = documentary.find_clips(w, [entry])
        return research(seg, w)
    monkeypatch.setattr(documentary, "research", research_with_clips)
    outline = special.write_outline(None, None)
    outline.sections[1].archive_clip = "C1"
    outline.sections[3].archive_clip = "C9"                          # made up: dropped, not fatal
    monkeypatch.setattr(special, "write_outline", lambda s, w: outline)

    seg = documentary.commission(world, _decision(world))
    while seg.state is not SegmentState.ready:
        seg = special.advance(seg, world, Buffer())
    start = seg.work["starts"][1]
    clip = seg.lines[start + 1]                                      # after the line that leads into it
    assert clip.archive == "Archive · Sunday 25 October" and clip.text == QUOTE
    assert clip.wav_path != src.lines[0].wav_path and clip.wav_path.exists()   # its own copy
    assert sum(1 for l in seg.lines if l.archive) == 1
    caption = next(c for c in seg.cues if c.kind == "lower_third" and c.payload.get("subtitle", "").startswith("Archive"))
    assert caption.payload["title"] == "Bea Kowalczyk"


def test_archive_footage_draws(world):
    import pygame

    from newsroom import scenes
    from newsroom.player import View
    pygame.font.init()
    c = pygame.Surface(scenes.CANVAS)
    scenes.render(c, View(mode="special", backdrop="fire_station", speaker="guest", guest_name="Bea Kowalczyk",
                          archive="Archive · Sunday 25 October", strand=CONFIG.documentary.title), 1.0)


def test_a_report_clip_avoids_the_handback(world, tmp_paths):
    seg = _cached(tmp_paths, "cccc3333", [("reporter", "Thanks, Dana. I'm at the fire station tonight.", None),
                                           ("reporter", "The petition box goes up the steps, flour and all.", None)])
    entry = {"date": "2026-10-26", "type": "field_report", "headline": "x", "hash": "cccc3333", "text": "x"}
    assert documentary.find_clips(world, [entry])[0]["text"].startswith("The petition box")
