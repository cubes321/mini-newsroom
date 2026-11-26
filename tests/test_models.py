

def test_a_guests_line_loses_their_own_name_in_front():
    """High Water's spring tide, 2026-11-20: "Ruth Hollis: 1066." would have been read out, name and all."""
    from newsroom.models import PanelScript

    s = PanelScript(headline="The spring tide", lower_third="High Water", guest_name="Ruth Hollis", lines=[
        {"speaker": "hw_host", "text": "Question one."},
        {"speaker": "guest", "guest_name": "Ruth Hollis", "text": "Ruth Hollis: 1066."},
        {"speaker": "guest", "guest_name": "Ruth Hollis", "text": "Ruth Hollis is my name, Des."},
        {"speaker": "hw_host", "text": "Ruth Hollis: right!"}])
    assert [l.text for l in s.lines] == ["Question one.", "1066.", "Ruth Hollis is my name, Des.", "Ruth Hollis: right!"]


def test_every_script_s_headline_says_in_its_schema_that_it_is_never_empty():
    """The 2026-11-26 scratch breakfast: Anthropic's structured output keeps "minLength" only as a hint, and three
    of twelve field reports on a general brief ("the morning commute") came back with "headline": "", each a retry."""
    import anthropic
    import pytest
    from pydantic import ValidationError

    from newsroom.models import BulletinScript, FieldReportScript, SegmentType, WeatherScript, script_schema

    narrowed = script_schema(SegmentType.field_report, ("host_a", "host_b", "weather_reporter"))
    for model in (FieldReportScript, BulletinScript, WeatherScript, narrowed):
        help_ = anthropic.transform_schema(model)["properties"]["headline"]["description"]
        assert "never empty" in help_ and "e.g." not in help_          # no example: the models copy one
    with pytest.raises(ValidationError, match="at least 4"):
        FieldReportScript(headline="", location="the fish quay", backdrop="harbour", lower_third="Miles Okafor",
                          lines=[{"speaker": "host_a", "text": "Over to Miles."}, {"speaker": "host_b", "text": "Thanks."}])
