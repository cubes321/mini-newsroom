"""Playout: consume ready segments on the wall clock, never block.

Rules:
- Slot N+1 starts when slot N's last line finishes playing, not at a hard
  nominal time; audio is never cut mid-sentence.
- If the next slot is not ready, play filler (music bed + card). After a
  while with nothing new, replay the last weather segment so the screen
  isn't dead air.
- A ready special airs right after a bumper, between loops of the rundown,
  without consuming a slot number.
- A failed slot is skipped; the producer's retime keeps deadlines honest.
- Cues are applied by elapsed time within the segment, so a five-minute
  special can change backdrop and captions as it goes.
- With audio=False (headless) line ends are simulated from durations so the
  same logic can be soak-tested without a sound device.
"""
from __future__ import annotations

import logging
import time
from collections import deque
from dataclasses import dataclass, field

from .buffer import Buffer
from .locations import time_of_day
from .models import Segment, SegmentState, SegmentType
from .producer import Producer
from .tts import ENV_WINDOW_S
from .world import World

log = logging.getLogger(__name__)

REPLAY_AFTER_S = 25.0      # filler this long -> replay last weather
FORGET_BEHIND = 6          # drop finished slots this far behind the head


@dataclass
class View:
    """Everything scenes.py needs to paint a frame. Plain data, no pygame."""
    mode: str = "testcard"               # testcard | filler | bumper | studio | weather | field | special
    speaker: str | None = None
    guest_name: str | None = None
    mouth: float = 0.0
    talking: bool = False
    lower_third: tuple[str, str] | None = None
    ticker: list[str] = field(default_factory=list)
    map_state: str | None = None
    temp_c: int | None = None
    backdrop: str | None = None
    tod: str = "day"                     # day | dusk | night, from the broadcast clock
    weather: str | None = None           # last weather report's map_state; grades exteriors
    chapter: dict | None = None          # {number, total, heading, title, standfirst}
    chapter_age_s: float = 0.0
    clock: str = ""
    slot_id: int | None = None
    buffer_depth_s: float = 0.0
    status: str = ""
    replay: bool = False


class Player:
    def __init__(self, buffer: Buffer, world: World, producer: Producer, *, audio: bool = True) -> None:
        self.buffer, self.world, self.producer, self.audio = buffer, world, producer, audio
        self.next_slot = 0
        self.current: Segment | None = None
        self.line_idx = 0
        self.line_start = 0.0
        self.seg_start = 0.0
        self.filler_since: float | None = None
        self.replaying = False
        self.last_weather: Segment | None = None
        self.last_type: SegmentType | None = None
        self.ticker: deque[str] = deque(maxlen=6)
        self.played = 0
        self.specials_played = 0
        self.filler_total_s = 0.0
        self._voice = None
        if audio:
            import pygame

            pygame.mixer.set_reserved(1)
            self._voice = pygame.mixer.Channel(0)
            self._start_music()

    # -------------------------------------------------------------- audio

    def _start_music(self) -> None:
        import pygame

        from .assets import ensure_music_bed

        try:
            pygame.mixer.music.load(str(ensure_music_bed()))
            pygame.mixer.music.set_volume(0.0)
            pygame.mixer.music.play(loops=-1)
        except Exception as e:  # noqa: BLE001
            log.warning("music bed unavailable: %s", e)

    def _set_music(self, vol: float) -> None:
        if self.audio:
            import pygame

            pygame.mixer.music.set_volume(vol)

    def _play_line(self, now: float) -> None:
        line = self.current.lines[self.line_idx]
        self.line_start = now
        if self.audio and line.wav_path:
            import pygame

            self._voice.play(pygame.mixer.Sound(str(line.wav_path)))
        if self.current.type is SegmentType.bumper:
            self._set_music(0.0)
        elif self.current.type is SegmentType.documentary:
            self._set_music(0.10)       # a bed under the special
        else:
            self._set_music(0.06)

    def _line_done(self, now: float) -> bool:
        line = self.current.lines[self.line_idx]
        if self.audio and self._voice is not None:
            return not self._voice.get_busy()
        return now - self.line_start >= (line.duration_s or 0.0)

    # ------------------------------------------------------------ control

    def _start(self, seg: Segment, now: float, *, replay: bool = False) -> None:
        self.current, self.line_idx, self.seg_start, self.replaying = seg, 0, now, replay
        if not replay:
            self.buffer.mark(seg, SegmentState.playing)
            if seg.headline:
                self.ticker.append(seg.headline)
            if seg.type is SegmentType.weather:
                self.last_weather = seg
        if self.filler_since is not None:
            self.filler_total_s += now - self.filler_since
            self.filler_since = None
        if seg.lines:
            self._play_line(now)
        log.info("%s slot %d %s (%.1fs, %d lines)%s", "replaying" if replay else "playing",
                 seg.slot_id, seg.type.value, seg.duration_s, len(seg.lines),
                 f" — {seg.headline!r}" if seg.headline else "")

    def _finish(self, now: float) -> None:
        seg = self.current
        if not self.replaying:
            self.buffer.mark(seg, SegmentState.done)
            if seg.type is SegmentType.documentary:
                self.specials_played += 1
                self.buffer.forget(seg.slot_id)
            else:
                self.producer.retime(seg.slot_id, self.seg_start, now - self.seg_start)
                self.buffer.forget(seg.slot_id - FORGET_BEHIND)
                self.next_slot = seg.slot_id + 1
                self.played += 1
            self.last_type = seg.type
        self.current = None
        self.replaying = False
        self._set_music(0.25)

    def update(self, now: float | None = None) -> None:
        now = now or time.time()
        if self.current is not None:
            if not self.current.lines:
                self._finish(now)
            elif self._line_done(now):
                self.line_idx += 1
                if self.line_idx < len(self.current.lines):
                    self._play_line(now)
                else:
                    self._finish(now)
            return

        # A finished special is aired right after a bumper, between loops.
        if self.last_type is SegmentType.bumper:
            special = self.buffer.pop_special()
            if special is not None:
                self._start(special, now)
                return

        # Nothing playing: is the next slot ready?
        state = self.buffer.state_of(self.next_slot)
        if state is SegmentState.failed:
            log.warning("skipping failed slot %d", self.next_slot)
            self.next_slot += 1
            return
        seg = self.buffer.get_ready(self.next_slot)
        if seg is not None:
            self._start(seg, now)
            return

        # Filler.
        if self.filler_since is None:
            self.filler_since = now
            self._set_music(0.25)
            log.info("filler: slot %d is %s", self.next_slot, state.value if state else "unknown")
        elif now - self.filler_since > REPLAY_AFTER_S and self.last_weather is not None:
            self._start(self.last_weather, now, replay=True)

    # --------------------------------------------------------------- view

    def _active_cues(self, elapsed: float) -> tuple[dict[str, dict], float]:
        """Latest payload per cue kind at `elapsed`, plus age of the current chapter cue."""
        active: dict[str, dict] = {}
        chapter_at = 0.0
        for c in self.current.cues:            # cues are few; a linear pass per frame is fine
            if c.at_s <= elapsed + 1e-6:
                active[c.kind] = c.payload
                if c.kind == "chapter":
                    chapter_at = c.at_s
        return active, elapsed - chapter_at

    def view(self, now: float | None = None) -> View:
        now = now or time.time()
        local = time.localtime(now)
        v = View(clock=time.strftime("%H:%M", local), ticker=list(self.ticker),
                 buffer_depth_s=self.buffer.ready_depth_s(), slot_id=self.next_slot,
                 tod=time_of_day(local.tm_hour), weather=self.world.last_weather.get("map_state"))
        seg = self.current
        if seg is None:
            v.mode = "filler" if self.filler_since is not None else "testcard"
            waited = now - self.filler_since if self.filler_since else 0.0
            v.status = f"slot {self.next_slot}: {self.buffer.state_of(self.next_slot) or 'not planned'} ({waited:.0f}s)"
            if self.last_weather:
                mp = next((c.payload for c in self.last_weather.cues if c.kind == "map_state"), {})
                v.map_state, v.temp_c = mp.get("state"), mp.get("temp_c")
            return v

        elapsed = now - self.seg_start
        cues, v.chapter_age_s = self._active_cues(elapsed)
        line = seg.lines[self.line_idx] if self.line_idx < len(seg.lines) else None
        v.speaker = line.speaker if line else None
        v.guest_name = line.guest_name if line else None
        v.replay = self.replaying
        if line and line.mouth_env:
            i = int((now - self.line_start) / ENV_WINDOW_S)
            v.mouth = line.mouth_env[i] if 0 <= i < len(line.mouth_env) else 0.0
            v.talking = v.mouth > 0.08
        lt = cues.get("lower_third")
        v.lower_third = (lt.get("title", ""), lt.get("subtitle", "")) if lt else None
        mp = cues.get("map_state", {})
        v.map_state, v.temp_c = mp.get("state"), mp.get("temp_c")
        v.backdrop = cues.get("backdrop", {}).get("backdrop")
        v.chapter = cues.get("chapter")
        if seg.type is SegmentType.documentary:
            v.mode = "studio" if v.speaker == "anchor" else "special"
        else:
            v.mode = {
                SegmentType.bumper: "bumper",
                SegmentType.weather: "weather",
                SegmentType.bulletin: "studio",
                SegmentType.field_report: "field" if v.speaker == "reporter" else "studio",
            }.get(seg.type, "studio")
        v.slot_id = seg.slot_id
        v.status = f"{'SPECIAL' if seg.type is SegmentType.documentary else 'slot ' + str(seg.slot_id)} " \
                   f"{seg.type.value} line {self.line_idx + 1}/{len(seg.lines)}"
        return v
