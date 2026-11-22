"""ComfyUI pictures in shadow mode: which segments get one, and the painter's manners on a shared GPU.

No ComfyUI: a fake client stands in, and the painter is stepped by hand, never started as a thread.
"""
from __future__ import annotations

import dataclasses
import io
import queue
from datetime import datetime

import pygame
import pytest

from newsroom import pictures, world as world_mod
from newsroom.config import CONFIG
from newsroom.models import Line, Segment, SegmentType as T

AT = datetime(2026, 11, 6, 19, 30).timestamp()
REAL_BRIEF = pictures.brief_for                  # the store fixture stands a blank brief in for it


def _png(colour=(40, 90, 160)) -> bytes:
    s = pygame.Surface((pictures.WIDTH, pictures.HEIGHT))
    s.fill(colour)
    pygame.draw.circle(s, (240, 200, 60), (700, 160), 90)
    buf = io.BytesIO()
    pygame.image.save(s, buf, "x.png")
    return buf.getvalue()


class FakeComfy:
    def __init__(self, up=True, busy=False, fail=False):
        self.is_up, self.is_busy, self.fail = up, busy, fail
        self.rendered: list[str] = []
        self.freed = 0

    def up(self):
        return self.is_up

    def busy(self):
        return self.is_busy

    def render(self, prompt, seed, model="z_image"):
        if self.fail:
            raise RuntimeError("out of memory")
        self.rendered.append(prompt)
        return _png()

    def free(self):
        self.freed += 1


@pytest.fixture
def store(tmp_path, monkeypatch):
    old_paths, old_pics = CONFIG.paths, CONFIG.pictures
    object.__setattr__(CONFIG, "paths", dataclasses.replace(old_paths, pictures=tmp_path / "pictures"))
    object.__setattr__(CONFIG, "pictures", dataclasses.replace(old_pics, poll_s=0.01, wait_s=0.0, per_day=3,
                                                               queue_max=3, idle_free_s=0.0))
    monkeypatch.setattr(pictures, "brief_for", lambda req: "")                # no LLM: the headline prompt
    yield tmp_path / "pictures"
    object.__setattr__(CONFIG, "paths", old_paths)
    object.__setattr__(CONFIG, "pictures", old_pics)


def _seg(type_=T.bulletin, show="news", headline="Gorse fire out behind the Salting", thread=None, lines=None,
         at=AT, **kw):
    return Segment(slot_id=1, type=type_, show=show, headline=headline, thread_id=thread, nominal_start_ts=at,
                   lines=lines or [Line(speaker="anchor", text="Hello.")], **kw)


def test_a_story_gets_one_picture_by_its_thread_and_a_piece_by_its_headline():
    w = world_mod.seed()
    t = w.seed_thread("Stray firework sets gorse alight behind the Salting", "crews on it", "", [])
    req = pictures.request_for(_seg(thread=t.id), w)
    assert req.key == t.id and req.subject == t.title and req.day == "2026-11-06" and req.serious
    feature = pictures.request_for(_seg(T.feature, "magazine", "Dev's parkin gets a bonfire name"), w)
    assert feature.key == "magazine|dev-s-parkin-gets-a-bonfire-name" and not feature.serious
    assert feature.prompt.startswith("A close view of what this story is about: Dev's parkin")   # the subject leads
    assert "wordless" in feature.prompt and "pixel art" in feature.prompt
    assert not any(w in pictures.RULES.lower() for w in ("letter", "sign", "logo", "text"))   # cfg 1 draws the nouns
    story_time = pictures.request_for(_seg(T.links, "rockpool", "The mermaid of Gull Rock"), w)
    assert "children's television" in story_time.prompt
    inquiry = pictures.request_for(_seg(T.interview, "inquiry", "Who signed off the harbour wall?"), w)
    assert inquiry.key == "inquiry|who-signed-off-the-harbour-wall"                # every show, in shadow mode
    assert pictures.request_for(_seg(T.feature, "magazine", "Bonfire guys", thread=t.id), w).key == t.id
    for none in (_seg(T.vox_pop, "magazine"), _seg(T.weather), _seg(T.links, "magazine"), _seg(repeat=True),
                 _seg(fallback=True), _seg(T.feature, "magazine", part="open"), _seg(T.bumper),
                 _seg(T.feature, "overnight"), _seg(T.sofa, "breakfast", "Presenters' crater cake")):
        assert pictures.request_for(none, w) is None, none.type


def test_a_key_is_offered_once_a_day_and_the_day_has_a_cap(store):
    p = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)
    w = world_mod.seed()
    assert p.offer(pictures.request_for(_seg(headline="One"), w))
    assert not p.offer(pictures.request_for(_seg(headline="One"), w))           # the same piece again
    assert p.offer(pictures.request_for(_seg(headline="Two"), w))
    assert p.offer(pictures.request_for(_seg(headline="Three"), w))
    assert not p.offer(pictures.request_for(_seg(headline="Four"), w))          # per_day = 3


def test_a_reworded_headline_is_the_same_picture(store):
    """The 2026-11-08 morning: Breakfast reworded its Remembrance bulletin every time, and each got a picture."""
    p = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)
    w = world_mod.seed()
    first = pictures.request_for(_seg(show="breakfast", headline="Remembrance Sunday Parade and Lifeboat Wreath Today"), w)
    assert p.offer(first)
    for again in ("Remembrance Parade and Lifeboat Wreath This Morning", "Remembrance Sunday Parade and Wreath Today"):
        assert not p.offer(pictures.request_for(_seg(show="breakfast", headline=again), w)), again
    t = w.seed_thread("Lifeboat crew lay Remembrance wreath on the harbour water", "laid at nine", "", [])
    assert not p.offer(pictures.request_for(_seg(headline="Wreath laid", thread=t.id), w))   # a split thread's title
    assert p.offer(pictures.request_for(_seg(show="breakfast", headline="Ruby Tennant Rows Twelve Hours for the Lifeboat Fund"), w))
    assert p.step() and p.step()
    restarted = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)                # a restart knows the day's headlines
    assert not restarted.offer(pictures.request_for(_seg(show="news", headline="Remembrance Sunday parade and lifeboat wreath this morning"), w))
    assert restarted.offer(pictures.request_for(_seg(headline="Fire Station Engine Bid Waits on Council Vote"), w))


def test_a_bulletin_leading_on_another_story_paints_its_own_thread(store, monkeypatch):
    """The 11-21 night: a bulletin headlined on the Tides' win was filed under t641, Gordon Lark booking a back
    room, and its brief painted a football match under Gordon's key."""
    from newsroom import llm
    from newsroom.models import PictureBrief
    w = world_mod.seed()
    t = w.seed_thread("Gordon Lark Books the Back Room Behind the Railway", "his three new minutes went down well", "", [])
    lines = [Line(speaker="anchor", text="The Tides beat Saltby Rovers three-one at home this afternoon. "
                                         "And Gordon Lark has been busy. He wants a back room behind the Railway "
                                         "for a January night.")]
    req = pictures.request_for(_seg(headline="Tides Beat Saltby Three-One; Darts Team Win at Home", thread=t.id,
                                    lines=lines), w)
    assert req.mixed and req.key == t.id
    assert "Gordon Lark" in req.context and "Saltby" not in req.context        # only the story's own sentences
    asked = []
    monkeypatch.setattr(llm, "complete_json", lambda task, schema, system, user, **k:
                        asked.append(user) or PictureBrief(picture="A small pub back room with a wooden stage."))
    REAL_BRIEF(req)
    assert "Tides" not in asked[0] and f"Story: {t.title}" in asked[0]
    # A reworded headline of the story itself is not mixed, and keeps its script.
    same = pictures.request_for(_seg(headline="Gordon Lark books a back room at the Railway", thread=t.id, lines=lines), w)
    assert not same.mixed and "Saltby" in same.context
    # The repeat check: the Tides' own picture doesn't turn away the stories a Tides-led bulletin carries.
    p = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)
    assert p.offer(pictures.request_for(_seg(T.sport, "news", "Tides Beat Saltby Three-One at Home"), w))
    assert p.offer(req)


def _seg_on(day: int, **kw):
    return _seg(at=datetime(2026, 11, day, 19, 30).timestamp(), **kw)


def test_a_story_keeps_its_picture_for_a_week_and_every_request_knows_which_picture_it_shows(store):
    w = world_mod.seed()
    t = w.seed_thread("Hake Glut Softens the Quay Price", "ten boats out", "", [])
    p = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)
    assert p.offer(pictures.request_for(_seg_on(10, headline="Hake glut on the quay", thread=t.id), w)) and p.step()
    made_on_10 = pictures.picture_for(t.id, "2026-11-10")
    assert made_on_10 and made_on_10.exists()
    # Two days on, and again the same day: no new picture, one alias, and the lookup finds the 10th's.
    restarted = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)              # it reads the index, not memory
    for _ in range(2):
        assert not restarted.offer(pictures.request_for(_seg_on(12, headline="Hake price eases", thread=t.id), w))
    [alias] = pictures.aliases("2026-11-12")
    assert alias["why"] == "story" and alias["to_day"] == "2026-11-10" and alias["to_key"] == t.id
    assert pictures.picture_for(t.id, "2026-11-12") == made_on_10
    # Past reuse_days, or with it off, the story gets a new picture.
    assert restarted.offer(pictures.request_for(_seg_on(18, headline="Hake price eases", thread=t.id), w))
    object.__setattr__(CONFIG, "pictures", dataclasses.replace(CONFIG.pictures, reuse_days=0))
    assert pictures.Painter(FakeComfy(), gpu=lambda: 15.0).offer(
        pictures.request_for(_seg_on(11, headline="Hake price eases", thread=t.id), w))
    # A reworded headline shows today's picture; one never made shows nothing.
    reworded = pictures.request_for(_seg_on(12, show="breakfast", headline="Remembrance Parade and Lifeboat Wreath Today"), w)
    assert restarted.offer(reworded)
    again = pictures.request_for(_seg_on(12, show="breakfast", headline="Remembrance Parade and Lifeboat Wreath This Morning"), w)
    assert not restarted.offer(again)
    assert pictures.aliases("2026-11-12")[-1]["to_key"] == reworded.key
    assert pictures.picture_for(again.key, "2026-11-12") is None              # queued, not made yet
    restarted.step(), restarted.step()
    assert pictures.picture_for(again.key, "2026-11-12") == pictures.picture_for(reworded.key, "2026-11-12")
    assert pictures.picture_for("nothing|at-all", "2026-11-12") is None


def test_a_picture_made_for_a_bulletin_led_by_another_story_is_not_kept(store):
    """Before 2acebe6, t641's picture was the Tides' football match: it mustn't stand for Gordon all week."""
    w = world_mod.seed()
    t = w.seed_thread("Gordon Lark Books the Back Room Behind the Railway", "three new minutes", "", [])
    old = pictures.request_for(_seg_on(10, headline="Tides Beat Saltby Three-One; Darts Team Win", thread=t.id), w)
    old.mixed = False                                                         # as the index has it from before
    p = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)
    assert p.offer(old) and p.step()
    later = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)
    assert later.offer(pictures.request_for(_seg_on(11, headline="Gordon Lark books the back room", thread=t.id), w))


def test_a_big_tide_is_high_water_not_a_wave():
    assert "not a wave" in pictures.BRIEF_SYSTEM and "storm or a gale" in pictures.BRIEF_SYSTEM


def test_the_painter_waits_for_comfyui_someone_elses_job_and_a_full_gpu(store):
    w = world_mod.seed()
    for client, gpu, why in ((FakeComfy(up=False), 15.0, "isn't up"), (FakeComfy(busy=True), 15.0, "busy"),
                             (FakeComfy(), 4.0, "GPU has 4.0 GB")):            # still full after the one /free
        p = pictures.Painter(client, gpu=lambda g=gpu: g)
        p.offer(pictures.request_for(_seg(), w))
        assert not p.step() and why in p.last_said
        assert client.rendered == [] and p.q.qsize() == 1                     # still waiting, not dropped
    leftover = FakeComfy()                                                     # our models from before a restart
    readings = iter([4.0, 15.0])
    p = pictures.Painter(leftover, gpu=lambda: next(readings))
    p.offer(pictures.request_for(_seg(), w))
    assert p.step() and leftover.freed == 1                                    # one /free, then it renders
    warm = pictures.Painter(FakeComfy(), gpu=lambda: 4.0)
    warm.warm = True                                                           # our own models fill the card
    warm.offer(pictures.request_for(_seg(headline="Another story"), w))
    assert warm.step()


def test_a_picture_is_stored_indexed_and_then_the_models_are_freed_when_idle(store):
    client = FakeComfy()
    p = pictures.Painter(client, gpu=lambda: 15.0)
    w = world_mod.seed()
    p.offer(pictures.request_for(_seg(headline="Gorse fire out"), w))
    assert p.step()
    [row] = pictures.made("2026-11-06")
    assert (store / row.file).read_bytes()[:4] == b"\x89PNG" and row.seconds >= 0 and row.ts
    assert pictures.Painter(client, gpu=lambda: 15.0)._keys("2026-11-06") == {row.key}   # a restart knows it
    assert not p.step() and client.freed == 1 and not p.warm                  # nothing waiting: unloaded


def test_a_failed_picture_is_skipped_and_nothing_is_stored(store):
    p = pictures.Painter(FakeComfy(fail=True), gpu=lambda: 15.0)
    p.offer(pictures.request_for(_seg(), world_mod.seed()))
    assert not p.step() and "failed" in p.last_said and pictures.made() == []


def test_offer_does_nothing_with_pictures_off_and_never_blocks(store, monkeypatch):
    monkeypatch.setattr(pictures, "_painter", None)
    pictures.offer(_seg(), world_mod.seed())                                   # off: no painter, no error
    p = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)
    p.q = queue.Queue(maxsize=1)
    monkeypatch.setattr(pictures, "_painter", p)
    w = world_mod.seed()
    pictures.offer(_seg(headline="A"), w)
    pictures.offer(_seg(headline="B"), w)                                      # queue full: dropped, not waited on
    assert p.q.qsize() == 1


def test_the_graph_is_z_image_turbo_with_the_prompt_and_seed():
    g = pictures.graph("a lighthouse", 7)
    assert g["4"]["inputs"]["text"] == "a lighthouse" and g["7"]["inputs"]["seed"] == 7
    assert g["1"]["inputs"]["unet_name"] == "z_image_turbo_bf16.safetensors"
    assert (g["6"]["inputs"]["width"], g["6"]["inputs"]["height"]) == (1024, 576)


def test_the_contact_sheet_shows_each_picture_full_and_in_the_screen_boxes(store):
    p = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)
    w = world_mod.seed()
    for h in ("Gorse fire out", "Dev's parkin"):
        p.offer(pictures.request_for(_seg(headline=h), w))
        p.step()
    [page] = pictures.sheet("2026-11-06", store / "sheet.png")
    img = pygame.image.load(str(page))
    assert img.get_width() > 1000 and img.get_height() > 250


def test_a_nights_model_can_be_chosen_and_an_unknown_one_falls_back(monkeypatch):
    monkeypatch.setenv("NEWSROOM_PICTURES_MODEL", "qwen_image_cfg")
    assert pictures.model() == "qwen_image_cfg"
    g = pictures.GRAPHS["qwen_image_cfg"]("x", 1)
    assert g["7"]["inputs"]["cfg"] == 2.5 and "11" not in g and "Disney" in g["5"]["inputs"]["text"]
    assert "11" in pictures.GRAPHS["qwen_image"]("x", 1)                         # the Lightning LoRA
    monkeypatch.setenv("NEWSROOM_PICTURES_MODEL", "sdxl")
    assert pictures.model() == "z_image"


def test_the_brief_says_what_to_draw_once_the_gates_pass_and_the_headline_stands_in_without_it(store):
    w = world_mod.seed()
    asked = []

    def brief(req):
        asked.append(req)
        return "A tray of dark, sticky ginger cake cut into squares on a bakery counter."
    client = FakeComfy(busy=True)
    p = pictures.Painter(client, gpu=lambda: 15.0, brief=brief)
    seg = _seg(T.feature, "magazine", "Dev's parkin gets a bonfire name",
               lines=[Line(speaker="anchor", text="Dev bakes his parkin every November.")])
    p.offer(pictures.request_for(seg, w))
    assert not p.step() and asked == []                                       # waiting: no call spent
    client.is_busy = False
    assert p.step() and len(asked) == 1 and "Dev bakes his parkin" in asked[0].context
    [row] = pictures.made("2026-11-06")
    assert row.brief.startswith("A tray of dark")
    assert row.prompt.startswith("A close view of what this story is about: A tray of dark, sticky ginger cake")
    assert "pixel art" in row.prompt and "wordless" in row.prompt                # the style and rules stay
    p = pictures.Painter(FakeComfy(), gpu=lambda: 15.0, brief=lambda req: 1 / 0)    # a brief that trips
    p.offer(pictures.request_for(_seg(headline="Gorse fire out"), w))
    assert p.step()
    row = pictures.made("2026-11-06")[-1]
    assert row.brief == "" and "about: Gorse fire out" in row.prompt             # the headline, still made


def test_a_brief_naming_something_written_is_set_aside(monkeypatch):
    from newsroom import llm
    from newsroom.models import PictureBrief
    req = pictures.request_for(_seg(T.feature, "magazine", "New cafe opens on the quay"), world_mod.seed())
    for said, kept in (("A steaming teapot and scones on a gingham table by a harbour window.", True),
                       ("A cafe with a chalkboard menu by the door and a sign over it.", False),
                       ("A shopfront whose banner reads GRAND OPENING.", False)):
        monkeypatch.setattr(llm, "complete_json", lambda *a, said=said, **k: PictureBrief(picture=said))
        assert (pictures.brief_for(req) == said) is kept, said
    monkeypatch.setattr(llm, "complete_json", lambda *a, **k: (_ for _ in ()).throw(llm.LLMError("down")))
    assert pictures.brief_for(req) == ""                                      # the call failed: no brief


def test_a_brief_naming_writing_or_the_studio_is_asked_for_again(monkeypatch):
    """On the 11-06 night the twelve headline-only pictures were the ones with words in them, and 18 briefs drew
    the programme itself (two presenters on a sofa) instead of what it was about."""
    from newsroom import llm
    from newsroom.models import PictureBrief
    req = pictures.request_for(_seg(T.interview, "breakfast", "Viewer asks why the Town Hall clock keeps stopping"),
                               world_mod.seed())
    for first in ("Two presenters sit on a bright sofa in a cosy studio with mugs of tea.",
                  "A shop window with a hand-painted sign above the door on Harrow Street."):
        said = iter([first, "A tall stone clock tower over a quiet harbour at dawn, its hands stopped."])
        asked = []
        monkeypatch.setattr(llm, "complete_json",
                            lambda task, schema, system, user, **k: asked.append(user) or PictureBrief(picture=next(said)))
        assert pictures.brief_for(req).startswith("A tall stone clock tower")
        assert len(asked) == 2 and "Say it again" in asked[1] and first in asked[1]


def test_football_is_soccer_and_the_tides_are_a_club():
    assert pictures._soccer("A large bright football beside a football pitch") == \
        "A large bright round soccer ball beside a soccer pitch"
    assert "the Tides are the football (soccer) club" in pictures.BRIEF_SYSTEM
    assert "ginger" not in pictures.BRIEF_SYSTEM                      # its example was copied three times
    assert "faces on objects" in pictures.QWEN_NEGATIVE
    req = pictures.Request(key="k", day="d", show="news", kind="sport", headline="h", subject="h",
                           brief="A football on wet grass")
    assert "round soccer ball on wet grass" in pictures.prompt_for(req)


def test_a_panel_item_gets_its_questions_story_and_a_round_on_several_things_none():
    w = world_mod.seed()
    t = w.seed_thread("Fender costs and the auction", "the crane is rebooked for the 17th", "", [])
    w.panels = [{"date": w.last_date, "questions": [{"question": "Pay now?", "thread_id": None},
                                                    {"question": "Move the auction?", "thread_id": t.id}]}]
    lines = [Line(speaker="anchor", text="Everyone's talking about bunting, boilers and the plaque.")]
    two = pictures.request_for(_seg(T.interview, "panel", "Auction on the Quay or moved?", lines=lines,
                                    brief="the SECOND question, {q2}: each answers"), w)
    assert two.key == t.id and two.subject == t.title and "bunting" not in two.context
    assert "rebooked for the 17th" in two.context
    for brief in ("the FIRST question, {q1}", "quick fire: one line each on the week's stories", ""):
        assert pictures.request_for(_seg(T.interview, "panel", "Quick fire", brief=brief), w) is None
