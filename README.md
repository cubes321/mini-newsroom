# Mini Newsroom

**An always-on, pixel-art television station for a town that doesn't exist.**

> **Watching?** Welcome to Port Wexley's television: Channel 7, the local news station, and Channel 8, its
> entertainment sister in the evenings. Port Wexley is a fictional town: the people, the council, the ferry
> and the news are all made up. Every programme is written and voiced by AI, live, around the clock.
>
> - Watch live on YouTube: [Port Wexley, @portwexley](https://www.youtube.com/@portwexley)
> - Watch live on Twitch: [twitch.tv/portwexley](https://www.twitch.tv/portwexley)
> - The four-minute tour, the Channel 7 promo: TODO
> - Help keep the lights on (the station costs about $1-2 a day to run): [ko-fi.com/portwexley](https://ko-fi.com/portwexley)
>
> Credits and licences: [docs/CREDITS.md](docs/CREDITS.md). Everything below is for people who want to run
> it or read the code.

Port Wexley has a mayor, a stopped Town Hall clock, ghost tours at the old
cannery and a baker who renames his treacle tart after the news. None of it is
real. LLMs write the scripts, Pocket TTS and Kokoro voice the presenters on
the CPU, and a Pygame window plays it out like a small local station.

**Channel 7** runs around the clock: *Morning Tide* on the breakfast sofa, a
news phone-in, a business half hour with the fish quay's prices, days out,
children's television with a seagull puppet, local sport, the *Coastwide*
magazine, an investigation, a debate, a late-night talk show and, every other
Thursday, the town council live. The news runs in between, a fifteen-minute
documentary airs every night (on Sundays, the week in review), and the test
card, repeats and teletext fill the small hours.

**Channel 8** is the evening entertainment channel on the same town, 18:00 to
22:30: a gameshow on the harbour steps against the tide, a teen magazine, a
teatime magazine from a studio kitchen, a pub quiz with a darts round, a soap
set on a television street, a wildlife series that takes turns with a
travelogue round the coast, and a TV movie, written and voiced ahead from a
bank of films. The station puts out one channel at a time.

Stories develop over days. A story desk plans what happens next, a senior
editor reviews its whole board, Channel 8's creative editor reviews every
programme after it airs, and the two editors meet once a day. Public figures
recur with their own voices, guests remember what they said last time, and
everything that airs goes into the town's archive so tomorrow's bulletin can
say "as we reported on Tuesday". The facts a model would get wrong are worked
out in code instead: the tides and the foot ferry, the football, rugby and
darts results, the fish auction's prices, the quiz scores and the count of
every council vote.

| | |
|---|---|
| ![Studio bulletin](docs/screenshots/studio.png) | ![Close-up](docs/screenshots/closeup.png) |
| Dana Ferris reads the bulletin | …and the close-up on the next line |
| ![Morning Tide](docs/screenshots/breakfast.png) | ![Breakfast handover](docs/screenshots/breakfast_live.png) |
| Rosie Treloar and Jonah Pike on the *Morning Tide* sofa | Handing over to Miles at the loading dock |
| ![Coastwide](docs/screenshots/magazine.png) | ![The Last Ferry](docs/screenshots/late.png) |
| Pat Holloway and Clive Ashdown on *Coastwide* | Vincent Marr and his guest on *The Last Ferry* |
| ![Big-picture wall](docs/screenshots/wall.png) | ![Field report](docs/screenshots/field.png) |
| Handing over to a live report at the loading dock | Miles Okafor live from the old cannery at dusk |
| ![Night in the rain](docs/screenshots/night.png) | ![Weather](docs/screenshots/weather.png) |
| Town Hall at night, graded for the last weather report | Gordon Pell and the weather map |
| ![Special report title card](docs/screenshots/special_title_card.png) | ![Special report guest](docs/screenshots/special_guest.png) |
| A special report opens | The harbourmaster, interviewed at the lifeboat station |
| ![Have Your Say](docs/screenshots/phonein.png) | ![Quayside](docs/screenshots/quayside.png) |
| A caller on the line to *Have Your Say* | Howard Lanyon opens *Quayside* on the fish auction's figures |
| ![Quayside at the fish quay](docs/screenshots/quayside_field.png) | ![Out and About](docs/screenshots/outabout.png) |
| Miles live from the fish quay | Meg Trethewey reviews a chippy on *Out and About* |
| ![Rock Pool](docs/screenshots/rockpool.png) | ![Full Time](docs/screenshots/fulltime.png) |
| Story time on *Rock Pool* with Poppy, Gully and Hugh Tremayne | Fran Kellaway on *Full Time* |
| ![The Inquiry](docs/screenshots/inquiry.png) | ![The Panel](docs/screenshots/panel.png) |
| The mayor in the chair on *The Inquiry* | *The Panel* |
| ![The Chamber](docs/screenshots/chamber.png) | ![A councillor speaks](docs/screenshots/chamber_close.png) |
| Full council live on *The Chamber* | A councillor on his feet |

![Six of the 26 locations](docs/screenshots/locations.png)
*Six of the 26 locations, at the time of day and in the weather the broadcast is having.*

## How it works

The one rule the whole design hangs on: **the broadcast never waits on the AI.**

```
 producer ──plans slots ahead──▶ priority queue ──▶ worker thread ──▶ buffer ──▶ player (wall clock)
                                      ▲                 │                            │
                                      │         LLM script + voices                  ▼
                story desk / editors / bookings / rundowns          continuity and adverts, then
                specials, documentary, adverts (idle time)          filler, when dry
```

- **Producer** keeps about ten minutes of unplayed content planned, working out
  when each slot will start from what is really queued. The schedule
  (`schedule.py`) decides which show each slot belongs to. The news loops a
  short pattern; the other shows run a written-out order with a brief per
  item, and each piece is told where it sits in its show (so only the opening
  says good evening and only the close says goodnight). *Coastwide* and *The
  Last Ferry* also get a running order planned by the model each evening: a
  theme, and a real subject for every item (`rundown.py`).
- **Bookings**: the evening and phone-in shows are booked ahead by the back
  office in idle time: the phone-in's question, guest and callers from 08:30;
  *The Inquiry*'s story, questions and guest, *The Panel*'s questions and
  panellists, and on council nights *The Chamber*'s four motions, all from
  18:30; on Channel 8, the evening's recipe, guests and quiz. A booked vote or
  quiz answer is counted in code, so the script reads the result it was given
  and the story moves on with it. A show with nothing booked in time airs a
  stand-in.
- **Worker** scripts each slot with the LLM (strict JSON, validated with
  pydantic, one retry, canned template as a last resort), voices every line,
  and stores a mouth envelope for lip-sync.
- **Player** consumes finished segments on the clock, never cutting audio
  mid-sentence. When nothing is ready it airs continuity (an ident, the
  "Later on Channel 7" card, the tides and ferry, community notices, trails for
  a finished special) in turn with local adverts, then filler. Breaking news
  cuts in at the next sentence and the programme resumes afterwards.
- **Adverts** for the town's shops and services (`adverts.py`, kept in
  `data/ads/`) are voiced in advance, so they are there when the model is
  slow; most programmes also have planned breaks of two adverts.
- **Tip-line**: anyone can add a line to `data/tipline.txt`. Plain tips go to
  the next bulletins; a line starting `BREAKING:` interrupts whatever is on,
  with a sting and Dana at the news desk.
- **The editors** run only when the worker is idle and the live buffer is
  healthy. The story desk gives each thread a phase and a planned next
  development and starts a few new stories a day. Every two hours the senior
  editor reads the whole board and leaves the desk a memo, and occasionally
  commissions a special. On Channel 8 nights the creative editor reads each
  programme after it airs and leaves notes for its planner, and may send a
  plan back once before air. From 16:00 the two editors hold a short meeting
  (`meeting.py`) to keep the channels out of each other's way and pass
  stories between them.
- **Sound**: Channel 7 has a sonic logo written down as notes (`jingle.py`),
  arranged for each show's bumper and ident, with music beds made from it
  (`station_audio.py`). Presenters and local guests are voiced by Pocket TTS
  cloning reference clips; Kokoro voices everyone else, and phone-in callers
  come through a telephone band.
- **Scenes** are drawn on a 320×180 canvas and scaled up with nearest
  neighbour, which is where the pixel look comes from. Writers choose from 26
  locations (Port Wexley and its countryside, the council chamber among them)
  and the studios have their own sets, from the breakfast sofa to the quiz
  pub and the soap's bar. Each backdrop is hand-checked pixel art
  (`assets/backdrops/`, made with ComfyUI), graded in code for the time of day
  and the last weather report, with rain, snow, fog and water animated on top;
  about a dozen locations come in layers that drift past each other in
  parallax (`parallax.py`). The people are drawn in code from a `Look`: the presenters
  to agreed descriptions, and every guest with a look of their own from their
  name, voice and role.
- **On a public stream**: every script and every voiced line passes a last word
  check (`safety.py`), F12 or a one-word file (`data/control.txt`) takes the
  station to the test card and back (`control.py`), and with `--obs` the
  live stream restarts at set times, at the next break in the programmes.

Model routing is config-driven (`[llm.routes]` in `config.toml`). Any
OpenAI-compatible endpoint works (LM Studio and llama.cpp locally, Moonshot's
Kimi and DeepSeek in the cloud), plus the Anthropic SDK. The shipped config
uses Claude Haiku 5.5 for the live scripts and DeepSeek Flash (thinking) for
most of the back office (the story desk, specials, the documentary and the
bookings), Claude Sonnet 5.5 as the senior editor and Flash's fallback, and
Claude Opus 5.5 only for once-a-night jobs (the creative editor and its seat
at the editors' meeting). Running costs are about $1-2 a day.

## Status

Working, and left on most nights. A night runs from the evening through to
the next morning with almost no filler and is recorded with OBS (`--obs`
starts a new file for each programme) or streamed (`docs/STREAMING.md`). Each
night's log is reviewed the next day and the fixes go in before the next run.
The public launch on YouTube and Twitch is planned for Christmas Eve 2026
(`docs/LAUNCH.md`).

Built and on air: both channels' schedules below; studio interviews, filmed
features, vox pops, phone-in calls, debates, a quiz, a gameshow, a teen
magazine, a soap, wildlife, a travelogue and a TV movie (first aired 24
November); specials and the nightly documentary, with archive clips; breaking
news from a viewer tip-line; the story bible, the desk, both editors and their
meeting; the annals and the Sunday review; provider switching, caching,
failure recovery and a stand-in for every show; backdrop art for every
location, with night pictures and parallax; code-drawn people; the station's
music; continuity and local adverts. Christmas Eve, Christmas Day and Boxing
Day have programmes of their own (`christmas.py`), not yet aired.

In progress: pictures for the stories, made by ComfyUI in shadow mode (made,
shown nowhere, while they are judged); *The Late News* on Channel 8 after a
short film (built and rehearsed, not yet on a real night); cartoons for the
content bank, on the back burner (`docs/CARTOON_NOTES.md`); and Channel 8's
later hours, comedy and a late drama, planned in `docs/ENGINE.md`.

## Channel 7's day

Unless breaking news cuts in, the station runs this schedule:

| from | show | what's on |
|---|---|---|
| 00:00 | overnight | the test card, repeats of the day's segments (not breakfast's) and SEVENTEXT, the station's teletext pages turning under a music bed; no live model calls, but the editors keep working, and a special made overnight airs after the test card |
| 06:00 | *Morning Tide* | breakfast on the sofa with Rosie Treloar and Jonah Pike: the headlines, sofa chats (the papers, a viewer's question, on this day in town history…), Gordon's weather, Miles's reports, and a goodbye before the news |
| 09:00 | the news | Dana Ferris, Gordon and Miles: weather, bulletins, field reports, a studio interview every third loop, Fran Kellaway's sport, specials, and "Later on Channel 7" once an hour |
| 10:00 | *Have Your Say* | Jonah Pike's news phone-in: one question from the day's news, viewers ringing in, and the official at the heart of the story in the studio |
| 11:00 | the news | |
| 13:00 | *Quayside* | Howard Lanyon on business, with the morning fish auction's prices and the jobs board |
| 13:30 | the news | |
| 15:00 | *Out and About* | Meg Trethewey on days out, culture and food: her walk for the weekend, reviews and features |
| 15:45 | the news | |
| 16:00 | *Rock Pool* | children's television with Poppy Tregenza and Gully the herring gull: makes, animal visitors, letters and story time |
| 16:45 | the news | |
| 18:45 | *Full Time* | Fran Kellaway and Tamsin Jago on fifteen minutes of local sport: the Tides, the rugby and the darts league |
| 19:00 | *Coastwide* | the early-evening magazine with Pat Holloway and Clive Ashdown: an hour of links and banter, filmed features from Miles, studio guests, vox pops, the consumer slot and Gordon's weather |
| 20:00 | *The Inquiry* | Pat Holloway takes one running story in depth: the questions still open, and the person who has to answer them |
| 20:30 | *The Panel* | Dana chairs three panellists on four questions from the week's news |
| 21:00 | the news | *Port Wexley Stories*, the nightly documentary, airs at the first bumper |
| 22:00 | *The Last Ferry* | Vincent Marr's late-night talk show with the lights down: a monologue, then guests who stay for two parts, late-night vox pops and a goodnight |
| 23:00 | the news | the late news |

Days that differ:

- **Council nights**, every other Thursday: *The Chamber* takes 20:00 to 21:00:
  full council live from the council chamber, the mayor in the chair, six
  councillors debating four motions booked from the day's stories, and the
  votes filed to the stories they decide. A carried motion becomes a promise
  with a due date, and the desk later reports whether it was kept
  (`promises.py`).
- **Sundays**: the documentary is *The Week in Port Wexley*, made from the
  annals (below); on 31 December it is *The Year*.
- **Bonfire Night**: *Coastwide*'s hour is a special on location, with the
  fireworks overhead.
- **Christmas Eve, Christmas Day and Boxing Day**: grids of their own.

Breakfast, the magazine and the talk show are **lighter** than the news: warm,
everyday local stories and what's on. The exception is one big running story,
which the opening item leads with briefly.

**Studio guests** are public figures, residents we have met, or new residents
the writer invents, who then join the recurring cast with a stable voice and
look. A guest who was just on is not rebooked; one with a loose end from last
time may be asked back about it. `uv run python -m newsroom.schedule` prints
the table, and `--clock HH:MM` starts the broadcast clock at any time of day
to try a show.

## Channel 8's evening

`--channel entertainment` puts out Channel 8 instead (`entertainment/`,
`docs/ENGINE.md`). It shares Port Wexley's world: its guests are the town's
residents, and the town hears about what airs.

| from | show | what's on |
|---|---|---|
| 18:00 | *High Water* | Des Kneebone's gameshow: two residents climb the twelve harbour steps against the tide, a question at a time, for prizes from the town's advertisers and a weekend away; every step, answer and wave played out in code, drawn on a tide gauge |
| 18:30 | *The Slipway* | the teen magazine with Tegan Trevenna, who throws herself into everything, and Elis Pengilly, who checks the rules: a young person from town with something to show (then Tegan has a go), a how-to, one to watch, a pupil from Greymouth Academy and grown-ups answering viewers' questions |
| 19:00 | *The Kettle's On* | the teatime magazine from a studio kitchen, with Maggie Truscott, who measures nothing, and Nigel Spargo, who weighs everything: a local cook's dish, an expert on the phones, a guest on the sofa and the community noticeboard |
| 20:00 | *Wexley Wits* | Clive Ashdown's pub quiz between two pubs: four rounds and a darts round, every answer and every dart scored in code |
| 20:20 | *Marina Row* | the soap: the last crabbing family on a row of old net lofts, now flats and a restaurant by a new marina; an episode a night, ending on a cliffhanger. Fiction, kept out of the town's news (`docs/MARINA_ROW.md`) |
| 20:40 | *Tideline* or *The Coast Road* | in turn: Rowan Polglase's coastal wildlife (one creature of the season, its count drawn in code), or Lorna Quayle's travelogue round the Greymouth coast, one leg a night (`docs/FACTUAL.md`) |
| 21:00 | the TV movie | an hour and a half: a film from a bank of seven approved (more written and waiting), each written scene by scene ahead of air, read by the creative editor and approved before it joins the bank, then voiced and played out whole with opening titles, three ad breaks and end credits. After a short film, *The Late News*: Dana Ferris at Channel 7's desk until 22:30, the town's own news read for Channel 8's viewers |
| 22:30 | closedown | the announcer's goodnight ("back tomorrow at six, with High Water"), then the test card |

The 20:40 and 21:00 slots rotate by what aired, not the weekday: whichever of
*Tideline* and *The Coast Road* aired less recently, and the film fit to air
that aired longest ago. The films are fiction, as *Marina Row* is: their parts
are made up, none of them joins the town, and nothing in them reaches the
news. Channel 7's town talk picks up what the town would be saying about
Channel 8 (the quiz result, the soap's cliffhanger) without ever treating it
as news.

| | |
|---|---|
| ![The Kettle's On](docs/screenshots/kettle.png) | ![Tonight's cook](docs/screenshots/kettle_cook.png) |
| Maggie and Nigel in *The Kettle's On* kitchen with tonight's cook | Nigel and Gwen Pascoe, a baker from the Harrow Street market |
| ![Wexley Wits](docs/screenshots/wits.png) | ![The darts round](docs/screenshots/wits_darts.png) |
| The Harbour Lights against the Cannery Tap on *Wexley Wits* | The darts round, every dart scored in code |
| ![Marina Row](docs/screenshots/marina_kitchen.png) | ![The Row at dusk](docs/screenshots/marina_quay.png) |
| *Marina Row*: Queenie's kitchen, behind the net loft | The Row at dusk |
| ![The Mermaid](docs/screenshots/marina_pub.png) | ![The Loft](docs/screenshots/marina_restaurant.png) |
| The Mermaid, the Row's pub | The Loft, the new restaurant in a converted net loft |
| ![The Coast Road](docs/screenshots/coastroad.png) | ![The Coast Road at dusk](docs/screenshots/coastroad_dusk.png) |
| Lorna Quayle meets the Saltby foot ferry's deckhand on *The Coast Road* | The end of the first leg, at the Saltby slip |

## Run it

Needs Python 3.12 (Kokoro doesn't install on 3.13), [uv](https://docs.astral.sh/uv/),
and either a local OpenAI-compatible server or an API key.

```bash
uv sync
uv run python -m newsroom                          # Channel 7
uv run python -m newsroom --channel entertainment  # Channel 8
```

Scripts come from whichever provider `[llm.routes]` in `config.toml` names.
Providers are declared under `[llm.providers.<name>]`. The shipped routes need
`ANTHROPIC_API_KEY` and `DEEPSEEK_API_KEY` in the environment; `moonshot`
(Kimi, `MOONSHOT_API_KEY`) and `lmstudio` (local, `http://localhost:1234`) are
declared too. `NEWSROOM_LLM=<name>` forces one provider for every task,
`--route a=b` moves one provider's or task's calls for a run, and
`NEWSROOM_LLM=off` runs entirely on canned template scripts with no model at
all, which is handy for working on the visuals.

**Every run writes the real town** unless told otherwise: it updates
`data/world.json` and adds to `data/cache/`, whose last two days feed the
overnight repeats. `--scratch` copies the world and the tip-line to a fresh
temp dir and runs on the copy with an empty cache; `--world PATH` and `--cache
DIR` point a run elsewhere (or `NEWSROOM_WORLD`, `NEWSROOM_CACHE` and
`NEWSROOM_TIPLINE`, which also cover the module CLIs). For a template smoke
test: `NEWSROOM_LLM=off uv run python -m newsroom --no-window --minutes 2 --scratch`.

Flags:

| flag | does |
|---|---|
| `--clock HH:MM` or `--clock "YYYY-MM-DD HH:MM"` | start the broadcast clock at another time, or on another day (a council night, Christmas) |
| `--channel entertainment` | put out Channel 8 |
| `--scratch`, `--world`, `--cache` | run on a copy of the town, or another one |
| `--minutes N` | exit after N minutes |
| `--no-window` | run the producer, workers and a simulated player headless |
| `--debug` | draw slot and buffer status on the picture |
| `--workers N` | N generation workers (model calls in parallel; TTS still one line at a time) |
| `--log-llm` | write every model prompt and reply, with token counts, to `data/llm_calls/<date>.jsonl` |
| `--route a=b[,...]` | move a provider's or a task's calls for this run |
| `--special-now`, `--documentary-now`, `--review week\|year`, `--breaking-now` | have the back office do one of these at its next idle moment |
| `--obs` | record each programme to its own file in OBS as it airs (its WebSocket server on) |
| `--audio-device NAME`, `--devices` | play into another sound output (part of its name), or list them |
| `--parallax`, `--no-parallax` | override `config.toml` on the drifting backdrops |
| `--pictures` | make ComfyUI pictures for the stories in shadow mode |
| `--snap DIR` | save a frame every 10 s |

Every run writes its log to `data/logs/station-<date>-<time>.log`, crashes on
any thread included. Token counts are on each call's log line, and running
totals per provider are logged every ten minutes and at exit (`LLM USAGE`).
`NEWSROOM_COUNCIL_NIGHT=1` (or `0`) makes any day a council night (or not), so
*The Chamber* can be tried with `--clock 18:20`.

Expected cold start: filler card → bumper → an advert or a short filler while Kokoro loads →
weather → bulletin → field report → bumper → … After the first loop the buffer
stays ahead and there is no more filler.

## The story browser

A read-only web page for looking through the town's stories, current and
past, without starting the station:

```bash
uv run python tools/story_browser.py      # then open http://127.0.0.1:8766
uv run python tools/story_browser.py --world data/backups/world-2026-11-15.json   # the town as it was that day
```

It shows every story thread (open, faded and closed, with a filter and a
search), each with its phase, its planned NEXT, its people, its beats day by
day and every piece of it the archive still holds. A piece opens as it went
out, line by line from the cache, with its audio while the cache keeps it.
There are also the days (the annals page and its keepsake clips, the stories
that moved, what was booked), the council's motions and promises, the
bookings and running orders, the residents, and the desk: the senior editor's
memo, the desk's rounds and the editors' meetings.

It never writes anything and serves only on 127.0.0.1, so it is safe to leave
open beside a station that is on air: it reads `world.json` only when the file
has changed, at most every two seconds, and lets go of it at once, and the
station retries a save that meets it.

## The story bible

`data/world.json` is the town's memory and cast list. It is not in git;
`data/backups/` keeps a copy as it stood each day (`[backups] keep` days) and
at the start of the last three runs.

- **Presenters**: on Channel 7, Dana Ferris (anchor, and *The Panel*), Gordon
  Pell (weather), Miles Okafor (field reporter); Rosie Treloar and Jonah Pike
  (breakfast; Jonah also has the phone-in); Pat Holloway and Clive Ashdown
  (*Coastwide*; Pat also has *The Inquiry*, Clive *Wexley Wits*); Vincent Marr
  (*The Last Ferry*); Fran Kellaway and Tamsin Jago (sport); Howard Lanyon
  (*Quayside*); Meg Trethewey (*Out and About*); Poppy Tregenza and Gully
  (*Rock Pool*); Hugh Tremayne (the history documentaries). On Channel 8,
  Des Kneebone (*High Water*), Tegan Trevenna and Elis Pengilly (*The
  Slipway*), Maggie Truscott and Nigel Spargo (*The Kettle's On*) and Rowan
  Polglase (*Tideline*); Clive hosts *Wexley Wits* and Dana *The Late News*,
  borrowed from Channel 7. Each show's prompt and JSON schema allow only its own cast.
- **People**: seeded public figures (the mayor, police and fire chiefs, the MP,
  the harbourmaster, a head teacher, the lifeboat coxswain, six town
  councillors with their wards and leanings) plus residents promoted from
  guests, callers and advertisers. Each has a stable voice, speaking speed and
  look so they can recur, and guests remember what they said last time.
- **Threads**: story lines with a phase (emerging → developing → peak →
  resolving → closed), the beats aired so far, the people involved and a
  planned NEXT development. Writers see the NEXT in their briefing and are told
  a follow-up must deliver it, so stories move instead of repeating. A long
  story whose NEXT names a later day waits in **the running-stories pool**, off
  the writers' board, until its day comes round.
- **Archive**: every segment aired, searchable, for callbacks and for the
  documentary's research.
- **Annals** (`annals.py`, `data/annals/`): each morning, a page of what the
  town did the day before, with up to three keepsake clips, kept for good. The
  Sunday review and the year's review are made from them.
- **Promises** (`promises.py`): what full council voted would happen, by when,
  and whether it did.
- **Town talk** (`talk.py`): what the town is saying that Channel 7 didn't
  report itself (the quiz, the soap), for the writers' small talk.

The **story desk** (`desk.py`) runs every `plan_every_s` when the worker is
idle and the live buffer is healthy. It assigns phases, writes next
developments, closes finished threads and seeds new ones (`[story]
seeds_per_day`, released a few at a time from the morning, none overnight). It
plans a batch of threads at a time, and only those for which something has
changed. Every two hours the **senior editor** (`senior.py`) reads the whole
board and leaves the desk a memo: threads to merge, people to trim, a story
that needs a new angle, a waiting story to move to another day.

```bash
uv run python -m newsroom.desk plan --dry      # see what the desk would do
uv run python -m newsroom.world editor         # the fuller briefing the desk sees
uv run python -m newsroom.world archive        # last 20 archive entries
uv run python -m newsroom.meeting minutes      # the editors' meeting as held
uv run python -m entertainment.creative notes  # the creative editor's marks and notes
```

## Specials, the documentary and the reviews

The editor reads the open threads every `check_every_s` and decides whether
one has earned a five-minute **special report**; usually the answer is no. A
commissioned special is a **resumable** low-priority job (outline, one section
per stage, voicing, finish) that re-queues itself after each stage, so live
slots are served in between and the longest uninterruptible unit is one model
call. Progress is checkpointed to `data/cache/*.partial.json` and resumed on
startup. A finished special airs at the next news bumper (overnight, the next
test card).

*Port Wexley Stories* (`documentary.py`) is fifteen minutes on one subject
every night at 21:00, made the same way with a research stage first: the
researcher reads every archive piece on the thread and writes dated notes, and
the outline and sections are written from those notes. It can place up to
three clips of earlier coverage as **archive footage**, in black and white and
captioned with who said it and when.

On Sundays the slot is *The Week in Port Wexley*, and on New Year's Eve *The
Year* (`review.py`): the same pipeline, researched from the annals instead of
a thread. A week needs three annals pages, a year fourteen; with fewer, the
night has an ordinary documentary.

```bash
uv run python -m newsroom.special decide                              # ask the editor now
uv run python -m newsroom.special make --thread t002                  # a special for a thread
uv run python -m newsroom.special make --documentary --thread t030    # a documentary now
uv run python -m newsroom.review week                                 # the week's notes, no model
```

## Tools

| tool | does |
|---|---|
| `tools/story_browser.py` | the story browser, above |
| `tools/one_off.py` | out-of-canon programmes (a real-world special, a visiting guest) from a hand-written script, with their own copy of the world: `voice` → `preview` → `air --obs` → `cards` → `short` |
| `tools/shorts.py` | YouTube Shorts re-rendered from the cache, not cut from a recording |
| `tools/scan_cache.py` | runs the safety word check over everything in the cache |
| `tools/obs_record.py` | records each programme in OBS from another window, following a running station's log |
| `tools/review_trial.py` | makes a week in review on a copy of the town, to judge it before it airs |

## Layout

`newsroom/` is the engine and Channel 7; `entertainment/` is Channel 8,
plugged in through registries the engine reads by show id, so `newsroom/`
never imports it.

| file | job |
|---|---|
| `config.toml` / `config.py` | providers, routes, voices, buffer horizon, paths |
| `models.py` | `Segment`, `Line`, `VisualCue`, and the per-type LLM schemas |
| `world.py` | the story bible: presenters, people, threads, archive |
| `llm.py` | one `complete_json()` door; OpenAI-compatible or Anthropic; strict JSON + one retry |
| `writers.py` | prompts per show and segment type, where each piece sits in its show, studio guests, template fallbacks |
| `rundown.py` | the evening running orders the model plans: a theme and a subject per item |
| `special.py` / `documentary.py` / `review.py` | specials, the nightly documentary, and the week's and year's reviews |
| `desk.py` / `senior.py` / `meeting.py` | the story desk, the senior editor, and the editors' meeting |
| `annals.py` / `promises.py` / `talk.py` | the town's long memory: a page a day, the council's promises, town talk |
| `phonein.py` / `inquiry.py` / `panel.py` / `chamber.py` | the booked shows: each one's booking, stand-in and briefing |
| `outabout.py` | *Out and About*'s reviews: stars out of five, remembered |
| `council.py` / `calendar.py` | the council's calendar and its six councillors; the town's annual events |
| `tides.py` / `sport.py` / `rugby.py` / `darts.py` / `quay.py` | facts worked out in code: tides and ferry, results and tables, the fish auction |
| `christmas.py` | Christmas Eve, Christmas Day and Boxing Day |
| `tipline.py` / `breaking.py` | the viewer tip-line, and breaking news from it |
| `adverts.py` / `continuity.py` | the local advert pool; idents, "Later on Channel 7", the tides card, notices and trails |
| `teletext.py` | SEVENTEXT, the overnight teletext pages |
| `tts.py` | Pocket TTS cloning `assets/voices/`, else Kokoro, on CPU → 24 kHz WAV + mouth envelope |
| `jingle.py` / `station_audio.py` / `assets.py` | the station's sonic logo, its arrangements and the music stems; bakes the bumpers and beds |
| `buffer.py` / `producer.py` / `workers.py` / `player.py` | the pipeline: queue and buffer, slot planning, generation and idle work, playout |
| `schedule.py` / `channel.py` | the shows, the daily schedule and the broadcast clock; which channel is on air |
| `locations.py` / `backdrops.py` / `skies.py` / `parallax.py` | the places, their art, time-of-day and weather grading, and the drifting layers |
| `scenes.py` / `sprites.py` / `logo.py` | draws the `View` on a 320×180 canvas scaled up; the people; the station bug |
| `pictures.py` | ComfyUI pictures for the stories, in shadow mode |
| `bank.py` / `film.py` | the content bank of finished films, and playing one out |
| `safety.py` / `control.py` | the last word check before a line is voiced; the kill switch |
| `obs.py` / `prune.py` | recording each programme in OBS; clearing old entries from the cache |
| `entertainment/highwater.py` / `highwater_show.py` / `tidegauge.py` | *High Water*: the game played in code, the programme, and its tide gauge |
| `entertainment/slipway.py` | *The Slipway* |
| `entertainment/kettle.py` | *The Kettle's On* |
| `entertainment/wits.py` / `quiz.py` / `oche.py` | *Wexley Wits*: the show, the quiz and its scores, every dart of the darts round |
| `entertainment/soap.py` / `marina_row.py` | the soap engine, and *Marina Row* |
| `entertainment/wildlife.py` / `seasons.py` / `creatures.py` | *Tideline*: the creatures of the season, chosen and counted in code |
| `entertainment/travelogue.py` | *The Coast Road* |
| `entertainment/movies.py` / `movie_night.py` / `movie_cards.py` | the TV movie: the bank of films written ahead, the 21:00 slot, the titles and credits |
| `entertainment/late_news.py` | *The Late News* after a short film |
| `entertainment/creative.py` | the creative editor |
| `entertainment/cartoons.py` | cartoons for the content bank (in progress) |

## Dev commands

```bash
uv run pytest                                          # all tests, on a temp town (no model, no TTS)
uv run python -m newsroom.schedule                     # the day's schedule
uv run python -m newsroom --clock 06:00 --debug        # watch breakfast at any hour
uv run python -m newsroom --clock "2026-12-24 18:00" --scratch   # Christmas Eve, on a copy
uv run python -m newsroom --channel entertainment --clock 17:50 --scratch   # Channel 8's evening, on a copy
uv run python -m entertainment.movies list             # the film bank (pitch, new, write, read, approve: see movies.py)
uv run python -m newsroom.llm weather --dry-run        # show prompt + schema, no call
uv run python -m newsroom.llm interview --show late --part cont --dry-run   # a guest's second part
uv run python -m newsroom.llm weather                  # live call to the routed provider
uv run python -m newsroom.world                        # print the writers' briefing
uv run python -m newsroom.workers field_report         # one segment end to end
uv run python -m newsroom --no-window --minutes 3 --scratch   # headless soak on a copy of the town
uv run python -m newsroom.tts "Good evening"           # synth one line and play it
uv run python -m newsroom.backdrops --sheet sheet.png  # every backdrop at day, dusk and night
uv run python -m newsroom.sprites --sheet people.png   # every presenter and a crowd of guests
uv run python -m newsroom.tides 2026-11-02             # that day's tides and foot ferry
uv run python -m newsroom.adverts                      # the advert pool (--make writes and voices one)
uv run python -m newsroom.continuity                   # the continuity pool (--bake bakes what's due)
uv run python -m newsroom.sport                        # the football: results, fixtures and the table
uv run python -m newsroom.quay                         # the fish auction's latest prices
uv run python -m newsroom.prune                        # what a cache clear-out would remove
uv run python -m newsroom --devices                    # the sound outputs, for --audio-device
uv run python -m newsroom.tipline "BREAKING: Smoke over the old cannery"   # breaking news
uv run python -m newsroom.tipline "The lifeboat open day is on Saturday"   # a tip for the bulletins
```

Generated audio and segment JSON live in `data/cache/`, keyed by the slot,
the day, the show, the provider and the running order's part and brief.
Entries older than `[cache] keep_days` that nothing still needs are cleared.

## Docs

| doc | what's in it |
|---|---|
| [docs/SHOWS.md](docs/SHOWS.md) | both channels' schedules, and every Channel 7 show in detail |
| [docs/ENGINE.md](docs/ENGINE.md) | the engine, the second channel, the creative editor and the editors' meeting |
| [docs/MARINA_ROW.md](docs/MARINA_ROW.md) | the soap's series bible |
| [docs/FACTUAL.md](docs/FACTUAL.md) | Channel 8's factual slot: *Tideline* and *The Coast Road* |
| [docs/PARALLAX.md](docs/PARALLAX.md) | parallax on location |
| [docs/STREAMING.md](docs/STREAMING.md) | OBS, VB-Cable, YouTube and Twitch |
| [docs/LAUNCH.md](docs/LAUNCH.md) | the Christmas Eve launch checklist |
| [docs/CARTOON_NOTES.md](docs/CARTOON_NOTES.md) | the cartoons, in progress |
| [docs/HANDOVER.md](docs/HANDOVER.md) | notes for whoever picks the work up next |
| [docs/CREDITS.md](docs/CREDITS.md) | every model, font and licence |

## Notes

- Python is pinned to 3.12 because `kokoro`/`misaki` do not install on 3.13.
- Kokoro and Pocket TTS run on CPU on purpose, so the GPU is free for a local
  model or ComfyUI.
- `<think>` blocks are stripped defensively regardless of provider.
- Generated content is cached per provider, so switching providers never
  replays another provider's scripts.
- `--workers N` is safe: the world state has its own lock (`World.lock`).

## Licence

Two licences:

- **The code is MIT** ([LICENSE](LICENSE)). Take the engine and build your own town with it.
- **Port Wexley is not.** The town, its people, programmes, the *Beacon* tune, the backdrops, the voices and
  the scripts are under the [Port Wexley Content Licence](LICENSE-CONTENT.md): you can run and enjoy it at
  home, but publishing, streaming, spin-offs and commercial use need permission. That includes the parts
  written into the source files.

Port Wexley and everyone in it are fictional.

Voices: [Pocket TTS](https://huggingface.co/kyutai/pocket-tts) by Kyutai (weights CC-BY-4.0, gated:
accept the terms and `hf auth login` once), cloning reference clips in `assets/voices/`. Most presenters'
clips are renders of their own [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) voices (Apache 2.0),
and so are the visitors'. The local guests, the mayor and councillors, and several presenters were designed
from a description with [DramaBox](https://huggingface.co/ResembleAI/Dramabox) by Resemble AI (LTX-2
Community License). Kokoro voices everyone else.

Every model, font and licence, and what each means for a monetised stream, is in
[docs/CREDITS.md](docs/CREDITS.md).
