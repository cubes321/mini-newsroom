"""The week in review on Sundays, and the year's on New Year's Eve, in the documentary's slot.

On a Sunday the nightly documentary is THE WEEK IN PORT WEXLEY: Miles Okafor looks back at the
week's stories from where they happened. On 31 December it is THE YEAR IN PORT WEXLEY, with Hugh
Tremayne, who tells the year as he tells the town's history. Both are documentaries in every other
way (documentary.py, special.py): commissioned in idle time from six, made in stages between live
slots, trailed, aired at nine and repeated overnight.

What differs is where the facts come from. Nobody is asked to choose a subject, and the research is
not a model's reading of the archive: the notes are put together in code from the annals (annals.py),
a page a day, plus today's page read live. So the review can only say what the station reported:

- the timeline is the main stories' first headline of the span and where each stood at the end;
- the details are the scores, full council's votes and its promises, the fish auction, the quiz;
- "still open" is what each story has due next, to end on;
- the archive clips are the days' keepsakes, the annals' own copies of the audio.

The producer (the outline) and the section writers are the documentary's, with a review's
instructions: one section a story, a lighter one for the rest of the week, nothing new happens.

A week needs MIN_PAGES days on the page, or Sunday has an ordinary documentary. `[documentary]
week_review` and `year_review` switch them off. To try one on any day:

    python -m newsroom --scratch --review week      # commissioned at the first idle moment
    python -m newsroom.review week                  # the research notes, and nothing else (no model)
"""
from __future__ import annotations

import logging
import os
from datetime import date, timedelta

from . import annals
from .config import CONFIG
from .models import DocumentaryCommission, DocumentaryResearch, Segment, Stakeholder, TimelineEntry
from .world import World

log = logging.getLogger(__name__)

WEEK, YEAR = "week", "year"
KINDS = (WEEK, YEAR)
STRANDS = {WEEK: "THE WEEK IN PORT WEXLEY", YEAR: "THE YEAR IN PORT WEXLEY"}
MIN_PAGES = {WEEK: 3, YEAR: 14}
TOP = {WEEK: 7, YEAR: 9}           # the stories a review is built on
ENV = "NEWSROOM_REVIEW"            # "week" or "year": tonight's documentary is that review, whatever the day

OUTLINE_SYSTEM = """\
You are the producer of {strand}, a fifteen-minute look back at the {span} on a small-town TV station
in the FICTIONAL town in the briefing. The presenter is {presenter_is} (speaker id "{presenter}"), on
location; the anchor (speaker id "anchor") introduces and closes it from the studio. Plan 6 to 8
sections: an opening that sets the mood of the {span}; then a section for each of the main stories in
the research notes, the biggest or the earliest first; one lighter section for the rest of it (the
sport, the weather, the quiz, the oddities under Details); and an ending that looks ahead from Still
open. Each section has a heading, the beats it establishes, a backdrop from the allowed list (the place
its story happened; vary them), and optionally one person from the notes to hear from, looking back on
their own {span}. The research notes are everything that happened: a review reports nothing new, and
nothing in Still open has happened yet. If ARCHIVE CLIPS are listed, place up to three, one per section,
by their id in archive_clip, each in the section of its own story. The title is the {span} in a phrase
of the town's own ("{example}"). Warm, local, specific, a little dry. Everything is fiction. Return
ONLY JSON.
"""

SECTION_RULE = """ THIS IS A LOOK BACK at the {span}: everything in it has been reported already, on the
days the notes give. Tell it in the past tense, by its day ("on Tuesday"); add no new development, no new
decision and no new number; a guest remembers and reflects, and announces nothing."""


def _today(world: World) -> date:
    return date.fromisoformat(world.last_date)


def window(kind: str, today: date) -> tuple[date, date]:
    """The days a review covers: Monday to tonight, or the first of January to tonight."""
    return (today - timedelta(days=6) if kind == WEEK else date(today.year, 1, 1)), today


def pages(world: World, kind: str, today: date | None = None) -> list[dict]:
    """The annals' pages for the span, and today's read live from the world (its keepsakes still in
    the cache), the oldest first."""
    today = today or _today(world)
    first, last = window(kind, today)
    kept = annals.span(first, last - timedelta(days=1))
    live = annals.digest(world, last)
    return kept + ([live] if live["pieces"] else [])


def tonight(world: World, today: date | None = None) -> str | None:
    """The review tonight's documentary slot carries, if any: the year's on New Year's Eve, the week's
    on a Sunday, when it is switched on and there are pages enough to make one."""
    today = today or _today(world)
    cfg = CONFIG.documentary
    forced = os.environ.get(ENV, "").strip().lower()
    if forced in KINDS:
        kind = forced
    elif (today.month, today.day) == (12, 31) and cfg.year_review:
        kind = YEAR
    elif today.weekday() == 6 and cfg.week_review:
        kind = WEEK
    else:
        return None
    have = len(pages(world, kind, today))
    if have < (1 if forced in KINDS else MIN_PAGES[kind]):
        log.info("review: only %d day(s) on the page for the %s; an ordinary documentary tonight", have, kind)
        return None
    return kind


def strand_tonight(world: World, today: date | None = None) -> str:
    """What the nine o'clock slot is called tonight, for the programme card."""
    kind = tonight(world, today)
    return STRANDS[kind] if kind else CONFIG.documentary.title


def commission(world: World, kind: str) -> Segment:
    """Tonight's review, as a documentary to make: no editor is asked."""
    from . import documentary

    today = _today(world)
    world.last_documentary_date = world.last_date      # tonight's slot is taken
    title = f"The Week to {today:%A} {today.day} {today:%B}" if kind == WEEK else f"Port Wexley in {today.year}"
    angle = ("What happened in Port Wexley this week, and what it leaves for the next." if kind == WEEK else
             f"What {today.year} was for Port Wexley: the stories that ran, how they ended, and what is carried over.")
    seg = documentary.commission(world, DocumentaryCommission(subject="history", working_title=title, angle=angle))
    seg.work.update(subject=kind, strand=STRANDS[kind])
    log.info("review: tonight is %s (%s)", STRANDS[kind].title(), title)
    return seg


def is_review(seg: Segment) -> bool:
    return seg.work.get("subject") in KINDS


def prompt_vars(seg: Segment) -> dict:
    kind = seg.work.get("subject")
    return {"span": kind, "example": "Frost, a Petition and a Slow Clock" if kind == WEEK
            else "The Year the Harbour Wall Came Down"}


# ------------------------------------------------------------------ research


def _day(iso: str) -> str:
    d = date.fromisoformat(iso)
    return f"{d:%A} {d.day} {d:%B}"


def stories(ps: list[dict]) -> list[dict]:
    """The span's stories from its pages, the most covered first: {thread_id, title, pieces, days,
    first, last, status, phase, people, next, beats: [(date, headline)]}."""
    by: dict[str, dict] = {}
    for p in ps:
        for s in p.get("stories", []):
            a = by.setdefault(s["thread_id"], {"thread_id": s["thread_id"], "pieces": 0, "days": 0, "beats": [],
                                              "first": p["date"], "people": []})
            a.update(title=s["title"], status=s.get("status", ""), phase=s.get("phase", ""), next=s.get("next", ""),
                     last=p["date"])
            a["pieces"] += s.get("pieces", 0)
            a["days"] += 1
            a["beats"] += [(p["date"], h) for h in s.get("beats", []) if h not in {b[1] for b in a["beats"]}]
            a["people"] += [n for n in s.get("people", []) if n not in a["people"]]
    return sorted(by.values(), key=lambda a: (-a["pieces"], -a["days"], a["first"]))


def _fit(text: str, n: int = 230) -> str:
    """A detail cut at a clause, not inside a figure: "…; mackerel £2.4" tells a writer the wrong price."""
    text = text.strip()
    if len(text) <= n:
        return text
    cut = max(text.rfind("; ", 0, n), text.rfind(", ", 0, n))
    return text[:cut if cut > n // 2 else n].rstrip(" ,;")


def _details(ps: list[dict], kind: str, told: int) -> list[str]:
    """The rest of the span, in a line each: the newest first of each sort, eight at most."""
    out: list[str] = []
    carried = [(p["date"], m) for p in ps for m in p.get("council", [])]
    if carried:
        won = sum(1 for _, m in carried if m["carried"])
        day, m = carried[-1]
        out.append(f"Full council voted on {len(carried)} motions ({won} carried, {len(carried) - won} lost); on "
                   f"{_day(day)}: \"{m['motion'][:120]}\" {m['for']}-{m['against']}, "
                   f"{'carried' if m['carried'] else 'lost'}")
    settled = [s for p in ps for s in p.get("settled", [])]
    if settled:
        kept = sum(1 for s in settled if s["state"] == "kept")
        s = settled[-1]
        out.append(f"Council promises: {kept} kept and {len(settled) - kept} broken; the latest {s['state']}: "
                   f"\"{s['text'][:110]}\"" + (f" ({s['note'][:60]})" if s.get("note") else ""))
    sport = [(p["date"], line) for p in ps for line in p.get("sport", [])]
    out += [_fit(f"Sport, {_day(d)}: {line}") for d, line in sport[-3:]]
    for key, label in (("quiz", "The pub quiz: "), ("auction", "")):       # the auction's line names and dates itself
        last = next((p[key] for p in reversed(ps) if p.get(key)), None)
        if last:
            out.append(_fit(f"{label}{last}"))
    docs = [t for p in ps for t in p.get("documentaries", [])]
    if docs:
        out.append("Documentaries shown: " + "; ".join(docs[-4:])[:200])
    opened, closed = sum(len(p.get("opened", [])) for p in ps), sum(len(p.get("closed", [])) for p in ps)
    pieces = sum(p.get("pieces", 0) for p in ps)
    out.append(f"The {kind} on Channel 7: {pieces} pieces on air over {len(ps)} days; {opened} stories opened, "
               f"{closed} closed; {told} are told here")
    weather = [(p["date"], p["weather"]) for p in ps if p.get("weather")]
    if weather:
        out.append(f"The weather, {_day(weather[-1][0])}: {weather[-1][1]}"[:200])
    return out[:8]


def notes(world: World, kind: str, today: date | None = None) -> tuple[DocumentaryResearch, list[dict]]:
    """The research notes and the archive clips for a review, from the annals: no model."""
    ps = pages(world, kind, today)
    top = stories(ps)[:TOP[kind]]
    firsts, lasts = [], []
    for s in top:
        d0, h0 = s["beats"][0] if s["beats"] else (s["first"], s["title"])
        same = h0.strip().lower() == s["title"].strip().lower()        # a story is often named by its first headline
        firsts.append((d0, s["title"] if same else f"{s['title']}: {h0}"))
        if s["status"] and (s["days"] > 1 or len(s["beats"]) > 1):
            where = {"closed": "closed", "resolving": "being settled", "faded": "gone quiet"}.get(s["phase"], "still running")
            lasts.append((s["last"], f"{s['title']}, {where}: {s['status']}"))
    rows = (firsts + lasts)[:14]                      # every story's start before any story's end
    timeline = [TimelineEntry(date=_day(d), event=e[:300], on_record=True) for d, e in sorted(rows, key=lambda r: r[0])]
    if not timeline:
        timeline = [TimelineEntry(date=_day(ps[-1]["date"]) if ps else "", event="A quiet stretch: no running story",
                                  on_record=True)]
    people, seen = [], set()
    for s in top:
        for name in s["people"][:2]:
            if name in seen or len(people) >= 8:
                continue
            seen.add(name)
            p = world.person_by_name(name)
            people.append(Stakeholder(name=name[:40], role=(p.role if p else "resident")[:60],
                                      stance=f"in the story of {s['title']}: {s['status']}"))
    questions = [f"{s['title']}: expected next, {s['next']}"[:300] for s in top
                 if s.get("next") and s["phase"] not in ("closed", "faded")][:5]
    research = DocumentaryResearch(timeline=timeline, people=people, details=_details(ps, kind, len(top)),
                                   questions=questions)
    mine = {s["thread_id"] for s in top}
    clips: list[dict] = []
    for p in reversed(ps):                            # the newest pages first
        for c in p.get("clips", []):
            wav = c["wav"] if os.path.isabs(c["wav"]) else str(annals.clips_dir() / c["wav"])
            story = c.get("story", "")
            if len(clips) >= 8 or not os.path.exists(wav):
                continue
            if story not in mine and not story.startswith("x"):      # a story the review doesn't tell
                continue
            if kind == WEEK and any(k["story"] == story and k["date"] != c["date"] for k in clips):
                continue                              # one keepsake a story in a week: its latest
            clips.append({**c, "wav": wav, "id": f"C{len(clips) + 1}"})
    return research, clips


def research(seg: Segment, world: World) -> DocumentaryResearch:
    """The documentary's research stage, for a review (documentary.research hands over to it)."""
    kind = seg.work["subject"]
    out, seg.work["clips"] = notes(world, kind)
    first, last = window(kind, _today(world))
    log.info("review %r researched from the annals (%s to %s): %d timeline entries, %d details, %d clips",
             seg.headline, first.isoformat(), last.isoformat(), len(out.timeline), len(out.details),
             len(seg.work["clips"]))
    return out


def main(argv: list[str] | None = None) -> int:
    import sys

    from . import documentary, world as world_mod

    args = sys.argv[1:] if argv is None else argv
    kind = args[0] if args and args[0] in KINDS else WEEK
    w = world_mod.load()
    ps = pages(w, kind)
    first, last = window(kind, _today(w))
    print(f"{STRANDS[kind]}: {first.isoformat()} to {last.isoformat()}, {len(ps)} day(s) on the page "
          f"(needs {MIN_PAGES[kind]}); tonight: {tonight(w) or 'an ordinary documentary'}")
    if not ps:
        return 0
    out, clips = notes(w, kind)
    seg = Segment(slot_id=0, type="documentary", work={"research": out.model_dump(), "clips": clips})
    print(documentary.notes_for_prompt(seg))
    print(documentary.clips_for_prompt(seg) or "(no archive clips)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
