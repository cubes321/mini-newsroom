"""The fish quay's morning auction, worked out rather than written by the model, like the scores.

Port Wexley's inshore boats land on the fish quay and their catch is auctioned at 06:30 on weekdays.
Which boats went out, what each species landed and what it fetched come from a seeded draw on the
date: the season sets what is running, a rough day (about one in six, more in winter) keeps the small
boats in, and a thin landing fetches more a kilo. So every bulletin, Quayside at 13:00 and Coastwide's
consumer slot quote the same figures, and a week-on-week change adds up. The results are known once
the auction is over (07:30 on the broadcast clock); at the weekend the latest is Friday's.

Fictional, like the town: the boats, the skippers and the buyers are invented.

    python -m newsroom.quay [YYYY-MM-DD HH:MM]
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta

QUAY = "the fish quay"
AUCTION = time(6, 30)
RESULTS = time(7, 30)                   # the hammer's down and the prices are chalked up
AUCTION_DAYS = range(5)                 # Monday to Friday
# The fleet: (boat, skipper, kind). The kind decides what it lands.
FLEET = [("Morwenna", "Kenny Hocking", "netter"), ("Silver Darling", "Pete Rowse", "netter"),
         ("Girl Jenna", "Lou Trebilcock", "crabber"), ("Boy Josh", "Alan Curnow", "crabber"),
         ("Kittiwake", "Sue Penna", "handliner"), ("Three Sisters", "Mick Harvey", "trawler"),
         ("Guiding Star", "Dave Nance", "trawler"), ("Ocean Pearl", "Tony Jewell", "netter"),
         ("Bluebell", "Ray Bolitho", "handliner"), ("Tregarthen", "Colin Ellery", "crabber"),
         ("Sea Spray", "Jan Polglase", "handliner"), ("Endeavour", "Steve Bunt", "trawler")]
SMALL = {"handliner", "crabber"}        # the ones a rough day keeps in
BUYERS = "Penrose & Daughters (the merchant on the quay), the Harbour Lights restaurant, two fish vans from Greymouth"
# (species, unit, base £ a kilo, base kilos a boat of a kind lands, kinds that land it, peak month, how seasonal 0-1)
SPECIES = [
    ("mackerel", "kg", 2.20, 180, {"handliner", "netter"}, 8, 0.8),
    ("pollack", "kg", 6.50, 60, {"handliner", "netter"}, 9, 0.5),
    ("bass", "kg", 14.00, 25, {"handliner", "netter"}, 9, 0.6),
    ("brown crab", "kg", 3.60, 220, {"crabber"}, 7, 0.4),
    ("lobster", "kg", 19.00, 18, {"crabber"}, 7, 0.6),
    ("monkfish", "kg", 9.80, 70, {"trawler"}, 3, 0.3),
    ("hake", "kg", 5.40, 110, {"trawler", "netter"}, 6, 0.3),
    ("plaice", "kg", 3.20, 90, {"trawler"}, 4, 0.4),
    ("Dover sole", "kg", 21.00, 20, {"trawler"}, 5, 0.4),
    ("squid", "kg", 8.20, 45, {"trawler", "handliner"}, 11, 0.9),
    ("cuttlefish", "kg", 4.10, 60, {"trawler"}, 4, 0.8),
    ("scallops", "kg", 11.50, 40, {"trawler"}, 1, 0.5),
]
ROUGH_CHANCE = (0.10, 0.28)             # summer, winter


@dataclass(frozen=True)
class Lot:
    species: str
    kilos: int
    price: float                        # £ a kilo


@dataclass(frozen=True)
class Auction:
    day: date
    rough: bool
    boats: tuple[tuple[str, str, str], ...]        # the boats that went out
    lots: tuple[Lot, ...]                          # by value, the best first
    best_boat: tuple[str, str, float]              # boat, skipper, takings

    @property
    def total(self) -> float:
        return sum(l.kilos * l.price for l in self.lots)


def _season(month: int, peak: int, amount: float) -> float:
    """1 at the peak month, down to 1 - amount six months away."""
    return 1 - amount * (1 - math.cos(2 * math.pi * (month - peak) / 12)) / 2


def auction(day: date) -> Auction | None:
    """The day's auction, the same every time it is asked for; None on a non-auction day."""
    if day.weekday() not in AUCTION_DAYS:
        return None
    rng = random.Random(f"quay|{day.isoformat()}")
    winter = (1 - math.cos(2 * math.pi * (day.month - 7) / 12)) / 2      # 0 in July, 1 in January
    rough = rng.random() < ROUGH_CHANCE[0] + (ROUGH_CHANCE[1] - ROUGH_CHANCE[0]) * winter
    out = tuple(b for b in FLEET if not (rough and b[2] in SMALL) and rng.random() < 0.85)
    takings: dict[str, float] = {}
    lots = []
    for name, unit, base, per_boat, kinds, peak, amount in SPECIES:
        season = _season(day.month, peak, amount)
        landed = {b[0]: per_boat * season * rng.uniform(0.4, 1.6) for b in out if b[2] in kinds}
        kilos = int(sum(landed.values()))
        if kilos < 5:
            continue
        usual = per_boat * season * sum(1 for b in FLEET if b[2] in kinds) * 0.85
        scarcity = (usual / max(kilos, 1)) ** 0.35                       # a thin landing fetches more
        price = round(base * (1.25 - 0.25 * season) * scarcity * rng.uniform(0.9, 1.1), 2)
        lots.append(Lot(name, kilos, price))
        for boat, k in landed.items():
            takings[boat] = takings.get(boat, 0.0) + k * price
    lots.sort(key=lambda l: -l.kilos * l.price)
    best = max(takings.items(), key=lambda kv: kv[1], default=("", 0.0))
    skipper = next((b[1] for b in FLEET if b[0] == best[0]), "")
    return Auction(day, rough, out, tuple(lots), (best[0], skipper, round(best[1])))


def latest(now: datetime) -> Auction | None:
    """The most recent auction whose results are in."""
    day = now.date() if now.time() >= RESULTS else now.date() - timedelta(days=1)
    for back in range(7):
        a = auction(day - timedelta(days=back))
        if a:
            return a
    return None


def _week_before(a: Auction) -> Auction | None:
    return auction(a.day - timedelta(days=7))


def _change(now: float, then: float) -> str:
    if not then:
        return "none landed a week ago"
    pct = round(100 * (now - then) / then)
    return "level with last week" if abs(pct) < 3 else f"{'up' if pct > 0 else 'down'} {abs(pct)}% on last week"


def _money(x: float) -> str:
    return f"£{x:,.0f}" if x >= 100 else f"£{x:.2f}"


def summary(now: datetime) -> str:
    """One line for every writer's briefing: the latest auction's headline figures."""
    a = latest(now)
    if not a:
        return ""
    prev = _week_before(a)
    top, dear = a.lots[0], max(a.lots, key=lambda l: l.price)
    mack = next((l for l in a.lots if l.species == "mackerel"), None)
    parts = [f"{len(a.boats)} of {len(FLEET)} boats out" + (", a rough day" if a.rough else ""),
             f"{_money(a.total)} sold" + (f", {_change(a.total, prev.total)}" if prev else ""),
             f"{top.species} earned most ({top.kilos:,} kg at {_money(top.price)} a kilo)",
             f"the dearest {dear.species} at {_money(dear.price)} a kilo"]
    if mack and mack not in (top, dear):
        parts.append(f"mackerel {_money(mack.price)} a kilo")
    return f"The fish auction on the quay ({a.day:%A %d %B}): " + "; ".join(parts) + "."


def for_prompt(now: datetime) -> str:
    """Everything a writer may use about the quay, in words."""
    a = latest(now)
    if not a:
        return ""
    prev = _week_before(a)
    before = {l.species: l for l in prev.lots} if prev else {}
    rows = "\n".join(
        f"  - {l.species}: {l.kilos:,} kg at {_money(l.price)} a kilo"
        + (f" ({'up' if l.price > before[l.species].price else 'down'} from {_money(before[l.species].price)} last week)"
           if l.species in before and abs(l.price - before[l.species].price) >= 0.05 else "")
        for l in a.lots)
    kept_in = [b for b in FLEET if b not in a.boats]
    when = "this morning" if a.day == now.date() else f"on {a.day:%A}"
    return (f"QUAY FACTS (use these exact figures, boats and names; never invent a price or a landing):\n"
            f"The auction on {QUAY} {when} ({a.day:%A %d %B}, 06:30): {len(a.boats)} of {len(FLEET)} boats out"
            + (" (a rough day kept the small boats in)" if a.rough else "") + f"; {_money(a.total)} sold in all"
            + (f", {_change(a.total, prev.total)}" if prev else "") + ".\n"
            f"By value:\n{rows}\n"
            f"Top boat: the {a.best_boat[0]} ({a.best_boat[1]}), about {_money(a.best_boat[2])}.\n"
            + (f"Stayed in: {', '.join(f'the {b[0]}' for b in kept_in)}.\n" if kept_in else "")
            + f"The fleet: " + "; ".join(f"the {b} ({s}, {k})" for b, s, k in FLEET) + ".\n"
            f"The buyers: {BUYERS}. The auction is on weekdays only.")


if __name__ == "__main__":
    import sys

    at = datetime.strptime(" ".join(sys.argv[1:3]), "%Y-%m-%d %H:%M") if len(sys.argv) > 2 else datetime.now()
    print(summary(at))
    print()
    print(for_prompt(at))
