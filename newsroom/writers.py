"""Turn a planned Segment into a scripted one.

For each segment type there is:
- a system prompt (who the station is, the hard rules, the output contract),
- a user prompt built from the world summary and the word budget,
- a canned template used when the model is unavailable or fails twice,
  so a slot never dies; it just gets a slightly boring script.

Writers only produce *text*. Voicing happens in workers.py so the two can
be tested apart.
"""
from __future__ import annotations

import logging
import random
from datetime import date

from . import llm
from .models import (
    SCRIPT_SCHEMAS,
    BulletinScript,
    FieldReportScript,
    Line,
    LiveLine,
    Segment,
    SegmentState,
    SegmentType,
    VisualCue,
    WeatherScript,
)
from .world import World

log = logging.getLogger(__name__)

STATION = "Port Wexley's evening news on channel 7"

_COMMON_RULES = """\
You write scripts for {station}, a small-town TV newsroom in a FICTIONAL town.
Everything is invented; never reference real people, real companies, or real events.
Tone: warm, dry, local. Specific, concrete details (street names, prices, a quote from a resident).
Rules:
- Use ONLY the speaker ids given in the town briefing. Never invent new speakers.
- Spoken lines only: no stage directions, no brackets, no markdown, no emojis.
- Numbers as words when short ("twelve degrees"); write out units.
- Do not repeat recent headlines. Follow up an open thread by id only when there is
  genuinely new development; a thread covered twice already should rest. Most segments
  should bring a NEW story.
- Stay within the word budget. Return ONLY JSON matching the schema; no commentary.
"""

_SYSTEM: dict[SegmentType, str] = {
    SegmentType.weather: _COMMON_RULES + """
This is the WEATHER segment. The weather presenter speaks (speaker id "weather"),
optionally after a one-sentence handover from "anchor".
Pick a plausible map_state for a coastal town and a temperature in Celsius.
Mention tomorrow briefly. Be cheerful; a small sailing aside is in character.
""",
    SegmentType.bulletin: _COMMON_RULES + """
This is the NEWS BULLETIN. The anchor (speaker id "anchor") reads two or three short
local stories. Each story is one or two sentences. Make at most one of them a follow-up
of an open thread (set thread_id and thread_status); otherwise thread_id is null.
headline = the top story in under 12 words. lower_third = a short caption for it.
""",
    SegmentType.field_report: _COMMON_RULES + """
This is an ON-SITE FIELD REPORT. Structure:
1. "anchor" introduces the story and hands to the reporter (one or two lines).
2. "reporter" reports from the location, includes what people there told them.
3. "anchor" thanks the reporter and adds a one-line tag.
Choose a backdrop from the allowed list and a specific location name.
If this follows up an open thread, set thread_id and a new thread_status.
""",
}


def build_prompt(seg_type: SegmentType, world: World, *, target_s: float) -> tuple[str, str]:
    from .config import CONFIG

    words = int(target_s / 60 * CONFIG.broadcast.words_per_minute)
    system = _SYSTEM[seg_type].format(station=STATION)
    user = (
        f"TOWN BRIEFING\n{world.summary_for_prompt()}\n\n"
        f"Write the {seg_type.value.replace('_', ' ')} segment. "
        f"Word budget: about {words} words total across all lines (plus or minus fifteen percent). "
        f"Today is {date.today():%A %d %B}."
    )
    return system, user


# --------------------------------------------------------------- templates


def _template(seg_type: SegmentType, world: World, rng: random.Random):
    wx_states = ["sunny", "cloudy", "rain", "fog", "wind"]
    if seg_type is SegmentType.weather:
        state = rng.choice(wx_states)
        temp = rng.randint(6, 19)
        return WeatherScript(
            lines=[
                LiveLine(speaker="anchor", text="Now over to Gordon for the weather."),
                LiveLine(speaker="weather", text=(
                    f"Thanks Dana. A {state} evening across {world.town}, {temp} degrees on the harbour "
                    "and a light onshore breeze. Tomorrow looks much the same, with a chance of a "
                    "brighter spell by the afternoon. A fine night for a walk along the front."
                )),
            ],
            headline=f"{state.title()} evening, {temp} degrees",
            map_state=state, temp_c=temp,
        )
    if seg_type is SegmentType.bulletin:
        lm = rng.choice(world.landmarks)
        return BulletinScript(
            lines=[
                LiveLine(speaker="anchor", text=(
                    f"Good evening. The council has confirmed that repairs to {lm} will begin next week, "
                    "with the work expected to take around a month."
                )),
                LiveLine(speaker="anchor", text=(
                    "And the Harrow Street market will stay open an hour later on Saturdays through the autumn, "
                    "after traders voted in favour of the change."
                )),
            ],
            headline=f"Repairs to {lm} begin next week",
            lower_third="Council confirms repair schedule",
        )
    if seg_type is SegmentType.field_report:
        return FieldReportScript(
            lines=[
                LiveLine(speaker="anchor", text="Our reporter Miles Okafor is down at the harbour tonight. Miles?"),
                LiveLine(speaker="reporter", text=(
                    "Thanks Dana. I'm standing by the old cannery, where a group of volunteers has spent the day "
                    "clearing the slipway. One of them told me it's the first time in twenty years the ramp has "
                    "been usable at low tide. They're hoping to have small boats launching from here by spring."
                )),
                LiveLine(speaker="anchor", text="Thanks Miles. We'll keep an eye on that one."),
            ],
            headline="Volunteers clear the old cannery slipway",
            location="The old cannery, Port Wexley harbour",
            backdrop="harbour",
            lower_third="Harbour slipway cleared by volunteers",
        )
    raise ValueError(seg_type)


# ------------------------------------------------------------------ public


def script_segment(seg: Segment, world: World) -> Segment:
    """Fill `seg.lines`, `seg.cues`, `seg.headline`; mark `scripted`. Updates world."""
    if seg.type not in SCRIPT_SCHEMAS:
        raise ValueError(f"{seg.type} is not an LLM-scripted type")

    system, user = build_prompt(seg.type, world, target_s=seg.target_s)
    schema = SCRIPT_SCHEMAS[seg.type]
    try:
        script = llm.complete_json(seg.type.value, schema, system, user)
        source = "llm"
    except llm.LLMError as e:
        log.warning("%s slot %d: using template (%s)", seg.type.value, seg.slot_id, e)
        script = _template(seg.type, world, random.Random(seg.content_hash or seg.id))
        source = "template"

    seg.lines = [Line(speaker=l.speaker, text=l.text.strip()) for l in script.lines if l.text.strip()]
    seg.headline = script.headline
    seg.cues = _cues_for(seg, script)
    _apply_to_world(seg, script, world)
    seg.state = SegmentState.scripted
    log.info("scripted %s slot %d via %s: %r (%d lines)", seg.type.value, seg.slot_id, source,
             seg.headline, len(seg.lines))
    return seg


def _cues_for(seg: Segment, script) -> list[VisualCue]:
    cues: list[VisualCue] = [VisualCue(at_s=0, kind="ticker", payload={"text": script.headline})]
    if isinstance(script, WeatherScript):
        cues.append(VisualCue(at_s=0, kind="map_state", payload={"state": script.map_state, "temp_c": script.temp_c}))
        cues.append(VisualCue(at_s=0, kind="lower_third", payload={"title": "Weather", "subtitle": script.headline}))
    elif isinstance(script, BulletinScript):
        cues.append(VisualCue(at_s=0, kind="lower_third", payload={"title": script.headline, "subtitle": script.lower_third}))
    elif isinstance(script, FieldReportScript):
        cues.append(VisualCue(at_s=0, kind="backdrop", payload={"backdrop": script.backdrop}))
        cues.append(VisualCue(at_s=0, kind="lower_third",
                              payload={"title": script.lower_third, "subtitle": f"Live from {script.location}"}))
    return cues


def _apply_to_world(seg: Segment, script, world: World) -> None:
    world.record_headline(script.headline)
    if isinstance(script, WeatherScript):
        world.record_weather(script.map_state, script.temp_c, script.headline)
    else:
        tid = getattr(script, "thread_id", None)
        status = getattr(script, "thread_status", None)
        known = {t.id for t in world.threads}
        seg.thread_id = world.update_thread(tid if tid in known else None, script.headline, status)
