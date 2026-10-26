"""An on-screen caption can't be empty: a reply with a blank headline, location or strap fails
validation, so it gets the validation retry instead of airing as a bare "Live from".

The reply below is Haiku's from 2026-10-26 22:06 with the speech cut short.
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


@pytest.mark.parametrize("field", ["headline", "location", "lower_third"])
def test_a_blank_caption_fails_validation(field):
    with pytest.raises(ValidationError):
        FieldReportScript.model_validate({**REPLY, field: ""})
