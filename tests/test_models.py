

def test_a_guests_line_loses_their_own_name_in_front():
    """High Water's spring tide, 2026-11-20: "Ruth Hollis: 1066." would have been read out, name and all."""
    from newsroom.models import PanelScript

    s = PanelScript(headline="The spring tide", lower_third="High Water", guest_name="Ruth Hollis", lines=[
        {"speaker": "hw_host", "text": "Question one."},
        {"speaker": "guest", "guest_name": "Ruth Hollis", "text": "Ruth Hollis: 1066."},
        {"speaker": "guest", "guest_name": "Ruth Hollis", "text": "Ruth Hollis is my name, Des."},
        {"speaker": "hw_host", "text": "Ruth Hollis: right!"}])
    assert [l.text for l in s.lines] == ["Question one.", "1066.", "Ruth Hollis is my name, Des.", "Ruth Hollis: right!"]
