"""Shared data model.

Two layers:
1. Broadcast objects (Line, VisualCue, Segment, Rundown) that move through
   the buffer and are persisted to data/cache as JSON.
2. LLM response schemas (WeatherScript, BulletinScript, FieldReportScript)
   that are the *only* thing the model is asked to produce. writers.py turns
   them into Segments. Keeping these thin keeps the model's job small.
"""
from __future__ import annotations

import re
import time
import uuid
from datetime import date
from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import AliasChoices, BaseModel, BeforeValidator, Field, create_model, model_validator

from .locations import BACKDROP_IDS

Speaker = Literal["anchor", "weather", "reporter", "host_a", "host_b", "mag_a", "mag_b", "late_host", "sport",
                  "sport_reporter", "business", "historian", "travel", "kids", "gully", "guest"]
SPEAKERS: tuple[str, ...] = ("anchor", "weather", "reporter", "host_a", "host_b", "mag_a", "mag_b", "late_host", "sport",
                             "sport_reporter", "business", "historian", "travel", "kids", "gully", "guest")
# Who goes out on location: Miles for the news and Coastwide, Tamsin for Full Time, Meg on Out and About.
FIELD_REPORTERS: tuple[str, ...] = ("reporter", "sport_reporter", "travel")
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
    continuity = "continuity"    # an ident, the programme card or a notice (continuity.py): covers a gap, outside the rundown
    ad_break = "ad_break"        # a planned break in a light show's running order: adverts from the pool
    sport = "sport"              # the sports desk: Fran at the sports corner (the news, and Full Time)
    call = "call"                # a phone-in: a caller on the line, the presenter, and maybe the studio guest
    review = "review"            # Out and About: a place to eat or a show, visited, with stars out of five


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
    fallback: bool = False                 # a canned script: the model was configured but unreachable
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


LiveSpeaker = Literal["anchor", "weather", "reporter", "host_a", "host_b", "mag_a", "mag_b", "late_host", "sport",
                      "sport_reporter", "business", "travel", "kids", "gully", "historian"]
GuestSpeaker = Literal["anchor", "weather", "reporter", "host_a", "host_b", "mag_a", "mag_b", "late_host", "sport",
                       "sport_reporter", "business", "travel", "kids", "gully", "historian", "guest"]


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

_OLD = ("old", "elder", "retired", "pension", "senior", "grand", "seventy", "eighty", "ninety")
_YOUNG = ("young", "teen", "child", "kid", "student", "pupil", "youth", "twent", "boy", "girl")
_MIDDLE = ("middle", "adult", "grown", "thirt", "fort", "fift", "sixt")


def _age(v):
    """Models write 'elderly', 'in her 70s', 'mid-40s', 34...; keep young, middle or old."""
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return "young" if v < 30 else "middle" if v < 65 else "old"
    if isinstance(v, str):
        v = v.strip().lower()
        if n := re.search(r"\d+", v):
            return _age(int(n.group()))
        for words, band in ((_MIDDLE, "middle"), (_OLD, "old"), (_YOUNG, "young")):
            if any(w in v for w in words):
                return band
        return None
    return v


def _accent(v):
    """'local', 'Cornish', 'Scottish' -> british; 'American', 'Canadian' -> american."""
    if isinstance(v, str):
        v = v.strip().lower()
        if any(w in v for w in ("america", "canad", "yank")) or v in ("us", "usa", "u.s."):
            return "american"
        if any(w in v for w in ("brit", "local", "engl", "scot", "wel", "irish", "cornish", "uk", "north", "south",
                                "west", "londo", "yorksh")):
            return "british"
        return None
    return v


Age = Annotated[Literal["young", "middle", "old"] | None, BeforeValidator(_age)]
Accent = Annotated[Literal["british", "american"] | None, BeforeValidator(_accent)]


def _clip(n: int) -> BeforeValidator:
    """Status notes are bookkeeping, not speech: cut an overlong one (Kimi overruns them)
    instead of failing the whole script and paying for a retry."""
    return BeforeValidator(lambda v: v[: n - 1].rstrip() + "…" if isinstance(v, str) and len(v) > n else v)


def _clip_words(n: int) -> BeforeValidator:
    """Like _clip, for text shown on screen: cut at a word, not inside one."""
    def cut(v):
        if not isinstance(v, str) or len(v) <= n:
            return v
        head = v[: n - 1]
        return (head.rsplit(" ", 1)[0] if " " in head else head).rstrip(" ,;:—-") + "…"
    return BeforeValidator(cut)


Status = Annotated[str | None, _clip(160)]
Memo = Annotated[str | None, _clip(140)]       # a guest's memory (world.Person.memories), bookkeeping too
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


class ChatterScript(BulletinScript):
    """Rock Pool's pieces: Poppy and Gully's quick back-and-forth runs past a bulletin's ten lines (the
    first run's make wanted eleven, 2026-10-30), and story time is many short lines too."""
    lines: list[LiveLine] = Field(min_length=1, max_length=24)


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
                for k in ("guest_name", "guest_role", "guest_gender", "guest_age", "guest_accent"):
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
    guest_age: Age = Field(default=None, description="young, middle or old")
    guest_accent: Accent = Field(default=None, description="british (a local) or american (from away)")
    thread_id: str | None = None
    thread_status: Status = Field(default=None, max_length=160)
    guest_memory: Memo = Field(default=None, max_length=140,
                               description="one line: what we learned about the guest that a later show could call back to")
    ask_next_time: Memo = Field(default=None, max_length=140,
                                description="usually null: something to ask the guest about next time")

    _lift = model_validator(mode="before")(_lift_guest)

    @model_validator(mode="after")
    def _guest_named(self):
        return _check_guest_named(self)


class CouchLine(GuestLine):
    guest_name: str | None = Field(default=None, max_length=40,
                                   description="on a 'guest' line: which guest is speaking")


class CouchScript(InterviewScript):
    """The Last Ferry's couch: a new guest, and the one before still sitting there. guest_name,
    guest_role and guest_gender are the new guest's; each guest line names its speaker."""
    lines: list[CouchLine] = Field(min_length=2, max_length=16)


class ChatterInterviewScript(InterviewScript):
    """A Rock Pool visitor: three voices trading short lines ran past an interview's sixteen (2026-10-30)."""
    lines: list[GuestLine] = Field(min_length=2, max_length=24)


class PanelLine(GuestLine):
    guest_name: str | None = Field(default=None, max_length=40,
                                   description="on a 'guest' line: the panellist speaking, by exact name")


class PanelScript(InterviewScript):
    """The Panel's debate: the chair and three panellists, each guest line naming its panellist (the
    first is lifted onto the script, as for any interview). Longer than an interview: four voices."""
    lines: list[PanelLine] = Field(min_length=4, max_length=24)

    @model_validator(mode="after")
    def _every_panellist_named(self):
        if any(l.speaker == "guest" and not (l.guest_name or "").strip() for l in self.lines):
            raise ValueError("every 'guest' line needs guest_name: the panellist speaking")
        return self


class CallLine(GuestLine):
    guest_name: str | None = Field(default=None, max_length=40,
                                   description="on a 'guest' line: the studio guest by exact name; leave it "
                                               "null for the caller")


class CallScript(BaseModel):
    """A phone-in call (phonein.py): a resident on the line, the presenter, and sometimes the studio
    guest answering them. Two kinds of guest in one item: the caller is cast here, like a vox pop's
    passer-by; the studio guest is booked and named on their own lines."""
    lines: list[CallLine] = Field(min_length=3, max_length=14)
    headline: str = Field(min_length=4, max_length=90)
    # "Have Your Say: " and the whole question overran 60 in the first run, and a retry costs a call.
    lower_third: Annotated[str, _clip_words(60)] = Field(min_length=4, max_length=60)
    caller_name: str = Field(min_length=3, max_length=40, description="the caller's first name and surname")
    caller_from: Annotated[str, _clip_words(40)] = Field(
        max_length=40, description="where they are ringing from, as Jonah would say it: a street, a village, a boat; "
                                   "never the town's own name ('Harbour Row', not 'Harbour Row, Port Wexley')")
    caller_gender: Gender = Field(default=None, description="for casting the caller's voice: 'f' or 'm'")
    caller_age: Age = Field(default=None, description="young, middle or old")
    caller_accent: Accent = Field(default=None, description="british (a local) or american (from away)")
    thread_id: str | None = Field(default=None, description="today's question's thread, or null")
    caller_memory: Memo = Field(default=None, max_length=140,
                                description="one line: what the caller said, so they can ring back another day")
    tip_used: int | None = Field(default=None, description="number of the VIEWER TIP the caller rang about, or null")

    @model_validator(mode="after")
    def _the_caller_speaks(self):
        if not any(l.speaker == "guest" and (l.guest_name or "").strip().lower() in ("", self.caller_name.strip().lower())
                   for l in self.lines):
            raise ValueError("the caller must speak: a 'guest' line with guest_name null (or the caller's name)")
        return self


class FeatureScript(BaseModel):
    """A filmed magazine piece: Miles on location, optionally with one resident."""
    lines: list[GuestLine] = Field(min_length=3, max_length=14)
    headline: str = Field(min_length=4, max_length=90)
    # On screen ("Report from ..."): cut at a word, not failed; a retry cost a whole feature on 2026-10-30.
    location: Annotated[str, _clip_words(60)] = Field(min_length=4, max_length=60,
                                                      description="the place in words, never a backdrop id")
    backdrop: Backdrop
    lower_third: Annotated[str, _clip_words(60)] = Field(min_length=4, max_length=60)   # likewise, the same day
    guest_name: str | None = Field(default=None, max_length=40)
    guest_role: str | None = Field(default=None, max_length=80)
    guest_gender: Gender = None
    guest_age: Age = None
    guest_accent: Accent = None
    thread_id: str | None = None
    thread_status: Status = Field(default=None, max_length=160)
    guest_memory: Memo = Field(default=None, max_length=140)
    ask_next_time: Memo = Field(default=None, max_length=140)

    _lift = model_validator(mode="before")(_lift_guest)

    @model_validator(mode="after")
    def _guest_named(self):
        return _check_guest_named(self)


_STARS = re.compile(r"^\s*(one|two|three|four|five|[1-5])\s+stars?(\s+out\s+of\s+(five|5))?\s*[:,.;\-–—]+\s*", re.I)


def _no_stars(v):
    """'Four stars: worth the climb' under four drawn stars says it twice (2026-10-30): keep the words."""
    if isinstance(v, str) and (m := _STARS.match(v)) and v[m.end():].strip():
        rest = v[m.end():].strip()
        return rest[:1].upper() + rest[1:]
    return v


class ReviewScript(BaseModel):
    """Out and About's review (outabout.py): Meg visits a place to eat or a show and gives it stars out of
    five that the town remembers; the owner, the cook or one of the players may speak for it."""
    lines: list[GuestLine] = Field(min_length=3, max_length=14)
    headline: str = Field(min_length=4, max_length=90)
    lower_third: Annotated[str, _clip_words(60)] = Field(min_length=4, max_length=60)
    place: Annotated[str, _clip_words(40)] = Field(
        max_length=40, description="its name as on the sign or the poster: 'The Gull's Rest', 'Saltby Players'")
    kind: Annotated[str, _clip_words(24)] = Field(
        max_length=24, description="what it is: cafe, restaurant, pub, takeaway, bakery, play, gallery, music night")
    where: Annotated[str, _clip_words(40)] = Field(
        max_length=40, description="where it is, in a few words, never the town's own name: 'the back lane above "
                                   "the harbour'")
    # On screen ("Report from ..."): cut at a word, not failed; a retry cost a whole feature on 2026-10-30.
    location: Annotated[str, _clip_words(60)] = Field(min_length=4, max_length=60,
                                                      description="the place in words, never a backdrop id")
    backdrop: Backdrop
    stars: int = Field(ge=1, le=5, description="out of five: most places three or four, a five is rare, a one rarer")
    verdict: Annotated[str, BeforeValidator(_no_stars), _clip_words(80)] = Field(
        max_length=80, description="the verdict in one line for the card, which shows the stars, so without them: "
                                   "'Worth the walk for the crab alone'")
    guest_name: str | None = Field(default=None, max_length=40, description="the owner, the cook or a player, or null")
    guest_role: str | None = Field(default=None, max_length=80)
    guest_gender: Gender = None
    guest_age: Age = None
    guest_accent: Accent = None
    guest_memory: Memo = Field(default=None, max_length=140)
    ask_next_time: Memo = Field(default=None, max_length=140)

    _lift = model_validator(mode="before")(_lift_guest)

    @model_validator(mode="after")
    def _guest_named(self):
        return _check_guest_named(self)


class VoxLine(BaseModel):
    speaker: GuestSpeaker = Field(validation_alias=SPEAKER_KEY)
    text: str = Field(min_length=1, max_length=600)
    guest_name: str | None = Field(default=None, max_length=40, description="required when speaker is 'guest'")
    guest_gender: Gender = None
    guest_age: Age = None
    guest_accent: Accent = None

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
    guest_age: Age = None
    guest_accent: Accent = None
    archive_clip: str | None = Field(default=None, max_length=8,
                                     description="the id of an ARCHIVE CLIP to play in this section (e.g. 'C1'); "
                                                 "null unless ARCHIVE CLIPS are listed")


class SpecialOutline(BaseModel):
    title: str = Field(max_length=60)
    # Three lines of the title card hold about 200 characters in Bahnschrift. DeepSeek Flash overran the
    # old hard 140 in 2 of its 13 outlines on 2026-10-29 and again in a trial (up to 150), each a whole
    # outline retried: ask for 140, take 180, and cut anything longer at a word.
    standfirst: Annotated[str, _clip_words(180)] = Field(
        max_length=180, description="one-sentence subtitle shown on the title card, under 140 characters")
    # 400 and 300 were too tight for DeepSeek Flash (450 and 354, so a whole outline retried); Sonnet
    # writes 230-340 and 180-260. About 40 s and 30 s spoken at the top.
    intro: str = Field(max_length=600, description="what the anchor says in the studio to hand over: "
                                                   "two to four sentences")
    outro: str = Field(max_length=450, description="what the anchor says back in the studio afterwards: "
                                                   "two or three sentences")
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
    next_development: Annotated[str, _clip(300)] = Field(max_length=300, description="one sentence: the concrete next thing that happens, with a day if relevant")
    people: list[str] = Field(default_factory=list, max_length=4,
                              description="names of known public figures or residents now involved")


class NewThread(BaseModel):
    title: str = Field(max_length=80)
    status: Annotated[str, _clip(200)] = Field(max_length=200, description="what is known so far, one sentence")
    next_development: Annotated[str, _clip(300)] = Field(max_length=300, description="one sentence")
    people: list[str] = Field(default_factory=list, max_length=3)
    from_guest: str | None = Field(default=None, description="the guest's name if this grows from their LOOSE END, else null")


class ThreadMerge(BaseModel):
    """Two threads that are one story under different titles: the duplicate folds into the other."""
    duplicate: str = Field(description="id of the thread that repeats another's story")
    into: str = Field(description="id of the thread to keep: usually the one covered more")


class DeskBreaking(BaseModel):
    """Something sudden the desk has happen now: it airs as breaking news, like a tip-line line."""
    tip: str = Field(min_length=12, max_length=240,
                     description="what has just happened and where, as it would first be phoned in: one or two sentences")


class StoryPlan(BaseModel):
    updates: list[ThreadUpdate] = Field(default_factory=list, max_length=30)    # a batch per call (desk.batch), with room for out-of-turn extras it skips
    new_threads: list[NewThread] = Field(default_factory=list, max_length=3)
    merges: list[ThreadMerge] = Field(default_factory=list, max_length=12)
    breaking: DeskBreaking | None = Field(default=None, description="rare: null on most rounds")
    note: Annotated[str, _clip(200)] = Field(default="", max_length=200, description="one line on the editorial thinking")


class InquiryCommission(BaseModel):
    """Tonight's subject for The Inquiry (inquiry.py): one running story taken in depth."""
    thread_id: str = Field(description="the story's id from the candidates")
    title: Annotated[str, _clip_words(70)] = Field(
        max_length=70, description="the evening's title, a question: 'Who Pays for the Harbour Wall?'")
    # Only ever read by the writers: Flash overran 300 in a trial, and a retry costs a whole commission.
    angle: Annotated[str, _clip_words(400)] = Field(
        max_length=400, description="what the half hour sets out to find, one or two sentences")
    questions: list[Annotated[str, _clip(200)]] = Field(
        min_length=2, max_length=4, description="the questions Pat puts to the guest, one sentence each")
    guest: str = Field(description="the person who has to answer them, in the studio: an exact name from the "
                                   "story's people or the public figures")


class PanelQuestion(BaseModel):
    question: Annotated[str, _clip_words(200)] = Field(max_length=200, description="the question as Dana puts it")
    thread_id: str | None = Field(default=None, description="the story it comes from, by id, or null")


class Panellist(BaseModel):
    name: str = Field(description="an exact name from the PEOPLE list")
    stance: Annotated[str, _clip_words(200)] = Field(
        max_length=200, description="where they stand on tonight's questions, one sentence")


class PanelLineup(BaseModel):
    """Tonight's Panel (panel.py): four questions from the week's news and three panellists who differ."""
    questions: list[PanelQuestion] = Field(min_length=4, max_length=4)
    panellists: list[Panellist] = Field(min_length=3, max_length=3)


class PhoneInBooking(BaseModel):
    """Today's Have Your Say (phonein.py): one question from the day's news and the guest who answers it."""
    thread_id: str = Field(description="the story's id from STORIES")
    question: Annotated[str, _clip_words(120)] = Field(
        max_length=120, description="today's question as Jonah puts it, one that people in town answer differently")
    guest: str = Field(description="the studio guest at the heart of the story: an exact name from PEOPLE")
    guest_stance: Annotated[str, _clip_words(200)] = Field(
        max_length=200, description="where the guest stands, one sentence")
    # Flash wrote 150-180 in the first booking (2026-10-30), each cut off mid-thought at the old 140.
    callers: list[Annotated[str, _clip_words(200)]] = Field(
        min_length=4, max_length=6, description="the kinds of caller who will ring, each with a different view: "
                                                "who they are and what they think, one line each")


class SeniorMemo(BaseModel):
    """The senior editor's review of the story desk's whole board (senior.py)."""
    memo: Annotated[str, _clip(1200)] = Field(
        max_length=1200, description="at most five short directives to the desk, naming threads by id")
    merges: list[ThreadMerge] = Field(default_factory=list, max_length=6)
    new_thread: NewThread | None = Field(default=None, description="one fresh story to open now, or null")


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
    owner_age: Age = None
    owner_accent: Accent = None
    lines: list[AdLine] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def _owner_named(self):
        if any(l.speaker == "owner" for l in self.lines) and not (self.owner_name or "").strip():
            raise ValueError("the owner speaks, so owner_name is required")
        return self


# ------------------------------------------------- continuity promos (continuity.py)


# A slide line wraps to three rows (about 190 characters) and is read out as shown: cut at a word.
SlideLine = Annotated[str, BeforeValidator(
    lambda v: v[:189].rsplit(" ", 1)[0].rstrip(" ,;") + "…" if isinstance(v, str) and len(v) > 190 else v)]


def _cut(n: int) -> BeforeValidator:
    """A name on a slide that runs long: cut at a word, with no ellipsis."""
    return BeforeValidator(lambda v: v[:n].rsplit(" ", 1)[0].rstrip(" &,-") if isinstance(v, str) and len(v) > n else v)


class TrailScript(BaseModel):
    """A trail for a finished special or tonight's documentary; the time and title are added in code."""
    shown: list[Annotated[str, _clip(80)]] = Field(min_length=1, max_length=3,
                                                   description="one to three short lines for the slide, under 50 characters each")
    spoken: str = Field(min_length=10, max_length=320,
                        description="what the announcer says after the time and title: 20 to 40 words")


class CommunityNotice(BaseModel):
    """A public-information slide from a local body, on the practical side of an open story."""
    thread_id: str | None = Field(default=None, description="the open thread it comes from")
    issuer: Annotated[str, _cut(32)] = Field(max_length=32, description="who puts it out, in capitals")
    lines: list[SlideLine] = Field(min_length=1, max_length=2,
                                   description="one or two plain sentences each, read out as shown")


SCRIPT_SCHEMAS: dict[SegmentType, type[BaseModel]] = {
    SegmentType.weather: WeatherScript,
    SegmentType.bulletin: TipBulletinScript,
    SegmentType.breaking: BulletinScript,
    SegmentType.field_report: FieldReportScript,
    SegmentType.sofa: BulletinScript,       # same shape: lines, headline, caption, optional follow-up
    SegmentType.links: BulletinScript,
    SegmentType.monologue: BulletinScript,
    SegmentType.sport: BulletinScript,
    SegmentType.interview: InterviewScript,
    SegmentType.consumer: InterviewScript,
    SegmentType.feature: FeatureScript,
    SegmentType.vox_pop: VoxPopScript,
    SegmentType.call: CallScript,
    SegmentType.review: ReviewScript,
}

_NARROWED: dict[tuple[SegmentType, tuple[str, ...]], type[BaseModel]] = {}


def script_schema(seg_type: SegmentType, cast: tuple[str, ...], couch: bool = False,
                  panel: bool = False, chatter: bool = False) -> type[BaseModel]:
    """The script schema with `lines[].speaker` narrowed to one show's cast.

    The JSON schema the model sees then lists only that show's presenters, the
    same way the Backdrop enum comes from locations.py. `couch`: an interview
    with two guests on The Last Ferry's couch; `panel`: The Panel's debate, three guests; `chatter`:
    Rock Pool's links and visitors, with more and shorter lines than a bulletin or an interview.
    """
    key = (seg_type, cast, couch, panel, chatter)
    if key not in _NARROWED:
        chat = {SegmentType.links: ChatterScript, SegmentType.interview: ChatterInterviewScript}
        base = (PanelScript if panel else CouchScript if couch else chat.get(seg_type) if chatter and seg_type in chat
                else SCRIPT_SCHEMAS[seg_type])
        lf = base.model_fields["lines"]
        line_base = lf.annotation.__args__[0]          # LiveLine, GuestLine, VoxLine or CallLine
        line = create_model(f"{line_base.__name__}_{'_'.join(cast)}"[:64], __base__=line_base,
                            speaker=(Literal[*cast], Field(validation_alias=SPEAKER_KEY)))
        bounds = {k: getattr(m, k) for m in lf.metadata for k in ("min_length", "max_length") if hasattr(m, k)}
        # The class name becomes the json_schema name, which servers cap at 64 characters.
        _NARROWED[key] = create_model(f"{base.__name__}_{'_'.join(cast)}"[:64], __base__=base,
                                      lines=(list[line], Field(**bounds)))
    return _NARROWED[key]
