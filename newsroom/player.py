"""Playout: consume ready segments on the wall clock, never block.

Rules:
- Slot N+1 starts when slot N's last line finishes playing, not at a hard
  nominal time; audio is never cut mid-sentence.
- If the next slot is not ready, continuity and local adverts cover the gap in turn
  (continuity.GAP_PATTERN: an ident, an advert, the programme card or a notice...),
  adverts up to `[adverts] max_in_a_row`; then filler (music bed + card),
  and after a while with nothing new, a replay of the last weather segment so
  the screen isn't dead air. An advert, like a special, uses no slot number.
- A ready special airs at a break, between loops of the rundown, without
  consuming a slot number, and only in a show that airs specials: after a
  bumper in the news, after the test card overnight. One made during
  breakfast or the evening shows waits for the news.
- Breaking news cuts in at the next line boundary (the overnight test card at
  once): the segment on air is set aside with its place and elapsed time, the
  breaking segment plays, then the programme resumes from the next line. A
  replay is dropped rather than resumed. Breaking news, like a special, uses
  no slot number and doesn't move the rundown on.
- A failed slot is skipped.
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

from . import adverts, continuity, documentary, schedule
from .buffer import Buffer
from .config import CONFIG
from .locations import time_of_day
from .models import FIELD_REPORTERS, Segment, SegmentState, SegmentType
from .producer import Producer
from .tts import ENV_WINDOW_S
from .world import World

log = logging.getLogger(__name__)

REPLAY_AFTER_S = 25.0      # filler this long -> replay last weather
LET_FINISH_S = 12.0        # breaking news waits for a segment with less than this left

# Segments shot on the interview set, and outside pieces with their wall caption at the handover.
INTERVIEW_SET = (SegmentType.interview, SegmentType.consumer, SegmentType.links, SegmentType.monologue,
                 SegmentType.sport)
OUTSIDE = {SegmentType.field_report: "LIVE", SegmentType.feature: "REPORT", SegmentType.vox_pop: "VOX POP"}
FORGET_BEHIND = 6          # drop finished slots this far behind the head
_BREAKS = (SegmentType.bumper, SegmentType.testcard)   # a ready special may air after these
GAP = (SegmentType.advert, SegmentType.continuity)    # cover a gap: outside the rundown, nothing to resume


@dataclass
class View:
    """Everything scenes.py needs to paint a frame. Plain data, no pygame."""
    mode: str = "testcard"               # testcard | filler | bumper | studio | weather | field | special
    show: str = "news"                   # schedule.SHOWS id: picks the set and the branding
    set: str = ""                        # "interview" on the interview set, "sports" at the sports corner
    people: list = field(default_factory=list)   # who is on that set: [(speaker id, guest name or None)]
    presenter: str = "anchor"            # who stands at the big-picture wall
    reporter: str = "reporter"           # who is out on location: Miles, or Tamsin on Full Time
    tag: str = ""                        # field scenes: LIVE, VOX POP, or nothing for a filmed piece
    resume_at: str = ""                  # overnight card: when programmes start again
    speaker: str | None = None
    guest_name: str | None = None
    guests: dict = field(default_factory=dict)   # every guest in shot: name -> (voice, role, age), for their look
    mouth: float = 0.0
    talking: bool = False
    lower_third: tuple[str, str] | None = None
    ticker: list[str] = field(default_factory=list)
    map_state: str | None = None
    temp_c: int | None = None
    backdrop: str | None = None
    tod: str = "day"                     # day | dusk | night, from the broadcast clock
    weather: str | None = None           # last weather report's map_state; grades exteriors
    shot: str = "wide"                   # studio framing: wide | close | wall
    wall_label: str = ""                 # caption on the big-picture wall's side panel
    strand: str = ""                     # a documentary's strand name, for its letterbox label
    archive: str = ""                    # archive footage on screen: its caption (black and white)
    chapter: dict | None = None          # {number, total, heading, title, standfirst}
    chapter_age_s: float = 0.0
    clock: str = ""
    slot_id: int | None = None
    buffer_depth_s: float = 0.0
    status: str = ""
    replay: bool = False
    repeat: bool = False                 # an earlier segment aired again overnight
    breaking: bool = False               # breaking news: red captions, and the BREAKING card over the sting
    advert: dict | None = None           # an advert's end card: business, tagline, where, owner, colour
    continuity: dict | None = None       # an ident, the programme card or a notice: kind, title, lines


class Player:
    def __init__(self, buffer: Buffer, world: World, producer: Producer, *, audio: bool = True,
                 ads: adverts.AdPool | None = None, cont: continuity.Pool | None = None) -> None:
        self.buffer, self.world, self.producer, self.audio = buffer, world, producer, audio
        self.ads = ads if ads is not None else adverts.pool()
        self.cont = cont if cont is not None else continuity.pool()
        self.ads_in_row = 0                  # adverts since the last real segment
        self.gap_n = 0                       # how far through continuity.GAP_PATTERN this gap is
        self.ads_played = 0
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
        self.breaking_played = 0
        self.stash: tuple[Segment, int, float] | None = None   # set aside by breaking news: (segment, next line, elapsed)
        self.filler_total_s = 0.0
        self._voice = None
        self._cast_of: tuple[str, list] = ("", [])     # (segment id, people on set), worked out once
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
        if self.current.type is SegmentType.bumper or self._kind() == "ident":
            self._set_music(0.0)            # the tune is the sound
        elif self.current.type is SegmentType.testcard:
            self._set_music(0.25)       # the card's line is silence; the bed is the sound
        elif self.current.type in (SegmentType.documentary, SegmentType.advert, SegmentType.ad_break,
                                   SegmentType.continuity):
            self._set_music(0.10)       # a bed under the special, or the adverts
        else:
            self._set_music(0.06)

    def _kind(self) -> str:
        return (self.current.work.get("continuity") or {}).get("kind", "") if self.current else ""

    def _line_done(self, now: float) -> bool:
        line = self.current.lines[self.line_idx]
        if self.audio and self._voice is not None:
            return not self._voice.get_busy()
        return now - self.line_start >= (line.duration_s or 0.0)

    # ------------------------------------------------------------ control

    def _start(self, seg: Segment, now: float, *, replay: bool = False) -> None:
        self.current, self.line_idx, self.seg_start, self.replaying = seg, 0, now, replay
        if seg.type not in GAP:
            self.ads_in_row = self.gap_n = 0
        if not replay and seg.type not in GAP:
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

    def time_left(self, now: float) -> float:
        """Seconds left of the segment on air (the producer plans from the end of it)."""
        if self.current is None or self.replaying:
            return 0.0
        return max(0.0, self.seg_start + self.current.duration_s - now)

    def _breaking_due(self) -> bool:
        """At a line boundary: cut in now? Not into a bumper or another breaking segment, and not
        when only a tag is left ("Thanks, Miles"): that finishes first, then breaking news airs."""
        seg = self.current
        left = sum(l.duration_s or 0.0 for l in seg.lines[self.line_idx:])
        return (self.stash is None and seg.type not in (SegmentType.breaking, SegmentType.bumper)
                and (left >= LET_FINISH_S or seg.type is SegmentType.testcard) and self.buffer.breaking_ready())

    def _interrupt(self, now: float) -> None:
        """Set the segment on air aside (or end it: a replay, the test card) and air breaking news."""
        seg = self.current
        if self.audio and self._voice is not None:
            self._voice.stop()
        if seg.type is SegmentType.testcard:
            self._finish(now)                    # the card just ends early
        elif self.replaying or seg.type in GAP:     # nothing to come back to
            self.current, self.replaying = None, False
        else:
            self.stash = (seg, self.line_idx, now - self.seg_start)
            self.current = None
            log.info("breaking news interrupts slot %d %s at line %d/%d",
                     seg.slot_id, seg.type.value, self.line_idx + 1, len(seg.lines))
        self._start(self.buffer.pop_breaking(), now)

    def _resume(self, now: float) -> None:
        seg, idx, elapsed = self.stash
        self.stash = None
        # Back-date the start so the segment's cues carry on where they were.
        self.current, self.line_idx, self.seg_start, self.replaying = seg, idx, now - elapsed, False
        self._play_line(now)
        log.info("resuming slot %d %s at line %d/%d", seg.slot_id, seg.type.value, idx + 1, len(seg.lines))

    def _finish(self, now: float) -> None:
        seg = self.current
        if seg.type is SegmentType.breaking:
            # Outside the rundown: no slot advance, and last_type stays as it was,
            # so a special can still follow the bumper before it.
            self.buffer.mark(seg, SegmentState.done)
            self.buffer.forget(seg.slot_id)
            self.breaking_played += 1
            self.current = None
            self._set_music(0.25)
            return
        if seg.type in GAP:
            # Outside the rundown too: nothing to mark in the buffer, no slot advance.
            if seg.type is SegmentType.advert:
                self.ads_in_row += 1
                self.ads_played += 1
            self.current = None
            self._set_music(0.25)
            return
        if not self.replaying:
            self.buffer.mark(seg, SegmentState.done)
            if seg.type is SegmentType.documentary:
                from .special import mark_aired

                self.specials_played += 1
                if not seg.repeat:                # a repeat is no new airing (it would block tonight's)
                    mark_aired(seg, self.world)
                self.buffer.forget(seg.slot_id)
            else:
                self.buffer.forget(seg.slot_id - FORGET_BEHIND)
                self.next_slot = seg.slot_id + 1
                self.played += 1
            if seg.type is SegmentType.ad_break:
                # Its adverts count towards the gap limit: a slow slot after a break gets the card sooner.
                self.ads_in_row = seg.work.get("ads", 0)
                self.ads_played += self.ads_in_row
            self.last_type = seg.type
        self.current = None
        self.replaying = False
        self._set_music(0.25)

    def update(self, now: float | None = None) -> None:
        now = now or schedule.now()
        if self.current is not None:
            if not self.current.lines:
                self._finish(now)
            elif self._line_done(now):
                self.line_idx += 1
                if self.line_idx < len(self.current.lines) and self._breaking_due():
                    self._interrupt(now)
                elif self.line_idx < len(self.current.lines):
                    self._play_line(now)
                else:
                    self._finish(now)
            elif self.current.type is SegmentType.testcard and self._breaking_due():
                self._interrupt(now)
            if self.current is not None:
                return
            # It just ended: what follows starts in this same tick, or view() would show the test
            # card for a frame at every join.

        # Breaking news first, then whatever it interrupted.
        if self.buffer.breaking_ready():
            self._start(self.buffer.pop_breaking(), now)
            return
        if self.stash is not None:
            self._resume(now)
            return

        # The documentary has its own slot: the first news bumper from airs_at, within the window.
        if (self.last_type is SegmentType.bumper and schedule.show_at(now).airs_specials
                and documentary.due(self.world, now)):
            doc = self.buffer.pop_special("documentary")
            if doc is not None:
                self._start(doc, now)
                return

        # The night's documentary again, overnight: after the first test card from repeat_at.
        if self.last_type is SegmentType.testcard and documentary.repeat_due(self.world, now):
            rep = documentary.load_repeat(self.world)
            if rep is not None:
                self._start(rep, now)
                return

        # A finished special is aired at a break (a bumper, or overnight the test
        # card), between loops, in a show that airs specials, from the hour it was given.
        if self.last_type in _BREAKS and schedule.show_at(now).airs_specials:
            special = self.buffer.pop_special("special", now)
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
            if seg.type is SegmentType.ad_break and not seg.lines:
                seg = adverts.break_segment(seg, self.ads)     # its adverts are picked as it airs
            self._start(seg, now)
            if not seg.lines:                    # an empty ad break (no adverts voiced yet): straight on
                self._finish(now)
                self.update(now)
            return

        # A gap: idents, cards and adverts in turn, then the filler card.
        item = self._gap_item(now)
        if item is not None:
            what = (item.work.get("advert", {}).get("business") if item.type is SegmentType.advert
                    else item.work.get("continuity", {}).get("kind"))
            log.info("gap: slot %d is %s; %s %r", self.next_slot, state.value if state else "unknown",
                     item.type.value, what)
            self._start(item, now)
            return

        # Filler.
        if self.filler_since is None:
            self.filler_since = now
            self._set_music(0.25)
            log.info("filler: slot %d is %s", self.next_slot, state.value if state else "unknown")
        elif now - self.filler_since > REPLAY_AFTER_S and self.last_weather is not None:
            self._start(self.last_weather, now, replay=True)

    def _gap_item(self, now: float) -> Segment | None:
        """The next thing in continuity.GAP_PATTERN that there is one of: an advert (while under
        max_in_a_row), an ident in this show's tune (never straight after a bumper), or a card."""
        show = schedule.show_at(now).id
        pattern = continuity.GAP_PATTERN
        for k in range(self.gap_n, len(pattern)):
            kind = pattern[k]
            if kind == "advert":
                seg = self.ads.pick() if self.ads_in_row < CONFIG.adverts.max_in_a_row else None
            elif kind == "ident" and k == 0 and self.last_type is SegmentType.bumper:
                seg = None
            else:
                seg = self.cont.pick(kind, show, now)
            if seg is not None:
                self.gap_n = k + 1
                return seg
        self.gap_n = len(pattern)
        return None

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

    def _studio_shot(self, seg: Segment, v: View) -> None:
        """Pick the studio framing for the current line.

        - Handing over to a field report: the anchor stands at the big wall with
          the location on it, until the reporter first speaks.
        - Introducing a special: the same, showing its first location.
        - Bulletins cut between the wide desk shot and a close-up, line by line.
        """
        handing_over = all(l.speaker not in (*FIELD_REPORTERS, "guest") for l in seg.lines[:self.line_idx + 1])
        if seg.type in OUTSIDE and handing_over and v.backdrop:
            v.shot, v.wall_label = "wall", OUTSIDE[seg.type]
            v.presenter = v.speaker or v.presenter
        elif seg.type is SegmentType.documentary and self.line_idx == 0:
            first = next((c.payload.get("backdrop") for c in seg.cues if c.kind == "backdrop"), None)
            if first:
                v.shot, v.wall_label, v.backdrop = "wall", seg.work.get("strand") or "SPECIAL REPORT", first
        elif seg.type is SegmentType.bulletin and self.line_idx % 2 == 1 and v.speaker == "anchor":
            v.shot = "close"            # the close-up is of the anchor: never someone else's voice
        elif seg.type is SegmentType.sofa and self.line_idx % 3 == 2:
            v.shot = "close"            # the sofa holds the two-shot longer, then cuts in
        elif seg.type in INTERVIEW_SET and self.line_idx > 0 and self.line_idx % 4 != 0:
            v.shot = "close"            # an interview: open wide, then singles on whoever speaks

    def _people(self, seg: Segment) -> list:
        """Who sits on the interview set: the presenters who speak, then the guest (on the late
        couch, the new guest and then the one who stayed on and moved down)."""
        if self._cast_of[0] != seg.id:
            hosts: list = []
            guests: list = []
            for l in seg.lines:
                c = self.world.presenter_named(l.guest_name) if l.speaker == "guest" else None
                if c and (c.id, None) not in hosts:
                    hosts.append((c.id, None))       # a presenter as a guest sits in the guest chair
                elif l.speaker == "guest" and not c:
                    if l.guest_name not in guests:
                        guests.append(l.guest_name)
                elif l.speaker not in (*FIELD_REPORTERS, "weather") and (l.speaker, None) not in hosts:
                    hosts.append((l.speaker, None))
            stayed = seg.work.get("couch")
            guests = (sorted(guests[:2], key=lambda g: g == stayed) if stayed
                      else guests[:3] if seg.show == "panel" else guests[:1])
            self._cast_of = (seg.id, hosts[:2] + [("guest", g) for g in guests])
        return self._cast_of[1]

    def view(self, now: float | None = None) -> View:
        now = now or schedule.now()
        local = time.localtime(now)
        v = View(clock=time.strftime("%H:%M", local), ticker=list(self.ticker),
                 buffer_depth_s=self.buffer.ready_depth_s(), slot_id=self.next_slot,
                 tod=time_of_day(local.tm_hour), weather=self.world.last_weather.get("map_state"))
        on_air = schedule.show_at(now)
        v.show = on_air.id
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
        v.reporter = next((l.speaker for l in seg.lines if l.speaker in FIELD_REPORTERS), "reporter")
        v.guest_name = line.guest_name if line else None
        as_presenter = self.world.presenter_named(v.guest_name) if v.speaker == "guest" else None
        if as_presenter:                     # a presenter as a guest is drawn as themselves,
            v.speaker, v.guest_name = as_presenter.id, None             # captioned as the script has them
            v.lower_third = (as_presenter.name, (line.guest_role if line else None) or as_presenter.role)
        v.replay = self.replaying
        v.repeat = seg.repeat
        v.show = seg.show
        v.breaking = seg.type is SegmentType.breaking
        if line and line.mouth_env:
            i = int((now - self.line_start) / ENV_WINDOW_S)
            v.mouth = line.mouth_env[i] if 0 <= i < len(line.mouth_env) else 0.0
            v.talking = v.mouth > 0.08
        lt = cues.get("lower_third")
        if not as_presenter:
            v.lower_third = (lt.get("title", ""), lt.get("subtitle", "")) if lt else None
        mp = cues.get("map_state", {})
        v.map_state, v.temp_c = mp.get("state"), mp.get("temp_c")
        v.backdrop = cues.get("backdrop", {}).get("backdrop")
        v.chapter = cues.get("chapter")
        if seg.type is SegmentType.documentary:
            v.mode = "studio" if v.speaker == "anchor" else "special"
            if v.mode == "special":
                v.presenter = documentary.presenter(seg)
            v.strand = seg.work.get("strand", "")
            v.archive = (line.archive or "") if line else ""
        elif v.breaking and self.line_idx == 0:
            v.mode, v.speaker = "breaking", None             # the sting, under the BREAKING NEWS card
        elif seg.type is SegmentType.testcard:
            v.mode, v.speaker = "testcard", None
            v.show, v.resume_at = on_air.id, schedule.next_start(on_air.id)
        else:
            v.mode = {
                SegmentType.bumper: "bumper",
                SegmentType.weather: "weather",
                SegmentType.bulletin: "studio",
                SegmentType.sofa: "studio",
                SegmentType.field_report: "field" if v.speaker in FIELD_REPORTERS else "studio",
                SegmentType.advert: "advert",
                SegmentType.ad_break: "advert",
                SegmentType.continuity: "ident" if self._kind() == "ident" else "notice",
            }.get(seg.type, "studio")
            if seg.type in (SegmentType.feature, SegmentType.vox_pop):
                v.mode = "field" if line and line.speaker in (*FIELD_REPORTERS, "guest") else "studio"
        if seg.type in INTERVIEW_SET or (v.mode == "studio" and seg.show in ("magazine", "late", "sport", "inquiry", "quayside", "panel")):
            sports = seg.type is SegmentType.sport or seg.show == "sport"
            v.set, v.people = "sports" if sports else "interview", self._people(seg)
            if seg.type not in INTERVIEW_SET:            # back from a film: the presenters, not its resident
                v.people = [p for p in v.people if p[0] != "guest"]
            v.presenter = next((p for p, _ in v.people if p != "guest"), v.presenter)
        v.tag = {SegmentType.field_report: "LIVE", SegmentType.vox_pop: "VOX POP"}.get(seg.type, "")
        if seg.type is SegmentType.continuity:
            v.continuity = dict(seg.work.get("continuity") or {})
        if seg.type in (SegmentType.advert, SegmentType.ad_break):
            v.advert = dict(cues.get("advert") or seg.work.get("advert", {}))     # a break: the advert airing now
            owner = self.world.presenter_named(v.advert.get("owner"))
            v.advert["owner_id"] = owner.id if owner else "guest"     # Gordon's ghost tours: Gordon
        for name in {v.guest_name, (v.advert or {}).get("owner"), *(n for w, n in v.people if w == "guest")} - {None}:
            p = self.world.person_by_name(name)
            v.guests[name] = (self.world.voice_for("guest", name), p.role if p else "", p.age if p else "")
        if as_presenter is None and v.speaker == "guest" and v.guest_name and seg.type is not SegmentType.documentary:
            p = self.world.person_by_name(v.guest_name)
            v.lower_third = (v.guest_name, line.guest_role or (p.role if p else "Port Wexley"))
        if v.mode == "studio":
            self._studio_shot(seg, v)
        v.slot_id = seg.slot_id
        label = {SegmentType.documentary: "DOCUMENTARY" if documentary.is_documentary(seg) else "SPECIAL",
                 SegmentType.breaking: "BREAKING",
                 SegmentType.advert: "ADVERT", SegmentType.continuity: "CONTINUITY",
                 SegmentType.ad_break: f"BREAK slot {seg.slot_id}"}.get(
                     seg.type, f"slot {seg.slot_id}")
        v.status = f"{label} " \
                   f"{seg.type.value} line {self.line_idx + 1}/{len(seg.lines)}"
        return v
