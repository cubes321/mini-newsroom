"""Marina Row, Channel 8's soap (docs/MARINA_ROW.md, the series bible): the series the soap engine plays
(entertainment/soap.py), at 20:20 each Channel 8 night: its cast, sets, bible and opening storylines.

The characters are fiction and never join the town's people; their actors are Port Wexley residents and will.
Each character's look is the actor in costume, drawn in code like every character (chosen by the user on a
contact sheet, 2026-11-13: data/contact-sheets/2026-11-13-marina-row-cast.png, A for everyone and B for Sal).
"""
from __future__ import annotations

from dataclasses import dataclass

from newsroom.sprites import Look

NAVY = (40, 52, 88)


@dataclass(frozen=True)
class Part:
    character: str
    actor: str
    gender: str
    age: str            # the actor's: young, middle or old
    household: str
    look: Look
    voice: str          # the actor's, a DramaBox design chosen by ear 2026-11-13 (assets/voices/<voice>.b.wav)


CAST: tuple[Part, ...] = (
    # Queenie: white hair in a bun, a navy gansey, a sharp mouth
    Part("Queenie Kernick", "Margery Trethowan", "f", "old", "the Kernicks",
         Look(skin=(230, 188, 166), hair=(232, 232, 236), top=NAVY, under=NAVY, hair_style="bun",
              top_style="jumper", mouth="smirk", brows="raised"), "bf_trethowan"),
    # Davey: dark unruly hair, stubble, a yellow oilskin, a navy beanie
    Part("Davey Kernick", "Dominic Carthew", "m", "middle", "the Kernicks",
         Look(skin=(214, 160, 128), hair=(48, 36, 30), top=(222, 186, 40), under=(36, 48, 84), hair_style="unruly",
              top_style="jacket", facial="stubble", hat="beanie", hat_col=(36, 48, 84)), "bm_carthew"),
    # Kerra: long dark hair, a black T-shirt and The Loft's black apron
    Part("Kerra Kernick", "Isla Glasson", "f", "young", "the Kernicks",
         Look(skin=(232, 190, 164), hair=(40, 30, 28), top=(34, 34, 38), under=(34, 34, 38), hair_style="long",
              top_style="tshirt", extra="apron", extra_col=(60, 60, 64), mouth="line"), "bf_glasson"),
    # Harriet: a sleek blonde bob, a cream blazer, earrings, a knowing smile
    Part("Harriet Lockwood", "Philippa Moyse", "f", "middle", "the Lockwoods",
         Look(skin=(236, 198, 176), hair=(222, 196, 130), top=(236, 226, 204), under=(40, 40, 46), hair_style="bob",
              top_style="blazer", extra="earrings", mouth="smirk"), "bf_moyse"),
    # Tristan: floppy fair hair, an olive gilet over a blue shirt, an eager smile
    Part("Tristan Lockwood", "Rupert Kinsman", "m", "middle", "the Lockwoods",
         Look(skin=(236, 196, 172), hair=(200, 170, 110), top=(100, 110, 70), under=(150, 180, 220),
              hair_style="swept", top_style="jacket", mouth="smile", brows="raised"), "bm_kinsman"),
    # Sal: a platinum bun, a plum cardigan, a pen in the pocket for the tab
    Part("Sal Annear", "Gaynor Pawley", "f", "middle", "The Mermaid",
         Look(skin=(226, 180, 152), hair=(236, 228, 210), top=(110, 40, 70), under=(236, 226, 220), hair_style="bun",
              top_style="cardigan", extra="pen", extra_col=(30, 30, 30), mouth="smirk"), "bf_pawley"),
)

BY_CHARACTER = {p.character: p for p in CAST}

# The four sets (assets/backdrops/<id>.png, ComfyUI art chosen on a contact sheet 2026-11-13: the kitchen seed 404,
# the rest 303; data/contact-sheets/2026-11-13-marina-row-sets.png). Studio sets, so never graded for the time of
# day: the Row is painted at dusk with its lamps lit. Each has furniture across the front with its marks 3 px below
# the top (x, baseline y, scale, facing), because a drama has no lower third to hide where a figure ends.
SETS: dict[str, tuple[str, str, dict[str, tuple[int, int, int, int]]]] = {
    "marina_kitchen": ("Queenie's kitchen", "the Kernicks' kitchen behind the net loft: the range, nets and floats, "
                       "a dresser of blue-and-white plates, the oilcloth table",
                       {"a": (96, 151, 2, 1), "b": (224, 151, 2, -1), "c": (160, 151, 2, -1)}),
    "marina_mermaid": ("The Mermaid", "the Row's pub: the bar with its pumps, bottles and optics, a pub table, a "
                       "mermaid painting; mark a is behind the bar (Sal's place), b and c at the table", {"a": (70, 151, 2, 1), "b": (196, 153, 2, -1), "c": (266, 153, 2, -1)}),
    "marina_loft": ("The Loft", "the Lockwoods' small-plates restaurant: bare brick, Edison bulbs, the pass, a table "
                    "for two, the yachts through the window; mark a is behind the pass (Harriet's, or Kerra "
                    "working), b and c at the table",
                    {"a": (66, 151, 2, 1), "b": (200, 153, 2, -1), "c": (268, 153, 2, -1)}),
    "marina_row": ("the Row", "the quay at dusk: Queenie's net loft, the converted flats, The Loft's lit window, the "
                   "pontoon and yachts", {"a": (90, 153, 2, 1), "b": (204, 153, 2, -1), "c": (262, 153, 2, -1)}),
}


def register_sets() -> None:
    """Put the sets where the painter and the scenes find them, for this run only: in locations.BY_ID and MARKS,
    never in locations.LOCATIONS, so no Channel 7 writer is offered a television street as a place in town."""
    from newsroom import locations

    for sid, (name, blurb, marks) in SETS.items():
        locations.BY_ID[sid] = locations.Location(sid, name, blurb, "studio", (40, 50, 80), (80, 60, 50))
        locations.MARKS[sid] = dict(marks)


BIBLE = (
    "Marina Row is a short street on the far side of a Cornish harbour: a television street, a set at WTV's "
    "studios, not a real street in Port Wexley (not Harbour Row). Its old net lofts have just been turned into flats "
    "and a restaurant, The Loft, beside a new pontoon for yachts, and the last crabbing family on the Row now lives "
    "next door to money from away. The Kernicks: Queenie, seventies, a skipper's widow, sharp-tongued and "
    "immovable, who owns the last unconverted net loft and won't sell it; her son Davey, forties, skipper of the "
    "last crabber on the Row, stubborn, decent and behind on the boat's loan; and his daughter Kerra, nineteen, "
    "who wants out of Port Wexley and is secretly working at The Loft. The Lockwoods, incomers from London: "
    "Harriet, forties, charming and ambitious, who runs The Loft and wants Queenie's loft next door; and Tristan, "
    "forties, who works from home, is desperate to be liked by the locals and keeps making it worse. Sal Annear, "
    "fifties, landlady of The Mermaid, the Row's pub, knows everything about everyone and has history with Davey. "
    "Old town against new money, fought over moorings, lofts and a granddaughter."
)

OPENING = (
    "The pontoon: Tristan's petition to extend the yacht pontoon would take the crabbers' moorings, and with them "
    "Davey's living.",
    "The loft: Harriet offers for Queenie's net loft; Queenie says no; Harriet raises the offer.",
    "Kerra's secret: she is working at The Loft, saving to leave; Queenie must not find out.",
)

# With no model: the bible's first night, its cliffhanger as planned (docs/MARINA_ROW.md).
STAND_IN = (
    "The Petition",
    "What will Queenie do now she knows about Kerra?",
    "Kerra Kernick. In her apron.",
    (("marina_mermaid", ("Sal Annear", "Davey Kernick"), "Davey hears in the pub about Tristan's petition to "
      "extend the pontoon over the crabbers' moorings."),
     ("marina_loft", ("Harriet Lockwood", "Tristan Lockwood"), "Harriet tells Tristan she has made Queenie an offer "
      "for her loft, and that the petition must wait."),
     ("marina_kitchen", ("Queenie Kernick", "Davey Kernick", "Kerra Kernick"), "Queenie tears up Harriet's letter "
      "over tea; Kerra says she is going out with friends."),
     ("marina_row", ("Davey Kernick", "Tristan Lockwood"), "Tristan tries to win Davey over on the quay, and makes it "
      "worse."),
     ("marina_mermaid", ("Sal Annear", "Queenie Kernick"), "Queenie tells Sal she will never sell; Sal says nothing "
      "about what she has seen."),
     ("marina_row", ("Queenie Kernick", "Harriet Lockwood"), "Queenie, out with the bins, sees her granddaughter "
      "through The Loft's window in one of Harriet's aprons.")),
    # Spares: side scenes for spare minutes, changing nothing.
    (("marina_mermaid", ("Sal Annear", "Tristan Lockwood"), "Tristan tries to order something Sal doesn't stock."),
     ("marina_kitchen", ("Queenie Kernick", "Kerra Kernick"), "Queenie teaches Kerra her mother's way with a pasty "
      "crimp; Kerra is hopeless at it."),
     ("marina_row", ("Davey Kernick", "Sal Annear"), "Davey and Sal remember a storm on the quay twenty years ago.")),
)


def _series():
    from .soap import Series

    return Series(id="marina", title="Marina Row", bible=BIBLE, cast=CAST, sets=SETS, airs_at="20:20",
                  opening=OPENING, stand_in=STAND_IN, colour=(46, 96, 128),
                  quiet=(("marina_mermaid", ("Sal Annear", "Davey Kernick"), "the weather and the boats"),
                         ("marina_loft", ("Harriet Lockwood", "Tristan Lockwood"), "a new dish Tristan doesn't like"),
                         ("marina_kitchen", ("Queenie Kernick", "Kerra Kernick"), "a box of old photographs"),
                         ("marina_row", ("Tristan Lockwood", "Davey Kernick"), "the gulls, awkwardly")),
                  ident="Now on Channel 8: Marina Row.")


MARINA_ROW = _series()
