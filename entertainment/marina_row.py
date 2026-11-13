"""Marina Row, Channel 8's soap (docs/MARINA_ROW.md, the series bible): its cast so far. The engine (the scene
item, episodes, cliffhangers as town talk) is still to build; nothing reads this module yet.

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
                       "mermaid painting", {"a": (70, 151, 2, 1), "b": (196, 153, 2, -1), "c": (266, 153, 2, -1)}),
    "marina_loft": ("The Loft", "the Lockwoods' small-plates restaurant: bare brick, Edison bulbs, the pass, a table "
                    "for two, the yachts through the window",
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
