"""Pictures made live by ComfyUI, in shadow mode: made in the back office, shown nowhere.

The user's idea (2026-11-03), decided 2026-11-04: for a few nights the station makes a picture for
the day's stories and every show's pieces, but nothing on screen shows them. Each night's go on a
contact sheet (`--sheet`) to judge how they would look and fit, and only then is it decided where
they show.

- One picture per story a day (by thread id), else one per piece (show and headline). The prompt is
  made here from the headline and the story's title, not by the writers: tonight's live scripts are
  untouched (the brainstorm had the writer name the picture; that can follow if these are good).
- It never holds anything up. `offer` drops a request on a queue and returns; one thread renders.
- Polite on the shared GPU: no render while ComfyUI has someone else's job queued, none from cold
  without the free memory for the model, `/free` once idle after rendering, a daily cap, and off
  unless `[pictures] enabled` or `--pictures`.

  python -m newsroom.pictures --try "a lighthouse at dusk"   one picture now, to check ComfyUI
  python -m newsroom.pictures --sheet [YYYY-MM-DD]           that day's contact sheet(s)
  python -m newsroom.pictures --status                       ComfyUI, the GPU and today's count
"""
from __future__ import annotations

import io
import json
import logging
import os
import queue
import re
import subprocess
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
import zlib
from dataclasses import asdict, dataclass
from datetime import date, datetime
from pathlib import Path

from .config import CONFIG
from .models import Segment, SegmentType as T

log = logging.getLogger(__name__)

WIDTH, HEIGHT = 1024, 576            # 16:9 at a multiple of 16; the screen boxes crop from it
# Every show while it's shadow mode: nothing airs, so the sheets can show what each would get (the user,
# 2026-11-06). The pieces with a subject; not the furniture, the weather, the vox pops or the chat.
TYPES = {T.bulletin, T.field_report, T.breaking, T.interview, T.feature, T.consumer, T.review, T.sofa,
         T.sport, T.call, T.monologue, T.documentary}
CHILDREN_LINKS = "rockpool"          # Rock Pool's links are its pieces (story time, the make); others are chat
SERIOUS = re.compile(r"\b(fire|blaze|crash|collision|accident|injur\w*|hurt|died|death|dead|body|police|arrest\w*|"
                     r"assault|missing|flood\w*|rescue\w*|sank|sinking)\b", re.I)

# The subject leads and the town is a short clause after the style: with the town first and in detail
# ("stone cottages, slate roofs and a harbour"), the first trial (2026-11-06) drew the same harbour
# panorama for Dev's parkin, a tailor and The Inquiry alike.
SUBJECT = ("A close view of what this story is about: {subject}. Show that thing itself, large and filling the "
           "picture: the objects, the room or the place, and the work going on there.")
STYLE = ("Detailed 16-bit pixel art, like a picture from a 1990s point-and-click adventure game: clean flat "
         "colours, crisp dark outlines, soft light. Set in a small fishing town on the English coast.")
CHILDREN = "Bright and friendly, for children's television."
# Worded without the things it rules out: at cfg 1 the negative is zeroed and the model follows nouns, so
# "no letters, no words on signs" drew signs with words on them (the second trial, 2026-11-06).
RULES = "A wordless picture, plain painted surfaces throughout. People have simple faces with no detail."


@dataclass
class Request:
    key: str                          # one picture per key a day: a thread id, or show|headline
    day: str                          # the broadcast date, YYYY-MM-DD
    show: str
    kind: str                         # the segment type
    headline: str
    thread: str = ""
    subject: str = ""                 # what the picture is of: the story's title, else the headline
    serious: bool = False             # a fire or an accident: the user decides whether these get pictures
    prompt: str = ""
    file: str = ""
    seconds: float = 0.0
    ts: float = 0.0


def enabled() -> bool:
    return CONFIG.pictures.enabled or os.environ.get("NEWSROOM_PICTURES") == "1"


def request_for(seg: Segment, world) -> Request | None:
    """What picture a freshly scripted segment would get, or None. Repeats, fallbacks and the
    furniture (bumpers, adverts, weather, vox pops, sport) get none."""
    if seg.repeat or seg.fallback or not seg.headline or not seg.lines:
        return None
    if seg.show == "overnight" or seg.part in ("open", "close") or not (
            seg.type in TYPES or (seg.type is T.links and seg.show == CHILDREN_LINKS)):
        return None
    thread = world.thread(seg.thread_id) if seg.thread_id else None
    day = date.fromtimestamp(seg.nominal_start_ts).isoformat()
    key = thread.id if thread else f"{seg.show}|{_slug(seg.headline)}"     # a story's picture, whichever show
    subject = thread.title if thread else seg.headline
    req = Request(key=key, day=day, show=seg.show, kind=seg.type.value, headline=seg.headline,
                  thread=thread.id if thread else "", subject=subject,
                  serious=bool(SERIOUS.search(f"{subject} {seg.headline}")))
    req.prompt = prompt_for(req)
    return req


def prompt_for(req: Request) -> str:
    return " ".join(p for p in (SUBJECT.format(subject=req.subject.rstrip(".")), STYLE,
                                CHILDREN if req.show == "rockpool" else "", RULES) if p)


def _slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60]


def _filename(key: str) -> str:
    return f"{_slug(key)}-{zlib.crc32(key.encode()) & 0xffff:04x}.png"


# ----------------------------------------------------------------- storage

def root() -> Path:
    return CONFIG.paths.pictures


def index_path() -> Path:
    return root() / "index.jsonl"


def made(day: str | None = None) -> list[Request]:
    """Everything made (on `day`, or ever), oldest first."""
    try:
        rows = [json.loads(l) for l in index_path().read_text(encoding="utf-8").splitlines() if l.strip()]
    except FileNotFoundError:
        return []
    return [Request(**r) for r in rows if day is None or r.get("day") == day]


def _store(req: Request, png: bytes) -> None:
    folder = root() / req.day
    folder.mkdir(parents=True, exist_ok=True)
    req.file = f"{req.day}/{_filename(req.key)}"
    (root() / req.file).write_bytes(png)
    with index_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(asdict(req)) + "\n")


# ----------------------------------------------------------------- ComfyUI

def graph(prompt: str, seed: int, width: int = WIDTH, height: int = HEIGHT) -> dict:
    """Z-Image Turbo, as in ComfyUI's own image_z_image_turbo workflow: Qwen3-4B text encoder, 9 steps at
    cfg 1 with res_multistep, the negative zeroed out. PreviewImage keeps it out of ComfyUI's output folder."""
    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": "z_image_turbo_bf16.safetensors", "weight_dtype": "default"}},
        "2": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["1", 0], "shift": 3}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": "qwen_3_4b.safetensors", "type": "lumina2", "device": "default"}},
        "4": {"class_type": "CLIPTextEncode", "inputs": {"clip": ["3", 0], "text": prompt}},
        "5": {"class_type": "ConditioningZeroOut", "inputs": {"conditioning": ["4", 0]}},
        "6": {"class_type": "EmptySD3LatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "7": {"class_type": "KSampler", "inputs": {"model": ["2", 0], "positive": ["4", 0], "negative": ["5", 0],
                                                   "latent_image": ["6", 0], "seed": seed, "steps": 9, "cfg": 1.0,
                                                   "sampler_name": "res_multistep", "scheduler": "simple", "denoise": 1.0}},
        "8": {"class_type": "VAELoader", "inputs": {"vae_name": "ae.safetensors"}},
        "9": {"class_type": "VAEDecode", "inputs": {"samples": ["7", 0], "vae": ["8", 0]}},
        "10": {"class_type": "PreviewImage", "inputs": {"images": ["9", 0]}},
    }


class Comfy:
    """ComfyUI's HTTP API: just what the painter needs."""

    def __init__(self, url: str) -> None:
        self.url = url.rstrip("/")
        self.client_id = uuid.uuid4().hex

    def _call(self, path: str, body: dict | None = None, timeout: float = 10.0) -> bytes:
        req = urllib.request.Request(self.url + path, data=None if body is None else json.dumps(body).encode(),
                                     headers={"Content-Type": "application/json"} if body is not None else {})
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.read()

    def up(self) -> bool:
        try:
            self._call("/system_stats", timeout=3.0)
            return True
        except (OSError, urllib.error.URLError):
            return False

    def busy(self) -> bool:
        """Someone else's job is running or waiting (an art session, the user in the UI)."""
        q = json.loads(self._call("/queue"))
        return bool(q.get("queue_running") or q.get("queue_pending"))

    def render(self, prompt: str, seed: int, timeout_s: float = 240.0) -> bytes:
        pid = json.loads(self._call("/prompt", {"prompt": graph(prompt, seed), "client_id": self.client_id}))["prompt_id"]
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            time.sleep(1.0)
            hist = json.loads(self._call(f"/history/{pid}")).get(pid)
            if not hist:
                continue
            status = hist.get("status", {})
            if status.get("status_str") == "error":
                raise RuntimeError(f"ComfyUI failed the picture: {status.get('messages', [])[-1:]}")
            for out in hist.get("outputs", {}).values():
                for img in out.get("images", []):
                    q = urllib.parse.urlencode({"filename": img["filename"], "subfolder": img.get("subfolder", ""),
                                                "type": img.get("type", "temp")})
                    return self._call(f"/view?{q}", timeout=30.0)
        raise TimeoutError(f"no picture from ComfyUI after {timeout_s:.0f}s")

    def free(self) -> None:
        self._call("/free", {"unload_models": True, "free_memory": True})


def gpu_free_gb() -> float | None:
    """Free memory on the card, from nvidia-smi; None if it can't be read."""
    try:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.free", "--format=csv,noheader,nounits"],
                             capture_output=True, text=True, timeout=10,
                             creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0)).stdout
        return int(out.split()[0]) / 1024
    except (OSError, ValueError, IndexError, subprocess.SubprocessError):
        return None


# ----------------------------------------------------------------- the painter

class Painter:
    """One thread, one queue. Every gate that says no leaves the request queued for later, except
    the daily cap; nothing here raises into the station."""

    def __init__(self, client: Comfy | None = None, *, gpu=gpu_free_gb) -> None:
        cfg = CONFIG.pictures
        self.cfg, self.client, self.gpu = cfg, client or Comfy(cfg.url), gpu
        self.q: queue.Queue[Request] = queue.Queue(maxsize=cfg.queue_max)
        self.known: dict[str, set[str]] = {}          # day -> keys made or queued
        self.warm = False                             # our models are loaded in ComfyUI: we /free when idle
        self.last_render = 0.0
        self.last_said = ""
        self.stop = threading.Event()

    def _keys(self, day: str) -> set[str]:
        if day not in self.known:
            self.known[day] = {r.key for r in made(day)}
        return self.known[day]

    def offer(self, req: Request) -> bool:
        keys = self._keys(req.day)
        if req.key in keys or len(keys) >= self.cfg.per_day:
            return False
        try:
            self.q.put_nowait(req)
        except queue.Full:
            return False
        keys.add(req.key)
        return True

    def _say(self, msg: str) -> None:
        if msg != self.last_said:
            log.info("pictures: %s", msg)
            self.last_said = msg

    def why_not(self) -> str:
        """'' when a picture may be made now, else the reason it waits."""
        if not self.client.up():
            return "ComfyUI isn't up; waiting"
        if self.client.busy():
            return "ComfyUI is busy with someone else's job; waiting"
        if not self.warm:
            free = self.gpu()
            if free is not None and free < self.cfg.min_free_gb:
                return f"the GPU has {free:.1f} GB free, under {self.cfg.min_free_gb:.0f}; waiting"
        return ""

    def step(self) -> bool:
        """Make one picture if one is waiting and the gates allow; True if one was made."""
        try:
            req = self.q.get(timeout=self.cfg.poll_s)
        except queue.Empty:
            self._maybe_free()
            return False
        try:
            reason = self.why_not()
        except Exception as e:  # noqa: BLE001
            reason = f"ComfyUI didn't answer ({e}); waiting"
        if reason:
            self._say(reason)
            self._requeue(req)
            self.stop.wait(self.cfg.wait_s)
            return False
        t0 = time.perf_counter()
        try:
            png = self.client.render(req.prompt, seed=zlib.crc32(req.key.encode()))
        except Exception as e:  # noqa: BLE001
            self._say(f"a picture failed ({e}); trying the next")
            self.warm = True                          # it may have loaded the models before failing
            return False
        req.seconds, req.ts = round(time.perf_counter() - t0, 1), time.time()
        _store(req, png)
        self.warm, self.last_render = True, time.monotonic()
        self._say("making pictures")
        log.info("pictures: %s for %s %r in %.1fs%s", req.file, req.show, req.subject[:70], req.seconds,
                 " (serious)" if req.serious else "")
        return True

    def _requeue(self, req: Request) -> None:
        try:
            self.q.put_nowait(req)
        except queue.Full:
            self._keys(req.day).discard(req.key)

    def _maybe_free(self) -> None:
        if self.warm and time.monotonic() - self.last_render > self.cfg.idle_free_s:
            try:
                if not self.client.busy():
                    self.client.free()
                    log.info("pictures: idle, so ComfyUI's models are unloaded")
                self.warm = False
            except Exception as e:  # noqa: BLE001
                self._say(f"couldn't free ComfyUI ({e})")
                self.warm = False

    def run(self) -> None:
        while not self.stop.is_set():
            try:
                self.step()
            except Exception:  # noqa: BLE001
                log.exception("pictures: the painter tripped; carrying on")
                self.stop.wait(self.cfg.wait_s)


_painter: Painter | None = None


def start() -> Painter | None:
    """The painter thread, if pictures are on."""
    global _painter
    if not enabled() or _painter is not None:
        return _painter
    _painter = Painter()
    threading.Thread(target=_painter.run, name="pictures", daemon=True).start()
    log.info("pictures: shadow mode on, %s, up to %d a day, into %s", CONFIG.pictures.url, CONFIG.pictures.per_day, root())
    return _painter


def offer(seg: Segment, world) -> None:
    """Called by the workers once a segment is scripted: never blocks, never raises."""
    if _painter is None:
        return
    try:
        req = request_for(seg, world)
        if req and _painter.offer(req):
            log.info("pictures: queued %s (%s %s)", req.key, req.show, req.kind)
    except Exception:  # noqa: BLE001
        log.exception("pictures: couldn't offer slot %s", seg.slot_id)


# ----------------------------------------------------------------- the contact sheet

SHEET_COLS, SHEET_ROWS = 2, 10


def _palette(surf, colours: int = 40):
    """k-means to `colours` colours, like the backdrops' pixelating: the look it would have on air."""
    import numpy as np
    import pygame

    a = pygame.surfarray.array3d(surf).reshape(-1, 3).astype(np.float32)
    rng = np.random.default_rng(5)
    centres = a[rng.choice(len(a), colours, replace=False)]
    for _ in range(12):
        lab = ((a[:, None, :] - centres[None]) ** 2).sum(-1).argmin(1)
        for k in range(colours):
            pts = a[lab == k]
            if len(pts):
                centres[k] = pts.mean(0)
    out = centres[lab].reshape(surf.get_width(), surf.get_height(), 3).astype(np.uint8)
    return pygame.surfarray.make_surface(out)


def _on_screen(img, box):
    """The picture as it would sit in a screen box: centre-cropped to the box's shape, box-scaled to
    its size in canvas pixels, the palette reduced, then blown up 2x nearest to look at."""
    import pygame

    w, h = img.get_size()
    aspect = box.w / box.h
    cw, ch = (int(h * aspect), h) if w / h > aspect else (w, int(w / aspect))
    crop = img.subsurface(pygame.Rect((w - cw) // 2, (h - ch) // 2, cw, ch))
    small = _palette(pygame.transform.smoothscale(crop, box.size))
    return pygame.transform.scale(small, (box.w * 2, box.h * 2))


def sheet(day: str, out: Path) -> list[Path]:
    """Contact sheets for `day`: each picture full, then in the news wall's screen and the sofa
    handover box at their size on air (2x), with its show, story and prompt subject."""
    import pygame

    from .scenes import SOFA_INSET, WALL_SCREEN

    pygame.font.init()
    font = pygame.font.SysFont("consolas", 15)
    rows = [r for r in made(day) if (root() / r.file).exists()]
    thumb = (384, 216)
    cell = (thumb[0] + WALL_SCREEN.w * 2 + SOFA_INSET.w * 2 + 40, max(thumb[1], WALL_SCREEN.h * 2) + 48)
    per = SHEET_COLS * SHEET_ROWS
    pages = []
    for p in range(0, max(1, len(rows)), per):
        chunk = rows[p:p + per]
        n_rows = max(1, -(-len(chunk) // SHEET_COLS))
        page = pygame.Surface((cell[0] * SHEET_COLS + 20, cell[1] * n_rows + 20))
        page.fill((24, 24, 28))
        for i, r in enumerate(chunk):
            x, y = 10 + (i % SHEET_COLS) * cell[0], 10 + (i // SHEET_COLS) * cell[1]
            img = pygame.image.load(io.BytesIO((root() / r.file).read_bytes()))
            page.blit(pygame.transform.smoothscale(img, thumb), (x, y))
            page.blit(_on_screen(img, WALL_SCREEN), (x + thumb[0] + 10, y))
            page.blit(_on_screen(img, SOFA_INSET), (x + thumb[0] + WALL_SCREEN.w * 2 + 20, y))
            when = datetime.fromtimestamp(r.ts).strftime("%H:%M") if r.ts else ""
            tag = f"{when} {r.show} {r.kind}{' ' + r.thread if r.thread else ''}{'  SERIOUS' if r.serious else ''}"
            top = y + max(thumb[1], WALL_SCREEN.h * 2) + 4
            page.blit(font.render(tag, True, (255, 200, 120) if r.serious else (200, 200, 210)), (x, top))
            page.blit(font.render(r.subject[:110], True, (235, 235, 240)), (x, top + 18))
        path = out if len(rows) <= per else out.with_name(f"{out.stem}-{p // per + 1}{out.suffix}")
        pygame.image.save(page, str(path))
        pages.append(path)
    return pages


def _cli() -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m newsroom.pictures", description=__doc__.split("\n\n")[0])
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--try", dest="try_", metavar="PROMPT", help="make one picture now, styled as the station would")
    g.add_argument("--sheet", nargs="?", const=date.today().isoformat(), metavar="YYYY-MM-DD",
                   help="that day's contact sheet (default today)")
    g.add_argument("--status", action="store_true", help="ComfyUI, the GPU and today's count")
    p.add_argument("--out", type=Path, help="where to write the picture or sheet")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")
    c = Comfy(CONFIG.pictures.url)
    if a.status:
        up = c.up()
        print(f"ComfyUI {CONFIG.pictures.url}: {'up' if up else 'not reachable'}"
              + (f", {'busy' if c.busy() else 'idle'}" if up else ""))
        free = gpu_free_gb()
        print(f"GPU free: {'unknown' if free is None else f'{free:.1f} GB'} (needs {CONFIG.pictures.min_free_gb:.0f} from cold)")
        print(f"made today: {len(made(date.today().isoformat()))} of {CONFIG.pictures.per_day}; on tonight: {enabled()}")
        return 0
    if a.sheet:
        pages = sheet(a.sheet, a.out or root() / f"sheet-{a.sheet}.png")
        print("\n".join(str(x) for x in pages))
        return 0
    req = Request(key="try", day=date.today().isoformat(), show="news", kind="try", headline=a.try_, subject=a.try_)
    t0 = time.perf_counter()
    png = c.render(prompt_for(req), seed=int(time.time()))
    out = a.out or root() / f"try-{datetime.now():%H%M%S}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_bytes(png)
    print(f"{out} in {time.perf_counter() - t0:.1f}s (ComfyUI keeps the models loaded: POST /free to unload)")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
