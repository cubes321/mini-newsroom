"""tools/story_browser.py: the read-only story browser, on a small town of its own. No newsroom import needed."""
from __future__ import annotations

import ast
import importlib.util
import json
import re
import sys
import threading
import urllib.request
from pathlib import Path

import pytest

_TOOL = Path(__file__).resolve().parent.parent / "tools" / "story_browser.py"
_spec = importlib.util.spec_from_file_location("story_browser", _TOOL)
sb = importlib.util.module_from_spec(_spec)
sys.modules["story_browser"] = sb
_spec.loader.exec_module(sb)

H1, H2, H3, H9 = "a1b2c3d4e5f60718", "b1b2c3d4e5f60718", "c1b2c3d4e5f60718", "d1b2c3d4e5f60718"


def _world() -> dict:
    return {
        "town": "Port Wexley", "broadcast_day": 20, "last_date": "2026-11-18",
        "characters": [{"id": "anchor", "name": "Dana Ferris"}, {"id": "reporter", "name": "Miles Okafor"}],
        "people": [{"id": "p001", "name": "Helen Strand", "role": "Mayor of Port Wexley", "kind": "official",
                    "appearances": 9, "memories": [{"date": "2026-11-17", "show": "news", "said": "No date yet."}]},
                   {"id": "p002", "name": "Nora Ellison", "role": "petition organiser", "kind": "resident"}],
        "threads": [
            {"id": "t1", "title": "Pool Petition Nears a Thousand Names", "status": "Names go to the chamber",
             "opened": "2026-11-16", "updated": "2026-11-18", "mentions": 5, "phase": "developing",
             "next_development": "On Thursday the clerk reads the names into the record.", "people": ["p001", "p002"],
             "beats": [{"date": "2026-11-16", "headline": "Pool petition opens", "status": "a stall on the quay"},
                       {"date": "2026-11-18", "headline": "Pool petition nears a thousand", "status": ""}]},
            {"id": "t2", "title": "Swimming pool names counted", "status": "", "opened": "2026-11-17",
             "updated": "2026-11-17", "phase": "closed", "merged_into": "t1", "beats": []},
            {"id": "t3", "title": "Brass Gull Bench Unveiled", "status": "unveiled", "opened": "2026-11-10",
             "updated": "2026-11-11", "phase": "faded", "beats": [{"date": "2026-11-11", "headline": "Gull bench"}]},
        ],
        "archive": [
            {"date": "2026-11-17", "type": "bulletin", "headline": "Pool names counted", "thread_id": "t2",
             "text": "Counted.", "show": "news", "hash": H2},
            {"date": "2026-11-17", "type": "field_report", "headline": "The Wall Survey Lands", "thread_id": "t9",
             "text": "Miles at the wall.", "show": "news", "hash": H9},
            {"date": "2026-11-18", "type": "interview", "headline": "Pool petition nears a thousand",
             "thread_id": "t1", "people": ["p002"], "text": "Good evening.", "show": "news", "hash": H1, "ts": 1795038215.0},
            {"date": "2026-11-18", "type": "interview", "headline": "Queenie at the bar", "fiction": True,
             "show": "marina", "hash": H3},
            {"date": "2026-11-18", "type": "weather", "headline": "Showers easing", "aired": False, "show": "news"},
        ],
        "inquiries": [{"date": "2026-11-15", "thread_id": "t9", "title": "Who Pays for the Wall?", "guest": "Helen Strand"}],
        "chambers": [{"date": "2026-11-19", "motions": [
            {"thread_id": "t1", "motion": "That the petition goes to the budget committee.", "mover": "Helen Strand",
             "title": "Pool petition", "for": 6, "against": 3, "abstain": 0, "carried": True, "applied": True,
             "votes": [{"councillor": "Gerald Thorne", "vote": "for", "why": "Costs first."}]}]}],
        "promises": [{"id": "pr1", "made": "2026-11-19", "thread_id": "t1", "text": "A pool costing by 3 December",
                      "due": "2026-12-03", "state": "open", "settled": "", "note": ""}],
        "desk_notes": [{"at": "2026-11-18 21:41", "planned": ["t1"], "new": 1, "merges": 1, "note": "Pool steps up."}],
        "senior_memo": "1) Keep the pool for Thursday.", "senior_memo_at": "2026-11-18 21:41",
        "meetings": [{"date": "2026-11-18", "at": "21:42", "turns": [{"seat": "news", "says": "Evening."}],
                      "minutes": {"verdict": "Quiet.", "actions": [{"to": "channel8", "what": "Rest Nora."}]}}],
    }


@pytest.fixture
def town(tmp_path):
    (tmp_path / "world.json").write_text(json.dumps(_world()), encoding="utf-8")
    annals = tmp_path / "annals"
    (annals / "clips").mkdir(parents=True)
    (annals / "2026-11-16.json").write_text(json.dumps({
        "date": "2026-11-16", "weekday": "Monday", "pieces": 12,
        "stories": [{"thread_id": "t1", "title": "Pool Petition", "phase": "peak", "pieces": 4,
                     "beats": ["Pool petition opens"], "people": ["Nora Ellison"], "next": "Thursday."}],
        "weather": "Bright and breezy", "clips": [{"wav": "2026-11-16_t1.wav", "who": "Miles Okafor",
                                                   "headline": "Pool petition opens", "text": "A stall on the quay."}]}),
        encoding="utf-8")
    (annals / "clips" / "2026-11-16_t1.wav").write_bytes(b"RIFF-keepsake")
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / f"{H1}.json").write_text(json.dumps({"headline": "Pool petition nears a thousand", "lines": [
        {"speaker": "anchor", "text": "Our guest tonight runs the petition.", "wav_path": str(cache / f"{H1}_00.wav")},
        {"speaker": "guest", "guest_name": "Nora Ellison", "guest_role": "organiser", "text": "A thousand, nearly.",
         "wav_path": str(cache / f"{H1}_01.wav")}]}), encoding="utf-8")
    (cache / f"{H1}_00.wav").write_bytes(b"RIFF-line")
    (tmp_path / "secret.txt").write_text("not for the web", encoding="utf-8")
    return sb.Files(tmp_path / "world.json", annals, cache)


def get(files, path) -> tuple[int, str]:
    status, _, body = sb.respond(files, path)
    return status, body.decode("utf-8", "replace")


def test_a_thread_page_has_its_beats_pieces_bookings_and_annals(town):
    status, html = get(town, "/thread/t1")
    assert status == 200
    for want in ("Pool Petition Nears a Thousand Names", "On Thursday the clerk reads the names",
                 "a stall on the quay", "Pool petition nears a thousand",
                 "Pool names counted",                                  # t2's piece: t2 was merged into t1
                 "That the petition goes to the budget committee", "A pool costing by 3 December",
                 "/day/2026-11-16", "Pool steps up.", "/person/p002"):
        assert want in html, want


def test_a_merged_thread_points_at_the_story_it_joined(town):
    status, html = get(town, "/thread/t2")
    assert status == 200 and "duplicate" in html and 'href="/thread/t1"' in html


def test_a_pruned_thread_shows_what_is_still_held_of_it(town):
    status, html = get(town, "/thread/t9")
    assert status == 200
    assert "no longer in this world" in html and "The Wall Survey Lands" in html and "Who Pays for the Wall?" in html
    assert get(town, "/thread/t404")[0] == 404


def test_the_story_list_filters_and_searches(town):
    _, live = get(town, "/threads")
    assert "/thread/t1" in live and "/thread/t3" not in live           # open stories by default
    _, faded = get(town, "/threads?state=faded")
    assert "/thread/t3" in faded and "/thread/t1" not in faded
    _, found = get(town, "/threads?state=all&q=nora")                  # a person's name finds their stories
    assert "/thread/t1" in found and "/thread/t3" not in found


def test_a_piece_shows_its_full_script_with_names_and_audio(town):
    status, html = get(town, f"/piece/{H1}")
    assert status == 200
    assert "Dana Ferris" in html and "Nora Ellison" in html and "A thousand, nearly." in html
    assert f"/audio/{H1}_00.wav" in html and f"/audio/{H1}_01.wav" not in html     # only audio the cache still has


def test_the_archive_marks_fiction_and_unaired_pieces(town):
    _, html = get(town, "/archive")
    assert "fiction" in html and "not yet aired" in html
    _, hidden = get(town, "/archive?fiction=hide")
    assert "Queenie at the bar" not in hidden


def test_a_day_page_has_the_annals_and_its_keepsake(town):
    status, html = get(town, "/day/2026-11-16")
    assert status == 200 and "Bright and breezy" in html and "/clip/2026-11-16_t1.wav" in html
    assert get(town, "/clip/2026-11-16_t1.wav")[0] == 200


@pytest.mark.parametrize("path", ["/clip/../world.json", "/clip/..%2Fsecret.txt", "/clip/..%5Csecret.txt",
                                  "/audio/../secret.txt", "/audio/secret.txt", "/clip/secret.txt",
                                  "/audio/%2E%2E%5Cworld.json", "/day/..%2Fsecret"])
def test_files_outside_the_clips_and_cache_are_never_served(town, path):
    status, html = get(town, path)
    assert status == 404 and "not for the web" not in html


def test_a_half_written_world_shows_the_last_good_copy(tmp_path, monkeypatch):
    monkeypatch.setattr(sb, "TRY_GAP_S", 0.0)
    p = tmp_path / "world.json"
    p.write_text(json.dumps({"town": "first"}), encoding="utf-8")
    f = sb.JsonFile(p, min_gap=0.0)
    assert f.get() == {"town": "first"}
    p.write_text('{"town": "sec', encoding="utf-8")                   # caught mid-write
    assert f.get() == {"town": "first"} and "showing the copy" in f.problem
    p.write_text(json.dumps({"town": "second", "pad": 1}), encoding="utf-8")
    assert f.get() == {"town": "second", "pad": 1} and not f.problem


def test_a_missing_world_is_a_page_not_a_crash(tmp_path):
    files = sb.Files(tmp_path / "nowhere.json", tmp_path / "annals", tmp_path / "cache")
    status, html = get(files, "/")
    assert status == 503 and "No town to show" in html


def _tree(root: Path) -> dict[str, bytes]:
    return {str(p.relative_to(root)): p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_browsing_every_page_changes_nothing_on_disk(town, tmp_path):
    before = _tree(tmp_path)
    seen, todo = set(), ["/"]
    while todo:
        path = todo.pop()
        if path in seen:
            continue
        seen.add(path)
        status, ctype, body = sb.respond(town, path)
        assert status in (200, 204), (status, path)
        if ctype.startswith("text/html"):
            todo += [h.replace("&amp;", "&") for h in re.findall(r'(?:href|src)="(/[^"]*)"', body.decode())]
    assert len(seen) > 15
    assert _tree(tmp_path) == before


def test_the_tool_never_imports_the_station():
    tree = ast.parse(_TOOL.read_text(encoding="utf-8"))
    names = [a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names]
    names += [n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)]
    assert not [n for n in names if n.split(".")[0] in ("newsroom", "entertainment")]


def test_it_serves_over_http_on_localhost(town):
    server = sb.serve(town, "127.0.0.1", 0)
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/threads", timeout=10) as r:
            assert r.status == 200 and "Pool Petition" in r.read().decode()
    finally:
        server.shutdown()
        server.server_close()
