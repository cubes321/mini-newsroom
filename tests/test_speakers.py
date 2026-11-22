"""Who says a line: the couch's two guests, the host, and a field report's people, who have no voice of their own."""
from __future__ import annotations

from newsroom import llm, world as world_mod, writers
from newsroom.models import FieldReportScript, Line, Segment, SegmentType as T


def _couch(*rows):
    return [Line(speaker=s, text=t, guest_name=g, guest_role={"Nell Tressider": "singer", "Dev Ramachandran": "baker"}.get(g))
            for s, g, t in rows]


def test_a_guest_who_speaks_to_themselves_was_the_other_guest():
    """The Last Ferry, 22:13 on 2026-11-21: Nell's line to Dev, filed under Dev."""
    w = world_mod.seed()
    lines = _couch(("late_host", None, "Nell, tell us about the Cannery Tap."),
                   ("guest", "Nell Tressider", "Years ago I played the back room with a piano that had two dead keys."),
                   ("guest", "Dev Ramachandran", "And he's never let me forget it, has he, Dev? You were there."),
                   ("guest", "Dev Ramachandran", "I did, and I was right. Your voice does carry."))
    assert writers.wrong_mouths(lines, w) == 1
    assert (lines[2].speaker, lines[2].guest_name, lines[2].guest_role) == ("guest", "Nell Tressider", "singer")
    assert lines[3].guest_name == "Dev Ramachandran"


def test_a_line_telling_of_its_own_speaker_was_the_other_guest():
    """22:08: "Marjorie was in the stands with a flask. She shouted the splits at me", filed under Marjorie."""
    w = world_mod.seed()
    lines = [Line(speaker="guest", guest_name="Ruth Keddie", text="A tea cosy and nothing else, Vincent."),
             Line(speaker="guest", guest_name="Marjorie Pell", text="Marjorie was in the stands with a flask. She shouted "
                                                                   "the splits at me.")]
    assert writers.wrong_mouths(lines, w) == 1 and lines[1].guest_name == "Ruth Keddie"


def test_a_line_to_both_guests_is_the_hosts():
    """22:01: "Lewis, you have never once ... Mary, did he teach you to brake?" under Mary: Vincent's question."""
    w = world_mod.seed()
    lines = [Line(speaker="late_host", text="And the missing hose?"),
             Line(speaker="guest", guest_name="Lewis Garrow", text="Turned up behind a stack of old crates."),
             Line(speaker="guest", guest_name="Mary Tonkin", text="Lewis, you have never once heard a bumper without "
                                                                 "offering it a lesson. Mary, did he teach you to brake?")]
    assert writers.wrong_mouths(lines, w) == 1
    assert (lines[2].speaker, lines[2].guest_name) == ("late_host", None)


def test_a_guest_giving_their_own_name_is_left_alone():
    w = world_mod.seed()
    lines = [Line(speaker="late_host", text="Tell us who you are."),
             Line(speaker="guest", guest_name="Gordon Lark", text="Thanks, Vincent. Gordon Lark, for anyone who's seen me."),
             Line(speaker="guest", guest_name="Gordon Lark", text="I'm Gordon, and I tell jokes about ferries."),
             Line(speaker="guest", guest_name="Gordon Lark", text="Gordon Lark here, live from a damp pub."),
             Line(speaker="guest", guest_name="Dolores Finch", text="Gordon, you'll want to hear this.")]
    assert writers.wrong_mouths(lines, w) == 0
    # a debate's three or more guests can't be told apart: left
    three = lines + [Line(speaker="guest", guest_name="Ivy Marchetti", text="Ivy, you've seen the green.")]
    assert writers.wrong_mouths(three, w) == 0


def test_a_field_report_puts_no_question_to_someone_with_no_voice(monkeypatch):
    """18:35 on 2026-11-21: Miles asked "Ivy, what's the story?" and Gordon answered for her."""
    w = world_mod.seed()
    ivy = next(p.name for p in w.people if p.name.startswith("Ivy "))
    asks = []

    def write(task, schema, system, user):
        asks.append(user)
        assert "Only the presenters speak" in system
        q = "Ivy, what's the story?" if len(asks) == 1 else "Ivy tells me the boats are in."
        return schema.model_validate({
            "headline": "Frost on the fish quay", "location": "the fish quay", "backdrop": "fish_quay",
            "lower_third": "Frost on the quay", "thread_id": None, "thread_status": None,
            "lines": [{"speaker": "anchor", "text": "Miles is on the quay."},
                      {"speaker": "reporter", "text": f"Thanks, Dana. The boats are in. {q}"},
                      {"speaker": "anchor", "text": "Thanks, Miles."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = writers.script_segment(Segment(slot_id=3, type=T.field_report, show="news", target_s=90), w)
    assert len(asks) == 2 and "NO QUESTION TO IVY" in asks[1] and ivy.split()[0] == "Ivy"
    assert "Ivy tells me" in seg.lines[1].text
    # the presenters asking each other, and a word that only looks like a name, are fine
    s = FieldReportScript.model_construct(lines=[Line(speaker="reporter", text="Dana, can you hear me? Right, what next?")])
    assert writers.asked_with_no_voice(s, w) == []
    s.lines.append(Line(speaker="reporter", text="Ivy, how did it go?"))
    assert writers.asked_with_no_voice(s, w) == ["Ivy"]
