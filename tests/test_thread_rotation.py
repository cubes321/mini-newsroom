"""The briefing's open threads rotate: of the stories updated today, the one followed up least
often today is listed first, so the bulletins don't lead with the same thread all evening
(the cannery ghost tour led six of nine on 2026-10-26, always first of the day's ties).

Template scripts only (NEWSROOM_LLM=off, set in conftest): no model, no TTS.
"""
from newsroom import world as world_mod


def _listed(w):
    block = w.summary_for_prompt().split("Open story threads")[1].split("Recent headlines")[0]
    return [line.split("]")[0].split("[")[1] for line in block.splitlines() if line.strip().startswith("- [")]


def test_a_follow_up_moves_a_story_down_the_list():
    w = world_mod.seed()
    a = w.update_thread(None, "Harbour wall cracks", "developing")
    b = w.update_thread(None, "Bakery petition", "developing")
    assert _listed(w)[:2] == [a, b]          # a tie: storage order
    w.update_thread(a, "Harbour wall: engineers called", "engineers due Tuesday")
    assert _listed(w).index(b) < _listed(w).index(a)
