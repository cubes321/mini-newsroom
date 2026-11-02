"""Out and About: Meg Trethewey on location at 15:00, and reviews with stars the town remembers.
The model is stubbed: no network."""
from __future__ import annotations

import time
from datetime import date, timedelta

import pygame

from newsroom import outabout, schedule, world as world_mod, writers
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentType as T, script_schema
from newsroom.player import Player


def _town():
    w = world_mod.seed()
    w.threads = []
    w.update_thread(None, "Harbour wall report due Friday", "so far")
    return w


def _review(w, **kw):
    schema = script_schema(T.review, schedule.get("outabout").cast_for(T.review))
    return schema.model_validate({
        "headline": "The Gull's Rest: four stars for the crab", "lower_third": "The review",
        "place": "The Gull's Rest", "kind": "cafe", "where": "Saltby green", "location": "Saltby village green",
        "backdrop": "village", "stars": 4, "verdict": "Worth the walk for the crab alone",
        "guest_name": "Dolores Finch", "guest_role": "owner, the Gull's Rest", "guest_gender": "f",
        "guest_memory": "bakes her own bread at five every morning",
        "lines": [{"speaker": "travel", "text": "A crab sandwich and a pot of tea, seven pounds."},
                  {"speaker": "guest", "text": "The crab came in this morning, Meg."},
                  {"speaker": "travel", "text": "Four stars: worth the walk for the crab alone."}], **kw})


def test_meg_is_a_presenter_with_a_voice_nobody_else_has():
    w = world_mod.seed()
    meg = w.character("travel")
    assert meg.name == "Meg Trethewey" and meg.voice == "bf_trethewey" and meg.lang == "b"
    assert meg.voice not in world_mod.GUEST_VOICES and all(p.voice != meg.voice for p in w.people)
    saved = world_mod._to_dict(w)
    saved["characters"] = [c for c in saved["characters"] if c["id"] != "travel"]   # a world from before her
    assert world_mod._from_dict(saved).character("travel").name == "Meg Trethewey"


def test_it_airs_from_three_to_quarter_to_four():
    lt = time.localtime()
    at = time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 15, 20, 0, 0, 0, -1))
    assert schedule.show_at(at).id == "outabout"
    assert time.localtime(schedule.show_end(at))[3:5] == (15, 45)


def test_a_review_is_remembered_and_opens_no_story(monkeypatch):
    w = _town()
    threads = len(w.threads)
    monkeypatch.setattr(writers.llm, "complete_json", lambda *a, **k: _review(w))
    seg = Segment(slot_id=3, type=T.review, show="outabout", target_s=120)
    writers.script_segment(seg, w)
    assert seg.work["review"]["stars"] == 4 and seg.work["review"]["place"] == "The Gull's Rest"
    assert w.reviews[-1]["owner"] == "Dolores Finch" and w.reviews[-1]["date"] == w.last_date
    assert len(w.threads) == threads and seg.thread_id is None
    assert w.person_by_name("Dolores Finch").memories[-1]["said"] == "bakes her own bread at five every morning"


def test_the_verdict_leaves_the_stars_to_the_card():
    w = _town()
    assert _review(w, verdict="Four stars: a proper walkers' stop").verdict == "A proper walkers' stop"
    assert _review(w, verdict="3 stars out of five - lovely").verdict == "Lovely"
    assert _review(w, verdict="Worth the walk").verdict == "Worth the walk"


def test_a_place_rests_a_fortnight_then_may_be_revisited():
    w = _town()
    old = (date.fromisoformat(w.last_date) - timedelta(days=20)).isoformat()
    w.reviews = [{"date": old, "place": "The Anchor", "kind": "pub", "where": "the quay", "stars": 2,
                  "verdict": "Cold chips", "owner": ""},
                 {"date": w.last_date, "place": "The Gull's Rest", "kind": "cafe", "where": "Saltby", "stars": 4,
                  "verdict": "Worth the walk", "owner": "Dolores Finch"}]
    brief = outabout.for_prompt(w)
    assert ": not The Gull's Rest;" in brief and "The Anchor (pub, the quay): 2 out of 5" in brief
    assert "not The Anchor" not in brief
    w.reviews += [dict(w.reviews[1], place=f"Cafe {n}") for n in range(9)]   # an afternoon's worth more
    assert "The Gull's Rest" in outabout.for_prompt(w).split("):")[0]       # still resting, though not shown


def test_an_owner_may_answer_back_on_coastwide_and_not_on_the_news():
    w = _town()
    w.reviews = [{"date": w.last_date, "place": "The Anchor", "kind": "pub", "where": "the quay", "stars": 2,
                  "verdict": "Cold chips", "owner": ""}]
    _, coastwide = writers.build_prompt(T.interview, w, target_s=120, show=schedule.get("magazine"))
    _, news = writers.build_prompt(T.interview, w, target_s=90, show=schedule.get("news"))
    assert "OUT AND ABOUT'S RECENT REVIEWS" in coastwide and "The Anchor" in coastwide
    assert "OUT AND ABOUT'S RECENT REVIEWS" not in news


def test_megs_pieces_are_not_the_news(monkeypatch):
    w = _town()
    t = w.threads[0]
    t.breaking, t.breaking_ts = w.last_date, schedule.now() - 60        # a story broke a minute ago
    monkeypatch.setattr(writers, "scene_due", lambda *a: t.id)
    seen = []

    def complete_json(task, schema, system, user, **kw):
        seen.append(user)
        raise writers.llm.LLMError("stub")
    monkeypatch.setattr(writers.llm, "complete_json", complete_json)
    seg = Segment(slot_id=2, type=T.field_report, show="outabout", target_s=60, brief="the walk for the weekend")
    writers.script_segment(seg, w)
    user = seen[0]
    assert "scene" not in seg.work and "FROM THE SCENE" not in user and "MILES" not in user
    assert "BIG RUNNING STORY" not in user and "PLACES MEG HAS REVIEWED" in user and "TIDE" in user.upper()
    assert {l.speaker for l in seg.lines} == {"travel"}                 # the canned piece: Meg alone


def test_every_canned_piece_is_meg_alone(monkeypatch):
    w = _town()
    monkeypatch.setattr(writers.llm, "complete_json",
                        lambda *a, **k: (_ for _ in ()).throw(writers.llm.LLMError("down")))
    for k, kind in enumerate((T.field_report, T.feature, T.review, T.vox_pop)):
        seg = Segment(slot_id=10 + k, type=kind, show="outabout", target_s=60)
        writers.script_segment(seg, w)
        assert "reporter" not in {l.speaker for l in seg.lines} and seg.lines[0].speaker == "travel"
    assert w.reviews == []                                               # a canned review isn't remembered


def _on_air(w, idx):
    pl = Player(Buffer(), w, producer=None, audio=False)
    seg = Segment(slot_id=6, type=T.review, show="outabout", target_s=120,
                  work={"review": {"place": "The Gull's Rest", "stars": 4, "verdict": "Worth the walk"}},
                  cues=writers._cues_for(Segment(slot_id=0, type=T.review), _review(w)),
                  lines=[Line(speaker="travel", text="Crab.", duration_s=2.0, mouth_env=[0.5] * 40),
                         Line(speaker="guest", text="Fresh.", guest_name="Dolores Finch", duration_s=2.0,
                              mouth_env=[0.5] * 40),
                         Line(speaker="travel", text="Four stars.", duration_s=2.0, mouth_env=[0.5] * 40)])
    pl.current, pl.line_idx = seg, idx
    pl.seg_start = pl.line_start = schedule.now() - 0.5
    return pl


def test_meg_is_on_location_and_the_stars_go_up_on_her_last_line():
    w = _town()
    v = _on_air(w, 0).view()
    assert v.mode == "field" and v.reporter == "travel" and v.tag == "REVIEW" and v.backdrop == "village"
    assert v.verdict is None
    v = _on_air(w, 2).view()
    assert v.verdict == {"place": "The Gull's Rest", "stars": 4, "verdict": "Worth the walk"}


def test_the_verdict_card_shows_the_stars():
    from newsroom import scenes

    pygame.font.init()
    w = _town()
    canvas = pygame.Surface(scenes.CANVAS)
    scenes.render(canvas, _on_air(w, 2).view(), 1.0)
    box = scenes.VERDICT_CARD
    star = lambda k: canvas.get_at((box.x + 24 + k * 22, box.y + 24))[:3]      # each star's centre
    assert [star(k) for k in range(5)] == [scenes.STAR_GOLD] * 4 + [scenes.STAR_EMPTY]


def test_a_review_is_indoors_where_the_place_is():
    assert outabout.backdrop_for("cafe", "village") == "tea_room"
    assert outabout.backdrop_for("Tea Room", "seafront") == "tea_room"
    assert outabout.backdrop_for("bakery", "main_street") == "tea_room"
    assert outabout.backdrop_for("pub", "village") == "dining_room"          # supper, not the darts pub
    assert outabout.backdrop_for("restaurant", "harbour") == "dining_room"
    assert outabout.backdrop_for("play", "village") == "village_hall"
    assert outabout.backdrop_for("music night", "village") == "village_hall"
    assert outabout.backdrop_for("takeaway", "seafront") == "seafront"       # anything else: the writer's pick
    assert outabout.backdrop_for("gallery", "main_street") == "main_street"
    assert outabout.backdrop_for("public garden", "park") == "park"            # a word inside a word isn't one
    assert outabout.backdrop_for("playground", "park") == "park"
    assert outabout.backdrop_for("car showroom", "main_street") == "main_street"
    from newsroom import backdrops, locations
    for _, bid in outabout.INTERIORS:
        assert bid in locations.BACKDROP_IDS and locations.BY_ID[bid].interior and backdrops.has_art(bid)


def test_the_review_goes_indoors_whatever_the_model_or_the_template_picked(monkeypatch):
    w = _town()
    for kind, picked, want in (("cafe", "village", "tea_room"), ("pub", "harbour", "dining_room"),
                               ("takeaway", "seafront", "seafront")):
        monkeypatch.setattr(writers.llm, "complete_json",
                            lambda *a, k=kind, b=picked, **kw: _review(w, kind=k, backdrop=b, place=f"The {k}"))
        seg = Segment(slot_id=4, type=T.review, show="outabout", target_s=120)
        writers.script_segment(seg, w)
        assert [c.payload["backdrop"] for c in seg.cues if c.kind == "backdrop"] == [want], kind
    monkeypatch.setattr(writers.llm, "complete_json",
                        lambda *a, **k: (_ for _ in ()).throw(writers.llm.LLMError("down")))
    seg = Segment(slot_id=5, type=T.review, show="outabout", target_s=120)
    writers.script_segment(seg, w)                                         # the canned tea room on the seafront
    assert [c.payload["backdrop"] for c in seg.cues if c.kind == "backdrop"] == ["tea_room"]
