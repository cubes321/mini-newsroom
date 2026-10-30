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

from . import breaking, inquiry, llm, panel, phonein, quay, schedule, sport, tides, tipline
from .locations import locations_for_prompt
from .models import (
    SCRIPT_SCHEMAS,
    BulletinScript,
    CallLine,
    CallScript,
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
from .world import RETURN_EXPIRE_S, Person, World

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
with guest_role, guest_gender ("f" or "m"), guest_age ("young", "middle" or "old") and guest_accent
("british" for a local, "american" for someone from away); their lines use speaker "guest". Prefer a listed
public figure or a resident we have met when one fits; otherwise invent a plausible resident.
Do not book anyone listed under RECENT GUESTS. guest_memory: one line on what we learned about the
guest that a later show could call back to. ask_next_time: usually null; something to ask them about
next time, if the chat leaves one (a gig coming up, a result to come, an unfinished story).
"""

_SPORT_DESK = """
Fran ("sport") is the sports presenter, at the sports corner: a former county footballer, quick and
keen, who knows everyone at the clubs and in the pubs. Every score, scorer, date, table position,
fixture and checkout comes from SPORT FACTS, RUGBY FACTS and DARTS FACTS exactly as given; never
invent a result, and never say how a match finished before the facts give its result. The darts is
the lighter end: pub teams, regulars, a good checkout. thread_id is null.
"""

# Full Time's reporter at the grounds and in the pubs since 2026-10-30 (Miles had it, on top of the news
# and Coastwide).
_TAMSIN = (" Tamsin Jago is Full Time's reporter: twenty-five, Port Wexley born, played for the Tides' women's "
           "side, knows everyone at the Quarry Field and in the darts pubs, and is a bit cheeky with Fran.")

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
    SegmentType.sport: _COMMON_RULES + _SPORT_DESK + """
This is THE SPORT in the news: Fran speaks alone, about a minute, from the sports corner. A quick
"thanks, Dana" or straight in, then the Tides' latest from SPORT FACTS (a result, the next game,
the table), then one shorter item from the smaller clubs if there's room.
headline = the main sports item in under 12 words. lower_third = "Sport" plus a short tag.
""",
    SegmentType.breaking: _COMMON_RULES + """
This is BREAKING NEWS, interrupting {interrupting}. The anchor (speaker id "anchor") cuts in from
the news desk: what has happened, where, and that it is not yet confirmed ({source}).
Keep it small-town and calm; no casualties or horrors that the tip doesn't state.
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
alternating lines, as their PLACE IN THE SHOW says: a bit of banter about something small and local
(Clive has usually found an odd fact), and what is coming up: a filmed report, a guest in the
studio, the vox pop or the consumer slot. No guests speak. Do not open a new story; thread_id is null unless you
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
their own guest_name (first name and surname), guest_gender and guest_age; make them different ages and
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

# Quayside at 13:00: Howard Lanyon ("business") on the town's money; every item gets QUAY FACTS (quay.py).
_QUAYSIDE_RULES = """
This is part of QUAYSIDE, the lunchtime business half hour. Howard Lanyon ("business") ran the
Harrow Street bank branch for thirty years: he knows who owes whom, has a dry wit and reads the
figures like tea leaves. Every auction figure, boat, skipper and buyer comes from QUAY FACTS exactly
as given; never invent a price or a landing. Other money (a shop's rent, a job's wage, a bill) is
small-town scale and plausible. Plain words: say what a figure means for people in town.
"""

_QUAYSIDE: dict[SegmentType, str] = {
    SegmentType.links: _COMMON_RULES + _QUAYSIDE_RULES + """
These are Howard's words TO CAMERA ("business" alone), as THIS ITEM and the PLACE IN THE SHOW say: the
opening figures and what's coming up, the jobs board (three or four vacancies, each with the
employer, the hours and who to ask, each its own line), or the closing figures. Several short lines,
never one long one. No guests speak. thread_id is null
unless you mention an open thread in passing.
headline = the point in under 12 words. lower_third = "Quayside" plus a short tag.
""",
    SegmentType.field_report: _COMMON_RULES + _QUAYSIDE_RULES + """
This is a REPORT from the fish quay on Quayside. "business" (Howard) hands to Miles in one line;
"reporter" (Miles) reports from the quay as THIS ITEM says: the morning's auction, the boats out and
those kept in, what a skipper or a buyer said; "business" thanks him in one line. The backdrop is
harbour; location is the place in words.
""",
    SegmentType.interview: _COMMON_RULES + _GUEST_RULES + _QUAYSIDE_RULES + """
This is the GUEST in the armchair on Quayside. Howard ("business") talks to one guest as THIS ITEM
says: a business owner, a trader, a skipper, the merchant on the quay. Practical questions about
money and trade (costs, customers, staff, what would help); the guest gives real figures and a real
worry. Friendly, but Howard asks how the sums add up.
headline = the guest and their point in under 12 words. lower_third = a short caption.
""",
    SegmentType.consumer: _COMMON_RULES + _GUEST_RULES + _QUAYSIDE_RULES + """
This is the PRICES item on Quayside, fronted by Howard ("business"): what something costs in town now
and why, as THIS ITEM says. He may talk to one guest (a trader, a council officer, a shopper), named in
guest_name with role and gender, or set guest_name to null and speak alone. End with one clear tip.
headline = the item in under 12 words. lower_third = a short caption.
""",
    SegmentType.feature: _COMMON_RULES + _GUEST_RULES + _QUAYSIDE_RULES + """
This is a FILMED REPORT on Quayside about a local business, as THIS ITEM says. Structure:
1. "business" (Howard) introduces it in one line.
2. "reporter" (Miles) tells it from the place; one person from the business ("guest", named in
   guest_name with guest_role and guest_gender) speaks two or three times: what they do, who works
   there, how trade is.
3. "business" comes back with a one-line tag on what it means for the town.
Choose a backdrop id from the LOCATIONS list; location is the place in words, never an id.
""",
    SegmentType.vox_pop: _COMMON_RULES + _QUAYSIDE_RULES + """
This is the VOX POP on Quayside. Howard ("business") hands over in one line; Miles ("reporter") asks
shoppers or traders ONE question about money (prices, the fish, a shop closing, wages); then three or
four answer in a line or two each. Each is speaker "guest" with their own guest_name (first name and
surname), guest_gender and guest_age; different ages and views, one of them funny. question = the
question as a caption. Choose a backdrop id from the LOCATIONS list; location is the place in words.
""",
}

# Have Your Say (phonein.py): Jonah (host_b) and the phones; every item gets TODAY'S QUESTION.
_PHONEIN_RULES = """
This is part of HAVE YOUR SAY, the morning news phone-in presented by Jonah Pike ("host_b"), a former
local-radio DJ: laid-back, quick, kind to nervous callers, a pun now and then but never at a caller's
expense, and fair: he gives every view a hearing and moves a long-winded caller on. One question all
hour, given as TODAY'S QUESTION, with a studio guest at the heart of the story. Facts come from the
briefing; callers have opinions, memories and their own small facts (their street, their shop, their
bus), never new news the briefing doesn't have. Small-town scale.
"""

_PHONEIN: dict[SegmentType, str] = {
    SegmentType.links: _COMMON_RULES + _PHONEIN_RULES + """
These are Jonah's words TO CAMERA ("host_b" alone), as THIS ITEM and the PLACE IN THE SHOW say: at the
open, a good morning, today's question, the studio guest by name and role, and the number to ring
(said as written); the travel, from the TIDES and the briefing (no invented road accidents), then back
to the phones; at the close, what callers said and thanks. Several short lines. No guests speak.
headline = the point in under 12 words. lower_third = "Have Your Say" plus a short tag.
""",
    SegmentType.interview: _COMMON_RULES + _PHONEIN_RULES + """
This is Jonah ("host_b") with THE STUDIO GUEST in the armchair, as THIS ITEM says. The guest is
speaker "guest", with guest_name their exact name and guest_role their role. Jonah puts today's
question, or the callers' points from SAID SO FAR; the guest answers from where they stand, with real
reasons, and may concede a point a caller made. Short questions; the guest talks more than Jonah.
headline = the guest's answer in under 12 words. lower_third = a short caption.
""",
    SegmentType.call: _COMMON_RULES + _PHONEIN_RULES + """
This is ONE CALL on Have Your Say. Jonah ("host_b") brings the caller in ("Let's go to the phones",
"Line two, you're on Have Your Say"), with their first name and where they're ringing from. The caller
is speaker "guest" with guest_name null on their lines; name them once in caller_name (first name and
surname), with caller_from, caller_gender, caller_age and caller_accent. They say what they think about
today's question in their own words, with something from their own life; Jonah replies, asks one
thing back, and keeps it moving. The studio guest may answer them once or twice: speaker "guest" with
guest_name the studio guest's exact name. Be THIS CALLER, not someone who has already rung. A real
voice: hesitant, cross, funny or nervous, not a speech. End with Jonah thanking them, or going to the
next line. caller_memory: one line on what they said. thread_id: today's question's thread.
headline = the caller and their point in under 12 words. lower_third = "Have Your Say" plus the question, short.
""",
    SegmentType.bulletin: _COMMON_RULES + """
These are THE HEADLINES in the middle of Have Your Say, Jonah Pike's news phone-in: Dana ("anchor") at
the news desk reads two or three short local stories, one or two sentences each, then hands back to
Jonah and the phones in one line. Make at most one of them a follow-up of an open thread (set
thread_id and thread_status); otherwise thread_id is null.
headline = the top story in under 12 words. lower_third = a short caption for it.
""",
}

# The Panel (panel.py): Dana ("anchor") chairs three panellists; every item gets TONIGHT'S PANEL.
_PANEL_RULES = """
This is part of THE PANEL, a half-hour debate chaired by Dana Ferris ("anchor"): dry, unflappable,
fair, quick to stop a speech and to press a dodge. The three panellists in TONIGHT'S PANEL keep to
their stances and their positions in the briefing; they disagree for real reasons, concede a point
now and then, and are never cartoons. Facts come from the briefing; opinions are theirs. Civil: no
shouting, nobody insulted. Small-town scale.
"""

_PANEL: dict[SegmentType, str] = {
    SegmentType.links: _COMMON_RULES + _PANEL_RULES + """
These are Dana's words TO CAMERA ("anchor" alone), as THIS ITEM and the PLACE IN THE SHOW say: at the
open, a brief welcome, the panellists by name and role, and the first question; at the close, thanks
and where they agreed and where they didn't. No panellist speaks. thread_id is null.
headline = the point in under 12 words. lower_third = "The Panel" plus a short tag.
""",
    SegmentType.interview: _COMMON_RULES + _PANEL_RULES + """
This is ONE DEBATE on The Panel, on the ONE question THIS ITEM names; the other questions have their
own debates elsewhere in the show, so do not put them, and do not end by moving on to the next. Dana
("anchor") puts it; each of the THREE panellists answers in turn (speaker "guest", guest_name their
exact name); then they take each other on, short exchanges, Dana stepping in to bring the quiet one in
or to press a dodge. Every panellist speaks at least twice. Set thread_id to the question's thread if
it has one.
headline = the question and the sharpest point, under 12 words. lower_third = the question, short.
""",
    SegmentType.vox_pop: _COMMON_RULES + _PANEL_RULES + """
This is the QUESTION FROM THE PUBLIC on The Panel. Dana ("anchor") hands over in one line; Miles
("reporter") asks people in town THIS ITEM's question; three or four answer in a line or two each, the
last putting it to the panel in their own words. Each is speaker "guest" with their own guest_name
(first name and surname), guest_gender and guest_age; different views. question = the question as a
caption. Choose a backdrop id from the LOCATIONS list; location is the place in words.
""",
}

# The Inquiry (inquiry.py): Pat (mag_a) on one story in depth; every item gets TONIGHT'S INQUIRY.
_INQUIRY_RULES = """
This is part of THE INQUIRY, a half-hour investigation into ONE story, given as TONIGHT'S INQUIRY
with its record. Keep to the record's dates and facts; what the record doesn't show is a question,
not a finding. Fair, precise, plain words; small-town scale; nobody accused of a crime the record
doesn't show. Light touches are fine, jokes are not.
"""

_INQUIRY: dict[SegmentType, str] = {
    SegmentType.links: _COMMON_RULES + _INQUIRY_RULES + """
These are Pat's words TO CAMERA ("mag_a" alone), as THIS ITEM and the PLACE IN THE SHOW say: at the
open, the story in a few lines and the questions she will put; at the close, what was found, what is
still not answered, and who has to answer it next. No guests speak.
headline = the point in under 12 words. lower_third = "The Inquiry" plus a short tag.
""",
    SegmentType.feature: _COMMON_RULES + _GUEST_RULES + _INQUIRY_RULES + """
This is a FILMED REPORT in The Inquiry, on what THIS ITEM names. Structure:
1. "mag_a" (Pat) introduces it in one line.
2. "reporter" (Miles) tells it from the location; one person ("guest", named in guest_name with
   guest_role and guest_gender) may speak two or three times: someone it affected, or who was there.
3. "mag_a" comes back with a one-line tag that sharpens the question.
Choose a backdrop id from the LOCATIONS list; location is the place in words, never an id.
""",
    SegmentType.interview: _COMMON_RULES + _GUEST_RULES + _INQUIRY_RULES + """
This is the STUDIO INTERVIEW in The Inquiry. Pat ("mag_a") and one guest in the armchair, as THIS
ITEM says: THE GUEST named in tonight's brief, or for "the other side" someone else who sees it
differently. Pat asks short, specific questions from THE QUESTIONS, follows up when an answer slides
away ("That's not what I asked"), and quotes the record back. The guest defends their position as
they would, with real reasons; no one collapses or confesses. Polite, firm, no shouting.
headline = the guest and the key answer (or non-answer) in under 12 words. lower_third = a short caption.
""",
    SegmentType.vox_pop: _COMMON_RULES + _INQUIRY_RULES + """
This is the VOX POP in The Inquiry. Pat ("mag_a") hands over in one line; Miles ("reporter") asks the
people most affected by tonight's story ONE question about it; then three or four answer in a line or
two each. Each is speaker "guest" with their own guest_name (first name and surname), guest_gender
and guest_age; different views, nobody a cartoon. question = the question as a caption. Choose a
backdrop id from the LOCATIONS list near the story; location is the place in words.
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
When THIS ITEM is a shorter second guest, keep it brisk: welcome them on, one story, a laugh, goodbye.
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
surname), guest_gender and guest_age; different ages and moods, one of them funny. Vincent may add one line
back in the studio. question = the question as a caption. Choose a backdrop id from the LOCATIONS
list; location is the place in words.
""",
}


# Full Time, the sports show at 18:45: Fran at the sports corner, Miles out at the grounds.
_SPORT: dict[SegmentType, str] = {
    SegmentType.sport: _COMMON_RULES + _SPORT_DESK + """
This is a piece on the SPORTS DESK in Full Time. Fran speaks alone, to camera, on what THIS ITEM
says, in its PLACE IN THE SHOW.
headline = the piece in under 12 words. lower_third = "Full Time" plus a short tag.
""",
    SegmentType.field_report: _COMMON_RULES + _SPORT_DESK + """
This is a LIVE REPORT on Full Time. "sport" (Fran) hands to Tamsin in one line; "sport_reporter"
(Tamsin) reports from the place THIS ITEM names: the club this week, training, the mood, an injury,
the darts regulars, what people there said; "sport" thanks her in one line.""" + _TAMSIN + """
Choose a backdrop id from the LOCATIONS list (stadium for the Tides, quarry_field for the Wreckers,
pub for the darts); location is the place in words, never an id.
""",
    SegmentType.interview: _COMMON_RULES + _GUEST_RULES + _SPORT_DESK + """
This is the GUEST on the sports desk in Full Time. Fran ("sport") talks to one guest as THIS ITEM
says: a player, the manager or coach, a darts captain, someone from a smaller club. Short, lively
questions; the guest tells a story or two (a goal, a try, a dressing-room moment, a night at the
oche, how they started) and is honest about the last result as the FACTS give it. The squads, the
manager, the coach and the darts regulars are in the FACTS: use those names.
headline = the guest and the best thing they said, under 12 words. lower_third = a short caption.
""",
    SegmentType.vox_pop: _COMMON_RULES + _SPORT_DESK + """
This is the VOX POP on Full Time. Fran ("sport") hands over in one line; Tamsin ("sport_reporter")
asks supporters ONE question about the club; then three or four answer in a line or two each.""" + _TAMSIN + """ Each is
speaker "guest" with their own guest_name (first name and surname), guest_gender and guest_age;
different ages and moods, one of them funny. question = the question as a caption. Choose a
backdrop id from the LOCATIONS list; location is the place in words.
""",
}

_LIGHT = """Weight: a LIGHTER programme than the main news. Prefer warm, quirky, everyday local
stories, people and what's on; keep grim or heavy stories out unless the briefing names a
BIG RUNNING STORY, which the headlines lead with briefly (what is new), then move on.
"""


BIG_STORY_MIN_MENTIONS = 4      # a peak the desk planned but nobody has covered yet doesn't count
BREAKING_LEAD_S = 2 * 3600      # bulletins lead with a story this long after it broke

_FROM_THE_SCENE = """

FROM THE SCENE: [{id}] {title} broke {mins} minutes ago as breaking news, not yet confirmed. Known so far:
{status}. This report is Miles ("reporter") live from where it happened: what he can now confirm, or
what turned out to be wrong; what people there saw; what happens next. Choose the backdrop for that
place. Set thread_id "{id}" and a thread_status saying what is now confirmed. No casualties or horrors
the story hasn't stated."""


def scene_due(world: World, now: float) -> str | None:
    """The story that broke most recently, if Miles hasn't reported from the scene yet and it
    broke within the window. One field report covers it (the archive shows one, with its thread
    id: a breaking story opens its own thread, so any field report on that thread is the one)."""
    from .config import CONFIG

    covered = {e.get("thread_id") for e in world.archive if e.get("type") == SegmentType.field_report.value}
    due = [t for t in world.open_threads() if t.breaking_ts and t.id not in covered
           and 0 <= now - t.breaking_ts < CONFIG.breaking.scene_window_s]
    return max(due, key=lambda t: t.breaking_ts).id if due else None


def scene_done(world: World, now: float) -> list[str]:
    """Stories that broke recently and that Miles has already reported from the scene: the
    bulletins carry them now, and other field reports should leave them be (on 2026-10-27 the
    next field report went back to the chip-shop fire, and the bulletin between led with it)."""
    covered = {e.get("thread_id") for e in world.archive if e.get("type") == SegmentType.field_report.value}
    return [t.id for t in world.open_threads()
            if t.breaking_ts and t.id in covered and 0 <= now - t.breaking_ts < BREAKING_LEAD_S]

_CONT = """PART TWO: you are CONTINUING the conversation with {name} ({role}) after the break. Use the
same guest_name, guest_role and guest_gender. One line welcoming viewers back, no long reintroduction,
then pick up where it left off and go somewhere new: another story, a different side of them.
Part one, for continuity: keep every fact the same, and do NOT ask these questions again or retell
the answers:
{asked}"""

_COUCH = """ON THE COUCH: {name} ({role}), the guest Vincent has just been talking to, stays on and moves
down the couch for the next guest, as on the big talk shows. Book and welcome a NEW guest: guest_name,
guest_role and guest_gender are the new guest's. Every "guest" line sets guest_name to who is speaking:
the new guest, or "{name}". The new guest gets most of the time; {name} chips in two or three times,
and the two guests talk to each other as well as to Vincent: they react, tease gently, find something
in common or don't. One conversation among three, not two interviews. Earlier, {name} talked about
this (don't go over it again; a callback is fine):
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

# Where a piece sits in its show, by show, type and running-order part (a close gets _CLOSE). Left to
# guess, the middle pieces opened and closed the show: on 2026-10-28 all twelve of Coastwide's middle
# links welcomed viewers, and Full Time's rugby on 2026-10-29 said goodbye with ten minutes to go.
_MIDDLE = ("PLACE IN THE SHOW: the MIDDLE of {title}, already under way: no welcome or good evening, and "
           "no goodbye or goodnight{extra}. ")
_ROLLING = ("PLACE IN THE SHOW: one item in the rolling news, which runs on all day and evening: no "
            "sign-off from anyone, presenter or guest (no goodnight, goodbye or see you tomorrow). The "
            "next item follows straight on.")
_PLACE: dict[tuple[str, SegmentType], dict[str, str]] = {
    ("sport", SegmentType.sport): {
        "open": "PLACE IN THE SHOW: this OPENS Full Time: a quick good evening and welcome to Full Time, the "
                "headlines, and what's coming up.",
        "": _MIDDLE.format(title="Full Time", extra=", and no hand-over to Coastwide") + "Go straight into it.",
    },
    ("magazine", SegmentType.links): {
        "open": "PLACE IN THE SHOW: this OPENS Coastwide: a good evening and welcome, then the banter and "
                "what's coming up.",
        "": _MIDDLE.format(title="Coastwide", extra=", and never \"Coastwide is next\": it is on now")
            + "Come out of the last item, a little banter, and on to what's next.",
    },
    ("panel", SegmentType.links): {
        "open": "PLACE IN THE SHOW: this OPENS The Panel: a brief good evening, then the panel and the first question.",
        "": _MIDDLE.format(title="The Panel", extra=""),
    },
    ("panel", SegmentType.interview): {"": _MIDDLE.format(title="The Panel", extra="")},
    ("phonein", SegmentType.links): {
        "open": "PLACE IN THE SHOW: this OPENS Have Your Say: a brief good morning, then the question and the guest.",
        "": _MIDDLE.format(title="Have Your Say", extra=""),
    },
    ("phonein", SegmentType.interview): {"": _MIDDLE.format(title="Have Your Say", extra="")},
    ("phonein", SegmentType.call): {"": _MIDDLE.format(title="Have Your Say", extra="")},
    ("quayside", SegmentType.links): {
        "open": "PLACE IN THE SHOW: this OPENS Quayside: a brief good afternoon, then the figures.",
        "": _MIDDLE.format(title="Quayside", extra=""),
    },
    ("inquiry", SegmentType.links): {
        "open": "PLACE IN THE SHOW: this OPENS The Inquiry: a brief good evening, then straight into the story.",
        "": _MIDDLE.format(title="The Inquiry", extra=""),
    },
    ("inquiry", SegmentType.interview): {"": _MIDDLE.format(title="The Inquiry", extra="")},
    ("inquiry", SegmentType.feature): {"": _MIDDLE.format(title="The Inquiry", extra="")},
    ("late", SegmentType.links): {
        "": _MIDDLE.format(title="The Last Ferry", extra=": Vincent says goodnight at the end of the show"),
    },
    ("news", SegmentType.bulletin): {"": _ROLLING},
    ("news", SegmentType.interview): {"": _ROLLING},
}

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


# Coastwide runs the same dozen kinds of item round its hour, and like the breakfast sofa it wrote the
# same item each lap: in the hour of 2026-10-29 the chip-shop vox pop five times, Dev's sourdough
# starter three times, Biscuit the harbour cat, the darts, the estuary birds, the rogue roofer and
# Oliver Fenwick-Hale twice each, and "clocks and chips" in nearly every link.
SHOW_MEMORY = 30                # tonight's items on the show listed for the next writer
SHOW_SAME_TYPE = 4              # earlier items of this item's kind, with how they began
REMEMBERS_ITS_SHOW = {"magazine": "COASTWIDE"}
_SHOW_TYPES = (SegmentType.links, SegmentType.feature, SegmentType.interview, SegmentType.vox_pop,
               SegmentType.consumer)

_SHOW_SO_FAR = """ON {title} ALREADY TONIGHT (do NOT do any of these again, even when this kind of item
comes round: a different subject, question, person, place, pet or food; a callback or passing mention is fine):
{heads}{same}"""


def _show_so_far(world: World, show: schedule.Show, seg_type: SegmentType, part: str) -> str:
    """What a magazine show has already done tonight, for the next item (or the goodbye's nod)."""
    title = REMEMBERS_ITS_SHOW.get(show.id)
    if not title or seg_type not in _SHOW_TYPES:
        return ""
    kinds = {t.value for t in _SHOW_TYPES}
    with world.lock:
        aired = [e for e in world.archive
                 if e["date"] == world.last_date and e.get("show") == show.id and e["type"] in kinds]
    if not aired:
        return ""
    heads = "\n".join(f"  - {e['type'].replace('_', ' ')}: {e['headline']}" for e in aired[-SHOW_MEMORY:])
    if part == "close":
        return f"ON {title} TONIGHT (for the nod to what was on):\n{heads}"
    same = [e for e in aired if e["type"] == seg_type.value][-SHOW_SAME_TYPE:]
    kind = seg_type.value.replace("_", " ")
    same_s = (f"\nTHE LAST {kind.upper()}S, how they began. This {kind} is about none of these subjects, not even "
              "from a new angle:\n" + "\n".join(f"  - {e['headline']}: {e['text'][:160]}" for e in same)) if same else ""
    return _SHOW_SO_FAR.format(title=title, heads=heads, same=same_s)


FIELD_MEMORY = 3                # the last field reports on this show the next one is shown


def _field_so_far(world: World, show: schedule.Show) -> str:
    """The show's last few field reports, so the next goes somewhere else: with nothing to say
    otherwise, two in a row took the same story (the harbour-wall pupils, then the one fire
    engine, on 2026-10-27)."""
    last = world.aired_today(SegmentType.field_report.value, show.id)[-FIELD_MEMORY:]
    if not last:
        return ""
    heads = "\n".join(f"  - {e['headline']}" + (f" [{e['thread_id']}]" if e.get("thread_id") else "") for e in last)
    return ("MILES'S LAST REPORTS (this one goes to a different story and place: do not follow up the "
            f"threads named here; a passing mention is fine):\n{heads}")


QUIET_THREADS = 4               # open threads beyond the briefing's offered to a news field report


def _quiet_threads(world: World, exclude: set[str]) -> str:
    """Open threads the briefing doesn't list, for a news field report to pick up before it
    invents a story: told to go somewhere other than Miles's last three, with only the
    briefing's five to choose from, it started new ones (four "second fire engine" threads and
    five "estuary tide in the wind" on 2026-10-27). Those with a planned NEXT first, then the
    longest quiet, which they also keep from fading."""
    shown = {t.id for t in world.briefing_threads()} | exclude
    quiet = sorted((t for t in world.open_threads() if t.id not in shown),
                   key=lambda t: (not t.next_development, t.moved_ts))[:QUIET_THREADS]
    if not quiet:
        return ""
    rows = "\n".join(f"  - [{t.id}] {t.title}: {t.status}" + (f"; NEXT: {t.next_development}" if t.next_development else "")
                     for t in quiet)
    return ("QUIET STORIES (open, not in the briefing's list): pick one of these up before starting a new "
            "story; set thread_id to it and deliver its NEXT step. Start a new story only if none fits.\n" + rows)


def _return_offer(p) -> str:
    """A guest with a loose end, offered back with what they said last time."""
    end = p.loose_ends[-1]
    said = "; ".join(m["said"] for m in p.memories[-2:]) or "(not noted)"
    return (f"A RETURN VISIT, if it suits THIS ITEM: {p.name} ({p.role}) was on {end['show']} on "
            f"{datetime.fromisoformat(end['date']):%A %d %B}. Last time: {said}. Something to ask them: {end['ask']}. "
            "Book them again and pick that up (welcome them back, no long reintroduction; keep what they said "
            "last time the same), or book someone new if it doesn't fit.")


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
    table = {"breakfast": _BREAKFAST, "magazine": _MAGAZINE, "late": _LATE, "sport": _SPORT,
             "inquiry": _INQUIRY, "quayside": _QUAYSIDE, "panel": _PANEL, "phonein": _PHONEIN}.get(show.id, {})
    system = table.get(seg_type, _SYSTEM.get(seg_type, ""))
    work = work or {}
    system = system.format(station=show.station, tone=show.tone, weight=_LIGHT if show.light else "",
                           interrupting=work.get("interrupting", "the programme"),
                           source=work.get("source", breaking.FROM_VIEWER))
    user = (
        f"TOWN BRIEFING\n{world.summary_for_prompt(show.cast_for(seg_type))}\n\n"
        f"Write the {seg_type.value.replace('_', ' ')} segment. "
        f"Word budget: about {words} words total across all lines (plus or minus fifteen percent). "
        f"Today is {date.fromtimestamp(schedule.now()):%A %d %B}; it is the {_part(show)}."
    )
    if show.light and show.id != "sport":         # the sports show has its own facts, not the news
        big = big_story(world)
        if big and show.opens and part != "open" and seg_type is not SegmentType.bulletin:
            user += (f"\n\nBIG RUNNING STORY: [{big.id}] {big.title}. It was covered at the top of the programme: "
                     "a passing mention at most, and nothing about it unless it fits this item.")
        else:
            user += (f"\n\nBIG RUNNING STORY: [{big.id}] {big.title}. NEXT: {big.next_development or 'no new step yet'}"
                     if big else "\n\nNo big running story today: keep it light.")
    cont = _last_interview.get(show.id) if part == "cont" and seg_type is SegmentType.interview else None
    couch = _last_interview.get(show.id) if part == "couch" and seg_type is SegmentType.interview else None
    # The tides are breakfast small talk, not for its guest: Rosie read Marjorie the ferry's
    # low-water gap in the middle of her book (2026-10-27).
    if seg_type is SegmentType.weather or show.id == "late" or (
            show.id == "breakfast" and seg_type is not SegmentType.interview) or (
            show.id == phonein.SHOW and seg_type is SegmentType.links):      # the travel: the ferries and the tide
        today = datetime.fromtimestamp(at_ts or schedule.now()).date()
        user += "\n\n" + tides.for_prompt(today, world.last_weather.get("map_state"))
    if seg_type is SegmentType.sport or show.id == "sport":
        user += "\n\n" + sport.for_prompt(datetime.fromtimestamp(at_ts or schedule.now()))
    scene = world.thread(work.get("scene")) if seg_type is SegmentType.field_report else None
    if scene:                             # the rota's angle ("the first ferry") would fight it
        user += _FROM_THE_SCENE.format(id=scene.id, title=scene.title, status=scene.status,
                                       mins=int(max(0, (at_ts or schedule.now()) - scene.breaking_ts) // 60))
    elif brief:
        user += f"\n\nTHIS ITEM: {brief}."
    done = scene_done(world, at_ts or schedule.now()) if seg_type is SegmentType.field_report and not scene else []
    if done:
        user += (f"\n\nMiles has already reported from the scene of {', '.join(f'[{d}]' for d in done)}; the bulletins "
                 "carry it now. This report is about another story: do not set thread_id to it.")
    last = _field_so_far(world, show) if seg_type is SegmentType.field_report and not scene else ""
    if last:
        user += "\n\n" + last
    if seg_type is SegmentType.field_report and not scene and not show.light:
        recent = {e.get("thread_id") for e in world.aired_today(SegmentType.field_report.value, show.id)[-FIELD_MEMORY:]}
        quiet = _quiet_threads(world, recent | set(done))
        if quiet:
            user += "\n\n" + quiet
    if show.id == inquiry.SHOW:
        user += "\n\n" + inquiry.for_prompt(world)
    if show.id == panel.SHOW:
        user += "\n\n" + panel.for_prompt(world)
    if show.id == phonein.SHOW and seg_type is not SegmentType.bulletin:
        user += "\n\n" + phonein.for_prompt(world, seg_type)
    if show.id == "quayside" and (facts := quay.for_prompt(datetime.fromtimestamp(at_ts or schedule.now()))):
        user += "\n\n" + facts
    so_far = _sofa_so_far(world, show, brief, part) if seg_type is SegmentType.sofa else _show_so_far(
        world, show, seg_type, part)
    if so_far:
        user += "\n\n" + so_far
    guests = _guests_so_far(world, show) if seg_type is SegmentType.interview and show.id == "breakfast" else ""
    if guests:
        user += ("\n\nIN THE ARMCHAIR ALREADY THIS MORNING (book a different sort of person, and give anything "
                 f"they plug a title unlike these):\n{guests}")
    if cont:
        user += "\n\n" + _CONT.format(**cont)
        if work.get("stays_on"):
            user += ("\n\nThey stay on the couch for the next guest: no goodbye or thanks at the end. Vincent "
                     "closes by saying another guest is joining them.")
    elif seg_type in (SegmentType.interview, SegmentType.feature, SegmentType.consumer, SegmentType.vox_pop) and (
            show.id not in (inquiry.SHOW, panel.SHOW, phonein.SHOW)):   # their guests are booked, however recent
        user += f"\n\nRECENT GUESTS (book someone else): {', '.join(_recent_guests) or 'none yet'}"
    back = world.person_by_name(work.get("return_guest")) if seg_type is SegmentType.interview else None
    if back and back.loose_ends:
        user += "\n\n" + _return_offer(back)
    if couch:
        user += "\n\n" + _COUCH.format(name=couch["name"], role=couch["role"], asked=couch["asked"][-1500:])
    if seg_type is SegmentType.breaking:
        user += f"\n\nWHAT HAS COME IN (unconfirmed): {work.get('tip', '')}"
    if seg_type is SegmentType.bulletin:
        now = at_ts or schedule.now()
        broke = [t for t in world.open_threads() if t.breaking_ts and 0 <= now - t.breaking_ts < BREAKING_LEAD_S]
        if broke:
            t = max(broke, key=lambda t: t.breaking_ts)
            user += (f"\n\nSTORY THAT BROKE {int((now - t.breaking_ts) // 60)} MINUTES AGO: [{t.id}] {t.title}. "
                     f"Known so far: {t.status}. Lead with it, as the follow-up of this thread: thread_id \"{t.id}\" and "
                     "a thread_status saying what is new, or plainly what is still not confirmed. "
                     "Do not invent casualties.")
    if tips and seg_type is SegmentType.call:
        user += ("\n\nVIEWER TIPS from the tip-line (unconfirmed). If one fits today's question, this caller may be "
                 "the viewer who sent it in, ringing about it in their own words: set tip_used to its number; "
                 "otherwise tip_used is null:\n" + "\n".join(f"  {i + 1}. {t}" for i, t in enumerate(tips)))
    elif tips:
        user += ("\n\nVIEWER TIPS from the tip-line (unconfirmed; use at most one, as a short item, and set "
                 "tip_used to its number; otherwise tip_used is null):\n"
                 + "\n".join(f"  {i + 1}. {t}" for i, t in enumerate(tips)))
    place = _PLACE.get((show.id, seg_type), {}).get(part)
    if place:
        user += "\n\n" + place.rstrip()
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
    if seg_type is SegmentType.sport:
        latest = sport.summary(datetime.fromtimestamp(schedule.now()))
        return BulletinScript(
            lines=[LiveLine(speaker="sport", text="Time for the sport." if part_ != "close" else "That's Full Time."),
                   LiveLine(speaker="sport", text=latest.replace("Tidewater Town FC (the Tides): ", "For the Tides: ")),
                   LiveLine(speaker="sport", text="More from the Tides and the smaller clubs next time. Goodnight."
                            if part_ == "close" else "That's the sport for now.")],
            headline="The Tides: the latest",
            lower_third="Sport, channel seven",
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
    if seg_type is SegmentType.call:
        booked = phonein.today(world) or {}
        guest = world.person_by_name(booked.get("guest"))
        lines = [CallLine(speaker=lead, text="Let's go to the phones. Line one, you're on Have Your Say. Good morning."),
                 CallLine(speaker="guest", text="Morning, Jonah. Long-time watcher, first time I've rung. I just think "
                                                "people want to be asked before things change, that's all."),
                 CallLine(speaker=lead, text="That's a fair point, and you've rung the right place to make it.")]
        if guest:
            lines += [CallLine(speaker=lead, text=f"{guest.name}, do people get asked?"),
                      CallLine(speaker="guest", guest_name=guest.name,
                               text="They should, and I'd rather hear it on this programme than not at all.")]
        lines.append(CallLine(speaker=lead, text="Thanks for ringing. Keep the calls coming."))
        return CallScript(lines=lines, headline="A caller wants to be asked first",
                          lower_third="Have Your Say", caller_name="Pam Rowe", caller_from="Harrow Street",
                          caller_gender="f", caller_age="old", caller_accent="british",
                          thread_id=booked.get("thread_id"))
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
    # The late couch likewise keeps on only the guest whose part was the slot before.
    first = seg.work.get("first_part", seg.slot_id - 1)
    follows = seg.part in ("cont", "couch") and _last_interview.get(show.id, {}).get("slot") == first
    cont = follows and seg.part == "cont"
    couch = _last_interview[show.id] if follows and seg.part == "couch" else None
    part = "" if seg.part in ("cont", "couch") and not follows else seg.part
    tips = tipline.offer() if seg.type in (SegmentType.bulletin, SegmentType.call) else []   # a viewer may ring in
    # A chat show may book back a guest who left something to ask, once a day per show.
    seg.work.pop("return_guest", None)
    seg.work.pop("loose_end_of", None)
    if (seg.type is SegmentType.interview and show.light and not cont
            and world.guest_returns.get(show.id) != world.last_date):
        back = world.return_guests(exclude=set(_recent_guests) | ({couch["name"]} if couch else set()))
        if back:
            seg.work["return_guest"] = back[0].name
    if seg.type is SegmentType.field_report:
        seg.work.pop("scene", None)
        scene = scene_due(world, seg.nominal_start_ts or schedule.now())
        if scene:
            seg.work["scene"] = scene         # build_prompt sends Miles there; _apply_to_world files it on it
            log.info("field_report slot %d: Miles reports from the scene of %s", seg.slot_id, scene)
    system, user = build_prompt(seg.type, world, target_s=seg.target_s, show=show,
                                part=part, brief=seg.brief, at_ts=seg.nominal_start_ts, work=seg.work, tips=tips)
    debate = seg.type is SegmentType.interview and show.id == panel.SHOW     # three panellists, booked tonight
    # The phone-in's studio guest is booked for the morning (phonein.py) and stays in the armchair all hour.
    studio = (phonein.today(world) or {}).get("guest") or None if show.id == phonein.SHOW else None
    booked = debate or (seg.type is SegmentType.interview and show.id == phonein.SHOW)
    schema = script_schema(seg.type, show.cast_for(seg.type), couch=bool(couch), panel=debate)
    system += _keys_hint(schema)
    try:
        script = llm.complete_json(seg.type.value, schema, system, user)
        rebooked = None if cont or booked else _rebooked(script, world)
        if rebooked:                      # the prompt asks for fresh guests; models forget, so ask again once
            log.info("%s slot %d: %s was just on; asking for another guest", seg.type.value, seg.slot_id, rebooked)
            again = (f"{rebooked} is already on the couch: guest_name is the NEW guest, someone else."
                     if couch and rebooked.lower() == couch["name"].lower()
                     else f"NOT {rebooked}: they were a guest very recently. Book a different person.")
            script = llm.complete_json(seg.type.value, schema, system, user + "\n\n" + again)
        # A guest booked of the writer's own accord who has been on before: ask again with what
        # they said, so they don't contradict themselves (the offered return visit had it already).
        known = None if cont or booked else _remembered(script, world, {seg.work.get("return_guest"),
                                                                        couch and couch["name"]})
        if known:
            log.info("%s slot %d: %s has been on before; asking again with what they said", seg.type.value,
                     seg.slot_id, known.name)
            note, end = _remembered_note(known)
            script = llm.complete_json(seg.type.value, schema, system, user + "\n\n" + note)
            if end:
                seg.work["loose_end_of"] = known.name
        source = "llm"
        used = getattr(script, "tip_used", None)
        if tips and isinstance(used, int) and 1 <= used <= len(tips):
            tipline.consume(tips[used - 1])
    except llm.LLMError as e:
        log.warning("%s slot %d: using template (%s)", seg.type.value, seg.slot_id, e)
        script = _template(seg.type, world, random.Random(seg.content_hash or seg.id), show, seg.part, seg.work)
        source = "template"
        # With NEWSROOM_LLM=off the template is the content; otherwise it stands in for a model
        # that was unreachable, and the cache and the overnight repeats must not keep it.
        seg.fallback = llm.provider_for(seg.type.value) != "off"

    stayed = couch["name"] if couch and source == "llm" else None

    call = isinstance(script, CallScript)

    def role(name: str | None) -> str | None:
        if stayed and name == stayed:
            return couch["role"]
        if call and name == script.caller_name:
            return f"On the line from {script.caller_from}"
        if (debate or studio) and (p := world.person_by_name(name)):
            return p.role                     # each panellist, or the phone-in's guest, under their own caption
        return getattr(script, "guest_role", None)
    seg.lines = [Line(speaker=l.speaker, text=l.text.strip(),
                      guest_name=(name := _guest_of(l, script, stayed, studio)),
                      guest_role=role(name) if l.speaker == "guest" else None)
                 for l in script.lines if l.text.strip()]
    if stayed and any(l.guest_name == stayed for l in seg.lines):
        seg.work["couch"] = stayed            # the player seats them further down the couch
    seg.work.pop("studio_guest", None)
    if studio:
        seg.work["studio_guest"] = studio     # in the armchair all hour (player.py), even when a caller speaks
    if call:
        seg.work["caller"], seg.work["caller_from"] = script.caller_name, script.caller_from   # on the phone
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


def _remembered(script, world: World, skip: set) -> Person | None:
    """The booked guest, if they have been on before and said something we kept, unless they are
    in `skip` (the offered return visit, the guest staying on the couch)."""
    name = getattr(script, "guest_name", None)
    if not name or not any(l.speaker == "guest" for l in script.lines):
        return None
    if name.strip().lower() in {s.strip().lower() for s in skip if s}:
        return None
    p = world.person_by_name(name)
    return p if p is not None and p.memories else None


def _remembered_note(p: Person) -> tuple[str, dict | None]:
    """What a returning guest said before, and their loose end if one is still waiting."""
    said = "; ".join(f"{m['said']} ({m['show']}, {datetime.fromisoformat(m['date']):%A %d %B})"
                     for m in p.memories[-2:])
    end = next((e for e in reversed(p.loose_ends) if 0 <= schedule.now() - e["ts"] < RETURN_EXPIRE_S), None)
    note = (f"{p.name} has been on before; what they said then is on record: {said}. Keep to it (no "
            "contradicting it), welcome them back, no long reintroduction."
            + (f" Something left to ask them last time: {end['ask']}. Pick it up if it suits this item." if end else ""))
    return note, end


def _guest_of(line, script, stayed: str | None = None, studio: str | None = None) -> str | None:
    """The guest's name for a guest line: on the line (vox pops) or on the script (interviews).
    On the late couch a line is the guest who `stayed` on, or else the new guest. On a call it is
    the `studio` guest if it names them, and otherwise the caller."""
    if line.speaker != "guest":
        return None
    name = getattr(line, "guest_name", None)
    if isinstance(script, CallScript):
        said, caller = (name or "").strip().lower().split(), script.caller_name.strip().lower().split()
        if not said or not studio or said == caller or said[-1] == caller[-1]:
            return script.caller_name
        guest = studio.lower().split()
        # The full name, the surname, or the first name alone ("Ivy"): Jonah's on first-name terms.
        return studio if said == guest or said[-1] == guest[-1] or said == guest[:1] else script.caller_name
    if stayed:
        return stayed if (name or "").strip().lower() == stayed.lower() else script.guest_name
    return name or getattr(script, "guest_name", None)


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
    elif isinstance(script, (InterviewScript, CallScript)):
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
    elif isinstance(script, CallScript):
        # A caller's view is not news: the call files under today's question without moving its story,
        # and never opens one (the 2026-10-27 lesson, when every chat-show guest became a thread).
        seg.thread_id = script.thread_id if world.thread(script.thread_id) else None
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
        tid = None if seg.type is SegmentType.breaking else seg.work.get("scene") or getattr(script, "thread_id", None)
        status = getattr(script, "thread_status", None)
        known = {t.id for t in world.threads}
        # The light shows follow stories up but never open one: on 2026-10-27 every Last Ferry and
        # Coastwide guest became a news story (Priya Anand's cat, Sadie Quill's rabbit), 44 of the
        # 108 open threads. What a guest talks about goes into their memory instead.
        opens = seg.type is SegmentType.breaking or (
            seg.type in THREAD_OPENERS and not schedule.get(seg.show).light)
        if tid not in known and opens and seg.type is not SegmentType.breaking:
            # Not a new story if an open (or faded) thread already has its headline: on 2026-10-27
            # the fire station's case for a second engine ran as twelve threads.
            same = world.same_story(script.headline)
            if same:
                tid = same[0].id
                log.info("%s slot %d: %r continues thread %s (shared %s)", seg.type.value, seg.slot_id,
                         script.headline[:60], tid, ", ".join(sorted(same[1])))
        if tid in known or opens:
            seg.thread_id = world.update_thread(tid if tid in known else None, script.headline, status)
    # Guests join the recurring cast (a stable voice and look), and the writers avoid rebooking them.
    if getattr(script, "guest_name", None) and any(l.speaker == "guest" for l in seg.lines):
        world.ensure_person(script.guest_name, script.guest_role, gender=script.guest_gender,
                            age=getattr(script, "guest_age", None), accent=getattr(script, "guest_accent", None))
        _recent_guests.append(script.guest_name)
        if not template:
            back = seg.work.get("return_guest")
            if back and back.lower() == script.guest_name.strip().lower():
                world.asked_back(back, seg.show)       # before this visit's own loose end is kept
                log.info("%s slot %d: %s came back to be asked about their loose end", seg.type.value,
                         seg.slot_id, back)
            elif (seg.work.get("loose_end_of") or "").lower() == script.guest_name.strip().lower():
                world.loose_ends_taken(script.guest_name)   # booked again of the writer's accord, and asked
            world.remember_guest(script.guest_name, schedule.get(seg.show).title.title(),
                                 getattr(script, "guest_memory", None), getattr(script, "ask_next_time", None))
    if isinstance(script, CallScript):            # a resident now, with a voice; they may ring again another day
        world.ensure_person(script.caller_name, "resident", gender=script.caller_gender, age=script.caller_age,
                            accent=script.caller_accent)
        if not template:
            world.remember_guest(script.caller_name, phonein.CALLED, script.caller_memory, None)
    for l in getattr(script, "lines", []):
        if isinstance(l, VoxLine) and l.speaker == "guest" and l.guest_name:
            world.ensure_person(l.guest_name, "resident", gender=l.guest_gender, age=l.guest_age, accent=l.guest_accent)
    if seg.type is SegmentType.interview and getattr(script, "guest_name", None):
        _last_interview[seg.show] = {
            "slot": seg.slot_id, "name": script.guest_name, "role": script.guest_role or "a guest",
            "asked": "\n".join(f"  {l.speaker}: {l.text[:220]}" for l in seg.lines)[:3000]}
    world.record_aired(seg.type.value, script.headline, seg.thread_id, " ".join(l.text for l in seg.lines),
                       content_hash=seg.content_hash,
                       show=seg.show, brief=seg.brief)
