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
"""
from __future__ import annotations

import argparse
import logging
import os
import shutil
import sys
import tempfile
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
    p.add_argument("--clock", type=str, default="", help="pretend the local time is HH:MM (test the schedule)")
    p.add_argument("--log-llm", action="store_true", help="write every LLM prompt and reply to data/llm_calls/")
    p.add_argument("--world", type=str, default="", help="world file to use instead of data/world.json")
    p.add_argument("--cache", type=str, default="", help="segment cache dir to use instead of data/cache")
    p.add_argument("--scratch", action="store_true",
                   help="run on a temp copy of the world and tip-line, with an empty cache and its own call log")
    p.add_argument("--route", type=str, default="",
                   help="move providers' or tasks' calls for this run: claude_sonnet=deepseek_pro[,...] (or NEWSROOM_ROUTES)")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


def redirect_paths(args: argparse.Namespace) -> None:
    """Point the world, cache and tip-line elsewhere. Must run before newsroom.config is
    imported: CONFIG is built at import time from these environment variables."""
    if args.route:
        os.environ["NEWSROOM_ROUTES"] = args.route
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
    os.environ["NEWSROOM_WORLD"] = str(scratch / "world.json")
    os.environ["NEWSROOM_CACHE"] = str(scratch / "cache")
    os.environ["NEWSROOM_TIPLINE"] = str(scratch / "tipline.txt")
    # --log-llm too: a test run's calls in the real data/llm_calls muddle a night's costs
    os.environ["NEWSROOM_LLM_CALLS"] = str(scratch / "llm_calls")
    log.info("scratch run in %s (copied from %s)", scratch, world)


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
    from . import assets, world as world_mod
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
    player = Player(buffer, w, producer, audio=audio)
    producer.on_air_left = player.time_left
    return w, buffer, producer, pool, player


def run_window(cfg, args) -> None:
    import pygame

    from . import scenes, schedule

    pygame.mixer.pre_init(cfg.tts.sample_rate, -16, 1, 512)
    pygame.init()
    screen = pygame.display.set_mode((cfg.broadcast.width, cfg.broadcast.height))
    pygame.display.set_caption("Mini Newsroom")
    canvas = pygame.Surface(scenes.CANVAS)
    clock = pygame.time.Clock()

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
        pygame.transform.scale(canvas, screen.get_size(), screen)
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
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-5s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "openai", "urllib3", "kokoro", "phonemizer"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    redirect_paths(args)
    from . import schedule
    from .config import CONFIG

    log.info("world %s | cache %s", CONFIG.paths.world, CONFIG.paths.cache)

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
        run_headless(CONFIG, args)
    else:
        run_window(CONFIG, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
