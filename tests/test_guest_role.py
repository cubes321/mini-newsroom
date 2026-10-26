"""A guest's caption is what today's script calls them, so the role travels on each guest line.

Template scripts only (NEWSROOM_LLM=off, set in conftest): no model, no TTS.
"""
from newsroom import world as world_mod, writers
from newsroom.models import Line, Segment, SegmentType as T


def test_guest_lines_carry_the_scripts_role():
    w = world_mod.seed()
    seg = writers.script_segment(Segment(slot_id=1, type=T.feature, show="magazine"), w)
    guest = [l for l in seg.lines if l.speaker == "guest"]
    assert guest and all(l.guest_role == "trainee lifeboat crew" for l in guest)
    assert all(l.guest_role is None for l in seg.lines if l.speaker != "guest")


def test_vox_pop_passers_by_have_no_role():
    seg = writers.script_segment(Segment(slot_id=2, type=T.vox_pop, show="magazine"), world_mod.seed())
    assert all(l.guest_role is None for l in seg.lines)


def test_cached_lines_without_a_role_still_load():
    assert Line.model_validate({"speaker": "guest", "text": "Hello.", "guest_name": "Len"}).guest_role is None
