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
import time
from collections import deque
from datetime import date, datetime

from . import llm, schedule, tides, tipline
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
    FeatureScript,
    GuestLine,
    InterviewScript,
    VoxLine,
    VoxPopScript,
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

_GUEST_RULES = """\
Studio guests: speaker id "guest". Name the guest ONCE in guest_name (first name and surname),
with guest_role and guest_gender ("f" or "m"); their lines use speaker "guest". Prefer a listed
public figure or a resident we have met when one fits; otherwise invent a plausible resident.
Do not book anyone listed under RECENT GUESTS.
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
    SegmentType.breaking: _COMMON_RULES + """
This is BREAKING NEWS, interrupting {interrupting}. The anchor (speaker id "anchor") cuts in from
the news desk: what has happened, where, and that it is not yet confirmed (it came in from a viewer
on the tip-line). Keep it small-town and calm; no casualties or horrors that the tip doesn't state.
The reporter (speaker id "reporter") may phone in for one to three short lines if he plausibly
could be nearby. The anchor finishes by promising more in the next bulletin and handing back to
{interrupting}. thread_id is null: this opens a new story; thread_status is what is known so far.
headline = the breaking story in under 12 words. lower_third = a short caption.
""",
    SegmentType.interview: _COMMON_RULES + _GUEST_RULES + """
This is a STUDIO INTERVIEW on the news. The anchor (speaker id "anchor") has one guest in the
studio armchair: someone with a stake in an open thread, ideally a listed public figure or a
resident we have met. One line of introduction, then four to six questions with the guest's
answers; the anchor presses politely on the NEXT development. A short thank-you to close.
Set thread_id and thread_status for the thread it advances.
headline = what the guest said that is news, under 12 words. lower_third = a short caption.
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
odd or cheering. It may end with one thing on in town today that the sofa hasn't mentioned yet.
It may follow up a lighter open thread (thread_id, thread_status); otherwise thread_id is null.
headline = the item itself in under 12 words: what happened or who it's about, never the format
("hosts chat about the papers"). lower_third = a short caption for it.
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
    SegmentType.interview: _COMMON_RULES + _GUEST_RULES + """
This is the GUEST ON THE SOFA: the sort of guest a breakfast show books, as THIS ITEM says. One
guest in the armchair; "host_a" leads the chat and "host_b" chips in. Keep it light: an uplifting
story, a funny guest who gets the hosts laughing, or someone here to plug something (a book, a
film, a television series, a gig or a show in town), who names it and says when and where. A
visitor from outside the town is fine for a plug; the guest and their work are invented, never a
real title or a real name. It comes mid-programme: the first line introduces the guest by name
(no good morning to the town, no date, no hosts introducing themselves; it is television, so
viewers, never listeners), then four to six easy exchanges with one funny or
touching moment, and a plug or a thank-you to close. Not hard news: thread_id is null unless a
lighter open thread genuinely fits.
headline = the guest and their story in under 12 words. lower_third = a short caption.
""",
}


# Coastwide, the early-evening magazine: Pat (mag_a) and Clive (mag_b) in the studio armchairs,
# Miles out filming, Gordon with a short weather.
_MAGAZINE: dict[SegmentType, str] = {
    SegmentType.links: _COMMON_RULES + """
These are the PRESENTERS' LINKS on Coastwide. "mag_a" (Pat) and "mag_b" (Clive) chat in short
alternating lines: a welcome, a bit of banter about something small and local (Clive has usually
found an odd fact), and what is coming up: a filmed report, a guest in the studio, the vox pop
and the consumer slot. No guests speak. Do not open a new story; thread_id is null unless you
mention an open thread in passing.
headline = the evening's theme in under 12 words. lower_third = "Coastwide" plus a short tag.
""",
    SegmentType.feature: _COMMON_RULES + _GUEST_RULES + """
This is a FILMED FEATURE on Coastwide: a few minutes on one local person, place or tradition,
not hard news. Structure:
1. "mag_a" or "mag_b" introduces it in one or two lines.
2. "reporter" (Miles) tells the story from the location; one resident ("guest", named in
   guest_name with guest_role and guest_gender) may speak two or three times.
3. "mag_a" or "mag_b" comes back with a one-line tag.
Choose a backdrop id from the LOCATIONS list; location is the place in words, never an id.
""",
    SegmentType.interview: _COMMON_RULES + _GUEST_RULES + """
This is the STUDIO GUEST on Coastwide. Pat ("mag_a") talks to one guest in the armchair: a
resident with something to show or tell (a hobby, a job, a bit of town history), or a public
figure off-duty. Warm and curious; let the guest tell a story with a detail or two.
Set thread_id only if the chat genuinely moves an open thread on.
headline = the guest and their story in under 12 words. lower_third = a short caption.
""",
    SegmentType.vox_pop: _COMMON_RULES + """
This is the VOX POP on Coastwide. Miles ("reporter") asks ONE question in a public place, then
three or four passers-by answer in a line or two each. Each passer-by is speaker "guest" with
their own guest_name (first name and surname) and guest_gender; make them different ages and
opinions, and let one be funny. Miles may add a short link between answers. Choose a light
question tied to something in the briefing (what the town thinks of the ghost tours, the best
chip shop, the quay ban...). question = the question as a caption. Choose a backdrop id from the
LOCATIONS list; location is the place in words.
""",
    SegmentType.consumer: _COMMON_RULES + _GUEST_RULES + """
This is the CONSUMER SLOT on Coastwide, fronted by Clive ("mag_b"). One practical item for
viewers: prices at the market, a rogue trader warning, a bus fare change, a parking charge, a
refund someone fought for. Clive explains it and may talk to one guest (a trader, a council
officer, the viewer who complained), named in guest_name with role and gender, or set guest_name
to null and speak alone. End with one clear tip for viewers.
headline = the item in under 12 words. lower_third = a short caption.
""",
    SegmentType.weather: _COMMON_RULES + """
This is a SHORT EVENING WEATHER on Coastwide. "mag_a" or "mag_b" hands to Gordon in one line,
then the weather presenter (speaker id "weather") gives tonight and tomorrow in a few sentences.
Pick a plausible map_state for a coastal town and a temperature in Celsius.
""",
}

# The Last Ferry, the late-night talk show: Vincent (late_host) and one guest at a time.
_LATE: dict[SegmentType, str] = {
    SegmentType.monologue: _COMMON_RULES + """
This is the OPENING MONOLOGUE of The Last Ferry. The host ("late_host", Vincent) speaks alone:
a good-evening, then four to six short wry observations on today's headlines and goings-on in
the town (from the briefing), affectionate rather than cruel, then a line saying a guest is
coming up (do not name them). Spoken jokes, not stage directions. thread_id is null.
headline = the monologue's main topic in under 12 words. lower_third = "The Last Ferry" and a tag.
""",
    SegmentType.interview: _COMMON_RULES + _GUEST_RULES + """
This is the GUEST INTERVIEW on The Last Ferry: a long, relaxed late-night conversation. Vincent
("late_host") talks to one guest: a public figure being more candid than usual, or a local
character with a life story (a retired lighthouse keeper, the oldest member of the sea-swimming
club, a market trader with a past). Get stories, a laugh, and one moment of something real; touch
on what is going on in town. Vincent asks short questions; the guest talks more than he does.
headline = the guest and the best thing they said, under 12 words. lower_third = a short caption.
""",
    SegmentType.links: _COMMON_RULES + """
This is a SHORT DESK PIECE on The Last Ferry between guests. Vincent ("late_host") speaks alone, wry
and warm, on the subject given in THIS ITEM (a viewer's letter, tomorrow's papers, what's on). No
guests speak. thread_id is null unless you mention an open thread in passing.
headline = the piece in under 12 words. lower_third = "The Last Ferry" plus a short tag.
""",
    SegmentType.vox_pop: _COMMON_RULES + """
This is the LATE VOX POP on The Last Ferry. Vincent ("late_host") hands over in one line; Miles
("reporter") is out in town late at night and asks ONE question; then three or four night owls
answer in a line or two each. Each is speaker "guest" with their own guest_name (first name and
surname) and guest_gender; different ages and moods, one of them funny. Vincent may add one line
back in the studio. question = the question as a caption. Choose a backdrop id from the LOCATIONS
list; location is the place in words.
""",
}

_LIGHT = """Weight: a LIGHTER programme than the main news. Prefer warm, quirky, everyday local
stories, people and what's on; keep grim or heavy stories out unless the briefing names a
BIG RUNNING STORY, which the headlines lead with briefly (what is new), then move on.
"""


BIG_STORY_MIN_MENTIONS = 4      # a peak the desk planned but nobody has covered yet doesn't count
BREAKING_LEAD_S = 2 * 3600      # bulletins lead with a story this long after it broke

_CONT = """PART TWO: you are CONTINUING the conversation with {name} ({role}) after the break. Use the
same guest_name, guest_role and guest_gender. One line welcoming viewers back, no long reintroduction,
then pick up where it left off and go somewhere new: another story, a different side of them.
Part one, for continuity: keep every fact the same, and do NOT ask these questions again or retell
the answers:
{asked}"""

# Breakfast runs its dozen sofa angles round five times a morning; without this the same angle
# gets the same item every lap (the town's birthday six times, ages that changed between chats).
SOFA_MEMORY = 24                # this morning's sofa headlines shown to the writer
SOFA_SAME_ANGLE = 4             # earlier chats on this item's angle, with an excerpt

_SOFA_SO_FAR = """ON THE SOFA ALREADY THIS MORNING (do NOT retell any of these, even when the angle comes round
again: pick a different person, place or thing, and don't build the chat round anyone, or any pet,
already featured; a passing mention is fine):
{heads}{same}
Facts already given on air this morning are settled: an anniversary, a birthday, an age or a date
said once is not announced again, and never contradicted."""

_CLOSE = """This is the END of the programme. Wrap up warmly: a nod to what was on, thanks to anyone
who joined you, a {goodbye}; {next_title} follows at {next_at}. No new stories."""

# The last interview per show, so a "cont" part keeps the same guest (see schedule.py).
_last_interview: dict[str, dict] = {}


def big_story(world: World):
    """The one running story a light show shouldn't skip: something that broke as breaking news
    today, else the most-covered thread at its peak."""
    broke = [t for t in world.open_threads() if t.breaking == world.last_date]
    if broke:
        return max(broke, key=lambda t: (t.updated, t.mentions))
    peak = [t for t in world.open_threads() if t.phase == "peak" and t.mentions >= BIG_STORY_MIN_MENTIONS]
    return max(peak, key=lambda t: (t.mentions, t.updated), default=None)


def _sofa_so_far(world: World, show: schedule.Show, brief: str, part: str) -> str:
    """What the sofa has already done this morning, for the next chat (or the goodbye's nod)."""
    aired = world.aired_today(SegmentType.sofa.value, show.id)
    if not aired:
        return ""
    heads = "\n".join(f"  - {e['headline']}" for e in aired[-SOFA_MEMORY:])
    if part == "close":
        guests = _guests_so_far(world, show)
        return f"ON THE SOFA THIS MORNING (for the nod to what was on):\n{heads}" + (
            f"\nAND IN THE ARMCHAIR:\n{guests}" if guests else "")
    same = [e for e in aired if brief and e.get("brief") == brief][-SOFA_SAME_ANGLE:]
    same_s = ("\nEARLIER CHATS ON THIS ITEM'S ANGLE, how they began (find something else):\n"
              + "\n".join(f"  - {e['headline']}: {e['text']}" for e in same)) if same else ""
    return _SOFA_SO_FAR.format(heads=heads, same=same_s)


def _guests_so_far(world: World, show: schedule.Show) -> str:
    """This morning's guests in the armchair, one headline each."""
    return "\n".join(f"  - {e['headline']}" for e in world.aired_today(SegmentType.interview.value, show.id))


def _part(show: schedule.Show) -> str:
    """'morning', 'afternoon', ... for greetings; breakfast is always the morning."""
    return "morning" if show.id == "breakfast" else schedule.part_of_day(schedule.now())


def build_prompt(seg_type: SegmentType, world: World, *, target_s: float,
                 show: schedule.Show | None = None, part: str = "", brief: str = "",
                 at_ts: float | None = None, work: dict | None = None,
                 tips: list[str] | None = None) -> tuple[str, str]:
    """System and user prompt. `part` and `brief` come from the show's running order:
    the big running story only at the top of a programme that has one, a second part
    with the same guest, the sign-off."""
    from .config import CONFIG

    show = show or schedule.get("news")
    words = int(target_s / 60 * CONFIG.broadcast.words_per_minute)
    table = {"breakfast": _BREAKFAST, "magazine": _MAGAZINE, "late": _LATE}.get(show.id, {})
    system = table.get(seg_type, _SYSTEM.get(seg_type, ""))
    work = work or {}
    system = system.format(station=show.station, tone=show.tone, weight=_LIGHT if show.light else "",
                           interrupting=work.get("interrupting", "the programme"))
    user = (
        f"TOWN BRIEFING\n{world.summary_for_prompt(show.cast_for(seg_type))}\n\n"
        f"Write the {seg_type.value.replace('_', ' ')} segment. "
        f"Word budget: about {words} words total across all lines (plus or minus fifteen percent). "
        f"Today is {date.today():%A %d %B}; it is the {_part(show)}."
    )
    if show.light:
        big = big_story(world)
        if big and show.opens and part != "open" and seg_type is not SegmentType.bulletin:
            user += (f"\n\nBIG RUNNING STORY: [{big.id}] {big.title}. It was covered at the top of the programme: "
                     "a passing mention at most, and nothing about it unless it fits this item.")
        else:
            user += (f"\n\nBIG RUNNING STORY: [{big.id}] {big.title}. NEXT: {big.next_development or 'no new step yet'}"
                     if big else "\n\nNo big running story today: keep it light.")
    cont = _last_interview.get(show.id) if part == "cont" and seg_type is SegmentType.interview else None
    if seg_type is SegmentType.weather or show.id in ("breakfast", "late"):
        today = datetime.fromtimestamp(at_ts or schedule.now()).date()
        user += "\n\n" + tides.for_prompt(today, world.last_weather.get("map_state"))
    if brief:
        user += f"\n\nTHIS ITEM: {brief}."
    so_far = _sofa_so_far(world, show, brief, part) if seg_type is SegmentType.sofa else ""
    if so_far:
        user += "\n\n" + so_far
    guests = _guests_so_far(world, show) if seg_type is SegmentType.interview and show.id == "breakfast" else ""
    if guests:
        user += ("\n\nIN THE ARMCHAIR ALREADY THIS MORNING (book a different sort of person, and give anything "
                 f"they plug a title unlike these):\n{guests}")
    if cont:
        user += "\n\n" + _CONT.format(**cont)
    elif seg_type in (SegmentType.interview, SegmentType.feature, SegmentType.consumer, SegmentType.vox_pop):
        user += f"\n\nRECENT GUESTS (book someone else): {', '.join(_recent_guests) or 'none yet'}"
    if seg_type is SegmentType.breaking:
        user += f"\n\nTHE TIP (from a viewer, unconfirmed): {work.get('tip', '')}"
    if seg_type is SegmentType.bulletin:
        now = at_ts or schedule.now()
        broke = [t for t in world.open_threads() if t.breaking_ts and 0 <= now - t.breaking_ts < BREAKING_LEAD_S]
        if broke:
            t = max(broke, key=lambda t: t.breaking_ts)
            user += (f"\n\nSTORY THAT BROKE {int((now - t.breaking_ts) // 60)} MINUTES AGO: [{t.id}] {t.title}. "
                     f"Known so far: {t.status}. Lead with it, as the follow-up of this thread: thread_id \"{t.id}\" and "
                     "a thread_status saying what is new, or plainly what is still not confirmed. "
                     "Do not invent casualties.")
    if tips:
        user += ("\n\nVIEWER TIPS from the tip-line (unconfirmed; use at most one, as a short item, and set "
                 "tip_used to its number; otherwise tip_used is null):\n"
                 + "\n".join(f"  {i + 1}. {t}" for i, t in enumerate(tips)))
    if part == "close":
        end = schedule.show_end(at_ts or schedule.now())
        user += "\n\n" + _CLOSE.format(goodbye="goodbye" if _part(show) == "morning" else "goodnight",
                                        next_title=schedule.show_at(end).title.title(),
                                        next_at=time.strftime("%H:%M", time.localtime(end)))
    if seg_type in (SegmentType.field_report, SegmentType.feature, SegmentType.vox_pop):
        user += f"\n\nLOCATIONS (backdrop ids):\n{locations_for_prompt()}"
    return system, user


# --------------------------------------------------------------- templates


def _template(seg_type: SegmentType, world: World, rng: random.Random, show: schedule.Show, part_: str = "",
              work: dict | None = None):
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
    if seg_type is SegmentType.breaking:
        tip = (work or {}).get("tip", "reports of an incident in town")
        back = (work or {}).get("interrupting", "the programme")
        return BulletinScript(
            lines=[
                LiveLine(speaker="anchor", text="We're interrupting the programme with some breaking news."),
                LiveLine(speaker="anchor", text=f"We're hearing reports that {tip[:1].lower() + tip[1:].rstrip('.')}. "
                                                "That hasn't been confirmed yet; it came in from a viewer a few minutes ago."),
                LiveLine(speaker="anchor", text=f"We'll have more in our next bulletin. Now, back to {back}."),
            ],
            headline=tip[:80],
            lower_third="Breaking: reports from a viewer",
        )
    if seg_type is SegmentType.sofa and part_ == "close":
        return BulletinScript(
            lines=[
                LiveLine(speaker="host_a", text="That's all from us this morning. Thank you for having us on with your breakfast."),
                LiveLine(speaker="host_b", text="Have a good day, Port Wexley. The news is next."),
            ],
            headline="Goodbye from Morning Tide",
            lower_third="Morning Tide, channel seven",
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
    other = next((c for c in show.cast_for(seg_type) if c not in (lead, "guest", "weather", "reporter")), lead)
    if seg_type is SegmentType.links and part_ == "close":
        return BulletinScript(
            lines=[LiveLine(speaker=lead, text=f"That's all from {show.title.title()} tonight. Thank you to all our guests."),
                   LiveLine(speaker=other, text="Goodnight from us, and the news is next.")
                   if other != lead else LiveLine(speaker=lead, text="Goodnight, Port Wexley. The news is next.")],
            headline=f"Goodnight from {show.title.title()}",
            lower_third=f"{show.title.title()}, channel seven",
        )
    if seg_type is SegmentType.links and show.id == "late":
        return BulletinScript(
            lines=[LiveLine(speaker=lead, text="A letter now, from a viewer on Harrow Street, who asks why the gulls "
                                               "only steal chips from people who have just sat down."),
                   LiveLine(speaker=lead, text="I have no answer. I have only sympathy, and a hat I no longer wear.")],
            headline="A letter about the gulls",
            lower_third="The Last Ferry",
        )
    if seg_type is SegmentType.links:
        return BulletinScript(
            lines=[
                LiveLine(speaker=lead, text=f"Good {part}, and welcome to {show.title.title()}."),
                LiveLine(speaker=other, text="Did you know the Town Hall clock has stopped at twenty past four more often than any other time?"),
                LiveLine(speaker=lead, text="I did not, and I'm not sure I needed to. Coming up: a guest in the studio, the vox pop, and your money."),
            ],
            headline="Tonight on Coastwide",
            lower_third=f"{show.title.title()}, channel seven",
        )
    if seg_type is SegmentType.monologue:
        lm = rng.choice(world.landmarks)
        return BulletinScript(
            lines=[
                LiveLine(speaker=lead, text=f"Good evening, and welcome aboard the last ferry of the night."),
                LiveLine(speaker=lead, text=f"Busy day in {world.town}. Somebody told me {lm} is having a moment. "
                                            "I've lived here long enough to know that means a committee."),
                LiveLine(speaker=lead, text="My guest tonight has a story or two. Stay with us."),
            ],
            headline="The day in Port Wexley, briefly",
            lower_third="The Last Ferry",
        )
    if seg_type in (SegmentType.interview, SegmentType.consumer):
        host = other if seg_type is SegmentType.consumer else lead
        p = next((p for p in world.people if p.kind == "resident"), None) or world.people[0]
        topic = "your money" if seg_type is SegmentType.consumer else "the week in town"
        return InterviewScript(
            lines=[
                GuestLine(speaker=host, text=f"With me tonight is {p.name}, {p.role}. Thank you for coming in."),
                GuestLine(speaker="guest", text="Happy to. It's been quite a week, to be honest."),
                GuestLine(speaker=host, text=f"Tell me about {topic}. What's changed?"),
                GuestLine(speaker="guest", text="People are talking to each other more, which in this town is saying something."),
                GuestLine(speaker=host, text="We'll leave it there. Thank you."),
            ],
            headline=f"{p.name} on {topic}",
            lower_third=p.role[:60],
            guest_name=p.name, guest_role=p.role,
        )
    if seg_type is SegmentType.feature:
        return FeatureScript(
            lines=[
                GuestLine(speaker=lead, text="Now, Miles has been down to the lifeboat station to meet the crew's newest volunteer."),
                GuestLine(speaker="reporter", text="Every Tuesday night the crew train here, whatever the weather, and this month there's a new face."),
                GuestLine(speaker="guest", text="I grew up watching them go out. I thought it was about time I learned how."),
                GuestLine(speaker="reporter", text="Training takes about a year before you go out on a real shout."),
                GuestLine(speaker=lead, text="Good luck to her. Thanks, Miles."),
            ],
            headline="The lifeboat crew's newest volunteer",
            location="the lifeboat station", backdrop="lifeboat_station",
            lower_third="New volunteer joins lifeboat crew",
            guest_name="Kerry Lyle", guest_role="trainee lifeboat crew", guest_gender="f",
        )
    if seg_type is SegmentType.vox_pop:
        return VoxPopScript(
            lines=[
                VoxLine(speaker="reporter", text="We asked people on the high street: what would you put in a time capsule for Port Wexley?"),
                VoxLine(speaker="guest", text="A fish supper. Wrapped properly.", guest_name="Len Hargreaves", guest_gender="m"),
                VoxLine(speaker="guest", text="The bus timetable, so they can laugh at it.", guest_name="Abi Okoro", guest_gender="f"),
                VoxLine(speaker="guest", text="A photo of the harbour at sunrise. Nothing beats it.", guest_name="Maureen Tate", guest_gender="f"),
            ],
            question="What would you put in a Port Wexley time capsule?",
            headline="What goes in the town's time capsule?",
            location="the high street", backdrop="main_street",
        )
    raise ValueError(seg_type)


# ------------------------------------------------------------------ public


def script_segment(seg: Segment, world: World) -> Segment:
    """Fill `seg.lines`, `seg.cues`, `seg.headline`; mark `scripted`. Updates world."""
    if seg.type not in SCRIPT_SCHEMAS:
        raise ValueError(f"{seg.type} is not an LLM-scripted type")

    show = schedule.get(seg.show)
    # A second part continues only the interview the producer planned as its first part (the slot
    # before, or the one before an ad break); after a restart that one may have come from the
    # cache, and then this is a fresh interview.
    first = seg.work.get("first_part", seg.slot_id - 1)
    cont = seg.part == "cont" and _last_interview.get(show.id, {}).get("slot") == first
    part = "" if seg.part == "cont" and not cont else seg.part
    tips = tipline.offer() if seg.type is SegmentType.bulletin else []
    system, user = build_prompt(seg.type, world, target_s=seg.target_s, show=show,
                                part=part, brief=seg.brief, at_ts=seg.nominal_start_ts, work=seg.work, tips=tips)
    schema = script_schema(seg.type, show.cast_for(seg.type))
    system += _keys_hint(schema)
    try:
        script = llm.complete_json(seg.type.value, schema, system, user)
        rebooked = None if cont else _rebooked(script, world)
        if rebooked:                      # the prompt asks for fresh guests; models forget, so ask again once
            log.info("%s slot %d: %s was just on; asking for another guest", seg.type.value, seg.slot_id, rebooked)
            script = llm.complete_json(seg.type.value, schema, system, user + (
                f"\n\nNOT {rebooked}: they were a guest very recently. Book a different person."))
        source = "llm"
        used = getattr(script, "tip_used", None)
        if tips and isinstance(used, int) and 1 <= used <= len(tips):
            tipline.consume(tips[used - 1])
    except llm.LLMError as e:
        log.warning("%s slot %d: using template (%s)", seg.type.value, seg.slot_id, e)
        script = _template(seg.type, world, random.Random(seg.content_hash or seg.id), show, seg.part, seg.work)
        source = "template"

    seg.lines = [Line(speaker=l.speaker, text=l.text.strip(), guest_name=_guest_of(l, script),
                      guest_role=getattr(script, "guest_role", None) if l.speaker == "guest" else None)
                 for l in script.lines if l.text.strip()]
    seg.headline = script.headline
    seg.cues = _cues_for(seg, script)
    _apply_to_world(seg, script, world, template=source == "template")
    seg.state = SegmentState.scripted
    log.info("scripted %s slot %d via %s: %r (%d lines)", seg.type.value, seg.slot_id, source,
             seg.headline, len(seg.lines))
    return seg


def _keys_hint(schema) -> str:
    """The output's keys in words. Some servers don't enforce the JSON schema, and a model
    left to guess invents its own shape ("segments" for lines), so spell it out."""
    def keys(model) -> str:
        parts = []
        for name, f in model.model_fields.items():
            item = getattr(f.annotation, "__args__", (None,))[0]
            parts.append(f"{name} (list of {{{keys(item)}}})" if isinstance(item, type) and hasattr(item, "model_fields") else name)
        return ", ".join(parts)
    return f"\nOutput: one JSON object with exactly these keys: {keys(schema)}.\n"


def _rebooked(script, world: World) -> str | None:
    """The guest's name if they were just on. (Vox-pop passers-by may recur, and a presenter
    may be a guest: Gordon runs the ghost tours. They appear as themselves.)"""
    name = getattr(script, "guest_name", None)
    if not name or not any(l.speaker == "guest" for l in script.lines):
        return None
    return name if name.lower() in {g.lower() for g in _recent_guests} else None


def _guest_of(line, script) -> str | None:
    """The guest's name for a guest line: on the line (vox pops) or on the script (interviews)."""
    if line.speaker != "guest":
        return None
    return getattr(line, "guest_name", None) or getattr(script, "guest_name", None)


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
    elif isinstance(script, InterviewScript):
        cues.append(VisualCue(at_s=0, kind="lower_third", payload={"title": script.headline, "subtitle": script.lower_third}))
    elif isinstance(script, FeatureScript):
        cues.append(VisualCue(at_s=0, kind="backdrop", payload={"backdrop": script.backdrop}))
        cues.append(VisualCue(at_s=0, kind="lower_third",
                              payload={"title": script.lower_third, "subtitle": f"Report from {script.location}"}))
    elif isinstance(script, VoxPopScript):
        cues.append(VisualCue(at_s=0, kind="backdrop", payload={"backdrop": script.backdrop}))
        cues.append(VisualCue(at_s=0, kind="lower_third", payload={"title": script.question, "subtitle": f"Vox pop: {script.location}"}))
    return cues


# Segments that may open a new story thread; the rest only follow existing ones up.
THREAD_OPENERS = (SegmentType.bulletin, SegmentType.field_report, SegmentType.interview, SegmentType.feature,
                  SegmentType.breaking)
_recent_guests: deque[str] = deque(maxlen=8)


def _apply_to_world(seg: Segment, script, world: World, *, template: bool = False) -> None:
    world.record_headline(script.headline)
    if isinstance(script, WeatherScript):
        world.record_weather(script.map_state, script.temp_c, script.headline)
    elif template and seg.type is not SegmentType.breaking:
        # A canned script is the same story every time: it may follow up the thread it
        # already has, but never opens one (NEWSROOM_LLM=off once opened five cannery
        # slipways in 72 seconds). Breaking news still does; its tip is real.
        same = next((t for t in world.open_threads() if t.title == script.headline[:80]), None)
        if same:
            seg.thread_id = world.update_thread(same.id, script.headline, None)
    else:
        # Breaking news always opens its own thread, even when the model names a related one
        # (an aground boat is not a follow-up of the lifeboat's old logbooks).
        tid = None if seg.type is SegmentType.breaking else getattr(script, "thread_id", None)
        status = getattr(script, "thread_status", None)
        known = {t.id for t in world.threads}
        if tid in known or seg.type in THREAD_OPENERS:
            seg.thread_id = world.update_thread(tid if tid in known else None, script.headline, status)
    # Guests join the recurring cast (a stable voice and look), and the writers avoid rebooking them.
    if getattr(script, "guest_name", None) and any(l.speaker == "guest" for l in seg.lines):
        world.ensure_person(script.guest_name, script.guest_role, gender=script.guest_gender)
        _recent_guests.append(script.guest_name)
    for l in getattr(script, "lines", []):
        if isinstance(l, VoxLine) and l.speaker == "guest" and l.guest_name:
            world.ensure_person(l.guest_name, "resident", gender=l.guest_gender)
    if seg.type is SegmentType.interview and getattr(script, "guest_name", None):
        _last_interview[seg.show] = {
            "slot": seg.slot_id, "name": script.guest_name, "role": script.guest_role or "a guest",
            "asked": "\n".join(f"  {l.speaker}: {l.text[:220]}" for l in seg.lines)[:3000]}
    world.record_aired(seg.type.value, script.headline, seg.thread_id, " ".join(l.text for l in seg.lines),
                       content_hash=seg.content_hash,
                       show=seg.show, brief=seg.brief)
