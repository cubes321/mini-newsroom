"""The town's businesses: a non-definitive directory the advert writer draws on.

Until 2026-11-27 the advert writer was told only what was already on air and to advertise something else, so
every advert was a new business ("Wexley Compass & Chart House", "Wexley Lantern & Glass Works"), each aired once
or twice and was gone within a night and a half, and residents were handed trades that weren't theirs: Brenda
Fisk, the tailor, had six businesses, a night nurse made pies. Now the code chooses before the model writes:

- most adverts (KNOWN_SHARE) re-advertise a business from the directory: the one advertised longest ago that
  isn't on air. Its name, owner, place and tagline are fixed here; the writer gives it a new angle.
- the rest go off the list: the code hands the writer a trade the town hasn't got yet (TRADES), it invents a
  business of that kind with a new owner, and the business joins the directory if it passes the checks. Past
  SLOW_AT businesses, fewer are invented (NEW_SHARE_LATER), so the ones we know keep coming back.

CORE is the hand-written part (approved by the user 2026-11-27: the residents' own businesses, the darts league's
ten pubs, four kept from the old pool and eighteen to fill the town's gaps). `World.directory` holds the rest: the
invented businesses and, for every one, what the adverts have established (a landlord, a tagline) and when it was
last advertised. A non-definitive list: other writers may still name a business that isn't in it.

    python -m newsroom.directory          # the directory as the advert writer sees it (reads the world, writes nothing)
"""
from __future__ import annotations

import random
import re
import time
from dataclasses import dataclass, replace

from .world import World

KNOWN_SHARE = 0.75                 # adverts for a business the directory knows,
NEW_SHARE_LATER = 0.1              # the share invented once there are
SLOW_AT = 80                       # this many businesses (not counting the seeds)
LAST_LINES_KEPT = 4                # an advert's lines kept, so the next one for the business says something else


@dataclass(frozen=True)
class Business:
    name: str
    kind: str                                 # the trade: "butcher", "pub", "fish and chips"
    where: str = ""                           # for the end card ("Harbour Row, above the Quay Steps")
    backdrop: str = ""                        # a locations.py id, or the writer chooses
    owner: str | None = None                  # who speaks for it, if anyone does
    owner_role: str | None = None
    owner_gender: str | None = None
    note: str = ""                            # a detail for the writer
    tagline: str = ""                         # once it has one, every advert ends on it


def _b(name, kind, where, backdrop, owner=None, role=None, gender=None, note="", tagline="") -> Business:
    return Business(name, kind, where, backdrop, owner, role, gender, note, tagline)


# The seeds' businesses (adverts.SEEDS, always on air): in the directory so nothing invents a rival, never
# chosen for a new advert of their own.
SEED_BUSINESSES: tuple[Business, ...] = (
    _b("Ramachandran's Bakery", "bakery", "Harrow Street market, from six", "market_shed", "Dev Ramachandran"),
    _b("The Lighthouse Café", "café", "Greymouth Point, daily from ten", "lighthouse", "Nuala Brennan"),
    _b("The Saltby Foot Ferry", "foot ferry", "Harbour steps, half-hourly from seven", "estuary"),
    _b("Tidewater Town FC", "football club", "Tidewater Stadium", "stadium"),
    _b("Pell's Cannery Ghost Tours", "ghost tours", "The old cannery, nightly at eight", "cannery", "Gordon Pell"),
    _b("Fowle & Sons Hardware", "hardware shop", "The high street, by the post office", "main_street", "Jasper Fowle"),
    _b("Harrow Street Market", "street market", "Harrow Street, Saturdays from eight", "market"),
    _b("Okonkwo's Taxis", "taxis", "Ring Port Wexley four-four-one", "residential_street", "Kenji Okonkwo"),
)

CORE: tuple[Business, ...] = (
    # ---------------------------------------------- the residents' own, as the news knows them
    _b("Gull's Rest Fish & Chips", "fish and chips", "Harbour Row, above the Quay Steps", "harbour", "Dolores Finch",
       "owner, Gull's Rest Fish & Chips", "f", "Out and About gave it four stars, for the hake"),
    _b("Brenda Fisk Tailoring", "tailor", "Main Street, Tuesday to Saturday", "main_street", "Brenda Fisk",
       "tailor and alterations, Main Street", "f", "alterations, repairs, school uniforms taken up",
       "Hems taken up, hearts let out."),
    _b("The Harbour Row Sail Loft", "sailmaker", "Harbour Row, from seven", "harbour", "Bernard Moss",
       "sailmaker, Harbour Row", "m", "sails cut and mended; Nell Osgood is his apprentice"),
    _b("Dougal Crane Roofing", "roofer", "Port Wexley, ring the office", "residential_street", "Dougal Crane",
       "roofer, Port Wexley", "m", "roofs, gutters, and chimneys swept", "Dry heads, honest prices"),
    _b("Kit's Coffee Stall", "coffee stall", "Harrow Street, from seven", "market", "Kit Anand",
       "coffee stall owner, Harrow Street", None, "a stall under an awning on Harrow Street"),
    _b("Thorne Pie Kitchen", "pie shop", "Harrow Street, from eight", "market", "Mabel Thorne",
       "Owner, Thorne Pie Kitchen", "f", "the town's pie shop"),
    _b("Harrow Street Smokehouse", "smokehouse", "Harrow Street, by the market", "market_shed", "Tamsin Rowe",
       "owner, Harrow Street Smokehouse", "f", "kippers, smoked mackerel, smoked cheese"),
    _b("Lind's Bikes and Bakes", "bike repair", "Harrow Street", "market", "Tessa Lind",
       "owner, bakery and bike repair, Harrow Street", "f", "bikes mended while you wait, with a bun"),
    _b("Lusk's Sweet Shop", "sweet shop", "Harrow Street", "main_street", "Peggy Lusk",
       "sweet shop owner, Harrow Street", "f", "sweets from the jar, by the quarter"),
    _b("Winnie's Hot Cocoa", "cocoa stall", "On the quay, from six", "harbour", "Winnie Gorse",
       "hot cocoa stallholder, Port Wexley quay", "f", "cocoa for the boats going out and the walkers"),
    _b("Gossard's Tackle Hire", "tackle and bait", "The fish quay, from six", "fish_quay", "Lenny Gossard",
       "tackle hire, Port Wexley fish quay", "m", "rods, lines and bait for the day, for visitors and locals"),
    _b("Carrick Wool", "wool shop", "Harbour Row", "main_street", "Ruby Carrick", "owner, Carrick Wool, Harbour Row",
       "f", "wool, patterns, and a knitting circle"),
    _b("Ferrier's Haberdashery", "haberdashery", "Harrow Street, from nine", "main_street", "Gwen Ferrier",
       "shopkeeper, Ferrier's Haberdashery, Harrow Street", "f", "buttons, ribbon, thread, zips"),
    _b("Galbraith's Corner Shop", "corner shop", "Main Street, open till ten", "main_street", "Ruth Galbraith",
       "owner, Galbraith's corner shop, Main Street", "f", "open late: milk, papers, the lot"),
    _b("The Bay Window", "tea room", "The bottom of the cliff path", "tea_room", None, None, None,
       "a tea room with a big bay window on the sea; Out and About gave it four stars, for the scone and the view"),
    _b("The Saltby Players", "amateur theatre", "The village hall on the green, Saltby", "village_hall", None, None,
       None, "the amateur theatre company over the water; Out and About gave it four stars"),
    # ---------------------------------------------- the darts league's ten pubs (darts.PUBS, geography.py)
    _b("the Anchor and Bell", "pub", "Quay Lane, under the church bell", "pub"),
    _b("the Lugger", "pub", "The fish quay", "pub", note="the fishermen's pub"),
    _b("the Harbour Lights", "pub", "The top of Harbour Row", "pub"),
    _b("the Ferryman", "pub", "By the Quay Steps", "pub", note="where the Saltby ferry goes from"),
    _b("the Pilchard", "pub", "Tallow Lane, behind the old cannery", "pub"),
    _b("the Crown at Saltby", "pub", "On the green, Saltby", "pub", "Ray Tollan", "landlord, the Crown at Saltby", "m"),
    _b("the Lantern", "pub", "Lantern Row, above the seafront", "pub", "Frank Dyer", "landlord, the Lantern", "m"),
    _b("the Cannery Tap", "pub", "Cannery Lane", "pub", "Gideon Ashby", "landlord, the Cannery Tap", "m"),
    _b("the Wexley Legion", "social club", "Main Street, by the town hall", "pub"),
    _b("the Railway", "pub", "By the station, Mill Lane", "pub"),
    # ---------------------------------------------- kept from the old advert pool, renamed
    _b("Tallack's Ropes", "ropemaker", "Harbour Row, six days a week", "harbour", "Ruth Tallack",
       "ropemaker, Harbour Row", "f", tagline="Tied up tight since 1871"),
    _b("Oakshott Sea Glass", "glassblower", "Harbour Row, by the slipway", "slipway", "Ruth Oakshott",
       "glassblower, Harbour Row", "f", "glass blown from the beach's own sea glass"),
    _b("Trevail's Kites and Lanterns", "kite and lantern mender", "Harrow Street, Saturdays", "main_street",
       "Nan Trevail", "mender, Harrow Street", "f", tagline="Bring it broken, leave it flying"),
    _b("Veryan's Chandlery", "chandler", "Harbour Row, from eight", "harbour", "Sol Veryan",
       "chandler, Harbour Row", "m", "everything for the boat"),
    # ---------------------------------------------- new, for the trades the town hadn't got
    _b("Jago's Butchers", "butcher", "Main Street, from eight", "main_street", "Pete Jago",
       "butcher, Main Street", "m", "sausages from the pigs on Harrow Hill"),
    _b("Nico's on Quay Lane", "barber", "Quay Lane, no appointment needed", "residential_street", "Nico Ferreira",
       "barber, Quay Lane", "m"),
    _b("Sea Pinks", "florist", "Harrow Street", "main_street", "Lowri Kemp", "florist, Harrow Street", "f"),
    _b("Harrow Street Pharmacy", "chemist", "Harrow Street, by the library", "main_street"),
    _b("Spindrift Books", "second-hand bookshop", "Lantern Row", "residential_street", "Ambrose Pike",
       "bookseller, Lantern Row", "m"),
    _b("The Suds Bucket", "launderette", "Main Street, seven till nine", "main_street"),
    _b("Station Garage", "garage", "By the station", "main_street", "Wes Kitto", "mechanic, Station Garage", "m",
       "MOTs, tyres, and the coast bus's spare parts"),
    _b("Salting Vets", "vet", "Greenhill Road", "residential_street", "Anjali Rao", "vet, Greenhill Road", "f"),
    _b("Kessick Bay Seal Trips", "boat trips", "From the Quay Steps", "harbour", "Jory Hext",
       "skipper, Kessick Bay Seal Trips", "m", "seal-watching trips round to Kessick Bay; gift vouchers in winter"),
    _b("Sea Thrift Guest House", "guest house", "Lantern Row", "residential_street", "June Ashcroft",
       "landlady, Sea Thrift Guest House", "f"),
    _b("Moretti's Ices", "seafront kiosk", "The seafront kiosk", "seafront", "Gina Moretti",
       "owner, Moretti's Ices, the seafront", "f", "ice cream in summer, hot chocolate in winter"),
    _b("Beer's Driving School", "driving school", "Ring the office", "residential_street", "Carol Beer",
       "driving instructor", "f"),
    _b("Miss Hendra's School of Dance", "dance school", "The church hall", "church", "Elaine Hendra",
       "dance teacher, the church hall", "f", "tap and ballet for every age"),
    _b("Bolitho Plumbing & Heating", "plumber", "Port Wexley, call-outs day and night", "residential_street",
       "Ross Bolitho", "plumber, Port Wexley", "m"),
    _b("Polgrey Farm Shop", "farm shop", "Polgrey, at the bridge", "farm", note="eggs, veg and cheese from the farm"),
    _b("Mabey's Greengrocers", "greengrocer", "Harrow Street", "market", "Hetty Mabey",
       "greengrocer, Harrow Street", "f"),
    _b("The Wexley Picture House", "cinema", "Main Street", "main_street", note="the town's small cinema"),
    _b("Hext's Fresh Fish", "fishmonger", "The fish quay", "fish_quay", "Sian Hext",
       "fishmonger, the fish quay", "f", "the fish off the boats that morning; her brother Jory runs the seal trips"),
)

# What the writer is handed when it goes off the list: a trade the directory hasn't got, so the town gets a
# florist rather than a seventh sail mender. Once each is taken, any of them again.
TRADES: tuple[str, ...] = (
    "hairdresser", "toy shop", "music shop", "photographer", "piano teacher", "dog groomer", "window cleaner",
    "electrician", "locksmith", "bike hire", "kayak hire", "pottery classes", "yoga classes", "antiques shop",
    "junk shop", "picture framer", "wedding dresses", "cobbler", "watch and clock repairs", "pet shop",
    "opticians", "cake maker", "delicatessen", "cheese shop", "wine merchant", "gift shop", "art gallery",
    "jeweller", "carpet fitter", "removals", "builders' merchant", "tree surgeon", "gardener", "boatbuilder",
    "outboard engine repairs", "sailing school", "swimming lessons", "gym", "bowls club", "chip van",
    "curry house", "Chinese takeaway", "pizza takeaway", "tea dance", "bingo", "choir", "charity shop",
    "craft fair", "bed shop", "printer", "travel agent", "nursery garden", "egg stall", "café on wheels",
    "children's party entertainer", "allotment society", "walking tours", "computer repairs", "decorator",
)


def _key(name: str) -> str:
    return " ".join(name.lower().split())


# Words that say nothing about which business it is, for telling near-duplicates apart.
_FILLER = {"the", "and", "co", "of", "at", "on", "in", "port", "wexley", "ltd", "company", "shop", "s"}


def _words(name: str) -> set[str]:
    return {w for w in re.findall(r"[a-z]+", name.lower().replace("'s", "")) if w not in _FILLER}


def near(a: str, b: str) -> bool:
    """Two names for the same business: "Wexley Pie & Pasty Hatch" and "Wexley Pasty & Pie Hatch"."""
    wa, wb = _words(a), _words(b)
    if not wa or not wb:
        return _key(a) == _key(b)
    return len(wa & wb) / len(wa | wb) >= 0.6


_WEXLEY_X_AND_Y = re.compile(r"^(port\s+)?wexley\s+[\w']+\s*(&|and)\s*[\w']+", re.I)


def formulaic(name: str) -> bool:
    """The shape every invented business had by 2026-11-27: "Wexley Lantern & Wick Repairs"."""
    return bool(_WEXLEY_X_AND_Y.match(name.strip()))


# ------------------------------------------------------------- the directory as it stands


def _record(world: World, name: str) -> dict:
    """The world's record of a business, made on first use. Caller holds the world's lock."""
    k = _key(name)
    rec = world.directory.get(k)
    if rec is None:
        rec = world.directory[k] = {"name": name}
    return rec


def businesses(world: World, seeds: bool = False) -> list[Business]:
    """Every business the directory knows: CORE with what its adverts have established (a landlord, a tagline),
    then the invented ones. `seeds` puts the seeds' businesses first."""
    with world.lock:
        recs = {k: dict(v) for k, v in world.directory.items()}
    fields = Business.__dataclass_fields__
    out = []
    core_keys = set()
    for b in (SEED_BUSINESSES if seeds else ()) + CORE:
        core_keys.add(_key(b.name))
        rec = recs.get(_key(b.name), {})
        learned = {f: rec[f] for f in ("owner", "owner_role", "owner_gender", "tagline")
                   if rec.get(f) and not getattr(b, f)}
        out.append(replace(b, **learned))
    seed_keys = {_key(b.name) for b in SEED_BUSINESSES}
    for k, rec in recs.items():
        if rec.get("invented") and k not in core_keys and k not in seed_keys:
            out.append(Business(**{f: rec.get(f) or fields[f].default for f in fields}))
    return out


def find(world: World, name: str) -> Business | None:
    k = _key(name)
    return next((b for b in businesses(world, seeds=True) if _key(b.name) == k), None)


def clash(world: World, name: str) -> str | None:
    """The directory's business an invented name is too close to, if any."""
    return next((b.name for b in businesses(world, seeds=True) if near(name, b.name)), None)


def owners(world: World) -> set[str]:
    return {b.owner.lower() for b in businesses(world, seeds=True) if b.owner}


# ------------------------------------------------------------------ choosing the next advert


@dataclass(frozen=True)
class Choice:
    known: Business | None = None             # re-advertise this one,
    trade: str = ""                           # or invent one of these
    last_lines: tuple[str, ...] = ()          # what its last advert said


def choose(world: World, on_air: list[str], rng: random.Random | None = None, mode: str | None = None) -> Choice:
    """The next advert: a known business not on air, advertised longest ago (never tried first), or a trade to
    invent. `mode` "known" or "new" forces one (the CLI, the tests); a known advert with nothing off air invents."""
    rng = rng or random.Random()
    live = {_key(n) for n in on_air}
    known = businesses(world)
    with world.lock:
        tried = {k: float(v.get("tried") or 0.0) for k, v in world.directory.items()}
    spare = [b for b in known if _key(b.name) not in live and not any(near(b.name, n) for n in on_air)]
    share_new = 1 - KNOWN_SHARE if len(known) < SLOW_AT else NEW_SHARE_LATER
    if mode != "new" and spare and (mode == "known" or rng.random() >= share_new):
        b = min(spare, key=lambda b: (tried.get(_key(b.name), 0.0), rng.random()))
        with world.lock:
            last = tuple(world.directory.get(_key(b.name), {}).get("last_lines") or ())
        return Choice(known=b, last_lines=last)
    kinds = {b.kind.lower() for b in businesses(world, seeds=True)}
    trades = [t for t in TRADES if t.lower() not in kinds] or list(TRADES)
    return Choice(trade=rng.choice(trades))


def tried(world: World, name: str, now: float | None = None) -> None:
    """An advert for it was attempted: the next pick moves on, even when this one fails (too long, refused)."""
    with world.lock:
        _record(world, name)["tried"] = now or time.time()


def advertised(world: World, script, choice: Choice) -> None:
    """A voiced advert went into the pool: remember what it said, and what it established. An invented business
    joins the directory; a known one with no landlord or tagline keeps the ones this advert gave it."""
    with world.lock:
        rec = _record(world, script.business)
        rec["adverts"] = int(rec.get("adverts") or 0) + 1
        rec["last_made"] = world.last_date
        rec["last_lines"] = [l.text for l in script.lines][:LAST_LINES_KEPT]
        if choice.known is None:
            rec.update(invented=world.last_date, kind=choice.trade, where=script.where, backdrop=script.backdrop)
        for f, v in (("owner", script.owner_name), ("owner_role", script.owner_role),
                     ("owner_gender", script.owner_gender), ("tagline", script.tagline)):
            if v and not (choice.known and getattr(choice.known, f)) and not rec.get(f):
                rec[f] = v


def _cli() -> int:
    from . import world as world_mod

    w = world_mod.load()
    with w.lock:
        recs = dict(w.directory)
    for b in businesses(w, seeds=True):
        r = recs.get(_key(b.name), {})
        tag = "seed" if _key(b.name) in {_key(s.name) for s in SEED_BUSINESSES} else ("invented " + r["invented"] if r.get("invented") else "")
        print(f"{b.name:<34} {b.kind:<22} {b.owner or '-':<18} {r.get('adverts', 0):>3} ads"
              f"  {r.get('last_made', ''):<10} {tag}")
    print(f"{len(businesses(w))} businesses, not counting the {len(SEED_BUSINESSES)} seeds")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
