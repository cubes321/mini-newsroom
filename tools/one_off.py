"""A one-off programme outside the canon: a hand-written script, voiced and aired by the station's engine.

    uv run python tools/one_off.py voice   data/one_off/budget-2026
    uv run python tools/one_off.py preview data/one_off/budget-2026      # silent, fast, frames to preview/
    uv run python tools/one_off.py air     data/one_off/budget-2026 --obs
    uv run python tools/one_off.py cards   data/one_off/budget-2026 --video "E:/recordings/<the recording>.mp4"
    uv run python tools/one_off.py short   data/one_off/disco-steve --section "Steve's back" --from 2 --to 5

The folder holds `script.md` (the words, checked by a person: nothing here goes through a model) and
`special.toml` (the programme's name, the show whose bumper and set it borrows, and the cast; optionally
`closing`, the last lower third's subtitle, and a `[set]` of its own, see register_set). It gets
its own world, a copy of data/world.json made at the first `voice`, so a new guest's voice and look stay
the same from one run to the next, and the real town never hears of the programme. Voiced lines go in
its own `cache/`, keyed by speaker and text: change a line and only that line is voiced again.

script.md: `## Intro`, `## 1. Heading` ..., `## Outro`, each with lines `NAME: text` (NAME from the
cast), or `NAME (mood): text` to put one of models.MOOD_NAMES in their face. Anything after a line of
`---` (the figures check) is not read out. A guest may be dressed by hand with `[cast.X.look]`
(sprites.Look fields), for this programme only.

`air` opens the station's window, gives OBS a moment, then plays the bumper and the sections one after
another and stops. With `--obs` it records one file named after the programme, like `--obs` on a night.
Esc ends it early (and stops the recording).

`cards` puts a title card before that recording and an end card after it, for an upload: words from
`[cards]` in special.toml (title, subtitle, details, with, `end`, a list of lines, and `strips`, the
bands top and bottom: chequers, lights or none).

`short` makes a YouTube Short of some lines of one section with tools/shorts.py (vertical, big
captions), from the voiced lines, so it needs `voice` first and no recording.
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
SPOKEN = re.compile(r"^([A-Z][A-Z ]*[A-Z])(?:\s*\((\w+)\))?:\s+(.+)$")   # NAME: text, or NAME (mood): text


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


def look_for(who: dict):
    """A guest's own look from `[cast.X.look]` in special.toml (sprites.Look fields, colours as [r, g, b]), or None."""
    from newsroom.sprites import Look

    spec = who.get("look")
    if not spec:
        return None
    tup = lambda v: tuple(tup(x) for x in v) if isinstance(v, list) else v     # noqa: E731  Looks are hashed
    return Look(**{k: tup(v) for k, v in spec.items()})


def register_looks(spec: dict) -> None:
    """Guests dressed by hand for this programme: scenes asks guest_look for a guest's look by name, so that is
    wrapped for this run only, and the generated look still answers for everyone else."""
    from newsroom import scenes

    looks = {who["name"]: lk for who in spec["cast"].values() if who.get("name") and (lk := look_for(who))}
    if not looks:
        return
    base = scenes.guest_look
    scenes.guest_look = lambda name, *a, **k: looks.get((name or "").strip()) or base(name, *a, **k)
    say(f"looks: {', '.join(looks)}")


def parse(folder: Path) -> tuple[dict, list[tuple[str, list[tuple[str, str, str | None]]]]]:
    """special.toml, and script.md as [(heading, [(cast key, text, mood or None)])] in running order."""
    from newsroom.models import MOOD_NAMES             # models reads no config, so this is before redirect()

    spec = tomllib.loads((folder / "special.toml").read_text(encoding="utf-8"))
    sections: list[tuple[str, list[tuple[str, str, str | None]]]] = []
    for raw in (folder / "script.md").read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if line == "---":
            break
        if m := HEADING.match(line):
            sections.append((m.group(1), []))
        elif (m := SPOKEN.match(line)) and sections:
            if m.group(1) not in spec["cast"]:
                sys.exit(f"script.md: {m.group(1)!r} isn't in special.toml's cast")
            if m.group(2) and m.group(2) not in MOOD_NAMES:
                sys.exit(f"script.md: {m.group(2)!r} isn't a mood ({', '.join(MOOD_NAMES)})")
            sections[-1][1].append((m.group(1), m.group(3).strip(), m.group(2)))
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
        for key, text, mood in lines:
            who = spec["cast"][key]
            line = Line(speaker=who["speaker"], text=text, guest_name=who.get("name"),
                        guest_role=who.get("role"), mood=mood)
            h = line_hash(who, text)
            done += 1
            if h in have:                         # voiced before, word for word, in this voice
                have[h].mood = mood                # a mood is drawn, not voiced
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
    register_looks(spec)
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


TITLE_S, END_S = 5.0, 15.0     # YouTube's end screen wants 5 to 20 s at the end; the elements go on the right


def _card(spec: dict, kind: str):
    """The title or end card at 1920x1080, drawn on the 320x180 canvas like everything on air: the
    programme's set dimmed behind, chequers top and bottom, the roundel, the words from [cards]."""
    import pygame

    from newsroom import backdrops, logo, scenes

    c = spec.get("cards", {})
    show = spec["show"]
    canvas = pygame.Surface(scenes.CANVAS)
    set_id = (spec.get("set") or {}).get("id") if scenes.SET_OVERRIDE else None
    canvas.blit(backdrops.surface(set_id or "studio_interview"), (0, 0))
    shade = pygame.Surface(scenes.CANVAS, pygame.SRCALPHA)
    shade.fill((8, 10, 20, 170 if kind == "title" else 200))
    canvas.blit(shade, (0, 0))
    strips = c.get("strips", "chequers")                         # chequers (the F1 shows), lights, none
    lights = [(150, 60, 200), (230, 60, 150), (240, 190, 50), (60, 180, 100), (60, 170, 230)]
    for y in (0, 174) if strips != "none" else ():
        for i in range(0, 320, 6):
            k = i // 6
            if strips == "lights":                               # a light-up dance floor's tiles
                col = lights[(k + (y > 0) * 2) % len(lights)]
                pygame.draw.rect(canvas, col if k % 2 else tuple(v // 2 for v in col), (i, y, 6, 6))
            else:                                                # a chequered flag
                pygame.draw.rect(canvas, (235, 235, 235) if k % 2 else (20, 20, 24), (i, y, 6, 6))
    band = pygame.Surface((320, 22), pygame.SRCALPHA)
    band.fill((8, 10, 20, 210))
    canvas.blit(band, (0, 150))                                  # the wordmark's strip, off the desk's chequers
    accent = logo.colour(show)
    scenes._layer.clear()
    scenes._pictures.clear()
    cream, grey = (244, 238, 222), (180, 188, 205)
    if kind == "title":
        logo.draw_mark(canvas, 160, 32, show, r=18)
        pygame.draw.rect(canvas, (16, 18, 30), (36, 58, 248, 66))
        pygame.draw.rect(canvas, accent, (36, 58, 5, 66))
        scenes.text(canvas, c.get("title", spec["programme"]).upper(), 162, 62, 16, cream, center=True)
        if c.get("subtitle"):
            scenes.text(canvas, c["subtitle"], 162, 84, 14, cream, center=True)
        if c.get("details"):
            scenes.text(canvas, c["details"], 162, 106, 7, grey, center=True)
        scenes.text(canvas, f"with {c.get('with', spec['presenter'])}", 160, 134, 8, cream, center=True)
        scenes.text(canvas, logo.wordmark(), 160, 157, 7, grey, center=True)
    else:                                                        # the right half is left for YouTube's boxes
        logo.draw_mark(canvas, 44, 46, show, r=22)
        pygame.draw.rect(canvas, accent, (16, 80, 4, 52))
        lines = c.get("end", ["Thanks for watching"])
        scenes.text(canvas, lines[0].upper(), 26, 80, 12, cream)
        for i, s in enumerate(lines[1:]):
            scenes.text(canvas, s, 26, 100 + 12 * i, 8, grey)
        scenes.text(canvas, logo.wordmark(), 16, 157, 7, grey)
    screen = pygame.Surface((1920, 1080))
    scenes.present(canvas, screen)
    return screen


def cards(folder: Path, args) -> None:
    """A title card before an `air --obs` recording and an end card after it, for an upload. The
    recording's black pre-roll is cut; the station's bed plays under both cards. Writes '<video> - cards.mp4'."""
    import subprocess

    spec, _ = parse(folder)
    redirect(folder)
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    import pygame

    pygame.init()
    pygame.display.set_mode((1, 1))
    register_set(spec)
    video = args.video.resolve() if args.video else None
    out_dir = folder / "cards"
    out_dir.mkdir(exist_ok=True)
    pngs = {}
    for kind in ("title", "end"):
        pngs[kind] = out_dir / f"{kind}.png"
        pygame.image.save(_card(spec, kind), str(pngs[kind]))
    pygame.quit()
    say(f"cards: {pngs['title']}, {pngs['end']}")
    if args.cards_only:
        return
    probe = subprocess.run(["ffmpeg", "-hide_banner", "-i", str(video), "-vf", "blackdetect=d=0.3:pix_th=0.05",
                            "-an", "-t", "10", "-f", "null", "-"], capture_output=True, text=True).stderr
    m = re.search(r"black_start:0(?:\.0+)? black_end:([\d.]+)", probe)
    skip = float(m.group(1)) if m else 0.0                        # air's pre-roll while OBS got going
    bed = ROOT / "assets" / "music" / "bed.wav"
    T, E = TITLE_S, END_S
    graph = (
        f"[0:v]fps=30,format=yuv420p,setsar=1,fade=in:st=0:d=0.6[v0];"
        f"[1:v]trim=start={skip},setpts=PTS-STARTPTS,fps=30,scale=1920:1080:flags=neighbor,format=yuv420p,"
        f"setsar=1[v1];"
        f"[2:v]fps=30,format=yuv420p,setsar=1,fade=out:st={E - 1.5}:d=1.5[v2];"
        f"[3:a]atrim=0:{T},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,"
        f"afade=in:st=0:d=0.6,afade=out:st={T - 1.2}:d=1.2,volume=0.5[a0];"
        f"[1:a]atrim=start={skip},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo[a1];"
        f"[4:a]atrim=start=20:end={20 + E},asetpts=PTS-STARTPTS,aformat=sample_rates=48000:channel_layouts=stereo,"
        f"afade=in:st=0:d=1,afade=out:st={E - 3}:d=3,volume=0.5[a2];"
        f"[v0][a0][v1][a1][v2][a2]concat=n=3:v=1:a=1[v][a]")
    target = video.with_name(f"{video.stem} - cards{video.suffix}")
    cmd = ["ffmpeg", "-hide_banner", "-v", "error", "-y",
           "-loop", "1", "-t", str(T), "-i", str(pngs["title"]), "-i", str(video),
           "-loop", "1", "-t", str(E), "-i", str(pngs["end"]), "-i", str(bed), "-i", str(bed),
           "-filter_complex", graph, "-map", "[v]", "-map", "[a]",
           "-c:v", "libx264", "-preset", "slow", "-crf", "18", "-pix_fmt", "yuv420p",
           "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
           "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(target)]
    say(f"cutting {skip:.2f}s of pre-roll; encoding {target.name}")
    subprocess.run(cmd, check=True)
    say(f"saved {target}")


def short(folder: Path, args) -> None:
    """Some lines of one section as a Short: the section goes into `shorts/` in the folder as a cached segment,
    and tools/shorts.py draws it. Only models are imported here: shorts sets up its sandbox (a copy of this
    folder's world) before newsroom.config is first read, and asserts that it was."""
    import shorts

    from newsroom.models import Line, Segment, SegmentState, SegmentType

    spec, _ = parse(folder)
    data = json.loads((folder / "segments.json").read_text(encoding="utf-8"))
    if data["script"] != _script_hash(folder):
        sys.exit("script.md or special.toml changed since it was voiced: run `voice` again first")
    sec = next((s for s in data["sections"] if s["heading"] == args.section), None)
    if sec is None:
        sys.exit(f"no section {args.section!r}: {[s['heading'] for s in data['sections']]}")
    seg = Segment(slot_id=1, type=SegmentType.interview, show=spec["show"], state=SegmentState.ready,
                  headline=f"{spec['headline']}: {args.section}", part=args.section,
                  lines=[Line.model_validate(d) for d in sec["lines"]])
    cache = folder / "shorts"
    cache.mkdir(exist_ok=True)
    key = f"{folder.name}-" + "".join(c if c.isalnum() else "-" for c in args.section.lower()).strip("-")
    (cache / f"{key}.json").write_text(seg.model_dump_json(), encoding="utf-8")
    render = shorts._render

    def _render(path, a, tmp):                  # inside the sandbox: a hand-dressed guest's look, then draw
        register_looks(spec)
        return render(path, a, tmp)

    shorts._render = _render
    argv = ["render", key, "--from", str(args.first), "--cache", str(cache),
            "--title", args.title or spec["programme"]]
    if args.to is not None:
        argv += ["--to", str(args.to)]
    shorts.main(argv)


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("what", choices=("voice", "preview", "air", "cards", "short"))
    ap.add_argument("folder", type=Path)
    ap.add_argument("--obs", action="store_true", help="record it in OBS, one file named after the programme")
    ap.add_argument("--audio-device", default="", help="play into this output (e.g. 'CABLE Input')")
    ap.add_argument("--video", type=Path, help="cards: the air --obs recording to put the cards round")
    ap.add_argument("--cards-only", action="store_true", help="cards: draw the two PNGs, don't encode")
    ap.add_argument("--section", help="short: the section, by its heading in script.md")
    ap.add_argument("--from", dest="first", type=int, default=0, help="short: its first line, from 0")
    ap.add_argument("--to", type=int, help="short: its last line, included (default: the section's last)")
    ap.add_argument("--title", help="short: the title over the picture (default: the programme)")
    a = ap.parse_args()
    folder = a.folder.resolve()
    if a.what == "voice":
        voice(folder)
    elif a.what == "short":
        if not a.section:
            sys.exit("short needs --section <a heading from script.md>")
        short(folder, a)
    elif a.what == "cards":
        if not a.video and not a.cards_only:
            sys.exit("cards needs --video <the recording> (or --cards-only)")
        cards(folder, a)
    else:
        a.preview = a.what == "preview"
        air(folder, a)
    return 0


if __name__ == "__main__":
    sys.exit(main())
