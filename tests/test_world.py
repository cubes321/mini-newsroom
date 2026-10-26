"""The story bible must not lose open threads, and test runs must not touch the real town.

    python -m unittest tests.test_world

Runs against a temp world and cache with NEWSROOM_LLM=off: no model, no TTS.
"""
import os
import shutil
import tempfile
import unittest
from pathlib import Path

# Before any newsroom import: CONFIG is built from these when newsroom.config is first imported.
_TMP = Path(tempfile.mkdtemp(prefix="newsroom-test-"))
os.environ["NEWSROOM_WORLD"] = str(_TMP / "world.json")
os.environ["NEWSROOM_CACHE"] = str(_TMP / "cache")
os.environ["NEWSROOM_TIPLINE"] = str(_TMP / "tipline.txt")
os.environ["NEWSROOM_LLM"] = "off"

from newsroom import world as world_mod, writers  # noqa: E402
from newsroom.config import CONFIG  # noqa: E402
from newsroom.models import Segment, SegmentType  # noqa: E402


def tearDownModule():
    shutil.rmtree(_TMP, ignore_errors=True)


def _world(n_closed: int, n_open: int) -> world_mod.World:
    """Open threads first in the list (the oldest, which a plain [-40:] evicts), and updated
    dates that don't follow list order, so "quietest" and "first in the list" differ."""
    w = world_mod.seed()
    for i in range(n_open + n_closed):
        t = w.seed_thread(f"story {i}", "known so far", "", [])
        t.updated = f"2026-10-{1 + i % 25:02d}"
        if i >= n_open:
            t.phase = "closed"
    return w


class PathOverrideTest(unittest.TestCase):
    def test_paths_point_at_the_temp_dir(self):
        self.assertEqual(CONFIG.paths.world, _TMP / "world.json")
        self.assertEqual(CONFIG.paths.cache, _TMP / "cache")
        self.assertEqual(CONFIG.paths.tipline, _TMP / "tipline.txt")


class ThreadCapTest(unittest.TestCase):
    def test_new_thread_drops_the_quietest_closed_one(self):
        w = _world(n_closed=world_mod.MAX_THREADS - 1, n_open=1)
        oldest = min((t for t in w.threads if t.phase == "closed"), key=lambda t: t.updated)
        w.update_thread(None, "A new story", "breaking")
        self.assertEqual(len(w.threads), world_mod.MAX_THREADS)
        self.assertIsNone(w.thread(oldest.id))
        self.assertEqual(len(w.open_threads()), 2)

    def test_open_threads_are_never_dropped(self):
        w = _world(n_closed=1, n_open=world_mod.MAX_THREADS - 1)
        open_ids = {t.id for t in w.open_threads()}
        with self.assertLogs("newsroom.world", level="WARNING"):
            w.update_thread(None, "One more", None)
            w.update_thread(None, "And another", None)
        self.assertEqual(len(w.threads), world_mod.MAX_THREADS + 1)
        self.assertTrue(open_ids <= {t.id for t in w.threads})
        self.assertFalse([t for t in w.threads if t.phase == "closed"])

    def test_seed_thread_uses_the_same_cap(self):
        w = _world(n_closed=0, n_open=world_mod.MAX_THREADS)
        with self.assertLogs("newsroom.world", level="WARNING"):
            w.seed_thread("Seeded by the desk", "", "", [])
        self.assertEqual(len(w.threads), world_mod.MAX_THREADS + 1)


class TemplateThreadTest(unittest.TestCase):
    def test_templates_do_not_open_threads(self):
        w = world_mod.seed()
        before = len(w.threads)
        for slot, kind in enumerate([SegmentType.field_report, SegmentType.bulletin] * 3):
            seg = writers.script_segment(Segment(slot_id=slot, type=kind), w)
            self.assertIsNone(seg.thread_id)
        self.assertEqual(len(w.threads), before)

    def test_templates_follow_up_their_own_thread(self):
        w = world_mod.seed()
        tid = w.update_thread(None, "Volunteers clear the old cannery slipway", None)
        seg = writers.script_segment(Segment(slot_id=0, type=SegmentType.field_report), w)
        self.assertEqual(seg.thread_id, tid)
        self.assertEqual(len(w.threads), 1)
        self.assertEqual(w.thread(tid).mentions, 2)


if __name__ == "__main__":
    unittest.main()
