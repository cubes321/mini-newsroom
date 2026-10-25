"""Shared data model.

Two layers:
1. Broadcast objects (Line, VisualCue, Segment, Rundown) that move through
   the buffer and are persisted to data/cache as JSON.
2. LLM response schemas (WeatherScript, BulletinScript, FieldReportScript)
   that are the *only* thing the model is asked to produce. writers.py turns
   them into Segments. Keeping these thin keeps the model's job small.
"""
from __future__ import annotations

import time
import uuid
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, create_model

from .locations import BACKDROP_IDS

Speaker = Literal["anchor", "weather", "reporter", "host_a", "host_b", "guest"]
SPEAKERS: tuple[str, ...] = ("anchor", "weather", "reporter", "host_a", "host_b", "guest")
Backdrop = Literal[*BACKDROP_IDS]       # one list, in locations.py, for the schema and the painter


class SegmentType(StrEnum):
    weather = "weather"
    bulletin = "bulletin"
    field_report = "field_report"
    bumper = "bumper"
    filler = "filler"
    documentary = "documentary"
    sofa = "sofa"                # breakfast: the two hosts chatting
    repeat = "repeat"            # overnight: an earlier segment from the cache
    testcard = "testcard"        # overnight: the card, music only


class SegmentState(StrEnum):
    planned = "planned"
    scripted = "scripted"
    voiced = "voiced"
    ready = "ready"
    playing = "playing"
    done = "done"
    failed = "failed"


# ---------------------------------------------------------------- broadcast


class Line(BaseModel):
    speaker: Speaker
    text: str
    guest_name: str | None = None          # only when speaker == "guest"
    wav_path: Path | None = None
    duration_s: float | None = None
    mouth_env: list[float] = Field(default_factory=list)


class VisualCue(BaseModel):
    at_s: float = 0.0
    kind: Literal["lower_third", "backdrop", "map_state", "ticker", "gesture", "chapter"]
    payload: dict = Field(default_factory=dict)


class Segment(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    slot_id: int
    type: SegmentType
    state: SegmentState = SegmentState.planned
    priority: int = 0                      # 0 = live slot, 9 = documentary
    show: str = "news"                     # schedule.SHOWS id
    repeat: bool = False                   # an earlier segment aired again overnight
    nominal_start_ts: float = Field(default_factory=time.time)
    target_s: float = 60.0
    lines: list[Line] = Field(default_factory=list)
    cues: list[VisualCue] = Field(default_factory=list)
    headline: str | None = None
    thread_id: str | None = None
    content_hash: str = ""
    error: str | None = None
    stage: str = ""                        # multi-stage jobs (specials): where generation got to
    work: dict = Field(default_factory=dict)   # their scratch state, JSON-serialisable

    @property
    def duration_s(self) -> float:
        return sum(l.duration_s or 0.0 for l in self.lines)

    @property
    def word_budget(self) -> int:
        from .config import CONFIG

        return int(self.target_s / 60 * CONFIG.broadcast.words_per_minute)


class Rundown(BaseModel):
    broadcast_date: date = Field(default_factory=date.today)
    slots: list[Segment] = Field(default_factory=list)
    horizon_s: float = 600.0


# -------------------------------------------------------------- LLM outputs


LiveSpeaker = Literal["anchor", "weather", "reporter", "host_a", "host_b"]


class LiveLine(BaseModel):
    """A line in a live segment: only the station's own presenters (script_schema narrows to one show)."""
    speaker: LiveSpeaker
    text: str = Field(min_length=1, max_length=900)


class ScriptLine(BaseModel):
    """A line in a special: adds invented interviewees."""
    speaker: Speaker
    text: str = Field(min_length=1, max_length=900)
    guest_name: str | None = Field(default=None, max_length=40,
                                   description="required when speaker is 'guest'; the person's name")


class WeatherScript(BaseModel):
    lines: list[LiveLine] = Field(min_length=1, max_length=8)
    headline: str = Field(max_length=90)
    map_state: Literal["sunny", "cloudy", "rain", "storm", "snow", "fog", "wind"]
    temp_c: int = Field(ge=-40, le=50)


class BulletinScript(BaseModel):
    lines: list[LiveLine] = Field(min_length=1, max_length=10)
    headline: str = Field(max_length=90)
    lower_third: str = Field(max_length=60)
    thread_id: str | None = Field(
        default=None, description="id of an existing thread this follows up, or null"
    )
    thread_status: str | None = Field(
        default=None, max_length=160,
        description="if following up: one plain sentence saying what is new, e.g. 'Repair crew now due Tuesday'",
    )


class FieldReportScript(BaseModel):
    lines: list[LiveLine] = Field(min_length=2, max_length=12)
    headline: str = Field(max_length=90)
    location: str = Field(max_length=60, description="the place in words, e.g. 'the slipway behind the old cannery'")
    backdrop: Backdrop
    lower_third: str = Field(max_length=60)
    thread_id: str | None = None
    thread_status: str | None = Field(default=None, max_length=160)


# ------------------------------------------------------------- specials


class EditorDecision(BaseModel):
    """The editor's call on whether any open thread has earned a special report."""
    commission: bool
    thread_id: str | None = Field(default=None, description="the thread to cover, or null")
    working_title: str = Field(default="", max_length=80)
    angle: str = Field(default="", max_length=300, description="the question the piece answers")
    reason: str = Field(default="", max_length=400, description="one or two sentences: why now, or why not")


class SectionPlan(BaseModel):
    heading: str = Field(max_length=60)
    beats: list[str] = Field(min_length=1, max_length=4, description="what this section establishes")
    backdrop: Backdrop
    guest_name: str | None = Field(default=None, max_length=40, description="an invented resident to hear from, or null")
    guest_role: str | None = Field(default=None, max_length=50, description="e.g. 'harbourmaster', 'retired cannery worker'")
    guest_gender: Literal["f", "m"] | None = Field(default=None, description="for casting the guest's voice")


class SpecialOutline(BaseModel):
    title: str = Field(max_length=60)
    standfirst: str = Field(max_length=140, description="one-sentence subtitle shown on the title card")
    intro: str = Field(max_length=400, description="what the anchor says in the studio to hand over")
    outro: str = Field(max_length=300, description="what the anchor says back in the studio afterwards")
    sections: list[SectionPlan] = Field(min_length=3, max_length=6)


class SpecialSection(BaseModel):
    lines: list[ScriptLine] = Field(min_length=2, max_length=10)


# ----------------------------------------------------------- story desk

Phase = Literal["emerging", "developing", "peak", "resolving", "closed"]


class ThreadUpdate(BaseModel):
    thread_id: str
    phase: Phase
    next_development: str = Field(max_length=300, description="one sentence: the concrete next thing that happens, with a day if relevant")
    people: list[str] = Field(default_factory=list, max_length=4,
                              description="names of known public figures or residents now involved")


class NewThread(BaseModel):
    title: str = Field(max_length=80)
    status: str = Field(max_length=200, description="what is known so far, one sentence")
    next_development: str = Field(max_length=300, description="one sentence")
    people: list[str] = Field(default_factory=list, max_length=3)


class StoryPlan(BaseModel):
    updates: list[ThreadUpdate] = Field(default_factory=list, max_length=10)
    new_threads: list[NewThread] = Field(default_factory=list, max_length=3)
    note: str = Field(default="", max_length=200, description="one line on the editorial thinking")


SCRIPT_SCHEMAS: dict[SegmentType, type[BaseModel]] = {
    SegmentType.weather: WeatherScript,
    SegmentType.bulletin: BulletinScript,
    SegmentType.field_report: FieldReportScript,
    SegmentType.sofa: BulletinScript,       # same shape: lines, headline, caption, optional follow-up
}

_NARROWED: dict[tuple[SegmentType, tuple[str, ...]], type[BaseModel]] = {}


def script_schema(seg_type: SegmentType, cast: tuple[str, ...]) -> type[BaseModel]:
    """The script schema with `lines[].speaker` narrowed to one show's cast.

    The JSON schema the model sees then lists only that show's presenters, the
    same way the Backdrop enum comes from locations.py.
    """
    key = (seg_type, cast)
    if key not in _NARROWED:
        base = SCRIPT_SCHEMAS[seg_type]
        line = create_model(f"LiveLine_{'_'.join(cast)}", __base__=LiveLine,
                            speaker=(Literal[*cast], ...))
        lf = base.model_fields["lines"]
        bounds = {k: getattr(m, k) for m in lf.metadata for k in ("min_length", "max_length") if hasattr(m, k)}
        # The class name becomes the json_schema name, which servers cap at 64 characters.
        _NARROWED[key] = create_model(f"{base.__name__}_{'_'.join(cast)}"[:64], __base__=base,
                                      lines=(list[line], Field(**bounds)))
    return _NARROWED[key]
