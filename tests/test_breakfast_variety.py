"""Breakfast variety: the sofa writer sees this morning's chats, and overnight repeats skip breakfast.

Run with the project's Python: python -m unittest discover -s tests
"""
from __future__ import annotations

import random
import unittest

from newsroom import schedule, workers, writers, world as world_mod
from newsroom.models import Segment, SegmentType as T

PAPERS = "the morning papers: two or three local stories the hosts have opinions about"
ON_THIS_DAY = "on this day in the town's history"


def _world() -> world_mod.World:
    w = world_mod.seed()                  # never load(): that's the real, process-cached world
    w.record_aired("sofa", "Port Wexley turns one hundred and fifty-five", None,
                   "Right, Jonah, grab your tea. On this day in eighteen seventy-one, Port Wexley was founded.",
                   show="breakfast", brief=ON_THIS_DAY)
    w.record_aired("sofa", "Marjorie Pell marks eighty-two at market", None,
                   "It's Marjorie Pell, turning eighty-two today.", show="breakfast",
                   brief="a birthday, an anniversary or a long-serving local worth a mention")
    w.record_aired("bulletin", "Harbour wall money confirmed", None, "The council confirmed...", show="breakfast")
    w.record_aired("sofa", "Old chat from yesterday", None, "Yesterday's sofa.", show="breakfast", brief=ON_THIS_DAY)
    w.archive[-1]["date"] = "2000-01-01"
    return w


def _sofa_prompt(w: world_mod.World, brief: str, part: str = "") -> str:
    _, user = writers.build_prompt(T.sofa, w, target_s=75.0, show=schedule.get("breakfast"), brief=brief, part=part)
    return user


class SofaContext(unittest.TestCase):
    def test_lists_this_mornings_sofa_chats_and_the_rule(self) -> None:
        user = _sofa_prompt(_world(), PAPERS)
        self.assertIn("ON THE SOFA ALREADY THIS MORNING", user)
        self.assertIn("Port Wexley turns one hundred and fifty-five", user)
        self.assertIn("Marjorie Pell marks eighty-two at market", user)
        self.assertIn("never contradicted", user)
        self.assertNotIn("Old chat from yesterday", user)          # another day
        self.assertNotIn("Harbour wall money confirmed", user.split("ON THE SOFA")[1])   # not a sofa chat
        self.assertNotIn("EARLIER CHATS ON THIS ITEM'S ANGLE", user)   # no papers chat yet

    def test_same_angle_shows_how_the_earlier_chat_began(self) -> None:
        user = _sofa_prompt(_world(), ON_THIS_DAY)
        same = user.split("EARLIER CHATS ON THIS ITEM'S ANGLE")[1]
        self.assertIn("On this day in eighteen seventy-one, Port Wexley was founded.", same)
        self.assertNotIn("Marjorie Pell", same)                    # a different angle
        self.assertNotIn("Yesterday's sofa", same)

    def test_memory_is_capped(self) -> None:
        w = world_mod.seed()
        for i in range(40):
            w.record_aired("sofa", f"Chat number {i}", None, "...", show="breakfast", brief=PAPERS)
        user = _sofa_prompt(w, PAPERS)
        self.assertNotIn("Chat number 15\n", user)
        self.assertIn(f"Chat number {40 - writers.SOFA_MEMORY}\n", user)
        self.assertEqual(user.split("EARLIER CHATS")[1].count("  - "), writers.SOFA_SAME_ANGLE)

    def test_goodbye_gets_the_list_for_its_nod(self) -> None:
        user = _sofa_prompt(_world(), "", part="close")
        self.assertIn("ON THE SOFA THIS MORNING (for the nod to what was on)", user)
        self.assertIn("Marjorie Pell marks eighty-two at market", user)
        self.assertNotIn("do NOT retell", user)

    def test_first_chat_and_other_types_have_no_block(self) -> None:
        self.assertNotIn("ON THE SOFA", _sofa_prompt(world_mod.seed(), PAPERS))
        _, news = writers.build_prompt(T.bulletin, _world(), target_s=75.0, show=schedule.get("news"))
        self.assertNotIn("ON THE SOFA", news)

    def test_scripting_records_show_and_brief(self) -> None:
        w = world_mod.seed()
        seg = Segment(slot_id=3, type=T.sofa, show="breakfast", brief=PAPERS)
        script = writers._template(T.sofa, w, random.Random(1), schedule.get("breakfast"))
        writers._apply_to_world(seg, script, w)
        self.assertEqual(w.aired_today("sofa", "breakfast")[-1]["brief"], PAPERS)


class OvernightRepeats(unittest.TestCase):
    def test_breakfast_never_repeats_overnight(self) -> None:
        for t in (T.sofa, T.bulletin, T.weather, T.field_report):
            self.assertFalse(workers.repeatable(Segment(slot_id=0, type=t, show="breakfast")), t)

    def test_other_shows_still_repeat(self) -> None:
        self.assertTrue(workers.repeatable(Segment(slot_id=0, type=T.bulletin, show="news")))
        self.assertTrue(workers.repeatable(Segment(slot_id=0, type=T.interview, show="late")))
        self.assertTrue(workers.repeatable(Segment(slot_id=0, type=T.feature, show="magazine")))
        self.assertTrue(workers.repeatable(Segment(slot_id=0, type=T.weather, show="")))   # old cache: news

    def test_unrepeatable_types_stay_out(self) -> None:
        self.assertFalse(workers.repeatable(Segment(slot_id=0, type=T.bumper, show="news")))


if __name__ == "__main__":
    unittest.main()
