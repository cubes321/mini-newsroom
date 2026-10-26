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
"""
from __future__ import annotations

import argparse
import logging
import os
import sys
import time

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
    p.add_argument("--clock", type=str, default="", help="pretend the local time is HH:MM (test the schedule)")
    p.add_argument("--log-llm", action="store_true", help="write every LLM prompt and reply to data/llm_calls/")
    p.add_argument("-v", "--verbose", action="store_true")
    return p.parse_args(argv)


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
        log.info("STATS frame p50=%.1fms p99=%.1fms | buffer %.0fs ready | states %s | played %d filler %.0fs",
                 p50, p99, self.buffer.ready_depth_s(), self.buffer.counts(), player.played, player.filler_total_s)
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
    pygame.quit()
    stats.last_log = 0
    stats.maybe_log(player)
    log.info("exit: worst p99 %.1fms, %d segments played, %.0fs filler", stats.worst_p99, player.played, player.filler_total_s)
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
    stats.last_log = 0
    stats.maybe_log(player)
    log.info("exit: %d segments played, %.0fs filler, transitions=%d, jobs ok=%d failed=%d",
             player.played, player.filler_total_s, len(buffer.transitions), pool.jobs_done, pool.jobs_failed)
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
    from . import schedule
    from .config import CONFIG

    if args.clock:
        schedule.set_clock(args.clock)
        log.info("broadcast clock set to %s (%s)", args.clock, schedule.show_at(schedule.now()).id)
    if args.special_now:
        os.environ["NEWSROOM_SPECIAL_NOW"] = "1"
    if args.log_llm:
        os.environ["NEWSROOM_LLM_LOG"] = "1"
    if args.workers != 1:
        # world.py mutates shared state from the worker thread without a lock;
        # more than one generator is unsupported until that is added.
        log.warning("--workers %d not supported yet (world state is unlocked); using 1", args.workers)
        args.workers = 1

    if args.no_window:
        run_headless(CONFIG, args)
    else:
        run_window(CONFIG, args)
    return 0


if __name__ == "__main__":
    sys.exit(main())
