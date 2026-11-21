"""The Slipway: Channel 8's teen magazine at 18:30 (entertainment/slipway.py, the user, 2026-11-19), in Cartoon Time's
half hour. The model is stubbed: no network."""
from __future__ import annotations

import time

import pytest

import entertainment
from entertainment import slipway
from newsroom import backdrops, llm, locations, schedule, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


@pytest.fixture
def channel():
    undo = entertainment.use()
    yield
    undo()


def _booking(feature="Morwenna Kitto", pupil="Ellie Penrose", what="mend a bike puncture"):
    return slipway.SlipwayBooking.model_validate({
        "feature": {"name": feature, "role": "founder of a junior sailing club", "gender": "f", "age": "young",
                    "about": "she started a Saturday club for twelve-year-olds who had never been in a boat"},
        "howto": {"what": what, "name": "Danny Hocking", "role": "bike repair stall, Harrow Street", "gender": "m",
                  "age": "young", "steps": ["Wheel off", "Find the hole", "Glue and patch", "Pump it up"]},
        "watch": {"name": "Jago Carne", "role": "apprentice boatbuilder", "gender": "m", "age": "young",
                  "about": "he built his first clinker dinghy alone this autumn"},
        "pupil": {"name": pupil, "year": "Year 10", "gender": "f",
                  "about": "she runs the Academy's board games club on Thursday lunchtimes"},
        "ask": {"name": "Sue Lanyon", "role": "beach lifeguard", "gender": "f", "age": "middle",
                "questions": ["Kayla from Saltby asks how you train", "Ben from Harbour Row asks what a rip is",
                              "Mia from the Salting asks what the flags mean"]},
        "letters": ["Jade from Saltby says hi", "Owen from the Salting says a pasty is a meal",
                    "Priya from Harbour Row asks if Tegan finished", "Sam says the kiosk does the best chips",
                    "Lily from Greenhill Road learnt three knots"],
        "question": "Is a pasty a meal or a snack?",
        "whats_on": ["a beach clean on Saturday at ten at the lifeboat station", "games night at the library, Friday"],
        "challenge": "find five kinds of seaweed on the beach, with a grown-up"})


def _stub(monkeypatch, reply):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, schema, system, user))
        if isinstance(reply, Exception):
            raise reply
        return reply(schema) if callable(reply) else reply
    monkeypatch.setattr(llm, "complete_json", complete_json)
    return seen


def test_the_slipway_has_cartoon_times_half_hour_and_undo_takes_it_off():
    before = schedule.show_at(_at(18, 40)).id
    undo = entertainment.use()
    try:
        assert schedule.show_at(_at(18, 40)).id == "slipway" and schedule.show_end(_at(18, 40)) == _at(19, 0)
        assert schedule.show_at(_at(19, 10)).id == "kettle"                       # the Kettle keeps its hour
        assert slipway.SET in locations.BY_ID and writers.CHECK_HOOKS["slipway"] is slipway.check
        assert (backdrops.ART_DIR / f"{slipway.SET}.png").exists()               # its art, approved 2026-11-20
        assert slipway.SET not in backdrops.PAINTERS                             # no stand-in painter since
        w = world_mod.seed()
        assert w.character("slip_a").name == "Tegan Trevenna" and w.character("slip_b").name == "Elis Pengilly"
        # Their voices are their own, never a guest pool voice (every resident with it would be recast).
        assert {w.character("slip_a").voice, w.character("slip_b").voice} == {"bf_trevenna", "bm_pengilly"}
        assert not {w.character("slip_a").voice} & set(world_mod.GUEST_VOICES_F)
    finally:
        undo()
    assert schedule.show_at(_at(18, 40)).id == before and slipway.SET not in locations.BY_ID


def test_tonight_is_booked_once_and_its_guests_join_the_town_the_pupil_as_a_teenager(monkeypatch):
    w = world_mod.seed()
    seen = _stub(monkeypatch, _booking())
    k = slipway.commission(w)
    assert len(seen) == 1 and slipway.booked(w) is k and len(seen) == 1
    pupil = w.person_by_name("Ellie Penrose")
    assert pupil is not None and world_mod.is_teen(pupil.role)                      # a teenager's voice
    assert w.person_by_name("Danny Hocking") and w.person_by_name("Morwenna Kitto")
    assert "Tegan" not in {p.name.split()[0] for p in w.people if p.name == "Tegan Trevenna"}   # never a resident


def test_a_recent_guest_or_how_to_is_not_booked_again_and_last_times_challenge_comes_back(monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    slipway.commission(w)
    w.slipways[-1]["date"] = slipway.date.fromordinal(slipway.date.fromisoformat(w.last_date).toordinal() - 7).isoformat()   # last week's
    seen = _stub(monkeypatch, _booking(pupil="Someone Else"))
    k = slipway.commission(w)
    assert k["stand_in"]                                                       # the same feature guest: refused
    assert "LAST TIME'S CHALLENGE: find five kinds of seaweed" in seen[0][3]
    assert k["last"] == "find five kinds of seaweed on the beach, with a grown-up"


def test_the_briefs_carry_tonights_booking(monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    slipway.commission(w)
    howto = slipway.brief_for(w, slipway._HOWTO)
    assert "Danny Hocking" in howto and "1. Wheel off; 2. Find the hole" in howto and "{" not in howto
    assert "Ellie Penrose" in slipway.brief_for(w, slipway._ACADEMY)
    assert "Jade from Saltby" in slipway.brief_for(w, slipway._LETTERS)
    assert "Lily from Greenhill Road" in slipway.brief_for(w, slipway._BITS_B[0])      # the rest of the messages
    assert "seaweed" in slipway.brief_for(w, slipway._CHALLENGE)
    assert "only for their own items" in slipway.for_prompt(w)
    watch, ask = slipway.brief_for(w, slipway._WATCH), slipway.brief_for(w, slipway._ASK)
    assert "Jago Carne, apprentice boatbuilder" in watch and "{" not in watch
    assert "Sue Lanyon, beach lifeguard" in ask and "Ben from Harbour Row asks what a rip is" in ask and "{" not in ask
    k = slipway.tonight(w)
    assert slipway.guest_for(k, slipway._WATCH) == "Jago Carne" and slipway.guest_for(k, slipway._ASK) == "Sue Lanyon"
    assert w.person_by_name("Jago Carne") and w.person_by_name("Sue Lanyon")             # they join the town
    assert slipway.caption(w, "Sue Lanyon") == "You asked: beach lifeguard"
    assert "one to watch, Jago Carne" in slipway.for_prompt(w) and "You asked: Sue Lanyon" in slipway.digest(w, w.last_date)


def test_a_booking_saved_before_the_new_items_still_airs(monkeypatch):
    """The town's slipways from 2026-11-19 have no one to watch and no YOU ASKED: their briefs still fill."""
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    k = slipway.commission(w)
    del k["watch"], k["ask"]
    assert "{" not in slipway.brief_for(w, slipway._WATCH) and "{" not in slipway.brief_for(w, slipway._ASK)
    assert slipway.guest_for(k, slipway._ASK) is None and "one to watch" not in slipway.for_prompt(w)
    assert slipway.digest(w, w.last_date).startswith("The feature")


def _spot(guest):
    return {"headline": "A guest", "lower_third": "The Slipway", "guest_name": guest, "guest_role": "someone",
            "lines": [{"speaker": "slip_a", "text": "Hiya!"}, {"speaker": "guest", "text": "Hello."},
                      {"speaker": "slip_b", "text": "What are the rules?"}, {"speaker": "guest", "text": "None."}]}


def test_an_item_with_the_wrong_guest_is_asked_for_once_more(channel, monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    slipway.commission(w)
    replies = iter(["Morwenna Kitto", "Danny Hocking"])
    seen = _stub(monkeypatch, lambda schema: schema.model_validate(_spot(next(replies))))
    seg = Segment(slot_id=5, type=T.interview, show="slipway", brief=slipway._HOWTO, target_s=200)
    writers.script_segment(seg, w)
    assert len(seen) == 2 and "the guest is Danny Hocking" in seen[1][3] and seg.headline == "A guest"


def test_a_how_to_long_enough_for_its_target_is_kept(channel, monkeypatch):
    """2026-11-21: the how-to came back at 21 lines twice, about right for its 200 s, over the interviews' cap of
    16 + 2, and aired as a 15 s template. The links keep theirs."""
    w = world_mod.seed()
    _stub(monkeypatch, _booking())
    slipway.commission(w)
    long = {**_spot("Danny Hocking"), "lines": [
        {"speaker": ("slip_a", "guest", "slip_b", "guest")[i % 4], "text": f"Step {i}, and the tyre lever."}
        for i in range(24)]}
    seen = _stub(monkeypatch, lambda schema: schema.model_validate(long))
    seg = Segment(slot_id=5, type=T.interview, show="slipway", brief=slipway._HOWTO, target_s=200)
    writers.script_segment(seg, w)
    assert len(seen) == 1 and not seg.fallback and len(seg.lines) == 24
    assert writers.line_cap("slipway", T.links) == 16 and writers.line_cap("slipway", T.call) is None
    assert writers.line_cap("highwater", T.interview) == 40


def test_with_the_model_down_every_item_is_still_tonights(channel, monkeypatch):
    w = world_mod.seed()
    _stub(monkeypatch, llm.LLMError("down"))
    k = slipway.commission(w)
    assert k["stand_in"] and k["pupil"]["name"]
    for brief, kind in ((slipway._FEATURE, T.interview), (slipway._HOWTO, T.interview), (slipway._ACADEMY, T.interview),
                        (slipway._WATCH, T.interview), (slipway._ASK, T.interview),
                        (slipway._BITS_A[0], T.links), (slipway._CHALLENGE, T.links)):
        seg = Segment(slot_id=3, type=kind, show="slipway", brief=brief, target_s=100)
        writers.script_segment(seg, w)
        assert seg.lines, brief[:20]
        if kind is T.interview:
            assert seg.lines[1].guest_name == slipway.guest_for(k, brief)


def test_the_half_hour_ends_on_the_challenge_in_time_for_the_kettle(channel):
    """The real producer, at the rehearsal's lengths (2026-11-19: interviews at 0.8 of target, Tegan and Elis's own
    items at 1.05) and 15% either side: the challenge and the goodbye close it by seven, nothing twice."""
    from newsroom.buffer import Buffer
    from newsroom.producer import Producer

    for factor in (0.85, 1.0, 1.15):
        p = Producer(Buffer(), 600, start_ts=_at(18, 30))
        seen, ended = [], None
        for _ in range(60):
            ts = p.cursor_ts
            seg = p.plan_one()
            if seg.show != "slipway":
                ended = ts
                break
            seen.append(seg.brief or "")
            k = 1.0 if seg.type in (T.bumper, T.ad_break) else (0.8 if seg.type is T.interview else 1.05) * factor
            p.cursor_ts = ts + seg.target_s * k
        assert ended is not None and abs(ended - _at(19)) <= 60, (factor, ended - _at(19))
        assert seen[-2].startswith("THE CHALLENGE"), factor
        for key in ("THE FEATURE", "HOW TO", "ONE TO WATCH", "ACADEMY CORNER", "YOU ASKED", "HAVE A GO",
                    "THE MESSAGES", "WHAT'S ON"):
            assert sum(b.startswith(key) for b in seen) == 1, (factor, key)
        bits = [b for b in seen if b in slipway._BITS_A or b in slipway._BITS_B]
        assert len(bits) == len(set(bits)), factor                               # no bit twice
        # No guest comes back but the feature's Have a Go: 2026-11-20's quick fives brought each one round again.
        k = {"feature": {"name": "F"}, "howto": {"name": "H"}, "pupil": {"name": "P"}, "watch": {"name": "W"},
             "ask": {"name": "A"}}
        guests = [slipway.guest_for(k, b) for b in seen if slipway.guest_for(k, b)]
        assert sorted(guests) == ["A", "F", "F", "H", "P", "W"], (factor, guests)
        # At last night's lengths, four bits where nine items looped (2026-11-20); seven if everything runs short.
        assert len(bits) <= (4 if factor == 1.0 else 7), (factor, len(bits))
