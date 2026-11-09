"""A film on air: its frames, read from the video by an ffmpeg pipe on a thread, ready for the time asked.

The soundtrack is the segment's one line, played by the mixer like any other (bank.segment); this module
only draws. Frames come at the window's size and are drawn straight onto it (scenes.present), not through
the 320x180 canvas, so a film isn't blown up from pixels. A player that asks for a time before the last
frame given (a restart, a replay) gets a fresh reader from that point.
"""
from __future__ import annotations

import logging
import queue
import subprocess
import threading

import pygame

log = logging.getLogger(__name__)

FPS = 24
AHEAD = 12                     # frames decoded ahead of the one on screen


class Reader:
    def __init__(self, path: str, size: tuple[int, int], start_s: float = 0.0):
        self.path, self.size, self.start_s = path, size, start_s
        self.q: queue.Queue = queue.Queue(maxsize=AHEAD)
        self.frame: pygame.Surface | None = None
        self.frame_t = start_s - 1.0
        self.done = False
        self._closed = threading.Event()
        w, h = size
        self.proc = subprocess.Popen(
            ["ffmpeg", "-loglevel", "error", "-ss", f"{start_s:.3f}", "-i", path, "-an",
             "-vf", f"scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,fps={FPS}",
             "-f", "rawvideo", "-pix_fmt", "rgb24", "-"],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
        self.thread = threading.Thread(target=self._read, daemon=True, name="film")
        self.thread.start()

    def _read(self) -> None:
        w, h = self.size
        n, k = w * h * 3, 0
        try:
            while not self._closed.is_set():
                buf = self.proc.stdout.read(n)
                if len(buf) < n:
                    break
                # Never a put that waits for ever: once the film is closed nobody takes a frame, and until
                # 2026-11-09 each closed reader's thread sat here for the rest of the run with a full queue
                # (twelve frames at the window's size, some 75 MB at 1080p) and its ffmpeg unreaped.
                while not self._closed.is_set():
                    try:
                        self.q.put((self.start_s + k / FPS, buf), timeout=0.25)
                        break
                    except queue.Full:
                        pass
                k += 1
        finally:
            self.done = True
            try:
                self.proc.stdout.close()
                self.proc.wait(timeout=5)
            except (OSError, ValueError, subprocess.TimeoutExpired):
                pass

    def at(self, t: float) -> pygame.Surface | None:
        """The frame for `t` seconds into the film (the last one decoded, if the decoder is behind)."""
        while True:
            try:
                ft, buf = self.q.queue[0] if self.q.queue else (None, None)
            except IndexError:
                ft = None
            if ft is None or ft > t:
                break
            ft, buf = self.q.get_nowait()
            self.frame, self.frame_t = pygame.image.frombuffer(buf, self.size, "RGB"), ft
        return self.frame

    def close(self) -> None:
        self._closed.set()
        try:
            self.proc.kill()
        except OSError:
            pass
        with self.q.mutex:                  # the frames waiting go now, not when the thread notices
            self.q.queue.clear()


_reader: Reader | None = None


def frame(path: str, t: float, size: tuple[int, int]) -> pygame.Surface | None:
    """The film's frame at `t`; the reader is kept between calls for the same film."""
    global _reader
    if _reader is None or _reader.path != path or _reader.size != size or t < _reader.frame_t - 0.5:
        if _reader is not None:
            _reader.close()
        _reader = Reader(path, size, max(0.0, t))
    return _reader.at(t)


def stop() -> None:
    global _reader
    if _reader is not None:
        _reader.close()
        _reader = None
