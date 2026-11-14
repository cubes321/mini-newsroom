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

**The presenter: Rowan Polglase** (chosen 2026-11-14), late sixties, the reserve's retired warden, who knows every
counter by name.

- **His look** is A of four on data/contact-sheets/2026-11-14-tideline-naturalist.png: white hair and beard, a tweed
  flat cap, an olive waxed jacket, binoculars on a strap. It's `sprites.LOOKS["naturalist"]`. The binoculars are a new
  value of `Look.extra`, not a new field, so no other character changed.
- **His voice** is `bm_polglase`, a DramaBox design: a soft Cornish accent, low and unhurried. It's B of three on
  data/voice-samples/tideline, with Kokoro's `bm_lewis` standing in.
- The speaker id `naturalist` is in config.toml. The show that speaks it isn't built yet.

**Filmed, not live.** The slot is after dark in winter, but the films are shot by day: every item pins its time of
day (`seg.work["tod"]`, which the player already honours for on-location shows) to day, or to dusk for a roost. The
writers are told that it's a film made earlier, so nobody says "tonight" or "good evening" from the mudflats. (On
11-02 Haiku followed a role card's "evening" over the brief.)

**An episode** is one creature or one place at this time of year:

| Part | What | On screen |
|---|---|---|
| Titles | the ident | the series' card |
| Open | the warden to camera: where we are and what we're looking for | the presenter on a backdrop |
| 4 sequences | narration over the creature, the first with the number; after each of the first three, a resident on what they've seen (a counter, a fisherman, the ferry crew) | **the hide view** (below), then a two-shot on the backdrop |
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
like The Kettle's On's `REST_DAYS`. The rests stay in code as hard limits (the user, 2026-11-14): the creative editor
(`entertainment/creative.py`, built that day) sits above them and judges what code can't: the same angle again, the
same story from a resident, a film that covers what the last one on that sight did.

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

**The first host: Lorna Quayle** (chosen 2026-11-14 from four: Lorna Quayle, Nell Harrower, Ruth Ellery, Hal Anand;
data/contact-sheets/2026-11-14-travelogue-hosts.png, data/voice-samples/travelogue-hosts).

- She is the town's most-seen celebrity, a comedian and singer with 73 appearances.
- Her running story is waiting. She waited fourteen minutes at the Saltby ferry office for a biscuit, retired her water
  joke, won the sorting office round with a tin of parkin, and is starting a waiting club.
- The proposed journey is the coast by every slow way there is (the ferries, the bus, a borrowed bike), collecting
  waiting stories along the way.
- **Her look**, chosen the same day, is A of three hand-dressed (data/contact-sheets/2026-11-14-lorna-quayle-looks.png):
  a canary-yellow raincoat over a navy top, gold earrings, and the face and ponytail she has had on air.
- **Her voice** is `bf_quayle`, C of three DramaBox designs (data/voice-samples/travelogue-lorna). It replaces the
  guest pool's `bf_emma`, which other residents share (Imelda Crane among them).
- Both are in `entertainment/travelogue.py`, which nothing reads until the series is built. Then her look is pinned
  to her by name and her voice moves to the new one, everywhere she appears.

**A series is a journey of six legs** around the Greymouth coast. One planner call writes the whole route when a
series starts: where it begins and ends, the host's own reason for making it (retracing a grandparent's round, the
book they're writing), and the stops on each leg. It's like the soap's arc. The route goes to the user before the
first leg airs.

**A leg** has three stops, each on a backdrop (the coast road, Saltby village, the tea room, the lighthouse,
the farm, the village hall), filmed by day like the wildlife. At each stop the host meets a resident, booked by the
planner (people we know first, as the rundown planner does). It ends on where they've got to and where the next leg
starts. A **route map**, the coast drawn in code with the journey dotted along it, would open and close each leg.
It's optional.

**Canon.** The residents met get memories as usual. A finished series is remembered as one entry ("Lorna Quayle's
coast road, six legs"), which Channel 7's Last Ferry can bring the host back to talk about.

## How it's built (Tideline, 2026-11-14)

`entertainment/wildlife.py` is the series. It was built like The Kettle's On (a canon booking in the back office, with
residents who get memories and a stand-in), in the soap's episode shape (planned items, spares, the close last). No
code was lifted out of `soap.py`: the soap assumes fiction, and only its shape carried over.

- **One lead sight an episode, chosen in code** (`pick`), not by the model.
  - Ten sights each resting 21 to 60 days ran dry within a fortnight when an episode used several. So the four
    sequences are angles on one sight, plus one sequence on a neighbour from the same backdrop (no number, no rest).
  - The pick is the sight longest unseen. When every sight is resting, it's the one rested longest. A rare sight
    leads on about one night in four once rested, at most once a winter.
  - `tests/test_wildlife.py` runs sixty nights at a Channel 8 night every two days and every four.
- **The number is drawn in code** from the sight's range, seeded by the date (`count_for`). The first sequence's brief
  carries it, to be said exactly.
- **The plan** (one call on The Chamber's route) gives a title, five watches (an angle each, close or wide; a flock always wide), three
  residents met, and the close. Known people first, with no new history; never a presenter, nobody twice, and
  nobody met in the last fourteen days. A plan that breaks those gives way to a stand-in made in code.
- **On air**, the episode runs: the ident, the open, then the first three sequences each followed by a meeting, the
  fourth (the neighbour's) and fifth sequences, the field notebook for spare minutes (three, then a break, round
  again with new ones), and the close at dusk. The first sequence alone carries the sight's facts and its number,
  and every item sees everything said before it in full.
  - Every item is out on location by day (`seg.work["location"]`, `["tod"]`, `["filmed"]`), with no LIVE tag.
  - Narration is in the hide, through two small engine hooks: `player.VIEW_HOOKS` (a show's say over the view) and
    `scenes.SCENES["hide"]`. There's no caption over the creature, and on air its feet are 60% of the way down, clear
    of the ticker.
- **Rowan** is `naturalist` in `models.py`, with a `Character` in `world.seed_characters`. A saved town picks him up
  on load.
- **The wildlife log** (`world.wildlife`): an episode is stamped aired when its first sequence, the one with the
  number, goes out (`player.AIRED_HOOKS`), since the archive keeps only about a night. Only aired episodes count for
  the rests, the residents' rest and `talk.wildlife`, the town's talk the next two days.
- **The schedule**: `("20:40", "tideline")`, and the closedown moves to 21:00. Tideline alternated with The Coast Road
  from the same day (`schedule.ROTATIONS`; "How it's built (The Coast Road)").

## How it's built (The Coast Road, 2026-11-14)

`entertainment/travelogue.py` is the series: *The Coast Road*, with Lorna Quayle (the working title chosen while
building).

- **She stays a resident.** Making her a presenter, as Rowan is, would have had `World.drop_presenter_people` delete
  her resident record at the next load: 73 appearances, her memories, and her place in threads and the archive.
  - So every line is a "guest" line with its speaker's name, as Marina Row's are (`writers.DEBATE_SHOWS`).
  - Her look and voice are pinned to her name on Channel 8 (`scenes.PINNED_LOOKS`, `world.PINNED_VOICES`).
  - At the first leg her `Person.voice` moves to `bf_quayle`, so Channel 7 hears her in it. Channel 7 still draws her
    as before.
- **The route** is one call a series: a title, her reason, and six legs, each with how she travels and three stops
  (a backdrop, the place, what happens, a resident and what they talk about).
  - `python -m entertainment.travelogue --plan` plans it on a read-only copy of the town and saves it to
    `data/travelogue/<host>.json`, which the station uses as it stands. So the user can read it first.
  - The first draft hung stops on dated news ("the crane booked for the seventeenth", "Monday's committee"). The legs
    air over a month, so the planner is now told nothing may hang on a date. The draft is kept as
    `lorna_quayle.draft1.json`; the route now saved is "Six Slow Ways and a Tin of Parkin".
- **A leg on air** runs: the opening, then three stops (Lorna arriving to camera, then meeting the stop's resident)
  with the road between them, the waiting moments for spare minutes (three, then a break), and the close at dusk.
  - It's filmed by day, with no LIVE tag, in its own view (`scenes.SCENES["road"]`, `player.VIEW_HOOKS`): Lorna in
    her raincoat, and the resident taking the frame when they speak.
  - The check hook keeps a to-camera piece Lorna's alone, and a meeting to Lorna and that stop's resident. It also
    points the meeting's memory at the resident, never at Lorna once an item.
- **The alternation** is `schedule.ROTATIONS`, a slot two shows share, read through `world.current()`. On a Channel 8
  night the slot goes to whichever series aired less recently before today, and tonight's booking holds it for the
  night. Tideline goes first; after the sixth leg Tideline has the slot until the user picks a new host.
- **Aired** is stamped when a leg's first stop goes out, and the next booking takes the next leg not yet aired.
- **The scratch run** (2026-11-20 on the clock, a town where Tideline aired two days before):
  - The rotation gave the slot to The Coast Road, the saved route was used, and leg 1 ran 20:43 to 21:00.
  - The writing was warm and funny. But the biscuit story was in every prompt ("fourteen" sixteen times), and the
    fish-quay stop read out the day's auction figures. Since fixed: her old story is in the first opening only, and
    there's a rule against figures and news of the day. That fix is untried with the model.
  - A known resident (Stan Tully) was again given a family detail.

## What goes to the user, in order

1. **This plan**, with the new canon above (the reserve, the seal colony).
2. **The bestiary and the hide view**, on a contact sheet. Done 2026-11-14: ten creatures, the close-up at 4× and
   the wide at 2× chosen. The egret and the seal could take more drawing.
3. **The naturalist**. Done 2026-11-14: Rowan Polglase, look A, voice B.
4. **The winter's seasonal list**. Done 2026-11-14 (`entertainment/seasons.py`): ten sights for November to February,
   five more waiting to be drawn, and the new canon approved: the Salting reserve and its hide, the seal colony below
   the light, the starling roost in the reeds, and the heronry in Wexley Woods. Spring's list is due before March.
5. The series titles, and both idents by ear (an arrangement of Beacon each, like Wits').
6. Then the travelogue: **the first host** from the shortlist, their look, and the first route. Done 2026-11-14: Lorna
   Quayle, look A, voice C. The first route waits for the build.

## Build order

1. Read `kettle.py`, `soap.py` and `documentary.py` in full, and decide what is shared. If the soap's planned episode
   is lifted out, check that Marina Row is unchanged (tests plus a scratch run with the model off).
2. The bestiary, the spots and the hide view, for the contact sheet.
3. The wildlife series: booking, live sequences, spares, the stand-in, the wildlife log. Built 2026-11-14, with two
   scratch runs, one with the model off and one with it on.
4. Town talk from the wildlife log. Built 2026-11-14 (`talk.wildlife`).
5. The travelogue: the shortlist, the route planner, the legs, the map. A scratch run, then the alternation switched
   on.

## Decided while building (2026-11-14), for the user to overrule

- **Tideline and The Coast Road alternate**, Tideline first. With the alternation a Tideline comes about every four
  days, so a sight comes round about every month, near its 21 to 35 day rest; and after the travelogue's six legs,
  Tideline has the slot every night again until the user picks a new host (a sight then comes round about every
  sixteen days, inside its rest: the picker takes the one rested longest, and the planner is shown what earlier
  episodes on it covered).
- **A leg counts as aired once its first stop has gone out**, as a Tideline episode does once its number has.
- **The Coast Road's ident** is the toy arrangement (Rock Pool's), until one is chosen by ear.
- **An advert break sits in the spare-minutes loop** (three notebook moments, then a break), as the soap's does. On
  the second model run the planned part filled 14½ minutes and only three notebook moments aired, so no break did.
- **No caption over the creature in the hide**, and on air its feet are 60% of the way down the frame. The approved
  sheet had 72%, before the lower third and ticker were drawn over it.
- **The ticker runs over the film**, as on The Kettle's On.

## Open questions

- Should Rowan appear on Channel 7 too (a Coastwide guest, Gordon's forecast for the seal pups), as Marina Row's
  actors can? Probably yes, since he's a resident.
