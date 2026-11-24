"""Channel 8's TV movie, 21:00 to 22:30 (docs/ENGINE.md "The TV movie"; the user, 2026-11-23): a film from the bank
(movies.py), written, approved, cast and voiced ahead, played out whole.

- **Which film:** schedule.ROTATIONS for the 21:00 slot. Of the films fit to air (approved, finished, voiced for the
  script and cast as they stand, every clip on disk, and long enough to fill the slot), the one aired longest ago,
  never-aired first, ties drawn on the day; the night's pick is kept in the world's bank_aired ("movie-<slug>"), so
  a restart gets the same film and a scratch run's nights stay with its copy of the town. No film fit to air: the
  slot is the closedown, as it was before the movie.
- **Each film is a show of its own** ("movie-<slug>"), registered the first time it's picked, so asking about
  tomorrow's film (a programme card) never changes tonight's: its ident, its cast's pins, its order.
- **The order:** the announcer's ident ("Now on Channel 8, tonight's film: ..."), the titles, every scene with an
  ad break at each act's end, the credits; then adverts until it's time to close, and a short break to close on.
  Every item's target is its voiced length, and the breaks share what the slot has left (BREAK_MIN_S to
  BREAK_MAX_S each). The order is whole (Show.whole_order): a film that starts late, or runs over, is never cut.
- **The items are made ahead** (workers.READY_HOOKS): a scene is its voiced lines from segments.json, the titles and
  credits are movie_cards'; the ident and the breaks are the station's own.
- **Too short:** a film that would leave more than the breaks can fill (The Last Lot, 57 minutes with its cards) is
  held out until the slot has a filler (borrowed news from Channel 7 was the user's thought, 2026-11-23).
"""
from __future__ import annotations

import logging
import random
import threading
from datetime import date, timedelta
from pathlib import Path

from newsroom import schedule
from newsroom.models import SegmentType as T
from newsroom.schedule import Item as I, Show

from . import movie_cards, movies

log = logging.getLogger(__name__)

SLOT = movies.SHOW                  # the 21:00 entry in Channel 8's SCHEDULE
SLOT_S = 90 * 60                    # 21:00 to 22:30
BREAKS = movies.ACTS - 1            # one at each act's end
BREAK_MIN_S, BREAK_MAX_S = 60.0, 240.0      # two adverts at least (adverts.BREAK_ADS), eight at most
IDENT_S = 12.0                      # the announcer over Channel 8's ident, about
FILL_S = 60.0                       # adverts after the credits, while there's time before 22:30
CLOSING_S = 60.0                    # the break the slot closes on
SLACK_S = 120.0                     # a film may leave this much for the fill, past full breaks
REST_DAYS = 7                       # as the content bank's: a film doesn't come back within a week if another can air
COLOUR = (70, 50, 96)
IDENT_TEXT = "Now on Channel 8, tonight's film: {title}."

_lock = threading.RLock()
_picked: dict[str, str | None] = {}         # day -> the film's slug (None: nothing fit to air)
_films: dict[str, dict] = {}                # slug -> its folder, film, cast, scenes and show, once registered
_undo: list = []


def show_id(slug: str) -> str:
    return f"{SLOT}-{slug}"


def _cards_s() -> tuple[float, float]:
    p = movie_cards._pass_s()
    return p, 2 * p


def running_s(scenes: list[dict]) -> float:
    """The film as it airs without its breaks: the ident, the titles, every scene, the credits."""
    titles, credits = _cards_s()
    return IDENT_S + titles + credits + sum(l.get("duration_s") or 0.0 for s in scenes for l in s["lines"])


def fills(scenes: list[dict]) -> bool:
    """Long enough that full breaks leave no more than SLACK_S of adverts before the close."""
    return running_s(scenes) + BREAKS * BREAK_MAX_S + CLOSING_S >= SLOT_S - SLACK_S


def fit_to_air(bank: Path | None = None) -> dict[str, tuple[Path, dict, list[dict]]]:
    """slug -> (folder, film, voiced scenes), for every film the slot can air tonight."""
    out = {}
    for folder, film in movies.films(bank):
        scenes = movies.voiced(folder)
        if scenes is None:
            continue
        if not fills(scenes):
            log.info("movie: %s is %.0f minutes with its cards, too short for the slot without a filler",
                     folder.name, running_s(scenes) / 60)
            continue
        out[folder.name] = (folder, film, scenes)
    return out


def tonight(day: date) -> str | None:
    """The film for `day`'s slot, picked once and kept in the world (bank_aired)."""
    from newsroom import world as world_mod

    d = day.isoformat()
    with _lock:
        if d in _picked:
            return _picked[d]
        choices = fit_to_air()
        w = world_mod.current()
        slug = None
        if choices:
            aired = {}
            for s in choices:
                with w.lock if w else _lock:
                    aired[s] = max(w.bank_aired.get(show_id(s), [""])) if w else ""
            held = [s for s in choices if aired[s] == d]                 # already tonight's (a restart)
            if held:
                slug = held[0]
            else:
                rested = (day - timedelta(days=REST_DAYS)).isoformat()
                fresh = sorted(s for s in choices if aired[s] < rested) or sorted(choices)
                random.Random(f"movie-{d}").shuffle(fresh)
                slug = min(fresh, key=lambda s: aired[s])
                if w is not None:
                    with w.lock:
                        w.bank_aired[show_id(slug)] = (w.bank_aired.get(show_id(slug), []) + [d])[-20:]
            _register(slug, *choices[slug])
            log.info("movie: %s for %s", slug, d)
        if w is not None:                     # before the world is loaded (the log line at start-up), no promise kept
            _picked[d] = slug
        return slug


def _due(world, now: float | None = None) -> bool:
    """workers.IDLE_JOBS: tonight's film not yet picked (it reads every film's voicing, about a fifth of a second:
    better in an idle moment than in the middle of a frame)."""
    return date.fromtimestamp(now or schedule.now()).isoformat() not in _picked


def _pick_now(world) -> None:
    tonight(date.fromtimestamp(schedule.now()))


def rotation(day: date) -> str:
    """schedule.ROTATIONS for the 21:00 slot: tonight's film's show, or the closedown if no film is fit to air."""
    slug = tonight(day)
    return show_id(slug) if slug else "closedown"


# ------------------------------------------------------------------ the film's show

def show_for(slug: str, film: dict, scenes: list[dict]) -> Show:
    title = film["outline"]["title"]
    rows = movies._live_rows(film)                       # the scenes still in it, in the order segments.json has them
    acts = [k.split(".")[0] for k, _ in rows]
    titles_s, credits_s = _cards_s()
    lengths = [sum(l.get("duration_s") or 0.0 for l in s["lines"]) for s in scenes]
    spare = SLOT_S - running_s(scenes) - CLOSING_S
    gap = min(BREAK_MAX_S, max(BREAK_MIN_S, spare / BREAKS))
    order: list = [I(T.bumper, brief="ident", target_s=IDENT_S), I(T.bumper, brief="titles", target_s=titles_s)]
    for i, (s, n) in enumerate(zip(scenes, lengths)):
        order.append(I(T.interview, brief=f"scene {s['number']}", target_s=n))
        if i + 1 < len(scenes) and acts[i + 1] != acts[i]:
            order.append(I(T.ad_break, brief="break", target_s=gap))
    order += [I(T.bumper, brief="credits", target_s=credits_s), I(T.ad_break, brief="fill", target_s=FILL_S)]
    return Show(
        show_id(slug), title.upper(), "FILM", COLOUR,
        pattern=tuple(order),
        loop_from=len(order) - 1,                         # adverts after the credits, until it's time to close
        whole_order=True,                                 # every scene airs, however late it started
        closing=(I(T.ad_break, brief="close", target_s=CLOSING_S),),
        target_s={T.bumper: IDENT_S, T.interview: movies.SCENE_S, T.ad_break: 60.0},
        cast=("guest",), lead="guest", cast_by_type={T.interview: ("guest",)},
        station=f"{title}, tonight's film on Channel 8, Port Wexley's second channel",
        tone=film["outline"].get("tone", ""), light=False, repeats_overnight=False,
    )


def _register(slug: str, folder: Path, film: dict, scenes: list[dict]) -> None:
    """The film's show on the engine, once: its order, its cast's voices and looks, its ident, its made-ahead items."""
    if slug in _films:
        return
    from newsroom import assets, continuity, player, workers, writers

    from . import quiz

    sid, cast = show_id(slug), movies.load_cast(folder)
    schedule.SHOWS[sid] = show_for(slug, film, scenes)
    _undo.append(movies.pin(cast))
    player.SEATS[sid] = 3
    player.BARE_SHOWS.add(sid)
    player.VIEW_HOOKS[sid] = movies._view
    workers.READY_HOOKS[sid] = fill
    writers.FICTION_SHOWS.add(sid)                        # the archive keeps only that it aired, never its words
    writers.UNFILED_SHOWS.add(sid)                        # never news
    assets.IDENTS[sid] = (folder / "ident.wav", IDENT_TEXT.format(title=film["outline"]["title"]))
    assets.IDENT_MUSIC[sid] = quiz.SHOW                   # Channel 8's own tune, as the closedown's
    assets.IDENT_VOICES[sid] = continuity.VOICE           # the continuity announcer
    _films[slug] = {"folder": folder, "film": film, "cast": cast, "scenes": {s["number"]: s for s in scenes},
                    "first": scenes[0], "sets": list(dict.fromkeys(s["set"] for s in scenes))}

    def undo() -> None:
        schedule.SHOWS.pop(sid, None)
        for reg in (player.SEATS, player.VIEW_HOOKS, workers.READY_HOOKS, assets.IDENTS, assets.IDENT_MUSIC,
                    assets.IDENT_VOICES):
            reg.pop(sid, None)
        for reg in (player.BARE_SHOWS, writers.FICTION_SHOWS, writers.UNFILED_SHOWS):
            reg.discard(sid)
    _undo.append(undo)


def fill(seg, world):
    """workers.READY_HOOKS: a scene, the titles or the credits, made from the film as voiced; None for the ident and
    the breaks, which the station makes as usual."""
    from newsroom.models import Line, SegmentState

    slug = seg.show[len(SLOT) + 1:]
    f = _films.get(slug)
    kind = seg.brief or ""
    if f is None or kind in ("ident", "break", "fill", "close"):
        return None
    title = f["film"]["outline"]["title"]
    if kind == "titles":
        made = movie_cards.titles_segment(seg.slot_id, seg.show, title, f["first"])
    elif kind == "credits":
        made = movie_cards.credits_segment(seg.slot_id, seg.show, title, f["cast"], f["sets"])
    elif kind.startswith("scene "):
        sc = f["scenes"][int(kind.split()[1])]
        made = movies.scene_segment(seg.slot_id, sc, [Line.model_validate(d) for d in sc["lines"]])
        made.headline = f"{title}, scene {sc['number']}"
    else:
        return None
    seg.lines, seg.headline = made.lines, made.headline
    seg.work = {**seg.work, **made.work}
    seg.state = SegmentState.ready
    return seg


# ------------------------------------------------------------------ on the channel

def register():
    """The 21:00 slot on Channel 8 (entertainment.use): the film's show, the rotation that picks the night's film, and
    a stand-in under the slot's own id for anything that asks for it by name. Returns an undo."""
    from newsroom import workers

    undo_install = movies.install()
    schedule.ROTATIONS[SLOT] = rotation
    job = (_due, _pick_now)
    workers.IDLE_JOBS.append(job)
    schedule.SHOWS[SLOT] = Show(SLOT, "THE CHANNEL 8 FILM", "FILM", COLOUR, pattern=(T.bumper, T.testcard),
                                loop_from=1, target_s={T.bumper: IDENT_S, T.testcard: 300.0},
                                repeats_overnight=False)

    def undo() -> None:
        with _lock:
            for u in reversed(_undo):
                u()
            _undo.clear()
            _films.clear()
            _picked.clear()
        schedule.ROTATIONS.pop(SLOT, None)
        schedule.SHOWS.pop(SLOT, None)
        if job in workers.IDLE_JOBS:
            workers.IDLE_JOBS.remove(job)
        undo_install()
    return undo
