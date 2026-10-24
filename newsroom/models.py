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

from pydantic import BaseModel, Field

Speaker = Literal["anchor", "weather", "reporter", "guest"]
SPEAKERS: tuple[str, ...] = ("anchor", "weather", "reporter", "guest")
Backdrop = Literal["harbour", "main_street", "town_hall", "park", "factory", "farm", "stadium", "school"]


class SegmentType(StrEnum):
    weather = "weather"
    bulletin = "bulletin"
    field_report = "field_report"
    bumper = "bumper"
    filler = "filler"
    documentary = "documentary"


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
    nominal_start_ts: float = Field(default_factory=time.time)
    target_s: float = 60.0
    lines: list[Line] = Field(default_factory=list)
    cues: list[VisualCue] = Field(default_factory=list)
    headline: str | None = None
    thread_id: str | None = None
    content_hash: str = ""
    error: str | None = None

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


LiveSpeaker = Literal["anchor", "weather", "reporter"]


class LiveLine(BaseModel):
    """A line in a live segment: only the station's own three voices."""
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
    location: str = Field(max_length=60)
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
    reason: str = Field(default="", max_length=300, description="why now, or why not")


class SectionPlan(BaseModel):
    heading: str = Field(max_length=60)
    beats: list[str] = Field(min_length=1, max_length=4, description="what this section establishes")
    backdrop: Backdrop
    guest_name: str | None = Field(default=None, max_length=40, description="an invented resident to hear from, or null")
    guest_role: str | None = Field(default=None, max_length=50, description="e.g. 'harbourmaster', 'retired cannery worker'")


class SpecialOutline(BaseModel):
    title: str = Field(max_length=60)
    standfirst: str = Field(max_length=140, description="one-sentence subtitle shown on the title card")
    intro: str = Field(max_length=400, description="what the anchor says in the studio to hand over")
    outro: str = Field(max_length=300, description="what the anchor says back in the studio afterwards")
    sections: list[SectionPlan] = Field(min_length=3, max_length=6)


class SpecialSection(BaseModel):
    lines: list[ScriptLine] = Field(min_length=2, max_length=10)


SCRIPT_SCHEMAS: dict[SegmentType, type[BaseModel]] = {
    SegmentType.weather: WeatherScript,
    SegmentType.bulletin: BulletinScript,
    SegmentType.field_report: FieldReportScript,
}
