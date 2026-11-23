"""The Inquiry's three faults of the 2026-11-22 night: the mayor, THE GUEST, booked three times running for items
that weren't hers (two templates), her trailed four times after she had left, and a goodnight over the line limit
(a third template). The model is stubbed: no network."""
from __future__ import annotations

from newsroom import council, llm, schedule, world as world_mod, writers
from newsroom.models import BulletinScript, Segment, SegmentType as T


def _night(w, guest="Helen Strand"):
    tid = w.update_thread(None, "Cannery historian still hunting front-row woman", "so far")
    t = w.thread(tid)
    t.people = [p.id for p in (w.person_by_name("Marjorie Pell"), w.person_by_name("Helen Strand")) if p]
    w.inquiries = [{"date": w.last_date, "thread_id": tid, "title": "Who Pays to Find the Front-Row Woman?",
                    "guest": guest, "angle": "who pays", "questions": ["Who is paying?"]}]
    return t


def test_the_re_ask_names_a_free_councillor_for_a_council_brief():
    w = world_mod.seed()
    _night(w)
    brief = "a councillor or board member who will vote on it: what they will vote for, and why"
    first = council.COUNCILLORS[0][0]
    assert writers._free_for_the_inquiry(w, ["Helen Strand"], brief)[0] == first
    taken = ["Helen Strand", first]                               # booked already tonight: the next one along
    name, role = writers._free_for_the_inquiry(w, taken, brief)
    assert name == council.COUNCILLORS[1][0] and role.startswith("councillor, ")
    note = writers._not_the_guest(w, "Helen Strand", brief, T.interview, suggest=True)
    assert f"Book {first} (councillor, " in note and "not THE GUEST" in note
    assert "Book " not in writers._not_the_guest(w, "Helen Strand", brief, T.interview)   # the first ask names nobody


def test_otherwise_one_of_the_storys_own_people_who_hasnt_been_on():
    w = world_mod.seed()
    _night(w)
    brief = "how the town handled something like it before, from the record and the town's history"
    assert writers._free_for_the_inquiry(w, ["Helen Strand"], brief)[0] == "Marjorie Pell"
    assert writers._free_for_the_inquiry(w, ["Helen Strand", "Marjorie Pell"], brief) is None   # nobody left: the model's


def test_booked_the_guest_twice_the_last_ask_names_someone_and_it_airs(monkeypatch):
    w = world_mod.seed()
    _night(w)
    monkeypatch.setattr(writers, "_recent_guests", writers.deque(maxlen=8))
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        name = "Helen Strand" if len(asked) < 2 else council.COUNCILLORS[0][0]
        return schema.model_validate({
            "headline": f"{name} on the search", "lower_third": "The Inquiry", "guest_name": name,
            "guest_role": "a guest", "guest_gender": "f",
            "lines": [{"speaker": "mag_a", "text": "Who is paying?"}, {"speaker": "guest", "text": "Not yet decided."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=100, type=T.interview, show="inquiry", target_s=120, part="other",
                  brief="a councillor or board member who will vote on it: what they will vote for, and why")
    writers.script_segment(seg, w)
    assert f"Book {council.COUNCILLORS[0][0]}" in asked[1]
    assert not seg.fallback and {l.guest_name for l in seg.lines if l.speaker == "guest"} == {council.COUNCILLORS[0][0]}


def _gone(w):
    part_two = next(i for i in map(schedule.as_item, schedule.SHOWS["inquiry"].pattern) if i.part == "cont").brief
    w.record_aired("interview", "Strand: no budget yet, part two", None, "...", show="inquiry", brief=part_two)


def test_the_guest_trailed_after_leaving_is_caught_from_the_nights_own_lines():
    w = world_mod.seed()
    _night(w)
    film = BulletinScript.model_validate({"headline": "The money", "lower_third": "The Inquiry", "lines": [
        {"speaker": "mag_a", "text": "That is exactly the question we will put to the mayor in the studio."},
        {"speaker": "mag_a", "text": "The council voted to ask for more, and Helen Strand is here to say what that means."},
        {"speaker": "mag_a", "text": "First, the money question is still open, and we're going to put it to the mayor now."},
        {"speaker": "mag_a", "text": "Helen Strand told us earlier that nothing is decided."},
        {"speaker": "mag_a", "text": "So who should get to ask the mayor what it will cost?"}]})
    assert writers.trails_gone_guest(film, w) == []                       # she hasn't left yet
    _gone(w)
    assert len(writers.trails_gone_guest(film, w)) == 3                   # not the past, not the vox pop's question


def test_asked_again_the_trail_comes_off_or_the_script_stands(monkeypatch):
    w = world_mod.seed()
    _night(w)
    _gone(w)
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        text = ("We will put it to the mayor next." if len(asked) == 1 else "The mayor told us earlier it is not decided.")
        return schema.model_validate({"headline": "The money", "lower_third": "The Inquiry",
                                      "lines": [{"speaker": "mag_a", "text": text}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=120, type=T.links, show="inquiry", target_s=40, brief="Pat links to the next film")
    writers.script_segment(seg, w)
    assert len(asked) == 2 and "THE GUEST has LEFT the studio, so these say" in asked[1]
    assert not seg.fallback and "earlier" in seg.lines[0].text


def test_a_line_over_the_limit_is_split_at_its_sentences_not_failed():
    long = " ".join(f"Sentence number {i} of Pat's goodnight, which goes on rather longer than it should." for i in range(14))
    assert len(long) > llm.LINE_MAX
    raw = ('{"headline": "Goodnight from The Inquiry", "lower_third": "The Inquiry", '
           '"lines": [{"speaker": "mag_a", "text": "%s"}, {"speaker": "mag_a", "text": "Goodnight."}]}' % long)
    script = llm._parse(BulletinScript, raw)
    assert len(script.lines) == 3 and all(len(l.text) <= llm.LINE_MAX for l in script.lines)
    assert " ".join(l.text for l in script.lines[:2]) == long and script.lines[-1].text == "Goodnight."
    one = "word " * 300                                                   # one sentence past the limit: cut at a space
    data = {"lines": [{"speaker": "mag_a", "text": one.strip()}]}
    assert llm.split_long_lines(data) and all(0 < len(l["text"]) <= llm.LINE_MAX for l in data["lines"])
    assert " ".join(l["text"] for l in data["lines"]) == one.strip()
