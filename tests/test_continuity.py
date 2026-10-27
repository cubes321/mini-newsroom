"""Continuity: idents, the programme card and notices fill a gap in turn with the adverts.

Kokoro is stubbed: every line is a short quiet WAV.
"""
from datetime import date, datetime

import numpy as np
import pytest
import soundfile as sf

from newsroom import adverts, assets, continuity, schedule, tts, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Segment, SegmentState, SegmentType
from newsroom.player import Player
from newsroom.producer import Producer
from newsroom.tts import SynthResult


@pytest.fixture
def cont(tmp_path, monkeypatch):
    def synth(text, voice, out, speed=1.0):
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
    assert {"programmes_20261027_20", "tides_20261027"} <= set(kinds)
    assert sum(k.startswith("notice_") for k in kinds) == len(continuity.NOTICES)
    assert not continuity.bake_one(world_mod.seed(), now)          # nothing left to do


def test_the_programme_card_lists_whats_next_and_expires_when_it_starts(cont):
    now = _ts("19:20")
    it = continuity.bake_programmes(now, world_mod.seed())
    card = it.segment.work["continuity"]
    assert card["lines"] == ["20:00  PORT WEXLEY NEWS", "21:00  PORT WEXLEY STORIES",     # tonight's documentary
                             "22:00  THE LAST FERRY", "23:00  PORT WEXLEY NEWS"]
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
