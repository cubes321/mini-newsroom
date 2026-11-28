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
    Saltby crossing" for Callum Tate, "Interview: Local Resident" for Cora Jessop. The Panel's stays its question."""
    from newsroom.models import InterviewScript, PanelScript

    say = [{"speaker": "late_host", "text": "Welcome on."}, {"speaker": "guest", "text": "Evening."}]
    cap = lambda lt, name, role=None: InterviewScript.model_validate(          # noqa: E731
        {"lines": say, "headline": "A ferry hand at midnight", "lower_third": lt, "guest_name": name,
         "guest_role": role}).lower_third
    assert cap("Night ferry hand, Saltby crossing", "Callum Tate", "ferry hand, Saltby foot ferry") == \
        "Callum Tate, ferry hand, Saltby foot ferry"
    assert cap("Interview: Local Resident", "Cora Jessop") == "Cora Jessop"
    assert cap("Callum Tate, Saltby Foot Ferry", "Callum Tate", "ferry hand") == "Callum Tate, Saltby Foot Ferry"
    assert cap("Night nurse", "Ruth Carver", "night nurse and volunteer steward on the ward at Harbour Hill") == \
        "Ruth Carver"                                                          # name and role past 60: the name
    panel = PanelScript.model_validate(
        {"lines": [{"speaker": "anchor", "text": "Q1."}] + [{"speaker": "guest", "guest_name": n, "text": "Yes."}
                                                            for n in ("Ann Lee", "Bo Ray", "Cy Fox")],
         "headline": "Second engine", "lower_third": "Q1: Second fire engine"})
    assert panel.lower_third == "Q1: Second fire engine"
