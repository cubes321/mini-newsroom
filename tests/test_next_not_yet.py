"""A story's NEXT is held until its day (world.said_next): on the 2026-11-22 night the news told seven newer stories'
next steps as done days early (the bottled ship too tall for the sill, due Friday, on Sunday night), because the
briefing said "a follow-up must deliver the NEXT development" and only long stories wait in the pool. No network."""
from __future__ import annotations

from datetime import datetime

from newsroom import world as world_mod, writers
from newsroom.world import said_next

SUN_NIGHT = datetime(2026, 11, 22, 21, 20).timestamp()
MON_MORNING = datetime(2026, 11, 23, 6, 2).timestamp()


def _thread(nxt: str):
    w = world_mod.seed()
    w.last_date = "2026-11-22"
    t = w.thread(w.update_thread(None, "Margaret Tully's Next Ship in a Bottle Meets the Shop Window", "under way"))
    t.next_development = nxt
    return w, t


def test_a_next_days_ahead_is_not_yet():
    _, t = _thread("On Friday 27 November Margaret Tully tries her next bottled ship in the lighthouse shop window "
                   "and finds the bottle an inch too tall for the sill.")
    s = said_next(t, SUN_NIGHT)
    assert "NOT YET" in s and "Friday 27 November" in s and "never report it as done" in s
    assert "too tall for the sill" in s                                  # what to build up to is still there


def test_tomorrow_is_said_as_tomorrow_and_today_by_its_hour():
    _, t = _thread("On Monday 23 November, by noon, Brenda Fisk has copied the stamp into her pattern book.")
    assert "due tomorrow, Monday 23 November" in said_next(t, SUN_NIGHT)
    morning = said_next(t, MON_MORNING)                                  # Morning Tide at 06:02: not yet
    assert "NOT YET" in morning and "later today, at about midday" in morning
    assert "NOT YET" not in said_next(t, datetime(2026, 11, 23, 12, 30).timestamp())


def test_a_next_due_now_or_undated_is_delivered():
    _, t = _thread("On Sunday 22 November the gulls are back on the pontoon.")
    assert said_next(t, SUN_NIGHT).startswith("; NEXT: On Sunday")
    _, t = _thread("Marjorie Pell writes to the county archive.")
    assert said_next(t, SUN_NIGHT) == "; NEXT: Marjorie Pell writes to the county archive."
    _, t = _thread("")
    assert said_next(t, SUN_NIGHT) == ""


def test_the_writers_briefing_and_quiet_stories_mark_it(monkeypatch):
    monkeypatch.setattr(world_mod.schedule, "now", lambda: SUN_NIGHT)
    w, t = _thread("On Tuesday 24 November the oak-chip sack lands half short at the smokehouse.")
    briefing = w.summary_for_prompt()
    assert f"[{t.id}]" in briefing and "NEXT, NOT YET (due on Tuesday 24 November" in briefing
    assert "a NEXT marked NOT YET has not happened" in briefing
    assert "NOT YET" not in w.summary_for_editor()                       # the desk plans it: it sees it bare
    monkeypatch.setattr(w, "briefing_threads", lambda auction=True: [])   # off the briefing: a quiet story
    quiet = writers._quiet_threads(w, set())
    assert f"[{t.id}]" in quiet and "NOT YET" in quiet and "never told as done" in quiet


# Real statuses from the town's board before and after the 2026-11-22 night: (status, NEXT, told as done?).
STATUSES = [
    ("Tamsin Rowe's oak-chip sack arrives half short; a note goes up in Dev Ramachandran's window and Sandra Okoye "
     "offers the Harrow Street traders' offcuts.",
     "On Tuesday 24 November the oak-chip sack lands half short at the smokehouse, Tamsin Rowe's note goes up in "
     "Dev Ramachandran's bakery window and Sandra Okoye offers the Harrow Street traders' offcuts.", True),
    ("Blue cannery float carried to the museum store; the scratched mark is being checked against the batch ledger",
     "On Monday 30 November Ned Pascoe carries the blue cannery float up to the museum store, Imogen Vale reads the "
     "scratched mark against the cannery batch ledger.", True),
    ("Ivy Marchetti walked the inner moorings at first light and all are down; one chafed warp found on the quay",
     "On Tuesday 24 November at first light, with the wind dropped, Ivy Marchetti walks the inner moorings and finds "
     "one chafed warp on the quay.", True),
    ("Rehearsals on the harbour front ahead of Tuesday's darts night; Oscar Lindqvist still has the last verse to get",
     "On Tuesday 24 November, darts night, Oscar Lindqvist rehearses the last verse with Jan Couch.", False),
    ("Dry suits are covered, but the boat is still short of funds.",
     "On Wednesday 2 December Lorna Penrose chalks two columns on the boathouse board: dry suits and the boat fund.",
     False),
    ("Ferry ladder comes off on Tuesday the first of December",
     "On Tuesday 1 December the Saltby ferry ladder is taken off the boat and measured.", False),
    ("Gulls on the pontoon all week, Morag Lyle says.",
     "On Tuesday 24 November the oak-chip sack lands half short at the smokehouse.", False),   # another story
]


def test_a_status_that_tells_the_next_as_done_is_caught():
    for status, nxt, done in STATUSES:
        _, t = _thread(nxt)
        assert world_mod.tells_next_as_done(status, t, SUN_NIGHT) is done, status
    _, t = _thread(STATUSES[0][1])                     # once the NEXT is due, the same words are just the news
    assert not world_mod.tells_next_as_done(STATUSES[0][0], t, datetime(2026, 11, 24, 18, 0).timestamp())


def test_the_quiet_stories_never_pass_it_on_as_fact(monkeypatch):
    monkeypatch.setattr(world_mod.schedule, "now", lambda: SUN_NIGHT)
    w, t = _thread(STATUSES[0][1])
    t.status = STATUSES[0][0]
    monkeypatch.setattr(w, "briefing_threads", lambda auction=True: [])
    quiet = writers._quiet_threads(w, set())
    assert "arrives half short" not in quiet.split("NEXT")[0] and "its planned step (NEXT) is still ahead" in quiet
