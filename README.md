# Mini Newsroom

**An always-on, pixel-art TV news channel for a town that doesn't exist.**

> **Watching?** Welcome to Channel 7, Port Wexley's local station. Port Wexley is a fictional town: the
> people, the council, the ferry and the news are all made up. Every programme is written and voiced by
> AI, live, around the clock.
>
> - Watch live on YouTube: TODO (Cubes Channel, @cubes123)
> - Watch live on Twitch: TODO
> - The four-minute tour, the Channel 7 promo: TODO
> - Help keep the lights on (the station costs about $1-2 a day to run): Ko-fi TODO
>
> Credits and licences: [docs/CREDITS.md](docs/CREDITS.md). Everything below is for people who want to run
> it or read the code.

Port Wexley has a mayor, a stopped Town Hall clock, ghost tours at the old
cannery and a baker who renames his treacle tart after the news. None of it is
real. An LLM writes the scripts, Pocket TTS and Kokoro voice the presenters on
the CPU, and a Pygame window plays it out like a small local station, Channel 7,
on a daily schedule of eleven programmes: *Morning Tide* on the breakfast
sofa, a news phone-in, a business half hour with the fish quay's prices, days
out, children's television with a seagull puppet, local sport, the
*Coastwide* magazine, an investigation, a debate, a late-night talk show and,
every other Thursday, the town council live. The news runs in between, a
fifteen-minute documentary airs every night, and the test card and repeats
fill the small hours.

Stories develop over days. A story desk plans what happens next, a senior
editor reviews its whole board, public figures recur with their own voices,
and everything that airs goes into the town's archive so tomorrow's bulletin
can say "as we reported on Tuesday". The facts a model would get wrong are
worked out in code instead: the tides and the foot ferry, the football, rugby
and darts results, the fish auction's prices and the count of every council
vote.

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
                     story desk / senior editor / bookings          continuity and adverts, then
                     specials, documentary, adverts (idle time)     filler, when dry
```

- **Producer** keeps about ten minutes of unplayed content planned, working out
  when each slot will start from what is really queued. The schedule
  (`schedule.py`) decides which show each slot belongs to. The news loops a
  short pattern; the other shows run a written-out order with a brief per
  item, handed out in turn so each lap of the hour has new angles, and sign
  off just before the next show starts.
- **Bookings**: the evening and phone-in shows are booked ahead by the back
  office in idle time: the phone-in's question, guest and callers from 08:30;
  *The Inquiry*'s story, questions and guest, *The Panel*'s questions and
  panellists, and on council nights *The Chamber*'s four motions, all from
  18:30. A booked vote is counted in code, so the debate reads the result it
  was given and the story moves on with it. A show with nothing booked in time
  airs a stand-in.
- **Worker** scripts each slot with the LLM (strict JSON, validated with
  pydantic, one retry, canned template as a last resort), voices every line,
  and stores a mouth envelope for lip-sync. Overlong captions are cut at a
  word rather than failing the script.
- **Player** consumes finished segments on the clock, never cutting audio
  mid-sentence. When nothing is ready it airs continuity (an ident, the
  "Later on Channel 7" card, the tides and ferry, community notices, trails for
  a finished special) in turn with local adverts, then filler and, after a
  while, a replay of the last weather. The programme card also airs once an
  hour in the news anyway. Breaking news cuts in at the next sentence and the
  programme resumes afterwards.
- **Adverts** for the town's shops and services (`adverts.py`, kept in
  `data/ads/`) are voiced in advance, so they are there when the model is
  slow. Eight hand-written ones are voiced on the first idle moments; the
  model writes another every half hour in idle time, up to forty. An owner
  who speaks in their advert joins the town's cast. Most of the programmes
  also have planned breaks of two adverts in their running orders (on *The
  Last Ferry*, between a guest's two parts).
- **Tip-line**: anyone can add a line to `data/tipline.txt`. Plain tips go to
  the next bulletins; a line starting `BREAKING:` interrupts whatever is on,
  with a sting and Dana at the news desk.
- **Story desk** and **editor** run only when the worker is idle and the live
  buffer is healthy. The desk gives each thread a phase and a planned next
  development, and starts up to ten new stories a day, a few at a time from
  06:00 (none overnight). Every two hours the senior editor reads the whole
  board and leaves the desk a memo. The editor occasionally commissions a
  special, which is written in resumable stages that interleave with live work.
- **Sound**: Channel 7 has a sonic logo written down as notes (`jingle.py`),
  arranged for each show's bumper and ident, with music beds made from it
  (`station_audio.py`). Presenters and local guests are voiced by Pocket TTS
  cloning reference clips; Kokoro voices everyone else, and phone-in callers
  come through a telephone band.
- **Scenes** are drawn on a 320×180 canvas and scaled up with nearest
  neighbour, which is where the pixel look comes from. Writers choose from 26
  locations (Port Wexley and its countryside, the council chamber among them)
  and the studio has eight sets, from the breakfast sofa to the panel set and
  the *Rock Pool* set.
  Each is hand-checked pixel art (`assets/backdrops/`, made with ComfyUI),
  graded in code for the time of day (a sunset tint at dusk; hand-made night
  pictures for the harbour, high street and Town Hall) and for the last
  weather report, with rain, snow, fog and water animated on top. Bulletins cut between a wide shot
  and a close-up, and the anchor hands over to reports from a big-picture
  wall. The people are drawn in code: the presenters to agreed descriptions,
  and every guest with a look of their own from their name, voice and role.

Model routing is config-driven. Any OpenAI-compatible endpoint works (LM
Studio and llama.cpp locally, Moonshot's Kimi in the cloud), plus the Anthropic
SDK. The shipped config uses Claude Haiku 5.5 for live segments and DeepSeek
Flash (thinking) for the back office (the editor, the story desk, specials,
the documentary and the evening shows' bookings), with Claude Sonnet 5.5 as
the senior editor over the desk and as Flash's fallback; Kimi k2.6 and k3 did
those jobs before and are still declared. The night run of 31 October, from
the evening shows to the next morning, cost under a dollar in model calls.

## Status

Working, and left on overnight. It runs from the evening through to the next
morning with almost no filler, and nights are recorded with OBS
(`--obs` starts a new file for each programme) or streamed to
YouTube (`docs/STREAMING.md`). Each night's log is reviewed the next day and
the fixes go in before the next run. Things that exist: the full schedule
below; studio interviews, filmed features, vox pops, phone-in calls, debates
and specials; breaking news from a viewer tip-line; the story bible, the desk
and the senior editor; provider switching, caching, failure recovery and a
stand-in for every show; backdrop art for every location, with night
pictures; code-drawn presenters, and a look of their own for every guest from
their name, voice and role; the station's music; continuity and local adverts
that cover the gaps and fill ad breaks; a nightly fifteen-minute documentary
researched from the town's archive, with clips of earlier coverage as archive
footage. `docs/SHOWS.md` has every programme in detail and `docs/ENGINE.md`
the plan to reuse the engine for a second channel.

## A normal day

Unless breaking news cuts in, the station runs this schedule:

| from | show | what's on |
|---|---|---|
| 00:00 | overnight | the test card, repeats of the day's segments (not breakfast's) and SEVENTEXT, the station's teletext pages turning under a music bed (news, weather, tides, sport, the fish quay, the day's programmes, notices); no live model calls, but the story desk and editor keep working, and a special made overnight airs after the test card |
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
| 19:00 | *Coastwide* | the early-evening magazine in the spirit of *Nationwide*, with Pat Holloway and Clive Ashdown: an hour of links and banter, filmed features from Miles, studio guests, vox pops, the consumer slot and Gordon's weather, each item with its own angle |
| 20:00 | *The Inquiry* | Pat Holloway takes one running story in depth: the questions still open, and the person who has to answer them |
| 20:30 | *The Panel* | Dana chairs three panellists on four questions from the week's news |
| 21:00 | the news | *Port Wexley Stories*, the nightly documentary, airs at the first bumper |
| 22:00 | *The Last Ferry* | Vincent Marr's late-night talk show with the lights down: a monologue, then guests who stay for two parts, late-night vox pops and a goodnight |
| 23:00 | the news | the late news |

Every other Thursday, from 5 November 2026, **The Chamber** takes 20:00 to
21:00 instead: full council live from the council chamber, the mayor in the
chair, six councillors debating four motions booked from the day's stories,
the public gallery, and the votes filed to the stories they decide.

Breakfast, the magazine and the talk show are **lighter** than the news: warm,
everyday local stories and what's on. The exception is one big running story
(a story that broke as breaking news today, or else the most-covered thread at
its peak): the headlines lead with it briefly, and in the magazine and the
talk show only the opening item does, so it isn't in every item of the hour.

**Breaking news** can cut into any of them. A line starting `BREAKING:` in the
tip-line interrupts at the next sentence: a sting, Dana at the news desk
(Miles may phone in), then back to the programme where it left off. For two
hours afterwards the bulletins lead with it.

**Studio guests** are public figures, residents we have met, or new residents
the writer invents, who then join the recurring cast with a stable voice and
look. A guest who was just on is not rebooked. A presenter can be a guest too
(Gordon Pell, who runs the cannery ghost tours on the side), and appears as
himself. `uv run python -m newsroom.schedule` prints the table, and `--clock
HH:MM` starts the broadcast clock at any time of day to try a show.

## Run it

Needs Python 3.12 (Kokoro doesn't install on 3.13), [uv](https://docs.astral.sh/uv/),
and either a local OpenAI-compatible server or an API key.

```bash
uv sync
uv run python -m newsroom
```

Scripts come from whichever provider `[llm.routes]` in `config.toml` names.
Providers are declared under `[llm.providers.<name>]`. Shipped entries:
`claude_haiku`, `claude_sonnet` and `deepseek_flash_think` (the routes as
shipped; need `ANTHROPIC_API_KEY` and `DEEPSEEK_API_KEY` in the environment), `moonshot` (Kimi, needs
`MOONSHOT_API_KEY`), `moonshot_k3`, `lmstudio` (local, `http://localhost:1234`)
and `anthropic`. Set
`NEWSROOM_LLM=<name>` to force one provider for every task, or
`NEWSROOM_LLM=off` to run entirely on canned template scripts with no model
at all, which is handy for working on the visuals.

Flags: `--debug` draws slot/buffer status, `--minutes N` auto-exits,
`--no-window` runs the producer, workers and a simulated player headless,
`--workers N` runs N generation workers (model calls in parallel; TTS still
one line at a time), `--snap DIR` saves a frame every 10 s, `--special-now` has the editor consider
a special immediately, `--documentary-now` commissions today's documentary at
once (it still airs in its slot), `--clock HH:MM` pretends the local time is HH:MM,
`--scratch` runs on a copy of the town (below), `--log-llm` writes every model prompt and reply, with token counts, to
`data/llm_calls/<date>.jsonl` (or set `log_calls = true` under `[llm]`).
`--obs` records each programme to its own file in OBS as it airs, `--audio-device NAME` plays into
another sound output (or set `audio_device` under `[broadcast]`), and `--devices` lists them.
Token counts are always on each call's log line, and running totals per
provider are logged every ten minutes and at exit (`LLM USAGE`). Every run also writes its log to
`data/logs/station-<date>-<time>.log` (a `--scratch` run to its own `logs/`, `NEWSROOM_LOGS` for
another folder), crashes on any thread included, so a night needs no redirect; Pocket TTS's
per-line chatter is left out of it and the window.

Test runs write to the real town unless told otherwise: every run updates
`data/world.json` and adds to `data/cache/`, whose last two days feed the
overnight repeats. `--world PATH` and `--cache DIR` point a run elsewhere, and
`--scratch` copies the world and the tip-line to a fresh temp dir and runs on
the copy with an empty cache (the path is logged; delete it when done;
`--log-llm` still writes to `data/llm_calls/`). The
same overrides work as environment variables, `NEWSROOM_WORLD`,
`NEWSROOM_CACHE` and `NEWSROOM_TIPLINE`, and those also cover the module CLIs
(`newsroom.world`, `newsroom.workers`, `newsroom.desk`, ...). Every run logs
the world and cache it is using. `NEWSROOM_COUNCIL_NIGHT=1` (or `0`) makes
any day a council night (or not), so *The Chamber* can be tried with `--clock
18:20`. For a template smoke test:
`NEWSROOM_LLM=off uv run python -m newsroom --no-window --minutes 2 --scratch`.

Expected cold start: filler card → bumper → an advert or a short filler while Kokoro loads →
weather → bulletin → field report → bumper → … After the first loop the buffer
stays ahead and there is no more filler.

## The story bible

`data/world.json` is the town's memory and cast list. It is not in git and
nothing backs it up, so test runs should use `--scratch` (above):

- **Presenters**: Dana Ferris (anchor, and *The Panel*), Gordon Pell
  (weather), Miles Okafor (field reporter); Rosie Treloar and Jonah Pike
  (breakfast; Jonah also has the phone-in); Pat Holloway and Clive Ashdown
  (*Coastwide*; Pat also has *The Inquiry*); Vincent Marr (*The Last Ferry*);
  Fran Kellaway and Tamsin Jago (sport); Howard Lanyon (*Quayside*); Meg
  Trethewey (*Out and About*); Poppy Tregenza and Gully (*Rock Pool*); Hugh
  Tremayne (the history documentaries), with fixed voices. Each show's prompt
  and JSON schema allow only its own cast.
- **People**: seeded public figures and worthies (the mayor, police and fire
  chiefs, the MP, the harbourmaster, a head teacher, the lifeboat coxswain,
  the historical society chair, six town councillors with their wards and
  leanings) plus residents promoted from guests, callers and advertisers.
  Each has a stable voice, speaking speed and look so they can recur, and
  guests remember what they said last time. Appearances are counted whenever
  a script names them.
- **Threads**: story lines with a phase (emerging → developing → peak →
  resolving → closed), the beats aired so far, the people involved and a
  planned NEXT development. Writers see the NEXT in their briefing and are told
  a follow-up must deliver it, so stories move instead of repeating. A thread
  names at most four people.
  The board keeps 40 threads: a new one drops the quietest closed thread,
  never an open one (with all 40 open it grows and logs a warning). Template
  scripts (`NEWSROOM_LLM=off` or a failed model call) never open threads,
  except breaking news, whose tip is real.
  **The running-stories pool**: a long story (open two days, or covered ten
  times) whose NEXT names a later day waits for it, off the writers' board and
  the desk's rounds, never faded for being quiet and not counted as live, so
  the desk opens new stories in its place. The writers see a short list of
  what is waiting, so a waiting story isn't reported early or reborn under a
  new id; The Inquiry, The Panel, The Chamber, the phone-in and the
  documentaries still take them. On its day it is back with its history
  (`world.pool_threads`; `[story] pool = false` switches it off).
- **Archive**: every segment aired, searchable, for callbacks and for the
  documentary's research. What each documentary established (its timeline and
  sections) is kept apart in `documentaries`, since the archive keeps only 400
  characters of a piece.

The **story desk** (`desk.py`) runs every `plan_every_s` when the worker is
idle and the live buffer is healthy. It assigns phases, writes next
developments, closes finished threads and seeds new ones (`[story]
seeds_per_day`, released a few at a time from `seeds_from`, none overnight).
Each call plans a batch of threads (`[story] batch`, the least recently
planned first), so the reply stays small as the town grows and the board
rotates. Every two hours the **senior editor** (`senior.py`) reads the whole
board and leaves the desk a memo: threads to merge, people to trim, a story
that needs a new angle.

```bash
uv run python -m newsroom.desk plan --dry      # see what the desk would do
uv run python -m newsroom.desk plan            # apply it
uv run python -m newsroom.world editor         # the fuller briefing the desk sees
uv run python -m newsroom.world archive        # last 20 archive entries
```

## Special reports

The first step towards documentaries. The editor reads the open threads every
`check_every_s` and decides whether one has earned a five-minute piece;
usually the answer is no. A commissioned special is a **resumable**
low-priority job: outline, then one section per stage, then voicing, then
finish. After each stage it re-queues itself, so live slots are served in
between and the longest uninterruptible unit is one model call. Progress is
checkpointed to `data/cache/*.partial.json` and resumed on startup; a stage that
fails (a model timeout) is tried once more before the special is dropped. A finished
special waits for the next news bumper (overnight, the next test card), and survives
a restart until it has aired. Knobs live under `[special]` and `[story]`
in `config.toml`.

```bash
uv run python -m newsroom.special decide                       # ask the editor now
uv run python -m newsroom.special make --thread t002           # write one for a thread
```

## The nightly documentary

*Port Wexley Stories* (`documentary.py`, `[documentary]` in `config.toml`): fifteen
minutes on one subject, every night. Once per broadcast day, in idle time from
18:00, the documentary editor picks a long-running thread or a piece of the
town's history. It is then made like a special, in stages between live slots,
with a research stage first: the researcher reads every archive piece on the
thread plus a keyword search, and writes notes (a dated timeline marking what is
on record and what is background, the people with a stake, telling details,
open questions). The outline (6–10 sections) and every section are written from
those notes. Voicing is a few lines per stage, so even fifteen minutes of
speech never holds up the live slots. It airs at the first news bumper from
21:00, within the hour; one not ready in time waits for tomorrow, and it never
airs at a special's break. `--documentary-now` commissions one straight away.

**Archive footage:** the research stage looks up the cached audio of the pieces
it read and offers the outline up to eight clips (a guest's quote, or else
Miles in the field; never an anchor reading the news). The outline places up to
three, one per section; the section's first line leads into the clip and the
next picks up after it. The clip airs in black and white, tagged ARCHIVE and
captioned with who said it and when, from the documentary's own copy of the
audio.

```bash
uv run python -m newsroom.special make --documentary --thread t030   # make one now
```

## Layout

| file | job |
|---|---|
| `config.toml` / `config.py` | providers, routes, voices, buffer horizon, paths |
| `models.py` | `Segment`, `Line`, `VisualCue`, and the per-type LLM schemas |
| `world.py` | the story bible: presenters, people, threads, archive |
| `llm.py` | one `complete_json()` door; OpenAI-compatible or Anthropic; strict JSON + one retry |
| `writers.py` | prompts per show and segment type, studio guests, template fallbacks |
| `special.py` | the editor decision and the resumable special-report stages |
| `documentary.py` | *Port Wexley Stories*: the pick, the research notes, the archive clips, the overnight repeat |
| `desk.py` | the story desk: phases, next developments, new threads |
| `senior.py` | the senior editor's memo on the whole board |
| `phonein.py` / `inquiry.py` / `panel.py` / `chamber.py` | the booked shows: each one's booking, stand-in and briefing |
| `outabout.py` | *Out and About*'s reviews: stars out of five, remembered, and an owner may answer back on *Coastwide* |
| `council.py` | the council calendar and the six councillors |
| `tides.py` / `sport.py` / `rugby.py` / `darts.py` / `quay.py` | facts worked out in code: tides and ferry, results and tables, the fish auction |
| `tipline.py` | the viewer tip-line file: new lines, pending tips, the CLI |
| `breaking.py` | breaking news: sorting tip-line lines, scripting and stinging the interrupt |
| `adverts.py` | the local advert pool and the planned ad breaks |
| `continuity.py` | idents, "Later on Channel 7", the tides card, notices and trails |
| `tts.py` | Pocket TTS cloning `assets/voices/`, else Kokoro, on CPU → 24 kHz WAV + mouth envelope |
| `jingle.py` / `station_audio.py` | the station's sonic logo, its arrangements and the music stems |
| `assets.py` | bakes the bumpers, breaking sting and music bed |
| `buffer.py` | priority intake queue + ready-by-slot dictionary + pockets for specials and breaking news |
| `schedule.py` | the shows, the daily schedule and the broadcast clock |
| `producer.py` | plans slots ahead from the schedule and the show's running order; closings and hand-overs |
| `workers.py` | generation thread, content cache, watchdog, idle editorial work and bookings |
| `player.py` | consumes the buffer, drives audio, applies timed cues, builds the `View` |
| `locations.py` | the places a picture can be set, and where people stand on the studio sets |
| `backdrops.py` / `skies.py` | backdrop art, time-of-day and weather grading, drifting skies and animated touches |
| `scenes.py` / `sprites.py` / `logo.py` | draws the `View` on a 320×180 canvas scaled up, with the station bug |
| `obs.py` | records each programme to its own file in OBS, from the player's log (`--obs`) |
| `tools/obs_record.py` | the same from another window, following a running station's log file |

## Dev commands

```bash
uv run python -m newsroom.tts "Good evening"          # synth one line and play it
uv run python -m newsroom.llm weather --dry-run        # show prompt + schema, no call
uv run python -m newsroom.llm sofa --show breakfast --dry-run   # a breakfast prompt
uv run python -m newsroom.llm interview --show late --part cont --dry-run   # a guest's second part
uv run python -m newsroom.schedule                     # the day's schedule
uv run python -m newsroom --clock 06:00 --debug        # watch breakfast at any hour
uv run python -m newsroom.llm weather                  # live call to the routed provider
uv run python -m newsroom.world                        # print the writers' briefing
uv run python -m newsroom.workers field_report         # one segment end to end
uv run python -m newsroom --no-window --minutes 3 --scratch   # headless soak on a copy of the town
uv run pytest                                          # all tests, on a temp town (no model, no TTS)
uv run python -m unittest tests.test_world             # thread cap and template threads (no model, no TTS)
uv run python -m newsroom.backdrops --sheet sheet.png  # every backdrop at day, dusk and night
uv run python -m newsroom.sprites --sheet people.png   # every presenter and a crowd of guests
uv run python -m newsroom.tides 2026-11-02             # that day's tides and foot ferry
uv run python -m newsroom.adverts                      # the advert pool (--make writes and voices one)
uv run python -m newsroom.continuity                   # the continuity pool (--bake bakes what's due)
uv run python -m newsroom.sport                        # the football: results, fixtures and the table
uv run python -m newsroom.quay                         # the fish auction's latest prices
uv run python -m newsroom --obs                         # record each programme in OBS as it airs
uv run python tools/obs_record.py data/logs/station-2026-11-05-1830.log   # the same for a station already running
uv run python -m newsroom --devices                     # the sound outputs, for --audio-device
uv run python -m newsroom.tipline "BREAKING: Smoke over the old cannery"   # breaking news
uv run python -m newsroom.tipline "The lifeboat open day is on Saturday"   # a tip for the bulletins
```

Generated audio and segment JSON live in `data/cache/`, keyed by (type, date,
slot, town, day, provider, show, and the running order's part and brief). Delete the folder to force regeneration.
Overnight repeats are drawn from the last two days of this cache.

## Notes

- Python is pinned to 3.12 because `kokoro`/`misaki` do not install on 3.13.
- Kokoro runs on CPU on purpose so the GPU is free for a local model.
- Kimi k2.6 is a thinking model: with thinking disabled it only accepts
  temperature 0.6; with it enabled, only 1.0 and it needs ~4000 `max_tokens`
  to leave room for reasoning. The Kimi providers in `config.toml` disable
  thinking for live segments and enable it for the editor, desk and specials
  on k3.
- `<think>` blocks are stripped defensively regardless of provider.
- Generated content is cached per provider, so switching providers never
  replays another provider's scripts.
- `--workers N` is safe: the world state has its own lock (`World.lock`).

## Licence

MIT; see [LICENSE](LICENSE). Port Wexley and everyone in it are fictional.

Voices: [Pocket TTS](https://huggingface.co/kyutai/pocket-tts) by Kyutai (weights CC-BY-4.0, gated:
accept the terms and `hf auth login` once), cloning reference clips in `assets/voices/`. Most presenters'
clips are renders of their own [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) voices (Apache 2.0),
and so are the visitors'. The local guests, the mayor and councillors, and three presenters (Tamsin Jago,
Howard Lanyon and Meg Trethewey) were designed from a description with
[DramaBox](https://huggingface.co/ResembleAI/Dramabox) by Resemble AI (LTX-2 Community License) on
2026-11-01, replacing a first set of guest clips made with Qwen3-TTS VoiceDesign. Kokoro voices everyone
else.

Every model, font and licence, and what each means for a monetised stream, is in
[docs/CREDITS.md](docs/CREDITS.md).
