"""The annals (a page a day, kept for good) and the reviews made from them: The Week in Port Wexley on
Sundays, The Year on New Year's Eve, in the documentary's slot.

No model or TTS: both are stubbed. The cache and the annals live in a temporary directory.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import date, timedelta

import pytest

from newsroom import annals, continuity, documentary, prune, review, special, workers
from newsroom import world as world_mod
from newsroom.buffer import Buffer
from newsroom.config import CONFIG
from newsroom.models import (DocumentaryOutline, Line, ScriptLine, SectionPlan, Segment, SegmentState, SegmentType,
                             SpecialSection)
from newsroom.tts import SynthResult

SUNDAY = date(2026, 11, 15)
MONDAY = SUNDAY - timedelta(days=6)
QUOTE = "We cover the whole coast with one engine, and on a bad night that is not enough."


@pytest.fixture(autouse=True)
def tmp_paths(tmp_path, monkeypatch):
    old = CONFIG.paths
    object.__setattr__(CONFIG, "paths", dataclasses.replace(
        old, cache=tmp_path / "cache", world=tmp_path / "world.json", annals=tmp_path / "annals"))
    (tmp_path / "cache").mkdir()
    monkeypatch.setattr(world_mod, "save", lambda *a, **k: None)
    monkeypatch.setattr(documentary, "_force", False)
    monkeypatch.delenv("NEWSROOM_REVIEW", raising=False)
    yield tmp_path
    object.__setattr__(CONFIG, "paths", old)


def _voiced(h: str, who: str | None = "Bea Kowalczyk") -> None:
    """A piece in the cache as a run left it: the anchor, then a guest's (or Miles's) line worth replaying."""
    cache = CONFIG.paths.cache
    lines = [Line(speaker="anchor", text="Now to the fire station.", wav_path=cache / f"{h}_00.wav", duration_s=4.0),
             Line(speaker="guest" if who else "reporter", text=QUOTE, guest_name=who,
                  guest_role="Station Officer" if who else None, wav_path=cache / f"{h}_01.wav", duration_s=8.0,
                  mouth_env=[0.2, 0.6])]
    for l in lines:
        l.wav_path.write_bytes(b"RIFF" + h.encode())
    seg = Segment(slot_id=3, type=SegmentType.field_report, headline="Engine petition", state=SegmentState.ready,
                  content_hash=h, lines=lines)
    (cache / f"{h}.json").write_text(seg.model_dump_json(), encoding="utf-8")


def _week(upto: date = SUNDAY, pages: bool = True):
    """A town with a week behind it: the fire engine's petition every day, the harbour wall on three, a
    slow clock once; a piece of each day's petition coverage voiced in the cache; a page a day written
    the morning after, as the worker does."""
    w = world_mod.seed()
    w.threads = []
    ids: dict[str, str] = {}
    day = MONDAY
    while day <= upto:
        w.last_date = day.isoformat()
        n = (day - MONDAY).days
        stories = [("engine", "Second fire engine petition", f"Petition reaches {1000 + 200 * n} names")]
        if n in (1, 3, 5):
            stories.append(("wall", "Harbour wall tender", f"Wall tender: bid {n} opened"))
        if n == 2:
            stories.append(("clock", "Town hall clock six minutes slow", "Cyril Dunmore wants a look at the clock"))
        for key, title, headline in stories:
            ids[key] = w.update_thread(ids.get(key), headline if key in ids else title, f"{headline}.")
            h = f"{key}{n}"
            if key == "engine":
                _voiced(h)
            w.record_aired("field_report", headline, ids[key], f"{headline}. Bea Kowalczyk spoke.", show="news",
                           content_hash=h)
            if key == "engine":
                w.record_aired("bulletin", f"{headline}, the council hears", ids[key], "More on the petition.", show="news")
        w.thread(ids["engine"]).next_development = "Full council debates the petition on Thursday 19 November."
        w.record_aired("weather", f"Frost on day {n}", None, "Gordon Pell on the frost.", show="news")
        if pages and day < upto:
            w.last_date = (day + timedelta(days=1)).isoformat()
            annals.tick(w)                           # the morning after
        day += timedelta(days=1)
    w.last_date = upto.isoformat()
    return w, ids


# --------------------------------------------------------------------- the annals


def test_the_morning_after_the_day_has_a_page_and_its_keepsake(tmp_paths):
    w, ids = _week(upto=MONDAY + timedelta(days=2), pages=False)
    assert annals.pending(w) == MONDAY                               # the oldest day without a page first
    assert annals.tick(w) and annals.tick(w) and not annals.tick(w)  # Monday, Tuesday; today's isn't over
    page = annals.load(MONDAY + timedelta(days=1))
    assert page["weekday"] == "Tuesday" and page["pieces"] == 4 and page["weather"] == "Frost on day 1"
    assert [(s["thread_id"], s["pieces"]) for s in page["stories"]] == [(ids["engine"], 2), (ids["wall"], 1)]
    engine = page["stories"][0]
    assert engine["beats"][0] == "Petition reaches 1200 names" and engine["title"] == "Second fire engine petition"
    assert "Thursday 19 November" in engine["next"]
    (clip,) = page["clips"]
    assert clip["text"] == QUOTE and clip["who"] == "Bea Kowalczyk" and clip["story"] == ids["engine"]
    kept = annals.clips_dir() / clip["wav"]
    assert kept.read_bytes() == b"RIFFengine1" and kept.parent.parent == CONFIG.paths.annals


def test_clearing_the_cache_never_touches_the_annals(tmp_paths, monkeypatch):
    """The user's question, 2026-11-09: a review plays the annals' own copies, so the cache can go."""
    import os
    import time

    w, ids = _week()
    long_ago = time.time() - 30 * 86400
    for f in CONFIG.paths.cache.iterdir():
        os.utime(f, (long_ago, long_ago))
    w.archive = []                                                   # and the archive has moved on
    monkeypatch.setattr(prune, "KEY", __import__("re").compile(r"[a-z]+\d(?=[_.])"))   # this test's short keys
    for _, files, _ in prune.plan(7, w):
        prune.delete(files)
    assert not any(CONFIG.paths.cache.iterdir())
    _, clips = review.notes(w, review.WEEK)
    assert len(clips) == 1 and clips[0]["date"] == (SUNDAY - timedelta(days=1)).isoformat()
    assert annals.clips_dir() in __import__("pathlib").Path(clips[0]["wav"]).parents


# --------------------------------------------------------------------- the week


def test_sunday_is_the_week_in_review_when_there_is_a_week_to_review(tmp_paths, monkeypatch):
    w, _ = _week()
    assert review.tonight(w) == review.WEEK and review.strand_tonight(w) == "THE WEEK IN PORT WEXLEY"
    assert review.tonight(w, SUNDAY - timedelta(days=1)) is None                 # a Saturday
    for f in sorted(CONFIG.paths.annals.glob("*.json"))[:5]:
        f.unlink()
    assert review.tonight(w) is None                                             # two days on the page: not a week
    monkeypatch.setenv("NEWSROOM_REVIEW", "week")
    assert review.tonight(w, SUNDAY - timedelta(days=1)) == review.WEEK          # asked for, whatever the day
    monkeypatch.delenv("NEWSROOM_REVIEW")
    monkeypatch.setattr(review, "CONFIG", dataclasses.replace(
        CONFIG, documentary=dataclasses.replace(CONFIG.documentary, week_review=False)))
    assert review.tonight(_week()[0]) is None                                    # switched off


def test_the_notes_are_the_weeks_record_and_nothing_else(tmp_paths):
    w, ids = _week()
    notes, clips = review.notes(w, review.WEEK)
    events = [(t.date, t.event) for t in notes.timeline]
    assert all(t.on_record for t in notes.timeline) and events == sorted(events, key=lambda e: date(
        2026, 11, int(e[0].split()[1])))                                         # in the order it happened
    assert ("Monday 9 November", "Second fire engine petition") in events                   # named by its first headline
    assert any(d == "Sunday 15 November" and "still running: Petition reaches 2200 names." in e for d, e in events)
    assert any("Harbour wall tender" in e for _, e in events) and any("clock" in e.lower() for _, e in events)
    assert notes.people[0].name == "Bea Kowalczyk"
    assert notes.questions == ["Second fire engine petition: expected next, Full council debates the petition on "
                               "Thursday 19 November."]
    assert any(d.startswith("The week on Channel 7: 25 pieces on air over 7 days; 3 stories opened") for d in notes.details)
    assert any("The weather, Sunday 15 November: Frost on day 6" in d for d in notes.details)
    assert [c["id"] for c in clips] == ["C1"] and clips[0]["date"] == SUNDAY.isoformat()   # the story's latest keepsake


def _stub_writers(monkeypatch):
    seen = {}

    def complete_json(task, schema, system, user, **k):
        seen.setdefault(task, []).append((system, user))
        if task == "special_outline":
            return DocumentaryOutline(
                title="Frost, a Petition and a Slow Clock", standfirst="Seven days in Port Wexley", intro="Tonight.",
                outro="Goodnight.", sections=[SectionPlan(heading=f"Part {i}", beats=["a beat"], backdrop="fire_station",
                                                          archive_clip="C1" if i == 1 else None) for i in range(6)])
        return SpecialSection(lines=[ScriptLine(speaker="reporter", text=f"Line {k}.") for k in range(2)])

    def synth(text, voice, out, speed=1.0, lang=None, phone=False, age=None):
        out.write_bytes(b"RIFF")
        return SynthResult(wav_path=out, duration_s=2.0, mouth_env=[0.5])

    monkeypatch.setattr(special.llm, "complete_json", complete_json)
    monkeypatch.setattr(workers.tts, "synthesize", synth)
    return seen


def test_the_week_is_made_like_a_documentary_from_the_annals_with_no_editor_or_researcher(tmp_paths, monkeypatch):
    w, ids = _week()
    seen = _stub_writers(monkeypatch)
    buf = Buffer()
    seg = review.commission(w, review.WEEK)
    assert seg.work["strand"] == "THE WEEK IN PORT WEXLEY" and seg.headline == "The Week to Sunday 15 November"
    assert w.last_documentary_date == SUNDAY.isoformat() and documentary.presenter(seg) == "reporter"
    while seg.state is not SegmentState.ready:
        seg = special.advance(seg, w, buf)
    assert set(seen) == {"special_outline", "special_section"}                   # nobody chose it or researched it
    system, user = seen["special_outline"][0]
    assert "a fifteen-minute look back at the week" in system and "THE WEEK IN PORT WEXLEY" in system
    assert "RESEARCH NOTES" in user and "Petition reaches 2200 names" in user and "ARCHIVE CLIPS" in user
    system, user = seen["special_section"][0]
    assert "THIS IS A LOOK BACK at the week" in system and "announces nothing" in system
    assert seg.headline == "Frost, a Petition and a Slow Clock"
    clip = next(l for l in seg.lines if l.archive)
    assert clip.text == QUOTE and clip.archive == "Archive · Sunday 15 November" and clip.wav_path.exists()
    assert seg.cues[0].payload["text"] == "THE WEEK IN PORT WEXLEY: Frost, a Petition and a Slow Clock"
    assert seg.cues[-1].payload["subtitle"] == "The Week in Port Wexley"
    assert w.documentaries[-1]["subject"] == "week" and "Town history" not in w.summary_for_prompt()
    assert buf.pop_special("documentary") is seg


def test_the_worker_books_the_review_instead_of_asking_the_editor(tmp_paths, monkeypatch):
    from newsroom import adverts

    w, _ = _week()
    buf = Buffer()
    pool = workers.WorkerPool(buf, w)
    monkeypatch.setattr(adverts, "seed_one", lambda w: False)
    monkeypatch.setattr(continuity, "bake_one", lambda w: False)
    monkeypatch.setattr(pool, "_buffer_healthy", lambda: True)
    for mod in ("desk.should_plan", "senior.should_review", "phonein.should_commission", "inquiry.should_commission",
                "panel.should_commission", "chamber.should_commission"):
        name, fn = mod.split(".")
        monkeypatch.setattr(getattr(__import__("newsroom", fromlist=[name]), name), fn, lambda *a, **k: False)
    monkeypatch.setattr(documentary, "should_commission", lambda w, b: True)
    monkeypatch.setattr(documentary, "decide", lambda w: pytest.fail("the editor was asked on a Sunday"))
    pool._idle_work()
    seg = buf.next_job(timeout=0.1)
    assert seg is not None and seg.work["subject"] == "week" and seg.stage == "research"


def test_the_programme_card_and_the_trail_call_it_by_its_name(tmp_paths, monkeypatch):
    assert documentary.strand_name("THE WEEK IN PORT WEXLEY") == "The Week in Port Wexley"
    assert documentary.strand_name("PORT WEXLEY STORIES") == "Port Wexley Stories"
    w, _ = _week()
    assert review.strand_tonight(w, SUNDAY) == "THE WEEK IN PORT WEXLEY"
    assert review.strand_tonight(w, SUNDAY - timedelta(days=2)) == CONFIG.documentary.title


# --------------------------------------------------------------------- the year


def test_new_years_eve_is_the_year_with_hugh(tmp_paths, monkeypatch):
    w, ids = _week()
    eve = date(2026, 12, 31)
    w.last_date = eve.isoformat()
    assert review.tonight(w) is None                                             # seven pages are not a year
    page = json.loads(annals.path(MONDAY).read_text(encoding="utf-8"))
    for k in range(20):                                                          # a quiet December on the page
        d = date(2026, 12, 1) + timedelta(days=k)
        annals.path(d).write_text(json.dumps(page | {"date": d.isoformat(), "clips": []}), encoding="utf-8")
    assert review.tonight(w) == review.YEAR and review.strand_tonight(w) == "THE YEAR IN PORT WEXLEY"
    seg = review.commission(w, review.YEAR)
    assert seg.headline == "Port Wexley in 2026" and documentary.presenter(seg) == "historian"
    notes, clips = review.notes(w, review.YEAR)
    assert notes.timeline[0].date == "Monday 9 November" and "Second fire engine petition" in notes.timeline[0].event
    assert any("The year on Channel 7" in d for d in notes.details)
    assert len(clips) == 6 and len({c["date"] for c in clips}) == 6              # a keepsake from each day it has one
    assert "look back at the year" in documentary.outline_system(seg, seg.work["strand"])
    assert "Hugh Tremayne" in documentary.outline_system(seg, seg.work["strand"])


def test_todays_page_read_live_has_no_result_of_a_match_still_to_come(tmp_paths, monkeypatch):
    """The Sunday review is booked at six from today's page as it stands: nothing later than now is on it."""
    from datetime import datetime

    from newsroom import schedule

    w = world_mod.seed()
    saturday = date(2026, 11, 7)                                                 # the Tides away, 15:00; no auction
    friday = date(2026, 11, 6)
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 7, 10, 0).timestamp())
    assert annals.digest(w, saturday)["sport"] == []
    assert "Friday 06 November" in annals.digest(w, friday)["auction"]           # yesterday's page is whole
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 6, 6, 0).timestamp())
    assert annals.digest(w, friday)["auction"] == ""                             # before the hammer
    monkeypatch.setattr(schedule, "now", lambda: datetime(2026, 11, 7, 18, 0).timestamp())
    assert any("the Tides lost 4-1" in line for line in annals.digest(w, saturday)["sport"])
