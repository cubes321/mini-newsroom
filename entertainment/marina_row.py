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
