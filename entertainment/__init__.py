"""Channel 8, Port Wexley's second channel: entertainment, sharing the town, its world.json and its people with
Channel 7 (docs/ENGINE.md); both are WTV's, Wexley Television's (the user named them, 2026-11-13).
`python -m newsroom --channel entertainment` puts it out instead.

The engine is newsroom/'s; this package brings the channel's own day and shows and plugs them in
through the engine's registries (writers.SHOW_SYSTEMS and the hooks beside it, workers.IDLE_JOBS,
scenes.SHOW_SETS, player.SEATS), so newsroom/ never imports it. The evening is The Kettle's On at 19:00
(kettle.py) and Wexley Wits at 20:00 (wits.py, quiz.py); then the closedown: the announcer's goodnight once and
the test card until seven the next evening, as small channels did, with no repeats and no SEVENTEXT
(those are Channel 7's). New shows take hours from it as they are built. Agreed with the user 2026-11-13:
the soap, Marina Row (soap.py, marina_row.py), at 20:20 after Wits; Cartoon Time comes back at 18:30 once the bank has
films (its shelf is empty, so its hour was the test card). Tideline, the wildlife series (wildlife.py; docs/FACTUAL.md,
planned with the user 2026-11-14), at 20:40, before the closedown at 21:00, in turn with The Coast Road, the travelogue
(travelogue.py), through schedule.ROTATIONS.
"""
from __future__ import annotations

import random

from newsroom.channel import Channel
from newsroom.models import SegmentType as T
from newsroom.schedule import Show

CHANNEL_8 = Channel(number="8", name="Channel 8", said="channel eight", wordmark="CHANNEL 8 · PORT WEXLEY")

# The closedown, one show from 21:00 to seven the next evening (one id, so the test card's "programmes
# resume at" is 19:00, not midnight): the goodnight once, then the card on a loop.
CLOSEDOWN = Show(
    "closedown", "GOODNIGHT", "CHANNEL 8", (52, 56, 118),
    pattern=(T.bumper, T.testcard), loop_from=1,
    target_s={T.bumper: 14.0, T.testcard: 300.0},
)
CLOSEDOWN_TEXT = ("That's the end of tonight's programmes on Channel 8. We're back tomorrow at seven, with The "
                  "Kettle's On. From all of us at WTV, goodnight.")

# The channel's day: (start, show id), as schedule.SCHEDULE. One episode a night: two Wits slots back
# to back would run as one show (schedule.show_end looks for a different id).
SCHEDULE: tuple[tuple[int | str, str], ...] = (
    (0, "closedown"),
    (19, "kettle"),             # The Kettle's On (kettle.py): the hour
    (20, "wits"),
    ("20:20", "marina"),        # Wits: twenty minutes (the user, 2026-11-07): seven rounds came to 14, chat filled the rest
    ("20:40", "tideline"),      # Marina Row, the soap (soap.py): twenty minutes after Wits (the user, 2026-11-13)
    ("21:00", "closedown"),     # Tideline, the wildlife series (wildlife.py): twenty minutes (the user, 2026-11-14)
)

# The continuity announcer's lines over Channel 8's ident (continuity.IDENT_LINES): Cartoon Time and the
# closedown take Wexley Wits' (the first), until they have tunes of their own.
IDENT_LINES = {"wits": ["This is Channel 8.", "Channel 8, for Port Wexley and the Greymouth coast."]}


def attend():
    """Give Channel 8's creative editor its seat at the editors' daily meeting (newsroom/meeting.py), and nothing
    else: the launcher calls this on a Channel 7 night, when the channel itself is off the air. Returns an undo."""
    from . import creative

    return creative.attend()


def use():
    """Put out the entertainment channel instead of Channel 7, from now. Returns an undo (for the tests)."""
    from newsroom import assets, channel, continuity, locations, player, scenes, schedule, workers, writers

    from . import creative, kettle, oche, quiz, soap, travelogue, wildlife, wits
    from .marina_row import MARINA_ROW
    from .cartoons import CARTOON_TIME

    saved = (schedule.SCHEDULE, dict(schedule.SHOWS), dict(locations.MARKS), dict(assets.IDENTS),
             list(workers.IDLE_JOBS), dict(writers._PLACE), dict(assets.IDENT_MUSIC), dict(assets.IDENT_VOICES),
             channel.use(CHANNEL_8), (continuity.SHOWS, continuity.IDENT_LINES, continuity.FOLDER))
    # Channel 8's continuity has a folder of its own: Channel 7's pool says "This is Channel 7" over its idents.
    continuity.SHOWS, continuity.IDENT_LINES = tuple(IDENT_LINES), IDENT_LINES
    continuity.FOLDER = assets.CONFIG.paths.continuity / "channel8"
    continuity._pool = None                                    # opened afresh on the new folder
    schedule.SCHEDULE = SCHEDULE
    schedule.SHOWS[quiz.SHOW] = wits.SHOW
    schedule.SHOWS[CARTOON_TIME.id] = CARTOON_TIME             # off the schedule until the bank has films
    schedule.SHOWS[kettle.SHOW] = kettle.SHOW_DEF
    schedule.SHOWS[CLOSEDOWN.id] = CLOSEDOWN
    # A new file: bumper_cartoons.wav says "channel seven", and a bumper is only rebaked for new music.
    assets.IDENTS[CARTOON_TIME.id] = (assets.CONFIG.paths.assets / "bumper_cartoons_8.wav",
                                      "It's Cartoon Time, on channel eight!")
    assets.IDENT_MUSIC[CARTOON_TIME.id] = "rockpool"          # until Cartoon Time has music of its own
    # A new file for new words (bumper_closedown.wav says "with Cartoon Time"; a bumper is only rebaked for new music).
    assets.IDENTS[CLOSEDOWN.id] = (assets.CONFIG.paths.assets / "bumper_closedown_kettle.wav", CLOSEDOWN_TEXT)
    assets.IDENT_MUSIC[CLOSEDOWN.id] = quiz.SHOW
    assets.IDENT_VOICES[CLOSEDOWN.id] = continuity.VOICE      # the continuity announcer says goodnight
    locations.MARKS[wits.SET] = wits.MARKS
    scenes.SHOW_SETS[quiz.SHOW] = wits.SET
    player.SEATS[quiz.SHOW] = 4
    assets.IDENTS[quiz.SHOW] = (assets.CONFIG.paths.assets / "bumper_wits.wav", wits.IDENT)
    workers.IDLE_JOBS.append((quiz.should_commission, quiz.commission))
    _kettle(kettle)
    undo_soap = soap.register(MARINA_ROW)
    undo_wildlife = wildlife.register()
    undo_travelogue = travelogue.register()
    writers.SHOW_SYSTEMS[quiz.SHOW] = wits.SYSTEMS
    writers._PLACE.update(wits.PLACE)
    writers.BRIEF_HOOKS[quiz.SHOW] = quiz.brief_for
    writers.PROMPT_HOOKS[quiz.SHOW] = quiz.for_prompt
    writers.SEAT_HOOKS[quiz.SHOW] = quiz.seats
    writers.CAPTION_HOOKS[quiz.SHOW] = quiz.caption
    writers.TEMPLATE_HOOKS[quiz.SHOW] = template
    writers.CHECK_HOOKS[quiz.SHOW] = quiz.check
    # Six questions with bonuses came to 25 lines, the twelve darts to 34: the debate's 24 failed three items
    # of five twice over on the scratch run (2026-11-07), and code's own rounds stood in.
    writers.LINE_CAPS[quiz.SHOW] = 40
    writers.AFTER_HOOKS[quiz.SHOW] = quiz.after
    player.OVERLAY_HOOKS[quiz.SHOW] = oche.overlay
    scenes.OVERLAYS[quiz.SHOW] = oche.draw
    player.VIEW_HOOKS[quiz.SHOW] = quiz.view                   # the set's scoreboard: the score, as Clive reads it
    scenes.DRESSINGS[quiz.SHOW] = wits.draw_board
    writers.BOOKED_SHOWS.add(quiz.SHOW)
    writers.DEBATE_SHOWS.add(quiz.SHOW)
    writers.UNFILED_SHOWS.add(quiz.SHOW)
    # The creative editor (creative.py): the soap, Tideline and The Coast Road enrolled themselves above; the two
    # light shows here. Its idle jobs go in last, so its catch-up is ahead of every booking and its reviews behind.
    undo_enrolled = (kettle.enrol(), quiz.enrol())
    undo_creative = creative.install()
    undo_seat = attend()

    def undo() -> None:
        undo_seat()
        undo_creative()
        for un in undo_enrolled:
            un()
        undo_travelogue()
        undo_wildlife()
        undo_soap()
        schedule.SCHEDULE = saved[0]
        schedule.SHOWS.clear(), schedule.SHOWS.update(saved[1])
        locations.MARKS.clear(), locations.MARKS.update(saved[2])
        assets.IDENTS.clear(), assets.IDENTS.update(saved[3])
        workers.IDLE_JOBS[:] = saved[4]
        writers._PLACE.clear(), writers._PLACE.update(saved[5])
        assets.IDENT_MUSIC.clear(), assets.IDENT_MUSIC.update(saved[6])
        assets.IDENT_VOICES.clear(), assets.IDENT_VOICES.update(saved[7])
        channel.use(saved[8])
        continuity.SHOWS, continuity.IDENT_LINES, continuity.FOLDER = saved[9]
        continuity._pool = None
        for reg in (scenes.SHOW_SETS, player.SEATS, writers.SHOW_SYSTEMS, writers.BRIEF_HOOKS, writers.PROMPT_HOOKS,
                    writers.SEAT_HOOKS, writers.CAPTION_HOOKS, writers.TEMPLATE_HOOKS, writers.CHECK_HOOKS,
                    writers.AFTER_HOOKS, writers.LINE_CAPS, player.OVERLAY_HOOKS, scenes.OVERLAYS,
                    player.VIEW_HOOKS, scenes.DRESSINGS, writers.STUDIO_HOOKS, writers.CALLED):
            reg.pop(quiz.SHOW, None)
            reg.pop(kettle.SHOW, None)
        for reg in (writers.BOOKED_SHOWS, writers.DEBATE_SHOWS, writers.UNFILED_SHOWS):
            reg.discard(quiz.SHOW)
            reg.discard(kettle.SHOW)
    return undo


def _kettle(kettle) -> None:
    """The Kettle's On's registrations (undone with Wits' by use()'s undo)."""
    from newsroom import assets, locations, player, scenes, workers, writers
    from newsroom.config import CONFIG

    assets.IDENTS[kettle.SHOW] = (assets.CONFIG.paths.assets / "bumper_kettle.wav", kettle.IDENT)
    assets.IDENT_MUSIC[kettle.SHOW] = "outabout"               # folk, until it has music of its own (by ear)
    assets.IDENT_VOICES[kettle.SHOW] = CONFIG.tts.voices.get("kettle_a", "bf_truscott")
    # Its own set waits for approved art; the breakfast sofa stands in, with the show's three marks added.
    locations.MARKS[kettle.STAND_IN_SET] = {**locations.MARKS[kettle.STAND_IN_SET], **kettle.MARKS}
    scenes.SHOW_SETS[kettle.SHOW] = kettle.STAND_IN_SET
    player.SEATS[kettle.SHOW] = 1                              # one guest at a time: the cook, the sofa, the expert
    workers.IDLE_JOBS.append((kettle.should_commission, kettle.commission))
    writers.SHOW_SYSTEMS[kettle.SHOW] = kettle.SYSTEMS
    writers._PLACE.update(kettle.PLACE)
    writers.BRIEF_HOOKS[kettle.SHOW] = kettle.brief_for
    writers.PROMPT_HOOKS[kettle.SHOW] = kettle.for_prompt
    writers.CAPTION_HOOKS[kettle.SHOW] = kettle.caption
    writers.STUDIO_HOOKS[kettle.SHOW] = kettle.studio            # the expert answers the calls
    writers.CALLED[kettle.SHOW] = kettle.CALLED
    writers.TEMPLATE_HOOKS[kettle.SHOW] = kettle.template
    writers.BOOKED_SHOWS.add(kettle.SHOW)                      # its guests are booked: no loose ends on the sofa
    writers.UNFILED_SHOWS.add(kettle.SHOW)                     # never news


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
    n = next((int(k[1]) - 1 for k in ("r1", "r2", "r3", "r4", "r5", "r6", "r7") if "{" + k + "}" in brief), None)
    lines: list = []
    if n is not None and q["rounds"][n]["kind"] in quiz.DARTS_ROUNDS:
        from .oche import PER_PLAYER, words

        r = q["rounds"][n]
        lines.append(PanelLine(speaker="mag_b", text=f"Round {n + 1}, {r['title']}. Three darts each, at the oche."))
        for k in range(0, len(r["throws"]), PER_PLAYER):
            mine = r["throws"][k:k + PER_PLAYER]
            lines.append(PanelLine(speaker="mag_b", text=f"{mine[0]['who']}, for {teams[mine[0]['to']]['name']}."))
            lines += [PanelLine(speaker="mag_b", text=d["call"]) for d in mine]
            lines.append(PanelLine(speaker="mag_b", text=f"That's {words(sum(d['points'] for d in mine))}."))
        s = r["scores_after"]
        lines.append(PanelLine(speaker="mag_b", text=f"Totals: {teams[0]['name']} {r['totals'][0]}, "
                                                    f"{teams[1]['name']} {r['totals'][1]}. So after round {n + 1}: "
                                                    f"{teams[0]['name']} {s[0]}, {teams[1]['name']} {s[1]}."))
        head = r["title"].capitalize()
    elif n is not None:
        r = q["rounds"][n]
        said = f"Round {n + 1}: {r['title']}."         # Clive's verdict shares a line with what he says next
        for x in r["questions"]:
            lines.append(PanelLine(speaker="mag_b", text=f"{said} {teams[x['to']]['name']}: {x['q']}"))
            wrong = x.get("wrong") or []
            lines.append(PanelLine(speaker="guest", guest_name=x["who"],
                                   text=x["a"].capitalize() + "?" if x["right"] else
                                   (f"{wrong[0]}?" if wrong else "I'll have to guess. Pass.")))
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
