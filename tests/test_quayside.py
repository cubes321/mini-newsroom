"""Quayside at 13:00: Howard Lanyon on the town's money, with the fish auction worked out in quay.py so
every show quotes the same figures."""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta

from newsroom import locations, quay, schedule, world as world_mod, writers
from newsroom.models import FieldReportScript, LiveLine, Segment, SegmentType as T

FRIDAY = datetime(2026, 10, 30, 13, 0)


def test_an_auction_is_the_same_every_time_and_only_on_weekdays():
    a, b = quay.auction(FRIDAY.date()), quay.auction(FRIDAY.date())
    assert a == b and a.lots and a.total > 0
    assert quay.auction(date(2026, 10, 31)) is None and quay.auction(date(2026, 11, 1)) is None
    assert quay.latest(datetime(2026, 11, 1, 13, 0)).day == FRIDAY.date()          # Sunday: Friday's
    assert quay.latest(datetime(2026, 10, 30, 7, 0)).day == date(2026, 10, 29)      # before the hammer


def test_a_rough_day_keeps_the_small_boats_in():
    rough = next(a for d in range(1, 200) if (a := quay.auction(date(2026, 1, 1) + timedelta(days=d))) and a.rough)
    assert not any(kind in quay.SMALL for _, _, kind in rough.boats)


def test_the_briefing_line_and_the_facts_agree():
    line, facts = quay.summary(FRIDAY), quay.for_prompt(FRIDAY)
    a = quay.latest(FRIDAY)
    top = a.lots[0]
    assert f"{top.species} earned most" in line and f"{top.kilos:,} kg" in line
    assert f"  - {top.species}: {top.kilos:,} kg" in facts and "never invent a price" in facts
    assert world_mod.QUAY_LABEL in world_mod.seed().summary_for_prompt() and "BACKGROUND" in world_mod.QUAY_LABEL


def test_quayside_is_at_one_with_howard_and_the_facts():
    lt = time.localtime()

    def at(h, m):
        return time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, h, m, 0, 0, 0, -1))
    assert schedule.show_at(at(13, 10)).id == "quayside" and schedule.show_end(at(13, 10)) == at(13, 30)
    assert schedule.show_at(at(13, 40)).id == "news"
    show = schedule.get("quayside")
    w = world_mod.seed()
    howard = w.character("business")
    assert howard.name == "Howard Lanyon" and howard.voice not in world_mod.GUEST_VOICES
    user = writers.build_prompt(T.field_report, w, target_s=100.0, show=show, at_ts=FRIDAY.timestamp())[1]
    assert "QUAY FACTS" in user and "Fish auction" not in user.split("QUAY FACTS")[0][-40:]
    assert show.cast_for(T.links) == ("business",) and "reporter" in show.cast_for(T.field_report)


def _report(backdrop, lead="business"):
    return FieldReportScript(
        lines=[LiveLine(speaker=lead, text="Miles is on the quay."),
               LiveLine(speaker="reporter", text="Eleven boats out, and bass fetched the most.")],
        headline="Bass tops the auction", location="the fish quay", backdrop=backdrop,
        lower_third="Miles Okafor on the fish quay", thread_id=None)


def _backdrop(seg):
    return next(c.payload["backdrop"] for c in seg.cues if c.kind == "backdrop")


def test_the_auction_report_is_on_the_fish_quay(monkeypatch):
    assert quay.BACKDROP in {loc.id for loc in locations.LOCATIONS}
    w = world_mod.seed()
    monkeypatch.setattr(writers.llm, "complete_json", lambda *a, **k: _report("harbour"))   # the model's own pick
    seg = Segment(slot_id=3, type=T.field_report, show="quayside", target_s=100.0, nominal_start_ts=FRIDAY.timestamp())
    writers.script_segment(seg, w)
    assert _backdrop(seg) == "fish_quay"

    def down(*a, **k):
        raise writers.llm.LLMError("no model")
    monkeypatch.setattr(writers.llm, "complete_json", down)                                 # the template too
    seg = Segment(slot_id=4, type=T.field_report, show="quayside", target_s=100.0, nominal_start_ts=FRIDAY.timestamp())
    writers.script_segment(seg, w)
    assert _backdrop(seg) == "fish_quay"


def test_with_no_model_miles_still_reports_the_auction(monkeypatch):
    def down(*a, **k):
        raise writers.llm.LLMError("no model")
    monkeypatch.setattr(writers.llm, "complete_json", down)
    sunday = datetime(2026, 11, 1, 13, 5)
    seg = Segment(slot_id=4, type=T.field_report, show="quayside", target_s=100.0, nominal_start_ts=sunday.timestamp())
    writers.script_segment(seg, world_mod.seed())
    a, said = quay.latest(sunday), " ".join(l.text for l in seg.lines)
    top = a.lots[0]
    assert a.day == FRIDAY.date() and "Friday's auction" in said and "this morning" not in said
    assert f"{top.kilos:,} kilos" in said and a.best_boat[0] in said and "cannery" not in said
    assert [l.speaker for l in seg.lines] == ["business", "reporter", "business"]
    assert top.species in seg.headline.lower()


def test_breaking_news_still_sends_miles_to_the_scene(monkeypatch):
    w = world_mod.seed()
    tid = w.update_thread(None, "Chandlery fire on the quay", "smoke reported, crews on the way")
    w.mark_breaking(tid, schedule.now() - 300)
    monkeypatch.setattr(writers.llm, "complete_json", lambda *a, **k: _report("loading_dock"))
    seg = Segment(slot_id=5, type=T.field_report, show="quayside", target_s=100.0, nominal_start_ts=schedule.now())
    writers.script_segment(seg, w)
    assert seg.work["scene"] == tid and _backdrop(seg) == "loading_dock"


def test_other_shows_choose_their_own_backdrop(monkeypatch):
    w = world_mod.seed()
    monkeypatch.setattr(writers.llm, "complete_json", lambda *a, **k: _report("harbour", "anchor"))
    seg = Segment(slot_id=6, type=T.field_report, show="news", target_s=90.0, nominal_start_ts=schedule.now())
    writers.script_segment(seg, w)
    assert _backdrop(seg) == "harbour"


def _news_bulletin(head):
    return {"headline": head, "lower_third": "News", "thread_id": None, "thread_status": None, "tip_used": None,
            "lines": [{"speaker": "anchor", "text": "Good evening."}, {"speaker": "anchor", "text": "More soon."}]}


def test_the_auction_is_news_once_then_background(monkeypatch):
    """2026-11-03: 76 of the night's 363 news items were the auction, "Ten boats in and fifteen thousand
    pounds on the quay" seven times. The first is news; then it leaves the news's briefing, and a
    bulletin that leads on it anyway is asked for another story."""
    monkeypatch.setattr(schedule, "now", lambda: FRIDAY.timestamp() + 8 * 3600)
    w = world_mod.seed()
    w.last_date = "2026-10-30"
    news = schedule.get("news")
    assert writers.quay.summary(FRIDAY)[:20] in writers.build_prompt(T.bulletin, w, target_s=75, show=news)[1]
    w.record_aired("bulletin", "Ten boats in and fifteen thousand pounds on the quay", None, "...", show="news")
    _, user = writers.build_prompt(T.bulletin, w, target_s=75, show=news)
    assert "the latest auction" not in user
    _, user = writers.build_prompt(T.links, w, target_s=45, show=schedule.get("quayside"))
    assert "the latest auction" in user                     # Quayside's own business
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return schema.model_validate(_news_bulletin("Ten boats land fifteen thousand pounds of fish" if len(asked) == 1
                                                    else "Bonfire stack climbs on the Salting"))
    monkeypatch.setattr(writers.llm, "complete_json", write)
    seg = Segment(slot_id=12, type=T.bulletin, show="news", target_s=75.0)
    writers.script_segment(seg, w)
    assert len(asked) == 2 and "NOT the fish auction" in asked[1] and seg.headline == "Bonfire stack climbs on the Salting"


def test_a_story_made_of_the_auction_leaves_the_news_too(monkeypatch):
    """2026-11-05: the desk opened t431 "Eleven boats out and steady prices at the quay". With the quay
    figures gone from the news's briefing, the story in its thread list (and the quiet stories offered
    to a field report) would have brought the auction straight back."""
    monkeypatch.setattr(schedule, "now", lambda: FRIDAY.timestamp() + 8 * 3600)
    w = world_mod.seed()
    w.last_date = "2026-10-30"
    for t in w.threads:
        t.phase = "closed"
    tid = w.update_thread(None, "Eleven boats out and steady prices at the quay", "the board held level")
    other = w.update_thread(None, "Bonfire stack climbs on the Salting", "gates open at six")
    news = schedule.get("news")
    assert tid in writers.build_prompt(T.field_report, w, target_s=75, show=news)[1]   # news until it's reported
    w.record_aired("bulletin", "Ten boats in and fifteen thousand pounds on the quay", None, "...", show="news")
    for kind in (T.bulletin, T.field_report):
        _, user = writers.build_prompt(kind, w, target_s=75, show=news)
        assert tid not in user and other in user, kind
    assert tid in writers.build_prompt(T.links, w, target_s=45, show=schedule.get("quayside"))[1]
    assert tid in {t.id for t in w.board_threads()}                  # still on the board for the other shows


def test_the_news_words_for_the_auction():
    for h in ("Ten boats in and fifteen thousand pounds on the quay", "Five Boats Out as Rough Sea Dents Quay Takings",
              "Fish quay sells fifteen thousand pounds as hake leads", "Rough sea keeps most boats in"):
        assert quay.about_the_auction(h), h
    for h in ("Lifeboat crew ready the wreath", "Bunting row on the quay", "Ferry boats return to the timetable"):
        assert not quay.about_the_auction(h), h


def test_the_quay_is_shut_on_christmas_day_boxing_day_and_new_years_day():
    """Christmas Day 2026 is a Friday: the news had "today's auction" to report, and teletext its prices."""
    assert quay.auction(date(2026, 12, 25)) is None and quay.auction(date(2027, 1, 1)) is None
    assert quay.auction(date(2026, 12, 24)) is not None and quay.auction(date(2026, 12, 28)) is not None
    assert quay.latest(datetime(2026, 12, 25, 13, 0)).day == date(2026, 12, 24)    # Christmas Eve's, still the latest
