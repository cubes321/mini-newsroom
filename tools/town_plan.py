"""Draw Port Wexley close up, in streets and blocks, from newsroom/geography.py and newsroom/townplan.py.

    uv run python tools/town_plan.py [out.png]

The old town from the Salting road down to the seafront, every place in it numbered with a key beside it, and the
locator as it looks on air at three of them. A white marker is a place the town's stories already have; a yellow
one was chosen with the map. Reads nothing of the town.
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

import pygame  # noqa: E402

import town_map as tm  # noqa: E402
from newsroom import geography as g, locator, townplan  # noqa: E402

BOX, PX, K = (-0.32, 1.5, -1.08, 1.0), 150, 4          # miles (west, east, south, north); pixels a mile; the scale-up
NEW = ("harbour_row", "gulls_rest", "harbour_office", "harbour_wall", "quay_lane", "library", "bakery",
       "cannery_shed", "cannery_tap", "the_railway", "harbour_lights", "the_ferryman", "the_lugger",
       "anchor_and_bell", "the_pilchard", "the_lantern", "wexley_legion", "the_crown")
STREET_AT = {"Harbour Row": (0.03, 0.2), "Harrow Street": (0.52, 0.24), "Main Street": (0.98, 0.42),
             "Quay Lane": (0.27, 0.22), "Gull Lane": (0.33, 0.55), "Tallow Lane": (0.55, -0.47),
             "Cannery Lane": (0.56, -0.2), "Greenhill Road": (1.36, 0.14), "Mill Lane": (1.08, 0.83),
             "Tidewater Road": (1.3, 1.0), "the Polgrey road": (0.62, 0.92), "the Kessick road": (1.42, -0.6),
             "Lantern Row": (0.74, -0.86), "the promenade": (0.37, -1.02)}
SAMPLES = ("gulls_rest", "library", "cannery_tap", "stadium")


def draw_plan() -> tuple[pygame.Surface, list[g.Place]]:
    f = tm.Frame((BOX[0], BOX[1], BOX[2], BOX[3]), PX)
    tm._land_and_water(f)
    townplan.draw(f.s, f.at, PX, (tm.SEA, tm.SEA_DEEP, tm.SHIMMER))
    tm._dashed(f.s, tm.FERRY, f.at(g.BY_ID["harbour"].xy), f.at((BOX[0], 0.23)), 4, 3, 2)
    inside = [p for p in g.PLACES if BOX[0] < p.xy[0] < BOX[1] and BOX[2] < p.xy[1] < BOX[3]]
    inside.sort(key=lambda p: (-p.xy[1], p.xy[0]))
    for p in inside:
        x, y = f.at(p.xy)
        pygame.draw.rect(f.s, tm.INK, (x - 2, y - 2, 5, 5))
        pygame.draw.rect(f.s, tm.CHOSEN if p.id in NEW else tm.CANON, (x - 1, y - 1, 3, 3))
    big = pygame.transform.scale(f.s, (f.w * K, f.h * K))
    for name, xy in STREET_AT.items():
        tm._label(big, name, tm._big(f, K, xy), 13, townplan.ROAD, anchor="center")
    for n, p in enumerate(inside, 1):
        x, y = tm._big(f, K, p.xy)
        tm._label(big, str(n), (x + 11, y - 13), 15, tm.CHOSEN if p.id in NEW else tm.PAPER, bold=True)
    tm._label(big, "PORT WEXLEY, THE OLD TOWN", (16, 24), 20, bold=True)
    tm._label(big, "the Grey", tm._big(f, K, (-0.2, -0.55)), 18, tm.SHIMMER, anchor="center")
    tm._label(big, "to Saltby, 8 min", tm._big(f, K, (-0.17, 0.2)), 12, tm.FERRY, anchor="center")
    pygame.draw.rect(big, tm.INK, big.get_rect(), 3)
    return big, inside


def main(out: Path) -> None:
    pygame.init()
    pygame.display.set_mode((10, 10))
    plan, inside = draw_plan()
    pad, side = 20, 470
    sheet = pygame.Surface((pad * 3 + plan.get_width() + side, pad * 2 + 60 + plan.get_height()))
    sheet.fill((26, 28, 40))
    tm._label(sheet, "Port Wexley close up: the town in streets and blocks (newsroom/townplan.py), with "
                     f"{len(NEW)} places of their own", (pad, 26), 20, bold=True)
    tm._label(sheet, "Yellow: added 2026-11-21, from the places the stories name most. White: already on the map. "
                     "The pubs are the darts league's ten.", (pad, 52), 14)
    sheet.blit(plan, (pad, 70))
    x, y = pad * 2 + plan.get_width(), 84
    tm._label(sheet, "THE PLACES, north to south", (x, y), 16, tm.CHOSEN, bold=True)
    y += 26
    for n, p in enumerate(inside, 1):
        name = p.name[:1].upper() + p.name[1:]
        tm._label(sheet, f"{n:2d}  {name}", (x, y), 14, tm.CHOSEN if p.id in NEW else tm.PAPER)
        y += 19
    y += 14
    tm._label(sheet, "Not in this window: the Crown at Saltby (new),", (x, y), 13)
    tm._label(sheet, "the station side and the two grounds.", (x, y + 17), 13)
    y += 50
    tm._label(sheet, "THE LOCATOR ON AIR, at four places", (x, y), 16, tm.CHOSEN, bold=True)
    y += 24
    font = tm._font(14)
    for i, pid in enumerate(SAMPLES):
        img = locator.picture(pid, (72, 52), 3, True)
        cx, cy = x + (i % 2) * 232, y + (i // 2) * 176
        sheet.blit(img, (cx, cy))
        cap = font.render(locator.caption(pid), True, (240, 240, 240))
        sheet.blit(cap, (cx + (img.get_width() - cap.get_width()) // 2, cy + img.get_height() - 28))
    out.parent.mkdir(parents=True, exist_ok=True)
    pygame.image.save(sheet, str(out))
    print(f"saved {out} {sheet.get_size()}")


if __name__ == "__main__":
    main(Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/contact-sheets/town-plan.png"))
