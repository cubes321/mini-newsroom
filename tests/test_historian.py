"""Hugh Tremayne presents the history documentaries (Miles keeps the ones on a running story):
his own voice, a little slower, with British pronunciation. He is a character of the town, so
the entertainment channel planned in the same world can use him too.
"""
from newsroom import documentary, world as world_mod
from newsroom.models import Segment, SegmentType


def _doc(subject: str) -> Segment:
    return Segment(slot_id=1, type=SegmentType.documentary, work={"format": "documentary", "subject": subject})


def test_hugh_is_on_the_staff_with_his_own_voice_speed_and_pronunciation():
    w = world_mod.seed()
    hugh = w.character("historian")
    assert hugh.name == "Hugh Tremayne" and hugh.voice == "am_santa"
    assert w.speed_for("historian") == 0.92 and w.lang_for("historian") == "b"
    assert w.speed_for("anchor") == 1.0 and w.lang_for("anchor") is None
    assert "am_santa" not in world_mod.GUEST_VOICES + world_mod.OLD_VOICES_M


def test_history_pieces_are_his_and_thread_pieces_stay_with_miles():
    assert documentary.presenter(_doc("history")) == "historian"
    assert documentary.presenter(_doc("thread")) == "reporter"
    system = documentary.SECTION_SYSTEM.format(strand="PORT WEXLEY STORIES", **documentary.prompt_vars(_doc("history")))
    assert '"historian"' in system and "Hugh Tremayne" in system and '"reporter"' not in system


def test_a_saved_world_gains_him_and_loses_nobody():
    w = world_mod.seed()
    d = world_mod._to_dict(w)
    d["characters"] = [c for c in d["characters"] if c["id"] != "historian"]
    for c in d["characters"]:
        c.pop("speed", None), c.pop("lang", None)              # saved before presenters had them
    w2 = world_mod._from_dict(d)
    assert w2.character("historian").speed == 0.92 and w2.character("anchor").speed == 1.0
