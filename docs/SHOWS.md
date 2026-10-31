# New shows for channel 7

Agreed in a brainstorm on 2026-10-30. The day had two long stretches of rolling news, 09:00 to 18:45
and 20:00 to 22:00 (apart from the 21:00 documentary). Seven shows go into them. Three other ideas,
*The Kettle's On*, *Harbour Row* and *Wexley Wits*, belong on the entertainment channel instead (see
`docs/ENGINE.md`).

Each show is a `schedule.Show`: a running order of item types, a cast, a set and a tone. A show costs
little when it reuses what exists. Most of the cost is in the things marked **new** below: an item
type, a set, a presenter (a look on a contact sheet, a voice by ear) or a source of facts.

## A day's schedule

| Time | Show | Notes |
|---|---|---|
| 06:00 | *Morning Tide* | as now |
| 09:00 | News | |
| 10:00 | **Have Your Say** | the news phone-in, an hour |
| 11:00 | News | |
| 13:00 | **Quayside** | business, half an hour |
| 13:30 | News | |
| 15:00 | **Out and About** | travel, culture and food, 45 minutes |
| 15:45 | News | |
| 16:00 | **Rock Pool** | children's TV, 45 minutes |
| 16:45 | News | |
| 18:45 | *Full Time* | as now |
| 19:00 | *Coastwide* | as now |
| 20:00 | **The Inquiry** | investigations, half an hour |
| 20:30 | **The Panel** | the debate, half an hour |
| 21:00 | News | the documentary airs at the first bumper, as now |
| 22:00 | *The Last Ferry* | as now |
| 23:00 | News | |

On a council night **The Chamber** takes 20:00 to 21:00 instead of *The Inquiry* and *The Panel*.

Rolling news still fills about five hours of the day, and the breaks between shows keep the bulletins
coming.

## The shows

### Have Your Say (10:00, an hour): the news phone-in. BUILT 2026-10-30

Jonah Pike, a former local-radio DJ, moves from the *Morning Tide* sofa to the phone-in desk after
breakfast. Each hour has one question from the day's news ("Should the lorry ban stay once the slates
are fixed?"). Viewers ring in, and a studio guest, the official or person at the heart of the story,
answers. Between calls come the travel news and the bulletin headlines.

- **New:** a `call` item: a caller on the line (a voiced guest with a phone caption and a waveform
  instead of a face), Jonah replying, and sometimes the studio guest answering. Callers are residents,
  cast like vox-pop voices, and some ring back on later days with their memories.
- **Reuses:** the interview set, the guest memory, the tip-line (a viewer tip can become a caller).
- **Size:** medium.
- **Built** (`phonein.py`, the `call` item, `schedule.py`, `writers._PHONEIN`): from 08:30 the back office
  books the question (`[phonein]`, route `phonein`), the studio guest and where they stand, and four to
  six kinds of caller with different views; each call takes the next in turn, and someone who rang on an
  earlier day may ring again. If nothing is booked by 10:00, the day's most-covered story and an official
  stand in. A call (`CallScript`) casts its caller like a vox pop's passer-by and names the studio
  guest on their own lines; the caller is voiced through a telephone band (`tts.telephone`) and shown as a
  box with their name, where they're ringing from and their voice's waveform, while the guest stays in the
  armchair all hour. A call files under the question's thread without moving it, and never opens one.
  Running order: Jonah's open, the guest on the question, two calls, then a quarter-hour loop of Dana's
  headlines from the news desk, calls, Jonah's travel (with the tides), a break, back to the guest with
  the callers' points, more calls; Jonah's close. Calls of about a minute, with the guest answering in
  most. A viewer tip can become a caller. The bumper uses the news arrangement, and the set is the interview armchairs, until each has
  its own.

### Quayside (13:00, half an hour): business. BUILT 2026-10-30

The harbour and the port trade, local firms, shop openings and closings, jobs, high-street prices.
It leads on the morning's fish auction: what landed, what it fetched, up or down on last week.

- **New:** `quay.py`, the day's landings and auction prices worked out in code from the season, the
  weather and the boats out, so every show quotes the same figures (as `sport.py` does for the
  scores). The bulletins and *Coastwide*'s consumer slot can use them too.
- **New:** a presenter, a business reporter who knows the quay.
- **Reuses:** the consumer slot, interviews (a trader, the harbourmaster), field reports from the
  fish quay and the market.
- **Size:** medium (most of it in `quay.py`).

### Out and About (15:00, 45 minutes): travel, culture and food. BUILT 2026-10-30

Days out along the Greymouth coast, the town's culture (a gallery opening, the amateur dramatics, a
music night, the library's talks) and food (a café or restaurant visited and reviewed, a recipe from a
local kitchen, what's in season on the market). Mostly out on location, which suits the country
backdrops.

- **New:** a presenter, out and about.
- **New:** a `review` item: a visit to a place to eat or a show, with a verdict out of five that the
  world remembers, so the place can be revisited or the owner can answer back.
- **Reuses:** features, vox pops, the country and town backdrops.
- **Size:** small to medium.
- **Built** (`outabout.py`, the `review` item, `schedule.py`, `writers._OUTABOUT`): Meg Trethewey (`travel`),
  late 40s, twenty years a ranger on the Greymouth coast path (person A of three, chosen on a contact
  sheet), presents the whole show on location: no studio and nobody to hand back to. Her pieces to camera
  are field reports (the open, her walk for the weekend with the tides, what's on, the close); features
  have a local showing her round; a review (`ReviewScript`) visits a place to eat or a show and gives it
  stars out of five, with the owner, cook or a player speaking for it, and the stars go up on a card as
  she gives them; one a lap, four or five an afternoon. The town keeps every review (`World.reviews`): a place rests a fortnight before it is
  reviewed again, an older one may be revisited, and on Coastwide an owner reviewed in the last week may
  answer back. The show is light but not the news: no big running story, no threads, and breaking news
  never sends Meg. Her voice is provisional (af_river, British); the bumper uses the news arrangement.

### Rock Pool (16:00, 45 minutes): children's TV. BUILT 2026-10-30

A presenter and Gully, a herring-gull puppet with opinions. A "make" in the studio, story time (Hugh
Tremayne reads a town legend), viewers' drawings and letters, an animal visitor (the lifeboat's cat, a
farm's lambs), a song now and then.

- **New:** a presenter, Gully's sprite (a puppet on the presenter's arm, with a beak that moves when
  he talks) and Gully's voice, a children's set, and a children's tone for the writers (short
  sentences, kind, nothing frightening, even about the news).
- **Reuses:** features, the historian, the guest memory.
- **Size:** large (mostly art and voice).
- **Built** (`schedule.py`, `writers._ROCKPOOL`, `sprites.draw_gully`, the `studio_kids` set): Poppy Tregenza
  (`kids`), late 20s, six years teaching Year Two at Saltby primary, copper bunches and dungarees, voiced
  by af_bella; and Gully (`gully`), a herring-gull puppet on her arm, drawn in code with a crown, a grey
  back, an orange-ringed eye and a lower beak that drops as he talks, and voiced by `bm_fable@puppet`:
  Fable spoken slower and raised a third (`tts.PUPPET`), so he sounds like nobody else and no guest
  loses Fable. All three were chosen on a contact sheet and by ear. In the studio throughout, on a set
  painted in code until it has art: the open, the make, an animal visitor, letters and drawings (first
  names and ages only), story time with Hugh in the visitor's seat, a guest with a job children love,
  and Gully's poem (a spoken verse stands in for a song). No ad breaks (the advert pool is pubs and
  garages), no news, no threads, no grown-up guests booked back for their loose ends. The loop is long
  so story time comes round about three times. The bumper uses the news arrangement.

### The Inquiry (20:00, half an hour): investigations. BUILT 2026-10-30

Pat Holloway, a former consumer champion who never lets a vague answer go, takes one story in depth:
a story at its peak, or one that has gone quiet with questions still open. Miles's film, the
documents (the archive and the thread's beats), a studio interview that pushes back, and what still
isn't answered. The one serious show in an evening of light ones.

- **Reuses:** the special-report writer (an outline, then sections) and the record of a story so far,
  with a hard studio interview added. The editor picks the subject from the threads.
- **New:** a "not answered" close, and the interview's pushing tone.
- **Size:** small.
- **Built** (`inquiry.py`, `schedule.py`, `writers._INQUIRY`): from 18:30 the back office picks the
  story (`[inquiry]`, route `inquiry`), its angle, two to four questions and the guest; if nothing is
  chosen by 20:00 the most-covered story at its peak stands in. Every item gets the brief, the record
  and what the earlier items established. Running order: Pat's open to camera, Miles's film (someone
  it affected, not the guest), the guest part one (one or two questions), a break, the paper trail, a
  vox pop, the guest part two, the other side, and Pat's close on what still isn't answered. The
  bumper uses the news arrangement until it has its own (by ear).

### The Panel (20:30, half an hour): the debate. BUILT 2026-10-30

Dana Ferris chairs three panellists, from the town's officials, worthies and residents, on four
questions from the week's news (three until 2026-10-31, when the half hour ran out at eleven minutes),
with a question from the public. The panellists keep
their positions from show to show, as the public figures do now.

- **New:** a `panel` item: a chair and three guests in one discussion, and a set with four chairs.
  The interview set seats two or three today.
- **Reuses:** the public figures' positions, the guest memory, the vox pop for questions from the
  public.
- **Size:** medium.

### The Chamber (council nights, 20:00 to 21:00): the council, live

The town's stories already head for "Monday's council". On a council night the meeting itself is on
air: Dana in the press seats, Helen Strand in the chair, Miles in the public gallery. Items come from
the threads that are due at council, members of the public speak, councillors argue, and the votes
settle the stories. The story desk takes each result as the thread's next development, so threads
reach an end instead of waiting at the council door.

- **New:** a council calendar (meeting nights, and threads tied to the next meeting), a `vote` result
  the desk applies, and a show that takes over the evening slot on those nights (as the documentary
  and breaking news already take over the news).
- **Reuses:** the council chamber backdrop, the officials and their positions, the desk.
- **Size:** large, and the most distinctive.

## New pieces, shared

| Piece | Used by |
|---|---|
| A `call` item (a voice on the phone) | *Have Your Say*; later *The Last Ferry* |
| A `panel` item and a four-chair set | *The Panel*; *The Chamber*'s debates |
| `quay.py`, the day's landings and prices | *Quayside*, the bulletins, *Coastwide* |
| A `review` item the world remembers | *Out and About*; *Coastwide* |
| A show that takes over a slot on some days | *The Chamber*; later weekend sport |
| New presenters (a look, a voice by ear) | *Quayside*, *Out and About*, *Rock Pool* (and Gully) |

## Build order

1. **The Inquiry**: built 2026-10-30.
2. **Quayside**: built 2026-10-30, with Howard Lanyon.
3. **The Panel**: built 2026-10-30.
4. **Have Your Say**: built 2026-10-30, with the call item.
5. **Out and About**: built 2026-10-30, with Meg Trethewey and the review item.
6. **The Chamber**: the calendar and the votes, once the senior editor and the new story allowance
   have been watched for a night or two (it changes how stories end).
7. **Rock Pool**: built 2026-10-30, with Poppy and Gully. The Chamber waits a night or two after it.

New presenters' voices wait until they can be chosen by ear; a show can be built and tested with a
provisional voice, as Tamsin's was.
