"""Moods: a script line says how it is said, and the face shows it (sprites.MOODS, chosen on a contact
sheet 2026-11-01). The model is stubbed and nothing is voiced."""
from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from newsroom import llm, scenes, sprites, world as world_mod, writers  # noqa: E402
from newsroom.buffer import Buffer  # noqa: E402
from newsroom.models import MOOD_NAMES, GuestLine, Line, Segment, SegmentType as T  # noqa: E402
from newsroom.player import Player  # noqa: E402
from newsroom.producer import Producer  # noqa: E402


def test_the_scripts_moods_are_the_faces_moods():
    assert sprites.MOODS == ("",) + MOOD_NAMES
    assert set(sprites.REACT) <= set(MOOD_NAMES) and set(sprites.REACT.values()) <= set(MOOD_NAMES)


def test_a_mood_in_the_models_own_words_is_mapped_or_dropped():
    def mood(m):
        return GuestLine.model_validate({"speaker": "guest", "text": "Well.", "mood": m}).mood
    assert mood("LAUGHING") == "laughing"
    assert mood("amused") == "happy" and mood("indignant") == "cross" and mood("sheepish") == "embarrassed"
    assert mood("neutral") is None and mood("") is None and mood(None) is None


def test_the_mood_goes_from_the_script_to_the_line_on_air(monkeypatch):
    w = world_mod.seed()

    def write(task, schema, system, user):
        assert "mood is drawn in the speaker's face" in system
        return schema.model_validate({
            "headline": "A gull rode the ferry", "lower_third": "The Last Ferry", "guest_name": "Megan Tolley",
            "guest_role": "ferry hand", "guest_gender": "f",
            "lines": [{"speaker": "late_host", "text": "Any crossing that stays with you?"},
                      {"speaker": "guest", "text": "A gull rode the whole way over.", "mood": "amused"},
                      {"speaker": "late_host", "text": "That is the most Port Wexley thing I have heard.",
                       "mood": "laughing"}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = writers.script_segment(Segment(slot_id=7, type=T.interview, show="late", target_s=120), w)
    assert [l.mood for l in seg.lines] == [None, "happy", "laughing"]


def test_a_script_keeps_three_moods_and_the_rarer_faces_win():
    moods = ["laughing", None, "smug", "laughing", None, "worried", "happy", None, "laughing", "sad"] + [None] * 6
    lines = [Line(speaker="host_b" if i % 2 else "guest", text="Well.", mood=m) for i, m in enumerate(moods)]
    writers.ration_moods(lines)
    assert [(i, l.mood) for i, l in enumerate(lines) if l.mood] == [(0, "laughing"), (5, "worried"), (9, "sad")]
    few = [Line(speaker="mag_a", text="Oh?", mood="smug"), Line(speaker="mag_b", text="Yes.", mood="laughing")]
    assert [l.mood for l in writers.ration_moods(few)] == ["smug", "laughing"]     # under the cap: untouched


def test_the_newsreaders_sign_off_is_a_plain_line(monkeypatch):
    w = world_mod.seed()

    def write(task, schema, system, user):
        assert "smug is a gloat or a dig" in str(schema.model_json_schema())
        return schema.model_validate({
            "headline": "Honey on the market stall", "lower_third": "Harrow Street market",
            "lines": [{"speaker": "anchor", "text": "A fourth jar of honey has turned up at Gwen Pascoe's stall."},
                      {"speaker": "anchor", "text": "Bring your own spoon, Gwen says.", "mood": "smug"}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = writers.script_segment(Segment(slot_id=8, type=T.bulletin, show="news", target_s=45), w)
    assert [l.mood for l in seg.lines] == [None, None]


def test_the_view_carries_the_lines_mood_and_the_listeners_react():
    buf = Buffer()
    pl = Player(buf, world_mod.seed(), Producer(buf, 600), audio=False)
    seg = Segment(slot_id=0, type=T.interview, show="late", lines=[
        Line(speaker="late_host", text="Hello.", duration_s=1.0),
        Line(speaker="guest", text="Ha!", guest_name="Megan Tolley", duration_s=1.0, mood="laughing")])
    pl.current, pl.line_idx, pl.seg_start, pl.line_start = seg, 1, 0.0, 0.0
    v = pl.view(0.5)
    assert v.mood == "laughing"
    assert scenes._mood(v, True) == "laughing" and scenes._mood(v, False) == "happy"
    v.mood = "cross"
    assert scenes._mood(v, False) == ""                      # a cross word leaves the others as they are
    pygame.init()
    for m in sprites.MOODS:                                  # every face draws, talking and shut, at every size
        c = pygame.Surface((320, 180))
        for scale in (1, 2, 4):
            sprites.draw_character(c, 160, 170, "anchor", 0.0, 0.5, scale=scale, mood=m)
            sprites.draw_character(c, 160, 170, "late_host", 0.6, 0.5, scale=scale, mood=m)


def test_a_presenter_never_thanks_themselves():
    """On the 2026-11-21 night 22 lines did: "Thanks, Rosie. Gordon, over to you" from Rosie, "Thanks, Fran here at
    the sports corner" from Fran, "Thanks, Pat and Clive. Gordon..." from Pat."""
    w = world_mod.seed()
    lines = [Line(speaker="host_a", text="Thanks, Rosie. Gordon, over to you. What's the sky doing?"),
             Line(speaker="sport", text="Thanks, Fran here at the sports corner. Tides won three-one."),
             Line(speaker="mag_a", text="Thanks, Pat and Clive. Gordon, what's the sky doing over the estuary?"),
             Line(speaker="anchor", text="Thank you, Dana. Good evening, Port Wexley."),
             Line(speaker="anchor", text="Thanks, Dana here, and the weather is in the safe hands of Gordon Pell."),
             Line(speaker="weather", text="Thanks, Dana. It is a cold one tonight."),              # Gordon thanking Dana
             Line(speaker="anchor", text="Thanks, Miles. Stay warm out there."),                 # Dana thanking Miles
             Line(speaker="guest", guest_name="Rosie Penhale", text="Thanks, Rosie. Lovely to be here."),
             Line(speaker="host_a", text="Thanks, Rosie."),                                       # nothing else: left
             Line(speaker="anchor", text="And thanks, Dana would say, to the lifeboat crew.")]   # not at the front
    assert writers.nobody_thanks_themselves(lines, w) == 5
    assert [l.text for l in lines] == [
        "Gordon, over to you. What's the sky doing?", "Fran here at the sports corner. Tides won three-one.",
        "Gordon, what's the sky doing over the estuary?", "Good evening, Port Wexley.",
        "Dana here, and the weather is in the safe hands of Gordon Pell.", "Thanks, Dana. It is a cold one tonight.",
        "Thanks, Miles. Stay warm out there.", "Thanks, Rosie. Lovely to be here.", "Thanks, Rosie.",
        "And thanks, Dana would say, to the lifeboat crew."]


def test_the_thanks_comes_off_as_the_script_is_filed(monkeypatch):
    w = world_mod.seed()

    def write(task, schema, system, user):
        assert "Nobody thanks or greets themselves" in system
        return schema.model_validate({
            "headline": "Clear and cold, with a frost by morning", "map_state": "sunny", "temp_c": 4,
            "lines": [{"speaker": "anchor", "text": "Thanks, Dana here, and Gordon Pell has the weather."},
                      {"speaker": "weather", "text": "Thanks, Dana. Clear and cold tonight, a frost by morning."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = writers.script_segment(Segment(slot_id=3, type=T.weather, show="news", target_s=60), w)
    assert [l.text for l in seg.lines] == ["Dana here, and Gordon Pell has the weather.",
                                           "Thanks, Dana. Clear and cold tonight, a frost by morning."]


def test_a_guests_reply_written_into_the_presenters_line_goes_back_to_the_guest():
    """Coastwide, 19:48 on 2026-11-21: Pat welcomed the beekeeper and thanked herself for it, in one line."""
    w = world_mod.seed()
    lines = [Line(speaker="mag_a", text="Our next guest knows more about the bees of Port Wexley than anyone has a right "
                                        "to. Welcome to Coastwide. Thank you, Pat. Happy to be here, though the bees are asleep."),
             Line(speaker="mag_a", text="Asleep, are they? So what do you do with a hive in November?"),
             Line(speaker="guest", guest_name="Ruth Oakley", guest_role="beekeeper, Harrow Street", text="You leave them be.")]
    out = writers.guests_reply_split_off(lines, w)
    assert [(l.speaker, l.guest_name, l.text) for l in out] == [
        ("mag_a", None, "Our next guest knows more about the bees of Port Wexley than anyone has a right to. Welcome to Coastwide."),
        ("guest", "Ruth Oakley", "Thank you, Pat. Happy to be here, though the bees are asleep."),
        ("mag_a", None, "Asleep, are they? So what do you do with a hive in November?"),
        ("guest", "Ruth Oakley", "You leave them be.")]
    assert out[1].guest_role == "beekeeper, Harrow Street"
    # with no guest to give it to, or the thanks at the very front, the line is left for the other repair
    alone = [Line(speaker="anchor", text="That is the news. Thank you, Dana. Goodnight.")]
    assert writers.guests_reply_split_off(alone, w) == alone
    front = [Line(speaker="mag_a", text="Thanks, Pat. Gordon, over to you."), lines[2]]
    assert writers.guests_reply_split_off(front, w) == front


def test_an_items_first_line_doesnt_thank_whoever_it_hands_to():
    """Told not to thank themselves, three of twelve replayed hand-overs thanked Gordon before he had spoken."""
    w = world_mod.seed()
    lines = [Line(speaker="anchor", text="Thanks, Gordon. Over to the weather, and it's a big one for the boats tonight."),
             Line(speaker="weather", text="Good evening, Port Wexley. Tonight's a spring-tide night.")]
    assert writers.nobody_thanks_themselves(lines, w) == 1
    assert lines[0].text == "Over to the weather, and it's a big one for the boats tonight."
    # thanks to someone who has spoken, or who isn't in the item, stands
    after = [Line(speaker="weather", text="Clear and cold tonight."), Line(speaker="anchor", text="Thanks, Gordon. On to the sport.")]
    assert writers.nobody_thanks_themselves(after, w) == 0
    outside = [Line(speaker="anchor", text="Thanks, Miles. Gordon Pell has the weather."),
               Line(speaker="weather", text="Clear and cold tonight.")]
    assert writers.nobody_thanks_themselves(outside, w) == 0
    guest = [Line(speaker="mag_a", text="Thank you, Ruth. Our next guest keeps eleven hives."),
             Line(speaker="guest", guest_name="Ruth Oakley", text="I do, Pat.")]
    assert writers.nobody_thanks_themselves(guest, w) == 1 and guest[0].text == "Our next guest keeps eleven hives."
