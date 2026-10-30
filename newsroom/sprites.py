"""Programmatic pixel characters.

Everything is drawn onto a low-resolution canvas (see scenes.CANVAS) and
scaled up with nearest-neighbour, so a 2x3 rectangle here is a chunky
pixel block on screen.

A character is a `Look`: a handful of knobs (hair, facial hair, glasses,
clothes, one accessory) drawn in whole units of `scale`, so the same look
works at scale 1 in the reporter box and at scale 4 in the close-up. The
presenters' looks are written out in LOOKS; a guest's look is worked out
from their name, voice and role (`guest_look`), so every resident and
celebrity gets one of their own, the same every time they appear.

Geometry is in units from the top centre of the head, for a character
facing right; facing left mirrors it. The footprint is 26 units wide and
37 high (head 14, neck 3, body 20) with the bottom at the baseline. Hair
and hats may reach 4 units above the head and 1-2 units past the shoulders.

    python -m newsroom.sprites --sheet out.png     # every presenter and a crowd of guests
"""
from __future__ import annotations

import math
import zlib
from dataclasses import dataclass, replace
from functools import lru_cache

import pygame

RGB = tuple[int, int, int]

OUTLINE_K = 0.45                 # outlines are the fill colour this dark
EYE = (20, 20, 30)
WHITE = (240, 240, 236)
INNER = (90, 30, 40)             # the open mouth
GOLD = (220, 180, 60)


@dataclass(frozen=True)
class Look:
    skin: RGB
    hair: RGB
    top: RGB                       # jacket, jumper, cardigan...
    under: RGB                     # the shirt or top at the neck
    hair_style: str = "short"      # short crop bob long ponytail bun curly swept unruly receding bald
    top_style: str = "blazer"      # blazer suit jumper cardigan jacket tshirt uniform chef
    tie: RGB | None = None
    facial: str = ""               # stubble beard moustache
    glasses: str = ""              # on up shades
    hat: str = ""                  # cap beanie flatcap peaked
    hat_col: RGB = (40, 50, 80)
    extra: str = ""                # lanyard pen chain collar earrings stripe apron hivis tape scarf soot towel yoke
    extra_col: RGB = GOLD
    mouth: str = "line"            # line smile smirk
    brows: str = ""                # raised
    temples: RGB | None = None     # greying at the sides
    freckles: bool = False
    tweed: bool = False


def _dark(c: RGB, k: float) -> RGB:
    return tuple(max(0, min(255, int(v * k))) for v in c)


def _mix(a: RGB, b: RGB, k: float) -> RGB:
    return tuple(int(x + (y - x) * k) for x, y in zip(a, b))


# The presenters, from the descriptions agreed for them.
LOOKS: dict[str, Look] = {
    # Dana Ferris: mid-40s, dark brown shoulder-length hair tucked behind one ear, navy blazer, dry half-smile
    "anchor": Look(skin=(232, 190, 160), hair=(62, 40, 30), top=(38, 56, 104), under=(240, 240, 240),
                   hair_style="bob", extra="earrings", mouth="smirk"),
    # Gordon Pell: early 60s, ruddy, neat grey hair and short grey beard, olive waxed jacket, mustard shirt
    "weather": Look(skin=(222, 160, 130), hair=(165, 165, 165), top=(92, 108, 62), under=(226, 186, 70),
                    top_style="jacket", facial="beard", mouth="smile", brows="raised"),
    # Miles Okafor: late 20s, short black hair, rust-red field jacket, white T-shirt, press lanyard
    "reporter": Look(skin=(122, 80, 56), hair=(22, 20, 20), top=(150, 66, 46), under=(236, 236, 236),
                     hair_style="crop", top_style="jacket", extra="lanyard", extra_col=(200, 40, 50)),
    # Rosie Treloar: mid-30s, freckles, copper-red ponytail, orange cardigan over a cream top, big smile
    "host_a": Look(skin=(236, 196, 168), hair=(176, 74, 40), top=(230, 120, 60), under=(250, 236, 200),
                   hair_style="ponytail", top_style="cardigan", mouth="smile", freckles=True),
    # Jonah Pike: late 30s, light brown skin, short dark brown hair, stubble, teal jumper with a collar
    "host_b": Look(skin=(176, 124, 92), hair=(50, 38, 32), top=(56, 108, 118), under=(235, 225, 210),
                   top_style="jumper", facial="stubble", mouth="smile"),
    # Pat Holloway: late 50s, silver-grey bob, reading glasses pushed up, plum jacket, cream blouse
    "mag_a": Look(skin=(228, 186, 158), hair=(178, 178, 184), top=(128, 44, 72), under=(240, 230, 220),
                  hair_style="bob", glasses="up"),
    # Clive Ashdown: mid-40s, unruly sandy hair, green tweed jacket, cream shirt, a pen in the top pocket
    "mag_b": Look(skin=(220, 176, 146), hair=(200, 170, 92), top=(92, 116, 62), under=(250, 245, 220),
                  hair_style="unruly", extra="pen", extra_col=(40, 60, 140), mouth="smile", brows="raised",
                  tweed=True),
    # Vincent Marr: late 50s, brown skin, black hair greying at the temples, moustache, charcoal suit, red tie
    "late_host": Look(skin=(160, 110, 84), hair=(34, 30, 30), top=(46, 46, 54), under=(232, 232, 232),
                      hair_style="swept", top_style="suit", tie=(196, 40, 50), facial="moustache",
                      temples=(150, 150, 150), mouth="smirk"),
}
# Fran Kellaway: mid-30s, former county footballer, a dark blonde ponytail, a zipped track top in
# the Tides' blue with a white band, a ready smile
LOOKS["sport"] = Look(skin=(226, 182, 150), hair=(150, 110, 60), top=(40, 110, 190), under=(240, 240, 236),
                      hair_style="ponytail", top_style="jacket", extra="stripe", extra_col=(240, 240, 236),
                      mouth="smile")
# Tamsin Jago: twenty-five, Full Time's reporter at the grounds and the pubs, long dark brown hair, a
# green waterproof and a scarf in the Tides' blue (chosen on a contact sheet, 2026-10-30)
LOOKS["sport_reporter"] = Look(skin=(214, 168, 138), hair=(58, 36, 24), top=(44, 96, 70), under=(236, 232, 220),
                               hair_style="long", top_style="jacket", extra="scarf", extra_col=(40, 110, 190),
                               mouth="smile")
# Howard Lanyon: mid-60s, Quayside's presenter, thirty years the Harrow Street bank manager: neat silver
# hair, a short grey beard, a navy blazer, a pale blue shirt and a green tie (chosen on a contact sheet,
# 2026-10-30)
LOOKS["business"] = Look(skin=(226, 186, 160), hair=(196, 196, 200), top=(40, 52, 90), under=(196, 216, 236),
                         hair_style="swept", top_style="blazer", tie=(40, 100, 70), facial="beard", mouth="smirk",
                         brows="raised")
# Meg Trethewey: late 40s, Out and About's presenter, twenty years a ranger on the coast path: dark
# brown hair greying at the sides in a plait, a red waterproof over an oatmeal top (chosen on a contact
# sheet, 2026-10-30)
LOOKS["travel"] = Look(skin=(230, 186, 156), hair=(74, 54, 42), top=(190, 52, 44), under=(226, 214, 190),
                       hair_style="ponytail", top_style="jacket", temples=(160, 150, 140), mouth="smile")
# Poppy Tregenza: late 20s, Rock Pool's presenter, six years teaching Year Two at Saltby primary: copper
# hair in bunches, freckles, a yellow top under denim dungarees (chosen on a contact sheet, 2026-10-30)
LOOKS["kids"] = Look(skin=(236, 196, 168), hair=(176, 74, 40), top=(250, 210, 70), under=(250, 236, 200),
                     hair_style="ponytail", top_style="tshirt", extra="apron", extra_col=(60, 86, 130),
                     mouth="smile", freckles=True)
# Hugh Tremayne: mid-60s, a retired history teacher, white hair receding, round glasses, a brown
# corduroy jacket over a cream shirt and a mustard tie, eyebrows up mid-story
LOOKS["historian"] = Look(skin=(226, 180, 152), hair=(225, 225, 228), top=(120, 84, 52), under=(236, 226, 196),
                          hair_style="receding", top_style="blazer", tie=(200, 150, 40), glasses="on",
                          mouth="smile", brows="raised", tweed=True)
LOOKS["guest"] = Look(skin=(225, 180, 150), hair=(160, 120, 60), top=(70, 90, 80), under=(200, 210, 190),
                      top_style="jumper")

# ------------------------------------------------------------------ guests

SKINS = [(240, 205, 180), (232, 190, 160), (214, 168, 136), (190, 140, 108), (160, 110, 84), (122, 80, 56),
         (96, 64, 46)]
HAIRS = [(30, 26, 24), (62, 40, 30), (96, 64, 40), (150, 110, 60), (200, 170, 92), (176, 74, 40)]
GREYS = [(150, 150, 150), (190, 190, 194), (225, 225, 228)]
TOPS = [(70, 90, 80), (110, 70, 90), (160, 130, 60), (50, 70, 120), (120, 120, 120), (150, 60, 50),
        (60, 110, 120), (90, 60, 110), (180, 150, 110), (40, 40, 48), (100, 120, 70), (200, 90, 80)]
UNDERS = [(240, 240, 236), (235, 225, 210), (200, 210, 230), (250, 240, 200), (220, 200, 210)]

# Role words that dress a guest: (words, look changes). The first rule that matches wins.
LEATHER, CANVAS, DENIM = (120, 78, 46), (150, 136, 104), (60, 86, 130)
COSTUMES: list[tuple[tuple[str, ...], dict]] = [
    # trades and shops, from the town's own roles (2026-10-27): ahead of the broader words below
    (("cobbler", "shoemender", "shoe", "saddler", "leather", "bookbinder", "blacksmith", "smith", "farrier",
      "cooper"),
     dict(top_style="tshirt", top=(220, 214, 196), extra="apron", extra_col=LEATHER)),
    # more of the town's trades (2026-10-28), from the roles the first evening run cast
    (("publican", "landlord", "landlady", "barman", "barmaid", "bar", "pub", "innkeeper", "brewer"),
     dict(top_style="tshirt", top=(110, 34, 44), extra="towel", extra_col=(236, 232, 220))),
    (("docker", "dock", "stevedore", "cannery worker", "packer", "warehouse", "porter"),
     dict(top_style="jacket", top=(40, 44, 52), extra="yoke", extra_col=(22, 22, 26), hat="flatcap",
          hat_col=(70, 64, 58))),
    (("lighthouse",), dict(top_style="jumper", top=(30, 38, 66), under=(30, 38, 66), hat="peaked",
                           hat_col=(236, 236, 236))),
    (("stallholder", "stall", "market trader", "trader", "costermonger"),
     dict(top_style="jacket", top=(150, 52, 44), extra="apron", extra_col=(60, 120, 70))),
    (("groomer", "kennel", "dog", "pet shop"),
     dict(top_style="tshirt", top=(96, 66, 120), extra="apron", extra_col=(214, 214, 222))),
    (("ghost", "tour guide", "guide", "storyteller"),
     dict(top_style="suit", top=(30, 28, 36), under=(30, 28, 36), extra="scarf", extra_col=(150, 30, 40))),
    (("chip", "chippy", "fishmonger", "butcher", "greengrocer", "grocer"),
     dict(top_style="tshirt", top=(70, 110, 150), extra="apron", extra_col=(236, 236, 230))),
    (("coffee", "barista", "tea room", "tearoom"),
     dict(top_style="tshirt", top=(40, 40, 46), extra="apron", extra_col=(110, 70, 40))),
    (("printer", "print", "stationer", "newsagent"),
     dict(top_style="tshirt", top=(200, 200, 205), extra="apron", extra_col=(60, 64, 72))),
    (("hardware", "ironmonger", "tool", "ladder", "crockery", "kettle", "shopkeeper", "proprietor", "lamp",
      "chandler", "candle"),
     dict(top_style="jumper", top=(120, 40, 40), extra="apron", extra_col=CANVAS)),
    (("mechanic", "garage", "bicycle", "bike", "plumber"),
     dict(top_style="tshirt", top=(200, 200, 205), extra="apron", extra_col=DENIM)),
    (("electrician", "roofer", "builder", "scaffold", "labourer", "joiner", "carpenter", "roadworks", "engineer"),
     dict(top_style="jacket", top=(60, 64, 72), extra="hivis", extra_col=(226, 232, 44))),
    (("tailor", "seamstress", "dressmaker", "alterations", "upholsterer", "milliner", "hatter"),
     dict(top_style="cardigan", extra="tape", extra_col=(236, 200, 40))),
    (("fc", "football", "footballer", "striker", "goalkeeper", "supporter", "rugby", "cricket"),
     dict(top_style="jacket", top=(30, 50, 100), extra="scarf", extra_col=(60, 150, 210))),
    (("taxi", "cab", "driver", "chauffeur", "ticket", "conductor", "postmistress", "postmaster", "postman",
      "postwoman", "post office"),
     dict(top_style="uniform", top=(30, 40, 70), under=(220, 220, 225), hat="peaked", hat_col=(30, 40, 70))),
    (("sweep",), dict(top_style="jacket", top=(36, 36, 40), under=(36, 36, 40), hat="flatcap",
                      hat_col=(30, 30, 34), extra="soot", extra_col=(70, 70, 74))),
    (("clockmaker", "watchmaker", "jeweller", "horologist", "antique"),
     dict(top_style="suit", top=(110, 90, 66), tweed=True, glasses="up")),
    (("fire",), dict(top_style="uniform", top=(30, 34, 50), under=(30, 34, 50), extra="stripe",
                     extra_col=(230, 200, 40))),
    (("police", "constable", "inspector", "sergeant", "detective"),
     dict(top_style="uniform", top=(24, 28, 44), under=(236, 236, 236), tie=(20, 20, 24))),
    (("lifeboat", "coastguard", "rnli"), dict(top_style="jacket", top=(236, 190, 40), under=(30, 40, 70),
                                              hat="beanie", hat_col=(30, 40, 70))),
    (("harbour", "fisher", "skipper", "trawler", "boat", "ferry", "sailor", "crab", "oyster", "quay"),
     dict(top_style="jumper", top=(36, 44, 76), under=(36, 44, 76), hat="beanie", hat_col=(150, 40, 40))),
    (("chef", "cook", "baker", "bakery", "cafe", "café", "restaurant", "pie", "pasty", "kitchen"),
     dict(top_style="chef", top=(240, 240, 236), under=(240, 240, 236))),
    (("mayor",), dict(top_style="suit", top=(40, 40, 50), under=(236, 236, 236), extra="chain")),
    (("vicar", "reverend", "rector", "priest", "chaplain", "curate"),
     dict(top_style="jacket", top=(26, 26, 30), under=(26, 26, 30), extra="collar")),
    (("farmer", "farm", "shepherd", "dairy", "allotment", "gardener"),
     dict(top_style="jacket", top=(84, 100, 60), hat="flatcap", hat_col=(110, 96, 70))),
    (("doctor", "nurse", "gp", "surgery", "paramedic", "vet"),
     dict(top_style="tshirt", top=(70, 140, 150), under=(70, 140, 150))),
    (("councillor", "mp", "parliament", "minister", "solicitor", "director", "manager", "chief", "chair", "officer",
      "clerk", "estate agent", "developer", "businessman", "businesswoman"),
     dict(top_style="suit")),
    (("teacher", "head", "librarian", "historian", "society", "archivist", "professor", "author"),
     dict(top_style="cardigan", glasses="on")),
    (("singer", "musician", "band", "actor", "actress", "star", "celebrity", "presenter", "comedian", "performer",
      "magician", "entertainer",
      "influencer", "dj", "artist", "painter", "designer"),
     dict(top_style="jacket", glasses="shades")),
    (("sea glass", "collector", "beachcomber", "birdwatcher", "naturalist", "rambler", "walker"),
     dict(top_style="jacket", top=(58, 128, 126), hat="beanie", hat_col=(196, 90, 76))),
    # sport, for Full Time's guests; outdoors. Late, so a coach driver or a ticket collector keeps their uniform
    (("bowls", "bowler"), dict(top_style="cardigan", top=(236, 232, 220), under=(236, 236, 236))),
    (("rowing", "rower", "cox", "oarsman", "oarswoman"),
     dict(top_style="tshirt", top=(30, 70, 60), extra="stripe", extra_col=(236, 200, 60))),
    (("swimmer", "swimming", "lido"),
     dict(top_style="tshirt", top=(40, 120, 170), extra="towel", extra_col=(236, 236, 236))),
    (("referee", "linesman", "umpire"), dict(top_style="tshirt", top=(24, 24, 28), under=(24, 24, 28))),
    (("midfielder", "defender", "winger", "groundsman", "physio"),
     dict(top_style="jacket", top=(40, 110, 190), under=(240, 240, 236), extra="stripe", extra_col=(240, 240, 236))),
    (("student", "pupil", "teen", "skater", "apprentice"), dict(top_style="tshirt")),
]
OLD_WORDS = ("retired", "pensioner", "grand", "veteran", "elder", "widow", "former", "oldest", "lifelong")
YOUNG_WORDS = ("student", "pupil", "teen", "young", "apprentice", "skater", "school")


@lru_cache(maxsize=512)
def guest_look(name: str | None, voice: str = "", role: str = "", age: str = "") -> Look:
    """A guest's look: the same name, voice and role always give the same person. The voice
    (af_/bf_ or am_/bm_) decides whether they read as a woman or a man, so look and voice agree;
    the age the script cast them at (young, middle, old) wins over the role's words."""
    key = (name or "guest").strip().lower()
    h = zlib.crc32(key.encode("utf-8"))

    def pick(seq, salt: int):
        return seq[(h >> salt) % len(seq)]

    fem = voice[1:2] == "f" if len(voice) > 1 and voice[1] in "fm" else h % 2 == 0
    r = (role or "").lower()
    age = {"young": 0, "middle": 1, "old": 2}.get(age, 2 if any(w in r for w in OLD_WORDS)
                                                  else 0 if any(w in r for w in YOUNG_WORDS) else (h >> 3) % 3)
    skin = pick(SKINS, 0)
    dark = SKINS.index(skin) >= 4                             # sandy and copper hair only with lighter skin
    hair = pick(GREYS, 5) if age == 2 else pick(HAIRS[:3] if dark else HAIRS, 5)
    if fem:
        style = pick(["bob", "long", "ponytail", "bun", "curly", "short"], 9)
        facial = ""
    else:
        style = pick(["short", "crop", "curly", "swept"] + (["receding", "bald"] if age else []), 9)
        facial = pick(["", "", "", "stubble", "beard", "moustache"], 13) if age or (h >> 13) % 2 else ""
    look = Look(skin=skin, hair=hair, top=pick(TOPS, 17), under=pick(UNDERS, 21),
                hair_style=style, top_style=pick(["jumper", "cardigan", "jacket", "tshirt", "blazer"], 23),
                facial=facial, glasses="on" if age == 2 and (h >> 27) % 2 else "",
                extra="earrings" if fem and (h >> 28) % 3 == 0 else "",
                mouth=pick(["line", "smile", "smirk", "line"], 29), brows="raised" if (h >> 30) % 3 == 0 else "")
    for words, change in COSTUMES:
        if any(w in r.split() or (len(w) > 3 and w in r) for w in words):
            look = replace(look, **change)
            break
    if look.top_style in ("suit", "uniform") and look.tie is None and not fem and look.extra != "stripe":
        look = replace(look, tie=pick([(120, 30, 40), (40, 60, 110), (60, 60, 60)], 11))
    return look


# ------------------------------------------------------------------ drawing

class _Pen:
    """Fills blocks in units from the top centre of the head, mirrored for facing left."""

    def __init__(self, canvas: pygame.Surface, x: int, top: int, s: int, facing: int,
                 light: tuple[float, float, float] | None = None) -> None:
        self.c, self.x, self.top, self.s, self.f = canvas, x, top, s, 1 if facing >= 0 else -1
        self.light = light if light and light != (1.0, 1.0, 1.0) else None

    def __call__(self, col: RGB, dx: int, dy: int, w: int = 1, h: int = 1) -> None:
        if self.light:
            col = tuple(min(255, int(c * k)) for c, k in zip(col, self.light))
        if self.f < 0:
            dx = -dx - w
        self.c.fill(col, (self.x + dx * self.s, self.top + dy * self.s, w * self.s, h * self.s))

    def rows(self, col: RGB, spans: list[tuple[int, int, int]]) -> None:
        """(row, from dx, to dx inclusive) spans."""
        for dy, a, b in spans:
            self(col, a, dy, b - a + 1)


HEAD = [(0, -6, 5)] + [(r, -7, 6) for r in range(1, 13)] + [(13, -6, 5)]
BODY = [(17, -10, 9), (18, -12, 11)] + [(r, -13, 12) for r in range(19, 37)]


def _outline(p: _Pen, spans, col: RGB, bottom_open: bool = False) -> None:
    """A one-unit border round a shape given as row spans (drawn first, then the shape over it)."""
    last = spans[-1][0]
    for dy, a, b in spans:
        p(col, a - 1, dy, b - a + 3)
    p(col, spans[0][1], spans[0][0] - 1, spans[0][2] - spans[0][1] + 1)
    if not bottom_open:
        p(col, spans[-1][1], last + 1, spans[-1][2] - spans[-1][1] + 1)


def _hair_back(p: _Pen, L: Look) -> None:
    st, c = L.hair_style, L.hair
    if st == "long":
        p.rows(c, [(r, -9, 8) for r in range(4, 19)])
        _edge = _dark(c, OUTLINE_K)
        p(_edge, -10, 4, 1, 15); p(_edge, 9, 4, 1, 12)
    elif st == "ponytail":
        p(_dark(c, OUTLINE_K), -11, 3, 4, 11)
        p(c, -10, 3, 3, 10)
        p(_dark(c, 0.8), -10, 3, 1, 2)                       # the band
    elif st == "bob":
        p(_dark(c, OUTLINE_K), -9, 2, 18, 13)
        p.rows(c, [(r, -8, 7) for r in range(2, 14)])


def _body(p: _Pen, L: Look) -> None:
    top, under = L.top, L.under
    _outline(p, BODY, _dark(top, OUTLINE_K), bottom_open=True)
    p.rows(top, BODY)
    shade = _dark(top, 0.8)
    p.rows(shade, [(r, -13, -11) for r in range(19, 37)])     # the far side, away from the light
    p(shade, -8, 25, 1, 12); p(shade, 7, 25, 1, 12)           # where the arms meet the body
    if L.tweed:
        for r in range(19, 37, 2):
            for d in range(-12 + r % 4, 12, 4):
                p(_dark(top, 0.88), d, r)
    st = L.top_style
    if st in ("blazer", "suit", "cardigan", "uniform"):
        deep = 26 if st == "cardigan" else 25
        spans = [(r, -max(0, 4 - (r - 17) // 2), max(0, 4 - (r - 17) // 2) - 1) for r in range(17, deep)]
        p.rows(under, [s for s in spans if s[2] >= s[1]])
        lapel = _dark(top, 0.7)
        for r, a, b in spans:                                 # lapel edges either side of the V
            p(lapel, a - 1, r); p(lapel, b + 1, r)
        if L.tie:
            p(L.tie, -1, 17, 2, 1)                            # knot
            p.rows(L.tie, [(r, -1, 0) for r in range(18, 29)])
            p(_dark(L.tie, 0.7), 0, 18, 1, 11)
        if st == "cardigan":
            for r in range(27, 36, 3):
                p(_dark(top, 0.6), 0, r)
    elif st == "jumper":
        p.rows(under, [(17, -4, -2), (17, 1, 3), (18, -3, -2), (18, 1, 2)])   # the collar points
        p(_dark(top, 0.75), -4, 18, 8, 1)                     # ribbed neck
    elif st == "jacket":
        p.rows(under, [(17, -3, 2), (18, -2, 1), (19, -1, 0)])
        p.rows(_dark(top, 0.7), [(17, -6, -4), (17, 3, 5), (18, -5, -3), (18, 2, 4)])   # collar
        p(_mix(top, (230, 230, 230), 0.35), 0, 20, 1, 17)     # zip
    elif st == "tshirt":
        p.rows(L.skin, [(17, -3, 2), (18, -2, 1)])
        p(_dark(top, 0.75), -4, 17, 1, 2); p(_dark(top, 0.75), 3, 17, 1, 2)
    elif st == "chef":
        for r in range(21, 34, 3):
            p(_dark(top, 0.7), -3, r); p(_dark(top, 0.7), 2, r)
        p(_dark(top, 0.85), -4, 17, 8, 2)
    if L.extra == "stripe":
        p(L.extra_col, -13, 29, 26, 2)
    elif L.extra == "lanyard":
        for i in range(8):
            p(L.extra_col, -3 + i // 3, 18 + i); p(L.extra_col, 2 - i // 3, 18 + i)
        p(WHITE, -1, 26, 3, 3); p(_dark(WHITE, 0.6), -1, 28, 3, 1)
    elif L.extra == "pen":
        p(L.extra_col, 6, 21, 1, 3); p(_dark(L.top, 0.6), 4, 24, 4, 1)   # in the top pocket
    elif L.extra == "chain":
        for d, r in ((-8, 18), (-7, 20), (-6, 22), (-4, 24), (-2, 25), (1, 25), (3, 24), (5, 22), (6, 20), (7, 18)):
            p(L.extra_col, d, r)
        p(L.extra_col, -1, 26, 2, 2)
    elif L.extra == "collar":
        p(WHITE, -1, 17, 2, 2)
    elif L.extra == "apron":                                  # a bib apron: straps over the shoulders
        a = L.extra_col
        p(a, -5, 17, 1, 5); p(a, 4, 17, 1, 5)
        p.rows(a, [(r, -6, 5) for r in range(22, 37)])
        p(_dark(a, 0.75), -6, 22, 12, 1); p(_dark(a, 0.8), -3, 30, 6, 1)   # the bib's top, a pocket
    elif L.extra == "hivis":                                  # a high-visibility vest, open at the front
        v, band = L.extra_col, (225, 225, 225)
        p.rows(v, [(r, -12, -4) for r in range(19, 37)] + [(r, 3, 11) for r in range(19, 37)])
        for r in (27, 31):
            p(band, -12, r, 9, 1); p(band, 3, r, 9, 1)
    elif L.extra == "tape":                                   # a tape measure round the neck
        for x in (-5, 4):
            p(L.extra_col, x, 17, 1, 17)
            for r in range(18, 34, 2):
                p(_dark(L.extra_col, 0.6), x, r)
    elif L.extra == "scarf":                                  # a club scarf in stripes, one end hanging
        stripes = (L.extra_col, WHITE)
        for r in range(16, 19):
            p(stripes[r % 2], -5, r, 10, 1)
        for r in range(19, 31):
            p(stripes[(r // 2) % 2], 2, r, 3, 1)
    elif L.extra == "towel":                                  # a bar or beach towel over the near shoulder
        t = L.extra_col
        p.rows(t, [(r, 6, 11) for r in range(18, 21)] + [(r, 7, 10) for r in range(21, 28)])
        for r in (22, 25):
            p(_dark(t, 0.7), 7, r, 4, 1)
    elif L.extra == "yoke":                                   # a donkey jacket's leather shoulders
        p.rows(L.extra_col, [(r, -12, -4) for r in range(18, 22)] + [(r, 3, 11) for r in range(18, 22)])


def _head(p: _Pen, L: Look, mouth: float, blink: bool) -> None:
    skin = L.skin
    p(skin, -3, 14, 6, 3)                                     # neck
    p(_dark(skin, 0.82), -3, 14, 2, 3)
    _outline(p, HEAD, _dark(skin, OUTLINE_K))
    p.rows(skin, HEAD)
    p.rows(_dark(skin, 0.9), [(r, -7, -6) for r in range(3, 13)])        # the far cheek in shade
    p(_dark(skin, OUTLINE_K), -9, 6, 1, 4); p(skin, -8, 6, 1, 4)         # far ear
    p(_dark(skin, 0.8), -8, 7, 1, 2)
    if L.extra == "earrings":
        p(L.extra_col, -8, 10)
    if L.extra == "soot":                                     # the chimney sweep's smudges
        for d, r in ((2, 9), (3, 10), (-4, 11), (-5, 10)):
            p(L.extra_col, d, r)
    if L.freckles:
        for d, r in ((-3, 9), (-1, 10), (4, 9), (5, 10)):
            p(_dark(skin, 0.85), d, r)
    # beard and stubble go under the mouth
    if L.facial == "stubble":                                 # a light dusting along the jaw
        for r in range(11, 14):
            for d in range(-6 + r % 2, 6, 2):
                p(_mix(skin, L.hair, 0.3), d, r)
    elif L.facial == "beard":
        p.rows(L.hair, [(9, -6, -4), (10, -6, 5), (11, -6, 5), (12, -6, 5), (13, -5, 4), (14, -3, 2)])
        p(_dark(L.hair, 0.8), -6, 10, 2, 3)
    # eyes: the white on the far side, the pupil looking the way they face
    brow = _dark(L.hair, 0.8) if L.hair[0] > 120 else L.hair
    by = 4 if L.brows == "raised" else 5
    for ex in (-3, 3):
        p(brow, ex - 1, by, 3, 1)
        if blink:
            p(_dark(skin, 0.55), ex - 1, 7, 3, 1)
        else:
            p(WHITE, ex - 1, 6, 1, 2)
            p(EYE, ex, 6, 1, 2)
    p(_dark(skin, 0.78), 1, 8, 1, 2)                          # nose shadow
    p(_dark(skin, 0.9), 0, 9, 1, 1)
    if L.facial == "moustache":
        p(L.hair, -2, 10, 6, 1)
    lip = _mix(_dark(skin, 0.75), (170, 60, 70), 0.35)
    if mouth > 0.08:                                          # open with the audio
        p(INNER, -1, 11, 4, max(1, round(mouth * 3)))
        p(lip, -1, 11 + max(1, round(mouth * 3)), 4, 1)
    elif L.mouth == "smile":
        p(lip, -1, 11, 4, 1); p(lip, -2, 10, 1, 1); p(lip, 3, 10, 1, 1)
    elif L.mouth == "smirk":
        p(lip, -1, 11, 4, 1); p(lip, 3, 10, 1, 1)
    else:
        p(lip, -1, 11, 4, 1)
    if L.glasses == "on":                                     # a dark top rim, a light lower one
        for ex in (-3, 3):
            p((40, 40, 48), ex - 2, 5, 4, 1); p((120, 120, 130), ex - 2, 8, 4, 1)
        p((40, 40, 48), 0, 6, 1, 1)
    elif L.glasses == "shades":
        p((24, 24, 30), -5, 5, 11, 1)
        p((24, 24, 30), -5, 6, 4, 2); p((24, 24, 30), 1, 6, 4, 2)
        p((90, 90, 110), -4, 6, 1, 1); p((90, 90, 110), 2, 6, 1, 1)


def _hair_front(p: _Pen, L: Look) -> None:
    c, st = L.hair, L.hair_style
    edge = _dark(c, OUTLINE_K)
    hi = _mix(c, (255, 255, 255), 0.2)
    if st == "bald":
        p(c, -7, 5, 2, 4); p(c, 6, 5, 1, 3)
        p(_mix(L.skin, (255, 255, 255), 0.25), 1, 1, 3, 1)  # a shine on the crown
    elif st == "receding":
        p(edge, -7, -1, 9, 1)
        p.rows(c, [(0, -7, 1), (1, -7, -3), (2, -7, -5)])
        p(c, -7, 3, 2, 6); p(c, 6, 4, 1, 3)
    else:
        cap = {"crop": [(-1, -6, 5), (0, -7, 6), (1, -7, 6)],
               "curly": [(-2, -6, -5), (-2, -2, -1), (-2, 2, 3), (-1, -7, 6), (0, -8, 7), (1, -8, 7), (2, -8, 7)],
               "unruly": [(-2, -3, -2), (-2, 3, 4), (-1, -7, 6), (0, -7, 7), (1, -7, 6), (2, -7, 2)],
               "swept": [(-2, -4, 3), (-1, -7, 5), (0, -7, 6), (1, -7, 6), (2, -7, 0)],
               }.get(st, [(-1, -6, 5), (0, -7, 6), (1, -7, 6), (2, -7, 4)])
        _outline(p, cap, edge, bottom_open=True)
        p.rows(c, cap)
        p(hi, 0, cap[0][0] + 1 if st == "curly" else cap[0][0], 3, 1)
        # the far side: sideburn, or hair down past the ear
        down = {"crop": 5, "short": 6, "curly": 8, "unruly": 7, "swept": 7, "bun": 7, "ponytail": 7}.get(st, 12)
        p(c, -7, 2, 2, down - 1)
        if st in ("bob", "long"):
            p.rows(c, [(r, -8, -5) for r in range(2, 13 if st == "bob" else 16)])
            p(c, 6, 2, 2, 4)                                  # tucked behind the near ear
            p(edge, 5, 3, 1, 2)
        elif st == "curly":
            p(c, 6, 2, 2, 3)
        else:
            p(c, 6, 2, 1, 2)
        if st == "bun":
            p(edge, -3, -5, 6, 4); p(c, -2, -5, 4, 3)
    if L.temples:
        p(L.temples, -7, 4, 2, 3); p(L.temples, 6, 3, 1, 2)
    if L.glasses == "up":
        frame = (30, 30, 36)
        p(frame, -5, -1, 11, 1); p((150, 170, 190), -4, 0, 3, 1); p((150, 170, 190), 2, 0, 3, 1)
    if L.hat == "beanie":
        _outline(p, [(-2, -6, 5), (-1, -7, 6), (0, -7, 6), (1, -7, 6), (2, -7, 6)], _dark(L.hat_col, OUTLINE_K),
                 bottom_open=True)
        p.rows(L.hat_col, [(-2, -6, 5), (-1, -7, 6), (0, -7, 6), (1, -7, 6)])
        p(_dark(L.hat_col, 0.75), -7, 2, 14, 1)
    elif L.hat == "cap":
        p.rows(L.hat_col, [(-2, -6, 5), (-1, -7, 6), (0, -7, 6), (1, -7, 6)])
        p(_dark(L.hat_col, 0.7), 2, 2, 9, 1)
    elif L.hat == "flatcap":
        p.rows(L.hat_col, [(-1, -7, 6), (0, -8, 8), (1, -8, 9)])
        p(_dark(L.hat_col, 0.7), 3, 2, 7, 1)
    elif L.hat == "peaked":                                   # a uniform cap: flat crown, band, badge, peak
        p.rows(L.hat_col, [(-3, -7, 6), (-2, -8, 7), (-1, -7, 6), (0, -7, 6)])
        p((20, 20, 24), -7, 1, 14, 1)
        p(GOLD, -1, -1, 2, 1)
        p((20, 20, 24), 1, 2, 9, 1)


def _beat(who: str, look: Look | None) -> float:
    """Each character blinks on their own beat, so two on a sofa don't blink together."""
    return ((sum(map(ord, who)) if look is None else hash(look)) % 7) * 0.5


def _blinking(who: str, look: Look | None, t: float) -> bool:
    return (t + _beat(who, look)) % 4.0 > 3.85                # every ~4 s


# Gestures: whoever is talking brings a hand up now and then; whoever is listening nods. The mouth
# says who is talking, so each character's last open mouth is kept (by who and look: two guests differ).
_TALKED: dict = {}
TALK_HOLD_S = 0.6                # still "talking" this long after the mouth last opened (between words)
LISTEN_AFTER_S = 1.5             # and listening after this long shut
HAND_EVERY_S, HAND_FOR_S, HAND_RISE_S = 5.5, 1.6, 0.2
NOD_EVERY_S, NOD_FOR_S = 4.3, 0.45


def _gesture(who: str, look: Look | None, mouth: float, t: float) -> tuple[str, float]:
    """("hand", how far up 0..1), ("nod", 1) or ("", 0) for this frame."""
    key = (who, look)
    if mouth > 0.08:
        _TALKED[key] = t
    last = _TALKED.get(key)
    beat = _beat(who, look)
    if last is not None and 0 <= t - last < TALK_HOLD_S:
        w = (t + beat) % HAND_EVERY_S
        return ("hand", min(1.0, w / HAND_RISE_S, (HAND_FOR_S - w) / HAND_RISE_S)) if w < HAND_FOR_S else ("", 0.0)
    if last is None or not 0 <= t - last < LISTEN_AFTER_S:
        return ("nod", 1.0) if (t + beat * 1.7) % NOD_EVERY_S < NOD_FOR_S else ("", 0.0)
    return "", 0.0


def _hand(p: _Pen, L: Look, up: float, t: float, beat: float) -> None:
    """A hand coming up into frame on the near side, a cuff of the top below it; every other
    gesture an index finger points."""
    n = int((t + beat) // HAND_EVERY_S)
    dx = 3 if n % 2 else 5
    hy = 37 - round(10 * up)
    if hy >= 36:
        return
    edge = _dark(L.top, OUTLINE_K)
    p(edge, dx - 1, hy + 3, 6, 37 - hy - 3)
    p.rows(L.top, [(r, dx, dx + 3) for r in range(hy + 3, 37)])
    skin, skin_edge = L.skin, _dark(L.skin, OUTLINE_K)
    p(skin_edge, dx - 1, hy - 1, 6, 5)
    p.rows(skin, [(r, dx, dx + 3) for r in range(hy, hy + 3)])
    p(_dark(skin, 0.82), dx, hy + 2, 4, 1)                    # the knuckles' shadow
    if n % 3 == 2:
        p(skin_edge, dx + 2, hy - 4, 3, 4)
        p(skin, dx + 3, hy - 3, 1, 3)                         # the pointing finger


def draw_character(canvas: pygame.Surface, x: int, y: int, who: str, mouth: float, t: float,
                   *, scale: int = 1, facing: int = 1, look: Look | None = None,
                   light: tuple[float, float, float] | None = None,
                   gesture: tuple[str, float] | None = None) -> None:
    """Head-and-shoulders character with the bottom at (x, y) baseline. mouth in 0..1.
    `look` overrides the presenter's own (guests pass guest_look(...)); `light` multiplies
    every colour, to sit them in a location's light (backdrops.person_light). `gesture` fixes
    one for a contact sheet; otherwise talking and listening choose (`_gesture`)."""
    if who == "gully":
        return draw_gully(canvas, x, y, mouth, t, scale=scale, facing=facing, light=light)
    L = look or LOOKS.get(who, LOOKS["guest"])
    kind, up = gesture if gesture is not None else _gesture(who, look, mouth, t)
    bob = int(round(math.sin(t * 2.0) * 0.6))                 # idle breathing
    top = y - 37 * scale + bob
    p = _Pen(canvas, x, top, scale, facing, light)
    hp = _Pen(canvas, x, top + scale, scale, facing, light) if kind == "nod" else p   # the head dips
    _hair_back(hp, L)
    _body(p, L)
    if kind == "hand":
        _hand(p, L, up, t, _beat(who, look))
    _head(hp, L, mouth, _blinking(who, look, t))
    _hair_front(hp, L)


GULL_WHITE, GULL_GREY, GULL_DARK = (244, 244, 240), (150, 160, 172), (40, 40, 48)
GULL_BEAK, GULL_SPOT = (242, 196, 48), (210, 50, 40)
# The crown at the back, the forehead sloping down to the beak at the front (+dx), a slim neck.
GULL_HEAD = ([(0, -4, 0), (1, -6, 2), (2, -7, 3), (3, -7, 4), (4, -7, 5)] + [(r, -7, 6) for r in range(5, 12)]
             + [(12, -6, 5), (13, -5, 4)] + [(r, -4, 4) for r in range(14, 22)])


def draw_gully(canvas: pygame.Surface, x: int, y: int, mouth: float, t: float, *, scale: int = 1,
               facing: int = 1, light: tuple[float, float, float] | None = None) -> None:
    """Gully, Rock Pool's herring-gull puppet, up from below frame on Poppy's arm in her yellow sleeve
    (chosen on a contact sheet, 2026-10-30). (x, y) is the bottom centre, like draw_character's; the
    lower beak drops with `mouth`, and he bobs when he talks, as a puppeteer's hand does."""
    talking = mouth > 0.08
    bob = (-1 if talking and int(t * 6) % 2 else 0) + int(round(math.sin(t * 2.0 + 1.0) * 0.6))
    p = _Pen(canvas, x, y - 40 * scale + bob * scale, scale, facing, light)
    sleeve = LOOKS["kids"].top
    edge = _dark(GULL_WHITE, 0.55)
    p(_dark(sleeve, 0.7), -5, 22, 11, 18)                    # Poppy's arm in its sleeve, up into the neck
    p(sleeve, -4, 22, 9, 18)
    for dy, a, b in GULL_HEAD:
        p(edge, a - 1, dy, b - a + 3)
    p(edge, GULL_HEAD[0][1], -1, GULL_HEAD[0][2] - GULL_HEAD[0][1] + 1)
    for dy, a, b in GULL_HEAD:
        p(GULL_WHITE, a, dy, b - a + 1)
    p(GULL_GREY, -6, 15, 7, 7)                               # the grey back, behind the neck
    p(_dark(GULL_GREY, 0.8), -6, 18, 7, 1)
    p(GULL_DARK, -6, 21, 3, 1)                               # black wingtips
    open_ = round(min(1.0, mouth) * 4)                       # the beak: the upper fixed, the lower dropped
    bk, bx = _dark(GULL_BEAK, 0.6), 7
    if open_:
        p((120, 30, 40), bx, 9, 8, open_)
    p(bk, bx, 6, 11, 4)
    p(GULL_BEAK, bx, 7, 10, 2)
    p(GULL_BEAK, bx, 6, 8, 1)
    p(bk, bx + 9, 9, 2, 2)                                   # the hook at the tip
    p(bk, bx, 9 + open_, 9, 3)
    p(GULL_BEAK, bx, 10 + open_, 8, 1)
    p(GULL_SPOT, bx + 5, 10 + open_, 2, 1)                   # the red spot on the lower beak
    if int(t * 10) % 47 == 0:                                # a blink now and then
        p(edge, 1, 5, 4, 2)
        return
    p((230, 120, 50), 1, 4, 4, 4)                            # an orange ring round a pale eye
    p((236, 220, 120), 2, 5, 2, 2)
    p(GULL_DARK, 3, 5, 1, 2)


def draw_mic(canvas: pygame.Surface, x: int, y: int) -> None:
    pygame.draw.rect(canvas, (40, 40, 40), (x, y, 3, 10))
    pygame.draw.rect(canvas, (90, 90, 90), (x - 1, y - 4, 5, 5))


# ------------------------------------------------------------------ contact sheet

SAMPLE_GUESTS = [
    ("Bea Kowalczyk", "af_kore", "Fire station officer"), ("Raymond Doyle", "bm_daniel", "Chief Inspector"),
    ("Helen Strand", "bf_emma", "Mayor of Port Wexley"), ("Ivy Marchetti", "af_bella", "Harbourmaster"),
    ("Oliver Fenwick-Hale", "bm_lewis", "MP for Wexley and the Levels"), ("Marjorie Pell", "af_aoede",
                                                                          "Chair, Wexley Historical Society"),
    ("Tom Penrose", "am_puck", "Lifeboat coxswain"), ("Sally Quay", "af_nicole", "Baker, Harbour Street"),
    ("Rev. Alan Moss", "bm_fable", "Vicar of St Petroc's"), ("Ken Hollis", "am_fenrir", "Retired fisherman"),
    ("Jade Okoro", "bf_isabella", "Student"), ("Dev Sharma", "am_puck", "Farmer"),
    ("Lola Vance", "af_bella", "Singer"), ("Priya Nair", "bf_emma", "GP"), ("Gary Bright", "bm_daniel", "resident"),
    ("Moira Teague", "af_aoede", "resident"),
    ("Arthur Penhale", "am_adam", "cobbler, Harrow Street"), ("Nuala Brennan", "af_sarah", "owner, Gull's Rest Fish & Chips"),
    ("Kit Anand", "af_river", "coffee stall owner"), ("Ross Daly", "bm_lewis", "printer, Saltmarsh Print & Copy"),
    ("Jasper Fowle", "am_echo", "owner, Fowle & Sons Hardware"), ("Sam Okafor", "am_adam", "bicycle mechanic"),
    ("Dougal Crane", "bm_daniel", "roofer, Port Wexley"), ("Rhiannon Lusk", "af_jessica", "electrician"),
    ("Edie Marsh", "af_nova", "seamstress, Main Street"), ("Gil Tarrant", "am_echo", "Secretary, Wexley Gulls FC"),
    ("Kenji Okonkwo", "am_adam", "taxi driver, Okonkwo's Taxis"), ("Wyn Prosser", "af_sky", "Saltby postmistress"),
    ("Albert Soames", "am_santa", "chimney sweep"), ("Hector Vane", "bm_fable", "clockmaker, Wexley Town Hall"),
    ("Fern Odell", "af_alloy", "ticket collector"), ("Sir Giles Wren", "bm_lewis", "Member of Parliament"),
]


def contact_sheet(path: str) -> None:
    """Every presenter (scale 2 and 4, both facings, shut/talking/blink) and a crowd of guests."""
    pygame.font.init()
    f = pygame.font.SysFont("consolas", 10)
    bg = (52, 58, 84)
    who = [w for w in LOOKS if w != "guest"]
    cw, ch = 96, 112
    rows = len(who) + (len(SAMPLE_GUESTS) + 7) // 8
    sheet = pygame.Surface((8 * cw, rows * ch))
    sheet.fill((30, 30, 36))
    for i, w in enumerate(who):
        y = i * ch
        sheet.fill(bg, (0, y, 8 * cw, ch - 4))
        sheet.blit(f.render(w, True, (230, 230, 230)), (4, y + 2))
        for j, (scale, facing, mouth, t) in enumerate([(2, 1, 0.0, 0.5), (2, 1, 0.7, 0.5), (2, -1, 0.0, 0.5),
                                                      (1, 1, 0.0, 0.5), (1, -1, 0.6, 0.5)]):
            bx = 4 + j * 60 if j < 3 else 190 + j * 34
            draw_character(sheet, bx + 30, y + ch - 8, w, mouth, t, scale=scale, facing=facing)
        for j, t in enumerate((0.5, (3.9 - _beat(w, None)) % 4.0)):      # the close-up: open eyes, then a blink
            close = pygame.Surface((180, 100))
            close.fill(bg)
            draw_character(close, 90, 172, w, 0.0, t, scale=4)
            sheet.blit(close, (8 * cw - 360 + j * 180, y + 6))
    y0 = len(who) * ch
    for k, (name, voice, role) in enumerate(SAMPLE_GUESTS):
        x, y = (k % 8) * cw, y0 + (k // 8) * ch
        sheet.fill(bg, (x + 2, y, cw - 4, ch - 4))
        draw_character(sheet, x + cw // 2, y + ch - 20, "guest", (k % 3) * 0.3, 0.5, scale=2,
                       facing=-1 if k % 2 else 1, look=guest_look(name, voice, role))
        sheet.blit(f.render(name[:15], True, (230, 230, 230)), (x + 4, y + ch - 18))
        sheet.blit(f.render(role[:15], True, (170, 170, 190)), (x + 4, y + ch - 9))
    pygame.image.save(pygame.transform.scale(sheet, (sheet.get_width() * 2, sheet.get_height() * 2)), path)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--sheet", required=True, help="write a contact sheet PNG here")
    contact_sheet(ap.parse_args().sheet)
