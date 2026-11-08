"""YouTube Shorts from segments that have aired: re-rendered from the cache, not cut from a recording.

    uv run python tools/shorts.py list --show coastwide --speaker mag_b
    uv run python tools/shorts.py list --type call --text "bin collection"
    uv run python tools/shorts.py render 001453b9537bca0e --from 2 --to 5 --title "Dolores Finch's chips"

A segment in data/cache/<hash>.json keeps its lines with their voiced WAVs, durations and mouth
envelopes, and its visual cues: enough to draw it again, frame by frame, headless, at any size. `render`
keeps lines N..M (as `list` numbers them), draws them as the station did (the same Player.view and
scenes.render, without the station's own lower third, ticker and clock), and lays the 960x540
picture in a 1080x1920 frame: the show and the programme's title above, big captions below, one
script line at a time, and a short slate at the end. The line WAVs play back to back with the music
bed under them at its on-air level, and ffmpeg writes H.264 + AAC at 30 fps.

Nothing is saved to the town: the player gets a copy of the world in a temporary folder (and its
cache, ads and continuity pools are pointed there too), and the player's own update() is never
called, so no segment is ever marked aired. `--cache DIR` reads another cache, a scratch run's say:
its world.json alongside, when there is one, gives the guests their faces from that run.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
say = lambda s: print(s, flush=True)                    # noqa: E731

CACHE = ROOT / "data" / "cache"
OUT = Path("E:/recordings/shorts")
BED = ROOT / "assets" / "music" / "bed.wav"
BED_VOLUME = 0.06               # under a live segment, as on air (player.py _play_line)

W, H = 1080, 1920               # the Short
PIC = (960, 540)                # the 320x180 canvas, three times over
PIC_AT = ((W - PIC[0]) // 2, 700)
FPS = 30
SLATE_S = 1.5
SLATE_WORDS = ("Port Wexley", "live on YouTube & Twitch")

CAPTION_TOP = PIC_AT[1] + PIC[1] + 80     # the speaker's name, then the words under it
CAPTION_W = W - 2 * 70
CAPTION_PX, NAME_PX = 66, 46
CAPTION_ROWS = 4                          # a longer line runs over several pages of captions
# The speakers in a clip, in the order they first speak: bright on the dark ground, apart from each other.
SPEAKER_COLOURS = [(255, 214, 90), (110, 214, 255), (255, 140, 120), (150, 235, 140), (215, 160, 255)]


# ------------------------------------------------------------------ pure parts (tests/test_shorts.py)


def trim(seg, first: int, last: int):
    """A copy of `seg` with only lines first..last (inclusive), its cues moved so the clip starts at 0.

    A cue is state that holds until the next of its kind (the backdrop, the map, the lower third), so
    the last cue of each kind at or before the cut carries on into the clip, at 0; the cues inside the
    clip move back by the time cut off the front; the ones after the clip ends are dropped."""
    if not 0 <= first <= last < len(seg.lines):
        raise ValueError(f"lines {first}..{last}: the segment has lines 0..{len(seg.lines) - 1}")
    offset = sum(l.duration_s or 0.0 for l in seg.lines[:first])
    end = offset + sum(l.duration_s or 0.0 for l in seg.lines[first:last + 1])
    held: dict[str, object] = {}
    inside = []
    for c in sorted(seg.cues, key=lambda c: c.at_s):
        if c.at_s <= offset + 1e-6:
            held[c.kind] = c                          # the latest of each kind wins
        elif c.at_s < end - 1e-6:
            inside.append(c.model_copy(update={"at_s": round(c.at_s - offset, 3)}))
    carried = [c.model_copy(update={"at_s": 0.0}) for c in held.values()]
    return seg.model_copy(update={"lines": [l.model_copy() for l in seg.lines[first:last + 1]],
                                  "cues": carried + inside})


def line_starts(lines) -> list[float]:
    """When each line starts, back to back with no gap: a cumulative sum of the durations."""
    out, t = [], 0.0
    for l in lines:
        out.append(t)
        t += l.duration_s or 0.0
    return out


def line_at(starts: list[float], t: float) -> int:
    """The line playing at time `t`: the last one started by then."""
    i = 0
    for k, s in enumerate(starts):
        if s <= t + 1e-9:
            i = k
    return i


def wrap(text: str, width: int, measure) -> list[str]:
    """Greedy word wrap; `measure(s)` is the pixel width of s. A word too long for a row gets one of its own."""
    rows, cur = [], ""
    for word in text.split():
        trial = f"{cur} {word}".strip()
        if measure(trial) <= width or not cur:
            cur = trial
        else:
            rows.append(cur)
            cur = word
    if cur:
        rows.append(cur)
    return rows


@dataclass
class Caption:
    start: float
    end: float
    speaker: str              # the speaker id, for the colour
    name: str                 # what the caption calls them
    rows: list[str]


def pages(rows: list[str], max_rows: int) -> list[list[str]]:
    """Rows in pages of at most max_rows, as even as they'll go (5 rows in pages of 4 -> 3 + 2, not 4 + 1)."""
    if not rows:
        return [[]]
    n = math.ceil(len(rows) / max_rows)
    size = math.ceil(len(rows) / n)
    return [rows[i:i + size] for i in range(0, len(rows), size)]


def captions(lines, names: list[str], width: int, measure, max_rows: int = CAPTION_ROWS) -> list[Caption]:
    """The clip's captions: each line from its start for its duration_s, split into pages when it is too
    long for one, each page on screen for its share of the line's words."""
    out = []
    for line, name, start in zip(lines, names, line_starts(lines)):
        dur = line.duration_s or 0.0
        ps = pages(wrap(line.text, width, measure), max_rows)
        words = [max(1, sum(len(r.split()) for r in p)) for p in ps]
        total, t = sum(words), start
        for p, n in zip(ps, words):
            share = dur * n / total
            out.append(Caption(t, t + share, line.speaker, name, p))
            t += share
        out[-1].end = start + dur                     # no float drift: the last page ends with the line
    return out


def caption_at(caps: list[Caption], t: float) -> Caption | None:
    for c in caps:
        if c.start <= t < c.end:
            return c
    return None


def speaker_colours(lines) -> dict[str, tuple[int, int, int]]:
    """A colour per speaker (a guest per name), in the order they first speak."""
    out: dict[str, tuple[int, int, int]] = {}
    for l in lines:
        key = who(l)
        if key not in out:
            out[key] = SPEAKER_COLOURS[len(out) % len(SPEAKER_COLOURS)]
    return out


def who(line) -> str:
    return f"guest:{line.guest_name}" if line.speaker == "guest" else line.speaker


# ------------------------------------------------------------------------------------------- list


def _index(cache: Path):
    """Every segment in the cache as plain JSON, newest first. Imports nothing from the station."""
    segs = []
    for f in cache.glob("*.json"):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if isinstance(d, dict) and d.get("lines"):
            segs.append((f.stem, d))
    segs.sort(key=lambda hd: hd[1].get("nominal_start_ts") or 0.0, reverse=True)
    return segs


SHOW_TITLES = {"news": "port wexley news", "breakfast": "morning tide", "magazine": "coastwide",
               "late": "the last ferry", "sport": "full time", "quayside": "quayside", "phonein": "have your say",
               "outabout": "out and about", "rockpool": "rock pool", "panel": "the panel", "chamber": "the chamber",
               "inquiry": "the inquiry", "overnight": "overnight"}     # so `--show coastwide` finds `magazine`


def _show_matches(want: str, show: str | None) -> bool:
    want = want.lower().replace("_", " ").strip()
    show = show or ""
    return want == show.lower() or want in SHOW_TITLES.get(show, "")


def _speaker_label(l: dict) -> str:
    return f"guest ({l.get('guest_name')})" if l.get("speaker") == "guest" else str(l.get("speaker"))


def cmd_list(args) -> None:
    cache = Path(args.cache) if args.cache else CACHE
    shown = 0
    for h, d in _index(cache):
        lines = d["lines"]
        if args.show and not _show_matches(args.show, d.get("show")):
            continue
        if args.type and d.get("type") != args.type:
            continue
        if args.speaker and not any(args.speaker.lower() in (l.get("speaker") or "").lower()
                                    or args.speaker.lower() in (l.get("guest_name") or "").lower() for l in lines):
            continue
        if args.text:
            hay = " ".join([d.get("headline") or ""] + [l.get("text") or "" for l in lines]).lower()
            if args.text.lower() not in hay:
                continue
        when = time.strftime("%Y-%m-%d %H:%M", time.localtime(d.get("nominal_start_ts") or 0))
        total = sum(l.get("duration_s") or 0.0 for l in lines)
        say(f"{h}  {d.get('show')}/{d.get('type')}  {when}  {total:.0f}s  {d.get('headline') or d.get('brief') or ''}")
        for i, l in enumerate(lines):
            say(f"  {i:>2}  {_speaker_label(l)}: {l.get('text')} ({l.get('duration_s') or 0:.1f}s)")
        say("")
        shown += 1
        if shown >= args.limit:
            say(f"(first {args.limit}, newest first: --limit for more)")
            break
    if not shown:
        say("nothing matches")


# ----------------------------------------------------------------------------------------- render


def _find(cache: Path, key: str) -> Path:
    exact = cache / f"{key}.json"
    if exact.exists():
        return exact
    hits = sorted(cache.glob(f"{key}*.json"))
    if len(hits) != 1:
        sys.exit(f"{key}: {'no segment' if not hits else f'{len(hits)} segments'} in {cache} start with that")
    return hits[0]


def _sandbox(cache: Path) -> Path:
    """A temporary world, cache and pools for the player, set before newsroom.config is imported (CONFIG
    reads these): the real data/world.json is never written from here."""
    tmp = Path(tempfile.mkdtemp(prefix="shorts-"))
    world = cache.parent / "world.json"                 # a scratch run's own world, where it has one
    if not world.exists() or cache.resolve() == CACHE.resolve():
        world = ROOT / "data" / "world.json"
    shutil.copy2(world, tmp / "world.json")
    for env, path in {"NEWSROOM_WORLD": tmp / "world.json", "NEWSROOM_CACHE": tmp / "cache",
                      "NEWSROOM_TIPLINE": tmp / "tipline.txt", "NEWSROOM_ADS": tmp / "ads",
                      "NEWSROOM_CONTINUITY": tmp / "continuity", "NEWSROOM_LLM_CALLS": tmp / "llm_calls",
                      "NEWSROOM_CONTROL": tmp / "control"}.items():
        os.environ[env] = str(path)
    os.environ["SDL_VIDEODRIVER"] = "dummy"
    os.environ["SDL_AUDIODRIVER"] = "dummy"
    return tmp


def _check_words(texts: list[str]) -> None:
    """The station's word check on everything the Short shows or says: a hit, and nothing is rendered."""
    try:
        from newsroom import safety
    except ImportError:
        # TODO(safety): newsroom/safety.py isn't here; check the words with it once it lands.
        say("WARNING: no newsroom.safety: the words have not been checked")
        return
    if bad := safety.check(texts):
        sys.exit(f"refused: {bad!r} is on the safety list; pick other lines")


def _names(seg, world) -> list[str]:
    out = []
    for l in seg.lines:
        if l.speaker == "guest":
            out.append(l.guest_name or "Guest")
        elif l.speaker == "voiceover":
            out.append("")
        else:
            c = world.character(l.speaker)
            out.append(c.name if c else l.speaker)
    return out


def _ffmpeg(out: Path, seg, total: float) -> list[str]:
    """Raw RGB frames on stdin; the line WAVs back to back, then silence under the slate; the bed under
    everything at its on-air level, faded out over the last second."""
    exe = shutil.which("ffmpeg")
    if not exe:
        sys.exit("ffmpeg isn't on PATH")
    cmd = [exe, "-y", "-loglevel", "error", "-f", "rawvideo", "-pix_fmt", "rgb24", "-s", f"{W}x{H}",
           "-r", str(FPS), "-i", "-"]
    for l in seg.lines:
        if l.wav_path and Path(l.wav_path).exists():
            cmd += ["-i", str(l.wav_path)]
        else:                                              # its audio is gone: silence for its length
            say(f"WARNING: no audio for {l.speaker}: {l.text[:40]}...; silence instead")
            cmd += ["-f", "lavfi", "-t", f"{l.duration_s or 0.0:.3f}", "-i", "anullsrc=r=24000:cl=mono"]
    n = len(seg.lines)
    cmd += ["-stream_loop", "-1", "-i", str(BED)]
    fmt = "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=mono"
    graph = "".join(f"[{i + 1}:a]{fmt}[l{i}];" for i in range(n))
    graph += "".join(f"[l{i}]" for i in range(n)) + f"concat=n={n}:v=0:a=1,apad=whole_dur={total + SLATE_S:.3f}[voice];"
    graph += (f"[{n + 1}:a]{fmt},volume={BED_VOLUME},afade=t=out:st={max(0.0, total + SLATE_S - 1.0):.3f}:d=1[bed];"
              "[voice][bed]amix=inputs=2:duration=first:normalize=0,aformat=channel_layouts=stereo[a]")
    cmd += ["-filter_complex", graph, "-map", "0:v", "-map", "[a]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-t", f"{total + SLATE_S:.3f}",
            "-movflags", "+faststart", str(out)]
    return cmd


def cmd_render(args) -> None:
    cache = Path(args.cache) if args.cache else CACHE
    path = _find(cache, args.hash)
    tmp = _sandbox(cache)
    try:
        _render(path, args, tmp)
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def _render(path: Path, args, tmp: Path) -> None:
    import pygame

    from newsroom import logo, scenes, schedule, world as world_mod
    from newsroom.buffer import Buffer
    from newsroom.config import CONFIG
    from newsroom.models import Segment
    from newsroom.player import Player

    assert CONFIG.paths.world.resolve() == (tmp / "world.json").resolve(), "the world isn't the sandbox's"
    full = Segment.model_validate_json(path.read_text(encoding="utf-8"))
    last = len(full.lines) - 1 if args.to is None else args.to
    try:
        seg = trim(full, args.first, last)
    except ValueError as e:
        sys.exit(str(e))
    show = schedule.get(seg.show)
    title = args.title or seg.headline or ""
    _check_words([l.text for l in seg.lines] + [title])

    pygame.init()
    pygame.display.set_mode(PIC)                     # backdrops convert() against a display
    world = world_mod.load()                         # the sandbox's copy; never saved from here
    player = Player(Buffer(), world, None, audio=False)
    now0 = seg.nominal_start_ts + sum(l.duration_s or 0.0 for l in full.lines[:args.first])
    player.current, player.seg_start, player.line_idx, player.line_start = seg, now0, 0, now0
    if seg.headline:
        player.ticker.append((seg.show, seg.headline))

    face = lambda px, bold=True: pygame.font.SysFont(scenes.TEXT_FACE, px, bold=bold)   # noqa: E731
    cap_font, name_font = face(CAPTION_PX), face(NAME_PX)
    starts = line_starts(seg.lines)
    total = seg.duration_s
    caps = captions(seg.lines, _names(seg, world), CAPTION_W, lambda s: cap_font.size(s)[0])
    colours = speaker_colours(seg.lines)
    line_keys = [who(l) for l in seg.lines]

    ground = _ground(show.colour)
    head = _header(show, title, face)
    slate = _slate(seg.show, face, logo)
    canvas, pic, frame = pygame.Surface(scenes.CANVAS), pygame.Surface(PIC), pygame.Surface((W, H))

    out_dir = Path(args.out) if args.out else OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    out = out_dir / f"{seg.show}_{path.stem}_{args.first}-{last}.mp4"
    say(f"{path.stem}: {show.title}, lines {args.first}..{last}, {total:.1f}s + {SLATE_S}s slate -> {out}")
    if total > 180:
        say("WARNING: over three minutes; YouTube won't take it as a Short")
    proc = subprocess.Popen(_ffmpeg(out, seg, total), stdin=subprocess.PIPE)
    n_frames = round((total + SLATE_S) * FPS)
    t0 = time.monotonic()
    try:
        for i in range(n_frames):
            t = i / FPS
            if t < total:
                idx = line_at(starts, t)
                player.line_idx, player.line_start = idx, now0 + starts[idx]
                scenes.render(canvas, player.view(now0 + t), t, overlays=False)
                scenes.present(canvas, pic)
                frame.blit(ground, (0, 0))
                frame.blit(head, (0, 0))
                pygame.draw.rect(frame, show.colour, pygame.Rect(PIC_AT[0] - 6, PIC_AT[1] - 6, PIC[0] + 12, PIC[1] + 12))
                frame.blit(pic, PIC_AT)
                cap = caption_at(caps, t)
                if cap is not None:
                    _caption(frame, cap, colours[line_keys[idx]], cap_font, name_font)
            else:
                frame.blit(slate, (0, 0))
            proc.stdin.write(pygame.image.tobytes(frame, "RGB"))
            if i and i % (FPS * 10) == 0:
                say(f"  {t:.0f}s of {total + SLATE_S:.0f}s ({time.monotonic() - t0:.0f}s so far)")
    finally:
        proc.stdin.close()
        proc.wait()
        pygame.quit()
    if proc.returncode != 0:
        sys.exit(f"ffmpeg failed ({proc.returncode})")
    say(f"wrote {out} in {time.monotonic() - t0:.0f}s")


# -------------------------------------------------------------------------------------- the frame


def _shadowed(surf, font, s: str, colour, center_x: int, y: int, shadow: int = 4) -> int:
    """Text centred on center_x with a dark drop shadow, so it reads over anything; returns its height."""
    img = font.render(s, True, colour)
    back = font.render(s, True, (0, 0, 0))
    x = center_x - img.get_width() // 2
    surf.blit(back, (x + shadow, y + shadow))
    surf.blit(img, (x, y))
    return img.get_height()


def _ground(colour):
    """The frame's background: night blue, darker toward the foot, the show's colour faint at the top."""
    import pygame

    g = pygame.Surface((W, H))
    for y in range(H):
        k = y / H
        tint = max(0.0, 0.35 - k) / 0.35 * 0.25
        base = (14 - 6 * k, 18 - 8 * k, 32 - 14 * k)
        g.fill(tuple(int(b * (1 - tint) + c * tint) for b, c in zip(base, colour)), pygame.Rect(0, y, W, 1))
    return g


def _header(show, title: str, face):
    """Above the picture: the station, the show in its colour, the programme's title (or the story)."""
    import pygame

    h = pygame.Surface((W, PIC_AT[1]), pygame.SRCALPHA)
    pygame.draw.rect(h, show.colour, pygame.Rect(0, 0, W, 14))
    y = 150
    y += _shadowed(h, face(38), "CHANNEL 7  ·  PORT WEXLEY", (235, 228, 210), W // 2, y) + 18
    y += _shadowed(h, face(104), show.title, show.colour, W // 2, y, shadow=5) + 30
    tf = face(56)
    rows = wrap(title, W - 160, lambda s: tf.size(s)[0])[:4]
    for r in rows:
        y += _shadowed(h, tf, r, (245, 245, 245), W // 2, y) + 6
    return h


def _caption(frame, cap: Caption, colour, cap_font, name_font) -> None:
    y = CAPTION_TOP
    if cap.name:
        y += _shadowed(frame, name_font, cap.name.upper(), colour, W // 2, y) + 14
    for r in cap.rows:
        y += _shadowed(frame, cap_font, r, (250, 250, 250), W // 2, y) + 4


def _slate(show_id: str, face, logo):
    """The end: the station's roundel and where to find it."""
    import pygame

    s = _ground((40, 60, 110))
    mark = pygame.Surface((80, 80), pygame.SRCALPHA)
    logo.draw_mark(mark, 40, 40, show_id, r=30, t=3.0)
    big = pygame.transform.scale(mark, (480, 480))
    s.blit(big, ((W - 480) // 2, 480))
    y = 1040
    y += _shadowed(s, face(120), SLATE_WORDS[0], (245, 238, 220), W // 2, y, shadow=6) + 30
    _shadowed(s, face(64), SLATE_WORDS[1], (255, 214, 90), W // 2, y)
    return s


# ------------------------------------------------------------------------------------------- main


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list", help="the cached segments, newest first, with their lines numbered")
    ls.add_argument("--show", help="a show's id or title: magazine or coastwide, phonein or 'have your say'")
    ls.add_argument("--type", help="the segment type: sofa, call, interview, field_report ...")
    ls.add_argument("--speaker", help="a speaker id (gully, mag_a) or part of a guest's name")
    ls.add_argument("--text", help="words in a line or the headline")
    ls.add_argument("--limit", type=int, default=20, help="how many segments (default %(default)s)")
    ls.add_argument("--cache", help=f"another cache folder (default {CACHE})")
    rd = sub.add_parser("render", help="a 1080x1920 Short of lines N..M of one segment")
    rd.add_argument("hash", help="the segment's file name in the cache (a unique start of it is enough)")
    rd.add_argument("--from", dest="first", type=int, default=0, help="the first line, as `list` numbers them")
    rd.add_argument("--to", type=int, help="the last line, included (default: the segment's last)")
    rd.add_argument("--title", help="the programme title over the picture (default: the segment's headline)")
    rd.add_argument("--out", help=f"the folder for the mp4 (default {OUT})")
    rd.add_argument("--cache", help=f"another cache folder (default {CACHE})")
    args = ap.parse_args(argv)
    {"list": cmd_list, "render": cmd_render}[args.cmd](args)


if __name__ == "__main__":
    main()
