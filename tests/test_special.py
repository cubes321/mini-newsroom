"""Special reports: cache keys, aired markers, retries and where a ready special airs.

No model or TTS calls: the outline and section writers are stubbed and the
cache lives in a temporary directory.
"""
from __future__ import annotations

import dataclasses
import time

import pytest

from newsroom import special, workers
from newsroom import world as world_mod
from newsroom.buffer import Buffer
from newsroom.config import CONFIG
from newsroom.models import (
    EditorDecision,
    Line,
    ScriptLine,
    SectionPlan,
    Segment,
    SegmentState,
    SegmentType,
    SpecialOutline,
    SpecialSection,
)
from newsroom.player import Player


@pytest.fixture(autouse=True)
def tmp_paths(tmp_path, monkeypatch):
    """Cache and world file in tmp_path (CONFIG is frozen, hence object.__setattr__)."""
    old = CONFIG.paths
    object.__setattr__(CONFIG, "paths", dataclasses.replace(old, cache=tmp_path, world=tmp_path / "world.json"))
    monkeypatch.setattr(world_mod, "save", lambda *a, **k: None)
    yield tmp_path
    object.__setattr__(CONFIG, "paths", old)


@pytest.fixture
def world():
    return world_mod.seed()


def _outline(title="The Baker's Petition") -> SpecialOutline:
    return SpecialOutline(
        title=title, standfirst="A second engine?", intro="Tonight, a petition.", outro="That was the petition.",
        sections=[SectionPlan(heading=f"Part {i}", beats=["a beat"], backdrop="market") for i in range(3)],
    )


def _commission(world, title="The Baker's Petition: A Second Engine for Port Wexley?") -> Segment:
    return special.commission(world, EditorDecision(commission=True, thread_id=None, working_title=title, angle="why"))


def _cache_finished(h: str, title: str, *, aired: bool) -> None:
    """A finished special in the cache under `h`, as a previous run would have left it."""
    wav = CONFIG.paths.cache / f"{h}_00.wav"
    wav.write_bytes(b"")
    seg = Segment(slot_id=special.SPECIAL_SLOT_BASE + 2, type=SegmentType.documentary, state=SegmentState.ready,
                  headline=title, content_hash=h, stage="finish",
                  lines=[Line(speaker="anchor", text="Same ink.", wav_path=wav, duration_s=300.0)])
    workers._save_cached(seg, h)
    if aired:
        special._aired_path(h).touch()


# ------------------------------------------------------------- cache keys


def test_new_commission_does_not_take_an_old_special_on_the_same_slot(world, monkeypatch):
    """The overnight bug: the Baker's commission got slot 1000002, which an earlier run's special
    had used, and generate() stamped the slot-keyed hash on it, so it replayed that special."""
    seg = _commission(world)
    slot_key = workers.content_hash(seg, world)
    _cache_finished(slot_key, "Same Ink, Same Harbour", aired=False)    # aired or not, it's another piece
    expected = special._hash(seg, world)
    monkeypatch.setattr(special, "write_outline", lambda s, w: _outline())

    buffer = Buffer()
    out = workers.generate(seg, world, buffer)

    assert buffer.pop_special() is None
    assert out.content_hash == expected != slot_key
    assert out.headline == "The Baker's Petition"
    assert out.stage == "sections"


def test_load_cached_skips_a_special_that_has_aired(world):
    seg = _commission(world)
    _cache_finished("abc123", "Same Ink", aired=False)
    assert workers._load_cached(seg, "abc123") is not None
    special._aired_path("abc123").touch()
    assert workers._load_cached(seg, "abc123") is None


def test_recommissioned_title_after_airing_is_made_again(world, monkeypatch):
    """Same title, thread and day as a special that already aired: write a new one, and drop the
    stale marker so a restart can still resume the new piece."""
    seg = _commission(world)
    h = special._hash(seg, world)
    _cache_finished(h, seg.headline, aired=True)
    monkeypatch.setattr(special, "write_outline", lambda s, w: _outline())

    buffer = Buffer()
    out = special.advance(seg, world, buffer)

    assert buffer.pop_special() is None
    assert out.stage == "sections"
    assert not special._aired_path(h).exists()


def test_retried_outline_still_skips_the_aired_special(world, monkeypatch):
    """The outline times out and is retried: the old piece's marker must still be there."""
    seg = _commission(world)
    h = special._hash(seg, world)
    _cache_finished(h, seg.headline, aired=True)
    calls = {"n": 0}

    def flaky(s, w):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("timed out")
        return _outline()

    monkeypatch.setattr(special, "write_outline", flaky)
    buffer = Buffer()
    with pytest.raises(TimeoutError):
        special.advance(seg, world, buffer)
    out = special.advance(seg, world, buffer)          # the retry

    assert buffer.pop_special() is None
    assert out.stage == "sections"


def test_unaired_special_in_its_own_cache_is_reused(world, monkeypatch):
    seg = _commission(world)
    h = special._hash(seg, world)
    _cache_finished(h, seg.headline, aired=False)
    monkeypatch.setattr(special, "write_outline", lambda s, w: pytest.fail("should have used the cache"))

    buffer = Buffer()
    special.advance(seg, world, buffer)

    assert buffer.pop_special().headline == seg.headline


# ---------------------------------------------------------------- retries


def test_failed_special_is_retried_once_then_dropped(world):
    buffer = Buffer()
    pool = workers.WorkerPool(buffer, world)
    seg = _commission(world, "The Quay Remembers")
    buffer.submit_special(seg)
    assert buffer.next_job(timeout=0) is seg

    pool._failed(seg, TimeoutError("moonshot_k3 unreachable"))
    assert buffer.next_job(timeout=0) is seg          # back on the queue
    assert buffer.special_pending()

    pool._failed(seg, TimeoutError("moonshot_k3 unreachable"))
    assert buffer.next_job(timeout=0) is None
    assert buffer.state_of(seg.slot_id) is SegmentState.failed
    assert not buffer.special_pending()


def test_retried_section_is_not_counted_twice(world, monkeypatch):
    seg = _commission(world)
    monkeypatch.setattr(special, "write_outline", lambda s, w: _outline())
    special.advance(seg, world)                       # outline

    calls = {"n": 0}

    def flaky(s, w, outline, i, words):
        calls["n"] += 1
        if calls["n"] == 1:
            raise TimeoutError("timed out")
        return SpecialSection(lines=[ScriptLine(speaker="reporter", text="On the quay.")])

    monkeypatch.setattr(special, "write_section", flaky)
    with pytest.raises(TimeoutError):
        special.advance(seg, world)
    special.advance(seg, world)                       # the retry
    assert seg.work["starts"] == [1]
    assert seg.work["next_section"] == 1


# ------------------------------------------------------------ where it airs


def _at(hour: int) -> float:
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, hour, 5, 0, 0, 0, -1))


def _player_with_ready_special(last_type: SegmentType) -> tuple[Player, Segment]:
    buffer = Buffer()
    seg = Segment(slot_id=special.SPECIAL_SLOT_BASE + 5, type=SegmentType.documentary, headline="Ghosts",
                  lines=[Line(speaker="anchor", text="Ghosts.", duration_s=300.0)])
    buffer.mark(seg, SegmentState.ready)
    player = Player(buffer, world_mod.seed(), producer=None, audio=False)
    player.last_type = last_type
    return player, seg


@pytest.mark.parametrize("hour, last_type, airs", [
    (1, SegmentType.testcard, True),       # overnight: after the test card (was: never, until 09:00)
    (1, SegmentType.weather, False),       # overnight, but after a repeat: wait for the card
    (10, SegmentType.bumper, True),        # the news: after a bumper, as before
    (7, SegmentType.bumper, False),        # breakfast doesn't air specials
])
def test_where_a_ready_special_airs(hour, last_type, airs):
    player, seg = _player_with_ready_special(last_type)
    player.update(_at(hour))
    assert (player.current is seg) is airs
