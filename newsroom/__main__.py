"""Entry point: `python -m newsroom`.

The main thread owns Pygame and never blocks. Everything slow (LLM, TTS)
happens on worker threads and lands in the buffer; the player only ever
reads what is already finished.

Flags:
  --no-window   headless soak: producer + workers + simulated player, logs only
  --minutes N   auto-exit after N minutes
  --debug       overlay slot/line/buffer status on the picture
  --clock HH:MM  start the broadcast clock at this time (test a show at any hour)
  --log-llm     write every LLM prompt and reply to data/llm_calls/<date>.jsonl
  --world PATH  read and write this world file instead of data/world.json (or NEWSROOM_WORLD)
  --cache DIR   segment cache to use instead of data/cache (or NEWSROOM_CACHE)
  --scratch     copy the world, tip-line and adverts to a temp dir and run on the copy with an empty cache
                (and --log-llm writes to that dir's llm_calls/)
  --documentary-now  commission today's documentary at the first idle moment (it still airs in its slot)
  --breaking-now  have the story desk break a story at its next idle moment (Miles then goes to the scene)
  --route A=B[,C=D]  for this run, send every task routed to provider A (or task A) to provider B
  --obs         record each programme to its own file in OBS as it airs (newsroom/obs.py)
  --audio-device NAME  play into this sound output (part of its name) instead of [broadcast] audio_device
  --devices     list the sound outputs and exit

Every run also logs to data/logs/station-<date>-<time>.log (NEWSROOM_LOGS; a scratch run's own logs/).
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

log = logging.getLogger("newsroom")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def parse_args(argv: list[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="newsroom")
    p.add_argument("--no-window", action="store_true", help="run producer/workers headless and log")
    p.add_argument("--minutes", type=float, default=0, help="auto-exit after N minutes (0 = until closed)")
    p.add_argument("--debug", action="store_true", help="draw status overlay")
    p.add_argument("--workers", type=int, default=1)
    p.add_argument("--snap", type=str, default="", help="save a PNG of the frame to this dir every 10 s")
    p.add_argument("--special-now", action="store_true", help="have the editor consider a special immediately")
    p.add_argument("--documentary-now", action="store_true",
                   help="commission today's documentary at the first idle moment, whatever the hour")
    p.add_argument("--breaking-now", action="store_true",
                   help="have the story desk break a story at its next idle moment, whatever the cap and the hour")
    p.add_argument("--clock", type=str, default="", help="pretend the local time is HH:MM, or YYYY-MM-DD HH:MM for another day (test the schedule)")
    p.add_argument("--channel", choices=("seven", "entertainment"), default="seven",
                   help="which channel to put out: Channel 7 (the default), or the entertainment channel "
                        "(entertainment/, sharing Port Wexley)")
    p.add_argument("--log-llm", action="store_true", help="write every LLM prompt and reply to data/llm_calls/")
    p.add_argument("--world", type=str, default="", help="world file to use instead of data/world.json")
    p.add_argument("--cache", type=str, default="", help="segment cache dir to use instead of data/cache")
    p.add_argument("--scratch", action="store_true",
                   help="run on a temp copy of the world and tip-line, with an empty cache and its own call log")
    p.add_argument("--route", type=str, default="",
                   help="move providers' or tasks' calls for this run: deepseek_flash_think=claude_sonnet[,...] (or NEWSROOM_ROUTES)")
    p.add_argument("--parallax", action="store_true",
                   help="draw the location backdrops that have layers in parallax, whatever config.toml says")
    p.add_argument("--pictures", action="store_true",
                   help="make ComfyUI pictures for the stories in shadow mode (shown nowhere; pictures.py)")
    p.add_argument("--obs", action="store_true",
                   help="record each programme to its own file in OBS (its WebSocket server on)")
    p.add_argument("--audio-device", type=str, default="",
                   help="play into this sound output (part of its name), e.g. 'CABLE Input'")
    p.add_argument("--devices", action="store_true", help="list the sound outputs and exit")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def redirect_paths(args: argparse.Namespace) -> None:
    """Point the world, cache and tip-line elsewhere. Must run before newsroom.config is
    imported: CONFIG is built at import time from these environment variables."""
    if args.route:
        os.environ["NEWSROOM_ROUTES"] = args.route
    if args.parallax:
        os.environ["NEWSROOM_PARALLAX"] = "1"
    if args.pictures:
        os.environ["NEWSROOM_PICTURES"] = "1"
    if args.world:
        os.environ["NEWSROOM_WORLD"] = args.world
    if args.cache:
        os.environ["NEWSROOM_CACHE"] = args.cache
    if not args.scratch:
        return
    data = Path(__file__).resolve().parent.parent / "data"
    scratch = Path(tempfile.mkdtemp(prefix="newsroom-scratch-"))
    world = Path(os.environ.get("NEWSROOM_WORLD") or data / "world.json")
    tipline = Path(os.environ.get("NEWSROOM_TIPLINE") or data / "tipline.txt")
    copies = {world: "world.json", tipline: "tipline.txt", tipline.with_suffix(".state.json"): "tipline.state.json"}
    for src, name in copies.items():
        if src.exists():
            shutil.copy2(src, scratch / name)
    ads = Path(os.environ.get("NEWSROOM_ADS") or data / "ads")
    if ads.exists():                         # the voiced adverts, so a gap still has one to air
        shutil.copytree(ads, scratch / "ads")
    os.environ["NEWSROOM_ADS"] = str(scratch / "ads")
    os.environ["NEWSROOM_CONTINUITY"] = str(scratch / "continuity")   # baked afresh: idents, cards, notices
    os.environ["NEWSROOM_PICTURES_DIR"] = str(scratch / "pictures")
    os.environ["NEWSROOM_WORLD"] = str(scratch / "world.json")
    os.environ["NEWSROOM_CACHE"] = str(scratch / "cache")
    os.environ["NEWSROOM_TIPLINE"] = str(scratch / "tipline.txt")
    # --log-llm too: a test run's calls in the real data/llm_calls muddle a night's costs
    os.environ["NEWSROOM_LLM_CALLS"] = str(scratch / "llm_calls")
    os.environ["NEWSROOM_LOGS"] = str(scratch / "logs")             # a test run's log stays with its copy
    log.info("scratch run in %s (copied from %s)", scratch, world)


LOG_FORMAT = "%(asctime)s %(levelname)-5s %(name)s: %(message)s"
# Loggers that drown the station's own: Pocket TTS wrote seven INFO lines a voiced line ("starting timer
# now!", "Generated: 4480 ms of audio..."), about 70% of the 2026-11-04 night; the workers' own "ready:
# 63.4s of audio in 17.4s wall" already says how fast the voicing goes.
NOISY = ("httpx", "httpx2", "httpcore", "httpcore2", "openai", "urllib3", "kokoro", "phonemizer",
         "pocket_tts")


def log_to_file(started: float | None = None) -> Path:
    """Every run also writes its log to data/logs/station-<date>-<time>.log (NEWSROOM_LOGS for another
    folder; a --scratch run's own logs/), so a night no longer needs its output redirected: the
    2026-11-04 night printed to a window that was then closed. Crashes on any thread are logged too."""
    folder = Path(os.environ.get("NEWSROOM_LOGS") or Path(__file__).resolve().parent.parent / "data" / "logs")
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"station-{time.strftime('%Y-%m-%d-%H%M', time.localtime(started))}.log"
    handler = logging.FileHandler(path, encoding="utf-8")
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt="%H:%M:%S"))
    logging.getLogger().addHandler(handler)
    logging.captureWarnings(True)                                   # torch's and pygame's warnings too

    def crashed(kind, value, tb, thread=None):
        logging.getLogger("newsroom").critical("unhandled %s%s", kind.__name__,
                                               f" in thread {thread}" if thread else "",
                                               exc_info=(kind, value, tb))
    sys.excepthook = crashed
    threading.excepthook = lambda a: crashed(a.exc_type, a.exc_value, a.exc_traceback,
                                             a.thread.name if a.thread else None)
    log.info("logging to %s", path)
    return path


class Stats:
    """Frame work-time percentiles (excluding the vsync wait) and buffer depth, logged each minute."""

    def __init__(self, buffer) -> None:
        self.buffer = buffer
        self.work: list[float] = []
        self.last_log = time.monotonic()
        self.worst_p99 = 0.0
        self.n_logs = 0

    def frame(self, work_s: float) -> None:
        self.work.append(work_s)

    def maybe_log(self, player) -> None:
        now = time.monotonic()
        if now - self.last_log < 60:
            return
        self.last_log = now
        if self.work:
            w = sorted(self.work)
            p50 = w[len(w) // 2] * 1000
            p99 = w[min(len(w) - 1, int(len(w) * 0.99))] * 1000
            self.worst_p99 = max(self.worst_p99, p99)
            self.work.clear()
        else:
            p50 = p99 = 0.0
        log.info("STATS frame p50=%.1fms p99=%.1fms | buffer %.0fs ready | states %s | played %d adverts %d "
                 "filler %.0fs", p50, p99, self.buffer.ready_depth_s(), self.buffer.counts(), player.played,
                 player.ads_played, player.filler_total_s)
        self.n_logs += 1
        if self.n_logs % 10 == 0:
            log_llm_usage()


def log_llm_usage() -> None:
    from . import llm

    log.info("LLM USAGE %s", llm.usage_summary())


def build(cfg, *, audio: bool, workers: int):
    from . import assets, tts, world as world_mod
    from .buffer import Buffer
    from .player import Player
    from .producer import Producer
    from .workers import WorkerPool

    assets.ensure_music_bed()
    w = world_mod.load()
    buffer = Buffer()
    producer = Producer(buffer, cfg.broadcast.horizon_s)
    producer.tick()
    pool = WorkerPool(buffer, w, n=workers)
    pool.start()
    from . import pictures

    pictures.start()                    # shadow mode: pictures made, shown nowhere (--pictures)
    tts.preload()                       # Pocket's model and voices, while the first bumper airs
    player = Player(buffer, w, producer, audio=audio)
    producer.on_air_left = player.time_left
    return w, buffer, producer, pool, player


def audio_outputs() -> list[str]:
    """The sound outputs SDL can play into, by name."""
    import pygame
    from pygame._sdl2 import audio

    pygame.mixer.init()
    try:
        return list(audio.get_audio_device_names(False))
    finally:
        pygame.mixer.quit()


def pick_output(wanted: str, names: list[str]) -> str | None:
    """The output called `wanted`, or the first whose name contains it (any case); None if none does."""
    if wanted in names:
        return wanted
    return next((n for n in names if wanted.lower() in n.lower()), None)


def open_audio(cfg, wanted: str) -> None:
    """Start pygame with its mixer on the chosen output, or on the system's if that output isn't there.
    `pygame.init()` doesn't fail on a bad device: it leaves the mixer off, and the first sound would."""
    import pygame

    device = None
    if wanted:
        names = audio_outputs()
        device = pick_output(wanted, names)
        if device is None:
            log.warning("audio: no output called %r (there are %s); playing on the system's", wanted, names)
    from .assets import MUSIC_SR

    # 44.1 kHz stereo, the music's: SDL converts each voice (TTS's 24 kHz mono) as it loads.
    pygame.mixer.pre_init(MUSIC_SR, -16, 2, 1024, devicename=device)
    pygame.init()
    if device and not pygame.mixer.get_init():
        log.warning("audio: %r wouldn't open; playing on the system's", device)
        pygame.mixer.init(MUSIC_SR, -16, 2, 1024)
    elif device:
        log.info("audio: playing into %s", device)


def run_window(cfg, args) -> None:
    import pygame

    from . import scenes, schedule

    open_audio(cfg, args.audio_device or cfg.broadcast.audio_device)
    screen = pygame.display.set_mode((cfg.broadcast.width, cfg.broadcast.height))
    pygame.display.set_caption("Mini Newsroom")
    canvas = pygame.Surface(scenes.CANVAS)
    clock = pygame.time.Clock()
    from . import backdrops

    threading.Thread(target=backdrops.warm_skies, name="warm-skies", daemon=True).start()
    if args.obs:
        from . import obs

        obs.attach()                        # before the first bumper plays: it starts the first file

    world, buffer, producer, pool, player = build(cfg, audio=True, workers=args.workers)
    stats = Stats(buffer)
    start = time.monotonic()
    last_tick = 0.0
    last_snap = -1
    running = True
    while running:
        t0 = time.perf_counter()
        for ev in pygame.event.get():
            if ev.type == pygame.QUIT or (ev.type == pygame.KEYDOWN and ev.key == pygame.K_ESCAPE):
                running = False
        now = schedule.now()
        if now - last_tick > 2.0:
            producer.tick(now)
            last_tick = now
        player.update(now)
        view = player.view(now)
        t = time.monotonic() - start
        dbg = f"{view.status} | buf {view.buffer_depth_s:.0f}s | {clock.get_fps():.0f}fps" if args.debug else None
        scenes.render(canvas, view, t, debug=dbg)
        scenes.present(canvas, screen)
        pygame.display.flip()
        if args.snap and int(t) % 10 == 0 and int(t) != last_snap:
            last_snap = int(t)
            os.makedirs(args.snap, exist_ok=True)
            pygame.image.save(screen, os.path.join(args.snap, f"frame_{last_snap:04d}_{view.mode}.png"))
        stats.frame(time.perf_counter() - t0)
        stats.maybe_log(player)
        clock.tick(cfg.broadcast.fps)
        if args.minutes and t > args.minutes * 60:
            running = False

    if args.obs:
        obs.detach()                        # the programme on air ends its file with the picture
    pool.shutdown()
    from . import world as world_mod        # imported late, like everything here: CONFIG follows the flags

    world_mod.save(world)                   # what the player wrote since the worker's last save
    pygame.quit()
    stats.last_log = 0
    stats.maybe_log(player)
    log.info("exit: worst p99 %.1fms, %d segments played, %d adverts, %.0fs filler", stats.worst_p99, player.played,
             player.ads_played, player.filler_total_s)
    log_llm_usage()


def run_headless(cfg, args) -> None:
    from . import schedule

    world, buffer, producer, pool, player = build(cfg, audio=False, workers=args.workers)
    stats = Stats(buffer)
    start = time.monotonic()
    last_tick = 0.0
    try:
        while True:
            t0 = time.perf_counter()
            now = schedule.now()
            if now - last_tick > 2.0:
                producer.tick(now)
                last_tick = now
            player.update(now)
            stats.frame(time.perf_counter() - t0)
            stats.maybe_log(player)
            time.sleep(1 / 30)
            if args.minutes and time.monotonic() - start > args.minutes * 60:
                break
    except KeyboardInterrupt:
        pass
    pool.shutdown()
    from . import world as world_mod        # imported late, like everything here: CONFIG follows the flags

    world_mod.save(world)                   # what the player wrote since the worker's last save
    stats.last_log = 0
    stats.maybe_log(player)
    log.info("exit: %d segments played, %d adverts, %.0fs filler, transitions=%d, jobs ok=%d failed=%d",
             player.played, player.ads_played, player.filler_total_s, len(buffer.transitions), pool.jobs_done, pool.jobs_failed)
    log_llm_usage()


def main(argv: list[str] | None = None) -> int:
    args = parse_args(sys.argv[1:] if argv is None else argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO, format=LOG_FORMAT, datefmt="%H:%M:%S")
    for noisy in NOISY:
        logging.getLogger(noisy).setLevel(logging.WARNING)
    if args.devices:
        print("\n".join(audio_outputs()))
        return 0
    redirect_paths(args)
    log_to_file()
    from . import schedule
    from .config import CONFIG

    log.info("world %s | cache %s", CONFIG.paths.world, CONFIG.paths.cache)

    if args.channel == "entertainment":       # before the clock: show_at reads the channel's own day
        import entertainment

        entertainment.use()
    if args.clock:
        schedule.set_clock(args.clock)
        log.info("broadcast clock set to %s (%s)", args.clock, schedule.show_at(schedule.now()).id)
    if args.special_now:
        os.environ["NEWSROOM_SPECIAL_NOW"] = "1"
    if args.documentary_now:
        os.environ["NEWSROOM_DOCUMENTARY_NOW"] = "1"
    if args.breaking_now:
        os.environ["NEWSROOM_BREAKING_NOW"] = "1"
    if args.log_llm:
        os.environ["NEWSROOM_LLM_LOG"] = "1"

    if args.no_window:
        if args.obs:
            log.info("--obs ignored: a headless run has no picture to record")
        run_headless(CONFIG, args)
    else:
        run_window(CONFIG, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
