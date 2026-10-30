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

### Have Your Say (10:00, an hour): the news phone-in

Jonah Pike, a former local-radio DJ, moves from the *Morning Tide* sofa to the phone-in desk after
breakfast. Each hour has one question from the day's news ("Should the lorry ban stay once the slates
are fixed?"). Viewers ring in, and a studio guest, the official or person at the heart of the story,
answers. Between calls come the travel news and the bulletin headlines.

- **New:** a `call` item: a caller on the line (a voiced guest with a phone caption and a waveform
  instead of a face), Jonah replying, and sometimes the studio guest answering. Callers are residents,
  cast like vox-pop voices, and some ring back on later days with their memories.
- **Reuses:** the interview set, the guest memory, the tip-line (a viewer tip can become a caller).
- **Size:** medium.

### Quayside (13:00, half an hour): business

The harbour and the port trade, local firms, shop openings and closings, jobs, high-street prices.
It leads on the morning's fish auction: what landed, what it fetched, up or down on last week.

- **New:** `quay.py`, the day's landings and auction prices worked out in code from the season, the
  weather and the boats out, so every show quotes the same figures (as `sport.py` does for the
  scores). The bulletins and *Coastwide*'s consumer slot can use them too.
- **New:** a presenter, a business reporter who knows the quay.
- **Reuses:** the consumer slot, interviews (a trader, the harbourmaster), field reports from the
  fish quay and the market.
- **Size:** medium (most of it in `quay.py`).

### Out and About (15:00, 45 minutes): travel, culture and food

Days out along the Greymouth coast, the town's culture (a gallery opening, the amateur dramatics, a
music night, the library's talks) and food (a café or restaurant visited and reviewed, a recipe from a
local kitchen, what's in season on the market). Mostly out on location, which suits the country
backdrops.

- **New:** a presenter, out and about.
- **New:** a `review` item: a visit to a place to eat or a show, with a verdict out of five that the
  world remembers, so the place can be revisited or the owner can answer back.
- **Reuses:** features, vox pops, the country and town backdrops.
- **Size:** small to medium.

### Rock Pool (16:00, 45 minutes): children's TV

A presenter and Gully, a herring-gull puppet with opinions. A "make" in the studio, story time (Hugh
Tremayne reads a town legend), viewers' drawings and letters, an animal visitor (the lifeboat's cat, a
farm's lambs), a song now and then.

- **New:** a presenter, Gully's sprite (a puppet on the presenter's arm, with a beak that moves when
  he talks) and Gully's voice, a children's set, and a children's tone for the writers (short
  sentences, kind, nothing frightening, even about the news).
- **Reuses:** features, the historian, the guest memory.
- **Size:** large (mostly art and voice).

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

### The Panel (20:30, half an hour): the debate

Dana Ferris chairs three panellists, from the town's officials, worthies and residents, on two or
three questions from the week's news, with a question from the public on each. The panellists keep
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
2. **Quayside**: `quay.py` gives the whole channel a new source of facts.
3. **The Panel**: the panel item and set.
4. **Have Your Say**: the call item.
5. **Out and About**: a presenter and the review item.
6. **The Chamber**: the calendar and the votes, once the senior editor and the new story allowance
   have been watched for a night or two (it changes how stories end).
7. **Rock Pool**: the most art and voice; best done when there's time to listen.

New presenters' voices wait until they can be chosen by ear; a show can be built and tested with a
provisional voice, as Tamsin's was.
