"""What's about on the Port Wexley coast, month by month: Tideline's hand-written seasonal list (docs/FACTUAL.md).

The winter, November to February, approved by the user on 2026-11-14 with its new canon (CANON). Like newsroom/calendar.py it is
written by hand, no model, nothing saved. The wildlife planner books only sights from this list. A sight's numbers
are drawn in code from its range, seeded by the date, so the warden and the town's counters agree on air, and the
wildlife log keeps what was booked.

Each sight is shown at a place the bestiary has (entertainment/creatures.py SPOTS). `creature` is "" for one the
bestiary doesn't draw yet (NOT_DRAWN): it can be talked about, but not booked as a sequence.

    python -m entertainment.seasons [month]
"""
from __future__ import annotations

from dataclasses import dataclass

WINTER = (11, 12, 1, 2)


@dataclass(frozen=True)
class Sight:
    id: str
    what: str                          # as the planner and the writers are told it
    creature: str                      # the bestiary's id, or "" if not drawn yet
    months: tuple[int, ...]
    place: tuple[str, str]             # (backdrop, spot)
    note: str                          # the facts the writers get: when, where, why, what the counters have seen
    tod: str = "day"
    count: tuple[int, int] | None = None   # a range the booking draws from
    counted: str = ""                  # what's counted ("pups", "birds at the roost")
    rest_days: int = 21                # not booked again within this
    rare: bool = False                 # a lucky sighting: booked at most once a winter


SIGHTS: tuple[Sight, ...] = (
    # --- the seals
    Sight("seal_colony", "the grey seal colony in the coves below the Greymouth light", "seal_head",
          (10, 11, 12), ("lighthouse", "sea"),
          "The colony pups from October to December on the shingle of the coves under the light, which you can only see "
          "from the cliff path. The pups are born white and stay ashore about three weeks; the mothers wait off the rocks, "
          "heads up in the water. Eamon Trask, who kept the light, says one used to watch him work.",
          count=(8, 30), counted="pups in the coves", rest_days=28),
    Sight("weaned_pup", "a weaned seal pup resting on the cannery slipway", "pup",
          (11, 12), ("slipway", "ramp_low"),
          "A pup that has left the colony sometimes hauls out on the slipway to rest. It is not lost and must be left "
          "alone: the warden's rule is a bus length away and no dogs.",
          rest_days=35, rare=True),
    Sight("slipway_seal", "the slipway seal", "seal",
          (11, 12, 1, 2), ("slipway", "ramp"),
          "The big seal that hauls out on the cannery slipway on the falling tide and shifts a length up the slip when "
          "people come by. The Saltby ferry's early rower, Ruth Hallam, says it heckles her.",
          rest_days=28),
    # --- the waders on the Salting
    Sight("curlew", "curlews back on the Salting's mud", "curlew",
          (11, 12, 1, 2), ("estuary", "mud"),
          "Curlews winter on the estuary from September to March, probing the mud with that long bill; busiest at dawn "
          "on a falling tide, by the county wader survey's counters.",
          count=(40, 90), counted="curlews", rest_days=21),
    Sight("high_tide_roost", "the high-tide roost of oystercatchers on the Salting's shore", "oystercatcher",
          (11, 12, 1, 2), ("estuary", "shore"),
          "At high water the waders crowd onto the last dry shore by the pool: oystercatchers mostly, with curlews and "
          "redshank among them. It reached nearly four hundred birds this autumn.",
          count=(250, 450), counted="birds at the roost", rest_days=21),
    Sight("brent", "brent geese on the channel", "brent",
          (11, 12, 1, 2), ("estuary", "channel"),
          "Small dark geese that breed in the Arctic and winter here from October to March, grazing the eelgrass along "
          "the channel, which has moved this autumn. Some of the town's counters count them every morning.",
          count=(60, 180), counted="brent geese", rest_days=21),
    Sight("egret", "the little egrets in the pool", "egret",
          (11, 12, 1, 2), ("estuary", "pool_edge"),
          "Little egrets fish the Salting's pool all year; there are more in winter. Thirty years ago there were none on "
          "this coast.",
          count=(4, 14), counted="little egrets", rest_days=28),
    Sight("heron", "the grey heron in the pool", "heron",
          (11, 12, 1, 2), ("estuary", "pool"),
          "Herons fish the pool and the slipway all year. One slipway regular has a name in a resident's night-sights "
          "notebook: Councillor Thorne.",
          rest_days=28),
    # --- dusk
    Sight("starlings", "the starling roost over the Salting's reeds at dusk", "starlings",
          (11, 12, 1, 2), ("estuary", "sky"),
          "From November to February tens of thousands of starlings gather over the reeds at dusk and wheel before they "
          "drop in to roost. Best on a still, clear evening, about half an hour before dark.",
          tod="dusk", count=(8000, 30000), counted="starlings", rest_days=35),
    Sight("otter", "an otter by the reeds at first light", "otter",
          (11, 12, 1, 2), ("estuary", "reeds"),
          "Otters use the estuary but are seldom seen: mostly their spraints on the stones and tracks in the mud. A sight of "
          "one at first light is the warden's best moment of a winter.",
          tod="dusk", rest_days=60, rare=True),
)

# Wanted by the list, not in the bestiary yet: talked about, not booked as a sequence, until they're on a sheet.
NOT_DRAWN = {
    "redshank": "the redshank the ringing volunteers count (thirty-three to forty-two this autumn)",
    "avocet": "avocets, newly wintering on the estuary",
    "heronry": "the heronry in Wexley Woods, where the herons start nesting in February (needs a heron spot in the woods)",
    "frogspawn": "the first frogspawn in the woods' ditches, late February",
    "snowdrops": "snowdrops on the woods' banks in February",
}

# New canon this list sets, approved by the user on 2026-11-14.
CANON = (
    "The Salting is a nature reserve, with a hide on the edge of the reeds. Rowan Polglase was its warden for thirty "
    "years and retired in 2021.",
    "A grey seal colony pups each autumn in the coves below the Greymouth light, seen only from the cliff path.",
    "Tens of thousands of starlings roost in the Salting's reeds from November to February.",
    "Herons nest in Wexley Woods from February (a heronry of about ten nests).",
)


def in_season(month: int) -> list[Sight]:
    return [s for s in SIGHTS if month in s.months]


if __name__ == "__main__":
    import sys
    for m in ([int(sys.argv[1])] if len(sys.argv) > 1 else WINTER):
        print(f"--- month {m}")
        for s in in_season(m):
            n = f"  {s.count[0]}-{s.count[1]} {s.counted}" if s.count else ""
            print(f"  {s.id:16} {s.what}{n}{'  (rare)' if s.rare else ''}")
