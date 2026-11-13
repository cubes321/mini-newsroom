"""Continuity: idents, the programme card and notices fill a gap in turn with the adverts.

Kokoro is stubbed: every line is a short quiet WAV.
"""
from datetime import date, datetime

import numpy as np
import pytest
import soundfile as sf

from newsroom import adverts, assets, continuity, schedule, tts, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentState, SegmentType
from newsroom.player import Player
from newsroom.producer import Producer
from newsroom.tts import SynthResult


@pytest.fixture
def cont(tmp_path, monkeypatch):
    def synth(text, voice, out, speed=1.0, lang=None):
        out.parent.mkdir(parents=True, exist_ok=True)
        sf.write(out, np.zeros(assets.SR // 2, dtype=np.float32), assets.SR, subtype="PCM_16")
        return SynthResult(wav_path=out, duration_s=0.5, mouth_env=[0.0])
    monkeypatch.setattr(tts, "synthesize", synth)
    monkeypatch.setattr(assets, "MUSIC", tmp_path / "music")             # no stems: the code renders
    p = continuity.Pool(tmp_path / "continuity")
    monkeypatch.setattr(continuity, "_pool", p)
    return p


def _ts(hhmm: str, day: date = date(2026, 10, 27)) -> float:
    h, m = map(int, hhmm.split(":"))
    return datetime.combine(day, datetime.min.time()).replace(hour=h, minute=m).timestamp()


def test_baking_does_this_shows_idents_first_then_the_card_tides_and_notices(cont):
    now = _ts("19:20")                                              # Coastwide
    kinds = []
    while continuity.bake_one(world_mod.seed(), now):
        kinds.append(max(cont.items(), key=lambda i: (cont.dir / f"{i.id}.json").stat().st_mtime_ns).id)
    assert kinds[:2] == ["ident_magazine_0", "ident_magazine_1"]
    assert {"programmes_20261027_2000", "tides_20261027"} <= set(kinds)
    assert sum(k.startswith("notice_") for k in kinds) == len(continuity.NOTICES)
    assert not continuity.bake_one(world_mod.seed(), now)          # nothing left to do


def test_the_programme_card_lists_whats_next_and_expires_when_it_starts(cont):
    now = _ts("19:20")
    it = continuity.bake_programmes(now, world_mod.seed())
    card = it.segment.work["continuity"]
    assert card["lines"] == ["20:00  THE INQUIRY", "20:30  THE PANEL",
                             "21:00  PORT WEXLEY STORIES", "22:00  THE LAST FERRY"]     # tonight's documentary at nine
    assert it.valid_until == _ts("20:00")
    at_2030 = continuity.bake_programmes(_ts("20:30"), world_mod.seed())
    assert at_2030.valid_until == _ts("21:00")                # gone before "coming up at nine" is wrong
    cont.add(it)
    assert cont.pick("card", "magazine", _ts("19:59")) is not None
    assert cont.pick("card", "magazine", _ts("20:00")) is None


def test_an_ident_is_in_the_shows_tune_and_rebuilt_for_a_new_stem(cont, tmp_path):
    w = world_mod.seed()
    now = _ts("10:00")
    continuity.bake_one(w, now)
    assert cont.pick("ident", "news", now).work["continuity"]["kind"] == "ident"
    assert cont.pick("ident", "late", now) is None
    assets.MUSIC.mkdir(parents=True)
    sf.write(assets.MUSIC / "ident_news.wav", np.zeros(assets.SR * 3, dtype=np.float32), assets.SR)
    continuity.bake_one(w, now)
    assert cont.get("ident_news_0").source_mtime == (assets.MUSIC / "ident_news.wav").stat().st_mtime


def _player(cont, ads_pool, last=None):
    buf = Buffer()
    pl = Player(buf, world_mod.seed(), Producer(buf, 600), audio=False, ads=ads_pool, cont=cont)
    pl.last_type = last
    return pl


def _ad():
    return Segment(slot_id=-1, type=SegmentType.advert, state=SegmentState.ready, work={"advert": {"business": "x"}})


class _Ads:
    def __init__(self, n):
        self.n = n

    def pick(self):
        if self.n <= 0:
            return None
        self.n -= 1
        return _ad()


def test_a_gap_runs_ident_advert_card_advert_advert_then_the_filler(cont, monkeypatch):
    now = _ts("10:00")
    monkeypatch.setattr(schedule, "now", lambda: now)
    w = world_mod.seed()
    while continuity.bake_one(w, now):
        pass
    pl = _player(cont, _Ads(5), last=SegmentType.weather)
    seen = []
    for _ in range(10):
        item = pl._gap_item(now)
        if item is None:
            break
        seen.append(item.work.get("continuity", {}).get("kind") or "advert")
        if item.type is SegmentType.advert:
            pl.ads_in_row += 1
    assert seen == ["ident", "advert", "programmes", "advert", "advert", "ident", "notice"]


def test_no_ident_straight_after_a_bumper_and_the_count_resets_on_a_programme(cont):
    now = _ts("10:00")
    w = world_mod.seed()
    while continuity.bake_one(w, now):
        pass
    pl = _player(cont, _Ads(1), last=SegmentType.bumper)
    assert pl._gap_item(now).type is SegmentType.advert
    pl._start(Segment(slot_id=0, type=SegmentType.weather, state=SegmentState.ready), now)
    assert pl.gap_n == 0 and pl.ads_in_row == 0


def test_the_programme_card_airs_ahead_of_a_news_bumper_once_an_hour(cont, monkeypatch):
    now = _ts("10:00")
    monkeypatch.setattr(schedule, "now", lambda: now)
    w = world_mod.seed()
    while continuity.bake_one(w, now):
        pass
    pl = _player(cont, _Ads(0), last=SegmentType.bulletin)

    def bumper(slot, show="news"):
        sting = [Line(speaker="voiceover", text="", duration_s=8.0)]      # with no lines it would end at once
        pl.buffer.mark(Segment(slot_id=slot, type=SegmentType.bumper, state=SegmentState.ready, show=show, lines=sting),
                       SegmentState.ready)

    def kind():
        return pl._kind() or pl.current.type.value

    bumper(0)
    pl.update(now)
    assert kind() == "programmes" and pl.next_slot == 0          # outside the rundown: the bumper still to come
    pl.current = None
    pl.update(now + 10)
    assert kind() == "bumper"
    pl._finish(now + 15)
    bumper(1)
    pl.update(now + 1800)
    assert kind() == "bumper"                                    # not again within the hour
    pl._finish(now + 1810)
    bumper(2, show="magazine")
    pl.update(now + 3700)
    assert kind() == "bumper"                                    # the rolling news only
    pl._finish(now + 3710)
    while continuity.bake_one(w, now + 3720):                   # the 10:00 card ran out at eleven: the next one
        pass
    bumper(3)
    pl.update(now + 3720)
    assert kind() == "programmes"


# ------------------------------------------------------------------ promos


def _waiting(fmt: str, airs_from: float = 0.0) -> Segment:
    work = {"format": fmt, "outline": {"title": "The Baker's Petition", "standfirst": "A second engine?",
                                       "intro": "Tonight, a petition.", "sections": [{"heading": "The queue"}]}}
    if airs_from:
        work["airs_from"] = airs_from
    return Segment(slot_id=1_000_007, type=SegmentType.documentary, headline="Petition", work=work,
                   content_hash="abc123")


def test_a_finished_special_gets_a_trail_with_its_time_until_it_airs(cont):
    now = _ts("14:10")
    buf = Buffer()
    seg = _waiting("special", airs_from=_ts("15:00"))
    buf.mark(seg, SegmentState.ready)
    w = world_mod.seed()
    assert continuity.should_make(w, buf, now)
    it = continuity.make(w, buf, now)                             # NEWSROOM_LLM=off: the standfirst
    card = it.segment.work["continuity"]
    assert it.kind == "trail" and it.valid_until == _ts("15:00")
    assert card["title"] == "THIS AFTERNOON AT 15:00" and card["lines"][0] == "The Baker's Petition"
    assert it.segment.lines[0].text == ("This afternoon at three o'clock on Channel 7: a special report, "
                                        "The Baker's Petition.")
    assert continuity.trails_due(buf, now) == []                  # one trail each
    assert cont.pick("card", "news", _ts("14:59")).work["continuity"]["kind"] == "trail"
    assert cont.pick("card", "news", _ts("15:00")) is None


def test_tonights_documentary_is_trailed_for_nine_but_not_something_on_in_five_minutes(cont):
    buf = Buffer()
    buf.mark(_waiting("documentary"), SegmentState.ready)
    w = world_mod.seed()
    assert continuity.trails_due(buf, _ts("20:56")) == []
    it = continuity.make(w, buf, _ts("19:30"))
    assert it.segment.lines[0].text.startswith("Tonight at nine o'clock on Channel 7: Port Wexley Stories")


def test_community_notices_come_from_the_model_a_few_a_day(cont, monkeypatch):
    from newsroom import llm
    from newsroom.models import CommunityNotice

    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return CommunityNotice(thread_id="t001", issuer="Harbour Office",
                               lines=["The slipway is closed on Thursday from nine for the survey."])
    monkeypatch.setattr(llm, "complete_json", write)
    monkeypatch.setattr(continuity, "_tried_notice", 0.0)
    w, buf = world_mod.seed(), Buffer()
    now = _ts("10:00")
    assert continuity.should_make(w, buf, now)
    it = continuity.make(w, buf, now)
    assert it.id == "community_20261027_0" and it.kind == "notice" and it.valid_until == _ts("00:00", date(2026, 10, 28))
    assert it.segment.work["continuity"]["title"] == "HARBOUR OFFICE"
    assert not continuity.should_make(w, buf, now + 60)          # notice_every_s apart
    continuity.make(w, buf, now + 3000)
    assert "[t001] HARBOUR OFFICE" in asked[-1]                  # told what is already up
    assert len(continuity._community(date(2026, 10, 27))) == 2


def _notice(cont, item_id, until=0.0):
    wav = cont.dir / f"{item_id}_00.wav"
    wav.parent.mkdir(parents=True, exist_ok=True)
    wav.write_bytes(b"")
    seg = Segment(slot_id=-1, type=SegmentType.continuity, show="news", state=SegmentState.ready,
                  work={"continuity": {"kind": "notice"}},
                  lines=[Line(speaker="voiceover", text="A notice.", wav_path=wav, duration_s=0.5)])
    cont.add(continuity.Item(id=item_id, kind="notice", valid_until=until, segment=seg))
    return wav


def test_removing_an_item_takes_its_own_files_and_nobody_elses(cont):
    """remove() deleted by prefix: the day's second notice went and took the eleventh to the twentieth
    with it, and an ident "_1" would have taken "_10"."""
    one, ten = _notice(cont, "community_20261109_1"), _notice(cont, "community_20261109_10")
    cont.remove("community_20261109_1")
    assert not one.exists() and not (cont.dir / "community_20261109_1.json").exists()
    assert ten.exists() and (cont.dir / "community_20261109_10.json").exists()
    assert cont.get("community_20261109_10") is not None and cont.get("community_20261109_1") is None


def test_an_item_that_expires_while_it_is_being_read_keeps_its_audio_until_it_is_over(cont, monkeypatch):
    """The worker's _expire deleted the WAVs of a card the player had just picked: the rest of it was silence."""
    until = _ts("20:00")
    wav = _notice(cont, "community_20261027_0", until)
    old = _notice(cont, "community_20261027_1", until)
    clock = [1_000_000.0]
    monkeypatch.setattr(continuity.time, "time", lambda: clock[0])
    cont._aired["community_20261027_1"] = 1.0                        # the other aired long ago
    assert cont.pick("card", "news", _ts("19:59")) is not None       # on air now: the first, never aired
    continuity._expire(cont, _ts("20:00"))
    assert cont.pick("card", "news", _ts("20:00")) is None           # out of the pool at once, and off the disk
    assert not (cont.dir / "community_20261027_0.json").exists()
    assert wav.exists() and not old.exists()                         # but its audio stays while it may be playing
    clock[0] += continuity.RETIRE_S + 1
    continuity._expire(cont, _ts("20:20"))
    assert not wav.exists()


def test_audio_nothing_owns_is_cleared_when_the_pool_opens(cont):
    import os
    import time as real_time

    keep = _notice(cont, "community_20261109_3")
    mix = cont.dir / "ident_news_10.wav"                             # an ident's mix: named for its own item
    for f in (mix, cont.dir / "ident_news_10_vo.wav", cont.dir / "trail_gone_00.wav", cont.dir / "trail_new_00.wav"):
        f.write_bytes(b"")
    (cont.dir / "ident_news_10.json").write_text("{}")
    long_ago = real_time.time() - continuity.RETIRE_S - 60
    for f in cont.dir.glob("*.wav"):
        if f.name != "trail_new_00.wav":
            os.utime(f, (long_ago, long_ago))
    continuity.Pool(cont.dir)
    left = sorted(f.name for f in cont.dir.glob("*.wav"))
    assert left == ["community_20261109_3_00.wav", "ident_news_10.wav", "ident_news_10_vo.wav", "trail_new_00.wav"]
    assert keep.exists()


def test_channel_eights_card_after_its_closedown_names_no_documentary_and_is_baked_once(cont):
    """The first soap scratch run (2026-11-13): after Channel 8's closedown the card listed Channel 7's nine o'clock
    documentary, began before the next show, never counted as current, and was baked every idle tick until nine."""
    import entertainment

    undo = entertainment.use()
    continuity._pool = cont                                     # use() opens Channel 8's folder: keep the test's
    try:
        now = _ts("20:45")
        it = continuity.bake_programmes(now, world_mod.seed())
        assert not any("STORIES" in l or "WEEK" in l for l in it.segment.work["continuity"]["lines"])
        assert it.valid_until == continuity.upcoming(now)[0][0] == _ts("19:00", date(2026, 10, 28))
        while continuity.bake_one(world_mod.seed(), now):
            pass
        assert sum(i.kind == "programmes" for i in cont.items()) == 1          # once, not every tick
    finally:
        undo()
