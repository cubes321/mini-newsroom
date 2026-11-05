"""A one-off programme outside the canon: a hand-written script, voiced and aired by the station's engine.

    uv run python tools/one_off.py voice   data/one_off/budget-2026
    uv run python tools/one_off.py preview data/one_off/budget-2026      # silent, fast, frames to preview/
    uv run python tools/one_off.py air     data/one_off/budget-2026 --obs

The folder holds `script.md` (the words, checked by a person: nothing here goes through a model) and
`special.toml` (the programme's name, the show whose bumper and set it borrows, and the cast; optionally
`closing`, the last lower third's subtitle, and a `[set]` of its own, see register_set). It gets
its own world, a copy of data/world.json made at the first `voice`, so a new guest's voice and look stay
the same from one run to the next, and the real town never hears of the programme. Voiced lines go in
its own `cache/`, keyed by speaker and text: change a line and only that line is voiced again.

script.md: `## Intro`, `## 1. Heading` ..., `## Outro`, each with lines `NAME: text` (NAME from the
cast). Anything after a line of `---` (the figures check) is not read out.

`air` opens the station's window, gives OBS a moment, then plays the bumper and the sections one after
another and stops. With `--obs` it records one file named after the programme, like `--obs` on a night.
Esc ends it early (and stops the recording).
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import time
import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
say = lambda s: print(s, flush=True)                    # noqa: E731

HEADING = re.compile(r"^##\s+(?:\d+\.\s*)?(.+?)\s*$")
SPOKEN = re.compile(r"^([A-Z][A-Z ]*[A-Z]):\s+(.+)$")


def redirect(folder: Path) -> None:
    """The programme's own world, cache and pools. Before newsroom.config is imported: CONFIG reads these."""
    world = folder / "world.json"
    if not world.exists():
        shutil.copy2(ROOT / "data" / "world.json", world)
        say(f"world: copied data/world.json to {world}")
    for env, path in {"NEWSROOM_WORLD": world, "NEWSROOM_CACHE": folder / "cache",
                      "NEWSROOM_TIPLINE": folder / "tipline.txt", "NEWSROOM_ADS": folder / "ads",
                      "NEWSROOM_CONTINUITY": folder / "continuity",
                      "NEWSROOM_LLM_CALLS": folder / "llm_calls"}.items():
        os.environ[env] = str(path)


def register_set(spec: dict) -> None:
    """A set of the programme's own ([set] in special.toml: id, name, host and guest marks), its art in
    assets/backdrops/<id>.png. Registered for this run only, so newsroom/locations.py, and with it every
    list the writers see, never hears of it. No art yet: the borrowed show's set, with a warning."""
    s = spec.get("set")
    if not s:
        return
    from newsroom import locations, scenes

    if not (ROOT / "assets" / "backdrops" / f"{s['id']}.png").exists():
        say(f"set: no assets/backdrops/{s['id']}.png yet, so {spec['show']}'s set stands in")
        return
    locations.BY_ID[s["id"]] = locations.Location(s["id"], s.get("name", s["id"]), s.get("name", s["id"]),
                                                  "studio", (28, 34, 60), (60, 50, 48))
    locations.MARKS[s["id"]] = {k: tuple(s[k]) for k in ("host", "guest")}
    scenes.SET_OVERRIDE = s["id"]
    say(f"set: {s['id']}")


def parse(folder: Path) -> tuple[dict, list[tuple[str, list[tuple[str, str]]]]]:
    """special.toml, and script.md as [(heading, [(cast key, text)])] in running order."""
    spec = tomllib.loads((folder / "special.toml").read_text(encoding="utf-8"))
    sections: list[tuple[str, list[tuple[str, str]]]] = []
    for raw in (folder / "script.md").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "---":
            break
        if m := HEADING.match(line):
            sections.append((m.group(1), []))
        elif (m := SPOKEN.match(line)) and sections:
            if m.group(1) not in spec["cast"]:
                sys.exit(f"script.md: {m.group(1)!r} isn't in special.toml's cast")
            sections[-1][1].append((m.group(1), m.group(2).strip()))
    sections = [s for s in sections if s[1]]
    if not sections:
        sys.exit("script.md: no spoken lines (NAME: text under ## headings)")
    return spec, sections


def line_hash(who: dict, text: str) -> str:
    key = f"{who['speaker']}|{who.get('name', '')}|{text}"
    if who.get("voice"):
        key = f"{who['voice']}|{key}"                # a recast voices them again
    return "oneoff_" + hashlib.sha1(key.encode()).hexdigest()[:12]


def voice(folder: Path) -> None:
    spec, sections = parse(folder)
    redirect(folder)
    from newsroom import tts, workers, world as world_mod
    from newsroom.models import Line

    world = world_mod.load()
    for who in spec["cast"].values():
        if who["speaker"] == "guest":
            p = world.ensure_person(who["name"], who.get("role"), gender=who.get("gender"), age=who.get("age"),
                                    accent=who.get("accent"))
            if p and who.get("voice"):
                p.voice = who["voice"]            # cast by hand (assets/voices/voices.toml), not from the pool
            say(f"cast: {who['name']} speaks as {world.voice_for('guest', who['name'])}")
    world_mod.save(world)                         # the guest keeps this voice (and look) on air
    tts.preload()
    out, n, done = [], sum(len(s[1]) for s in sections), 0
    have = _voiced_lines(folder) if (folder / "segments.json").exists() else {}
    for heading, lines in sections:
        voiced = []
        for key, text in lines:
            who = spec["cast"][key]
            line = Line(speaker=who["speaker"], text=text, guest_name=who.get("name"),
                        guest_role=who.get("role"))
            h = line_hash(who, text)
            done += 1
            if h in have:                         # voiced before, word for word, in this voice
                voiced.append((h, have[h]))
                continue
            t0 = time.perf_counter()
            workers.voice_line(line, 0, world, h)
            say(f"[{done}/{n}] {key} {line.duration_s:5.1f}s ({time.perf_counter() - t0:.0f}s)  {text[:60]}")
            voiced.append((h, line))
        out.append({"heading": heading, "keys": [h for h, _ in voiced],
                    "lines": [json.loads(l.model_dump_json()) for _, l in voiced]})
    (folder / "segments.json").write_text(json.dumps({"script": _script_hash(folder), "sections": out}, indent=1),
                                          encoding="utf-8")
    total = sum(l["duration_s"] or 0 for s in out for l in s["lines"])
    say(f"voiced {n} lines, {total / 60:.1f} minutes, in {folder / 'segments.json'}")


def _script_hash(folder: Path) -> str:
    return hashlib.sha1((folder / "script.md").read_bytes() + (folder / "special.toml").read_bytes()).hexdigest()


def _voiced_lines(folder: Path) -> dict:
    from newsroom.models import Line

    data = json.loads((folder / "segments.json").read_text(encoding="utf-8"))
    got = {}
    for s in data["sections"]:
        for h, d in zip(s.get("keys", []), s["lines"]):      # the key it was voiced under, not today's
            l = Line.model_validate(d)
            if l.wav_path and Path(l.wav_path).exists():
                got[h] = l
    return got


def segments(folder: Path, spec: dict):
    """The bumper and one studio interview per section, ready to air, in slots 0, 1, 2 ..."""
    from newsroom.assets import bumper_segment
    from newsroom.models import Line, Segment, SegmentState, SegmentType, VisualCue

    data = json.loads((folder / "segments.json").read_text(encoding="utf-8"))
    if data["script"] != _script_hash(folder):
        sys.exit("script.md or special.toml changed since it was voiced: run `voice` again first")
    show, title = spec["show"], spec["headline"]
    segs = [bumper_segment(Segment(slot_id=0, type=SegmentType.bumper, show=show))]
    n = len(data["sections"])
    for i, s in enumerate(data["sections"]):
        lines = [Line.model_validate(d) for d in s["lines"]]
        heading = s["heading"]
        first = lines[0].duration_s or 0.0
        if i == 0:                                # the presenter's name, then the programme's
            lt = {"title": spec["presenter"], "subtitle": spec["programme"]}
        elif i == n - 1:
            lt = {"title": spec["programme"], "subtitle": spec.get("closing", "A summary, not advice")}
        else:
            lt = {"title": title, "subtitle": heading}
        cues = [VisualCue(at_s=0.0, kind="lower_third", payload=lt),
                VisualCue(at_s=max(first, 6.0), kind="lower_third", payload={})]
        headline = title if i in (0, n - 1) else f"{title}: {heading}"
        segs.append(Segment(slot_id=i + 1, type=SegmentType.interview, show=show, state=SegmentState.ready,
                            headline=headline, lines=lines, cues=cues, part=heading))
    return segs


def air(folder: Path, args) -> None:
    spec, _ = parse(folder)
    redirect(folder)
    if args.preview:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    import pygame

    from newsroom import scenes, world as world_mod
    from newsroom.__main__ import open_audio
    from newsroom.buffer import Buffer
    from newsroom.config import CONFIG
    from newsroom.models import SegmentState
    from newsroom.player import Player

    if args.preview:
        pygame.init()
    else:
        open_audio(CONFIG, args.audio_device or CONFIG.broadcast.audio_device)
    screen = pygame.display.set_mode((CONFIG.broadcast.width, CONFIG.broadcast.height))
    pygame.display.set_caption("Mini Newsroom")
    canvas = pygame.Surface(scenes.CANVAS)
    clock = pygame.time.Clock()

    world = world_mod.load()                    # the programme's copy, never saved from here
    register_set(spec)
    buffer = Buffer()
    segs = segments(folder, spec)
    for s in segs:
        buffer.mark(s, SegmentState.ready)
    last = segs[-1].slot_id
    total = sum(s.duration_s for s in segs)
    player = Player(buffer, world, None, audio=not args.preview)
    player._gap_item = lambda now: None         # no adverts or idents after the end: it just stops
    say(f"{spec['programme']}: {len(segs)} segments, {total / 60:.1f} minutes")

    rec = None
    if args.obs:
        from newsroom.obs import Off, Recorder

        try:
            rec = Recorder(False, say)
        except Off as e:
            sys.exit(str(e))

    def frame(t: float, now: float, draw: bool = True) -> None:
        if draw:
            scenes.render(canvas, player.view(now), t)
            scenes.present(canvas, screen)
        pygame.display.flip()

    snaps = folder / "preview"
    if args.preview:
        shutil.rmtree(snaps, ignore_errors=True)
        snaps.mkdir()
    step = 1 / CONFIG.broadcast.fps
    start_wall, sim = time.time(), 0.0
    t_start = time.monotonic()
    preroll = 0.0 if args.preview else 3.0
    started = recording = False
    seen: set[tuple[int, int]] = set()
    try:
        while True:
            if not args.preview:
                for ev in pygame.event.get():
                    if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                        raise KeyboardInterrupt
            t = sim if args.preview else time.monotonic() - t_start
            now = start_wall + t
            if not started:
                if rec and not recording:
                    rec.start(spec["programme"])
                    recording = True
                if t < preroll:                  # black while OBS gets going
                    screen.fill((0, 0, 0))
                    frame(t, now, draw=False)
                    clock.tick(CONFIG.broadcast.fps)
                    continue
                started = True
                say("on air")
            player.update(now)
            if player.current is None and player.next_slot > last:
                break
            frame(t, now)
            if args.preview:
                cur = player.current
                key = (cur.slot_id, player.line_idx) if cur else (-1, -1)
                if key not in seen and now - player.line_start > 1.5:
                    seen.add(key)            # a frame per line, once its shot has settled
                    pygame.image.save(screen, str(snaps / f"{cur.slot_id:02d}_{player.line_idx:02d}.png"))
                sim += step
            else:
                clock.tick(CONFIG.broadcast.fps)
        say("off air")
        if not args.preview:
            hold = time.monotonic()
            while time.monotonic() - hold < 2.0:     # hold the last picture a moment, then stop
                pygame.event.pump()
                clock.tick(CONFIG.broadcast.fps)
    except KeyboardInterrupt:
        say("stopped early")
    finally:
        if rec and recording:
            rec.stop()
        pygame.quit()
    if args.preview:
        say(f"preview frames in {snaps}")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=("voice", "preview", "air"))
    ap.add_argument("folder", type=Path)
    ap.add_argument("--obs", action="store_true", help="record it in OBS, one file named after the programme")
    ap.add_argument("--audio-device", default="", help="play into this output (e.g. 'CABLE Input')")
    a = ap.parse_args()
    folder = a.folder.resolve()
    if a.what == "voice":
        voice(folder)
    else:
        a.preview = a.what == "preview"
        air(folder, a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
