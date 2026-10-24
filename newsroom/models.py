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

Speaker = Literal["anchor", "weather", "reporter"]
SPEAKERS: tuple[str, ...] = ("anchor", "weather", "reporter")


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
    wav_path: Path | None = None
    duration_s: float | None = None
    mouth_env: list[float] = Field(default_factory=list)


class VisualCue(BaseModel):
    at_s: float = 0.0
    kind: Literal["lower_third", "backdrop", "map_state", "ticker", "gesture"]
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


class ScriptLine(BaseModel):
    speaker: Speaker
    text: str = Field(min_length=1, max_length=900)


class WeatherScript(BaseModel):
    lines: list[ScriptLine] = Field(min_length=1, max_length=8)
    headline: str = Field(max_length=90)
    map_state: Literal["sunny", "cloudy", "rain", "storm", "snow", "fog", "wind"]
    temp_c: int = Field(ge=-40, le=50)


class BulletinScript(BaseModel):
    lines: list[ScriptLine] = Field(min_length=1, max_length=10)
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
    lines: list[ScriptLine] = Field(min_length=2, max_length=12)
    headline: str = Field(max_length=90)
    location: str = Field(max_length=60)
    backdrop: Literal[
        "harbour", "main_street", "town_hall", "park", "factory", "farm", "stadium", "school"
    ]
    lower_third: str = Field(max_length=60)
    thread_id: str | None = None
    thread_status: str | None = Field(default=None, max_length=160)


SCRIPT_SCHEMAS: dict[SegmentType, type[BaseModel]] = {
    SegmentType.weather: WeatherScript,
    SegmentType.bulletin: BulletinScript,
    SegmentType.field_report: FieldReportScript,
}
