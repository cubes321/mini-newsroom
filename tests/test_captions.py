"""An on-screen caption can't be empty or a placeholder: a reply with a blank or "x" headline,
location or strap fails validation, so it gets the validation retry instead of airing as a bare
"Live from" (and opening a thread called "x").

The reply below is Haiku's from 2026-10-26 22:06 with the speech cut short; at 22:29 it sent "x"
for all three.
"""
import pytest
from pydantic import ValidationError

from newsroom.models import FieldReportScript

REPLY = {
    "lines": [{"speaker": "anchor", "text": "Miles, over to you."},
              {"speaker": "reporter", "text": "Thanks, Dana. I'm at the harbour front."}],
    "headline": "School boat doubles its run", "location": "the harbour front",
    "backdrop": "harbour", "lower_third": "Miles Okafor, reporting from the harbour",
}


def test_a_filled_in_field_report_validates():
    assert FieldReportScript.model_validate(REPLY).location == "the harbour front"


def test_an_overlong_caption_is_cut_at_a_word_not_failed():
    """On the 2026-10-31 night seven reports and vox pops failed on a location past 60 characters, and
    the editor's call went to Sonnet over a 400-character reason. Captions and notes are cut instead."""
    from newsroom.models import EditorDecision

    place = "the harbour front, by the lifeboat station where the crews are tied up for the night"
    s = FieldReportScript.model_validate({**REPLY, "location": place, "headline": "Harbour crews " * 8})
    assert len(s.location) <= 60 and s.location.endswith("…") and place.startswith(s.location[:-1])
    assert len(s.headline) <= 90 and s.headline.endswith("Harbour crews…")
    assert len(EditorDecision(commission=False, reason="Not yet. " * 60).reason) == 400


@pytest.mark.parametrize("field", ["headline", "location", "lower_third"])
def test_a_blank_caption_fails_validation(field):
    for placeholder in ("", "x", "TBD"):
        with pytest.raises(ValidationError):
            FieldReportScript.model_validate({**REPLY, field: placeholder})



def test_an_interview_caption_names_the_guest():
    """On the 2026-11-27 night one interview in five was captioned without the guest's name: "Night ferry hand,
    Saltby crossing" for Callum Tate, "Interview: Local Resident" for Cora Jessop."""
    from types import SimpleNamespace

    from newsroom import writers

    def cap(lt, name, role=None):
        s = SimpleNamespace(lower_third=lt, guest_name=name, guest_role=role)
        writers.caption_names_guest(s)
        return s.lower_third

    assert cap("Night ferry hand, Saltby crossing", "Callum Tate", "ferry hand, Saltby foot ferry") ==         "Callum Tate, ferry hand, Saltby foot ferry"
    assert cap("Interview: Local Resident", "Cora Jessop") == "Cora Jessop"
    assert cap("Callum Tate, Saltby Foot Ferry", "Callum Tate", "ferry hand") == "Callum Tate, Saltby Foot Ferry"
    assert cap("Night nurse", "Ruth Carver", "night nurse and volunteer steward on the ward at Harbour Hill") ==         "Ruth Carver"                                                          # name and role past 60: the name
    assert cap("Consumer: boiler cover", None) == "Consumer: boiler cover"     # nobody to name


def test_only_interviews_written_with_the_guest_rules_have_their_caption_changed():
    """The Panel's and The Chamber's captions are the programme's, and so are the hand-built shows' (The Kettle,
    Tideline, the Mayor's message): the rule is in script_segment, for prompts with the guest rules only."""
    from newsroom import schedule, writers, world as world_mod
    from newsroom.models import SegmentType

    def system(show):
        return writers.build_prompt(SegmentType.interview, world_mod.seed(), target_s=60, show=schedule.get(show))[0]

    assert writers._GUEST_RULES in system("late") and writers._GUEST_RULES in system("magazine")
    assert writers._GUEST_RULES not in system("panel")
