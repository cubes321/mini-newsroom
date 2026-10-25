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

from . import llm, schedule
from .locations import locations_for_prompt
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
    script_schema,
)
from .world import World

log = logging.getLogger(__name__)

_COMMON_RULES = """\
You write scripts for {station}, a small-town TV newsroom in a FICTIONAL town.
Everything is invented; never reference real people, real companies, or real events.
Tone: {tone}. Specific, concrete details (street names, prices, a quote from a resident).
{weight}Rules:
- Use ONLY the speaker ids given in the town briefing. Never invent new speakers.
- Spoken lines only: no stage directions, no brackets, no markdown, no emojis.
- Numbers as words when short ("twelve degrees"); write out units.
- Do not repeat recent headlines. When you follow up an open thread (by id), report its NEXT
  development or a concrete step towards it; never restate what was already reported. Threads
  without a NEXT should rest. Most segments should still bring at least one NEW story.
- Quote the listed public figures by name where natural; do not invent a new mayor, chief or
  councillor when a listed one fits. Respect the dates in the briefing.
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
Choose a backdrop id from the LOCATIONS list for the picture. Separately, location is the
place name as a viewer would say it ("the slipway behind the old cannery"), never a backdrop id.
If this follows up an open thread, set thread_id and a new thread_status.
""",
}

# Breakfast (Morning Tide): the two hosts on the sofa front everything; Gordon and Miles
# keep their jobs. Keyed by type, used in place of _SYSTEM when the show is breakfast.
_BREAKFAST: dict[SegmentType, str] = {
    SegmentType.bulletin: _COMMON_RULES + """
This is THE HEADLINES, read on the breakfast sofa. "host_a" reads two or three short local
stories, one or two sentences each; "host_b" may add ONE short line of reaction. Make at most
one of them a follow-up of an open thread (set thread_id and thread_status); otherwise null.
headline = the top story in under 12 words. lower_third = a short caption for it.
""",
    SegmentType.sofa: _COMMON_RULES + """
This is a SOFA CHAT between the two breakfast hosts, "host_a" and "host_b", taking turns in
short lines with natural back-and-forth (a little teasing is fine; no studio guests speak).
Spend most of it on ONE light local item in a bit more depth: a person, an event, something
odd or cheering. Finish with a quick look at what's on in town today. It may follow up a
lighter open thread (thread_id, thread_status); otherwise thread_id is null.
headline = the item in under 12 words. lower_third = a short caption for it.
""",
    SegmentType.weather: _COMMON_RULES + """
This is the MORNING WEATHER. "host_a" or "host_b" hands to Gordon in one sentence, then the
weather presenter (speaker id "weather") gives today: the morning, the afternoon, the evening.
Pick a plausible map_state for a coastal town and a temperature in Celsius. Mention the morning
tide or the sea state in passing. Be cheerful; a small sailing aside is in character.
""",
    SegmentType.field_report: _COMMON_RULES + """
This is an ON-SITE FIELD REPORT on the breakfast show. Structure:
1. "host_a" (or "host_b") introduces the story from the sofa and hands to the reporter.
2. "reporter" reports live from the location this morning, including what people there said.
3. "host_a" or "host_b" thanks the reporter with a one-line tag.
Choose a backdrop id from the LOCATIONS list for the picture. Separately, location is the
place name as a viewer would say it ("the slipway behind the old cannery"), never a backdrop id.
If this follows up an open thread, set thread_id and a new thread_status.
""",
}


_LIGHT = """Weight: a LIGHTER programme than the main news. Prefer warm, quirky, everyday local
stories, people and what's on; keep grim or heavy stories out unless the briefing names a
BIG RUNNING STORY, which the headlines lead with briefly (what is new), then move on.
"""


BIG_STORY_MIN_MENTIONS = 4      # a peak the desk planned but nobody has covered yet doesn't count


def big_story(world: World):
    """The one running story a light show shouldn't skip: the most-covered thread at its peak."""
    peak = [t for t in world.open_threads() if t.phase == "peak" and t.mentions >= BIG_STORY_MIN_MENTIONS]
    return max(peak, key=lambda t: (t.mentions, t.updated), default=None)


def _part(show: schedule.Show) -> str:
    """'morning', 'afternoon', ... for greetings; breakfast is always the morning."""
    return "morning" if show.id == "breakfast" else schedule.part_of_day(schedule.now())


def build_prompt(seg_type: SegmentType, world: World, *, target_s: float,
                 show: schedule.Show | None = None) -> tuple[str, str]:
    from .config import CONFIG

    show = show or schedule.get("news")
    words = int(target_s / 60 * CONFIG.broadcast.words_per_minute)
    table = _BREAKFAST if show.id == "breakfast" else _SYSTEM
    system = table[seg_type].format(station=show.station, tone=show.tone, weight=_LIGHT if show.light else "")
    user = (
        f"TOWN BRIEFING\n{world.summary_for_prompt(show.cast_for(seg_type))}\n\n"
        f"Write the {seg_type.value.replace('_', ' ')} segment. "
        f"Word budget: about {words} words total across all lines (plus or minus fifteen percent). "
        f"Today is {date.today():%A %d %B}; it is the {_part(show)}."
    )
    if show.light:
        big = big_story(world)
        user += (f"\n\nBIG RUNNING STORY: [{big.id}] {big.title}. NEXT: {big.next_development or 'no new step yet'}"
                 if big else "\n\nNo big running story today: keep it light.")
    if seg_type is SegmentType.field_report:
        user += f"\n\nLOCATIONS (backdrop ids):\n{locations_for_prompt()}"
    return system, user


# --------------------------------------------------------------- templates


def _template(seg_type: SegmentType, world: World, rng: random.Random, show: schedule.Show):
    """Canned scripts fronted by the show's lead; every LLM-scripted type needs one."""
    wx_states = ["sunny", "cloudy", "rain", "fog", "wind"]
    lead = show.lead
    lead_c = world.character(lead)
    lead_name = lead_c.name.split()[0] if lead_c else "Dana"
    part = _part(show)
    part = "evening" if part == "night" else part
    if seg_type is SegmentType.weather:
        state = rng.choice(wx_states)
        temp = rng.randint(6, 19)
        later = ("The afternoon looks much the same, with a chance of a brighter spell later on. "
                 "A fine day to get out on the water." if part == "morning" else
                 "Tomorrow looks much the same, with a chance of a brighter spell by the afternoon. "
                 "A fine night for a walk along the front.")
        return WeatherScript(
            lines=[
                LiveLine(speaker=lead, text="Now over to Gordon for the weather."),
                LiveLine(speaker="weather", text=(
                    f"Thanks {lead_name}. A {state} {part} across {world.town}, {temp} degrees on the harbour "
                    f"and a light onshore breeze. {later}"
                )),
            ],
            headline=f"{state.title()} {part}, {temp} degrees",
            map_state=state, temp_c=temp,
        )
    if seg_type is SegmentType.sofa:
        lm = rng.choice(world.landmarks)
        return BulletinScript(
            lines=[
                LiveLine(speaker="host_a", text=(
                    f"Now, Jonah, I walked past {lm} on the way in this morning and there was a queue already."
                )),
                LiveLine(speaker="host_b", text="At half past five? For what, Rosie?"),
                LiveLine(speaker="host_a", text=(
                    "The Harrow Street bakers are doing their autumn loaf today, and word has got round."
                )),
                LiveLine(speaker="host_b", text=(
                    "Well, I knead to know more. Sorry. Do send us a picture if you're in that queue."
                )),
                LiveLine(speaker="host_a", text=(
                    "And later today, the library's reading hour is at eleven, and the lifeboat crew "
                    "are out on the water for practice this afternoon, so give them a wave."
                )),
            ],
            headline="Early queue for the market bakers' autumn loaf",
            lower_third="Harrow Street market, this morning",
        )
    if seg_type is SegmentType.bulletin:
        lm = rng.choice(world.landmarks)
        return BulletinScript(
            lines=[
                LiveLine(speaker=lead, text=(
                    f"Good {part}. The council has confirmed that repairs to {lm} will begin next week, "
                    "with the work expected to take around a month."
                )),
                LiveLine(speaker=lead, text=(
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
                LiveLine(speaker=lead, text=(
                    f"Our reporter Miles Okafor is down at the harbour {'tonight' if part == 'evening' else 'this ' + part}. Miles?"
                )),
                LiveLine(speaker="reporter", text=(
                    f"Thanks {lead_name}. I'm standing by the old cannery, where a group of volunteers has been "
                    "clearing the slipway. One of them told me it's the first time in twenty years the ramp has "
                    "been usable at low tide. They're hoping to have small boats launching from here by spring."
                )),
                LiveLine(speaker=lead, text="Thanks Miles. We'll keep an eye on that one."),
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

    show = schedule.get(seg.show)
    system, user = build_prompt(seg.type, world, target_s=seg.target_s, show=show)
    schema = script_schema(seg.type, show.cast_for(seg.type))
    try:
        script = llm.complete_json(seg.type.value, schema, system, user)
        source = "llm"
    except llm.LLMError as e:
        log.warning("%s slot %d: using template (%s)", seg.type.value, seg.slot_id, e)
        script = _template(seg.type, world, random.Random(seg.content_hash or seg.id), show)
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
    world.record_aired(seg.type.value, script.headline, seg.thread_id, " ".join(l.text for l in seg.lines))
