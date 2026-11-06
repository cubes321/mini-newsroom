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

    def render(self, prompt, seed):
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
    yield tmp_path / "pictures"
    object.__setattr__(CONFIG, "paths", old_paths)
    object.__setattr__(CONFIG, "pictures", old_pics)


def _seg(type_=T.bulletin, show="news", headline="Gorse fire out behind the Salting", thread=None, **kw):
    return Segment(slot_id=1, type=type_, show=show, headline=headline, thread_id=thread, nominal_start_ts=AT,
                   lines=[Line(speaker="anchor", text="Hello.")], **kw)


def test_a_story_gets_one_picture_by_its_thread_and_a_piece_by_its_headline():
    w = world_mod.seed()
    t = w.seed_thread("Stray firework sets gorse alight behind the Salting", "crews on it", "", [])
    req = pictures.request_for(_seg(thread=t.id), w)
    assert req.key == t.id and req.subject == t.title and req.day == "2026-11-06" and req.serious
    feature = pictures.request_for(_seg(T.feature, "magazine", "Dev's parkin gets a bonfire name"), w)
    assert feature.key == "magazine|dev-s-parkin-gets-a-bonfire-name" and not feature.serious
    assert "No text anywhere" in feature.prompt and "pixel art" in feature.prompt
    story_time = pictures.request_for(_seg(T.links, "rockpool", "The mermaid of Gull Rock"), w)
    assert "children's television" in story_time.prompt
    inquiry = pictures.request_for(_seg(T.interview, "inquiry", "Who signed off the harbour wall?"), w)
    assert inquiry.key == "inquiry|who-signed-off-the-harbour-wall"                # every show, in shadow mode
    assert pictures.request_for(_seg(T.feature, "magazine", "Bonfire guys", thread=t.id), w).key == t.id
    for none in (_seg(T.vox_pop, "magazine"), _seg(T.weather), _seg(T.links, "magazine"), _seg(repeat=True),
                 _seg(fallback=True), _seg(T.feature, "magazine", part="open"), _seg(T.bumper),
                 _seg(T.feature, "overnight")):
        assert pictures.request_for(none, w) is None, none.type


def test_a_key_is_offered_once_a_day_and_the_day_has_a_cap(store):
    p = pictures.Painter(FakeComfy(), gpu=lambda: 15.0)
    w = world_mod.seed()
    assert p.offer(pictures.request_for(_seg(headline="One"), w))
    assert not p.offer(pictures.request_for(_seg(headline="One"), w))           # the same piece again
    assert p.offer(pictures.request_for(_seg(headline="Two"), w))
    assert p.offer(pictures.request_for(_seg(headline="Three"), w))
    assert not p.offer(pictures.request_for(_seg(headline="Four"), w))          # per_day = 3


def test_the_painter_waits_for_comfyui_someone_elses_job_and_a_full_gpu(store):
    w = world_mod.seed()
    for client, gpu, why in ((FakeComfy(up=False), 15.0, "isn't up"), (FakeComfy(busy=True), 15.0, "busy"),
                             (FakeComfy(), 4.0, "GPU has 4.0 GB")):
        p = pictures.Painter(client, gpu=lambda g=gpu: g)
        p.offer(pictures.request_for(_seg(), w))
        assert not p.step() and why in p.last_said
        assert client.rendered == [] and p.q.qsize() == 1                     # still waiting, not dropped
    warm = pictures.Painter(FakeComfy(), gpu=lambda: 4.0)
    warm.warm = True                                                           # our own models fill the card
    warm.offer(pictures.request_for(_seg(), w))
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
