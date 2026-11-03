"""SEVENTEXT, the overnight teletext pages (teletext.py): built from the world in code, no model and no
voice; drawn as a 40 x 24 grid; and recorded a little by tools/obs_record.py."""
from __future__ import annotations

import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402

from newsroom import scenes, schedule, teletext, world as world_mod  # noqa: E402
from newsroom.buffer import Buffer  # noqa: E402
from newsroom.models import Segment, SegmentType as T  # noqa: E402
from newsroom.player import Player  # noqa: E402
from newsroom.producer import Producer  # noqa: E402
from newsroom.workers import generate  # noqa: E402

NOW = datetime(2026, 11, 2, 2, 14, 33)


def _world():
    w = world_mod.seed()
    tid = w.update_thread(None, "Harbour wall report due Friday, tenders could follow next week",
                          "The harbourmaster's report on the wall goes to council on Friday.")
    w.update_thread(tid, "Wall report delayed a day", "The report now lands on Saturday.")
    return w


def test_every_page_fits_the_grid():
    ps = teletext.pages(_world(), NOW)
    nums = [p["num"] for p in ps]
    assert nums[:3] == [100, 101, 102] and nums[-7:] == [120, 130, 140, 150, 160, 170, 180] and nums == sorted(nums)
    for p in ps:
        assert teletext.height(p["rows"]) <= len(teletext.BODY), p["num"]
        assert all(len(r.get("t", "")) < teletext.COLS for r in p["rows"]), p["num"]
    assert len(teletext.header(170, NOW)) <= teletext.COLS
    story = next(p for p in ps if p["num"] == 102)
    assert any("council on Friday" in r.get("t", "") or "Saturday" in r.get("t", "") for r in story["rows"])


def test_the_pages_turn_with_time_and_the_header_counts_up_first():
    work = {"pages": teletext.pages(_world(), NOW)}
    page, prev, since = teletext.on_screen(work, 0.0)
    assert page["num"] == 100 and since == 0.0
    page, prev, since = teletext.on_screen(work, teletext.PAGE_S * 2 + 3)
    assert page["num"] == 102 and prev == 101 and since == 3.0
    assert teletext.on_screen(work, teletext.PAGE_S * len(work["pages"]))[0]["num"] == 100   # round again
    calls = []
    c = pygame.Surface((320, 180))
    teletext.draw(c, page, prev, 0.4, NOW, lambda key, make, at: calls.append(key))
    assert [k[0] for k in calls] == ["tth"]                           # searching: the header only
    calls.clear()
    teletext.draw(c, page, prev, 5.0, NOW, lambda key, make, at: calls.append(key))
    assert [k[0] for k in calls] == ["tth", "ttp"]


def test_a_teletext_slot_is_ready_and_silent_and_the_player_shows_its_pages():
    w = _world()
    seg = generate(Segment(slot_id=3, type=T.teletext, show="overnight", target_s=130,
                           nominal_start_ts=NOW.timestamp()), w)
    n = len(seg.work["teletext"]["pages"])
    assert seg.lines and seg.lines[0].text == "" and seg.duration_s == teletext.PAGE_S * n
    buf = Buffer()
    pl = Player(buf, w, Producer(buf, 600), audio=False)
    pl.current, pl.line_idx, pl.seg_start, pl.line_start = seg, 0, 0.0, 0.0
    v = pl.view(teletext.PAGE_S * 7 + 5)
    assert v.mode == "teletext" and v.teletext["page"] == seg.work["teletext"]["pages"][7]
    pygame.init()
    c, screen = pygame.Surface((320, 180)), pygame.Surface((960, 540))
    scenes.render(c, v, 0.0)
    scenes.present(c, screen)
    banner_y = (teletext.Y0 + teletext.CH + 2) * 3                  # every page's banner, on row 1
    assert screen.get_at((480, banner_y))[:3] != (0, 0, 0)


def test_the_overnight_loop_turns_to_the_pages():
    assert T.teletext in schedule.get("overnight").pattern


def test_the_recorder_keeps_the_first_two_blocks_of_pages(tmp_path: Path):
    lines = []
    for n in range(4):
        lines += [f"02:{n:02d}:00 INFO  newsroom.player: playing slot {10 + n * 3} teletext (130.0s, 1 lines) [overnight]",
                  f"02:{n:02d}:30 INFO  newsroom.player: playing slot {11 + n * 3} interview (80.0s, 9 lines) [late] - 'x'",
                  f"02:{n:02d}:50 INFO  newsroom.player: playing slot {12 + n * 3} testcard (60.0s, 1 lines) [overnight]"]
    log = tmp_path / "night.log"
    log.write_text("\n".join(lines + ["exit: worst p99 2.0ms"]) + "\n", encoding="utf-8")
    out = subprocess.run([sys.executable, "tools/obs_record.py", str(log), "--dry-run", "--from-start"],
                         capture_output=True, text=True, timeout=60).stdout
    assert out.count("START Seventext") == 2 and out.count("STOP  Seventext") == 2
    assert "The Last Ferry" not in out                                # the repeats between aren't recorded
