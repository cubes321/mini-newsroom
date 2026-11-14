"""The editors' meeting: once a day the station's editors sit down together (the user, 2026-11-14).

WTV runs two channels on one town. Channel 7's senior editor (senior.py) keeps the news board in shape; Channel 8's
creative editor (entertainment/creative.py) keeps its programmes good. Until now neither heard from the other, and
all that crossed was the town's talk (talk.py). The meeting has four jobs:

- keep the channels out of each other's way: someone in a hard news story is not tonight's jolly guest, the same
  resident is not on both channels all week, a council night or a big story is known to the other side;
- pass stories between them: something that really happened on a Channel 8 programme that the news might pick up,
  and news the light programmes should nod to or steer clear of;
- guard the shared canon: a new fact about the town either side has established is told to the other, and a
  contradiction is named with who fixes it;
- a joint look at the day, kept as minutes the owner can read in the morning.

It is a real exchange: each editor speaks as themselves, on their own model, two rounds, and then the minutes are
written. One call per idle tick (workers._idle_work), from MEET_FROM, after any booking already due, so it never
holds a programme. A turn that fails is tried once more; then the day has no meeting and nothing changes.

**Seats, not channels.** This module knows who sits at the table (SEATS) and nothing of the other channel's code:
the creative editor's seat is registered from outside (entertainment.attend(), on both channels' nights). With one
seat, or any seat's model off, there is no meeting.

**Where the minutes go.** Each action is addressed to a seat. The news side's reach the story desk and the senior
editor beside the senior memo (for_desk); the other seat reads its own (actions). At most one story is OFFERED to
the desk, which may seed it from the day's allowance as it may a guest's loose end; the offer goes once it is
seeded, after OFFER_ROUNDS rounds, or with the day.

**A drama's story stays out of the room.** The minutes sit in the desk's prompt, and what is in a prompt gets used.
So a seat brings only what the town already knows of a drama (that it aired, the question it left: talk.py), never
its arc, an unaired plan or its ledger.

    python -m newsroom.meeting minutes [--date D]     the meeting as held: who said what, and the minutes
    python -m newsroom.meeting hold [--dry]           hold today's now, all of it; --dry keeps and saves nothing
"""
from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Annotated, Callable

from pydantic import BaseModel, BeforeValidator, Field

from . import channel, llm, safety, schedule
from .config import CONFIG
from .models import _clip, _clip_words
from .world import World

log = logging.getLogger(__name__)

MEET_FROM = "16:00"                # before the evening's bookings on either channel (the first is from 17:00)
ROUNDS = 2                         # each editor speaks this many times
TURN_WORDS = 150
MAX_TOKENS = 16000                 # thinking counts against it; the Opus provider's own default is 4000
TIMEOUT_S = 120
TRIES, TRY_GAP_S = 2, 20 * 60      # a turn that fails is tried once more, later; then no meeting today
KEPT = 14                          # meetings kept, with their turns
STANDS_DAYS = 1                    # yesterday's minutes still stand: the channels take turns
OFFER_ROUNDS = 4                   # the desk is shown an offered story this many rounds at most
# Who writes the minutes: its own route, or the senior editor's (Sonnet) while config.toml has none.
TASK = "meeting" if "meeting" in CONFIG.llm.routes else "senior_editor"


@dataclass(frozen=True)
class Seat:
    name: str                      # how the minutes address it: "news", "channel8"
    title: str                     # "the senior editor of Channel 7"
    task: str                      # the route its turns are on: each editor on their own model
    persona: str                   # who they are at the table
    brief: Callable                # (world) -> what they bring, read from the world alone
    people: Callable | None = None     # (world) -> {resident's name: where they are on this channel}
    order: int = 5                 # who speaks first


SEATS: dict[str, Seat] = {}


def seat(name: str, title: str, *, task: str, persona: str, brief: Callable, people: Callable | None = None,
         order: int = 5) -> Callable[[], None]:
    """Give an editor a seat. Returns an undo."""
    SEATS[name] = Seat(name, title, task, persona, brief, people, order)
    return lambda: SEATS.pop(name, None)


def _order() -> list[Seat]:
    return sorted(SEATS.values(), key=lambda s: (s.order, s.name))


def _safe(f: Callable | None, world: World):
    """A seat's own callable must never take the idle worker down."""
    if f is None:
        return None
    try:
        return f(world)
    except Exception:  # noqa: BLE001
        log.exception("editors' meeting: a seat's own %s failed", getattr(f, "__name__", "callable"))
        return None


# ------------------------------------------------------------------ the schemas

Note = Annotated[str, _clip_words(240)]


def _first(n: int) -> BeforeValidator:
    return BeforeValidator(lambda v: v[:n] if isinstance(v, list) else v)


class Turn(BaseModel):
    says: Annotated[str, _clip_words(1100)] = Field(description="what you say at the table, as yourself")


class Action(BaseModel):
    to: str = Field(description="the seat that agreed to do it: one of SEATS' names")
    about: Annotated[str, _clip(60)] = Field(
        default="", description="the programme's name, or a story's thread id; empty if it is for the whole channel")
    what: Note = Field(description="one sentence a planner can act on")


class Offer(BaseModel):
    what: Annotated[str, _clip_words(300)] = Field(description="what happened, where and to whom, as a tip-off")
    people: Annotated[list[str], _first(3)] = Field(default_factory=list, description="the residents in it, exact names")


class Minutes(BaseModel):
    """What the editors' meeting agreed (meeting.py)."""
    verdict: Annotated[str, _clip_words(500)] = Field(
        description="two or three sentences: how each channel's last night went, and what matters tonight")
    actions: Annotated[list[Action], _first(8)] = Field(default_factory=list)
    canon: Annotated[list[Note], _first(4)] = Field(
        default_factory=list, description="a fact about the town now settled between the channels, or a "
                                          "contradiction and who puts it right")
    offer: Offer | None = Field(default=None, description="one thing that really happened on the entertainment "
                                                          "channel that the news desk may make a story of, or null")


_RULES = """\
This is the daily editors' meeting of WTV, Wexley Television, which runs two channels in the FICTIONAL town of the
briefing: Channel 7, the news channel, and Channel 8, the entertainment channel. They share the town: its people, its
places, its calendar. The meeting has four jobs:
- KEEP OUT OF EACH OTHER'S WAY: someone in a hard news story is not tonight's jolly guest; the same resident is not
  on both channels all week (ON BOTH CHANNELS lists them); a council night or a big story is known to the other side.
- PASS STORIES: something that really happened on a Channel 8 programme that the news could pick up (a quiz upset, a
  sight drawing a crowd, a place visited), and news the light programmes should nod to or steer clear of.
- GUARD THE SHARED CANON: a new fact about the town either side has established is told to the other; a
  contradiction is named, and who must put it right.
- A JOINT LOOK AT THE DAY: how each channel's last night went, and what matters tonight.
Channel 8's drama is fiction inside the town: its story is not town fact and is not discussed here, beyond that it
aired and what the town is asking.
WHAT THE MEETING CAN DO, and all it can do: what is agreed goes as a short note to the news channel's story desk (it
plans the running stories' next steps and may open a new one) and to the planners who book each Channel 8
programme's next edition (its guests, subjects, questions, plans). So agree only what such a note can carry: who or
what to keep off or put on, what to steer clear of or nod to, a fact to keep to. Neither of you can send the other
anything later, look through old scripts, put a correction on air, or meet again before tomorrow: don't offer to. The
first held dry (2026-11-14) had each editor promising the other a football score by evening.
Say only what your own notes below show: if they show no last night for your channel, you have none to report.
Speak as yourself, plainly, to a colleague: at most {words} words, up to four points, each naming a programme, a
story or a person. Answer what was put to you, and say no where you mean no. Don't plan the other channel's
programmes for it. Everything is fiction, at small-town scale. Return ONLY JSON.
"""

_MINUTES = """\
You take the minutes of the daily editors' meeting of WTV, Wexley Television, which runs two channels in a FICTIONAL
town: Channel 7, the news channel, and Channel 8, the entertainment channel. Write what was AGREED, not what was said:
- verdict: two or three sentences: how each channel's last night went, and what matters tonight.
- actions: at most eight, only what the editor it is addressed to agreed to or did not contest; nothing one side
  asked and the other refused. Each is `to` a seat (a name from SEATS), `about` a programme by its name or a story by
  its thread id (empty if it is for the whole channel), and `what`: one sentence a planner can act on. An action is
  read by the news channel's story desk or by the planner who books a programme's next edition, and by nobody else:
  leave out anything such a planner can't do (sending something later, checking old scripts, a correction on air),
  and never one action twice for two programmes: address it to the whole channel.
- canon: at most four: a fact about the town now settled between the channels, or a contradiction and who puts it
  right. Never anything from Channel 8's drama: its story is fiction, not the town's.
- offer: at most ONE thing that really happened on a Channel 8 programme that the news desk may make a story of, as a
  tip-off (what, where, who), if the news side wanted it; null otherwise. Never the drama's story.
The minutes stand until tomorrow's meeting: write nothing that will be untrue by then (a match not yet played, "no
result yet"), and give a date to anything that ends on one. Add nothing that was not said. Return ONLY JSON.
"""


# ------------------------------------------------------------------ the news side's seat

_NEWS = ("You are the senior editor of Channel 7, the news channel. You guard the news: the town's facts, the board "
         "of running stories and what the bulletins repeat. You know the board below. You don't make Channel 8's "
         "programmes, and its drama is no business of the news.")


def _who(x) -> str:
    return x if isinstance(x, str) else (x.get("name") or "") if isinstance(x, dict) else ""


def _tonight(rows: list[dict], day: str) -> dict | None:
    return next((r for r in reversed(rows) if r.get("date") == day), None)


def _bookings(world: World) -> list[tuple[str, str, list[str]]]:
    """Tonight's Channel 7 bookings made so far: (the programme, what it is on, who is booked)."""
    day, out = world.last_date, []
    if b := _tonight(world.inquiries, day):
        out.append(("The Inquiry", b.get("title") or "", [_who(b.get("guest"))]))
    if b := _tonight(world.phone_ins, day):
        out.append(("Have Your Say", b.get("question") or "", [_who(b.get("guest"))]))
    if b := _tonight(world.panels, day):
        out.append(("The Panel", "; ".join(str(q) for q in (b.get("questions") or [])[:3]),
                    [_who(p) for p in b.get("panellists") or []]))
    return [(show, what, [n for n in names if n]) for show, what, names in out]


def _news_brief(world: World) -> str:
    out = f"BRIEFING\n{world.summary_for_editor()}"
    if world.senior_memo:
        out += f"\n\nYOUR LATEST MEMO TO THE STORY DESK ({world.senior_memo_at}):\n{world.senior_memo}"
    if booked := _bookings(world):
        out += "\n\nBOOKED ON CHANNEL 7 TONIGHT:\n" + "\n".join(
            f"  - {show}: {what}" + (f" (with {', '.join(names)})" if names else "") for show, what, names in booked)
    return out


def _news_people(world: World) -> dict[str, str]:
    out: dict[str, str] = {}
    for t in world.board_threads():
        for pid in t.people:
            if p := world.person(pid):
                out.setdefault(p.name, f"in the news ({t.id}: {t.title[:60]})")
    for show, _, names in _bookings(world):
        for n in names:
            out.setdefault(n, f"booked tonight on {show}")
    return out


seat("news", "the senior editor of Channel 7", task="senior_editor", persona=_NEWS, brief=_news_brief,
     people=_news_people, order=0)


# ------------------------------------------------------------------ holding it

def _on(task: str) -> bool:
    return llm.provider_for(task) != "off"


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def today(world: World) -> dict | None:
    return next((m for m in reversed(world.meetings) if m["date"] == world.last_date), None)


def due(world: World, now: float | None = None) -> bool:
    """Is there a call of today's meeting to make? Two seats or more, every model there to ask, MEET_FROM passed,
    and the meeting neither over nor waiting out a failed turn."""
    seats = _order()
    if len(seats) < 2 or not all(_on(s.task) for s in seats) or not _on(TASK):
        return False
    now = now or schedule.now()
    if now < _at(MEET_FROM, now):
        return False
    m = today(world)
    if m is None:
        return True
    return not m["done"] and (not m["tried"] or time.time() - m["ts"] >= TRY_GAP_S)


def _new(world: World) -> dict:
    return {"date": world.last_date, "at": f"{datetime.fromtimestamp(schedule.now()):%H:%M}", "turns": [],
            "minutes": None, "done": False, "tried": 0, "ts": 0.0, "shown": 0, "taken": False}


def step(world: World) -> bool:
    """One call of today's meeting: the next editor's turn, or the minutes once every turn is in. False if it
    failed (tried once more later, then the day has no meeting)."""
    m = today(world)
    if m is None:
        m = _new(world)
        with world.lock:
            world.meetings.append(m)
            del world.meetings[:-KEPT]
    return _advance(world, m)


def _sheet(world: World) -> str:
    """What code can tell both editors: the day, who is on the air, and the residents on both channels."""
    seats = [(s, {k.lower(): (k, v) for k, v in (_safe(s.people, world) or {}).items()}) for s in _order() if s.people]
    day = date.fromisoformat(world.last_date)
    out = (f"TODAY is {day:%A %d %B}. {schedule.clock_line(schedule.now())} {channel.CURRENT.name} is the channel on "
           "the air today; the other is off until its next night.")
    both = sorted(set.intersection(*(set(p) for _, p in seats))) if len(seats) >= 2 else []
    if both:
        out += "\n\nON BOTH CHANNELS (the same resident on each side):\n" + "\n".join(
            f"  - {seats[0][1][k][0]}: " + "; ".join(p[k][1] for _, p in seats) for k in both[:20])
    else:
        out += "\n\nON BOTH CHANNELS: nobody at present."
    return out


def _said(m: dict) -> str:
    return "\n\n".join(f"{t['title'].upper()}: {t['says']}" for t in m["turns"])


def _advance(world: World, m: dict) -> bool:
    seats = _order()
    try:
        if len(m["turns"]) < ROUNDS * len(seats):
            s = seats[len(m["turns"]) % len(seats)]
            last = len(m["turns"]) >= (ROUNDS - 1) * len(seats)
            user = (f"{_safe(s.brief, world) or ''}\n\n{_sheet(world)}\n\nTHE MEETING SO FAR:\n"
                    + (_said(m) or "(nothing yet: you open it)")
                    + f"\n\nYour turn, {s.title}"
                    + (": your last word today. Settle only what is still open, in a sentence or two each; don't "
                       "say again what is already agreed." if last else "."))
            t = llm.complete_json(s.task, Turn, _RULES.format(words=TURN_WORDS) + "\n" + s.persona, user,
                                  max_tokens=MAX_TOKENS, timeout_s=TIMEOUT_S)
            if bad := safety.check(t.says):
                raise llm.LLMError(f"{bad!r} in {s.title}'s turn")
            with world.lock:
                m["turns"].append({"seat": s.name, "title": s.title, "says": t.says.strip()})
            log.info("editors' meeting: %s: %s", s.title, t.says.replace("\n", " / "))
        else:
            user = ("SEATS:\n" + "\n".join(f"  - {s.name}: {s.title}" for s in seats)
                    + f"\n\n{_sheet(world)}\n\nTHE MEETING:\n{_said(m)}")
            mins = llm.complete_json(TASK, Minutes, _MINUTES, user, max_tokens=MAX_TOKENS, timeout_s=TIMEOUT_S)
            if bad := safety.check(safety.strings(mins)):          # they go into the desk's and the planners' prompts
                raise llm.LLMError(f"{bad!r} in the minutes")
            names = {s.name for s in seats}
            with world.lock:
                m["minutes"] = {"verdict": mins.verdict, "canon": list(mins.canon),
                                "actions": [a.model_dump() for a in mins.actions if a.to in names],
                                "offer": mins.offer.model_dump() if mins.offer else None}
                m["done"] = True
            log.info("editors' meeting: minutes: %s | %d actions, %d canon%s", mins.verdict.replace("\n", " "),
                     len(m["minutes"]["actions"]), len(mins.canon), ", a story offered" if mins.offer else "")
        with world.lock:
            m["tried"] = 0
        return True
    except llm.LLMError as e:
        with world.lock:
            m["tried"], m["ts"] = m["tried"] + 1, time.time()
            m["done"] = m["tried"] >= TRIES
        log.warning("editors' meeting: %s (%s)", "no meeting today" if m["done"] else "a turn failed; once more later",
                    str(e)[:200])
        return False


# ------------------------------------------------------------------ what was agreed, for those who act on it

def latest(world: World) -> dict | None:
    """The newest meeting with minutes that still stands: today's, or yesterday's (the channels take turns, so the
    last one was held on the other channel's night)."""
    since = (date.fromisoformat(world.last_date) - timedelta(days=STANDS_DAYS)).isoformat()
    return next((m for m in reversed(world.meetings)
                 if m.get("minutes") and since <= m["date"] <= world.last_date), None)


def actions(world: World, to: str) -> tuple[str, list[tuple[str, str]]]:
    """The standing minutes' actions for a seat: (the meeting's date, [(about, what)])."""
    m = latest(world)
    if not m:
        return "", []
    return m["date"], [(a.get("about") or "", a["what"]) for a in m["minutes"]["actions"] if a["to"] == to]


def canon(world: World) -> list[str]:
    m = latest(world)
    return list(m["minutes"]["canon"]) if m else []


def for_desk(world: World, *, offer: bool = True) -> str:
    """The standing minutes as the news side reads them, after the senior memo: its actions, the canon, and (the
    desk only) a story offered today, until it is taken or has been shown OFFER_ROUNDS times."""
    m = latest(world)
    if not m:
        return ""
    mins, out = m["minutes"], []
    acts = [(a.get("about") or "", a["what"]) for a in mins["actions"] if a["to"] == "news"]
    if acts:
        out.append(f"FROM THE EDITORS' MEETING ({m['date']}): what the senior editor agreed with Channel 8's creative "
                   "editor. Follow it where it touches these threads:\n"
                   + "\n".join(f"  - {f'[{about}] ' if about else ''}{what}" for about, what in acts))
    if mins["canon"]:
        out.append("SETTLED BETWEEN THE CHANNELS (the town's facts: keep to them):\n"
                   + "\n".join(f"  - {c}" for c in mins["canon"]))
    o = mins.get("offer")
    if offer and o and m["date"] == world.last_date and not m.get("taken") and m.get("shown", 0) < OFFER_ROUNDS:
        with world.lock:
            m["shown"] = m.get("shown", 0) + 1
        out.append("OFFERED BY CHANNEL 8 (it really happened in the town, on one of its programmes; not news unless "
                   f"you make it so): {o['what']}" + (f" People: {', '.join(o['people'])}." if o.get("people") else "")
                   + "\nIf it would really make news in a small town, you may seed it as one of the new threads; if "
                     "not, leave it.")
    return "\n\n".join(out) + "\n\n" if out else ""


_WORD = re.compile(r"[a-z']{4,}")


def offer_seeded(world: World, new_threads: list) -> None:
    """The desk's round is in: if one of its new stories is the one offered, the offer is taken and shown no more."""
    m = today(world)
    o = (m.get("minutes") or {}).get("offer") if m else None
    if not o or m.get("taken"):
        return
    names = {n.lower() for n in o.get("people") or []}
    words = set(_WORD.findall(o["what"].lower()))
    for nt in new_threads:
        if names & {p.lower() for p in nt.people} or len(words & set(_WORD.findall(f"{nt.title} {nt.status}".lower()))) >= 3:
            with world.lock:
                m["taken"] = True
            log.info("editors' meeting: the desk took the offered story (%s)", nt.title)
            return


# ------------------------------------------------------------------ reading it, holding it by hand

def show(m: dict) -> str:
    out = [f"THE EDITORS' MEETING, {m['date']} at {m.get('at', '?')}"]
    out += [f"\n{t['title'].upper()}:\n  {t['says']}" for t in m["turns"]]
    mins = m.get("minutes")
    if not mins:
        return "\n".join(out + ["\n(no minutes: " + ("the meeting was not finished)" if not m["done"] else "it failed)")])
    out.append(f"\nMINUTES\n  {mins['verdict']}")
    out += [f"  - to {a['to']}" + (f" [{a['about']}]" if a.get("about") else "") + f": {a['what']}" for a in mins["actions"]]
    out += [f"  canon: {c}" for c in mins["canon"]]
    if o := mins.get("offer"):
        out.append(f"  offered to the news desk: {o['what']}" + (" (taken)" if m.get("taken") else ""))
    return "\n".join(out)


def _cli(argv: list[str]) -> int:
    import argparse

    from . import world as world_mod

    ap = argparse.ArgumentParser(prog="python -m newsroom.meeting")
    ap.add_argument("cmd", choices=["minutes", "hold"])
    ap.add_argument("--date", help="minutes: the day (default: the latest held)")
    ap.add_argument("--dry", action="store_true", help="hold: print it without keeping or saving it")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "openai", "urllib3", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    print(f"world: {CONFIG.paths.world}")
    w = world_mod.load()
    if a.cmd == "minutes":
        m = next((x for x in reversed(w.meetings) if not a.date or x["date"] == a.date), None)
        print(show(m) if m else "No meeting has been held" + (f" on {a.date}." if a.date else " yet."))
        return 0 if m else 1
    try:                                              # the other channel's editor, if this station has one
        import entertainment

        entertainment.attend()
    except ImportError:
        pass
    seats = _order()
    if len(seats) < 2 or not all(_on(s.task) for s in seats) or not _on(TASK):
        print("no meeting: it needs two editors and their models (" + ", ".join(s.title for s in seats) + ")")
        return 1
    m = _new(w)
    while not m["done"]:
        if not _advance(w, m):
            m["done"] = True                          # by hand: no second try later
    print(show(m))
    if not a.dry and m.get("minutes"):
        with w.lock:
            w.meetings[:] = [x for x in w.meetings if x["date"] != m["date"]] + [m]
            del w.meetings[:-KEPT]
        world_mod.save(w)
    return 0 if m.get("minutes") else 1


if __name__ == "__main__":
    import sys

    # Run as a script this file is "__main__", a second copy: the seats are registered on newsroom.meeting.
    from newsroom import meeting as _meeting

    raise SystemExit(_meeting._cli(sys.argv[1:]))
