"""Port Wexley's story browser: the town's stories, current and past, read in a web browser outside the station.

    uv run python tools/story_browser.py                    # then open http://127.0.0.1:8766
    uv run python tools/story_browser.py --world data/world.backup-2026-11-15-pre-night.json   # an older town

What it shows, all read from the files the station keeps:

- the story threads, open, faded and closed (filter, search), each with its status, its NEXT, its people, its beats
  day by day, the pieces the archive still holds, and everything booked on it (The Chamber's motions and the
  council's promises, The Inquiry, The Panel, Have Your Say, documentaries and specials);
- a piece as it went out: the full script from the cache, line by line, with its audio while the cache keeps it;
- the days: the annals page where one was written (with its keepsake clips), the stories that moved that day,
  what was booked, and what the archive still holds of it;
- the council, the bookings and running orders, the residents, and the desk (the senior editor's memo, the desk's
  rounds and the editors' meetings).

**Strictly read-only.** It never imports newsroom (`world.load()` seeds a missing town and rolls the day, and
`world.save` is a call away), opens nothing for writing, and serves only on 127.0.0.1. It can run beside a station
that is on air: the station rewrites data/world.json by writing a .tmp and replacing the file, and on Windows that
replace fails while any other process has the file open (tried 2026-11-18; FILE_SHARE_DELETE doesn't help). So the
world is read as seldom and as briefly as possible: a stat first, a read only when the file has changed and at most
every couple of seconds, the whole file in one read with the handle closed before it is parsed. A read that meets a
half-written file is tried again, and after that the last good copy is shown, with a note.
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import threading
import time
from collections import defaultdict
from datetime import date, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, quote, unquote, urlencode, urlsplit

ROOT = Path(__file__).resolve().parent.parent
PORT = 8766                    # 8765 is the voice-samples server in .claude/launch.json
MIN_GAP_S = 2.0                # the world file is looked at no more often than this
TRIES = 6                      # reads of a file caught mid-write before the last good copy is shown
TRY_GAP_S = 0.25
PAGE = 100                     # archive pieces to a page
LIVE = ("emerging", "developing", "peak", "resolving")
PHASE_ORDER = {p: n for n, p in enumerate(LIVE + ("faded", "closed"))}
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_CLIP = re.compile(r"^[\w.-]+\.wav$")
_LINE_WAV = re.compile(r"^[0-9a-f]{8,40}_\d{1,3}\.wav$")
_HASH = re.compile(r"^[0-9a-f]{8,40}$")
_ID = re.compile(r"^[\w-]{1,40}$")


def _env_path(var: str, default: Path) -> Path:
    v = os.environ.get(var)
    return Path(v) if v else default


# ----------------------------------------------------------------------------------------------- reading


class JsonFile:
    """One JSON file that a running station may rewrite at any moment, read seldom and briefly (see the module's
    docstring). `get()` gives the newest good copy, or None if there has never been one; `problem` says why the
    copy shown may be stale."""

    def __init__(self, path: Path, min_gap: float = MIN_GAP_S):
        self.path = Path(path)
        self.min_gap = min_gap
        self.lock = threading.Lock()
        self.data = None
        self.key: tuple | None = None
        self.checked = -1e9
        self.read_at = 0.0
        self.problem = ""

    def _stat(self) -> tuple | None:
        try:
            st = self.path.stat()
            return st.st_mtime_ns, st.st_size
        except OSError:
            return None

    def get(self):
        with self.lock:
            now = time.monotonic()
            if self.data is not None and now - self.checked < self.min_gap:
                return self.data
            self.checked = now
            key = self._stat()
            if self.data is not None and key is not None and key == self.key:
                return self.data
            if key is None and self.data is None:     # never there: os.replace never leaves the name missing
                self.problem = f"{self.path} not found"
                return None
            err: Exception | None = None
            for n in range(TRIES):
                if n:
                    time.sleep(TRY_GAP_S)
                    key = self._stat()
                try:
                    with open(self.path, "rb") as f:          # one read, closed before the parse
                        raw = f.read()
                    data = json.loads(raw.decode("utf-8"))
                except (OSError, ValueError) as e:            # missing, mid-replace, half-written
                    err = e
                    continue
                self.data, self.key, self.read_at, self.problem = data, key, time.time(), ""
                return data
            self.problem = f"{self.path.name} could not be read just now ({type(err).__name__}: {err})"
            if self.data is not None:
                self.problem += f"; showing the copy read at {datetime.fromtimestamp(self.read_at):%H:%M:%S}"
            return self.data


class Files:
    """Where the town's files are, and the readers for them."""

    def __init__(self, world: Path, annals: Path, cache: Path):
        self.world_path, self.annals, self.cache = Path(world), Path(annals), Path(cache)
        self.world = JsonFile(self.world_path)
        self._pages: dict[str, JsonFile] = {}
        self._segments: dict[str, dict | None] = {}
        self._town: tuple[int, Town] | None = None
        self.lock = threading.Lock()

    def town(self) -> Town | None:
        w = self.world.get()
        if not isinstance(w, dict):
            return None
        with self.lock:
            if self._town is None or self._town[0] != id(w):
                self._town = (id(w), Town(w))
            return self._town[1]

    def annals_days(self) -> list[str]:
        try:
            return sorted((p.stem for p in self.annals.glob("*.json") if _DATE.match(p.stem)), reverse=True)
        except OSError:
            return []

    def annals_page(self, day: str) -> dict | None:
        if not _DATE.match(day):
            return None
        with self.lock:
            f = self._pages.setdefault(day, JsonFile(self.annals / f"{day}.json"))
        page = f.get()
        return page if isinstance(page, dict) else None

    def segment(self, h: str) -> dict | None:
        """A piece's cached segment (its whole script), read once: the cache writes a segment and leaves it."""
        if not _HASH.match(h or ""):
            return None
        with self.lock:
            if h in self._segments:
                return self._segments[h]
        try:
            seg = json.loads((self.cache / f"{h}.json").read_bytes().decode("utf-8"))
        except (OSError, ValueError):
            return None                                  # not cached (yet, or any more): try again next time
        with self.lock:
            if len(self._segments) > 2000:
                self._segments.clear()
            self._segments[h] = seg if isinstance(seg, dict) else None
        return self._segments[h]


# ----------------------------------------------------------------------------------------------- the town


class Town:
    """One snapshot of world.json, indexed for the pages. Built once per read of the file."""

    def __init__(self, w: dict):
        self.w = w
        self.threads: dict[str, dict] = {t["id"]: t for t in w.get("threads", []) if isinstance(t, dict) and t.get("id")}
        self.people: dict[str, dict] = {p["id"]: p for p in w.get("people", []) if isinstance(p, dict) and p.get("id")}
        self.by_name: dict[str, dict] = {}
        for p in self.people.values():
            self.by_name.setdefault(p.get("name", ""), p)
        self.chars: dict[str, dict] = {c["id"]: c for c in w.get("characters", []) if isinstance(c, dict) and c.get("id")}
        self.archive: list[dict] = [e for e in w.get("archive", []) if isinstance(e, dict)]
        self.pieces: dict[str, list[dict]] = defaultdict(list)       # root thread -> its pieces, oldest first
        for e in self.archive:
            if e.get("thread_id"):
                self.pieces[self.root(e["thread_id"])].append(e)
        self.merged_from: dict[str, list[str]] = defaultdict(list)
        self.person_threads: dict[str, list[str]] = defaultdict(list)
        for t in self.threads.values():
            if t.get("merged_into"):
                self.merged_from[self.root(t["merged_into"])].append(t["id"])
            for pid in t.get("people", []):
                self.person_threads[pid].append(t["id"])

    def root(self, tid: str) -> str:
        """The story a thread id belongs to now: a thread merged into another is that other one."""
        for _ in range(6):
            t = self.threads.get(tid)
            if not t or not t.get("merged_into"):
                break
            tid = t["merged_into"]
        return tid

    def thread_title(self, tid: str) -> str:
        t = self.threads.get(tid)
        if t:
            return t.get("title", tid)
        mine = self.pieces.get(tid)                  # a pruned thread: the last headline still held, or a booking's title
        found = next((e["headline"] for e in reversed(mine or []) if e.get("headline")), "")
        for key in ("specials", "documentaries", "inquiries"):
            found = found or next((b.get("title", "") for b in self.w.get(key, [])
                                   if isinstance(b, dict) and b.get("thread_id") == tid), "")
        return found

    def speaker(self, line: dict) -> str:
        if line.get("guest_name"):
            return line["guest_name"]
        s = line.get("speaker", "")
        return self.chars.get(s, {}).get("name") or s


# ----------------------------------------------------------------------------------------------- html


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def url(path: str, **q) -> str:
    q = {k: v for k, v in q.items() if v not in (None, "", False)}
    return quote(path) + ("?" + urlencode(q) if q else "")


def link(href: str, text) -> str:
    return f'<a href="{esc(href)}">{esc(text)}</a>'


def badge(text: str, kind: str = "") -> str:
    return f'<span class="badge {esc(kind or text)}">{esc(text)}</span>'


def short(text, n: int = 160) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


def nice_date(iso: str) -> str:
    try:
        return f"{date.fromisoformat(iso):%a %d %b %Y}"
    except (TypeError, ValueError):
        return iso or ""


def clock(ts) -> str:
    try:
        return f"{datetime.fromtimestamp(float(ts)):%H:%M}" if ts else ""
    except (OSError, OverflowError, ValueError, TypeError):
        return ""


def thread_link(town: Town, tid: str, text: str | None = None) -> str:
    if not tid:
        return ""
    title = text or town.thread_title(tid) or tid
    return f'<a href="{esc(url("/thread/" + tid))}">{esc(title)}</a> <span class="id">{esc(tid)}</span>'


def thread_ref(town: Town, tid: str) -> str:
    """Just the story's id, as a link: for a line that already says what the story is."""
    return f'<a class=id href="{esc(url("/thread/" + tid))}" title="{esc(town.thread_title(tid))}">{esc(tid)}</a>' if tid else ""


def person_link(town: Town, name: str) -> str:
    p = town.by_name.get(name)
    return link(f"/person/{p['id']}", name) if p else esc(name)


def phase_badge(t: dict) -> str:
    out = badge(t.get("phase", "?"))
    if t.get("merged_into"):
        out += " " + badge("merged", "flag")
    if t.get("waits_until"):
        out += " " + badge(f"waits {t['waits_until']}", "flag")
    if t.get("breaking"):
        out += " " + badge(f"broke {t['breaking']}", "breaking")
    return out


CSS = """
:root { --bg:#f6f3ec; --fg:#1d1b18; --muted:#6b655c; --card:#fffdf8; --line:#ddd5c6; --accent:#0b5f8a;
  --emerging:#5b8c3a; --developing:#0b5f8a; --peak:#b0361c; --resolving:#8a5a0b; --faded:#8c877f; --closed:#4a4640; }
@media (prefers-color-scheme: dark) { :root { --bg:#16181b; --fg:#e8e4dc; --muted:#9a948a; --card:#1f2226;
  --line:#33373d; --accent:#6cb6e0; --faded:#77726a; --closed:#a39d93; } }
* { box-sizing:border-box }
body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, "Segoe UI", sans-serif }
header { background:#0d2a3d; color:#f2efe8; padding:10px 16px; display:flex; flex-wrap:wrap; gap:6px 18px; align-items:baseline }
header .name { font:700 19px Georgia, serif; letter-spacing:.02em }
header a { color:#cfe6f5; text-decoration:none } header a:hover { text-decoration:underline }
header .meta { margin-left:auto; color:#9fb6c6; font-size:13px }
main { max-width:1100px; margin:0 auto; padding:16px }
h1 { font:700 25px/1.25 Georgia, serif; margin:6px 0 10px } h2 { font:700 19px Georgia, serif; margin:26px 0 8px;
  border-bottom:1px solid var(--line); padding-bottom:4px } h3 { margin:16px 0 6px; font-size:16px }
a { color:var(--accent) } .id, .muted { color:var(--muted); font-size:12.5px }
.card { background:var(--card); border:1px solid var(--line); border-radius:6px; padding:10px 14px; margin:8px 0 }
.next { border-left:4px solid var(--accent) } .warn { background:#fff1c2; color:#4a3b00; border-color:#e2c35a }
.badge { display:inline-block; font-size:11.5px; font-weight:600; padding:1px 7px; border-radius:9px; color:#fff;
  background:var(--muted); vertical-align:1px; white-space:nowrap }
.badge.emerging{background:var(--emerging)} .badge.developing{background:var(--developing)} .badge.peak{background:var(--peak)}
.badge.resolving{background:var(--resolving)} .badge.faded{background:var(--faded)} .badge.closed{background:var(--closed)}
.badge.breaking{background:#b0361c} .badge.flag{background:#7a5ea8} .badge.fiction{background:#a8487a}
.badge.unaired{background:#c08a00} .badge.kept{background:var(--emerging)} .badge.broken{background:var(--peak)}
.badge.open{background:var(--developing)} .badge.lapsed{background:var(--faded)}
table { border-collapse:collapse; width:100% } td, th { text-align:left; vertical-align:top; padding:5px 8px;
  border-bottom:1px solid var(--line) } th { font-size:12.5px; color:var(--muted); font-weight:600 }
.wrap { overflow-x:auto }
form.filters { display:flex; flex-wrap:wrap; gap:8px; align-items:center; margin:8px 0 }
input[type=search], select { font:inherit; padding:4px 8px; border:1px solid var(--line); border-radius:4px;
  background:var(--card); color:var(--fg) } input[type=search] { min-width:240px }
button { font:inherit; padding:4px 12px; border-radius:4px; border:1px solid var(--line); background:var(--card); color:var(--fg) }
.tabs a { margin-right:10px } .tabs a.on { font-weight:700; color:var(--fg); text-decoration:none }
.day { font-weight:700; margin-top:14px } ul.beats { margin:4px 0 8px; padding-left:20px }
.script p { margin:6px 0 } .script .who { font-weight:700 } audio { height:28px; vertical-align:middle; max-width:260px }
.votes td:first-child { white-space:nowrap } pre.memo { white-space:pre-wrap; font:inherit; margin:0 }
details summary { cursor:pointer }
@media (max-width:640px) { header .meta { margin-left:0 } td, th { padding:4px 5px } input[type=search] { min-width:0; width:100% } }
"""

NAV = [("/", "Front page"), ("/threads", "Stories"), ("/days", "Days"), ("/archive", "Archive"),
       ("/council", "Council"), ("/bookings", "Bookings"), ("/people", "People"), ("/desk", "Desk")]


def page(files: Files, title: str, body: str) -> str:
    w = files.world.data if isinstance(files.world.data, dict) else {}
    meta = ""
    if w:
        saved = clock(files.world.key[0] / 1e9) if files.world.key else ""
        meta = (f"{esc(w.get('town', ''))} · broadcast day {esc(w.get('broadcast_day', ''))} · "
                f"{esc(nice_date(w.get('last_date', '')))}" + (f" · saved {saved}" if saved else ""))
    nav = " ".join(link(h, t) for h, t in NAV)
    warn = f'<div class="card warn">{esc(files.world.problem)}</div>' if files.world.problem else ""
    return (f"<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport "
            f'content="width=device-width,initial-scale=1"><title>{esc(title)} · Port Wexley stories</title>'
            f"<style>{CSS}</style></head><body><header><span class=name>Port Wexley stories</span>{nav}"
            f'<span class=meta>{meta}</span></header><main>{warn}{body}</main></body></html>')


# ----------------------------------------------------------------------------------------------- pages


def front(files: Files, town: Town, q: dict) -> str:
    w = town.w
    live = sorted((t for t in town.threads.values() if t.get("phase") in LIVE),
                  key=lambda t: (t.get("updated", ""), PHASE_ORDER.get(t.get("phase"), 9)), reverse=True)
    counts = defaultdict(int)
    for t in town.threads.values():
        counts[t.get("phase", "?")] += 1
    out = [f"<h1>{esc(w.get('town', 'Port Wexley'))}, {esc(nice_date(w.get('last_date', '')))}</h1>",
           '<p class="muted">' + " · ".join(f"{n} {esc(p)}" for p, n in sorted(counts.items(),
                                            key=lambda kv: PHASE_ORDER.get(kv[0], 9)))
           + f" · {len(town.archive)} pieces in the archive · {len(files.annals_days())} annals pages</p>"]
    out.append(f"<h2>On the board ({len(live)})</h2>")
    for t in live:
        out.append(f'<div class="card">{phase_badge(t)} <b>{thread_link(town, t["id"])}</b>'
                   f'<div>{esc(t.get("status", ""))}</div>'
                   f'<div class="muted">NEXT: {esc(short(t.get("next_development"), 260))}</div>'
                   f'<div class="muted">opened {esc(t.get("opened", ""))} · updated {esc(t.get("updated", ""))} · '
                   f'{t.get("mentions", 0)} mentions · {len(town.pieces.get(t["id"], []))} pieces held</div></div>')
    aired = [e for e in reversed(town.archive) if e.get("type") in ("bulletin", "field_report", "breaking", "special")
             and e.get("headline")][:15]
    out.append("<h2>Latest on air</h2>" + archive_table(town, aired))
    if w.get("headlines"):
        out.append("<h2>The ticker's headlines</h2><ul>" + "".join(f"<li>{esc(h)}</li>" for h in w["headlines"][:20])
                   + "</ul>")
    if w.get("senior_memo"):
        out.append(f"<h2>The senior editor's memo <span class=muted>{esc(w.get('senior_memo_at', ''))}</span></h2>"
                   f'<div class="card"><pre class=memo>{esc(w["senior_memo"])}</pre></div>'
                   + link("/desk", "The desk's rounds and the editors' meetings"))
    return page(files, "Front page", "".join(out))


def _matches(town: Town, t: dict, needle: str) -> bool:
    hay = [t.get("id", ""), t.get("title", ""), t.get("status", ""), t.get("next_development", "")]
    hay += [b.get("headline", "") + " " + b.get("status", "") for b in t.get("beats", [])]
    hay += [town.people.get(pid, {}).get("name", "") for pid in t.get("people", [])]
    return needle in " ".join(hay).lower()


def threads(files: Files, town: Town, q: dict) -> str:
    state = q.get("state", "live")
    needle = q.get("q", "").strip().lower()
    sort = q.get("sort", "updated")
    rows = list(town.threads.values())
    pick = {"live": lambda t: t.get("phase") in LIVE, "faded": lambda t: t.get("phase") == "faded",
            "closed": lambda t: t.get("phase") == "closed", "all": lambda t: True}.get(state, lambda t: True)
    rows = [t for t in rows if pick(t) and (not needle or _matches(town, t, needle))]
    key = {"opened": lambda t: (t.get("opened", ""), t["id"]), "mentions": lambda t: (t.get("mentions", 0), t["id"]),
           "updated": lambda t: (t.get("updated", ""), t.get("moved_ts", 0) or 0, t["id"])}.get(sort)
    rows.sort(key=key or (lambda t: t["id"]), reverse=True)
    tabs = " ".join(f'<a class="{"on" if s == state else ""}" href="{esc(url("/threads", state=s, q=q.get("q"), sort=sort))}">'
                    f"{label}</a>" for s, label in (("live", "Open"), ("faded", "Faded"), ("closed", "Closed"),
                                                    ("all", "All")))
    form = (f'<form class=filters method=get action="/threads"><input type=hidden name=state value="{esc(state)}">'
            f'<input type=search name=q value="{esc(q.get("q", ""))}" placeholder="Search titles, beats, NEXT, people">'
            f'<select name=sort>' + "".join(f'<option value={s}{" selected" if s == sort else ""}>{lab}</option>'
                                             for s, lab in (("updated", "Last moved"), ("opened", "Opened"),
                                                            ("mentions", "Most covered")))
            + "</select><button>Search</button></form>")
    trs = []
    for t in rows:
        trs.append(f"<tr><td>{phase_badge(t)}</td><td><b>{thread_link(town, t['id'])}</b>"
                   f'<div class="muted">{esc(short(t.get("next_development"), 200))}</div></td>'
                   f"<td>{esc(t.get('opened', ''))}</td><td>{esc(t.get('updated', ''))}</td>"
                   f"<td>{t.get('mentions', 0)}</td><td>{len(town.pieces.get(t['id'], []))}</td></tr>")
    table = (f'<div class=wrap><table><tr><th>Phase</th><th>Story and NEXT</th><th>Opened</th><th>Updated</th>'
             f"<th>Mentions</th><th>Pieces held</th></tr>{''.join(trs)}</table></div>") if trs else "<p>No stories match.</p>"
    return page(files, "Stories", f"<h1>Stories</h1><div class=tabs>{tabs}</div>{form}"
                                  f'<p class=muted>{len(rows)} of {len(town.threads)} threads</p>{table}')


def archive_table(town: Town, entries: list[dict], *, show_date: bool = True, show_thread: bool = True) -> str:
    if not entries:
        return "<p class=muted>None held.</p>"
    trs = []
    for e in entries:
        flags = ""
        if e.get("fiction"):
            flags += " " + badge("fiction")
        if e.get("aired") is False:
            flags += " " + badge("not yet aired", "unaired")
        head = e.get("headline") or short(e.get("text"), 90) or e.get("type", "")
        h = e.get("hash")
        title = link(f"/piece/{h}", head) if h and _HASH.match(h) else esc(head)
        when = (esc(e.get("date", "")) + " " if show_date else "") + clock(e.get("ts"))
        thr = f'<div class="muted">{thread_link(town, e["thread_id"])}</div>' if show_thread and e.get("thread_id") else ""
        trs.append(f"<tr><td>{when}</td><td>{esc(e.get('show', ''))}</td><td>{esc(e.get('type', ''))}</td>"
                   f"<td>{title}{flags}{thr}</td></tr>")
    return ("<div class=wrap><table><tr><th>When</th><th>Show</th><th>Item</th><th>Headline</th></tr>"
            + "".join(trs) + "</table></div>")


def thread_page(files: Files, town: Town, tid: str) -> tuple[int, str]:
    w = town.w
    t = town.threads.get(tid)
    family = {tid} | set(town.merged_from.get(tid, []))
    pieces = town.pieces.get(tid, [])              # a merged thread's pieces are filed under the story it joined
    days = files.annals_days()
    annals_hits = []
    for d in days:
        p = files.annals_page(d) or {}
        for s in p.get("stories", []):
            if s.get("thread_id") in family:
                annals_hits.append((d, s))
    booked = bookings_for(town, family)
    if not t and not pieces and not annals_hits and not booked:
        return 404, page(files, "Not found", f"<h1>No story {esc(tid)}</h1><p>Not in this world, its archive, its "
                                             f"bookings or the annals. {link('/threads?state=all', 'All stories')}</p>")
    out = []
    if t:
        out.append(f"<h1>{esc(t.get('title', tid))}</h1><p>{phase_badge(t)} <span class=id>{esc(tid)}</span> · "
                   f"opened {esc(nice_date(t.get('opened', '')))} · last moved {esc(nice_date(t.get('updated', '')))}"
                   f" · {t.get('mentions', 0)} mentions</p>")
        if t.get("merged_into"):
            out.append(f'<div class="card warn">Closed as a duplicate of '
                       f'{thread_link(town, town.root(t["merged_into"]))}: its pieces are there.</div>')
        out.append(f'<div class=card><b>Where it stands:</b> {esc(t.get("status", ""))}</div>')
        if t.get("next_development"):
            out.append(f'<div class="card next"><b>NEXT:</b> {esc(t["next_development"])}</div>')
        if t.get("people"):
            out.append("<h2>People</h2><ul>" + "".join(
                f"<li>{link('/person/' + pid, town.people[pid].get('name', pid))} "
                f"<span class=muted>{esc(town.people[pid].get('role', ''))}</span></li>" if pid in town.people
                else f"<li>{esc(pid)}</li>" for pid in t["people"]) + "</ul>")
        if town.merged_from.get(tid):
            out.append("<p class=muted>Also folded in: " + ", ".join(thread_link(town, m) for m in town.merged_from[tid])
                       + "</p>")
        beats = t.get("beats", [])
        if beats:
            out.append(f"<h2>Beats ({len(beats)})</h2>")
            by_day: dict[str, list[dict]] = defaultdict(list)
            for b in beats:
                by_day[b.get("date", "")].append(b)
            for d in sorted(by_day, reverse=True):
                items = []
                for b in by_day[d]:
                    s = f" <span class=muted>{esc(b['status'])}</span>" if b.get("status") else ""
                    items.append(f"<li><b>{esc(b.get('headline', ''))}</b>{s}</li>")
                out.append(f'<div class=day>{link("/day/" + d, nice_date(d)) if _DATE.match(d) else esc(d)}</div>'
                           f"<ul class=beats>{''.join(items)}</ul>")
    else:
        out.append(f"<h1>{esc(town.thread_title(tid) or tid)}</h1><div class='card warn'>Thread <b>{esc(tid)}</b> is no "
                   f"longer in this world (pruned); this is what the archive and the annals still hold of it.</div>")
    out.append(f"<h2>Pieces the archive still holds ({len(pieces)})</h2>"
               + archive_table(town, list(reversed(pieces)), show_thread=False))
    if booked:
        out.append("<h2>Booked on it</h2>" + booked)
    if annals_hits:
        out.append("<h2>In the annals</h2>")
        for d, s in annals_hits:
            out.append(f'<div class=card>{link("/day/" + d, nice_date(d))} · {badge(s.get("phase", "?"))} · '
                       f'{s.get("pieces", 0)} pieces<ul class=beats>'
                       + "".join(f"<li>{esc(b)}</li>" for b in s.get("beats", [])) + "</ul></div>")
    planned = [n for n in w.get("desk_notes", []) if tid in (n.get("planned") or [])]
    if planned:
        out.append("<h2>On the desk's rounds</h2>" + "".join(
            f'<div class=card><span class=muted>{esc(n.get("at", ""))}</span> {esc(n.get("note", ""))}</div>'
            for n in reversed(planned)))
    title = t.get("title", tid) if t else tid
    return 200, page(files, title, "".join(out))


def bookings_for(town: Town, family: set[str]) -> str:
    """Everything booked on a story: council motions and promises, The Inquiry, The Panel, Have Your Say,
    documentaries, specials."""
    w = town.w
    out = []
    for c in w.get("chambers", []):
        for m in c.get("motions", []):
            if m.get("thread_id") in family:
                out.append(f"<h3>The Chamber, {link('/day/' + c.get('date', ''), nice_date(c.get('date', '')))}</h3>"
                           + motion_card(town, m))
    pr = [p for p in w.get("promises", []) if p.get("thread_id") in family]
    if pr:
        out.append("<h3>The council's promises</h3>" + promises_table(town, pr, with_thread=False))
    for i in w.get("inquiries", []):
        if i.get("thread_id") in family:
            out.append(f"<div class=card><b>The Inquiry</b> {esc(nice_date(i.get('date', '')))}: {esc(i.get('title', ''))}"
                       f"<div class=muted>guest {person_link(town, i.get('guest', ''))}"
                       f"{' (stand-in)' if i.get('stand_in') else ''} · {esc(i.get('angle', ''))}</div></div>")
    for p in w.get("panels", []):
        for qn in p.get("questions", []):
            if qn.get("thread_id") in family:
                out.append(f"<div class=card><b>The Panel</b> {esc(nice_date(p.get('date', '')))}: "
                           f"{esc(qn.get('question', ''))}</div>")
    for p in w.get("phone_ins", []):
        if p.get("thread_id") in family:
            out.append(f"<div class=card><b>Have Your Say</b> {esc(nice_date(p.get('date', '')))}: "
                       f"{esc(p.get('question', ''))}<div class=muted>guest {person_link(town, p.get('guest', ''))}</div></div>")
    for d in w.get("documentaries", []):
        if d.get("thread_id") in family:
            out.append(f"<div class=card><b>Documentary</b> {esc(nice_date(d.get('date', '')))}: "
                       f"<b>{esc(d.get('title', ''))}</b><div>{esc(d.get('standfirst', ''))}</div></div>")
    for s in w.get("specials", []):
        if s.get("thread_id") in family:
            out.append(f"<div class=card><b>Special</b> {esc(nice_date(s.get('date', '')))}: {esc(s.get('title', ''))}</div>")
    return "".join(out)


def piece_page(files: Files, town: Town, h: str) -> tuple[int, str]:
    entries = [e for e in town.archive if e.get("hash") == h]
    seg = files.segment(h)
    if not entries and not seg:
        return 404, page(files, "Not found", f"<h1>No piece {esc(h)}</h1><p>Neither the archive nor the cache has it.</p>")
    e = entries[-1] if entries else {}
    head = e.get("headline") or (seg or {}).get("headline") or e.get("type") or "A piece"
    tid = e.get("thread_id") or (seg or {}).get("thread_id")
    out = [f"<h1>{esc(head)}</h1><p class=muted>"
           + " · ".join(x for x in (link("/day/" + e["date"], nice_date(e["date"])) if e.get("date") else "",
                                    esc(clock(e.get("ts"))), esc(e.get("show") or (seg or {}).get("show", "")),
                                    esc(e.get("type") or (seg or {}).get("type", ""))) if x)
           + (" " + badge("fiction") if e.get("fiction") else "")
           + (" " + badge("not yet aired", "unaired") if e.get("aired") is False else "") + "</p>"]
    if tid:
        out.append(f"<p>Story: {thread_link(town, tid)}</p>")
    if e.get("brief") or (seg or {}).get("brief"):
        out.append(f'<div class=card><b>Brief:</b> {esc(e.get("brief") or seg.get("brief"))}</div>')
    if e.get("people"):
        out.append("<p>With " + ", ".join(link("/person/" + pid, town.people[pid].get("name", pid))
                                         if pid in town.people else esc(pid) for pid in e["people"]) + "</p>")
    if seg and seg.get("lines"):
        out.append("<h2>As it went out</h2><div class='card script'>")
        for n, line in enumerate(seg["lines"]):
            if not isinstance(line, dict):
                continue
            wav = Path(str(line.get("wav_path") or "")).name
            audio = ""
            if wav and _LINE_WAV.match(wav) and (files.cache / wav).exists():
                audio = f' <audio controls preload=none src="{esc("/audio/" + wav)}"></audio>'
            role = f" <span class=muted>({esc(line['guest_role'])})</span>" if line.get("guest_role") else ""
            mood = f" <span class=muted>[{esc(line['mood'])}]</span>" if line.get("mood") else ""
            out.append(f"<p><span class=who>{esc(town.speaker(line))}</span>{role}{mood}: {esc(line.get('text', ''))}"
                       f"{audio}</p>")
        out.append("</div>")
    elif e.get("text"):
        out.append("<h2>From the archive</h2><p class=muted>The cache no longer holds the full script; the archive "
                   f"keeps the opening.</p><div class=card>{esc(e['text'])}</div>")
    return 200, page(files, head, "".join(out))


def all_days(files: Files, town: Town) -> dict[str, dict]:
    days: dict[str, dict] = defaultdict(lambda: {"annals": False, "beats": 0, "pieces": 0, "booked": 0})
    for d in files.annals_days():
        days[d]["annals"] = True
    for t in town.threads.values():
        for b in t.get("beats", []):
            if _DATE.match(b.get("date", "")):
                days[b["date"]]["beats"] += 1
    for e in town.archive:
        if _DATE.match(e.get("date", "")):
            days[e["date"]]["pieces"] += 1
    w = town.w
    for key in ("chambers", "inquiries", "panels", "phone_ins", "rundowns", "documentaries", "specials"):
        for b in w.get(key, []):
            if isinstance(b, dict) and _DATE.match(b.get("date", "")):
                days[b["date"]]["booked"] += 1
    return days


def days_page(files: Files, town: Town, q: dict) -> str:
    days = all_days(files, town)
    trs = []
    for d in sorted(days, reverse=True):
        x = days[d]
        trs.append(f"<tr><td>{link('/day/' + d, nice_date(d))}</td><td>{'yes' if x['annals'] else ''}</td>"
                   f"<td>{x['beats'] or ''}</td><td>{x['pieces'] or ''}</td><td>{x['booked'] or ''}</td></tr>")
    return page(files, "Days", "<h1>Days</h1><p class=muted>The annals keep a page a day for good; the threads keep "
                               "their beats; the archive holds only the last thousand pieces (about three days).</p>"
                               "<div class=wrap><table><tr><th>Day</th><th>Annals page</th><th>Beats</th>"
                               "<th>Pieces held</th><th>Bookings</th></tr>" + "".join(trs) + "</table></div>")


def day_page(files: Files, town: Town, d: str) -> tuple[int, str]:
    if not _DATE.match(d):
        return 404, page(files, "Not found", f"<h1>No day {esc(d)}</h1>")
    w = town.w
    out = [f"<h1>{esc(nice_date(d))}</h1>"]
    p = files.annals_page(d)
    if p:
        out.append(f"<h2>The annals page</h2><p class=muted>{p.get('pieces', 0)} pieces on air"
                   + (" · this page failed when it was written" if p.get("failed") else "") + "</p>")
        for s in p.get("stories", []):
            ppl = ", ".join(person_link(town, n) for n in s.get("people", []))
            out.append(f'<div class=card>{badge(s.get("phase", "?"))} <b>{thread_link(town, s.get("thread_id", ""), s.get("title"))}</b>'
                       f' <span class=muted>{s.get("pieces", 0)} pieces</span><ul class=beats>'
                       + "".join(f"<li>{esc(b)}</li>" for b in s.get("beats", [])) + "</ul>"
                       + (f'<div class=muted>{ppl}</div>' if ppl else "")
                       + (f'<div class=muted>NEXT then: {esc(s["next"])}</div>' if s.get("next") else "") + "</div>")
        facts = [("Weather", p.get("weather")), ("Fish auction", p.get("auction")), ("Pub quiz", p.get("quiz"))]
        lists = [("Sport", p.get("sport")), ("Documentaries", p.get("documentaries")),
                 ("Promises made", p.get("promised")), ("Stories opened", p.get("opened")),
                 ("Stories closed", p.get("closed")), ("Headlines", p.get("headlines"))]
        for label, v in facts:
            if v:
                out.append(f"<p><b>{label}:</b> {esc(v)}</p>")
        if p.get("council"):
            out.append("<h3>Full council</h3><ul>" + "".join(
                f"<li>{esc(m.get('title') or m.get('motion', ''))}: {m.get('for', 0)}–{m.get('against', 0)}, "
                f"{'carried' if m.get('carried') else 'lost'}</li>" for m in p["council"]) + "</ul>")
        if p.get("settled"):
            out.append("<h3>Promises settled</h3><ul>" + "".join(
                f"<li>{badge(s.get('state', '?'))} {esc(s.get('text', ''))} <span class=muted>{esc(s.get('note', ''))}"
                f"</span></li>" for s in p["settled"]) + "</ul>")
        for label, v in lists:
            if v:
                out.append(f"<h3>{label}</h3><ul>" + "".join(f"<li>{esc(x)}</li>" for x in v) + "</ul>")
        if p.get("clips"):
            out.append("<h3>Keepsakes</h3>")
            for c in p["clips"]:
                wav = str(c.get("wav", ""))
                audio = (f'<audio controls preload=none src="{esc("/clip/" + wav)}"></audio>'
                         if _CLIP.match(wav) and (files.annals / "clips" / wav).exists() else "")
                who = c.get("guest_name") or c.get("who") or c.get("speaker", "")
                out.append(f'<div class=card><b>{esc(who)}</b>'
                           + (f" <span class=muted>{esc(c['guest_role'])}</span>" if c.get("guest_role") else "")
                           + f' · {esc(c.get("headline", ""))}<div>“{esc(c.get("text", ""))}”</div>{audio}</div>')
    moved = []
    for t in town.threads.values():
        bs = [b for b in t.get("beats", []) if b.get("date") == d]
        if bs:
            moved.append((t, bs))
    if moved:
        moved.sort(key=lambda tb: (-len(tb[1]), tb[0]["id"]))
        out.append(f"<h2>Stories that moved ({len(moved)})</h2>")
        for t, bs in moved:
            heads = list(dict.fromkeys(b.get("headline", "") for b in bs if b.get("headline")))
            out.append(f'<div class=card>{phase_badge(t)} <b>{thread_link(town, t["id"])}</b><ul class=beats>'
                       + "".join(f"<li>{esc(h)}</li>" for h in heads) + "</ul></div>")
    booked = day_bookings(town, d)
    if booked:
        out.append("<h2>Booked that day</h2>" + booked)
    held = [e for e in town.archive if e.get("date") == d]
    out.append(f"<h2>Pieces the archive still holds ({len(held)})</h2>"
               + (archive_table(town, held, show_date=False) if held else
                  "<p class=muted>None: the archive keeps only the last thousand pieces.</p>"))
    if not (p or moved or held or booked):
        return 404, page(files, d, out[0] + "<p>Nothing is kept of this day.</p>")
    return 200, page(files, nice_date(d), "".join(out))


def day_bookings(town: Town, d: str) -> str:
    w = town.w
    out = []
    for c in w.get("chambers", []):
        if c.get("date") == d:
            out.append(f"<h3>The Chamber</h3>" + "".join(motion_card(town, m) for m in c.get("motions", [])))
    for i in w.get("inquiries", []):
        if i.get("date") == d:
            out.append(f"<div class=card><b>The Inquiry:</b> {thread_link(town, i.get('thread_id', ''), i.get('title'))}"
                       f"<div class=muted>guest {person_link(town, i.get('guest', ''))}</div></div>")
    for p in w.get("panels", []):
        if p.get("date") == d:
            out.append(panel_card(town, p))
    for p in w.get("phone_ins", []):
        if p.get("date") == d:
            out.append(phonein_card(town, p))
    for r in w.get("rundowns", []):
        if r.get("date") == d:
            out.append(rundown_card(town, r))
    for x in w.get("documentaries", []):
        if x.get("date") == d:
            out.append(f"<div class=card><b>Documentary:</b> {esc(x.get('title', ''))} "
                       f"{thread_ref(town, x.get('thread_id', '')) if x.get('thread_id') else ''}"
                       f"<div>{esc(x.get('standfirst', ''))}</div></div>")
    for s in w.get("specials", []):
        if s.get("date") == d:
            out.append(f"<div class=card><b>Special:</b> {thread_link(town, s.get('thread_id', ''), s.get('title'))}</div>")
    return "".join(out)


def archive_page(files: Files, town: Town, q: dict) -> str:
    rows = list(reversed(town.archive))
    shows = sorted({e.get("show") or "" for e in rows} - {""})
    types = sorted({e.get("type") or "" for e in rows} - {""})
    dates = sorted({e.get("date") or "" for e in rows} - {""}, reverse=True)
    needle = q.get("q", "").strip().lower()
    if q.get("date"):
        rows = [e for e in rows if e.get("date") == q["date"]]
    if q.get("show"):
        rows = [e for e in rows if e.get("show") == q["show"]]
    if q.get("type"):
        rows = [e for e in rows if e.get("type") == q["type"]]
    if q.get("fiction") == "hide":
        rows = [e for e in rows if not e.get("fiction")]
    if needle:
        rows = [e for e in rows if needle in f"{e.get('headline', '')} {e.get('text', '')} {e.get('brief', '')}".lower()]
    try:
        n = max(0, int(q.get("page", "0")))
    except ValueError:
        n = 0
    shown = rows[n * PAGE:(n + 1) * PAGE]

    def sel(name, values, label):
        return (f'<select name={name}><option value="">{label}</option>'
                + "".join(f'<option{" selected" if q.get(name) == v else ""}>{esc(v)}</option>' for v in values)
                + "</select>")

    form = ('<form class=filters method=get action="/archive">'
            f'<input type=search name=q value="{esc(q.get("q", ""))}" placeholder="Search headlines and text">'
            + sel("date", dates, "Any day") + sel("show", shows, "Any show") + sel("type", types, "Any item")
            + f'<label><input type=checkbox name=fiction value=hide{" checked" if q.get("fiction") == "hide" else ""}>'
            " hide the soap</label><button>Filter</button></form>")
    nav = []
    base = {k: v for k, v in q.items() if k != "page"}
    if n:
        nav.append(link(url("/archive", **base, page=str(n - 1) if n > 1 else ""), "← newer"))
    if (n + 1) * PAGE < len(rows):
        nav.append(link(url("/archive", **base, page=str(n + 1)), "older →"))
    return page(files, "Archive", "<h1>The archive</h1><p class=muted>The last thousand pieces, newest first. "
                                  "Older days live on in the threads' beats and the annals.</p>" + form
                + f"<p class=muted>{len(rows)} pieces · {' · '.join(nav)}</p>" + archive_table(town, shown)
                + f"<p>{' · '.join(nav)}</p>")


def motion_card(town: Town, m: dict) -> str:
    result = "carried" if m.get("carried") else "lost"
    votes = "".join(f"<tr><td>{esc(v.get('councillor', ''))}</td><td>{esc(v.get('vote', ''))}</td>"
                    f"<td>{esc(v.get('why', ''))}</td></tr>" for v in m.get("votes", []))
    return (f"<div class=card><b>{esc(m.get('title') or '')}</b> {thread_ref(town, m.get('thread_id', '')) if m.get('thread_id') else ''}"
            f"<div>{esc(m.get('motion', ''))}</div><div class=muted>moved by {person_link(town, m.get('mover', ''))} · "
            f"{m.get('for', 0)} for, {m.get('against', 0)} against, {m.get('abstain', 0)} abstaining · "
            f"<b>{result}</b>{' on the casting vote' if m.get('casting') else ''}"
            f"{'' if m.get('applied') else ' · not yet applied to the town'}</div>"
            + (f"<div class=muted>The gallery: {esc(m['public'])}</div>" if m.get("public") else "")
            + f"<div class=muted>If carried: {esc(m.get('if_carried', ''))}<br>If lost: {esc(m.get('if_lost', ''))}</div>"
            + (f"<details><summary>The votes</summary><table class=votes>{votes}</table></details>" if votes else "")
            + "</div>")


def promises_table(town: Town, promises: list[dict], *, with_thread: bool = True) -> str:
    trs = "".join(f"<tr><td>{badge(p.get('state', '?'))}</td><td>{esc(p.get('text', ''))}"
                  + (f"<div class=muted>{thread_link(town, p.get('thread_id', ''))}</div>" if with_thread and p.get("thread_id") else "")
                  + (f"<div class=muted>{esc(p['note'])}</div>" if p.get("note") else "")
                  + f"</td><td>{esc(p.get('made', ''))}</td><td>{esc(p.get('due', ''))}</td><td>{esc(p.get('settled', ''))}</td></tr>"
                  for p in promises)
    return ("<div class=wrap><table><tr><th>State</th><th>Promise</th><th>Made</th><th>Due</th><th>Settled</th></tr>"
            + trs + "</table></div>")


def council_page(files: Files, town: Town, q: dict) -> str:
    w = town.w
    out = ["<h1>The council</h1>", "<h2>The council's promises</h2>"]
    pr = sorted(w.get("promises", []), key=lambda p: (p.get("state") != "open", p.get("due", "")))
    out.append(promises_table(town, pr) if pr else "<p class=muted>No promises held: none made yet, or all lapsed.</p>")
    out.append("<h2>The Chamber's nights</h2>")
    chambers = sorted(w.get("chambers", []), key=lambda c: c.get("date", ""), reverse=True)
    if not chambers:
        out.append("<p class=muted>No council nights yet.</p>")
    for c in chambers:
        out.append(f"<h3>{link('/day/' + c.get('date', ''), nice_date(c.get('date', '')))}</h3>"
                   + "".join(motion_card(town, m) for m in c.get("motions", [])))
    return page(files, "Council", "".join(out))


def panel_card(town: Town, p: dict) -> str:
    qs = "".join(f"<li>{esc(x.get('question', ''))} {thread_ref(town, x['thread_id']) if x.get('thread_id') else ''}</li>"
                 for x in p.get("questions", []))
    who = "".join(f"<li>{person_link(town, x.get('name', ''))} <span class=muted>{esc(x.get('stance', ''))}</span></li>"
                  for x in p.get("panellists", []))
    return f"<div class=card><b>The Panel</b> {esc(nice_date(p.get('date', '')))}<ol>{qs}</ol><ul>{who}</ul></div>"


def phonein_card(town: Town, p: dict) -> str:
    calls = "".join(f"<li>{esc(c)}</li>" for c in p.get("callers", []))
    return (f"<div class=card><b>Have Your Say</b> {esc(nice_date(p.get('date', '')))}: {esc(p.get('question', ''))} "
            f"{thread_ref(town, p['thread_id']) if p.get('thread_id') else ''}"
            f"<div class=muted>studio guest {person_link(town, p.get('guest', ''))}: {esc(p.get('guest_stance', ''))}</div>"
            + (f"<details><summary>{len(p.get('callers', []))} callers</summary><ul>{calls}</ul></details>" if calls else "")
            + "</div>")


def rundown_card(town: Town, r: dict) -> str:
    slots = r.get("slots") or {}
    def order(k):
        try:
            return int(k)
        except ValueError:
            return 999
    trs = "".join(f"<tr><td>{esc(k)}</td><td>{esc(v.get('type', ''))}</td><td>{esc(v.get('subject', ''))}"
                  + (f"<div class=muted>{person_link(town, v['guest'])}</div>" if v.get("guest") else "") + "</td></tr>"
                  for k, v in sorted(slots.items(), key=lambda kv: order(kv[0])) if isinstance(v, dict))
    return (f"<div class=card><b>{esc(r.get('title', ''))}</b> <span class=muted>{esc(r.get('show', ''))} · "
            f"{esc(nice_date(r.get('date', '')))}</span><div>{esc(r.get('theme', ''))}</div>"
            f"<details><summary>{len(slots)} items</summary><table><tr><th>Slot</th><th>Item</th><th>Subject</th></tr>"
            f"{trs}</table></details></div>")


def bookings_page(files: Files, town: Town, q: dict) -> str:
    w = town.w
    newest = lambda xs: sorted(xs, key=lambda x: x.get("date", ""), reverse=True)
    out = ["<h1>Bookings</h1>", "<h2>The Inquiry</h2>"]
    for i in newest(w.get("inquiries", [])):
        qs = "".join(f"<li>{esc(x)}</li>" for x in i.get("questions", []))
        out.append(f"<div class=card><b>{esc(nice_date(i.get('date', '')))}</b>: "
                   f"{thread_link(town, i.get('thread_id', ''), i.get('title'))}<div>{esc(i.get('angle', ''))}</div>"
                   f"<div class=muted>guest {person_link(town, i.get('guest', ''))}{' (stand-in)' if i.get('stand_in') else ''}"
                   f"</div><ol>{qs}</ol></div>")
    out.append("<h2>The Panel</h2>" + "".join(panel_card(town, p) for p in newest(w.get("panels", []))))
    out.append("<h2>Have Your Say</h2>" + "".join(phonein_card(town, p) for p in newest(w.get("phone_ins", []))))
    out.append("<h2>Running orders</h2>" + ("".join(rundown_card(town, r) for r in newest(w.get("rundowns", [])))
                                            or "<p class=muted>None held.</p>"))
    out.append("<h2>Documentaries</h2>")
    for d in newest(w.get("documentaries", [])):
        secs = "".join(f"<li><b>{esc(s.get('heading', ''))}</b>"
                       + (f" <span class=muted>with {esc(s['guest'])}</span>" if s.get("guest") else "") + "</li>"
                       for s in d.get("sections", []) if isinstance(s, dict))
        out.append(f"<div class=card><b>{esc(d.get('title', ''))}</b> <span class=muted>{esc(nice_date(d.get('date', '')))}</span> "
                   f"{thread_ref(town, d['thread_id']) if d.get('thread_id') else ''}<div>{esc(d.get('standfirst', ''))}</div>"
                   + (f"<details><summary>Sections</summary><ul>{secs}</ul></details>" if secs else "") + "</div>")
    out.append("<h2>Specials</h2><ul>" + "".join(
        f"<li>{esc(nice_date(s.get('date', '')))}: {thread_link(town, s.get('thread_id', ''), s.get('title')) if s.get('thread_id') else esc(s.get('title', ''))}</li>"
        for s in newest(w.get("specials", []))) + "</ul>")
    return page(files, "Bookings", "".join(out))


def people_page(files: Files, town: Town, q: dict) -> str:
    needle = q.get("q", "").strip().lower()
    rows = [p for p in town.people.values()
            if not needle or needle in f"{p.get('name', '')} {p.get('role', '')} {p.get('notes', '')}".lower()]
    rows.sort(key=lambda p: (-(p.get("appearances") or 0), p.get("name", "")))
    total = len(rows)
    rows = rows[:300]
    trs = "".join(f"<tr><td>{link('/person/' + p['id'], p.get('name', p['id']))}</td><td>{esc(p.get('role', ''))}</td>"
                  f"<td>{esc(p.get('kind', ''))}</td><td>{p.get('appearances', 0)}</td>"
                  f"<td>{len(town.person_threads.get(p['id'], []))}</td></tr>" for p in rows)
    form = (f'<form class=filters method=get action="/people"><input type=search name=q value="{esc(q.get("q", ""))}" '
            f'placeholder="Search names, roles, notes"><button>Search</button></form>')
    return page(files, "People", f"<h1>The town's people</h1>{form}<p class=muted>{total} match"
                                 f"{'; the 300 seen most on air are listed' if total > 300 else ''}</p>"
                                 "<div class=wrap><table><tr><th>Name</th><th>Role</th><th>Kind</th><th>Appearances</th>"
                                 f"<th>Stories</th></tr>{trs}</table></div>")


def person_page(files: Files, town: Town, pid: str) -> tuple[int, str]:
    p = town.people.get(pid)
    if not p:
        return 404, page(files, "Not found", f"<h1>No one called {esc(pid)}</h1>")
    out = [f"<h1>{esc(p.get('name', pid))}</h1><p>{esc(p.get('role', ''))} <span class=muted>· {esc(p.get('kind', ''))}"
           f" · first seen {esc(p.get('first_seen', ''))} · {p.get('appearances', 0)} appearances</span></p>"]
    if p.get("notes"):
        out.append(f"<div class=card>{esc(p['notes'])}</div>")
    tids = sorted(town.person_threads.get(pid, []), key=lambda t: town.threads[t].get("updated", ""), reverse=True)
    if tids:
        out.append("<h2>Stories</h2><ul>" + "".join(f"<li>{phase_badge(town.threads[t])} {thread_link(town, t)}</li>"
                                                    for t in tids) + "</ul>")
    if p.get("memories"):
        out.append("<h2>What they said on air</h2>" + "".join(
            f"<div class=card><span class=muted>{esc(m.get('date', ''))} · {esc(m.get('show', ''))}</span> "
            f"{esc(m.get('said', ''))}</div>" for m in reversed(p["memories"])))
    if p.get("loose_ends"):
        out.append("<h2>Loose ends</h2><ul>" + "".join(
            f"<li><span class=muted>{esc(m.get('date', ''))}</span> {esc(m.get('ask', ''))}</li>" for m in p["loose_ends"])
                   + "</ul>")
    held = [e for e in reversed(town.archive) if pid in (e.get("people") or [])]
    out.append(f"<h2>Pieces the archive still holds ({len(held)})</h2>" + archive_table(town, held))
    return 200, page(files, p.get("name", pid), "".join(out))


def desk_page(files: Files, town: Town, q: dict) -> str:
    w = town.w
    out = ["<h1>The desk</h1>"]
    if w.get("senior_memo"):
        out.append(f"<h2>The senior editor's memo <span class=muted>{esc(w.get('senior_memo_at', ''))}</span></h2>"
                   f"<div class=card><pre class=memo>{esc(w['senior_memo'])}</pre></div>")
    out.append("<h2>The story desk's rounds</h2>")
    for n in reversed(w.get("desk_notes", [])):
        planned = ", ".join(thread_link(town, t) for t in n.get("planned") or [])
        out.append(f"<div class=card><b>{esc(n.get('at', ''))}</b> <span class=muted>{n.get('new', 0)} new, "
                   f"{n.get('merges', 0)} merged</span><div>{esc(n.get('note', ''))}</div>"
                   + (f"<div class=muted>Planned: {planned}</div>" if planned else "") + "</div>")
    out.append("<h2>The editors' meetings</h2>")
    for m in sorted(w.get("meetings", []), key=lambda m: (m.get("date", ""), m.get("at", "")), reverse=True):
        mins = m.get("minutes") or {}
        turns = "".join(f"<div class=card><b>{esc(t.get('title') or t.get('seat', ''))}</b>"
                        f"<pre class=memo>{esc(t.get('says', ''))}</pre></div>" for t in m.get("turns", []))
        acts = "".join(f"<li><b>{esc(a.get('to', ''))}</b>{' (' + esc(a['about']) + ')' if a.get('about') else ''}: "
                       f"{esc(a.get('what', ''))}</li>" for a in mins.get("actions", []) if isinstance(a, dict))
        canon = "".join(f"<li>{esc(c)}</li>" for c in mins.get("canon", []))
        out.append(f"<h3>{esc(nice_date(m.get('date', '')))} {esc(m.get('at', ''))}</h3>"
                   + (f"<div class=card><b>Verdict:</b> {esc(mins['verdict'])}</div>" if mins.get("verdict") else "")
                   + (f"<b>Actions</b><ul>{acts}</ul>" if acts else "") + (f"<b>Canon</b><ul>{canon}</ul>" if canon else "")
                   + (f"<details><summary>The meeting, turn by turn</summary>{turns}</details>" if turns else ""))
    return page(files, "Desk", "".join(out))


# ----------------------------------------------------------------------------------------------- routing


def _file(path: Path, ctype: str) -> tuple[int, str, bytes]:
    try:
        with open(path, "rb") as f:          # read whole and closed at once: prune may want to delete it
            return 200, ctype, f.read()
    except OSError:
        return 404, "text/plain; charset=utf-8", b"not found"


def respond(files: Files, raw_path: str) -> tuple[int, str, bytes]:
    """(status, content type, body) for a request path with its query: the whole site, no network involved."""
    parts = urlsplit(raw_path)
    path = unquote(parts.path)
    q = {k: v[-1] for k, v in parse_qs(parts.query).items()}
    html_type = "text/html; charset=utf-8"
    seg = path.strip("/").split("/")
    if seg[0] == "clip" and len(seg) == 2:
        return _file(files.annals / "clips" / seg[1], "audio/wav") if _CLIP.match(seg[1]) else (404, "text/plain", b"no")
    if seg[0] == "audio" and len(seg) == 2:
        return _file(files.cache / seg[1], "audio/wav") if _LINE_WAV.match(seg[1]) else (404, "text/plain", b"no")
    if path == "/favicon.ico":
        return 204, "image/x-icon", b""
    town = files.town()
    if town is None:
        msg = files.world.problem or f"No world at {files.world_path}"
        return 503, html_type, page(files, "No world", f"<h1>No town to show</h1><p>{esc(msg)}</p>").encode()
    status, body = 200, None
    if path in ("/", ""):
        body = front(files, town, q)
    elif path == "/threads":
        body = threads(files, town, q)
    elif seg[0] == "thread" and len(seg) == 2 and _ID.match(seg[1]):
        status, body = thread_page(files, town, seg[1])
    elif seg[0] == "piece" and len(seg) == 2 and _HASH.match(seg[1]):
        status, body = piece_page(files, town, seg[1])
    elif path == "/days":
        body = days_page(files, town, q)
    elif seg[0] == "day" and len(seg) == 2:
        status, body = day_page(files, town, seg[1])
    elif path == "/archive":
        body = archive_page(files, town, q)
    elif path == "/council":
        body = council_page(files, town, q)
    elif path == "/bookings":
        body = bookings_page(files, town, q)
    elif path == "/people":
        body = people_page(files, town, q)
    elif seg[0] == "person" and len(seg) == 2 and _ID.match(seg[1]):
        status, body = person_page(files, town, seg[1])
    elif path == "/desk":
        body = desk_page(files, town, q)
    else:
        status, body = 404, page(files, "Not found", f"<h1>Nothing at {esc(path)}</h1>")
    return status, html_type, body.encode("utf-8")


class Handler(BaseHTTPRequestHandler):
    files: Files

    def do_GET(self):  # noqa: N802
        try:
            status, ctype, body = respond(self.files, self.path)
        except Exception as e:  # noqa: BLE001  - a page that trips on odd data must not take the browser down
            status, ctype = 500, "text/plain; charset=utf-8"
            body = f"This page tripped on the town's data: {type(e).__name__}: {e}".encode()
            self.log_error("%s on %s", repr(e), self.path)
        self.send_response(status)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store" if ctype.startswith("text/html") else "max-age=3600")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):
        pass                                                   # quiet: one line per request is noise


def serve(files: Files, host: str = "127.0.0.1", port: int = PORT) -> ThreadingHTTPServer:
    handler = type("BoundHandler", (Handler,), {"files": files})
    return ThreadingHTTPServer((host, port), handler)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Browse Port Wexley's stories, read-only, outside the station.")
    ap.add_argument("--world", type=Path, default=_env_path("NEWSROOM_WORLD", ROOT / "data" / "world.json"),
                    help="the world file (default data/world.json; a backup shows an older town)")
    ap.add_argument("--annals", type=Path, default=_env_path("NEWSROOM_ANNALS", ROOT / "data" / "annals"))
    ap.add_argument("--cache", type=Path, default=_env_path("NEWSROOM_CACHE", ROOT / "data" / "cache"),
                    help="where the pieces' full scripts and audio are")
    ap.add_argument("--port", type=int, default=PORT)
    a = ap.parse_args(argv)
    files = Files(a.world, a.annals, a.cache)
    server = serve(files, "127.0.0.1", a.port)
    print(f"Port Wexley stories: http://127.0.0.1:{server.server_port}/  (reading {a.world}; Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
