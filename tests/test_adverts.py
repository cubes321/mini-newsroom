"""Local adverts: the seed set, the pool, the model-written ones, and the player airing them in gaps.

Kokoro and the model are stubbed: no audio is synthesised, no network.
"""
import pygame
import pytest

from newsroom import adverts, llm, scenes, world as world_mod
from newsroom.buffer import Buffer
from newsroom.config import CONFIG
from newsroom.models import AdvertScript, Line, Segment, SegmentState, SegmentType
from newsroom.player import Player
from newsroom.producer import Producer
from newsroom.tts import SynthResult


@pytest.fixture
def pool(tmp_path, monkeypatch):
    def synth(text, voice, out, speed=1.0):
        out.write_bytes(b"RIFF")                      # only has to exist
        return SynthResult(wav_path=out, duration_s=len(text.split()) / 2.5, mouth_env=[0.5])
    monkeypatch.setattr(adverts.tts, "synthesize", synth)
    p = adverts.AdPool(tmp_path / "ads")
    monkeypatch.setattr(adverts, "_pool", p)
    return p


@pytest.fixture
def world():
    return world_mod.seed()


def test_seeds_are_15_to_30_seconds_and_name_their_owners():
    for ad_id, s in adverts.SEEDS.items():
        words = sum(len(l.text.split()) for l in s.lines)
        assert 35 <= words <= 75, (ad_id, words)                 # about 15-30 s at 150 words a minute
        assert s.owner_name or all(l.speaker == "voiceover" for l in s.lines)


def test_seeding_voices_one_at_a_time_and_owners_join_the_cast(pool, world):
    assert adverts.seed_one(world) and len(pool) == 1
    while adverts.seed_one(world):
        pass
    assert len(pool) == len(adverts.SEEDS)
    assert world.person_by_name("Jasper Fowle").role == "owner, Fowle & Sons Hardware"   # new to this town
    assert world.person_by_name("Dev Ramachandran").role == "Baker, Harrow Street market"  # a role he had stays
    ghosts = next(a for a in pool._ads.values() if a.id == "seed_ghosts")
    assert ghosts.segment.lines[1].speaker == "guest" and ghosts.segment.lines[1].guest_name == "Gordon Pell"
    assert not any(p.name == "Gordon Pell" for p in world.people)    # a presenter isn't added as a resident
    reloaded = adverts.AdPool(pool.dir)
    assert len(reloaded) == len(adverts.SEEDS)


def test_voiceover_never_shares_the_owners_voice(pool, world):
    for ad_id, s in adverts.SEEDS.items():
        ad = adverts.build(ad_id, s, world, seed=True)
        if s.owner_name:
            assert ad.voice != world.voice_for("guest", s.owner_name), ad_id


def test_pick_rotates_and_never_repeats_a_business_twice_running(pool, world):
    while adverts.seed_one(world):
        pass
    picks = [pool.pick().work["advert"]["business"] for _ in range(len(adverts.SEEDS))]
    assert len(set(picks)) == len(adverts.SEEDS)                 # each once before any comes round again
    more = [pool.pick().work["advert"]["business"] for _ in range(30)]
    assert all(a != b for a, b in zip(more, more[1:]))
    seg = pool.pick()
    assert seg.type is SegmentType.advert and seg.slot_id == -1 and seg.state is SegmentState.ready


@pytest.fixture
def small_pool_size():
    old = CONFIG.adverts                              # CONFIG is frozen; swap the field and put it back
    object.__setattr__(CONFIG, "adverts", type(old)(pool_size=len(adverts.SEEDS) + 2))
    yield
    object.__setattr__(CONFIG, "adverts", old)


def test_the_pool_drops_the_oldest_model_ads_and_keeps_the_seeds(pool, world, small_pool_size):
    while adverts.seed_one(world):
        pass
    for i in range(4):
        s = AdvertScript(business=f"Shop {i}", tagline="t", where="w", backdrop="harbour",
                         lines=[{"speaker": "voiceover", "text": "Buy it."}, {"speaker": "voiceover", "text": "Now."}])
        ad = adverts.build(f"ad_{i}", s, world)
        ad.made = f"2026-10-2{i}"
        pool.add(ad)
    assert len(pool) == len(adverts.SEEDS) + 2
    assert "ad_0" not in pool and "ad_1" not in pool and "ad_3" in pool and "seed_bakery" in pool
    assert not list(pool.dir.glob("ad_0*"))


def test_the_model_writes_a_new_one_and_never_a_duplicate(pool, world, monkeypatch):
    script = AdvertScript(business="Saltby Kayaks", tagline="Paddle the Grey", where="Saltby slipway",
                          backdrop="estuary", owner_name="Rhona Day", owner_role="kayak instructor", owner_gender="f",
                          lines=[{"speaker": "owner", "text": "Ever seen the estuary from the water?"},
                                 {"speaker": "voiceover", "text": "Saltby Kayaks. Paddle the Grey."}])
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: script)
    ad = adverts.make(world)
    assert ad and "Saltby Kayaks" in pool.businesses()
    assert world.person_by_name("Rhona Day").voice.startswith(("af_", "bf_"))
    assert adverts.make(world) is None                          # already on air

    long = AdvertScript(business="Saltby Windsurf", tagline="t", where="w", backdrop="estuary",
                        lines=[{"speaker": "voiceover", "text": "Waves crash. " * 12}] * 4)
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: long)
    assert adverts.make(world) is None and "Saltby Windsurf" not in pool.businesses()   # over 32 s
    assert not [f for f in pool.dir.glob("ad_*.wav") if "Windsurf" in f.name]

    def down(*a, **k):
        raise llm.LLMUnavailable("off")
    monkeypatch.setattr(llm, "complete_json", down)
    assert adverts.make(world) is None


def _player(pool, world):
    buf = Buffer()
    return Player(buf, world, Producer(buf, 600), audio=False, ads=pool), buf


def _run_out(pl, now):
    """Let the segment on air finish (line ends are simulated from durations); whatever follows
    starts in the same update."""
    seg = pl.current
    while seg is not None and pl.current is seg:
        now += max(l.duration_s or 0 for l in pl.current.lines) + 0.01
        pl.update(now)
    return now


def test_a_gap_gets_adverts_then_the_filler_card(pool, world):
    while adverts.seed_one(world):
        pass
    pl, buf = _player(pool, world)
    now = 1_000_000.0
    for i in range(CONFIG.adverts.max_in_a_row):
        pl.update(now)
        assert pl.current is not None and pl.current.type is SegmentType.advert, i
        assert pl.view(now).mode == "advert"
        now = _run_out(pl, now)
    pl.update(now)
    assert pl.current is None and pl.filler_since is not None     # three in a row: the card
    assert pl.next_slot == 0 and pl.ads_played == CONFIG.adverts.max_in_a_row


def test_a_ready_slot_follows_the_advert_and_resets_the_count(pool, world):
    while adverts.seed_one(world):
        pass
    pl, buf = _player(pool, world)
    now = 1_000_000.0
    pl.update(now)
    assert pl.current.type is SegmentType.advert
    seg = Segment(slot_id=0, type=SegmentType.bulletin, state=SegmentState.ready, headline="News",
                  lines=[Line(speaker="anchor", text="Good evening.", duration_s=2.0)])
    buf.submit(seg)
    buf.mark(seg, SegmentState.ready)
    now = _run_out(pl, now)
    pl.update(now)
    assert pl.current is seg and pl.ads_in_row == 0


def test_no_frame_of_test_card_between_two_ready_segments(pool, world):
    pl, buf = _player(pool, world)
    segs = [Segment(slot_id=i, type=SegmentType.bulletin, state=SegmentState.ready, headline=f"News {i}",
                    lines=[Line(speaker="anchor", text="Good evening.", duration_s=2.0)]) for i in range(2)]
    for seg in segs:
        buf.submit(seg)
        buf.mark(seg, SegmentState.ready)
    now = 1_000_000.0
    pl.update(now)
    assert pl.current is segs[0]
    now = _run_out(pl, now)
    assert pl.current is segs[1] and pl.view(now).mode == "studio"


def test_the_advert_scene_draws_with_and_without_an_owner(pool, world):
    from newsroom.player import View
    pygame.font.init()
    c = pygame.Surface(scenes.CANVAS)
    for card in ({"business": "Harrow Street Market", "tagline": "Fresh", "where": "Saturdays"},
                 {"business": "Pell's Ghost Tours", "tagline": "Boo", "where": "Nightly", "owner": "Gordon Pell",
                  "owner_id": "weather"},
                 {"business": "Okonkwo's Taxis", "tagline": "Home", "where": "Ring 441", "owner": "Kenji Okonkwo",
                  "owner_id": "guest"}):
        scenes.render(c, View(mode="advert", advert=card, backdrop="harbour", speaker="guest", mouth=0.5), 0.5)
