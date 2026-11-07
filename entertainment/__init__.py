"""Port Wexley's second channel: entertainment, sharing the town, its world.json and its people with
Channel 7 (docs/ENGINE.md). `python -m newsroom --channel entertainment` puts it out instead.

The engine is newsroom/'s; this package brings the channel's own day and shows and plugs them in
through the engine's registries (writers.SHOW_SYSTEMS and the hooks beside it, workers.IDLE_JOBS,
scenes.SHOW_SETS, player.SEATS), so newsroom/ never imports it. For now the day has one show built,
Wexley Wits at 20:00 (wits.py, quiz.py); the other hours are the overnight test card, which still
shows Channel 7's ident and repeats until the channel has a bank of its own to fill them.
"""
from __future__ import annotations

import random

# The channel's day: (start, show id), as schedule.SCHEDULE. One episode a night: two Wits slots back
# to back would run as one show (schedule.show_end looks for a different id).
SCHEDULE: tuple[tuple[int | str, str], ...] = (
    (0, "overnight"),
    (20, "wits"),
    ("20:30", "overnight"),
)


def use():
    """Put out the entertainment channel instead of Channel 7, from now. Returns an undo (for the tests)."""
    from newsroom import assets, locations, player, scenes, schedule, workers, writers

    from . import quiz, wits

    saved = (schedule.SCHEDULE, dict(schedule.SHOWS), dict(locations.MARKS), dict(assets.IDENTS),
             list(workers.IDLE_JOBS), dict(writers._PLACE))
    schedule.SCHEDULE = SCHEDULE
    schedule.SHOWS[quiz.SHOW] = wits.SHOW
    locations.MARKS[wits.SET] = wits.MARKS
    scenes.SHOW_SETS[quiz.SHOW] = wits.SET
    player.SEATS[quiz.SHOW] = 4
    assets.IDENTS[quiz.SHOW] = (assets.CONFIG.paths.assets / "bumper_wits.wav", wits.IDENT)
    workers.IDLE_JOBS.append((quiz.should_commission, quiz.commission))
    writers.SHOW_SYSTEMS[quiz.SHOW] = wits.SYSTEMS
    writers._PLACE.update(wits.PLACE)
    writers.BRIEF_HOOKS[quiz.SHOW] = quiz.brief_for
    writers.PROMPT_HOOKS[quiz.SHOW] = quiz.for_prompt
    writers.SEAT_HOOKS[quiz.SHOW] = quiz.seats
    writers.CAPTION_HOOKS[quiz.SHOW] = quiz.caption
    writers.TEMPLATE_HOOKS[quiz.SHOW] = template
    writers.BOOKED_SHOWS.add(quiz.SHOW)
    writers.DEBATE_SHOWS.add(quiz.SHOW)
    writers.UNFILED_SHOWS.add(quiz.SHOW)

    def undo() -> None:
        schedule.SCHEDULE = saved[0]
        schedule.SHOWS.clear(), schedule.SHOWS.update(saved[1])
        locations.MARKS.clear(), locations.MARKS.update(saved[2])
        assets.IDENTS.clear(), assets.IDENTS.update(saved[3])
        workers.IDLE_JOBS[:] = saved[4]
        writers._PLACE.clear(), writers._PLACE.update(saved[5])
        for reg in (scenes.SHOW_SETS, player.SEATS, writers.SHOW_SYSTEMS, writers.BRIEF_HOOKS, writers.PROMPT_HOOKS,
                    writers.SEAT_HOOKS, writers.CAPTION_HOOKS, writers.TEMPLATE_HOOKS):
            reg.pop(quiz.SHOW, None)
        for reg in (writers.BOOKED_SHOWS, writers.DEBATE_SHOWS, writers.UNFILED_SHOWS):
            reg.discard(quiz.SHOW)
    return undo


_RIGHT = ("That's right!", "Correct!", "Yes! Two points.", "Spot on.")
_WRONG = ("Ooh, no, I'm afraid not.", "Not quite.", "Sorry, no.")


def template(seg_type, world, rng: random.Random, part: str, work: dict, brief: str):
    """Wexley Wits with no model: still tonight's questions, answers and score, from the booking."""
    from newsroom.models import BulletinScript, LiveLine, PanelLine, PanelScript, SegmentType as T

    from . import quiz

    q = quiz.booked(world)
    teams = q["teams"]
    if seg_type is T.links:
        return BulletinScript(lines=[
            LiveLine(speaker="mag_b", text=f"Good evening, and welcome to Wexley Wits, live from {q['venue']}!"),
            LiveLine(speaker="mag_b", text=f"Tonight {teams[0]['name']}, {' and '.join(teams[0]['members'])}, "
                                           f"take on {teams[1]['name']}, {' and '.join(teams[1]['members'])}."),
            LiveLine(speaker="mag_b", text="Two points for your own question, one for a bonus. Let's play!")],
            headline=f"Wexley Wits: {teams[0]['name']} against {teams[1]['name']}", lower_third="Wexley Wits")
    if seg_type is not T.interview:
        return None
    n = next((int(k[1]) - 1 for k in ("r1", "r2", "r3", "r4") if "{" + k + "}" in brief), None)
    lines: list = []
    if n is not None:
        r = q["rounds"][n]
        said = f"Round {n + 1}: {r['title']}."         # Clive's verdict shares a line with what he says next
        for x in r["questions"]:
            lines.append(PanelLine(speaker="mag_b", text=f"{said} {teams[x['to']]['name']}: {x['q']}"))
            lines.append(PanelLine(speaker="guest", guest_name=x["who"],
                                   text=x["a"].capitalize() + "?" if x["right"] else "I'll have to guess. Pass."))
            if not x["right"] and x["stolen"]:
                lines.append(PanelLine(speaker="guest", guest_name=x["bonus_who"], text=x["a"].capitalize() + "!"))
            said = rng.choice(_RIGHT) if x["right"] or x["stolen"] else f"{rng.choice(_WRONG)} It was {x['a']}."
        s = r["scores_after"]
        lines.append(PanelLine(speaker="mag_b", text=f"{said} So after round {n + 1}: {teams[0]['name']} {s[0]}, "
                                                    f"{teams[1]['name']} {s[1]}."))
        head = f"Round {n + 1}: {r['title']}"
    elif part == "close":
        s = q["final"]
        w = teams[q["winner"]]
        lines = [PanelLine(speaker="mag_b", text=f"And the final score: {teams[0]['name']} {s[0]}, "
                                                 f"{teams[1]['name']} {s[1]}. {w['name']} win!"),
                 PanelLine(speaker="guest", guest_name=w["members"][0], text="Drinks are on us. Well, on him."),
                 PanelLine(speaker="guest", guest_name=w["members"][1], text="Steady on."),
                 PanelLine(speaker="mag_b", text="That's Wexley Wits. Goodnight!")]
        head = f"{w['name']} win Wexley Wits"
    else:
        t = teams[rng.randrange(2)]
        lines = [PanelLine(speaker="mag_b", text=f"Before the result, a word with {t['members'][0]}. How's the season?"),
                 PanelLine(speaker="guest", guest_name=t["members"][0], text="Up and down, Clive. Like the darts."),
                 PanelLine(speaker="guest", guest_name=t["members"][1], text="Mostly down."),
                 PanelLine(speaker="mag_b", text="Honest, at least!")]
        head = f"A word with {t['name']}"
    return PanelScript(lines=lines[:24], headline=head, lower_third="Wexley Wits",
                       guest_name=next((l.guest_name for l in lines if l.speaker == "guest"), None))
