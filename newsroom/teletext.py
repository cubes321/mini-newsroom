"""SEVENTEXT: Channel 7's teletext pages, cycling overnight between the repeats (the user's idea,
2026-10-31), as British television filled the small hours in the 1980s.

A page is a 40 x 24 grid of character cells in teletext's eight colours: the header row (page number,
the service, the date and a running clock), a double-height banner, the page's own rows, and the four
coloured links along the bottom. Every word comes from what the station already knows, worked out in
code: the stories on the board, the weather, the tides and the ferry, the football table, the fish
auction, the day's schedule, the town's notices and what's on. No model call and no voice, so a block of pages
costs nothing and fills time the repeats leave over.

A `teletext` segment is one silent line of `PAGE_S` per page with the pages in `work["teletext"]`; the
player shows the page for the time into it, counting the header up to the new page number first, as a
set did while it searched.

    python -m newsroom.teletext            # print the pages as text
"""
from __future__ import annotations

import hashlib
import json
import logging
import textwrap
from datetime import date, datetime, timedelta

from . import calendar, council, promises, quay, safety, schedule, sport, tides

log = logging.getLogger(__name__)

NAME = "SEVENTEXT"
COLS, ROWS = 40, 24
CW, CH = 6, 7                       # a character cell on the 320 x 180 canvas
X0, Y0 = (320 - COLS * CW) // 2, (180 - ROWS * CH) // 2     # a 4:3 page in the middle of the frame
PAGE_S = 10.0                       # each page stays up this long
SEARCH_S = 1.2                      # the header counts up to it first
BODY = range(1, ROWS - 1)           # rows between the header and the links
COLOURS = {"black": (0, 0, 0), "red": (255, 40, 40), "green": (40, 230, 40), "yellow": (255, 255, 40),
           "blue": (40, 40, 255), "magenta": (255, 40, 255), "cyan": (40, 255, 255), "white": (255, 255, 255)}
LINKS = (("News", "red", 101), ("Weather", "green", 120), ("Sport", "yellow", 140), ("TV", "cyan", 160))
STORIES = 5                         # pages 102 to 106

# The coast for the weather map, a character cell each: land (#), sea (.), and a cell half land on its
# left (>) or right (<). The estuary runs up from the south-west; the town is on its eastern shore.
COAST = ("########################",
         "###########>.<##########",
         "##########>..<##########",
         "#########>...<##########",
         "#######>.....<##########",
         "####>........<##########",
         ">............<##########",
         "...............<########",
         "........................")
PLACES = ((13, 4, "PORT WEXLEY"), (1, 2, "SALTBY"), (2, 7, "Grey Estuary"))


def row(text: str = "", fg: str = "white", bg: str | None = None, dh: bool = False) -> dict:
    """One row of the page: text from the second column (the first holds teletext's colour codes)."""
    return {"t": text[:COLS - 1], "fg": fg, "bg": bg, "dh": dh}


def _wrap(text: str, width: int = COLS - 2) -> list[str]:
    return textwrap.wrap(" ".join(text.split()), width) or [""]


def _leader(left: str, num: int, fg: str = "white") -> dict:
    """'News headlines .............. 101'"""
    dots = COLS - 2 - len(left) - 4
    return row(f"{left} {'.' * max(1, dots - 1)} {num}", fg)


def _banner(title: str, fg: str, bg: str) -> list[dict]:
    return [row(f" {title}", fg, bg, dh=True), row()]


def _page(num: int, title: str, rows: list[dict], art: dict | None = None) -> dict:
    # The last look (safety.py): a page is read, never voiced, so tts.synthesize's check never sees it.
    # A row with a blocked word goes out blank; the page keeps its shape.
    for i, r in enumerate(rows):
        if bad := safety.check(r.get("t", "")):
            log.warning("content check: %r on teletext page %d; that row is left blank", bad, num)
            rows[i] = row()
    page = {"num": num, "title": title, "rows": rows, "art": art}
    page["key"] = hashlib.sha1(json.dumps(page, sort_keys=True).encode()).hexdigest()[:12]
    return page


def height(rows: list[dict]) -> int:
    """The rows a page's body takes: two for a double-height one, an art block its own."""
    return sum(r.get("h", 2 if r.get("dh") else 1) for r in rows)


# ------------------------------------------------------------------- pages


def _stories(world) -> list:
    """The stories most recently on air, newest first. One with a blocked word in what the pages would
    print is left out whole: checked here, before wrapping can split a phrase across two rows."""
    def clean(t) -> bool:
        bad = safety.check([t.title, t.status] + [b.get("headline") or "" for b in t.beats])
        if bad:
            log.warning("content check: %r in story %s; kept off teletext", bad, t.id)
        return not bad
    recent = sorted(world.open_threads(), key=lambda t: (t.moved_ts, t.mentions), reverse=True)
    return [t for t in recent if clean(t)][:STORIES]


def _index(now: datetime) -> dict:
    rows = _banner(NAME, "yellow", "blue") + [
        row(f"Port Wexley and the Greymouth coast", "cyan"),
        row(f"{now:%A %d %B %Y}", "white"), row(),
        _leader("News headlines", 101, "yellow"), _leader("Weather", 120), _leader("Tides and ferry", 130),
        _leader("Sport", 140), _leader("The fish quay", 150), _leader("On Channel 7 today", 160),
        _leader("Notices", 170), _leader("Council watch", 175), _leader("What's on", 180), row(),
        row("Programmes return at six with", "green"), row("Morning Tide.", "green")]
    return _page(100, "INDEX", rows)


def _headlines(stories: list) -> dict:
    rows = _banner("NEWS", "white", "red")
    for i, t in enumerate(stories):
        head = _wrap(t.title, COLS - 7)
        rows.append(row(f"{head[0]:<{COLS - 7}} {102 + i}", "yellow" if i == 0 else "white"))
        for more in head[1:2]:
            rows.append(row(f" {more}", "cyan"))
        rows.append(row())
    return _page(101, "NEWS", rows[:ROWS - 2])


def _story(t, num: int) -> dict:
    rows = _banner("NEWS", "white", "red")
    for line in _wrap(t.title, COLS - 2)[:2]:
        rows.append(row(line, "yellow"))
    rows.append(row())
    for line in _wrap(t.status)[:6]:
        rows.append(row(line, "white"))
    seen, earlier = {t.title.lower()}, []
    for b in reversed(t.beats):                               # the newest first, each headline once, not the title
        h = (b.get("headline") or "").strip()
        if h and h.lower() not in seen and len(earlier) < 3:
            seen.add(h.lower())
            earlier.append(b)
    earlier.reverse()
    if earlier:
        rows += [row(), row("EARLIER", "cyan")]
        for b in reversed(earlier):
            try:
                day = f"{date.fromisoformat(b.get('date', '')):%a}: "
            except ValueError:
                day = ""
            for line in _wrap(f"{day}{b['headline']}")[:2]:
                rows.append(row(line, "white"))
    return _page(num, "NEWS", rows[:ROWS - 3])


_SKY_WORDS = {"sunny": "Sunny spells", "cloudy": "Cloudy", "rain": "Showers", "storm": "Gales and heavy rain",
              "snow": "Snow", "fog": "Fog patches", "wind": "Windy", None: "Settled"}


def _weather(world, now: datetime) -> dict:
    state, temp = world.last_weather.get("map_state"), world.last_weather.get("temp_c")
    rows = _banner("WEATHER", "white", "green") + [
        {"art": "map", "h": len(COAST), "state": state}, row(),
        row(f"{_SKY_WORDS.get(state, 'Settled')}" + (f", {temp}C" if temp is not None else ""), "yellow", dh=True),
        row("The latest forecast from Gordon Pell.", "white")]
    return _page(120, "WEATHER", rows)


def _tides(day: date, state: str | None) -> dict:
    rows = _banner("TIDES AND FERRY", "white", "blue")
    rows.append(row(f"Port Wexley, {day:%A %d %B}", "cyan"))
    rows.append(row())
    for t, kind, h in tides.tides(day):
        rows.append(row(f"{'High water' if kind == 'high' else 'Low water':<14}{t:%H:%M}   {h:.1f} m",
                        "yellow" if kind == "high" else "white"))
    rows.append(row())
    f = tides.ferry(day, state)
    rows.append(row("SALTBY FOOT FERRY", "cyan"))
    if f["suspended"]:
        rows.append(row(f["suspended"].capitalize(), "red"))
    elif f["sailings"]:
        rows.append(row(f"Every half hour from {f['sailings'][0]:%H:%M}", "white"))
        rows.append(row(f"Last crossing {f['sailings'][-1]:%H:%M}", "white"))
        for a, b in f["gaps"]:
            rows.append(row(f"No crossings {a:%H:%M} to {b:%H:%M}", "yellow"))
        rows.append(row("(low water)", "white"))
    return _page(130, "TIDES", rows)


def _sport(now: datetime) -> dict:
    rows = _banner("SPORT", "black", "yellow")
    said = sport.summary(now).split(": ", 1)[-1].rstrip(".")    # the Tides' last result; next; position
    for part in said.split("; ")[:2]:
        for line in _wrap(part[:1].upper() + part[1:] + ".")[:2]:
            rows.append(row(line, "cyan"))
    rows += [row(), row(f"{sport.LEAGUE[:30]:<30}  P Pts", "yellow")]
    for i, r in enumerate(sport.table(now)[:9], 1):
        rows.append(row(f"{i:>2} {r['club'][:25]:<26} {r['p']:>2} {r['pts']:>3}",
                        "green" if r["club"] == sport.CLUB else "white"))
    return _page(140, "SPORT", rows)


def _quay(now: datetime) -> dict:
    rows = _banner("THE FISH QUAY", "white", "blue")
    a = quay.latest(now)
    if not a:
        return _page(150, "QUAY", rows + [row("No auction this week.", "white")])
    rows.append(row(f"The auction, {a.day:%A %d %B}", "cyan"))
    rows.append(row(f"{len(a.boats)} of {len(quay.FLEET)} boats out" + (", a rough day" if a.rough else ""), "white"))
    rows += [row(), row(f"{'':<16}{'kg':>7}  {'per kilo':>9}", "yellow")]
    for lot in a.lots[:7]:
        rows.append(row(f"{lot.species.capitalize():<16}{lot.kilos:>7,}  {quay._money(lot.price):>9}", "white"))
    rows += [row(), row(f"Sold in all {quay._money(a.total)}", "green")]
    if a.best_boat[0]:
        rows.append(row(f"Best boat {a.best_boat[0]} ({a.best_boat[1]})", "white"))
    return _page(150, "QUAY", rows)


def _title(t: str) -> str:
    """'OUT AND ABOUT' -> 'Out and About'."""
    words = t.lower().split()
    return " ".join(w if i and w in ("and", "the", "of", "on", "in") else w.capitalize() for i, w in enumerate(words))


def _schedule(day: date) -> dict:
    rows = _banner("ON CHANNEL 7 TODAY", "white", "magenta")
    six = datetime.combine(day, datetime.min.time()).replace(hour=6).timestamp()
    shown = set()
    for ts, _ in schedule.starts(six, days=1):
        show = schedule.show_at(ts)
        if ts < six or ts in shown or show.id == "overnight":
            continue
        shown.add(ts)
        rows.append(row(f"{datetime.fromtimestamp(ts):%H:%M}  {_title(show.title)}",
                        "yellow" if show.id != "news" else "white"))
    if council.meets_on(day):
        rows += [row(), row("Full council live at eight tonight.", "cyan")]
    return _page(160, "TV", rows[:ROWS - 2])


def _notices(day: date) -> dict:
    from .continuity import NOTICES

    rows = _banner("NOTICES", "white", "cyan")
    for title, lines in list(NOTICES.values())[:3]:
        rows.append(row(title, "yellow"))
        said = lines[0]
        for more in lines[1:]:                                # whole sentences, as many as fit three rows
            if len(_wrap(f"{said} {more}")) <= 3:
                said = f"{said} {more}"
        for line in _wrap(said)[:3]:
            rows.append(row(line, "white"))
        rows.append(row())
    for line in _wrap(council.calendar_line(day))[:3]:
        rows.append(row(line, "cyan"))
    return _page(170, "NOTICES", rows[:ROWS - 2])


def _council_watch(world, day: date) -> dict:
    """What full council voted would happen, and whether it has (promises.py): the open ones first, the
    overdue at the top, then the latest verdicts."""
    rows = _banner("COUNCIL WATCH", "black", "yellow")
    n = promises.tally(world)
    rows.append(row(f"Promised at full council: {n['kept']} kept,", "cyan"))
    rows.append(row(f"{n['broken']} broken, {n['open']} still to come.", "cyan"))
    rows.append(row())
    board = promises.board(world, day)
    if not board:
        rows.append(row("Nothing promised yet. Full council", "white"))
        rows.append(row("meets every other Thursday at eight.", "white"))
    for label, colour, p in board:
        block = [row(label, colour)] + [row(line, "white") for line in _wrap(p["text"])[:2]]
        if height(rows + block) > len(BODY) - 1:
            break
        rows += block
    return _page(175, "COUNCIL", rows)


def _whats_on(day: date) -> dict:
    """The coming week from the calendar (calendar.coming_up): the town's events, full council and the matches,
    a day at a time, as many whole days as fit."""
    rows = _banner("WHAT'S ON", "white", "green")
    by_day: dict[date, list[str]] = {}
    for c in calendar.coming_up(day, 8):
        by_day.setdefault(c.day, []).append(c.brief)
    for d, texts in by_day.items():
        block = [row("Today" if d == day else f"{d:%A} {d.day} {d:%B}", "yellow")]
        for t in texts:
            block += [row(line, "white") for line in _wrap(t)[:3]]
        if height(rows + block) > len(BODY) - 1:
            break
        rows += block
    return _page(180, "WHAT'S ON", rows)


def pages(world, now: datetime | None = None) -> list[dict]:
    """Every page, in the order the service turns them."""
    now = now or datetime.fromtimestamp(schedule.now())
    stories = _stories(world)
    state = world.last_weather.get("map_state")
    out = [_index(now), _headlines(stories)] + [_story(t, 102 + i) for i, t in enumerate(stories)]
    return out + [_weather(world, now), _tides(now.date(), state), _sport(now), _quay(now),
                  _schedule(now.date()), _notices(now.date()), _council_watch(world, now.date()),
                  _whats_on(now.date())]


def segment(seg, world):
    """Turn a planned teletext slot into a ready one: the pages, and one silent line to time them by."""
    from .assets import testcard_segment
    from .models import SegmentState

    seg.work["teletext"] = {"pages": pages(world, datetime.fromtimestamp(seg.nominal_start_ts or schedule.now()))}
    seg.target_s = PAGE_S * len(seg.work["teletext"]["pages"])
    seg = testcard_segment(seg)
    seg.state = SegmentState.ready
    return seg


def on_screen(work: dict, elapsed: float) -> tuple[dict, int, float]:
    """The page up `elapsed` seconds in, the page before it, and how long it has been up."""
    ps = work.get("pages") or []
    if not ps:
        return {}, 100, 0.0
    i = int(max(0.0, elapsed) // PAGE_S) % len(ps)
    return ps[i], ps[i - 1]["num"] if i else 100, max(0.0, elapsed) - (int(max(0.0, elapsed) // PAGE_S)) * PAGE_S


def header(num: int, now: datetime, showing: int | None = None) -> str:
    """'P101 SEVENTEXT 101 Sun 01 Nov 02:14/33': the page asked for, the page on (counting up to it
    while the set searches), the date, the clock."""
    return f"P{num:<3} {NAME} {num if showing is None else showing} {now:%a %d %b} {now:%H:%M/%S}"


# ------------------------------------------------------------------- drawing

_glyphs: dict = {}
_fonts: dict = {}


def _glyph(ch: str, fg: str, dh: bool, k: int):
    """One character at the window's size, stretched to its cell like a teletext set's narrow, tall
    letters; double height is the same letter stretched over two rows."""
    import pygame

    key = (ch, fg, dh, k)
    if key not in _glyphs:
        if k not in _fonts:
            _fonts[k] = pygame.font.SysFont("consolas,lucidaconsole,couriernew,dejavusansmono", CH * k, bold=True)
        g = _fonts[k].render(ch, True, COLOURS[fg])
        _glyphs[key] = pygame.transform.smoothscale(g, (CW * k, CH * k * (2 if dh else 1)))
    return _glyphs[key]


def _text_surface(rows: list[tuple[int, int, str, str, bool]], k: int):
    """The page's characters at the window's size: (row, column, text, colour, double) each."""
    import pygame

    s = pygame.Surface((COLS * CW * k, ROWS * CH * k), pygame.SRCALPHA)
    for r, c, text, fg, dh in rows:
        for i, ch in enumerate(text):
            if ch != " " and c + i < COLS:
                s.blit(_glyph(ch, fg, dh, k), ((c + i) * CW * k, r * CH * k))
    return s


def _layout(page: dict) -> tuple[list, list, list]:
    """Where everything goes: the text runs, the background bars and the art blocks, by grid row."""
    text, bars, art = [], [], []
    r = BODY.start
    for item in page.get("rows", []):
        h = item.get("h", 2 if item.get("dh") else 1)
        if r + h > BODY.stop:
            break
        if "art" in item:
            art.append((r, item))
        else:
            if item.get("bg"):
                bars.append((r, h, item["bg"]))
            if item.get("t"):
                text.append((r, 1, item["t"], item.get("fg", "white"), bool(item.get("dh"))))
        r += h
    col = 1
    for word, colour, _ in LINKS:
        text.append((ROWS - 1, col, word, colour, False))
        col += len(word) + 3
    return text, bars, art


def _draw_map(canvas, r: int, item: dict) -> list:
    """The coast in sea and land blocks, the weather over the land, and the places named."""
    import pygame

    sea, land = COLOURS["blue"], COLOURS["green"]
    for y, line in enumerate(COAST):
        for x, ch in enumerate(line):
            cx, cy = X0 + (x + 8) * CW, Y0 + (r + y) * CH
            pygame.draw.rect(canvas, sea, (cx, cy, CW, CH))
            if ch == "#":
                pygame.draw.rect(canvas, land, (cx, cy, CW, CH))
            elif ch == ">":
                pygame.draw.rect(canvas, land, (cx, cy, CW // 2, CH))
            elif ch == "<":
                pygame.draw.rect(canvas, land, (cx + CW // 2, cy, CW // 2, CH))
    state = item.get("state")
    sx, sy = X0 + 26 * CW, Y0 + r * CH + 2                    # the symbol, over the land to the north-east
    if state in ("sunny", None):
        pygame.draw.rect(canvas, COLOURS["yellow"], (sx, sy, CW * 3, CH * 2))
        for dx, dy in ((-CW, CH // 2), (CW * 3, CH // 2), (CW, -CH // 2 - 1), (CW, CH * 2)):
            pygame.draw.rect(canvas, COLOURS["yellow"], (sx + dx, sy + dy, CW, CH // 2 + 1))
    else:
        cloud = COLOURS["white"] if state != "storm" else (150, 150, 150)
        pygame.draw.rect(canvas, cloud, (sx, sy + CH // 2, CW * 4, CH + 2))
        pygame.draw.rect(canvas, cloud, (sx + CW, sy - 1, CW * 2, CH // 2 + 2))
        if state in ("rain", "storm"):
            for i in range(4):
                pygame.draw.rect(canvas, COLOURS["cyan"], (sx + i * CW + 2, sy + CH * 2 + 1 + (i % 2) * 2, 2, 3))
        elif state == "snow":
            for i in range(4):
                pygame.draw.rect(canvas, COLOURS["white"], (sx + i * CW + 2, sy + CH * 2 + 2 + (i % 2) * 2, 2, 2))
    return [(r + y, 8 + x, name, "white" if y < 6 else "cyan", False) for x, y, name in PLACES]


def draw(canvas, page: dict, prev: int, since: float, now: datetime, queue) -> None:
    """Paint the page on the canvas (black, the bars, the art) and queue its letters at full size with
    `queue(key, make(k), at)`; in the first SEARCH_S only the header, counting up to the page."""
    import pygame

    canvas.fill((0, 0, 0))
    num = page.get("num", 100)
    searching = since < SEARCH_S
    shown = prev + round((num - prev) * since / SEARCH_S) if searching and num > prev else num
    head = header(num, now, shown)
    queue(("tth", head), lambda k: _text_surface([(0, 0, head[:COLS], "white", False)], k), (X0, Y0))
    if searching:
        return
    text, bars, art = _layout(page)
    for r, h, bg in bars:
        pygame.draw.rect(canvas, COLOURS[bg], (X0, Y0 + r * CH, COLS * CW, h * CH))
    for r, item in art:
        if item["art"] == "map":
            text += _draw_map(canvas, r, item)
    queue(("ttp", page.get("key")), lambda k: _text_surface(text, k), (X0, Y0))


if __name__ == "__main__":
    from . import world as world_mod

    for p in pages(world_mod.load()):
        print(f"\n--- P{p['num']} {p['title']} ({height(p['rows'])} rows)")
        for r in p["rows"]:
            print("  [art]" if "art" in r else f"  {r['t']}")
