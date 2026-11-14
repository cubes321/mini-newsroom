# Channel 8's factual slot: the plan

Drafted and approved 2026-11-14. Built so far: the bestiary and the hide view (`entertainment/creatures.py`). The slot is 20:40 to 21:00 on Channel 8, after
Marina Row (docs/ENGINE.md, "Channel 8's evening").

**Decided with the user on 2026-11-14:**

- **Two series alternate**, by Channel 8 night (not weekday): a coastal **wildlife** series and a town celebrity's
  **travelogue**.
- **Canon, not fiction.** It is the town's real coast and its real residents: what the wildlife films see is true in
  Port Wexley, and the people met are residents with memories, as on Channel 7. Unlike Marina Row, it is not in
  `writers.FICTION_SHOWS`.
- **The animals are drawn in code**, like Gully: a small bestiary, approved on a contact sheet.
- **A new naturalist presents the wildlife series**: a new resident, a look on a contact sheet and a DramaBox voice
  by ear, like Maggie and Nigel.

## What the town already has, and what would be new canon

**Already in the world:**

- **The Salting**, where the bonfire is held and a path runs out by the estuary. It is also a council ward (Alan
  Penhaligon's). The estuary set shows mudflats, reeds and wading birds.
- **The estuary counters**: Carys Lunt (31 years on the county wader survey), Gwen Tarrant, Tom Redfern, Gordon
  Tonkin and Ned Trevena, plus Tom Nancarrow's wader count. They are ready-made contributors.
- **The slipway seal** (it "shifts a length up the slip as the school run boards") and **the slipway heron**, which
  a Last Ferry guest named Councillor Thorne.
- The backdrops: the estuary, the woods, the lighthouse rocks, the coast road, the seafront beach, the slipway, the
  harbour and the farm.

**New canon, for the user to approve:**

- **A nature reserve on the Salting**, with a warden. There is none in the world today; "reserve" only turns up as
  council money.
- **A grey seal colony** that pups on the rocks below the lighthouse each autumn. Today there is one seal, on the
  slipway.

Each of these becomes a fact of the town the first time it airs. The seasonal list (below) holds anything else of
the kind, so new canon is never made up live.

## The wildlife series

**Working title: *Tideline*** (to be chosen; "Wild Wexley" is the other candidate). Neither name is used in the town.

**The presenter.** The reserve's retired warden, in their sixties or seventies, who knows every counter by name. Two
unused names, checked against the town: **Rowan Polglase** or **Bryony Penberthy** (one of the two, or two looks of
each, on a sheet). They get a look in `sprites.LOOKS` (a field coat; binoculars would be a new `Look` field, so it
defaults to off and gets the `--sheet` before-and-after check in CLAUDE.md) and a DramaBox voice by ear.

**Filmed, not live.** The slot is after dark in winter, but the films are shot by day: every item pins its time of
day (`seg.work["tod"]`, which the player already honours for on-location shows) to day, or to dusk for a roost. The
writers are told that it's a film made earlier, so nobody says "tonight" or "good evening" from the mudflats. (On
11-02 Haiku followed a role card's "evening" over the brief.)

**An episode** is one creature or one place at this time of year:

| Part | What | On screen |
|---|---|---|
| Titles | the ident | the series' card |
| Open | the warden to camera: where we are and what we're looking for | the presenter on a backdrop |
| 4 sequences, about 3 minutes each | narration over the creature, then a resident on what they've seen (a counter, a fisherman, the lifeboat crew) | **the hide view** (below), then a two-shot on the backdrop |
| Spares | short "field notebook" moments for the minutes the plan leaves | the hide view, quiet narration |
| Close | what to look for this week and where; next time | the presenter in the last light |

**Facts come from the booking, not the script**, as the quiz scores and the council votes do. The back office's plan
books each sequence's creature, place, time of day and anything countable ("eleven pups"). The live writers read
those back, and the wildlife log is written from the booking when the episode airs, never taken from what Haiku
said.

**The seasons follow the real calendar**, from a hand-written list in code (like `calendar.py`: drafted, approved by
the user, no model). For November, for example: seal pups below the lighthouse, the waders back on the Salting,
brent geese, the starling roost over the reeds, the herons. The planner is given the month's list and the log of what
earlier episodes covered, and books nothing outside the list. A creature isn't booked again within a rest period,
like The Kettle's On's `REST_DAYS`. The creative editor in TODO.md takes that job over when it is built.

**The hide view** is a new view, the documentary's look (`scenes.draw_special`: a letterboxed backdrop with a strand
label) without the presenter on screen:

- the composed backdrop (after the sky, the grading and any parallax) is cropped and scaled up 2× with nearest
  neighbour, which reads as a long lens;
- the creature is drawn large at a spot on the crop;
- the warden's narration plays as a voice-over.

**Chosen on the contact sheet (2026-11-14, data/contact-sheets/2026-11-14-tideline-bestiary.png):** two shots.

- **Close-ups** are at 4×, with the place soft behind the creature, as a long lens's shallow focus does.
- **Wides** are at 2×, sharp, for setting the scene and for the flocks (the brent geese, the murmuration).

At its own size on the whole backdrop a creature is a speck, so that view is only for the presenter's two-shots.
`creatures.SHOTS` and `shot_for` hold this.

**The bestiary** goes in a new module (`entertainment/creatures.py`), with each creature a small drawing function
with an idle movement (a head turn, a bob, wings). The first eight are for winter: grey seal and pup, heron, curlew,
oystercatcher, brent geese (a flock), a starling murmuration (particles, which code does well), little egret and
otter. Each backdrop gets named spots where a creature may sit (like `locations.MARKS`). Spring's creatures go on a
sheet before March.

**Canon.** Each aired episode adds an entry to a **wildlife log** in the world, written from the booking when the
episode airs. Two places read it: the planner (so it doesn't repeat itself) and Channel 7's town talk (`talk.py`, as
the quiz result is), so Coastwide can mention it. The residents who spoke get memories as usual.

## The travelogue

**Working title: *The Coast Road with …*** (the host's name).

**The host is a town celebrity**, chosen by the user for each series from a shortlist. The town has 90 actors,
novelists, singers, comedians and cooks among its residents, but **only 21 have British voices**. The other 69 speak
the American visitor voices, which is wrong for a home-town celebrity walking their own coast. So the shortlist is
short:

- the regulars: **Lorna Quayle**, comedian and singer (73 appearances); **Nell Harrower** of the Saltmarsh Strings
  (52); **Ruth Ellery**, author of *The Salt Ledger* (18);
- a handful of one-time guests.

Recasting a well-known American-voiced resident is the other route, as `_recast_guests` did in November. Their look
is dressed by hand (as `[cast.X.look]` does for the one-offs) and shown on a sheet.

**A series is a journey of six legs** around the Greymouth coast. One planner call writes the whole route when a
series starts: where it begins and ends, the host's own reason for making it (retracing a grandparent's round, the
book they're writing), and the stops on each leg. It's like the soap's arc. The route goes to the user before the
first leg airs.

**A leg** has three or four stops, each on a backdrop (the coast road, Saltby village, the tea room, the lighthouse,
the farm, the village hall), filmed by day like the wildlife. At each stop the host meets a resident, booked by the
planner (people we know first, as the rundown planner does). It ends on where they've got to and where the next leg
starts. A **route map**, the coast drawn in code with the journey dotted along it, would open and close each leg.
It's optional.

**Canon.** The residents met get memories as usual. A finished series is remembered as one entry ("Lorna Quayle's
coast road, six legs"), which Channel 7's Last Ferry can bring the host back to talk about.

## How it's built

**Like The Kettle's On, shaped like an episode of the soap.** The Kettle's On (`entertainment/kettle.py`) is the
nearest precedent: a canon Channel 8 show that books its people in the back office, with tokens in its briefs, a
rest period and residents who get memories. The soap (`entertainment/soap.py`) gives the episode's shape: a plan,
items written live to their part of it, spares for the minutes it leaves, the closing item last in the slot, and
"aired" only once the last item has gone. The soap assumes fiction (every line a character), so its machinery won't
transfer whole. How much of either to share is settled when building, after reading both in full. The soap's planned
episode is the likeliest piece to lift into a shared module, since the TV movie and the anthology need it too.

- **The alternation.** Each series is a show of its own, with its own id, ident, programme card and captions. Tonight's
  is picked for the 20:40 slot the way `schedule.show_at` already picks Bonfire Night's or Christmas's version of a
  show (`special_night`, `special_day`), through a small registry rather than a picker inside the show.
- **The modules.** `entertainment/wildlife.py` and `entertainment/travelogue.py` hold each series' bible, presenter,
  prompts, booking and stand-in, as `kettle.py` and `marina_row.py` do.
- **The schedule.** `("20:40", <the factual slot>)`, then the closedown at 21:00.
- **Live items.** The residents' parts are Channel 7's interview item on a backdrop. The hide view is a new view
  mode, which needs a registry hook in `scenes`; none exists for this yet. Every line is the presenter or a named
  resident.

## What goes to the user, in order

1. **This plan**, with the new canon above (the reserve, the seal colony).
2. **The bestiary and the hide view**, on a contact sheet. Done 2026-11-14: ten creatures, the close-up at 4× and
   the wide at 2× chosen. The egret and the seal could take more drawing.
3. **The naturalist**: their name, a look (two or three on a sheet) and a voice (DramaBox, two or three by ear).
4. **November's list** (and the rest of the winter's), the hand-written seasonal calendar.
5. The series titles, and both idents by ear (an arrangement of Beacon each, like Wits').
6. Then the travelogue: **the first host** from the shortlist, their look, and the first route.

## Build order

1. Read `kettle.py`, `soap.py` and `documentary.py` in full, and decide what is shared. If the soap's planned episode
   is lifted out, check that Marina Row is unchanged (tests plus a scratch run with the model off).
2. The bestiary, the spots and the hide view, for the contact sheet.
3. The wildlife series: booking, live sequences, spares, the stand-in, the wildlife log. Then two scratch runs, one
   with the model off and one with it on, at 20:35 on a Channel 8 clock.
4. Town talk from the wildlife log.
5. The travelogue: the shortlist, the route planner, the legs, the map. A scratch run, then the alternation switched
   on.

## Open questions

- **Until the travelogue is built**, should the wildlife series air every Channel 8 night, or the closedown come
  forward to 20:40 on the travelogue's nights? I'd air the wildlife every night: it gives the planner's rest rules and
  the log a real test sooner.
- Should the warden appear on Channel 7 too (a Coastwide guest, Gordon's forecast for the seal pups), as Marina Row's
  actors can? Probably yes, since they're a resident.
- Does the slot need an advert break? The soap has none; with spares filling the slot, the factual slot wouldn't need
  one either.
