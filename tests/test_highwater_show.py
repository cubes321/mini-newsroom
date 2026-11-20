"""High Water on air (entertainment/highwater_show.py): the booking, the briefs, the check and the half hour. The game
is tested in test_highwater.py. The model is stubbed: no network."""
from __future__ import annotations

import time

import pytest

import entertainment
from entertainment import highwater as hw, highwater_show as hs
from newsroom import llm, locations, schedule, world as world_mod, writers
from newsroom.models import PanelLine, Segment, SegmentType as T


def _at(h, m=0):
    lt = time.localtime()
    return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))


@pytest.fixture
def channel():
    undo = entertainment.use()
    yield
    undo()


def _town():
    w = world_mod.seed()
    for i, (name, role) in enumerate((("Jan Pascoe", "harbour cafe owner"), ("Dev Hocking", "crab boat skipper"),
                                      ("Sue Tonkin", "librarian, Harrow Street"), ("Ray Opie", "retired postman"),
                                      ("Kayla Penrose", "pupil at Greymouth Academy, Year 10"))):
        w.ensure_person(name, role, "resident")
    return w


def _booking(business="Somebody Else's Shop"):
    def qs(kind, n):
        return [{"question": f"{kind} question number {i} please?", "answer": f"{kind} {i}", "wrong": f"not {i}"}
                for i in range(n)]
    return hs.HighWaterBooking.model_validate({
        "paddle": qs("paddle", hs.MOST_ASKED), "swim": qs("swim", hs.MOST_ASKED), "spring": qs("spring", 3),
        "harbour": qs("harbour", 6),
        "prizes": [{"business": business, "prize": p} for p in ("a cream tea", "a hamper", "a voucher", "a weekend")]})


def _stub(monkeypatch, reply):
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append((task, schema, system, user))
        if isinstance(reply, Exception):
            raise reply
        return reply(schema) if callable(reply) else reply
    monkeypatch.setattr(llm, "complete_json", complete_json)
    return seen


def test_high_water_has_six_oclock_and_undo_takes_it_off():
    before = schedule.show_at(_at(18, 10)).id
    undo = entertainment.use()
    try:
        assert schedule.show_at(_at(18, 10)).id == "highwater" and schedule.show_end(_at(18, 10)) == _at(18, 30)
        assert schedule.show_at(_at(18, 40)).id == "slipway"
        assert hs.SET in locations.BY_ID and writers.CHECK_HOOKS["highwater"] is hs.check
        assert "highwater" in writers.DEBATE_SHOWS and writers.LINE_CAPS["highwater"] == 40
        host = world_mod.seed().character("hw_host")
        assert host.name == "Des Kneebone" and host.voice == "bm_kneebone"         # his own, never a guest pool's
        assert "High Water" in entertainment.CLOSEDOWN_TEXT
    finally:
        undo()
    assert schedule.show_at(_at(18, 10)).id == before and hs.SET not in locations.BY_ID


def test_two_grown_up_residents_climb_each_with_their_own_nature():
    w = _town()
    cs = hs.climbers(w)
    assert len(cs) == 2 and cs == hs.climbers(w)                              # the night's draw
    assert all(not world_mod.is_teen(c["role"]) and c["role"] != "resident" for c in cs)
    for c in cs:
        assert (c["ability"], c["bold"]) == hs._nature(c["name"]) and 0.6 <= c["ability"] <= 0.85


def test_nobody_climbs_again_soon_or_after_another_channel_8_show(monkeypatch):
    w = _town()
    _stub(monkeypatch, _booking())
    first = {c["name"] for c in hs.commission(w)["climbers"]}
    w.highwaters[-1]["date"] = hs._since(w, 7)                                # last week's
    w.kettles.append({"date": w.last_date, "dish": {"cook": "Sue Tonkin"}, "sofa": {"name": "Ray Opie"}})
    out = hs._lately_on_channel8(w)
    assert first <= out and {"Sue Tonkin", "Ray Opie"} <= out
    assert not {c["name"] for c in hs.climbers(w)} & out


def test_the_booking_gives_each_turn_its_question_and_the_prizes_their_real_donors(monkeypatch):
    w = _town()
    seen = _stub(monkeypatch, _booking())
    k = hs.commission(w)
    assert len(seen) == 1 and "THE DONORS, in order" in seen[0][3]
    paddle = [t["question"]["q"] for r in k["game"]["rounds"] for t in r["turns"] if t["choice"] == hw.PADDLE]
    swim = [t["question"]["q"] for r in k["game"]["rounds"] for t in r["turns"] if t["choice"] == hw.SWIM]
    assert paddle == [f"paddle question number {i} please?" for i in range(len(paddle))]   # in the order played
    assert swim == [f"swim question number {i} please?" for i in range(len(swim))]
    assert [q["q"] for q in k["game"]["spring"]["questions"]] == [f"spring question number {i} please?" for i in range(3)]
    donors = hs.donors(w)
    assert [p["business"] for p in k["prizes"].values()] + [k["star"]["business"]] == donors   # never the model's
    assert "Somebody Else's Shop" not in str(k["prizes"]) and k["star"]["prize"] == "a weekend"


def test_a_round_brief_carries_every_turn_the_tide_and_where_they_stand(monkeypatch):
    w = _town()
    _stub(monkeypatch, _booking())
    k = hs.commission(w)
    for n in range(hw.ROUNDS):
        r = k["game"]["rounds"][n]
        brief = hs.brief_for(w, "{r%d}" % (n + 1))
        assert f"ROUND {n + 1} OF {hw.ROUNDS}" in brief and "THEN THE TIDE" in brief and "WHERE THEY STAND" in brief
        for t in r["turns"]:
            if "question" in t:
                assert f"\"{t['question']['q']}\"" in brief
        for wsh in r["washed"]:
            said = "THROWS THE LIFE RING" if wsh["ring"] else "WASHED OFF"
            assert f"It reaches {wsh['who']} on step {wsh['from']}: {wsh['who'] + ' ' if wsh['ring'] else ''}{said}" in brief
    hm = hs.brief_for(w, "{hm}")
    assert "THE HARBOURMASTER'S ROUND" in hm and all(f"\"{x['question']['q']}\"" in hm
                                                     for x in k["game"]["harbour"]["questions"])
    close = hs.brief_for(w, "{close}")
    assert all(x["who"] in close for x in k["game"]["results"]) and "The Slipway is next" in close
    assert k["game"]["spring"]["who"] in hs.brief_for(w, "{spring}")


def test_a_round_missing_a_question_is_asked_for_again_then_the_codes_own_stands_in(channel, monkeypatch):
    w = _town()
    _stub(monkeypatch, _booking())
    k = hs.commission(w)
    seg = Segment(slot_id=4, type=T.interview, show="highwater", brief="{r1}", target_s=220)
    seats = [c["name"] for c in k["climbers"]]

    def short(schema):                                    # Des asks nothing: every question missing, twice
        return schema.model_validate({"headline": "Round one", "lower_third": "High Water", "lines": [
            {"speaker": "hw_host", "text": "Round one, off we go!"},
            {"speaker": "guest", "guest_name": seats[0], "text": "Ready, Des."},
            {"speaker": "guest", "guest_name": seats[1], "text": "Me too."},
            {"speaker": "hw_host", "text": "Steady as she goes."}]})
    seen = _stub(monkeypatch, short)
    writers.script_segment(seg, w)
    assert len(seen) == 2 and "weren't asked" in seen[1][3]
    asked = [t["question"] for t in k["game"]["rounds"][0]["turns"] if "question" in t]
    assert not hs.missing(seg.lines, asked)                                    # the code's own round: every one


def test_the_codes_own_rounds_and_spring_tide_ask_everything_and_seat_both_climbers(channel, monkeypatch):
    w = _town()
    _stub(monkeypatch, llm.LLMError("down"))
    k = hs.commission(w)
    assert k["stand_in"]
    for brief in ("{r1}", "{r2}", "{hm}", "{r3}", "{r4}", "{spring}"):
        seg = Segment(slot_id=5, type=T.interview, show="highwater", brief=brief, target_s=200)
        writers.script_segment(seg, w)
        assert not hs.missing(seg.lines, hs._questions(k, brief)), brief
        assert seg.work.get("seats") == [c["name"] for c in k["climbers"]]


def test_missing_reads_des_lines_in_order():
    qs = [{"q": "What is the capital city of Canada?"}, {"q": "How many legs does a spider have?"}]
    lines = [PanelLine(speaker="hw_host", text="Jan, a swim: what is the capital city of Canada?"),
             PanelLine(speaker="guest", guest_name="Jan", text="How many legs does a spider have?")]
    assert hs.missing(lines, qs) == ["How many legs does a spider have?"]     # a climber's line doesn't count


# Each item's airtime as a share of its target, from the third rehearsal (2026-11-19).
MEASURED = (("MEET", 0.49), ("{r", 0.76), ("{hm}", 0.59), ("a word", 0.87), ("{spring}", 0.59), ("{close}", 0.78))


def _measured(seg) -> float:
    if seg.type in (T.bumper, T.ad_break):
        return 1.0
    if seg.type is T.links:
        return 2.0                                                  # Des's opening ran long, at about twice
    b = seg.brief or ""
    return next((f for k, f in MEASURED if b.startswith(k)), 0.8)


def test_the_half_hour_ends_on_the_spring_tide_and_the_result_by_half_past(channel):
    """The real producer at the rehearsal's lengths and 15% either side: every round airs (Show.whole_order), the
    spring tide and the result close it near half past, and the chats between rounds are few."""
    from newsroom.buffer import Buffer
    from newsroom.producer import Producer

    for factor in (0.85, 1.0, 1.15):
        p = Producer(Buffer(), 600, start_ts=_at(18))
        seen, ended = [], None
        for _ in range(60):
            ts = p.cursor_ts
            seg = p.plan_one()
            if seg.show != "highwater":
                ended = ts
                break
            seen.append(seg.brief or "")
            k = _measured(seg) * (1.0 if seg.type in (T.bumper, T.ad_break) else factor)
            p.cursor_ts = ts + seg.target_s * k
        assert ended is not None and abs(ended - _at(18, 30)) <= 90, (factor, ended - _at(18, 30))
        chats = [b for b in seen if b.startswith(hs._DONE)]
        assert len(chats) <= (5 if factor < 1 else 3), factor                    # a few words between rounds: 8 minutes once
        assert len(chats) == len(set(chats)), factor                             # none twice
        assert seen[-2] == "{spring}" and seen[-1] == "{close}", factor
        assert [b for b in seen if b in ("{r1}", "{r2}", "{hm}", "{r3}", "{r4}")] == ["{r1}", "{r2}", "{hm}", "{r3}", "{r4}"]


def test_the_booking_asks_for_what_the_played_game_needs_and_a_short_list_is_made_up(monkeypatch):
    """Three turns a round (2026-11-19): a night takes up to 15 easy and 19 hard questions, so the game is played first
    and the model asked for that many and two more; one that comes back short is topped up, never failed."""
    w = _town()
    b = _booking()
    b.paddle, b.swim = b.paddle[:1], b.swim[:1]
    seen = _stub(monkeypatch, b)
    k = hs.commission(w)
    need = hs.needs(k["game"])
    assert f"{need[hw.PADDLE] + hs.SPARE} EASY questions" in seen[0][2] and f"{need[hw.SWIM] + hs.SPARE} HARD" in seen[0][2]
    turns = [t for r in k["game"]["rounds"] for t in r["turns"] if t["choice"] in (hw.PADDLE, hw.SWIM)]
    assert all("question" in t for t in turns) and not k["stand_in"]
    assert turns and any(t["question"]["q"] == "paddle question number 0 please?" for t in turns if t["choice"] == hw.PADDLE)


def test_a_question_in_des_own_words_counts_as_asked():
    """2026-11-19's rehearsal: "In music, what does fortissimo mean?" asked as "What does fortissimo mean, in music?"
    counted as not asked by its first five words, and the round went to the code's own."""
    qs = [{"q": "In music, what does fortissimo mean?"}, {"q": "How many months are in a year?"}]
    said = [PanelLine(speaker="hw_host", text="Sadie, a swim for you: what does fortissimo mean, in music?"),
            PanelLine(speaker="guest", guest_name="Sadie", text="Very loud!"),
            PanelLine(speaker="hw_host", text="Hilda, paddle: how many months make up a year?")]
    assert hs.missing(said, qs) == []
    assert hs.missing(said[:2], qs) == ["How many months are in a year?"]
    assert hs.missing([PanelLine(speaker="hw_host", text="What a night for music!")], qs[:1]) == [qs[0]["q"]]   # one word isn't it


def test_a_two_minute_break_takes_four_adverts_and_a_minutes_still_two():
    """High Water's three breaks are two minutes each, as a commercial half hour's (the user, 2026-11-19)."""
    from newsroom import adverts

    class Ad:
        lines, cues, duration_s, work = [], [], 30.0, {"advert": {"business": "Fowle & Sons"}}

    class Pool:
        def pick(self, now=None):
            return Ad()
    for target, n in ((60.0, 2), (120.0, 4), (0.0, 2)):
        seg = adverts.break_segment(Segment(slot_id=1, type=T.ad_break, show="highwater", target_s=target), Pool())
        assert seg.work["ads"] == n, target
    assert hs.SHOW_DEF.target_s[T.ad_break] == 120.0 and sum(e is T.ad_break for e in hs.SHOW_DEF.pattern) == 3


def test_a_short_question_counts_by_its_short_words_too_and_the_first_meet_is_one_climber(monkeypatch):
    """The fourth rehearsal (2026-11-19): "What is nine times six?" went to the code's own round, and the first meet
    introduced both climbers."""
    qs = [{"q": "What is nine times six?"}]
    assert hs.missing([PanelLine(speaker="hw_host", text="Hilda, a paddle: what's six times nine?")], qs) == []
    assert hs.missing([PanelLine(speaker="hw_host", text="Hilda, a paddle: nine lives, has a cat?")], qs) == [qs[0]["q"]]
    w = _town()
    _stub(monkeypatch, _booking())
    k = hs.commission(w)
    first, second = (hs.brief_for(w, f"MEET THE CLIMBER: Des meets {{meet{i}}}") for i in (1, 2))
    a, b = (c["name"] for c in k["climbers"])
    assert f"ONLY {a} is met" in first and f"{b} is met in the next" in first and f"{a}, met already" in second


def test_the_result_once_aired_is_the_towns_talk_the_next_day(channel, monkeypatch):
    from datetime import date, timedelta

    from newsroom import player, talk

    w = _town()
    _stub(monkeypatch, _booking())
    k = hs.commission(w)
    assert player.AIRED_HOOKS[hs.SHOW] is hs.aired
    tomorrow = date.fromisoformat(w.last_date) + timedelta(days=1)
    hs.aired(Segment(slot_id=9, type=T.interview, show=hs.SHOW, brief="{spring}", target_s=100), w)
    assert not k.get("result_aired") and talk.highwater(w, tomorrow) is None     # the result never went out
    hs.aired(Segment(slot_id=10, type=T.interview, show=hs.SHOW, brief="{close}", target_s=75), w)
    said = talk.highwater(w, tomorrow)
    assert k["result_aired"] and said.startswith("High Water, the gameshow on Channel 8")
    assert all(x["who"] in said for x in k["game"]["results"]) and said in talk.line(w, tomorrow)
    assert talk.highwater(w, date.fromisoformat(w.last_date)) is None             # tonight's: not yet, as the town knows
