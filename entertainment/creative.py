"""Channel 8's creative editor: the one who keeps the made-up and the light programmes good (the user, 2026-11-13;
planned 2026-11-14).

Channel 7's senior editor guards the news: the board's shape, the town's canon, repeats. Nobody stood above
Channel 8's planners: each show books itself, and nothing checked that the soap's storylines pay off, that a
character stays themselves, or that a joke or an angle isn't used twice. This is that editor, on a stronger model
than the planners (the "creative" route: Opus, or the senior editor's if config.toml has no such route). It does
two things, both in the back office and neither on the live path:

- AFTER AIR it reviews each programme once, in idle time, the same night: the plan as booked and the words that
  went out (the archive entry's cached segment). It leaves short NOTES for whoever plans the next edition, REMARKS
  for the station's owner (what only a change to a programme's standing rules could fix), and keeps a LEDGER: what
  has been told, what the programme has established, what a drama has set up and not yet paid off.
- BEFORE AIR it vets a plan (the soap's arc and episode, Tideline's plan, The Coast Road's route) and may send it
  back ONCE with notes. The planner plans again on its own model; if that second plan fails the module's own
  check, the first stands. A plan that is merely not how the editor would do it passes.

Notes go into PLANNER prompts only (for_planner), never into every item's (writers.PROMPT_HOOKS): both 20:40 series
showed that what is in every item's prompt is said in every item. The rests stay in code (kettle.REST_DAYS, the
sight rotation, the contributor rests) as hard limits; the editor judges what code can't.

Shows enrol themselves (register), so a programme not yet designed joins with a few lines. With no key, the models
off or any error, every entry point behaves as if the editor were absent and the planners run exactly as before.

    python -m entertainment.creative notes                 the latest marks, notes, remarks and ledger
    python -m entertainment.creative review [--dry] [--date D] [--show ID]

Both read the world NEWSROOM_WORLD names (the town's own by default); `review` without --dry saves it, so never
while a station is running on that world.
"""
from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Annotated, Callable, Literal

from pydantic import BaseModel, BeforeValidator, Field

from newsroom import llm, safety, schedule
from newsroom.config import CONFIG
from newsroom.models import _clip, _clip_words
from newsroom.world import World

log = logging.getLogger(__name__)

# The stronger model: its own route, or the senior editor's (Sonnet) while config.toml has none.
TASK = "creative" if "creative" in CONFIG.llm.routes else "senior_editor"
MAX_TOKENS = 16000                 # thinking counts against it, and the Opus provider's own default is 4000
REVIEW_TIMEOUT_S, VET_TIMEOUT_S = 120, 90
VET_MARGIN_S = 30 * 60             # no vet this close to air: the booking must not be held
VET_BUDGET_S = 240                 # nor once the booking has already taken this long
CATCH_UP_DAYS = 7                  # a night whose review was missed (the station was closed) is still reviewed
NOTE_DAYS = 21                     # notes older than this are no longer the planner's business
ITEM_CHARS, SHOW_CHARS = 2500, 40_000    # the words read: each item's, and a programme's in all
TRIES, TRY_GAP_S, QUIET_S = 2, 30 * 60, 3600
KEPT = {"told": 40, "facts": 40, "open": 12, "log": 60, "vets": 30}


@dataclass(frozen=True)
class Entry:
    id: str
    title: str
    kind: str                      # fiction | factual | light
    brief: str                     # what the programme is and what good looks like, for the editor
    decides: str = ""              # what its nightly planner decides: notes ask only for that
    series_decides: str = ""       # what its long plan decides (an arc, a route), if it has one
    vetted: bool = False           # its plans are read before air
    airs_at: str = ""              # "20:20"
    digest: Callable | None = None     # (world, day) -> that night's plan as booked; "" for none or a stand-in
    aired: Callable | None = None      # (world) -> the dates it aired, by its own stamp (else the archive says)
    books: Callable | None = None      # (world) -> is its booking due now?


SHOWS: dict[str, Entry] = {}
_quiet_until = 0.0                 # after a model that can't be reached: no calls until then


def register(show_id: str, title: str, *, kind: str, brief: str, decides: str = "", series_decides: str = "",
             vetted: bool = False, airs_at: str = "", digest: Callable | None = None,
             aired: Callable | None = None, books: Callable | None = None) -> Callable[[], None]:
    """Enrol a programme with the editor. Returns an undo."""
    SHOWS[show_id] = Entry(show_id, title, kind, brief, decides, series_decides, vetted, airs_at, digest, aired, books)
    return lambda: SHOWS.pop(show_id, None)


def install() -> Callable[[], None]:
    """The editor's idle jobs (workers.IDLE_JOBS). First of all, a missed night's review that a booking due now is
    waiting for: at most one call before any booking. Last of all, every other review. Returns an undo."""
    from newsroom import workers

    first, last = (urgent_due, review_urgent), (later_due, review_later)
    workers.IDLE_JOBS.insert(0, first)
    workers.IDLE_JOBS.append(last)

    def undo() -> None:
        global _quiet_until
        for job in (first, last):
            if job in workers.IDLE_JOBS:
                workers.IDLE_JOBS.remove(job)
        _quiet_until = 0.0
    return undo


# ------------------------------------------------------------------ what the editor keeps

def state(world: World) -> dict:
    """world.creative: {notes, ledger, log, vets, tried}."""
    with world.lock:
        c = world.creative
        for key, empty in (("notes", dict), ("ledger", dict), ("log", list), ("vets", list), ("tried", dict)):
            if key not in c:
                c[key] = empty()
        return c


def _ledger(world: World, show_id: str) -> dict:
    with world.lock:
        led = state(world)["ledger"].setdefault(show_id, {})
        for key in ("told", "facts", "open"):
            led.setdefault(key, [])
        return led


def _on() -> bool:
    """Is there an editor to ask? Not with the models off (every test, a station with no key set to "off"), nor in
    the hour after its model couldn't be reached."""
    return llm.provider_for(TASK) != "off" and time.time() >= _quiet_until


def _failed(e: Exception, what: str) -> None:
    global _quiet_until
    # No key, no network: every later call would fail the same way. A timeout is one slow call, not that.
    if isinstance(e, llm.LLMUnavailable) and not isinstance(e, llm.LLMTimeout):
        _quiet_until = time.time() + QUIET_S
        log.warning("creative editor unavailable for %s (%s); quiet for an hour", what, str(e)[:160])
    else:
        log.warning("creative editor: %s failed (%s)", what, str(e)[:200])


def _safe(f: Callable | None, *args):
    """A show's own callable must never take a booking or the idle worker down."""
    if f is None:
        return None
    try:
        return f(*args)
    except Exception:  # noqa: BLE001
        log.exception("creative editor: a programme's own %s failed", getattr(f, "__name__", "callable"))
        return None


def _at(hhmm: str, now: float) -> float:
    h, m = (int(x) for x in hhmm.split(":"))
    return datetime.fromtimestamp(now).replace(hour=h, minute=m, second=0, microsecond=0).timestamp()


def _fresh(day: str, today: str, days: int = NOTE_DAYS) -> bool:
    try:
        return 0 <= (date.fromisoformat(today) - date.fromisoformat(day)).days <= days
    except ValueError:
        return False


# ------------------------------------------------------------------ the schemas

Note = Annotated[str, _clip_words(240)]
Short = Annotated[str, _clip_words(140)]


def _first(n: int) -> BeforeValidator:
    """A list past its length is cut, not failed: a slip must never cost a second call to the strong model."""
    return BeforeValidator(lambda v: v[:n] if isinstance(v, list) else v)


class Verdict(BaseModel):
    """The editor's reading of a plan before it airs."""
    ok: bool = Field(description="true: the plan may air as it is")
    notes: Annotated[list[Note], _first(4)] = Field(
        default_factory=list, description="if not ok: what to change, each naming the scene, sequence or stop")


class Review(BaseModel):
    """The editor's reading of a programme after it has aired."""
    mark: Literal["good", "fair", "weak"]
    verdict: Annotated[str, _clip(300)] = Field(description="one or two sentences: how it went")
    notes: Annotated[list[Note], _first(4)] = Field(
        default_factory=list, description="to the planner of the NEXT edition: only what THE PLANNER DECIDES")
    series_notes: Annotated[list[Note], _first(3)] = Field(
        default_factory=list, description="to its long plan (the arc, the next route), if it has one")
    remarks: Annotated[list[Note], _first(3)] = Field(
        default_factory=list, description="for the station's owner: what only a change to its standing rules could fix")
    told: Annotated[list[Short], _first(8)] = Field(
        default_factory=list, description="jokes, stories, angles, facts told tonight that must not come round again")
    established: Annotated[list[Short], _first(6)] = Field(
        default_factory=list, description="what tonight established that later editions must keep to")
    planted: Annotated[list[Short], _first(4)] = Field(
        default_factory=list, description="a drama: what tonight set up that is not yet paid off")
    paid_off: Annotated[list[int], _first(12)] = Field(
        default_factory=list, description="the numbers from STILL OPEN that tonight paid off or closed")


_WHO = """\
You are the creative editor of Channel 8, the entertainment channel of a small-town television station in a FICTIONAL
town. The senior editor guards the news; you keep the made-up and the light programmes good. You don't write scripts
or plans yourself."""

_REVIEW = _WHO + """
After a programme has aired you read its plan and what went out, and leave short notes for whoever plans its next
edition. Look for:
- BUILD AND PAYOFF: what was set up and never paid off; a cliffhanger answered too cheaply or not at all; a storyline
  standing still. STILL OPEN lists what earlier episodes planted: say which numbers tonight paid off.
- CHARACTERS AND DOUBLE ACTS: people who stopped being themselves. A pair works because their ways clash (one
  measures nothing, the other weighs everything): say so when they agreed all night or swapped ways.
- TOLD TWICE: a joke, story, fact, angle, dish or kind of guest that TOLD BEFORE already has, or that came round
  twice tonight.
- THE SAME AGAIN: a film on a sight it has shown before, from the same angle, with the same people.
- NEW HISTORY: a resident of the town given family, a past or a habit the town never knew. In a drama: the town's
  real people, places or news treated as part of the story, or the story treated as town fact.
notes: at most four short directives to the planner of this programme's NEXT edition, each asking only for something
THE PLANNER DECIDES; if it decides nothing nightly, leave notes empty. series_notes: the same for its long plan, if
it has one. remarks: what only a change to the programme's standing rules could fix, for the station's owner. told,
established, planted: what tonight added, a line each (planted is a drama's only). If the words were not kept, judge
the plan alone and say less. An item marked a stand-in script is not the writers' work: ignore it. Small-town scale;
everything is fiction. Return ONLY JSON.
"""

_VET = _WHO + """
A planner has drafted the {what} below, before it airs. Read it against what the planner was given, your last notes,
TOLD BEFORE, ESTABLISHED and STILL OPEN. Send it back only for something a viewer would notice: a storyline that goes
nowhere or drops what was planted; a cliffhanger nobody would ask about; a character acting against what is
ESTABLISHED; an angle, story or person the programme has had before; new history for a resident of the town; the
town's news inside a drama. A plan that is merely not how you would do it passes: ok = true, no notes. If you send it
back: at most four short notes, each naming the scene, sequence or stop and what to do instead, and only about what
this planner decides. It comes back once and then airs. Return ONLY JSON.
"""

SENT_BACK = """

YOUR FIRST DRAFT of the {what}:
{plan}

THE CREATIVE EDITOR SENT IT BACK, once, with these notes:
{notes}

Plan it again, whole, to the same rules. Change what the notes ask and keep what they don't touch. The editor will not
see it again: this draft airs."""


# ------------------------------------------------------------------ what went out

def _name(world: World, speaker: str | None) -> str:
    c = world.character(speaker) if speaker else None
    return c.name if c else (speaker or "?")


def _cached_words(world: World, h: str | None) -> str:
    """A segment's lines as they were voiced, from its cache entry (workers._save_cached keeps every scripted
    segment, a drama's too, for [cache] keep_days); "" if it has gone."""
    if not h:
        return ""
    try:
        seg = json.loads((CONFIG.paths.cache / f"{h}.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    said = "\n".join(
        f"{l['guest_name'] if l.get('speaker') == 'guest' and l.get('guest_name') else _name(world, l.get('speaker'))}: "
        f"{l.get('text', '')}" for l in seg.get("lines", []) if l.get("text"))
    return ("(a stand-in script) " if seg.get("fallback") else "") + said


def _words(world: World, show_id: str, day: str) -> tuple[str, int, bool]:
    """What went out on `day`: the text, how many items, and whether any of the words themselves were kept."""
    entries = [e for e in world.aired_archive() if e.get("show") == show_id and e.get("date") == day]
    if not entries:
        return "", 0, False
    cap = max(300, min(ITEM_CHARS, SHOW_CHARS // len(entries)))
    out, kept = [], False
    for e in entries:
        said = _cached_words(world, e.get("hash")) or e.get("text") or ""     # the archive's own 400; none for a drama
        kept = kept or bool(said)
        head = e.get("headline") or e.get("brief") or e.get("type") or "item"
        out.append(f"[{head}]\n{said[:cap] if said else '(its words were not kept)'}")
    return "\n\n".join(out), len(entries), kept


def _aired_days(world: World, e: Entry) -> list[str]:
    if e.aired is not None:
        return sorted(set(_safe(e.aired, world) or []))
    return sorted({a["date"] for a in world.aired_archive() if a.get("show") == e.id})


def _over(world: World, e: Entry, now: float) -> bool:
    """Tonight's edition has gone out: its slot has come, another programme has the air, and nothing of it is
    written and still waiting to air."""
    if e.airs_at and now < _at(e.airs_at, now):
        return False
    if schedule.show_at(now).id == e.id:
        return False
    with world.lock:
        return not any(a.get("show") == e.id and a.get("date") == world.last_date and a.get("aired") is False
                       for a in world.archive)


def _reviewed(world: World, show_id: str, day: str) -> bool:
    return any(l["show"] == show_id and l["date"] == day for l in state(world)["log"])


def _may_try(world: World, show_id: str, day: str) -> bool:
    t = state(world)["tried"].get(f"{day}|{show_id}")
    return not t or (t["n"] < TRIES and time.time() - t["ts"] >= TRY_GAP_S)


def _pending(world: World, now: float) -> list[tuple[Entry, str]]:
    """The reviews owed, the earlier night first: for each programme tonight's edition once it is over, and the
    latest earlier night within CATCH_UP_DAYS. Not every night it ever missed: only the one its next plan follows."""
    today = world.last_date
    since = (date.fromisoformat(today) - timedelta(days=CATCH_UP_DAYS)).isoformat()
    out = []
    for e in SHOWS.values():
        days = [d for d in _aired_days(world, e) if since <= d <= today]
        earlier = [d for d in days if d < today][-1:]
        tonight = [today] if today in days and _over(world, e, now) else []
        out += [(e, d) for d in earlier + tonight if not _reviewed(world, e.id, d) and _may_try(world, e.id, d)]
    return sorted(out, key=lambda p: p[1])


def _urgent(world: World, now: float | None = None) -> tuple[Entry, str] | None:
    """A missed night's review that tonight's booking is waiting for: the programme's booking is due now, and air
    is far enough off that one more call won't hold it."""
    if not _on():
        return None
    now = now or schedule.now()
    for e, day in _pending(world, now):
        if (day != world.last_date and e.books is not None and e.airs_at
                and now < _at(e.airs_at, now) - VET_MARGIN_S and _safe(e.books, world)):
            return e, day
    return None


def _later(world: World, now: float | None = None) -> tuple[Entry, str] | None:
    if not _on():
        return None
    return next(iter(_pending(world, now or schedule.now())), None)


def urgent_due(world: World, now: float | None = None) -> bool:
    try:
        return _urgent(world, now) is not None
    except Exception:  # noqa: BLE001
        log.exception("creative editor: could not tell what is due")
        return False


def later_due(world: World, now: float | None = None) -> bool:
    try:
        return _later(world, now) is not None
    except Exception:  # noqa: BLE001
        log.exception("creative editor: could not tell what is due")
        return False


def review_urgent(world: World) -> None:
    if found := _urgent(world):
        review(world, found[0].id, found[1])


def review_later(world: World) -> None:
    if found := _later(world):
        review(world, found[0].id, found[1])


# ------------------------------------------------------------------ after air: the review

def _history(world: World, e: Entry, *, numbered: bool = True) -> str:
    """What the editor already holds on a programme: its last marks, its last notes and its ledger."""
    st, led = state(world), _ledger(world, e.id)
    out = []
    logs = [l for l in st["log"] if l["show"] == e.id and l.get("mark")][-3:]
    if logs:
        out.append("YOUR LAST REVIEWS of it:\n" + "\n".join(f"  - {l['date']}: {l['mark']}. {l['verdict']}" for l in logs))
    n = st["notes"].get(e.id)
    if n and (n.get("items") or n.get("series")):
        out.append(f"YOUR LAST NOTES ({n['date']}):\n" + "\n".join(
            f"  - {x}" for x in (n.get("items") or []) + [f"(long plan) {s}" for s in n.get("series") or []]))
    if led["told"]:
        out.append("TOLD BEFORE:\n" + "\n".join(f"  - {t['date']}: {t['what']}" for t in led["told"]))
    if led["facts"]:
        out.append("ESTABLISHED:\n" + "\n".join(f"  - {t['what']}" for t in led["facts"]))
    if led["open"]:
        out.append("STILL OPEN (set up, not yet paid off):\n" + "\n".join(
            f"  {i + 1}. ({t['planted']}) {t['what']}" if numbered else f"  - ({t['planted']}) {t['what']}"
            for i, t in enumerate(led["open"])))
    return "\n\n".join(out)


def _programme(e: Entry) -> str:
    return (f"THE PROGRAMME: {e.title} ({e.kind}). {e.brief}\n"
            f"THE PLANNER DECIDES: {e.decides or 'nothing nightly: leave notes empty'}"
            + (f"\nITS LONG PLAN DECIDES: {e.series_decides}" if e.series_decides else ""))


def review(world: World, show_id: str, day: str, *, dry: bool = False) -> Review | None:
    """Read one programme's edition and keep what the editor makes of it. None if there was nothing to read, the
    editor couldn't be asked, or its reply won't do."""
    e = SHOWS.get(show_id)
    if e is None or not _on():
        return None
    st = state(world)
    if not dry:
        with world.lock:                              # stamped before the call: a failed review never stays due
            t = st["tried"].setdefault(f"{day}|{show_id}", {"n": 0, "ts": 0.0})
            t["n"], t["ts"] = t["n"] + 1, time.time()
            for key in [k for k in st["tried"] if not _fresh(k.split("|")[0], world.last_date, CATCH_UP_DAYS * 2)]:
                del st["tried"][key]
    plan = _safe(e.digest, world, day) or ""
    if not plan:                                      # nothing booked, or the stand-in: not the planner's work
        log.info("creative editor: %s on %s not reviewed (no plan of its own)", e.title, day)
        if not dry:
            _log(world, e, day, "", "not reviewed: a stand-in, or no plan of its own", False)
        return None
    words, n, kept = _words(world, show_id, day)
    user = (f"{_programme(e)}\n\n" + (h + "\n\n" if (h := _history(world, e)) else "")
            + f"THE PLAN for {day}, as booked:\n{plan}\n\n"
            + (f"WHAT WENT OUT ({n} items):\n{words}" if kept else
               "THE WORDS WERE NOT KEPT: judge the plan alone, and say less."))
    try:
        r = llm.complete_json(TASK, Review, _REVIEW, user, max_tokens=MAX_TOKENS, timeout_s=REVIEW_TIMEOUT_S)
    except llm.LLMError as err:
        _failed(err, f"{e.title}'s review")
        return None
    if bad := safety.check(safety.strings(r)):        # its notes go into planners' prompts
        log.warning("creative editor: %r in %s's review; not kept", bad, e.title)
        return None
    if not dry:
        _apply(world, e, day, r, kept)
    log.info("creative editor: %s on %s: %s — %s%s", e.title, day, r.mark, r.verdict,
             f" | notes: {' / '.join(r.notes)}" if r.notes else "")
    return r


def _log(world: World, e: Entry, day: str, mark: str, verdict: str, words: bool, notes: list | None = None,
         remarks: list | None = None) -> None:
    st = state(world)
    with world.lock:
        st["log"].append({"date": day, "show": e.id, "title": e.title, "kind": e.kind, "mark": mark,
                          "verdict": verdict, "notes": list(notes or []), "remarks": list(remarks or []),
                          "words": words})
        del st["log"][:-KEPT["log"]]


def _apply(world: World, e: Entry, day: str, r: Review, words: bool) -> None:
    st, led = state(world), _ledger(world, e.id)
    with world.lock:
        before = st["notes"].get(e.id) or {}
        held = before.get("series") if _fresh(before.get("date", ""), day) else None
        # The long plan's notes wait for the next arc or route: a later review with none of its own keeps them.
        st["notes"][e.id] = {"date": day, "items": list(r.notes), "series": list(r.series_notes) or list(held or [])}
        gone = {i - 1 for i in r.paid_off if 1 <= i <= len(led["open"])}
        led["open"] = [t for i, t in enumerate(led["open"]) if i not in gone]
        led["open"] += [{"planted": day, "what": p} for p in r.planted]
        led["told"] += [{"date": day, "what": t} for t in r.told]
        led["facts"] += [{"date": day, "what": f} for f in r.established]
        for key in ("told", "facts", "open"):
            del led[key][:-KEPT[key]]
    _log(world, e, day, r.mark, r.verdict, words, r.notes, r.remarks)


# ------------------------------------------------------------------ into the planners' prompts

def for_planner(world: World, show_id: str, *, series: bool = False) -> str:
    """The editor's standing word to a planner, to end its prompt with: "" if there is none. `series` is the long
    plan's (an arc, a route). Never for a live writer: what is in every item's prompt is said in every item."""
    try:
        return _for_planner(world, show_id, series)
    except Exception:  # noqa: BLE001
        log.exception("creative editor: no notes for %s's planner", show_id)
        return ""


def _for_planner(world: World, show_id: str, series: bool) -> str:
    c = world.creative
    if not c:
        return ""
    out = []
    n = (c.get("notes") or {}).get(show_id)
    items = (n.get("series" if series else "items") or []) if n and _fresh(n.get("date", ""), world.last_date) else []
    if items:
        out.append(f"THE CREATIVE EDITOR'S NOTES, after the edition of {n['date']}. Follow them where they touch what "
                   "you are planning:\n" + "\n".join(f"  - {x}" for x in items))
    led = (c.get("ledger") or {}).get(show_id) or {}
    kind = SHOWS[show_id].kind if show_id in SHOWS else next(
        (l.get("kind") for l in reversed(c.get("log") or []) if l["show"] == show_id), "")
    if kind == "fiction" and led.get("open"):
        out.append("STILL OPEN (set up in earlier episodes and not yet paid off: pay one off or move it on when the "
                   "story allows; don't let it drop):\n"
                   + "\n".join(f"  - ({t['planted']}) {t['what']}" for t in led["open"]))
    if kind in ("fiction", "factual") and led.get("facts"):
        out.append("ESTABLISHED in earlier editions (keep to it):\n"
                   + "\n".join(f"  - {t['what']}" for t in led["facts"][-15:]))
    if kind == "factual" and led.get("told"):
        out.append("TOLD BEFORE (not the same again):\n"
                   + "\n".join(f"  - {t['date']}: {t['what']}" for t in led["told"][-12:]))
    return "\n\n" + "\n\n".join(out) if out else ""


# ------------------------------------------------------------------ before air: the vet

def vet(world: World, show_id: str, what: str, plan_text: str, context: str = "", *, started: float | None = None,
        margin: bool = True) -> list[str] | None:
    """The editor's notes on a plan it sends back, or None: it passes, or there is no editor to ask, or no time
    (`started` is the booking's time.monotonic(); `margin` False for a plan made days ahead, by hand)."""
    e = SHOWS.get(show_id)
    if e is None or not e.vetted or not _on():
        return None
    now = schedule.now()
    if margin and e.airs_at and now > _at(e.airs_at, now) - VET_MARGIN_S:
        log.info("creative editor: %s's %s not read: too close to air", e.title, what)
        return None
    if started is not None and time.monotonic() - started > VET_BUDGET_S:
        log.info("creative editor: %s's %s not read: the booking has taken long enough", e.title, what)
        return None
    user = (f"{_programme(e)}\n\n" + (h + "\n\n" if (h := _history(world, e, numbered=False)) else "")
            + (f"WHAT THE PLANNER WAS GIVEN:\n{context.replace(llm.CACHE_BREAK, '')}\n\n" if context else "")
            + f"THE DRAFT {what.upper()}:\n{plan_text}")
    try:
        v = llm.complete_json(TASK, Verdict, _VET.format(what=what), user, max_tokens=MAX_TOKENS,
                              timeout_s=VET_TIMEOUT_S, retries=0)
    except llm.LLMError as err:
        _failed(err, f"{e.title}'s {what}")
        return None
    notes = [n.strip() for n in v.notes if n and n.strip()]
    if v.ok or not notes:
        log.info("creative editor: passed %s's %s", e.title, what)
        return None
    if bad := safety.check(notes):
        log.warning("creative editor: %r in its notes on %s's %s; the plan stands", bad, e.title, what)
        return None
    log.info("creative editor: sent back %s's %s: %s", e.title, what, " / ".join(notes))
    return notes


def redraft(world: World, show_id: str, what: str, first, *, text: Callable, again: Callable,
            check: Callable | None = None, context: str = "", started: float | None = None, margin: bool = True):
    """A planner's plan, vetted: `first` if the editor passes it (or can't be asked), else the planner's second
    draft with the editor's notes (`again(more)`, `more` to add to its prompt), once. A second draft that can't be
    made or fails the planner's own `check` gives way to the first, which passed it: never to the stand-in."""
    try:
        notes = vet(world, show_id, what, text(first), context, started=started, margin=margin)
    except Exception:  # noqa: BLE001
        log.exception("creative editor: could not read %s's %s; it stands", show_id, what)
        return first
    if not notes:
        return first
    title = SHOWS[show_id].title
    try:
        second = again(SENT_BACK.format(what=what, plan=text(first), notes="\n".join(f"  - {n}" for n in notes)))
        if check is not None:
            check(second)
        took = "second"
    except llm.LLMError as e:
        log.warning("creative editor: %s's second %s won't do (%s); the first stands", title, what, str(e)[:200])
        second, took = first, "first"
    except Exception:  # noqa: BLE001
        log.exception("creative editor: %s's second %s failed; the first stands", title, what)
        second, took = first, "first"
    st = state(world)
    with world.lock:
        st["vets"].append({"date": world.last_date, "show": show_id, "what": what, "notes": notes, "took": took})
        del st["vets"][:-KEPT["vets"]]
    return second


# ------------------------------------------------------------------ for the owner's morning read

def report(world: World) -> str:
    """Each programme's latest mark, notes, remarks and ledger, and the plans sent back."""
    st = state(world)
    shows = list(dict.fromkeys(l["show"] for l in st["log"]))
    out = []
    for sid in shows:
        logs = [l for l in st["log"] if l["show"] == sid]
        last = next((l for l in reversed(logs) if l.get("mark")), logs[-1])
        out.append(f"{last.get('title', sid).upper()}  ({last['date']}: {last.get('mark') or 'not reviewed'})")
        out.append(f"  {last['verdict']}")
        n = st["notes"].get(sid) or {}
        out += [f"  note: {x}" for x in n.get("items") or []] + [f"  long plan: {x}" for x in n.get("series") or []]
        out += [f"  for you: {x}" for l in logs[-3:] for x in l.get("remarks") or []]
        led = st["ledger"].get(sid) or {}
        out += [f"  still open ({t['planted']}): {t['what']}" for t in led.get("open") or []]
        if led.get("facts"):
            out.append(f"  established: {len(led['facts'])} kept; the last: {led['facts'][-1]['what']}")
        if led.get("told"):
            out.append(f"  told: {len(led['told'])} kept; the last: {led['told'][-1]['what']}")
        marks = " ".join(f"{l['date'][5:]}:{l.get('mark') or '-'}" for l in logs[-8:])
        out.append(f"  marks: {marks}\n")
    for v in st["vets"][-8:]:
        out.append(f"sent back {v['date']} {v['show']} {v['what']} (the {v['took']} aired): {' / '.join(v['notes'])}")
    return "\n".join(out) or "The creative editor has reviewed nothing yet."


def _cli(argv: list[str]) -> int:
    import argparse

    import entertainment
    from newsroom import world as world_mod

    ap = argparse.ArgumentParser(prog="python -m entertainment.creative")
    ap.add_argument("cmd", choices=["notes", "review"])
    ap.add_argument("--dry", action="store_true", help="review: print it without keeping or saving it")
    ap.add_argument("--date", help="review: the night to read (default: the latest it aired)")
    ap.add_argument("--show", help="review: one programme's id (default: every one enrolled)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "openai", "urllib3", "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    print(f"world: {CONFIG.paths.world}")
    entertainment.use()                               # the programmes enrol themselves
    w = world_mod.load()
    if a.cmd == "notes":
        print(report(w))
        return 0
    done = 0
    for e in [SHOWS[a.show]] if a.show in SHOWS else list(SHOWS.values()):
        day = a.date or next(iter(_aired_days(w, e)[-1:]), None)
        if not day:
            print(f"{e.title}: nothing aired to read")
            continue
        r = review(w, e.id, day, dry=a.dry)
        print(f"\n{e.title} on {day}:\n" + (r.model_dump_json(indent=2) if r else "  (no review)"))
        done += bool(r)
    if done and not a.dry:
        world_mod.save(w)
    return 0 if done else 1


if __name__ == "__main__":
    import sys

    raise SystemExit(_cli(sys.argv[1:]))
