"""A banked TV movie (entertainment/movies.py), cast, voiced ahead and played out on its own: the first half of the
movie's air step, which the station's 21:00 slot will reuse, and a way to record a film for watching.

    uv run python tools/film.py voice   data/movies/the-last-lot        # cast.toml if there is none, then every line
    uv run python tools/film.py preview data/movies/the-last-lot --scenes 1-3    # silent, fast: a frame a line
    uv run python tools/film.py air     data/movies/the-last-lot --obs  # the window, recorded by OBS

The film's folder gets its own copy of the world and its own cache (as tools/one_off.py does), so the town never hears
of it and the station's cache pruning never takes its voices. The opening titles go before the first scene and the end
credits after the last (entertainment/movie_cards.py), when those scenes are played; --no-cards leaves them off. The parts are pinned by name (cast.toml: a voice from the
guest pool each, by gender and age; a look drawn from the name unless dressed by hand), never residents. `voice` reads
script.md as it stands, so hand edits are voiced; a changed line, or a recast part, is voiced again and nothing else.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "tools"))
from one_off import redirect, say  # noqa: E402  (stdlib only at import: newsroom.config is read after redirect)


def _script_hash(folder: Path) -> str:
    """What the voicing depends on: the script, and each part's voice and speed (a look or a credit can change
    in cast.toml without the film being voiced again)."""
    import tomllib

    cast = tomllib.loads((folder / "cast.toml").read_text(encoding="utf-8"))
    voices = json.dumps({n: [c["voice"], c.get("speed", 1.0)] for n, c in sorted(cast.items())})
    return hashlib.sha1((folder / "script.md").read_bytes() + voices.encode("utf-8")).hexdigest()


def _setup(folder: Path):
    """The film, its cast (written if missing) and its show on the engine; after redirect()."""
    from entertainment import movies as M

    film = M.load(folder)
    if not (folder / "cast.toml").exists():
        (folder / "cast.toml").write_text(M.cast_toml(M.cast(film)), encoding="utf-8")
        say(f"cast: wrote {folder / 'cast.toml'}")
    cast = M.load_cast(folder)
    for name, c in cast.items():
        say(f"cast: {name} speaks as {c['voice']} ({c['gender']}, {c['age']})")
    M.register_film(cast, film["outline"]["title"])
    return M, film, cast


def voice(folder: Path, only: str | None = None) -> None:
    redirect(folder)
    M, film, cast = _setup(folder)
    from newsroom import tts, workers, world as world_mod
    from newsroom.models import Line

    world = world_mod.load()
    _, scenes = M.parse(folder / "script.md")
    scenes = [s for s in scenes if s.number in _range(only, len(scenes))]
    have = _voiced(folder)
    # A whole run starts segments.json afresh (every clip still reused by its key), so a script that has lost scenes
    # leaves none of its old numbers behind; a run of some scenes merges into what is there.
    kept = {s["number"]: s for s in _scenes_voiced(folder)} if only else {}
    tts.preload()
    out, n, done = [], sum(len(s.lines) for s in scenes), 0
    for sc in scenes:
        keys, lines = [], []
        for who, text, mood in sc.lines:
            key = M.line_key(cast[who], who, text)
            line = Line(speaker="guest", text=text, guest_name=who, mood=mood or None)
            done += 1
            if key in have:                       # voiced before, word for word, in this voice
                have[key].mood = mood or None     # a mood is drawn, not voiced
                line = have[key]
            else:
                t0 = time.perf_counter()
                workers.voice_line(line, 0, world, key)
                say(f"[{done}/{n}] scene {sc.number} {who.split()[0]} {line.duration_s:5.1f}s "
                    f"({time.perf_counter() - t0:.0f}s)  {text[:50]}")
            keys.append(key)
            lines.append(line)
        out.append({"number": sc.number, "set": sc.set, "when": sc.when, "characters": sc.characters, "keys": keys,
                    "lines": [json.loads(l.model_dump_json()) for l in lines]})
        kept[sc.number] = out[-1]
        _write(folder, [kept[k] for k in sorted(kept)])     # as it goes: a stopped run keeps what it voiced
    total = sum(l["duration_s"] or 0 for s in out for l in s["lines"])
    say(f"voiced {n} lines, {total / 60:.1f} minutes, in {folder / 'segments.json'}")


def _write(folder: Path, scenes: list) -> None:
    (folder / "segments.json").write_text(json.dumps({"script": _script_hash(folder), "scenes": scenes}, indent=1),
                                          encoding="utf-8")


def _scenes_voiced(folder: Path) -> list:
    if not (folder / "segments.json").exists():
        return []
    return json.loads((folder / "segments.json").read_text(encoding="utf-8"))["scenes"]


def _voiced(folder: Path) -> dict:
    from newsroom.models import Line

    if not (folder / "segments.json").exists():
        return {}
    got = {}
    for s in json.loads((folder / "segments.json").read_text(encoding="utf-8"))["scenes"]:
        for k, d in zip(s["keys"], s["lines"]):
            l = Line.model_validate(d)
            if l.wav_path and Path(l.wav_path).exists():
                got[k] = l
    return got


def _range(spec: str | None, top: int) -> set[int]:
    if not spec:
        return set(range(1, top + 1))
    lo, _, hi = spec.partition("-")
    return set(range(int(lo), int(hi or lo) + 1))


def segments(folder: Path, M, which: set[int], title: str, cast: dict, cards: bool = True, only_cards: bool = False):
    """The scenes in `which`, with the opening titles before the first scene and the end credits after the last
    (when those are in `which`, and `cards`); `only_cards`: the titles and credits and no scenes."""
    from entertainment import movie_cards
    from newsroom.config import CONFIG
    from newsroom.models import Line

    data = json.loads((folder / "segments.json").read_text(encoding="utf-8"))
    if data["script"] != _script_hash(folder):
        sys.exit("script.md or cast.toml changed since it was voiced: run `voice` again first")
    every = data["scenes"]
    chosen = [] if only_cards else [s for s in every if s["number"] in which]
    out = []
    if only_cards or (cards and chosen and chosen[0] is every[0]):
        out.append(movie_cards.titles_segment(0, M.SHOW, title, every[0], CONFIG.paths.cache))
    out += [M.scene_segment(len(out) + i, s, [Line.model_validate(d) for d in s["lines"]]) for i, s in enumerate(chosen)]
    if only_cards or (cards and chosen and chosen[-1] is every[-1]):
        sets = list(dict.fromkeys(s["set"] for s in every))
        out.append(movie_cards.credits_segment(len(out), M.SHOW, title, cast, sets, CONFIG.paths.cache))
    return out


def air(folder: Path, args) -> None:
    redirect(folder)
    if args.preview:
        os.environ["SDL_VIDEODRIVER"] = "dummy"
        os.environ["SDL_AUDIODRIVER"] = "dummy"
    import pygame

    M, film, cast = _setup(folder)
    from newsroom import scenes, world as world_mod
    from newsroom.__main__ import open_audio
    from newsroom.buffer import Buffer
    from newsroom.config import CONFIG
    from newsroom.models import SegmentState
    from newsroom.player import Player

    title = film["outline"]["title"]
    if args.preview:
        pygame.init()
    else:
        open_audio(CONFIG, args.audio_device or CONFIG.broadcast.audio_device)
    screen = pygame.display.set_mode((CONFIG.broadcast.width, CONFIG.broadcast.height))
    pygame.display.set_caption("Mini Newsroom")
    canvas = pygame.Surface(scenes.CANVAS)
    clock = pygame.time.Clock()

    world = world_mod.load()                     # the film's copy, never saved from here
    buffer = Buffer()
    segs = segments(folder, M, _range(args.scenes, 999), title, cast, cards=not args.no_cards,
                    only_cards=args.only_cards)
    for s in segs:
        buffer.mark(s, SegmentState.ready)
    last = segs[-1].slot_id
    total = sum(s.duration_s for s in segs)
    player = Player(buffer, world, None, audio=not args.preview)
    player._gap_item = lambda now: None          # nothing after the end: it just stops
    say(f"{title}: {len(segs)} items, {total / 60:.1f} minutes")

    rec = None
    if args.obs:
        from newsroom.obs import Off, Recorder

        try:
            rec = Recorder(False, say)
        except Off as e:
            sys.exit(str(e))

    snaps = folder / "preview"
    if args.preview:
        shutil.rmtree(snaps, ignore_errors=True)
        snaps.mkdir(exist_ok=True)               # rmtree can leave it, if something has it open
        for old in snaps.glob("*.png"):
            old.unlink(missing_ok=True)
    step = 1 / CONFIG.broadcast.fps
    start_wall, sim, t_start = time.time(), 0.0, time.monotonic()
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
                    rec.start(title)
                    recording = True
                if t < preroll:                  # black while OBS gets going
                    screen.fill((0, 0, 0))
                    pygame.display.flip()
                    clock.tick(CONFIG.broadcast.fps)
                    continue
                started = True
                say("on air")
            player.update(now)
            if player.current is None and player.next_slot > last:
                break
            scenes.render(canvas, player.view(now), t)
            scenes.present(canvas, screen)
            pygame.display.flip()
            if args.preview:
                cur = player.current
                if cur and cur.work.get("card"):      # the titles and credits: a frame every two seconds
                    key = (cur.slot_id, int((now - player.line_start) / 2.0))
                    settled = True
                else:
                    key = (cur.slot_id, player.line_idx) if cur else (-1, -1)
                    settled = cur is not None and now - player.line_start > 1.5   # once its shot has settled
                if cur and key not in seen and settled:
                    seen.add(key)
                    pygame.image.save(screen, str(snaps / f"{cur.slot_id:02d}_{key[1]:02d}.png"))
                sim += step
            else:
                clock.tick(CONFIG.broadcast.fps)
        say("off air")
        if not args.preview:
            hold = time.monotonic()
            while time.monotonic() - hold < 2.0:  # hold the last picture a moment, then stop
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


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("cmd", choices=("voice", "preview", "air"))
    ap.add_argument("folder")
    ap.add_argument("--scenes", help="voice/preview/air only these scenes, e.g. 1-3 or 7")
    ap.add_argument("--obs", action="store_true", help="air: record it with OBS")
    ap.add_argument("--audio-device", help="air: the output device (default: config.toml's)")
    ap.add_argument("--no-cards", action="store_true", help="preview/air: no opening titles or end credits")
    ap.add_argument("--only-cards", action="store_true", help="preview/air: the opening titles and end credits alone")
    a = ap.parse_args()
    folder = Path(a.folder).resolve()
    if not (folder / "script.md").exists():
        sys.exit(f"no script.md in {folder}")
    if a.cmd == "voice":
        voice(folder, a.scenes)
    else:
        a.preview = a.cmd == "preview"
        air(folder, a)


if __name__ == "__main__":
    main()
