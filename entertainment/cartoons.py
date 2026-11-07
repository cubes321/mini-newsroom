"""Cartoons for the entertainment channel: written here, rendered offline with H3, kept in the bank.

The user's idea (2026-11-07): animated films made ahead, a series or two of our own, aired in Cartoon Time
from the content bank (newsroom/bank.py). Rendering is GPU work and only happens when the user says
(`render` is never called by the station). One episode, step by step:

    python -m entertainment.cartoons plan --series gully            write an episode: scenes, shots, lines
    python -m entertainment.cartoons render data/cartoons/gully/<ep>   queue its scenes on ComfyUI (or Wan2GP)
    python -m entertainment.cartoons assemble data/cartoons/gully/<ep> title card, the scenes, the end card
    python -m entertainment.cartoons ingest data/cartoons/gully/<ep>   onto the bank's shelf

A scene is one H3 render: one place, up to 15 seconds, at most five short lines, two or three shots (the
h3-reference-video skill's measured limits). The prompt is built here in H3's six sections from the series'
characters and style; the writer only says what happens. Each character has reference pictures (a full
figure and a face) and, once a voice is chosen, a voice clip, in data/cartoons/<series>/refs: they come
from the design stage, which the user approves on a sheet.

The engine (the speed test, 2026-11-07, one 5 s two-character scene): ComfyUI's H3 Ref2VA with the 4-step turbo
LoRA took 1.7 min, 20 steps 7.2 min, Wan2GP's FastH3 NVFP4 2.5 min. All three spoke the lines word for word;
the ComfyUI pair painted a storybook town that matches the characters, Wan2GP a semi-real one they sat on top
of, with a second of dead air at the cut. Turbo smears a fast wing, which a dialogue cartoon can live with:
about 10 min a 15 s scene, so a 3-minute episode is about 2 hours. CARTOON_ENGINE=wan2gp keeps the other.

Original characters only, never anyone else's: the inventor pair is in the spirit of a classic double act
(an eccentric and a wiser, wordless companion) with its own names, look and town.
"""
from __future__ import annotations

import json
import logging
import os
import difflib
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from pydantic import BaseModel, Field

from newsroom import llm
from newsroom.config import CONFIG
from newsroom.models import SegmentType as T
from newsroom.schedule import Item as I, Show

log = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent / "data" / "cartoons"
WAN2GP = Path(os.environ.get("WAN2GP_DIR", "C:/pinokio/api/wan2gp.git/app"))
ENGINE_MODEL = os.environ.get("CARTOON_MODEL", "minimax_h3_fasth3_omni_nvfp4")   # Wan2GP's model, if chosen
ENGINE = os.environ.get("CARTOON_ENGINE", "comfy")                                 # "comfy" (turbo) or "wan2gp"
COMFY_DIR = Path(os.environ.get("COMFY_DIR", "C:/stabilitymatrix/Data/Packages/ComfyUI"))
COMFY_API = os.environ.get("COMFY_API", "http://127.0.0.1:8188")
H3 = {"unet": "minimax_h3_ref2va_pruned_int8_convrot.safetensors",
      "turbo": "minimax_h3_ref2v_turbo_4step_v0.1_comfyui_bf16.safetensors",
      "clip": "qwen3vl_32b_minimax_h3_nvfp4_awq.safetensors",
      "vae": "minimax_h3_video_vae_int8_convrot.safetensors",
      "audio_vae": "minimax_h3_audio_vae_fp32.safetensors"}
TURBO_STEPS = 4
# The dialogue (the user's idea, 2026-11-07, from the music videos): recorded first, one line at a time in the cast's
# voices, laid on the scene's timeline, and given to H3 as <Audio 1>, which it copies almost sample for sample and
# moves the mouths to. Every voice is the same in every scene, and no line is invented or garbled (H3 speaking for
# itself babbled for three seconds in the pilot's scene 2). "h3" lets H3 voice the lines from the clips instead.
DIALOGUE = os.environ.get("CARTOON_DIALOGUE", "recorded")
TRACK_SR = 44100
POSSESSIVE = {"He": "his", "She": "her", "They": "their", "It": "its"}
LEAD_S, TAIL_S, GAP_S, MAX_GAP_S = 0.6, 0.8, 0.45, 2.2   # the first line's start, quiet at the end, between lines
# The bed under every scene's track (the copy probes, 2026-11-07): over silent gaps H3 made up speech of its own
# (0.39 match to the track); over a continuous bed it copied the track (0.90). So no scene's track is ever quiet:
# the series' score, sliced so it runs on across the cuts, and the place's ambience, under the lines (whose level
# is Pocket's, 0.085 RMS).
MUSIC_RMS, AMB_RMS = 0.022, 0.014
FPS = 24
SCENE_S = 15.0
MAX_LINES = 5
RESOLUTION = "1152x640"
TASK = "cartoon" if "cartoon" in CONFIG.llm.routes else "senior_editor"     # Sonnet, unless routed otherwise


@dataclass(frozen=True)
class Character:
    key: str                     # speaker id in the scripts, and the refs' file stem
    name: str
    looks: str                   # what H3 keeps: shape, colours, clothes, in the series' style
    voice: str                   # how they sound, for H3; "" = never speaks
    pronoun: str = "He"


@dataclass(frozen=True)
class Series:
    id: str
    title: str
    premise: str
    style: str                   # the medium, named for H3 ("hand-drawn 2D cartoon ...")
    music: str                   # the score under every scene
    cast: tuple[Character, ...]
    places: tuple[str, ...]      # where episodes happen, in Port Wexley
    tone: str = ""

    def refs(self) -> Path:
        return ROOT / self.id / "refs"

    def plate(self, place: str) -> Path | None:
        """The place's plate (places/placeN.png, N its number in `places`): an empty painting of it, given to
        H3 so the chip shop is the same chip shop in every scene (the pilot built it three ways)."""
        if place not in self.places:
            return None
        path = ROOT / self.id / "places" / f"place{self.places.index(place) + 1}.png"
        return path if path.exists() else None

    def sound(self, name: str) -> Path | None:
        """A bed in sound/: score.wav (the series' underscore, one continuous piece) or ambN.wav (place N)."""
        path = ROOT / self.id / "sound" / name
        return path if path.exists() else None


STYLE = ("hand-drawn 2D cartoon animation in the style of a classic British children's television cartoon: clean "
         "bold outlines, flat warm colours, simple painted backgrounds of a small Cornish-looking fishing town")

SERIES: dict[str, Series] = {s.id: s for s in (
    Series(
        "gully", "GULLY AND BISCUIT",
        "Gully, a cheeky, greedy, endlessly confident herring gull, and Biscuit, the lifeboat station's ginger-and-"
        "white cat, who has seen it all and is not impressed, share Port Wexley's harbour. Every episode Gully has a "
        "scheme (usually for chips); Biscuit says very little and is usually right.",
        STYLE, "a light, bouncy cartoon score: pizzicato strings, a xylophone and a tin whistle, in a major key",
        (Character("gully", "Gully", "a big white-and-grey herring gull with a yellow beak with a red spot, pink legs and "
                   "bright, mischievous eyes", "a fast, chirpy, slightly squawky young male voice, always mid-scheme"),
         Character("biscuit", "Biscuit", "a plump ginger-and-white tabby cat with white fur on her chest and paws, an "
                   "ordinary four-legged cat, and heavy-lidded, unimpressed eyes",
                   "a slow, dry, low female voice with a West Country burr, few words", "She"),
         # The regulars (2026-11-07): the pilot's chip-shop man was a new man in every scene. Silent until cast.
         Character("trethewey", "Mr Trethewey", "a stout, cheerful man in his fifties who runs the chip shop: round "
                   "red cheeks, a red nose, a bushy brown moustache, a white paper hat, a white short-sleeved shirt and "
                   "a red-and-white striped apron", ""),
         Character("dot", "Dot Penrose", "the fishmonger, a brisk woman with short dark hair under a navy knitted "
                   "bobble hat, a navy jumper, a long dark green apron, yellow rubber gloves and white wellington boots",
                   "", "She")),
        ("the harbour wall at low tide", "the lifeboat station slipway", "the chip shop on the quay",
         "the fish market on Harrow Street", "the lighthouse at dusk", "the Saltby ferry's deck"),
        tone="gently slapstick, warm, never cruel; for children and the grown-ups watching with them",
    ),
    Series(
        "inventor", "MORWENNA AND BALLAST",
        "Morwenna Kitto, a cheerful, eccentric retired harbour engineer, builds contraptions in her shed on the quay to "
        "solve small problems in the most complicated way possible. Ballast, her tortoise, never speaks, moves very "
        "slowly and quietly saves the day.",
        STYLE, "a jaunty brass-band-flavoured cartoon score on a tuba, a cornet and a snare, in a major key",
        (Character("morwenna", "Morwenna Kitto", "a tall woman in her sixties with wild grey curls, round goggles pushed "
                   "up on her head, a bright yellow oilskin jacket worn open over faded blue denim dungarees with colourful "
                   "patches on the knees, and green wellington boots", "a warm, excitable older woman's voice "
                   "with a Cornish accent, talking fast when an idea strikes", "She"),
         Character("ballast", "Ballast", "a small brown tortoise with a shiny patterned shell and a calm, wise face",
                   "", "He")),
        ("Morwenna's shed on the quay, full of contraptions", "the harbour wall", "the allotments on the hill",
         "the town hall steps", "the beach at Saltby", "the Harrow Street market"),
        tone="cheerful, inventive slapstick with a kind heart; the contraption always half-works",
    ),
)}

# Cartoon Time: an hour of films from the bank, a series in turn, a bumper between. Nothing is written live.
CARTOON_TIME = Show(
    "cartoons", "CARTOON TIME", "CARTOONS", (230, 90, 60),
    pattern=(T.bumper, I(T.film, brief="gully"), I(T.film, brief="inventor"), T.bumper),
    loop_from=1,
    target_s={T.bumper: 8.0, T.film: 120.0},
    cast=("kids",), lead="kids",
    station="Cartoon Time, on Port Wexley's second channel",
    tone="bright and silly",
    light=True, repeats_overnight=False,
)

# ------------------------------------------------------------------ the writer


class Shot(BaseModel):
    at: float = Field(ge=0, lt=SCENE_S, description="seconds into the scene this shot starts; the first is 0")
    action: str = Field(max_length=300, description="camera and framing, then what happens, in order")


class Said(BaseModel):
    who: str = Field(description="a character key from THE CAST")
    words: str = Field(max_length=160, description="one short line, as said")


class Scene(BaseModel):
    place: str = Field(max_length=120, description="one of THE PLACES, copied exactly")
    on_screen: list[str] = Field(default_factory=list, max_length=3,
                                 description="the keys of THE CAST who are seen in this scene")
    summary: str = Field(max_length=200, description="the scene in one sentence")
    shots: list[Shot] = Field(min_length=1, max_length=3)
    lines: list[Said] = Field(default_factory=list, max_length=MAX_LINES)
    sounds: str = Field(max_length=200, description="what we hear besides the lines: waves, gulls, a contraption")


class Episode(BaseModel):
    title: str = Field(max_length=60)
    logline: str = Field(max_length=200)
    scenes: list[Scene] = Field(min_length=2, max_length=12)


_SYSTEM = """\
You write one episode of {title}, a cartoon on a small-town TV station's second channel, set in the
FICTIONAL fishing town of Port Wexley. {premise} Tone: {tone}.
Write {n} SCENES. Each scene is one continuous piece of animation in ONE of THE PLACES, at most fifteen
seconds long: two or three shots (the first at 0 seconds, the others later, each restating where it is),
and at most five SHORT lines in all (about three seconds each), spoken only by THE CAST's speaking
characters. A character who never speaks acts, and that is often the joke. The episode has a beginning, a
turn and a payoff across the scenes, and visual comedy that animation can show: things falling, flying,
running, a contraption going wrong. Original jokes only; no famous characters, catchphrases or brands.
- PLACE is one of THE PLACES copied exactly; say the time of day in the summary and shots instead.
- ON_SCREEN lists who is seen in the scene (at most three of THE CAST). Only THE CAST are characters:
  anyone else is an unnamed crowd far in the background, never featured, close up or acting.
- No written words anywhere: never ask for lettering on a sign, label, paper or plan.
Return ONLY JSON.
"""


def write(series: Series, n: int = 6, idea: str = "") -> Episode:
    cast = "\n".join(f"  - {c.key}: {c.name}, {c.looks}; " + (f"speaks: {c.voice}" if c.voice else "NEVER SPEAKS")
                     for c in series.cast)
    user = (f"THE CAST:\n{cast}\n\nTHE PLACES:\n" + "\n".join(f"  - {p}" for p in series.places)
            + (f"\n\nTHIS EPISODE'S IDEA: {idea}" if idea else "")
            + _done(series))
    ep = llm.complete_json(TASK, Episode, _SYSTEM.format(title=series.title, premise=series.premise,
                                                          tone=series.tone, n=n), user)
    talkers = {c.key for c in series.cast if c.voice}
    keys = [c.key for c in series.cast]
    for s in ep.scenes:                          # a line for a silent character, or nobody, is dropped
        s.lines = [l for l in s.lines if l.who in talkers][:MAX_LINES]
        if s.place not in series.places:         # a near miss is taken as the place it nearly is
            s.place = (difflib.get_close_matches(s.place, series.places, n=1, cutoff=0.0) or [s.place])[0]
        s.on_screen = [k for k in dict.fromkeys(s.on_screen + [l.who for l in s.lines]) if k in keys][:4]
        s.shots = sorted(s.shots, key=lambda x: x.at)
        s.shots[0].at = 0.0
    return ep


def _done(series: Series) -> str:
    made = sorted((ROOT / series.id).glob("*/episode.json"))
    titles = [json.loads(p.read_text(encoding="utf-8"))["title"] for p in made][-12:]
    return ("\n\nEPISODES ALREADY MADE (a new story, not these):\n" + "\n".join(f"  - {t}" for t in titles)) if titles else ""


# ------------------------------------------------------------------ H3's prompt for a scene


@dataclass(frozen=True)
class Cue:
    at: float                    # seconds into the scene the line starts, in the recorded track
    who: str
    words: str


_TITLES = {"mr", "mrs", "ms", "miss", "dr"}


def _seen(series: Series, scene: Scene) -> list[Character]:
    """Who is on screen: the writer's list, else (older episodes) anyone named in the summary or shots by a
    word of their name that isn't a title; never more than four (with a plate, nine pictures in all)."""
    if scene.on_screen:
        keys = set(scene.on_screen) | {l.who for l in scene.lines}
    else:
        text = " ".join([scene.summary, *(s.action for s in scene.shots)])
        keys = {l.who for l in scene.lines} | {c.key for c in series.cast if any(
            re.search(rf"\b{re.escape(w)}\b", text, re.I) for w in c.name.split() if w.lower() not in _TITLES)}
    return ([c for c in series.cast if c.key in keys] or list(series.cast[:1]))[:4]


def prompt(series: Series, scene: Scene, cues: list[Cue] | None = None,
           bed: bool = False) -> tuple[str, list[Path], list[Path]]:
    """The scene's H3 prompt in its six sections, and its reference pictures and voice clips in the order the
    prompt names them (<Picture N>, <Audio N>). Only the characters on screen are referenced, then the place's
    plate if it has one. With `cues` the sound is recorded (`bed`: the score and the place's ambience under
    it): the caller gives the track as <Audio 1>, and no voice clip is referenced."""
    present = _seen(series, scene)
    pics: list[Path] = []
    voices: list[Path] = []
    defs, keep = [], []
    speakers = {c.key: f"S{i + 1}" for i, c in enumerate(c for c in present if c.voice)}
    for k, c in enumerate(present, start=1):
        full, face = series.refs() / f"{c.key}_full.png", series.refs() / f"{c.key}_face.png"
        pics += [full, face]
        d = (f"<Subject {k}> is {c.name}, {c.looks}, from <Picture {len(pics) - 1}> (full figure) and "
             f"<Picture {len(pics)}> (face).")
        if c.voice and cues is not None:
            d += f" {c.pronoun} speaks ({speakers[c.key]}) in {c.voice}; {POSSESSIVE.get(c.pronoun, 'their')} lines are heard in <Audio 1>."
        elif c.voice:
            clip = series.refs() / f"{c.key}_voice.wav"
            if clip.exists():
                voices.append(clip)
                d += f" {c.pronoun} speaks ({speakers[c.key]}) in {c.voice}, exactly the voice heard in <Audio {len(voices)}>."
            else:
                d += f" {c.pronoun} speaks ({speakers[c.key]}) in {c.voice}."
        else:
            d += f" {c.pronoun} never speaks."
        defs.append(d)
        keep.append(f"<Subject {k}> (appears in every shot): fully_preserved - keep {c.name}'s shape, colours and "
                    f"look in the {series.style.split(':')[0]}")
    shots = " ".join(f"[Shot {i + 1}] " + (f"At 00:{s.at:06.3f}, cut to " if i else "") + f"{s.action.rstrip('. ')}, at "
                     f"{scene.place}." for i, s in enumerate(scene.shots))
    said = " ".join(f"({speakers[l.who]}) <d>[English] {l.words}</d>" for l in scene.lines if l.who in speakers)
    plate = series.plate(scene.place)
    if plate:
        pics.append(plate)
        setting = (f". The setting is {scene.place} in Port Wexley, retained exactly as seen in <Picture {len(pics)}>: "
                   f"its buildings, layout, colours and drawing style, with nobody else in it; the light may change "
                   f"with the time of day")
    else:
        setting = f". The reference images' background is not retained; the setting is {scene.place} in Port Wexley"
    music = f"non_diegetic_music: {series.music}."
    if cues is not None and not cues and bed:
        sound = (f"overall_soundscape: Everything heard is <Audio 1> reproduced exactly: {scene.sounds.rstrip('. ')}, "
                 f"and the score. Nobody speaks: no speech, no voices, no other sound.")
        music = "non_diegetic_music: the cartoon score heard in <Audio 1>, reproduced exactly."
    elif cues:
        # Plain quotes, never <d> tags: given a written line H3 voices it itself and leaves the recording
        # (the A/B's tea-cosy scene: the right words, its own timing, a 0.02 match to the track). Wan2GP's H3
        # handler says the same; the music videos quote their lyric the same way.
        names = {c.key: c.name.split()[0] for c in present}
        said = "; ".join(f'at 00:{q.at:06.3f} ({speakers[q.who]}) {names[q.who]} says "{q.words}"' for q in cues
                         if q.who in speakers)
        sound = (f"overall_soundscape: Everything heard is <Audio 1> reproduced exactly, in time with it: {said}. Each "
                 f"speaker is visibly speaking with natural lip movements synchronized to <Audio 1>. Under the "
                 f"dialogue, {scene.sounds.rstrip('. ')}, as heard in <Audio 1>. No other speech, no other sound.")
        if bed:
            music = "non_diegetic_music: the cartoon score heard in <Audio 1>, reproduced exactly."
    else:
        sound = f"overall_soundscape: {scene.sounds.rstrip('. ')}. " + (f"Dialogue: {said} Only the dialogue above." if said else
                                                           "Nobody speaks.")
    text = "\n".join([
        "subject_definitions: " + " ".join(defs),
        f"summary: [reference generation] {scene.summary}",
        "retention_analysis: " + ". ".join(keep) + setting + ".",
        f"detailed_description: The target video is {series.style}, {scene.place}. {shots}",
        sound,
        music,
    ])
    return text, pics, voices


# ------------------------------------------------------------------ the recorded dialogue


def _speak(series: Series, who: str, words: str):
    """One line in a character's voice: Pocket TTS cloning their voice clip (CPU), as a float array at the TTS
    rate. The engine is this one function, so a GPU voice can take its place."""
    from newsroom import tts

    clip = series.refs() / f"{who}_voice.wav"
    if not clip.exists():
        raise FileNotFoundError(f"no voice for {who} yet: {clip.name} (the casting stage)")
    with tts._SYNTH_LOCK:
        return tts._pocket_speak(words, clip)


def _trim(a, sr: int):
    """A line without the silence the voice engine leaves either side (a 30 ms margin kept)."""
    import numpy as np

    loud = np.flatnonzero(np.abs(a) > 0.02 * (float(np.abs(a).max()) or 1.0))
    if not len(loud):
        return a
    m = int(0.03 * sr)
    return a[max(0, loud[0] - m): loud[-1] + m]


def _bed(series: Series, scene: Scene, i: int, n: int):
    """Scene i's bed, `n` samples of stereo at TRACK_SR: the score from (i - 1) scenes in, so the slices join up
    into one piece across the episode, and the place's ambience; None when the series has neither yet."""
    import numpy as np
    import soundfile as sf

    def level(path: Path, start: float, rms: float):
        a, sr = sf.read(path, dtype="float32", always_2d=True)
        if a.shape[1] == 1:
            a = np.repeat(a, 2, axis=1)
        if sr != TRACK_SR:
            x = np.arange(int(len(a) * TRACK_SR / sr)) * sr / TRACK_SR
            a = np.stack([np.interp(x, np.arange(len(a)), a[:, ch]) for ch in (0, 1)], axis=1).astype(np.float32)
        at = int(start * TRACK_SR) % max(1, len(a))
        out = np.take(a, np.arange(at, at + n), axis=0, mode="wrap")     # a short bed loops
        return out * (rms / (float(np.sqrt((a ** 2).mean())) or 1.0))

    total = n / TRACK_SR
    score = series.sound("score.wav")
    place = series.sound(f"amb{series.places.index(scene.place) + 1}.wav") if scene.place in series.places else None
    if not score and not place:
        return None
    bed = np.zeros((n, 2), dtype=np.float32)
    if score:
        bed += level(score, (i - 1) * total, MUSIC_RMS)
    if place:
        bed += level(place, (i * 7.3) % 20.0, AMB_RMS)                  # a different stretch of it each scene
    fade = min(n, int(0.02 * TRACK_SR))                                  # no click at either end of a scene
    bed[:fade] *= np.linspace(0, 1, fade)[:, None]
    bed[-fade:] *= np.linspace(1, 0, fade)[:, None]
    return bed


def record(series: Series, scene: Scene, folder: Path, i: int) -> tuple[Path, list[Cue]] | None:
    """Scene i's sound: each line recorded once (kept in sceneNN/lines, so a retake is one file deleted), laid
    on the scene's timeline with natural gaps, the spare time spread evenly between lines, over the series' bed
    (_bed), written as sceneNN.dialogue.wav (stereo, the scene's exact length). A scene nobody speaks in gets
    the bed alone (cues []). None when there is nothing to record: no lines and no bed."""
    import numpy as np
    import soundfile as sf
    from newsroom.config import CONFIG

    talkers = {c.key for c in series.cast if c.voice}
    lines = [l for l in scene.lines if l.who in talkers]
    total = frames(SCENE_S) / FPS
    n = int(round(total * TRACK_SR))
    bed = _bed(series, scene, i, n)
    if not lines:
        if bed is None:
            return None
        path = folder / f"scene{i:02d}.dialogue.wav"
        sf.write(path, np.clip(bed, -1, 1), TRACK_SR)
        return path, []
    sr = CONFIG.tts.sample_rate
    store = folder / f"scene{i:02d}" / "lines"
    store.mkdir(parents=True, exist_ok=True)
    clips = []
    for k, l in enumerate(lines, start=1):
        wav = store / f"{k:02d}_{l.who}.wav"
        if not wav.exists():
            sf.write(wav, _trim(_speak(series, l.who, l.words), sr), sr)
        a, got = sf.read(wav, dtype="float32")
        clips.append(np.interp(np.arange(int(len(a) * TRACK_SR / got)) * got / TRACK_SR, np.arange(len(a)), a))
    speech = sum(len(c) for c in clips) / TRACK_SR
    spare = total - LEAD_S - TAIL_S - speech - GAP_S * (len(clips) - 1)
    if spare < 0:
        raise ValueError(f"scene {i}'s lines run {speech:.1f}s: too long for {total:.1f}s")
    gap = GAP_S + (min(MAX_GAP_S - GAP_S, spare / (len(clips) - 1)) if len(clips) > 1 else 0.0)
    lead = LEAD_S + min(0.9, max(0.0, spare - (gap - GAP_S) * (len(clips) - 1)) / 2)
    track = np.zeros(n, dtype=np.float32)
    cues, t = [], lead
    for l, c in zip(lines, clips):
        at = int(round(t * TRACK_SR))
        track[at: at + len(c)] += c[: len(track) - at]
        cues.append(Cue(round(t, 3), l.who, l.words))
        t += len(c) / TRACK_SR + gap
    path = folder / f"scene{i:02d}.dialogue.wav"
    mix = np.stack([track, track], axis=1) + (bed if bed is not None else 0.0)
    sf.write(path, np.clip(mix, -1, 1), TRACK_SR)
    return path, cues


# ------------------------------------------------------------------ the steps


def plan(series_id: str, n: int = 6, idea: str = "") -> Path:
    series = SERIES[series_id]
    ep = write(series, n, idea)
    slug = re.sub(r"[^a-z0-9]+", "-", ep.title.lower()).strip("-")[:40]
    folder = ROOT / series_id / slug
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "episode.json").write_text(ep.model_dump_json(indent=1), encoding="utf-8")
    for i, scene in enumerate(ep.scenes, start=1):
        text, pics, voices = prompt(series, scene)
        (folder / f"scene{i:02d}.prompt.txt").write_text(text, encoding="utf-8")
    log.info("cartoons: %s, %d scenes, in %s", ep.title, len(ep.scenes), folder)
    return folder


def frames(seconds: float) -> int:
    """H3's frame counts are 17k+5 at 24 fps: the nearest to `seconds` (124 = 5 s, 362 = 15.08 s, the top)."""
    return max(22, min(362, round((seconds * FPS - 5) / 17) * 17 + 5))


def settings(series: Series, scene: Scene, seed: int) -> dict:
    """One Wan2GP task (`wgp.py --process`): the model, the prompt, the references, the length.
    Voice clips go in audio_guide, audio_guide2, audio_guide3 with audio_prompt_type A / AB / ABD (Wan2GP's
    Ref2VA handler), in the prompt's <Audio N> order; 15 s in all, so two voices get 7.5 s each."""
    text, pics, voices = prompt(series, scene)
    missing = [p for p in pics if not p.exists()]
    if missing:
        raise FileNotFoundError(f"no reference pictures yet: {', '.join(p.name for p in missing)} (the design stage)")
    s = {"model_type": ENGINE_MODEL, "prompt": text, "image_refs": [str(p) for p in pics], "video_prompt_type": "I",
         "video_length": frames(SCENE_S), "resolution": RESOLUTION, "seed": seed}
    for key, clip in zip(("audio_guide", "audio_guide2", "audio_guide3"), voices):
        s[key] = str(clip)
    if voices:
        s["audio_prompt_type"] = "ABD"[:len(voices)]                 # A, AB, ABD (zip keeps three at most)
    return s


def comfy_graph(text: str, pics: list[str], voices: list[str], seed: int, length: int, prefix: str,
                steps: int = TURBO_STEPS) -> dict:
    """ComfyUI's H3 Ref2VA template (as the h3-reference-video skill builds it): int8 UNET, the turbo LoRA when
    steps is 4, res_multistep / simple, BasicGuider. `pics` and `voices` are names in ComfyUI's input folder, in
    the prompt's <Picture N> / <Audio N> order."""
    w, h = (int(x) for x in RESOLUTION.split("x"))
    model = ["1", 0]
    g = {
        "1": {"class_type": "UNETLoader", "inputs": {"unet_name": H3["unet"], "weight_dtype": "default"}},
        "3": {"class_type": "CLIPLoader", "inputs": {"clip_name": H3["clip"], "type": "minimax", "device": "default"}},
        "4": {"class_type": "VAELoader", "inputs": {"vae_name": H3["vae"]}},
        "5": {"class_type": "VAELoader", "inputs": {"vae_name": H3["audio_vae"]}},
        "9": {"class_type": "MiniMaxH3ReferenceToVideo", "inputs": {
            "clip": ["3", 0], "vae": ["4", 0], "audio_vae": ["5", 0], "prompt": text, "width": w, "height": h,
            "length": length, "ref_image_size": "match"}},
        "10": {"class_type": "RandomNoise", "inputs": {"noise_seed": seed}},
        "11": {"class_type": "KSamplerSelect", "inputs": {"sampler_name": "res_multistep"}},
        "15": {"class_type": "VAEDecode", "inputs": {"samples": ["14", 0], "vae": ["4", 0]}},
        "16": {"class_type": "VAEDecodeAudio", "inputs": {"samples": ["14", 0], "vae": ["5", 0]}},
        "17": {"class_type": "CreateVideo", "inputs": {"images": ["15", 0], "audio": ["16", 0], "fps": float(FPS)}},
        "18": {"class_type": "SaveVideo", "inputs": {"video": ["17", 0], "filename_prefix": f"cartoons/{prefix}",
                                                       "format": "auto", "format.codec": "auto"}},
    }
    for i, name in enumerate(pics):
        g[str(100 + i)] = {"class_type": "LoadImage", "inputs": {"image": name}}
        g["9"]["inputs"][f"ref_images.ref_image_{i}"] = [str(100 + i), 0]
    for i, name in enumerate(voices):
        g[str(200 + i)] = {"class_type": "LoadAudio", "inputs": {"audio": name}}
        g["9"]["inputs"][f"ref_audios.ref_audio_{i}"] = [str(200 + i), 0]
    if steps == TURBO_STEPS:
        g["2"] = {"class_type": "LoraLoaderModelOnly", "inputs": {"model": model, "lora_name": H3["turbo"],
                                                                 "strength_model": 1.0}}
        model = ["2", 0]
    g["12"] = {"class_type": "BasicScheduler", "inputs": {"model": model, "scheduler": "simple", "steps": steps,
                                                          "denoise": 1.0}}
    g["13"] = {"class_type": "BasicGuider", "inputs": {"model": model, "conditioning": ["9", 0]}}
    g["14"] = {"class_type": "SamplerCustomAdvanced", "inputs": {"noise": ["10", 0], "guider": ["13", 0],
                                                                 "sampler": ["11", 0], "sigmas": ["12", 0],
                                                                 "latent_image": ["9", 1]}}
    return g


def _comfy(path: str, body: dict | None = None) -> dict:
    import urllib.request

    req = urllib.request.Request(COMFY_API + path, data=None if body is None else json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=30) as r:
        raw = r.read()
    return json.loads(raw) if raw else {}


def _to_comfy(series: Series, path: Path, as_name: str | None = None) -> str:
    """A reference into ComfyUI's input folder, under a name that says whose it is (copied when changed)."""
    import shutil

    name = f"cartoon_{series.id}_{as_name or path.name}"
    dst = COMFY_DIR / "input" / name
    if not dst.exists() or dst.stat().st_mtime < path.stat().st_mtime or dst.stat().st_size != path.stat().st_size:
        shutil.copy2(path, dst)
    return name


def _rendered(folder: Path, i: int) -> Path | None:
    return next(iter(sorted((folder / f"scene{i:02d}").glob("*.mp4"))[-1:]), None)


def render(folder: Path, dry_run: bool = False, engine: str | None = None) -> list[Path]:
    """Every scene not yet rendered (GPU: only when the user says). ComfyUI: the whole episode is queued at once
    (its queue runs in order), then each scene is collected as it finishes; a scene with a video is kept, so a
    stopped night resumes. Wan2GP: one headless run each."""
    if (engine or ENGINE) == "comfy":
        return _render_comfy(folder, dry_run)
    series = SERIES[folder.parent.name]
    ep = Episode.model_validate_json((folder / "episode.json").read_text(encoding="utf-8"))
    out = []
    for i, scene in enumerate(ep.scenes, start=1):
        task = folder / f"scene{i:02d}.wan2gp.json"
        task.write_text(json.dumps(settings(series, scene, seed=1000 + i), indent=1), encoding="utf-8")
        cmd = [str(WAN2GP / "env" / "Scripts" / "python.exe"), "wgp.py", "--process", str(task),
               "--output-dir", str(folder / f"scene{i:02d}")] + (["--dry-run"] if dry_run else [])
        log.info("cartoons: scene %d of %d on Wan2GP%s", i, len(ep.scenes), " (dry run)" if dry_run else "")
        subprocess.run(cmd, cwd=WAN2GP, check=True)
        out += sorted((folder / f"scene{i:02d}").glob("*.mp4"))[-1:]
    return out


def _render_comfy(folder: Path, dry_run: bool) -> list[Path]:
    import shutil
    import time

    series = SERIES[folder.parent.name]
    ep = Episode.model_validate_json((folder / "episode.json").read_text(encoding="utf-8"))
    jobs: list[tuple[int, str]] = []
    for i, scene in enumerate(ep.scenes, start=1):
        if _rendered(folder, i):
            log.info("cartoons: scene %d already rendered", i)
            continue
        rec = record(series, scene, folder, i) if DIALOGUE == "recorded" else None
        text, pics, voices = prompt(series, scene, rec[1] if rec else None,
                                    bed=_bed(series, scene, i, 1) is not None)
        missing = [p for p in pics if not p.exists()]
        if missing:
            raise FileNotFoundError(f"no reference pictures yet: {', '.join(p.name for p in missing)} (the design stage)")
        names = [p.name if dry_run else _to_comfy(series, p) for p in pics]
        audio = [v.name if dry_run else _to_comfy(series, v) for v in voices]
        if rec:                                          # the recorded dialogue is <Audio 1>, the only audio
            audio = [rec[0].name if dry_run else _to_comfy(series, rec[0], f"{folder.name}_{rec[0].name}")]
        graph = comfy_graph(text, names, audio, seed=1000 + i, length=frames(SCENE_S),
                            prefix=f"{series.id}_{folder.name}_scene{i:02d}")
        (folder / f"scene{i:02d}.comfy.json").write_text(json.dumps(graph, indent=1), encoding="utf-8")
        if dry_run:
            continue
        r = _comfy("/prompt", {"prompt": graph, "client_id": "cartoons"})
        if r.get("node_errors"):
            raise RuntimeError(f"ComfyUI refused scene {i}: {json.dumps(r['node_errors'])[:1500]}")
        jobs.append((i, r["prompt_id"]))
        log.info("cartoons: scene %d of %d queued on ComfyUI", i, len(ep.scenes))
    for i, pid in jobs:
        t0 = time.monotonic()
        while not (h := _comfy(f"/history/{pid}").get(pid)):
            time.sleep(20)
        if h["status"].get("status_str") != "success":
            raise RuntimeError(f"scene {i} failed on ComfyUI: {json.dumps(h['status'].get('messages', [])[-1:])[:1500]}")
        out = folder / f"scene{i:02d}"
        out.mkdir(exist_ok=True)
        for o in h["outputs"].values():
            for f in o.get("images", []):
                if f.get("type") == "output":
                    shutil.copy2(COMFY_DIR / "output" / f["subfolder"] / f["filename"], out / f["filename"])
        log.info("cartoons: scene %d rendered (%.1f min since the last)", i, (time.monotonic() - t0) / 60)
    return [p for i in range(1, len(ep.scenes) + 1) if (p := _rendered(folder, i))]


def _card(text: list[str], path: Path, size=(1152, 640)) -> Path:
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame

    pygame.font.init()
    s = pygame.Surface(size)
    s.fill((30, 60, 90))
    big, small = pygame.font.SysFont("arial", 72, bold=True), pygame.font.SysFont("arial", 34)
    for k, line in enumerate(text):
        f = big if k == 0 else small
        img = f.render(line, True, (250, 240, 200))
        s.blit(img, img.get_rect(center=(size[0] // 2, size[1] // 2 - 40 + k * 70)))
    pygame.image.save(s, str(path))
    return path


def assemble(folder: Path) -> Path:
    """The title card, every scene in order, the end card: one film, at the scenes' size, 24 fps."""
    series = SERIES[folder.parent.name]
    ep = Episode.model_validate_json((folder / "episode.json").read_text(encoding="utf-8"))
    clips = [sorted((folder / f"scene{i:02d}").glob("*.mp4"))[-1] for i in range(1, len(ep.scenes) + 1)]
    title = _card([series.title, ep.title], folder / "title.png")
    end = _card([series.title, "on channel seven"], folder / "end.png")
    w, h = (int(x) for x in RESOLUTION.split("x"))
    args, parts, i = [], [], 0          # i: the next input's index (a card is two inputs, a scene one)
    for k, (src, still) in enumerate([(title, True), *((c, False) for c in clips), (end, True)]):
        if still:
            args += ["-loop", "1", "-t", "3", "-i", str(src), "-f", "lavfi", "-t", "3", "-i",
                     "anullsrc=channel_layout=stereo:sample_rate=44100"]
            v, a, i = i, i + 1, i + 2
        elif (track := folder / f"scene{k:02d}.dialogue.wav").exists():   # our sound, not H3's copy of it
            args += ["-i", str(src), "-i", str(track)]
            v, a, i = i, i + 1, i + 2
        else:
            args += ["-i", str(src)]
            v, a, i = i, i, i + 1
        parts.append(f"[{v}:v]scale={w}:{h},fps={FPS},setsar=1[v{k}];[{a}:a]aresample=44100,"
                     f"aformat=channel_layouts=stereo[a{k}]")
    n = len(parts)
    graph = ";".join(parts) + ";" + "".join(f"[v{k}][a{k}]" for k in range(n)) + f"concat=n={n}:v=1:a=1[v][a]"
    film = folder / "episode.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args, "-filter_complex", graph, "-map", "[v]",
                    "-map", "[a]", "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", str(film)], check=True)
    return film


def ingest(folder: Path):
    from newsroom import bank

    ep = Episode.model_validate_json((folder / "episode.json").read_text(encoding="utf-8"))
    return bank.ingest(folder / "episode.mp4", "cartoons", folder.parent.name, ep.title)


def _cli() -> int:
    import argparse

    p = argparse.ArgumentParser(prog="python -m entertainment.cartoons")
    sub = p.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("plan")
    a.add_argument("--series", choices=sorted(SERIES), required=True)
    a.add_argument("--scenes", type=int, default=6)
    a.add_argument("--idea", default="")
    for cmd in ("render", "assemble", "ingest"):
        b = sub.add_parser(cmd)
        b.add_argument("folder", type=Path)
        if cmd == "render":
            b.add_argument("--dry-run", action="store_true")
            b.add_argument("--engine", choices=("comfy", "wan2gp"), default=None)
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    if args.cmd == "plan":
        print(plan(args.series, args.scenes, args.idea))
    elif args.cmd == "render":
        print(render(args.folder, args.dry_run, args.engine))
    elif args.cmd == "assemble":
        print(assemble(args.folder))
    else:
        print(ingest(args.folder))
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
