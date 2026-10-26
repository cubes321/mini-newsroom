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
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, BeforeValidator, Field, create_model, model_validator

from .locations import BACKDROP_IDS

Speaker = Literal["anchor", "weather", "reporter", "host_a", "host_b", "mag_a", "mag_b", "late_host", "guest"]
SPEAKERS: tuple[str, ...] = ("anchor", "weather", "reporter", "host_a", "host_b", "mag_a", "mag_b", "late_host", "guest")
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
    interview = "interview"      # a studio guest in the armchair (news, magazine, talk show)
    links = "links"              # magazine: the two presenters' links and banter
    feature = "feature"          # magazine: a filmed piece, introduced at the big-picture wall
    vox_pop = "vox_pop"          # magazine: Miles asks passers-by one question
    consumer = "consumer"        # magazine: the consumer slot
    monologue = "monologue"      # talk show: the host's opening
    breaking = "breaking"        # breaking news from the tip-line: interrupts whatever is on
    advert = "advert"            # a local advert from the pool (adverts.py): covers a gap, outside the rundown
    ad_break = "ad_break"        # a planned break in a light show's running order: adverts from the pool


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
    speaker: Literal[*SPEAKERS, "voiceover"]   # the voiceover only speaks in adverts
    text: str
    guest_name: str | None = None          # only when speaker == "guest"
    guest_role: str | None = None          # what the script calls them today (the caption)
    wav_path: Path | None = None
    duration_s: float | None = None
    mouth_env: list[float] = Field(default_factory=list)
    archive: str | None = None             # archive footage in a documentary: its caption ("Archive · ...")


class VisualCue(BaseModel):
    at_s: float = 0.0
    kind: Literal["lower_third", "backdrop", "map_state", "ticker", "gesture", "chapter", "advert"]
    payload: dict = Field(default_factory=dict)


class Segment(BaseModel):
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    slot_id: int
    type: SegmentType
    state: SegmentState = SegmentState.planned
    priority: int = 0                      # 0 = live slot, 9 = documentary
    show: str = "news"                     # schedule.SHOWS id
    repeat: bool = False                   # an earlier segment aired again overnight
    part: str = ""                         # place in the show's running order: open | cont | close
    brief: str = ""                        # the running order's angle for this item
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


LiveSpeaker = Literal["anchor", "weather", "reporter", "host_a", "host_b", "mag_a", "mag_b", "late_host"]
GuestSpeaker = Literal["anchor", "weather", "reporter", "host_a", "host_b", "mag_a", "mag_b", "late_host", "guest"]


def _gender(v):
    """Models write 'female', 'Male', 'woman'...; keep the first letter that means something."""
    if isinstance(v, str):
        v = v.strip().lower()
        if v[:1] in ("f", "w") or v in ("woman", "girl"):
            return "f"
        if v[:1] == "m" or v in ("man", "boy"):
            return "m"
        return None
    return v


Gender = Annotated[Literal["f", "m"] | None, BeforeValidator(_gender)]


def _clip(n: int) -> BeforeValidator:
    """Status notes are bookkeeping, not speech: cut an overlong one (Kimi overruns them)
    instead of failing the whole script and paying for a retry."""
    return BeforeValidator(lambda v: v[: n - 1].rstrip() + "…" if isinstance(v, str) and len(v) > n else v)


Status = Annotated[str | None, _clip(160)]
# Models sometimes write "speaker_id" (the prompts say "speaker id"); accept both.
SPEAKER_KEY = AliasChoices("speaker", "speaker_id")


class LiveLine(BaseModel):
    """A line in a live segment: only the station's own presenters (script_schema narrows to one show)."""
    speaker: LiveSpeaker = Field(validation_alias=SPEAKER_KEY)
    text: str = Field(min_length=1, max_length=900)


class ScriptLine(BaseModel):
    """A line in a special: adds invented interviewees."""
    speaker: Speaker
    text: str = Field(min_length=1, max_length=900)
    guest_name: str | None = Field(default=None, max_length=40,
                                   description="required when speaker is 'guest'; the person's name")


class WeatherScript(BaseModel):
    lines: list[LiveLine] = Field(min_length=1, max_length=8)
    headline: str = Field(min_length=4, max_length=90)
    map_state: Literal["sunny", "cloudy", "rain", "storm", "snow", "fog", "wind"]
    temp_c: int = Field(ge=-40, le=50)


class BulletinScript(BaseModel):
    lines: list[LiveLine] = Field(min_length=1, max_length=10)
    headline: str = Field(min_length=4, max_length=90)
    lower_third: str = Field(min_length=4, max_length=60)
    thread_id: str | None = Field(
        default=None, description="id of an existing thread this follows up, or null"
    )
    thread_status: Status = Field(
        default=None, max_length=160,
        description="if following up: one plain sentence saying what is new, e.g. 'Repair crew now due Tuesday'",
    )


class FieldReportScript(BaseModel):
    lines: list[LiveLine] = Field(min_length=2, max_length=12)
    headline: str = Field(min_length=4, max_length=90)
    location: str = Field(min_length=4, max_length=60, description="the place in words, e.g. 'the slipway behind the old cannery'")
    backdrop: Backdrop
    lower_third: str = Field(min_length=4, max_length=60)
    thread_id: str | None = None
    thread_status: Status = Field(default=None, max_length=160)


# ---------------------------------------------------- studio guests and vox pops


def _lift_guest(data):
    """Models often put guest_name/role/gender on each guest line; take them from the first one."""
    if isinstance(data, dict) and not data.get("guest_name"):
        for line in data.get("lines") or []:
            if isinstance(line, dict) and line.get("guest_name"):
                for k in ("guest_name", "guest_role", "guest_gender"):
                    data.setdefault(k, line.get(k))
                    if data[k] is None:
                        data[k] = line.get(k)
                break
    return data


def _check_guest_named(script):
    if any(l.speaker == "guest" for l in script.lines) and not (script.guest_name or "").strip():
        raise ValueError("the guest speaks, so guest_name is required")
    return script


class GuestLine(BaseModel):
    """A line where a guest may speak; the guest is named once on the script."""
    speaker: GuestSpeaker = Field(validation_alias=SPEAKER_KEY)
    text: str = Field(min_length=1, max_length=900)


class InterviewScript(BaseModel):
    """A studio interview: a presenter and one guest in the armchair (the consumer slot may have none)."""
    lines: list[GuestLine] = Field(min_length=2, max_length=16)
    headline: str = Field(min_length=4, max_length=90)
    lower_third: str = Field(min_length=4, max_length=60)
    guest_name: str | None = Field(default=None, max_length=40, description="the guest's full name; required if 'guest' speaks")
    guest_role: str | None = Field(default=None, max_length=80, description="e.g. 'harbourmaster', 'retired cannery worker'")
    guest_gender: Gender = Field(default=None, description="for casting the guest's voice: 'f' or 'm'")
    thread_id: str | None = None
    thread_status: Status = Field(default=None, max_length=160)

    _lift = model_validator(mode="before")(_lift_guest)

    @model_validator(mode="after")
    def _guest_named(self):
        return _check_guest_named(self)


class FeatureScript(BaseModel):
    """A filmed magazine piece: Miles on location, optionally with one resident."""
    lines: list[GuestLine] = Field(min_length=3, max_length=14)
    headline: str = Field(min_length=4, max_length=90)
    location: str = Field(min_length=4, max_length=60, description="the place in words, never a backdrop id")
    backdrop: Backdrop
    lower_third: str = Field(min_length=4, max_length=60)
    guest_name: str | None = Field(default=None, max_length=40)
    guest_role: str | None = Field(default=None, max_length=80)
    guest_gender: Gender = None
    thread_id: str | None = None
    thread_status: Status = Field(default=None, max_length=160)

    _lift = model_validator(mode="before")(_lift_guest)

    @model_validator(mode="after")
    def _guest_named(self):
        return _check_guest_named(self)


class VoxLine(BaseModel):
    speaker: GuestSpeaker = Field(validation_alias=SPEAKER_KEY)
    text: str = Field(min_length=1, max_length=600)
    guest_name: str | None = Field(default=None, max_length=40, description="required when speaker is 'guest'")
    guest_gender: Gender = None

    @model_validator(mode="after")
    def _guest_named(self):
        if self.speaker == "guest" and not (self.guest_name or "").strip():
            raise ValueError("a 'guest' line needs guest_name")
        return self


class VoxPopScript(BaseModel):
    """Miles puts one question to several passers-by."""
    lines: list[VoxLine] = Field(min_length=4, max_length=12)
    question: str = Field(max_length=90, description="the question Miles asks, as a caption")
    headline: str = Field(min_length=4, max_length=90)
    location: str = Field(min_length=4, max_length=60)
    backdrop: Backdrop


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
    archive_clip: str | None = Field(default=None, max_length=8,
                                     description="the id of an ARCHIVE CLIP to play in this section (e.g. 'C1'); "
                                                 "null unless ARCHIVE CLIPS are listed")


class SpecialOutline(BaseModel):
    title: str = Field(max_length=60)
    standfirst: str = Field(max_length=140, description="one-sentence subtitle shown on the title card")
    intro: str = Field(max_length=400, description="what the anchor says in the studio to hand over")
    outro: str = Field(max_length=300, description="what the anchor says back in the studio afterwards")
    sections: list[SectionPlan] = Field(min_length=3, max_length=6)


class DocumentaryOutline(SpecialOutline):
    """A fifteen-minute documentary: the special's outline with more sections."""
    sections: list[SectionPlan] = Field(min_length=6, max_length=10)


class DocumentaryCommission(BaseModel):
    """The day's documentary: a long-running thread or a piece of the town's history."""
    subject: Literal["thread", "history"] = Field(description="a story we have been covering, or the town's past")
    thread_id: str | None = Field(default=None, description="for a thread subject: its id from the briefing")
    working_title: str = Field(max_length=80)
    angle: str = Field(max_length=300, description="the question the documentary answers")
    search_terms: list[str] = Field(default_factory=list, max_length=6,
                                    description="words to search the archive for (names, places, things)")
    reason: str = Field(default="", max_length=300, description="why this subject today")


class TimelineEntry(BaseModel):
    date: str = Field(max_length=30, description="a date, or 'about 1900' for history")
    event: str = Field(max_length=300)        # 200 was too tight: Sonnet's events run long
    on_record: bool = Field(description="true only if the archive extracts report it; false for background")


class Stakeholder(BaseModel):
    name: str = Field(max_length=40)
    role: str = Field(max_length=60)
    stance: str = Field(max_length=240, description="what they want, or what they said")


class DocumentaryResearch(BaseModel):
    """The researcher's notes, written from the archive before the outline. The writers keep to them."""
    timeline: list[TimelineEntry] = Field(min_length=1, max_length=14)
    people: list[Stakeholder] = Field(default_factory=list, max_length=8)
    details: list[str] = Field(default_factory=list, max_length=8,
                               description="telling details from the coverage: a number, a quote, an object")
    background: list[str] = Field(default_factory=list, max_length=6,
                                  description="history not on record that the piece may establish, consistent "
                                              "with the briefing")
    questions: list[str] = Field(default_factory=list, max_length=5, description="what is still open")


class SpecialSection(BaseModel):
    lines: list[ScriptLine] = Field(min_length=1, max_length=10)


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
    status: Annotated[str, _clip(200)] = Field(max_length=200, description="what is known so far, one sentence")
    next_development: str = Field(max_length=300, description="one sentence")
    people: list[str] = Field(default_factory=list, max_length=3)


class StoryPlan(BaseModel):
    updates: list[ThreadUpdate] = Field(default_factory=list, max_length=30)    # a batch per call (desk.batch), with room for out-of-turn extras it skips
    new_threads: list[NewThread] = Field(default_factory=list, max_length=3)
    note: Annotated[str, _clip(200)] = Field(default="", max_length=200, description="one line on the editorial thinking")


class TipBulletinScript(BulletinScript):
    """A bulletin, plus which viewer tip (if any) it used, so the tip is spent."""
    tip_used: int | None = Field(default=None, description="number of the VIEWER TIP used, or null")


# ------------------------------------------------------------- adverts


class AdLine(BaseModel):
    speaker: Literal["voiceover", "owner"] = Field(validation_alias=SPEAKER_KEY)
    text: str = Field(min_length=1, max_length=300)


class AdvertScript(BaseModel):
    """A 15-30 second local TV advert: a voiceover, and perhaps the owner speaking for themselves.
    The end-card text is clipped rather than failed when it runs long (Kimi overruns limits)."""
    business: Annotated[str, _clip(40)] = Field(max_length=40, description="the business's name as on its sign")
    tagline: Annotated[str, _clip(48)] = Field(max_length=48, description="the slogan on the end card")
    where: Annotated[str, _clip(48)] = Field(max_length=48,
                                             description="where to find it, for the end card ('Harrow Street, from seven')")
    backdrop: Backdrop
    owner_name: str | None = Field(default=None, max_length=40, description="required if the owner speaks")
    owner_role: Annotated[str | None, _clip(50)] = Field(default=None, max_length=50,
                                                         description="e.g. 'baker, Harrow Street market'")
    owner_gender: Gender = None
    lines: list[AdLine] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def _owner_named(self):
        if any(l.speaker == "owner" for l in self.lines) and not (self.owner_name or "").strip():
            raise ValueError("the owner speaks, so owner_name is required")
        return self


SCRIPT_SCHEMAS: dict[SegmentType, type[BaseModel]] = {
    SegmentType.weather: WeatherScript,
    SegmentType.bulletin: TipBulletinScript,
    SegmentType.breaking: BulletinScript,
    SegmentType.field_report: FieldReportScript,
    SegmentType.sofa: BulletinScript,       # same shape: lines, headline, caption, optional follow-up
    SegmentType.links: BulletinScript,
    SegmentType.monologue: BulletinScript,
    SegmentType.interview: InterviewScript,
    SegmentType.consumer: InterviewScript,
    SegmentType.feature: FeatureScript,
    SegmentType.vox_pop: VoxPopScript,
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
        lf = base.model_fields["lines"]
        line_base = lf.annotation.__args__[0]          # LiveLine, GuestLine or VoxLine
        line = create_model(f"{line_base.__name__}_{'_'.join(cast)}"[:64], __base__=line_base,
                            speaker=(Literal[*cast], Field(validation_alias=SPEAKER_KEY)))
        bounds = {k: getattr(m, k) for m in lf.metadata for k in ("min_length", "max_length") if hasattr(m, k)}
        # The class name becomes the json_schema name, which servers cap at 64 characters.
        _NARROWED[key] = create_model(f"{base.__name__}_{'_'.join(cast)}"[:64], __base__=base,
                                      lines=(list[line], Field(**bounds)))
    return _NARROWED[key]
