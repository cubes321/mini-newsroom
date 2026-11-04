"""A guest is on a show once a day: on 2026-11-03 Coastwide interviewed the mayor three times in an hour, every
19 slots, because the writers' list of the last eight guests had forgotten her each time. The model is
stubbed: no network."""
from __future__ import annotations

from newsroom import llm, schedule, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def test_guests_today_are_this_shows_and_todays():
    w = world_mod.seed()
    w.record_aired("interview", "Mayor on frost", None, "...", show="magazine", guest="Helen Strand", aired=False)
    w.record_aired("interview", "Mayor again", None, "...", show="magazine", guest="helen strand")
    w.record_aired("interview", "Mayor at breakfast", None, "...", show="breakfast", guest="Jasper Fowle")
    w.record_aired("vox_pop", "Chips", None, "...", show="magazine")
    w.archive.append({"date": "2020-01-01", "type": "interview", "show": "magazine", "guest": "Ruth Ellery"})
    assert w.guests_today("magazine") == ["Helen Strand"]


def test_a_guest_already_on_the_show_today_is_not_booked_again(monkeypatch):
    w = world_mod.seed()
    w.record_aired("interview", "Mayor Helen Strand, off duty, on frost", None, "...", show="magazine",
                   guest="Helen Strand", aired=False)
    monkeypatch.setattr(writers, "_recent_guests", writers.deque(maxlen=8))    # she has dropped off it
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        name = "Helen Strand" if len(asked) == 1 else "Ellie Marr"
        return schema.model_validate({
            "headline": "Frost on the quay", "lower_third": "Coastwide", "guest_name": name,
            "guest_role": "a guest", "guest_gender": "f",
            "lines": [{"speaker": "mag_a", "text": "Cold one?"}, {"speaker": "guest", "text": "Freezing."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=91, type=T.interview, show="magazine", target_s=90)
    writers.script_segment(seg, w)
    assert "RECENT GUESTS (book someone else): Helen Strand" in asked[0]
    assert len(asked) == 2 and "NOT Helen Strand" in asked[1]
    assert w.guests_today("magazine") == ["Helen Strand", "Ellie Marr"]


def _inquiry_night(w):
    w.inquiries = [{"date": w.last_date, "thread_id": None, "title": "Who Opens the Keeper's Lamp Room?",
                    "guest": "Ivy Marchetti", "angle": "who holds the key", "questions": ["Who decided?"]}]
    tam = w.person_by_name("Tam Buchanan")
    tam.memories = [{"said": "the crew launch from the slipway", "show": "Coastwide", "date": w.last_date}]


def _interview(name):
    return {"headline": f"{name} on the lamp room", "lower_third": "The Inquiry", "guest_name": name,
            "guest_role": "a guest", "guest_gender": "f",
            "lines": [{"speaker": "mag_a", "text": "Who decided?"}, {"speaker": "guest", "text": "Not me."}]}


def test_the_inquirys_guest_is_not_put_back_by_the_ask_about_a_returning_guest(monkeypatch):
    """2026-11-03, slot 141: THE GUEST booked for "the other side"; asked again, Tam Buchanan; asked about
    Tam with what he said before (and no longer told "NOT Ivy"), THE GUEST again, and that aired."""
    w = world_mod.seed()
    _inquiry_night(w)
    monkeypatch.setattr(writers, "_recent_guests", writers.deque(maxlen=8))
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return schema.model_validate(_interview("Tam Buchanan" if len(asked) == 2 else "Ivy Marchetti"))
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=141, type=T.interview, show="inquiry", part="other", target_s=120)
    writers.script_segment(seg, w)
    assert len(asked) == 3 and "NOT Ivy Marchetti" in asked[2] and "Tam Buchanan has been on before" in asked[2]
    assert not seg.fallback and {l.guest_name for l in seg.lines if l.speaker == "guest"} == {"Tam Buchanan"}


def test_the_inquirys_films_are_not_the_guests_either(monkeypatch):
    w = world_mod.seed()
    _inquiry_night(w)
    monkeypatch.setattr(writers, "_recent_guests", writers.deque(maxlen=8))
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return schema.model_validate({
            "headline": "The lamp room key", "lower_third": "The Inquiry", "location": "the lighthouse",
            "backdrop": "lighthouse", "guest_name": "Ivy Marchetti" if len(asked) == 1 else "Morag Lyle",
            "guest_role": "a guest", "guest_gender": "f",
            "lines": [{"speaker": "mag_a", "text": "Miles?"}, {"speaker": "reporter", "text": "Here."},
                      {"speaker": "guest", "text": "It's locked."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=142, type=T.feature, show="inquiry", target_s=100)
    writers.script_segment(seg, w)
    assert len(asked) == 2 and "they are THE GUEST" in asked[1]


def test_the_close_names_its_own_programme():
    w = world_mod.seed()
    _, user = writers.build_prompt(T.links, w, target_s=45, show=schedule.get("inquiry"), part="close")
    assert "END of The Inquiry" in user and "never another" in user
    assert writers._title(schedule.get("outabout")) == "Out and About"
