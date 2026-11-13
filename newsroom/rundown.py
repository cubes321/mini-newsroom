"""Model-planned running orders: tonight's theme and a real subject for each item, on top of the fixed hour orders.

Coastwide and The Last Ferry run fixed orders (schedule.py): each slot has a type and a kind of angle ("a public
figure off duty", "a club, a team or a society"), and the writer of each item picks the subject on its own, with
only the show so far to go on. From `[rundown] lead_min` before a show in `[rundown] shows`, in idle time, the
back office plans the evening in one call: a theme the presenters' links can come back to, and for each planned
slot a subject from the town (a story, an event, a club, a place) and, for an interview, a guest from the people
we know, so the evening is built as a whole rather than one item at a time.

The plan is keyed by the slot's place in the show's order (the producer puts it in `seg.work["order_pos"]`), and
each slot is taken once: after a restart the order starts again from the top, and the slots already written
go back to their fixed briefs. Nothing is planned for a special night's or a special day's version of a show
(its order is different), and a failed call leaves the fixed orders as they were.

    python -m newsroom.rundown magazine        # print the slots the planner would be given, no model
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime, timedelta

from . import calendar, llm, schedule
from .config import CONFIG
from .models import RunningOrder, SegmentType as T
from .world import World

log = logging.getLogger(__name__)

PLANNED = (T.interview, T.feature, T.consumer, T.vox_pop)    # the slots that get a subject; links get the theme
THEMED = (T.links, T.monologue)
RECENT_DAYS = 3                 # a guest on the show in the last few days isn't offered again
OVERRUN = 1.15                  # plan this much more than the hour: items come in short
PEOPLE = 16
SUBJECTS = 30                   # the show's recent headlines, so the plan doesn't repeat them
MAX_SLOTS = 28                  # items come in short, but an hour rarely airs more; 35 asked too much
MAX_TOKENS = 4000               # 28 slots of JSON (the non-thinking route's own default is 2000)

_SYSTEM = """\
You plan tonight's running order for {title}, a programme on a small-town TV station in the FICTIONAL town
in the briefing: {station}. Its tone: {tone}. The order is fixed (SLOTS: each slot's type and the kind of
item it is); you choose what each planned slot is ABOUT, so the evening hangs together and nothing repeats.
- THEME: one short phrase that ties the evening together (the season, a town event coming up, a mood), for
  the presenters' links to come back to now and then. Not a news story. The links carry it: the items don't
  each have to be about it, and most shouldn't be.
- Each slot: a concrete subject from the town: a story in the briefing, an event coming up, a club, a place,
  a trade, a person with a story. Fit the slot's kind of item. A vox pop's subject is its one question.
- Every slot a DIFFERENT subject: no place, person, club or story twice in the evening (one lighthouse, one
  football club, one walk), and one story per slot, not two joined together.
- An interview's guest: an exact name from PEOPLE (someone with something left to ask is a good booking),
  or empty for someone new the writer will cast. Nobody twice. Features, consumer items and vox pops: no guest.
- Someone we know (PEOPLE, the briefing) is booked for what the briefing says about them or what is left to
  ask them: never give them a new history (how long they have lived here, a past job, a family). A slot whose
  kind would need one ("someone who moved here and stayed") goes to someone new.
- A light show: the big serious stories only if one is the talk of the town, and then from the human side.
- Nothing from RECENTLY ON THIS SHOW again. Facts only from the briefing; invent no events.
Everything is fiction. Return ONLY JSON.
"""


def _start(sid: str, now: float) -> float | None:
    """When `sid` next starts within the coming day, on the broadcast clock."""
    for ts, _ in schedule.starts(now):
        if ts > now and schedule.show_at(ts).id == sid and schedule.show_at(ts - 1).id != sid:
            return ts
    return None


def booked(world: World, sid: str, day: str | None = None) -> dict | None:
    day = day or world.last_date
    return next((r for r in reversed(world.rundowns) if r.get("date") == day and r.get("show") == sid), None)


def due(world: World, now: float | None = None) -> str | None:
    """A show to plan now: in `[rundown] shows`, starting within `lead_min`, its ordinary version (not a special
    night's or a special day's), and not planned yet today."""
    if os.environ.get("NEWSROOM_RUNDOWN") == "0":       # the tests: the worker's other jobs, whatever the time
        return None
    now = now or schedule.now()
    for sid in CONFIG.rundown.shows:
        at = _start(sid, now)
        if at is None or at - now > CONFIG.rundown.lead_min * 60 or booked(world, sid):
            continue
        if schedule.show_at(at) is schedule.SHOWS.get(sid):
            return sid
    return None


def slots(show: schedule.Show, length_s: float) -> list[dict]:
    """The slots of `show`'s order that fill `length_s` (and a little over): {pos, type, part, angle}, the planned
    ones only. A vox pop's angle is the one the producer will give it, in turn (show.briefs)."""
    out, run, pos, given = [], 0.0, 0, {}
    while run < length_s * OVERRUN and pos < 80:
        item = show.item(pos)
        run += show.target_for(item)
        angle = item.brief if isinstance(item.brief, str) else ""
        if not angle and item.type in show.briefs:
            n = given.get(item.type, 0)
            given[item.type] = n + 1
            angle = show.briefs[item.type][n % len(show.briefs[item.type])]
        if item.type in PLANNED and item.part in ("", "couch"):
            kind = "a short second guest on the couch" if item.part == "couch" else item.type.value.replace("_", " ")
            out.append({"pos": pos, "type": item.type.value, "part": item.part, "kind": kind, "angle": angle})
        pos += 1
    return out[:MAX_SLOTS]


def _people(world: World, sid: str) -> list:
    """Who may be booked: anyone with something left to ask first, then the public figures and the residents
    seen most, none on this show in the last few days."""
    since = (date.fromisoformat(world.last_date) - timedelta(days=RECENT_DAYS)).isoformat()
    recent = {p.name for p in world.people if any(m.get("show") == sid and m.get("date", "") >= since
                                                  for m in p.memories)}
    back = [p for p in world.return_guests(exclude=recent, limit=4)]
    rest = sorted((p for p in world.people if p.name not in recent and p not in back
                   and p.kind in ("official", "worthy", "resident") and p.role != "resident"),
                  key=lambda p: -p.appearances)
    return (back + rest)[:PEOPLE]


def _recent_subjects(world: World, sid: str) -> list[str]:
    since = (date.fromisoformat(world.last_date) - timedelta(days=RECENT_DAYS)).isoformat()
    with world.lock:
        heads = [e["headline"] for e in world.archive if e.get("show") == sid and e.get("date", "") >= since
                 and e.get("headline") and e["type"] not in (T.ad_break.value, T.bumper.value)]
    return list(dict.fromkeys(heads))[-SUBJECTS:]


def prompt(world: World, sid: str, at: float) -> tuple[str, str, list[dict], list]:
    show = schedule.SHOWS[sid]
    order = slots(show, schedule.show_end(at) - at)
    people = _people(world, sid)
    ends = {p.name: p.loose_ends[-1]["ask"] for p in people if p.loose_ends}
    system = _SYSTEM.format(title=show.title.title(), station=show.station, tone=show.tone)
    user = (f"BRIEFING\n{world.summary_for_prompt(cast=show.cast)}\n\n"
            f"COMING UP IN TOWN:\n{calendar.for_prompt(sid, datetime.fromtimestamp(at)) or '  (nothing listed)'}\n\n"
            f"TONIGHT: {show.title.title()} at {datetime.fromtimestamp(at):%H:%M} on {datetime.fromtimestamp(at):%A}.\n\n"
            "SLOTS (number: the item, the kind of thing it is):\n"
            + "\n".join(f"  {s['pos']}: {s['kind']}" + (f": {s['angle']}" if s["angle"] else "") for s in order)
            + "\n\nPEOPLE:\n" + "\n".join(f"  - {p.name}, {p.role}" + (f" (left to ask: {ends[p.name]})"
                                                                       if p.name in ends else "") for p in people)
            + "\n\nRECENTLY ON THIS SHOW (don't repeat):\n"
            + ("\n".join(f"  - {h}" for h in _recent_subjects(world, sid)) or "  (nothing yet)"))
    return system, user, order, people


def commission(world: World, sid: str, now: float | None = None) -> dict:
    """Plan tonight's `sid` (one call) and record it; an empty plan, recorded, if the model fails, so the fixed
    order runs and nothing asks again today."""
    now = now or schedule.now()
    at = _start(sid, now) or now
    system, user, order, people = prompt(world, sid, at)
    by_pos = {s["pos"]: s for s in order}
    names = {p.name.lower(): p.name for p in people}
    theme, planned = "", {}
    try:
        plan = llm.complete_json("rundown", RunningOrder, system, user, max_tokens=MAX_TOKENS)
    except llm.LLMError as e:
        log.warning("rundown: no plan for %s (%s); the fixed order runs", sid, e)
        plan = None
    if plan is not None:
        theme, used = plan.theme.strip(), set()
        for s in plan.slots:
            slot = by_pos.get(s.slot)
            if slot is None or str(s.slot) in planned or not s.subject.strip():
                continue
            guest = names.get(s.guest.strip().lower(), "") if slot["type"] == T.interview.value else ""
            if guest in used:
                guest = ""
            if guest:
                used.add(guest)
            planned[str(s.slot)] = {"type": slot["type"], "subject": s.subject.strip(), "guest": guest}
    entry = {"date": world.last_date, "show": sid, "title": schedule.SHOWS[sid].title, "theme": theme,
             "slots": planned, "taken": []}
    with world.lock:
        world.rundowns = (world.rundowns + [entry])[-30:]
    log.info("rundown: %s planned, %d of %d slots, theme %r%s", sid, len(planned), len(order), theme,
             f", guests {', '.join(g for g in (v['guest'] for v in planned.values()) if g)}" if planned else "")
    return entry


def _entry(world: World, show: schedule.Show) -> dict | None:
    r = booked(world, show.id)
    return r if r and r.get("title") == show.title and not show.location else None


def take(world: World, show: schedule.Show, pos) -> dict | None:
    """The plan for the slot at `pos` of tonight's `show`, once: a slot already written (before a restart) or a
    special version of the show gets none."""
    r = _entry(world, show)
    if r is None or pos is None or str(pos) not in r["slots"]:
        return None
    with world.lock:
        if str(pos) in r["taken"]:
            return None
        r["taken"].append(str(pos))
    return r["slots"][str(pos)]


def theme(world: World, show: schedule.Show) -> str:
    r = _entry(world, show)
    return r["theme"] if r else ""


def for_prompt(world: World, show: schedule.Show, seg_type: T, slot: dict | None) -> str:
    """What the writer is told: this item's planned subject and guest, and the evening's theme for the links."""
    out = []
    if slot:
        out.append(f"TONIGHT'S RUNNING ORDER has this item as: {slot['subject'].rstrip('.')}.")
        if slot.get("guest"):
            p = world.person_by_name(slot["guest"])
            out.append(f"THE GUEST, booked for it: {slot['guest']}" + (f", {p.role}" if p else "")
                       + ". Use exactly this name as guest_name.")
    t = theme(world, show) if seg_type in THEMED else ""
    if t:
        out.append(f"TONIGHT'S THEME, for the links to come back to now and then (lightly, not every line): {t}.")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    import sys

    from . import world as world_mod

    args = sys.argv[1:] if argv is None else argv
    sid = args[0] if args else "magazine"
    w = world_mod.load()
    at = _start(sid, schedule.now()) or schedule.now()
    system, user, order, _ = prompt(w, sid, at)
    print(system, "\n", user, f"\n\n{len(order)} planned slots", sep="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
