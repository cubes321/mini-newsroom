"""A character's puppet: paper pieces cut from the approved design and from variants of it.

data/cartoons/<series>/puppets/<who>/
    kit.json          the manifest (Kit)
    base.png          the design, padded to a multiple of 16 (Qwen's latent grid); every pixel coordinate in the
                      manifest is in this picture
    variants/<v>.png  Qwen-Image-Edit's changes to base.png (a beak open, eyes shut, a wing raised), drawn with
                      the ref-latent graph so the body stays where it was (under 0.01% of it moved, 2026-11-08)
    pieces/<pose>_<face>.png   what Blender shows: a pose with a face, on paper

A face is spliced in from its variant only inside its region (Qwen opening Gully's beak also widened his
eyes, which flickered when every syllable swapped the whole head), and only where the variant differs from
the design. The paper: an off-white cut edge, a lifted soft shadow, a faint grain; a gap the outline encloses
(between the legs) stays uncut paper.
"""
from __future__ import annotations

import json
import logging
import re
import shutil
import time
from pathlib import Path
from typing import Literal

import numpy as np
from pydantic import BaseModel, Field
from scipy import ndimage

log = logging.getLogger(__name__)

PAD, EDGE, SHADOW = 48, 9, (12, 15)           # pixels: room for the shadow, the cut edge's width, the lift
PAPER = np.array([247, 243, 233], np.float32)


class Variant(BaseModel):
    prompt: str                                # what Qwen changes; "change nothing else" is added
    seed: int = 202
    new_pose: bool = False                     # a whole new drawing (in flight, walking): keep only the character


class Face(BaseModel):
    variant: str                               # a key of Kit.variants
    region: str                                # a key of Kit.regions: where it may change the design


class Kit(BaseModel):
    who: str
    design: str                                # the approved design, relative to the series folder
    natural: Literal["left", "right", "front"]  # which way the design faces
    height: float = Field(gt=0)                # stage units for base.png's height (Gully: 10)
    feet_y: int                                # base.png row the feet stand on
    anchors: dict[str, tuple[int, int]] = {}   # named points in base.png: head, ankle, ...
    pose_anchors: dict[str, dict[str, tuple[int, int]]] = {}   # a pose whose point is elsewhere (a raised fist's hold)
    regions: dict[str, list[tuple[int, int, int, int]]] = {}
    variants: dict[str, Variant] = {}
    poses: dict[str, str | None] = {"normal": None}   # pose -> its variant (None: the design)
    faces: dict[str, Face] = {}                # besides "closed", the design's own face
    loud: str = "talk"                         # the face for a loud syllable (Gully: squawk)
    cut_holes: bool = False                    # a prop: its big enclosed holes of background are cut out
    looks: str = ""                            # a prop: the look it was drawn from (another look, another drawing)
    facing: dict[str, Literal["left", "right", "front"]] = {}   # a pose drawn facing another way (walking)
    walk: list[str] = []                       # poses that alternate as a walk (two strides)
    fly: str | None = None                     # the pose for flying

    def folder(self, series_dir: Path) -> Path:
        return series_dir / "puppets" / self.who

    def faces_on(self, pose: str) -> bool:
        """A new drawing's head is elsewhere: its faces would be spliced into thin air, so it keeps its own."""
        v = self.poses.get(pose)
        return v is None or not self.variants[v].new_pose

    def natural_of(self, pose: str) -> str:
        return self.facing.get(pose, self.natural)

    def piece(self, series_dir: Path, pose: str, face: str) -> Path:
        face = face if face == "closed" or face in self.faces else ("talk" if face in ("squawk",) else "closed")
        if not self.faces_on(pose):
            face = "closed"
        return self.folder(series_dir) / "pieces" / f"{pose}_{face}.png"

    def feet_of(self, series_dir: Path, pose: str) -> int:
        """The row a pose stands on: the design's feet, or a new drawing's lowest row (pieces/feet.json)."""
        if pose == "normal" or self.faces_on(pose):
            return self.feet_y
        meta = self.folder(series_dir) / "pieces" / "feet.json"
        return json.loads(meta.read_text())[pose] if meta.exists() else self.feet_y

    def anchor(self, name: str, pose: str = "normal") -> tuple[int, int] | None:
        """A named point as the pose draws it: Dot's shaking fist holds the bucket, not her lowered hand
        (the Chip Lift's shot 21, 2026-11-09, hung it at her hip)."""
        return self.pose_anchors.get(pose, {}).get(name) or self.anchors.get(name)

    @property
    def upp(self) -> float:
        """Stage units per pixel of base.png."""
        return self.height / self._h

    @property
    def half(self) -> float:
        """Half the drawing's width in stage units (pieces/box.json; without one, most of the picture)."""
        if self._box:
            return (self._box[2] - self._box[0]) / 2 * self.upp
        return 0.3 * self._w * self.upp

    _h: int = 0                                # base.png's height, set by load()
    _w: int = 0
    _box: tuple[int, int, int, int] | None = None     # the design's drawing in base.png: x0, y0, x1, y1


def load(series_dir: Path, who: str) -> Kit:
    path = series_dir / "puppets" / who / "kit.json"
    kit = Kit.model_validate_json(path.read_text(encoding="utf-8"))
    import pygame

    kit._w, kit._h = pygame.image.load(str(path.parent / "base.png")).get_size()
    box = path.parent / "pieces" / "box.json"
    if box.exists():
        kit._box = tuple(json.loads(box.read_text(encoding="utf-8")))
    return kit


def kits(series_dir: Path) -> dict[str, Kit]:
    return {p.parent.name: load(series_dir, p.parent.name) for p in sorted((series_dir / "puppets").glob("*/kit.json"))}


# ------------------------------------------------------------------ pictures as arrays (pygame: no Pillow here)


def rgb(path: Path) -> np.ndarray:
    import pygame

    return pygame.surfarray.array3d(pygame.image.load(str(path))).swapaxes(0, 1).astype(np.float32)


def save_rgba(a: np.ndarray, path: Path):
    import pygame

    h, w = a.shape[:2]
    path.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(pygame.image.frombuffer(np.ascontiguousarray(a.astype(np.uint8)).tobytes(), (w, h), "RGBA"),
                      str(path))


def save_rgb(a: np.ndarray, path: Path):
    save_rgba(np.dstack([a.clip(0, 255), np.full(a.shape[:2], 255.0)]), path)


# ------------------------------------------------------------------ the pieces


def splice(base: np.ndarray, var: np.ndarray, boxes, ref: np.ndarray | None = None, thr: float = 60,
           grow: int = 6) -> np.ndarray:
    """`var` where it differs from `ref` (default: `base`) inside the boxes, laid onto `base`, feathered."""
    diff = np.abs(var - (base if ref is None else ref)).sum(2) > thr
    m = np.zeros(diff.shape, bool)
    for x0, y0, x1, y1 in boxes:
        m[y0:y1, x0:x1] |= diff[y0:y1, x0:x1]
    m = ndimage.binary_dilation(ndimage.binary_closing(m, iterations=3), iterations=grow)
    w = ndimage.gaussian_filter(m.astype(np.float32), 2)[..., None]
    return base * (1 - w) + var * w


def cream_of(img: np.ndarray) -> np.ndarray:
    """The design's plain background: the median of its border."""
    edge = np.concatenate([img[0], img[-1], img[:, 0], img[:, -1]])
    return np.median(edge, axis=0).astype(np.float32)


def cut(img: np.ndarray, cream: np.ndarray, cut_holes: bool = False) -> tuple[np.ndarray, np.ndarray]:
    """The drawing and its alpha: the background is the cream joined to the border; the outline's soft edge
    becomes partial black; an enclosed gap stays as uncut paper."""
    near = np.abs(img - cream).sum(2) < 45
    lab, _ = ndimage.label(near)
    edge = set(np.unique(np.concatenate([lab[0], lab[-1], lab[:, 0], lab[:, -1]]))) - {0}
    fg = ~np.isin(lab, list(edge))
    # Loose islands (a speck in Mr Trethewey's design, the motion marks by Dot's fist) would cut out as bits
    # of paper of their own: only the main shape and anything at least a fiftieth of it is kept.
    parts, n = ndimage.label(fg)
    if n > 1:
        sizes = ndimage.sum(fg, parts, range(1, n + 1))
        fg = np.isin(parts, 1 + np.nonzero(sizes >= sizes.max() / 50)[0])
    # A prop's big enclosed hole of background (inside a bucket's handle) is cut out; a small one stays uncut
    # paper. Props only: a character's white is too near the cream to tell (Biscuit's chest went see-through).
    holes, n = ndimage.label(fg & (np.abs(img - cream).sum(2) < 18)) if cut_holes else (None, 0)
    if n:
        sizes = ndimage.sum(np.ones_like(holes), holes, range(1, n + 1))
        fg &= ~np.isin(holes, 1 + np.nonzero(sizes > fg.sum() * 0.015)[0])
    ring = ~fg & ndimage.binary_dilation(fg, iterations=2)
    a = fg.astype(np.float32)
    a[ring] = np.clip((cream.mean() - img.mean(2)[ring]) / cream.mean(), 0, 1)
    col = img.copy()
    col[ring] = 0
    col[near & fg] = PAPER
    return col, a


def grain(shape: tuple[int, int], seed: int) -> np.ndarray:
    """Paper: fine fibre and a broader mottle, about ±3.5%."""
    fine = ndimage.gaussian_filter(np.random.default_rng(seed).normal(0, 1, shape), 1.2)
    broad = ndimage.gaussian_filter(np.random.default_rng(seed + 1).normal(0, 1, shape), 6)
    g = fine * 0.9 + broad * 2.5
    return 1.0 + 0.035 * g / g.std()


def paper(col: np.ndarray, a: np.ndarray, g: np.ndarray) -> np.ndarray:
    """Padded RGBA: the lifted shadow, the cut paper edge, the grained drawing on it."""
    col = np.pad(col, ((PAD, PAD), (PAD, PAD), (0, 0)))
    a = np.pad(a, PAD)
    disk = np.hypot(*np.mgrid[-EDGE:EDGE + 1, -EDGE:EDGE + 1]) <= EDGE
    card = ndimage.gaussian_filter(ndimage.binary_dilation(a > 0.5, structure=disk).astype(np.float32), 0.8)
    shadow = ndimage.shift(ndimage.gaussian_filter(card, 5), SHADOW, order=1) * 0.38
    alpha = card + shadow * (1 - card)
    c = (PAPER * card[..., None] * (1 - a[..., None]) + col * a[..., None]) * g[..., None]
    c = np.where(alpha[..., None] > 1e-4, c / np.maximum(alpha, 1e-4)[..., None], 0)
    return np.dstack([c.clip(0, 255), alpha.clip(0, 1) * 255])


def build(series_dir: Path, who: str) -> list[Path]:
    """Every pose with every face, on paper, into pieces/; then the kit's sheet. Needs every variant drawn."""
    kit = load(series_dir, who)
    d = kit.folder(series_dir)
    base = rgb(d / "base.png")
    cream = cream_of(base)
    var = {k: rgb(d / "variants" / f"{k}.png") for k in kit.variants}
    g = grain((base.shape[0] + 2 * PAD, base.shape[1] + 2 * PAD), sum(map(ord, who)))
    out = []
    feet = {}
    for pose, pv in kit.poses.items():
        body = base if pv is None else var[pv]
        looks = {"closed": body}
        if not kit.faces_on(pose):
            _, a = cut(body, cream)
            feet[pose] = int(np.nonzero((a > 0.5).any(1))[0].max())
            looks_faces = {}
        else:
            looks_faces = kit.faces
        for face, f in looks_faces.items():
            looks[face] = splice(body, var[f.variant], kit.regions[f.region], ref=base,
                                 grow=10 if f.region == "head" else 6)
        for face, img in looks.items():
            path = d / "pieces" / f"{pose}_{face}.png"
            save_rgba(paper(*cut(img, cream, kit.cut_holes), g), path)
            out.append(path)
    (d / "pieces" / "feet.json").write_text(json.dumps(feet), encoding="utf-8")
    _, a = cut(base, cream, kit.cut_holes)
    ys, xs = np.nonzero(a > 0.5)
    (d / "pieces" / "box.json").write_text(json.dumps([int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())]),
                                           encoding="utf-8")
    sheet(d, out)
    return out


def sheet(d: Path, pieces: list[Path], cols: int = 5) -> Path:
    """The pieces on harbour blue, named, for the user's approval."""
    import os

    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.font.init()
    w, h = 300, 380
    page = pygame.Surface((cols * w, -(-len(pieces) // cols) * h))
    page.fill((70, 130, 160))
    font = pygame.font.SysFont("arial", 18, bold=True)
    for k, p in enumerate(pieces):
        im = pygame.image.load(str(p))
        s = min(w / im.get_width(), (h - 24) / im.get_height())
        im = pygame.transform.smoothscale(im, (int(im.get_width() * s), int(im.get_height() * s)))
        x, y = k % cols * w, k // cols * h
        page.blit(im, (x + (w - im.get_width()) // 2, y + 22))
        page.blit(font.render(p.stem, True, (255, 255, 255)), (x + 6, y + 2))
    out = d / "sheet.png"
    pygame.image.save(page, str(out))
    return out


def plate(series_dir: Path, n: int) -> Path:
    """The place's plate on the same paper (grained), cached in puppets/plates/."""
    out = series_dir / "puppets" / "plates" / f"place{n}.png"
    src = series_dir / "places" / f"place{n}.png"
    if not out.exists() or out.stat().st_mtime < src.stat().st_mtime:
        p = rgb(src)
        save_rgb(p * grain(p.shape[:2], 23 + n)[..., None], out)
    return out


# ------------------------------------------------------------------ the variants, by Qwen-Image-Edit


KEEP = (" Change nothing else at all: keep exactly the same pose, position, size, outlines, colours and the plain "
        "background, pixel for pixel. Same flat cartoon drawing style.")
POSE = (" Keep exactly the same character: the same colours, markings, face, outlines and flat cartoon drawing "
        "style, at the same size, alone on the same plain background, with nothing else in the picture.")


def edit_graph(prompt: str, image: str, seed: int, prefix: str) -> dict:
    """Qwen-Image-Edit 2511, 4 steps, with the ref-latent graph (no vae in the encoders, ReferenceLatent on
    both): the result lines up with the picture it edits (the backdrops' night variants, 2025-10-26)."""
    from entertainment.cartoons import QWEN

    return {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": QWEN["unet"], "weight_dtype": "default"}},
        "2": {"class_type": "LoraLoaderModelOnly", "inputs": {"model": ["1", 0], "lora_name": QWEN["lora"],
                                                              "strength_model": 1.0}},
        "3": {"class_type": "ModelSamplingAuraFlow", "inputs": {"model": ["2", 0], "shift": 3.0}},
        "4": {"class_type": "CLIPLoader", "inputs": {"clip_name": QWEN["clip"], "type": "qwen_image",
                                                     "device": "default"}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": QWEN["vae"]}},
        "20": {"class_type": "LoadImage", "inputs": {"image": image}},
        "21": {"class_type": "VAEEncode", "inputs": {"pixels": ["20", 0], "vae": ["5", 0]}},
        "6": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["4", 0], "prompt": prompt,
                                                                      "image1": ["20", 0]}},
        "7": {"class_type": "TextEncodeQwenImageEditPlus", "inputs": {"clip": ["4", 0], "prompt": "",
                                                                      "image1": ["20", 0]}},
        "8": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["6", 0], "latent": ["21", 0]}},
        "9": {"class_type": "ReferenceLatent", "inputs": {"conditioning": ["7", 0], "latent": ["21", 0]}},
        "10": {"class_type": "KSampler", "inputs": {"model": ["3", 0], "positive": ["8", 0], "negative": ["9", 0],
                                                    "latent_image": ["21", 0], "seed": seed, "steps": 4, "cfg": 1.0,
                                                    "sampler_name": "euler", "scheduler": "simple", "denoise": 1.0}},
        "11": {"class_type": "VAEDecode", "inputs": {"samples": ["10", 0], "vae": ["5", 0]}},
        "12": {"class_type": "SaveImage", "inputs": {"images": ["11", 0], "filename_prefix": f"cartoons/{prefix}"}},
    }


# A prop's height in stage units from the plain words of its look (Gully's drawing stands about 8). Raised
# 2026-11-09: at 2 to 3 units a bucket was a thimble beside the cast.
SIZES = (("tiny", 2.0), ("small", 3.2), ("little", 3.2), ("large", 5.5), ("big", 5.5), ("huge", 7.0))
PROP_SIZE = 4.0
PROP_W = 6.0                                   # stage units: the widest a prop is drawn (Gully is about 8 wide)
LINE = 7                                       # pixels: about the cast's outline in their designs
MARGIN = 32


def _cast_upp(series_dir: Path) -> float:
    """Stage units per pixel of the lead's design: the scale every paper edge and outline is cut at."""
    from entertainment import cartoons

    try:
        return load(series_dir, cartoons.SERIES[series_dir.name].cast[0].key).upp
    except (KeyError, OSError, IndexError):
        return 10.0 / 1344


def fit_prop(series_dir: Path, key: str, looks: str) -> Kit:
    """A prop's base.png and kit.json from its drawing (drawn.png, as Qwen drew it: far bigger than asked).

    The drawing is shrunk to the cast's own pixel scale BEFORE it is cut out, so the paper edge and shadow come
    out as wide as the cast's; shrunk as a card instead (to 2026-11-09), a bucket's edge and outline were a
    quarter of Gully's and it looked pasted in. Its outline, thinned by the shrinking, is drawn back out to
    LINE. Tall as the plain words of its look say, never wider than PROP_W. Its grip, where a beak or a hand
    holds it, is the top of its body: the first row at least 40% as wide as its widest (not a curl of steam)."""
    d = series_dir / "puppets" / key
    drawn = d / "drawn.png"
    if not drawn.exists():
        shutil.copy2(d / "base.png", drawn)
    img = rgb(drawn)
    cream = cream_of(img)
    _, a = cut(img, cream, cut_holes=True)
    ys, xs = np.nonzero(a > 0.5)
    bh, bw = max(1, ys.max() - ys.min()), max(1, xs.max() - xs.min())
    size = next((s for w, s in SIZES if re.search(rf"\b{w}\b", looks, re.I)), PROP_SIZE)
    size = min(size, PROP_W * bh / bw)
    upp = _cast_upp(series_dir)
    s = min(1.0, size / (bh * upp))
    crop = img[max(0, ys.min() - 8):ys.max() + 9, max(0, xs.min() - 8):xs.max() + 9]
    if s < 1.0:
        blur = (1 / s - 1) * 0.5
        crop = ndimage.zoom(ndimage.gaussian_filter(crop, (blur, blur, 0)), (s, s, 1), order=1)
    small = np.pad(crop, ((MARGIN, MARGIN), (MARGIN, MARGIN), (0, 0)), mode="edge")
    small[:MARGIN], small[-MARGIN:], small[:, :MARGIN], small[:, -MARGIN:] = cream, cream, cream, cream
    grow = round(LINE * (1 - s) / 2)
    if grow:
        _, a = cut(small, cream, cut_holes=True)
        fg = a > 0.5
        small[ndimage.binary_dilation(fg, iterations=grow) & ~fg] = 0
    save_rgb(small, d / "base.png")
    _, a = cut(small, cream, cut_holes=True)
    fg = a > 0.5
    ys, xs = np.nonzero(fg)
    wide = fg.sum(1)
    top = int(np.nonzero(wide >= 0.4 * wide.max())[0][0])
    mid = int(np.nonzero(fg[top])[0].mean())
    kit = Kit(who=key, design=f"puppets/{key}/base.png", natural="front", cut_holes=True, looks=looks,
              height=round(small.shape[0] * upp, 3), feet_y=int(ys.max()),
              anchors={"grip": (mid, top), "head": (int((xs.min() + xs.max()) / 2), int((ys.min() + ys.max()) / 2))})
    (d / "kit.json").write_text(kit.model_dump_json(indent=1), encoding="utf-8")
    return kit


def props(folder: Path) -> list[Path]:
    """A kit for every prop the episode names (props.json) that has none yet: Qwen redraws the series' lead's
    design as the prop, alone, in the same style on the same cream (so it cuts out the same way), sized from
    the plain words of its look (Gully stands 10). Each kit is one drawing; its grip is its top middle, where
    a beak or a hand holds it. GPU: only when the user says."""
    from entertainment import cartoons

    series_dir = folder.parent
    wanted = json.loads((folder / "props.json").read_text(encoding="utf-8"))
    lead = cartoons.SERIES[series_dir.name].cast[0].key
    style = series_dir / "puppets" / lead / "base.png"
    name = f"cartoon_puppet_{series_dir.name}_style.png"
    shutil.copy2(style, cartoons.COMFY_DIR / "input" / name)
    jobs = []
    for key, looks in wanted.items():
        old = series_dir / "puppets" / key
        if (old / "kit.json").exists():
            if json.loads((old / "kit.json").read_text(encoding="utf-8")).get("looks") == looks:
                fit_prop(series_dir, key, looks)       # drawn before from this look: sized by today's rules
                build(series_dir, key)
                continue
        prompt = (f"Replace the character in this picture with {key}: {looks.rstrip('. ')}. Draw it alone, centred, "
                  f"upright, about a third of the picture's height, in exactly the same flat cartoon style, bold black "
                  f"outlines and flat colours, on the same plain cream background. No character, no animal, no text, "
                  f"nothing else in the picture.")
        r = cartoons._comfy("/prompt", {"prompt": edit_graph(prompt, name, 202, f"puppets/prop_{key}"),
                                        "client_id": "cartoons"})
        jobs.append((key, looks, r["prompt_id"]))
    made = []
    for key, looks, pid in jobs:
        while not (h := cartoons._comfy(f"/history/{pid}").get(pid)):
            time.sleep(3)
        if h["status"].get("status_str") != "success":
            raise RuntimeError(f"prop {key} failed: {json.dumps(h['status'].get('messages', [])[-1:])[:800]}")
        d = series_dir / "puppets" / key
        if d.exists():   # the same key, another look ("chips" was a heap, then a cone): the old kept aside, now
            d.rename(series_dir / "puppets" / f"{key}.{len(list(d.parent.glob(f'{key}.*'))) + 1}")
        (d / "variants").mkdir(parents=True, exist_ok=True)
        for o in h["outputs"].values():
            for f in o.get("images", []):
                shutil.copy2(cartoons.COMFY_DIR / "output" / f["subfolder"] / f["filename"], d / "drawn.png")
                shutil.copy2(d / "drawn.png", d / "base.png")
        fit_prop(series_dir, key, looks)
        made += build(series_dir, key)
        log.info("cutout: prop %s drawn", key)
    if jobs:
        cartoons._comfy("/free", {"unload_models": True, "free_memory": True})
    return made


def draw(series_dir: Path, who: str, redo: tuple[str, ...] = ()) -> list[Path]:
    """Every variant not yet drawn (and `redo`, on the next seed), on ComfyUI. GPU: only when the user says."""
    from entertainment import cartoons

    kit = load(series_dir, who)
    d = kit.folder(series_dir)
    name = f"cartoon_puppet_{series_dir.name}_{who}_base.png"
    shutil.copy2(d / "base.png", cartoons.COMFY_DIR / "input" / name)
    jobs = []
    for k, v in kit.variants.items():
        path = d / "variants" / f"{k}.png"
        if k in redo and path.exists():
            takes = len(list(d.glob(f"variants/{k}.*.png")))
            path.rename(d / "variants" / f"{k}.{takes + 1}.png")
        if path.exists():
            continue
        seed = v.seed + 101 * len(list(d.glob(f"variants/{k}.*.png")))
        r = cartoons._comfy("/prompt", {"prompt": edit_graph(v.prompt.rstrip() + (POSE if v.new_pose else KEEP), name, seed,
                                                             f"puppets/{who}_{k}"), "client_id": "cartoons"})
        jobs.append((k, r["prompt_id"]))
    done = []
    for k, pid in jobs:
        while not (h := cartoons._comfy(f"/history/{pid}").get(pid)):
            time.sleep(3)
        if h["status"].get("status_str") != "success":
            raise RuntimeError(f"variant {who}/{k} failed: {json.dumps(h['status'].get('messages', [])[-1:])[:800]}")
        for o in h["outputs"].values():
            for f in o.get("images", []):
                dst = d / "variants" / f"{k}.png"
                dst.parent.mkdir(exist_ok=True)
                shutil.copy2(cartoons.COMFY_DIR / "output" / f["subfolder"] / f["filename"], dst)
                done.append(dst)
        log.info("cutout: %s's %s drawn", who, k)
    if jobs:
        cartoons._comfy("/free", {"unload_models": True, "free_memory": True})
    return done
