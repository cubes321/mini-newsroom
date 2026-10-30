# Handover

## Picking up on the evening of 2026-10-30

Everything is on `master` (last pushed `e4a984a`). Since the 2026-10-29 DeepSeek night: the back
office runs on DeepSeek Flash with Sonnet as a two-hourly senior editor and as Flash's fallback; a
daily allowance of new stories (8) replaced the open-thread cap; four new shows went on the
schedule (*Have Your Say* 10:00, *Quayside* 13:00, *The Inquiry* 20:00, *The Panel* 20:30); Tamsin Jago is *Full Time*'s
reporter; *Coastwide* remembers its evening; the specials' sections no longer restate or foretell.
Tonight is two jobs, in this order.

### 1. A better TTS than Kokoro, and the voices waiting to be heard

The TODO's TTS item has the bar: keep up live (Kokoro on the CPU voices a minute of audio in about
4–18 s, and the buffer wants about ten minutes ready), fit beside the LLM and ComfyUI on the shared
16 GB card or run on the CPU (check `nvidia-smi` before loading anything), and have enough distinct
voices for the cast, with British voices that sound British. Voice the same lines with each
candidate and Kokoro, time each, and choose by ear before wiring one in behind `[tts] backend`.

More voices matter now: each new presenter took a voice from the guest pool, which is down to 9
female and 6 male Kokoro voices for the whole town.

To hear and choose on the same listening page (`newsroom/station_audio.py`, as for Fran and the
stings), whichever engine wins:

- **Tamsin Jago** (`sport_reporter`, *Full Time*'s reporter, twenty-five, Port Wexley born):
  provisional `af_sarah`, British. Try it against `af_bella`, `af_nova` and `af_sky`.
- **Howard Lanyon** (`business`, *Quayside*, a retired bank manager in his sixties): provisional
  `am_echo`, British, speed 0.95.
- **The new shows' bumpers**: *Quayside*, *The Inquiry* and *The Panel* use the news arrangement
  of the station tune (`jingle.VOICINGS` has no entry for them). Give each its own, as *Full Time*
  got "drive".

The chosen voice goes in `config.toml` `[tts.voices]`, and leaves `GUEST_VOICES_F`/`_M` in
`world.py`; guests who had it are recast on the next start.

### 2. The overnight run

The first night on the new back office, and the first airing of *The Inquiry* and *The Panel* (both
booked in idle time from 18:30). The routes are in `config.toml` now, so no `NEWSROOM_ROUTES`.
Run it in **its own PowerShell window**, not a Claude app terminal tab: an app update closed the
2026-10-29 night at 08:21.

```powershell
Set-Location 'E:\programming\mini newsroom'
$env:ANTHROPIC_API_KEY = [Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY', 'User')
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY', 'User')
$env:PYTHONIOENCODING = 'utf-8'
$day = Get-Date -Format 'yyyy-MM-dd'
Copy-Item data\world.json "data\world.backup-$day-pre-night.json"
cmd /c "uv run python -m newsroom --clock 18:30 --log-llm --minutes 930 > data\night-$day.log 2>&1"
```

What to check, against the 2026-10-29 night (`data/measure-deepseek-2026-10-29.log`) and the
all-Claude 2026-10-28 one (`data/measure-2026-10-28.log`):

- **The senior editor**: its memos ("senior editor:" lines) and whether the desk's notes stop
  converging on one meeting (11 of 24 rounds said "converge" on 2026-10-29).
- **New stories**: how many the desk and the senior editor seed ("seeded thread"), up to 8 a day,
  and whether they air.
- **The fallback**: how often "falling back to" fires, and why.
- **The Inquiry** (20:00): the story and guest it booked ("inquiry: tonight"), and whether Pat's
  questions run across both halves of the interview.
- **The Panel** (20:30): the lineup ("panel: tonight"), four separate voices at the desk, one
  question per debate.
- **Full Time**: Tamsin at the stadium and the darts pub, the Wreckers' vox pop at the Quarry Field.
- **Coastwide**: repeats across the hour (list what aired 19:00–20:00, as for the recording).
- **Cost**: DeepSeek's usage export against the call log, and the night against $0.55 (Flash) and
  $2.18 (all Claude) for the same span.
- **The usual**: no filler in STATS, tracebacks, failed calls, the title-match continuations.

*Quayside* is at 13:00 and a night run ends mid-morning, so it needs its own run (`--clock 12:45`
for an hour or so) to be seen on air.

### The shows still to build

From the 2026-10-30 brainstorm; the full plan, a day's schedule and the reasons are in
[SHOWS.md](SHOWS.md). *Have Your Say* (10:00) was built on the evening of 2026-10-30: Jonah's phone-in,
with the `call` item (a caller through a telephone band, a box with a waveform instead of a face). It
needs a morning run to be seen on air (`--clock 09:45`), as *Quayside* does. Still to build, in the
agreed order:

1. **Out and About** (15:00, 45 minutes): travel, culture and food. Days out along the Greymouth
   coast, the town's culture (gallery, amateur dramatics, music nights, the library's talks) and
   food (a café or restaurant visited and reviewed, a recipe, what's in season). Needs a new
   presenter (a look on a contact sheet, a voice by ear) and a `review` item with a verdict the
   world remembers, so a place can be revisited or its owner answer back. Small to medium.
2. **The Chamber** (council nights, 20:00 to 21:00): the council meeting, live. Dana in the press
   seats, Helen Strand in the chair, Miles in the public gallery; items from the threads due at
   council, the public speaking, and votes that settle the stories (the desk takes each result as
   the thread's next development). Needs a council calendar, a `vote` result the desk applies, and
   a show that takes over the evening slot on those nights (as the documentary and breaking news
   take over the news). Do it after a night or two of watching the senior editor and the new
   story allowance: it changes how stories end. Large.
3. **Rock Pool** (16:00, 45 minutes): children's TV. A presenter and Gully, a herring-gull puppet
   with opinions; a "make" in the studio, story time (Hugh Tremayne reads a town legend), viewers'
   drawings, an animal visitor. Needs a presenter, Gully's sprite (a puppet with a moving beak) and
   voice, a children's set and a children's tone for the writers. Large, mostly art and voice: best
   when there's time to listen.

The day's schedule leaves the news at 09:00, 11:00, 13:30, 15:45, 16:45, 21:00 and 23:00 once all
seven are on. *The Kettle's On*, *Harbour Row* and *Wexley Wits* are kept for the entertainment
channel (`docs/ENGINE.md`).

Art waiting for ComfyUI: a proper set for *The Panel* (`studio_panel` is painted in code) and a
fish quay backdrop for *Quayside* (Miles reports the auction from the harbour until then).

## Where it stood on 2026-10-26

Where Mini Newsroom stands at the end of 2026-10-26, and how to pick it up.
The backlog is [TODO.md](../TODO.md) and the overview is the [README](../README.md).
Everything below is on `master` at `cubes321/mini-newsroom` (last pushed: `41145d9`), except
the work in progress listed under **In flight**.

Today's work: the first overnight run and the fixes it led to (specials, story-desk timeouts,
breakfast variety); a local-model bench; refined code-drawn characters with a look for every
guest; guest captions from the script; people lit by their location; a retry for empty desk
plans; tides and the Saltby foot ferry; local adverts that cover the gaps; fresh README
screenshots.

## Routing (decided 2026-10-26)

The Claude bench was committed in `3bf3527`, and the routes now use it: `claude_haiku` (Haiku
5.5, thinking off) writes every live segment, breaking news and adverts; `claude_sonnet`
(Sonnet 5.5, thinking on) ran the story desk, editor and specials until 2026-10-30, when they moved
to `deepseek_flash_think` (a quarter of the price) with Sonnet as the senior editor (`senior.py`)
and Flash's fallback. Haiku stays off the editor
(in the bench it re-commissioned an aired special). The story desk plans every 30 minutes
(`plan_every_s = 1800`). This holds until DeepSeek is benched for comparison; the Kimi
providers are still declared, so switching back is a change to `[llm.routes]`.

## What it is now

An always-on pixel-art TV station for the made-up town of Port Wexley. It runs a
full day on a schedule (`newsroom/schedule.py`):

| From | Show | Presenters | Set |
|---|---|---|---|
| 00:00 | overnight: test card and repeats | — | test card |
| 06:00 | *Morning Tide* (breakfast) | Rosie Treloar `host_a`, Jonah Pike `host_b` | `studio_sofa` |
| 09:00 | the news | Dana Ferris `anchor` | `studio_wide` |
| 19:00 | *Coastwide* (magazine) | Pat Holloway `mag_a`, Clive Ashdown `mag_b` | `studio_interview` |
| 20:00 | the news | Dana | `studio_wide` |
| 22:00 | *The Last Ferry* (talk show) | Vincent Marr `late_host` | `studio_interview`, lights down |
| 23:00 | the late news | Dana | `studio_wide` |

Gordon Pell (`weather`) and Miles Okafor (`reporter`) work across the shows.
Breakfast, the magazine and the talk show are `light=True`: gentler stories,
except one big running story, which they lead with briefly. That is a story
that broke as breaking news today, or else the most-covered thread at its peak
with at least four pieces of coverage. In the magazine and the talk show only
the opening item leads with it; later items mention it in passing at most.

**Breaking news** can cut into any of these, and **local adverts** fill any gap when the next
segment isn't ready (see below).

## How it fits together

- **The pipeline:**
  - `schedule.show_at(ts)` picks the show for each slot by its *planned* start time.
  - The producer restarts the pattern at each show change, so every show opens on its bumper.
  - The producer's cursor (when the next planned slot will start) is worked out on every tick:
    now, plus what is left on air (`player.time_left`), plus the unplayed queue (real lengths
    once voiced, targets before).
  - The producer keeps its show until that show's own end (`schedule.show_end`), and only then asks
    the schedule what is next.
  - Workers script each slot with the LLM, voice it with Kokoro, and cache it.
  - The player plays it on the clock.
- **Running orders:**
  - The news and breakfast loop a short `pattern`.
  - *Coastwide* and *The Last Ferry* have a written-out hour order. Entries are a type or an
    `Item(type, part, brief)`.
  - `loop_from` is where the order wraps if it runs out; it never wraps back to the bumper.
  - `closing` is planned once when less than half of the next item would fit before the hour.
    A guest's second part is never cut.
  - Parts: `open` (the only item that leads with the big story), `cont` (the same guest after
    the break, given part one's transcript), `close` (the sign-off).
  - `brief` is the angle given to the writer. A show can list `briefs` per type, handed out in
    turn; breakfast uses this so every sofa chat and report gets a different angle.
  - Each breakfast sofa chat is told this morning's earlier chats, and that a date or age said
    once is settled. Overnight repeats skip breakfast segments.
- **Per-show casts:** `Show.cast` / `Show.cast_for(type)` say who may speak;
  `models.script_schema(type, cast)` narrows the JSON speaker enum; `world.summary_for_prompt(cast)`
  lists only that cast.
- **Prompts** live in `writers.py`, one table per show (`_SYSTEM`, `_BREAKFAST`, `_MAGAZINE`,
  `_LATE`). Each LLM-scripted type has a canned template for when the model fails.
- **Segment types:**
  - Live: `bumper`, `weather`, `bulletin`, `field_report`, `sofa`, `interview`, `links`, `feature`,
    `vox_pop`, `consumer`, `monologue`.
  - Overnight: `testcard`, `repeat`.
  - Outside the rundown (no slot the producer plans): `documentary` (specials), `breaking`,
    `advert`.
- **Guests:**
  - The writer books guests from the cast or invents them. Once booked, they join `world.people`
    with a fixed voice. `ensure_person` upgrades a generic "resident" role when a later script
    (or an advert) names what they do.
  - A guest who was just on triggers one retry for someone else.
  - A presenter can be a guest and appears as themselves (Gordon runs the cannery ghost tours).
  - **Captions** use the role today's script gives them (`Line.guest_role`), also for a
    presenter booked as a guest.
- **Characters** (`sprites.py`):
  - Drawn in code, chunky on purpose: the user preferred this to generated PNG sprites (tried
    and set aside), because it suits the backdrops and varies for any guest.
  - A `Look` is skin, hair style and colour, facial hair, glasses, top style, tie, one accessory
    and a resting mouth. The eight presenters are in `LOOKS`, from agreed descriptions.
  - `guest_look(name, voice, role)` gives each guest a stable look: the voice decides whether
    they read as a woman or a man; role words dress them (`COSTUMES`: fire, police, lifeboat,
    harbour, chef, mayor, vicar, farmer, GP, councillor, teacher, celebrity, student).
  - The player puts every guest in shot on `View.guests` (name -> voice, role).
  - Three-quarter faces mirror with `facing`; the footprint is 26×37 units, as the sets expect.
  - On location people take half the backdrop's time-of-day and weather grade
    (`backdrops.person_light`); the late show's guests sit in its lights-down look.
  - `python -m newsroom.sprites --sheet out.png` draws every presenter and a crowd of guests.
- **Story threads:** only bulletins, field reports, interviews and features may open new ones.
  The thread cap drops closed threads first and never an open one.
- **Story desk** (`desk.py`): plans a batch of 8 threads per call on k3 (240 s, no SDK retry).
  A plan that updates none of the round's threads is asked for once more, then left for the
  next round.
- **Tides and the foot ferry** (`tides.py`): arithmetic from a fixed epoch, not the model. A
  semi-diurnal tide about 50 minutes later each day with a spring-neap cycle; the Saltby foot
  ferry across the Grey estuary every half hour from 07:00, the last at 23:15, none near low
  water or in a storm or fog. Weather, breakfast and late-show prompts get the day's times.
  `python -m newsroom.tides 2026-11-02`.
- **Shots:**
  - The interview set seats whoever is in `View.people`; close shots crop round the speaker.
  - Outside pieces open at the big-picture wall with the presenter who introduces them.
  - The sofa uses a LIVE inset box instead.
  - A resident on location faces Miles.
- **Breaking news and the tip-line** (`tipline.py`, `breaking.py`):
  - Tips are lines in `data/tipline.txt` (`python -m newsroom.tipline "..."`, `--list`).
  - A plain tip is offered to the next bulletins as VIEWER TIPS; `tip_used` spends it; unused
    tips expire after six hours.
  - A `BREAKING:` line becomes a segment outside the rundown, scripted with Dana at the desk,
    with the sting as a silent first line. The player sets the segment on air aside at the next
    line boundary, airs the breaking news, then resumes. A replay or an advert is dropped
    rather than resumed.
  - A second `BREAKING:` within `[breaking] cooldown_s`, or an old one at a restart, becomes a
    plain tip.
- **Specials:** they have their own cache key, survive restarts (`special.resume_ready`), are
  marked aired with `data/cache/<hash>.aired`, air after the test card overnight and after a
  news bumper in the day, and a failed stage is retried once.
- **The nightly documentary** (`documentary.py`, `[documentary]`, 2026-10-26): a special with
  `work["format"] = "documentary"`, 900 s. `should_commission`: once per broadcast day
  (`last_documentary_date`), from `commission_from` (18:00) until `airs_at` (21:00), never while a
  special is in hand; the editor goes on commissioning specials while a documentary is in hand. Stages: research (archive
  pieces on the thread plus `search_archive`, then `DocumentaryResearch` notes) -> outline
  (`DocumentaryOutline`, 6–10 sections) -> sections -> voice (10 lines a turn, `VOICE_LINES_PER_TURN`,
  for specials too) -> finish (`world.documentaries` gets the timeline and sections; no special
  cooldown). The buffer's side pocket is filtered by format (`buffer.seg_format`); the player pops a
  documentary only at a news bumper within `window_s` of `airs_at` on a day none has aired
  (`last_documentary_aired`). Routes: `documentary_commission` and `documentary_research` on Sonnet;
  the outline and sections reuse the special routes. `--documentary-now` forces a commission.
  First real run (scratch town, Claude, `--clock 20:35`): commissioned at once on t030 (59 pieces),
  researched from 42 archive pieces (8 timeline entries, 7 on record), outlined in 9 sections and
  made in about four minutes; 2,528 words, 838 s; aired at the 21:00 bumper and the news carried on
  after it with no filler. About $0.30 on Sonnet. Not yet seen in the window.
- **Adverts** (`adverts.py`, `data/ads/`, `[adverts]` in config.toml):
  - When the next slot isn't ready the player airs one, outside the rundown, up to
    `max_in_a_row` (3), then the filler card and the weather replay.
  - Eight hand-written `SEEDS` are voiced on the worker's first idle ticks, whatever the buffer
    and with or without a model; the model writes one every `make_every_s` (30 min) in healthy
    idle time, up to `pool_size` (40). A model-written one voiced past 32 s is dropped.
  - An owner who speaks joins the cast. Voiceovers use the guest voices, never the owner's.
  - The scene: the business's place, the owner on screen, an end card, no lower third or ticker.
  - `python -m newsroom.adverts` lists the pool; `--make` writes and voices one.
  - **Ad breaks** (2026-10-26): `ad_break` items in the light shows' orders (breakfast before each
    round of headlines, the magazine between blocks, the talk show between a guest's two parts),
    60 s targets. The worker only marks the slot ready; the player fills it with `BREAK_ADS` (2)
    adverts as it airs, so the pool and the "least recently aired" order are current. An empty
    pool (the first minute of a run) means the break is passed straight over. The producer never
    closes on a break that sits between a guest's parts.
- **Overnight:** repeats come from the last 48 hours of `data/cache/`, with no model calls; the
  story desk and editor keep working.
- **Kimi** (via Moonshot) doesn't get the JSON schema enforced, so the code is tolerant:
  `writers._keys_hint` puts the keys in the system prompt; the schemas accept `speaker_id`,
  guest details on each line and "female"/"male"; short card and status text is clipped on
  parse instead of failing.
- **LM Studio:** thinking is turned off with `extra_body = { reasoning_effort = "none" }`
  (`enable_thinking` is ignored).

## Running and testing

```bash
uv run python -m newsroom                                   # the station, at the real time
uv run python -m newsroom --clock 19:00 --debug             # any show at any hour
uv run python -m newsroom --scratch --clock 22:10 --minutes 3   # on a temp copy of the town
uv run python -m newsroom --log-llm                         # every prompt and reply to data/llm_calls/
NEWSROOM_LLM=off uv run python -m newsroom --scratch ...    # canned scripts only, no model calls
uv run pytest                                               # 73 tests on a temp town, no model, no TTS
uv run python -m newsroom.schedule                          # the day's table
uv run python -m newsroom.llm vox_pop --show magazine --dry-run   # a prompt and its schema
uv run python -m newsroom.workers interview --show news     # one real segment end to end
uv run python -m newsroom.backdrops --sheet sheet.png       # every backdrop, day/dusk/night
uv run python -m newsroom.sprites --sheet people.png        # every presenter and a crowd of guests
uv run python -m newsroom.tides                             # today's tides and ferry
uv run python -m newsroom.adverts                           # the advert pool
uv run python -m newsroom.tipline "BREAKING: Smoke over the old cannery"   # interrupt whatever is on
```

**Off-screen runs:** `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` runs the windowed loop
without a window or sound, with `--snap DIR` saving a frame every 10 s. The `--no-window` mode
doesn't build views, so it doesn't exercise the scenes or the player's view code.

**Soak hygiene:** use `--scratch`. It copies the world, the tip-line and the advert pool to a
temp folder and runs on the copies with an empty cache, so a test run can't touch the town's
canon or feed the overnight repeats. Without it, a run writes to `data/world.json` and
`data/cache/`. `pytest` uses temp paths through `tests/conftest.py`; bare
`unittest discover` doesn't, so don't use it.

## State of the town

The story bible (`data/world.json`, not in git) is on broadcast day 3 (2026-10-26):
- 32 threads, 27 of them open (far above `[story] max_open_threads = 8`; the desk closes them
  slowly);
- 59 people, many of them vox-pop residents;
- 8 specials made, 411 items in the archive.

**`data/ads/` doesn't exist yet.** The next real run voices the eight seed adverts in its first
idle moments (about 20 s of CPU), and writes the town into them: Jasper Fowle (hardware),
Kenji Okonkwo (taxis) and Nuala Brennan (the Lighthouse Café) get those roles, Gordon's ghost
tours become "Pell's Cannery Ghost Tours", and Dev's treacle tart is "the Thirteen O'Clock
Tart". Then one Kimi k2.6 call every 30 minutes adds a new advert.

**The Gordon Pell mix-up (fixed 2026-10-26):** the story desk had named him among a thread's
people, which made a "Gordon Pell, resident" entry (p010) that took the credit for 111 mentions
of the weatherman. `ensure_person` now refuses a presenter's name, and `load()` removes such
entries and their ids. p010 and the archive's "Gordon Pell turns forty with cannery cake" (his
agreed look is early 60s) are gone from the real town; the backup is
`data/world.backup-2026-10-26-gordon.json`. Presenters' ages aren't in the prompts.

## Known gaps (details in TODO)

- **Art:** 14 exteriors have lit night art and 8 keep the tint on purpose; some positions are
  still set for the old placeholder pictures (lighthouse beam, slipway water, the crane and
  drill tower behind the clock).
- **Adverts:** a gap advert plays out even if the slot it covers becomes ready a second in, so
  a gap costs up to one advert's length. Breaks aren't seen with a real model yet.
- **Format repetition:** the magazine's and talk show's hour orders wrap once, after about 33
  minutes.
- **Breaking news** comes only from the tip-line; there is no follow-up report from Miles yet.
- **Length caps:** a spoken line over 900 characters (Miles) still fails once and recovers on
  the retry.
- **Not yet seen with a real model:** tides in the scripts, the new guest captions, adverts
  written in a live run (one was written by hand with `--make`), and the LM Studio provider
  through the app's own config.

## Good next steps

1. **A `--log-llm` night on Claude**, the routing chosen on 2026-10-26 (Haiku live, Sonnet
   for the back office, desk every 30 minutes), to get real token counts and costs. Then the
   DeepSeek bench for comparison.
2. **A real-model evening** to see today's features in real scripts: tides and the ferry at
   breakfast and on *The Last Ferry*, guest captions, and adverts in gaps.
3. ~~Small fixes~~: the test-card flash and the Gordon Pell mix-up, done 2026-10-26.
4. ~~Ad breaks inside the light shows~~, done 2026-10-26.
5. ~~Art session~~, done 2026-10-26: `studio_late` for *The Last Ferry*, and 11 more night
   exteriors (14 in all; the other 8 keep the tint on purpose).
6. ~~The world-state lock~~, done 2026-10-26: `World.lock`; `--workers N` works; a special is
   archived when it airs. One worker is still the default.
7. ~~The documentary, part 2~~, done 2026-10-26: archive footage (`documentary.find_clips`,
   `archive_clip` on a section, `Line.archive`). Follow-ups are in TODO.

## Verified

- **The first real documentary**, 2026-10-26 22:05–22:50 on a scratch town (`--scratch --clock 20:30
  --documentary-now --log-llm --minutes 45`, Claude routes): Sonnet chose t030, the baker's petition
  for a second engine (59 pieces); research found 42 archive pieces, 9 timeline entries (6 on record)
  and 2 clips; the outline gave 8 sections with both clips placed; the sections stayed with what is on
  record ("reports differ on the exact time... so we say only that it happened at the fire station").
  13 Sonnet calls, about 83k tokens in and 18k out, and ready about 4 minutes after the commission. It
  aired at the first bumper after 21:00 (844.7 s, 61 lines); the user watched it and liked it. The same
  evening found the four fixes listed in TODO (blank captions, voices on Dana's close-up, cut
  headlines, a thread that led every bulletin) and the weather now comes once a news loop.
- **The first overnight run** (2026-10-25 22:28 to 2026-10-26 07:33): 525 segments, no filler;
  k2.6 made 179 calls, all fine. It found the story-desk timeouts (now 240 s with no retry), the
  specials bugs (now fixed) and breakfast repetition (now fixed).
- **Real Kimi scripts, 2026-10-25 evening:** *Coastwide*'s and *The Last Ferry*'s hours signed
  off within seconds of the hour; breaking news cut in at line boundaries and the programme
  resumed; breakfast was seen with real scripts in the overnight run.
- **2026-10-26, template runs on a scratch town** (`--scratch`, `NEWSROOM_LLM=off`, off-screen):
  three-minute runs in *The Last Ferry*, *Coastwide* and *Morning Tide* with no errors; guests in
  costume (a baker in chef's whites); the startup gap covered by an advert, with 0 s of filler.
- **One real advert from Kimi** ("Buchanan's Boatyard Chandlery", with Tam Buchanan), valid on
  the second attempt; it ran 36 s, which led to the 40–55 word brief and the 32 s cut.
- **Costs** from the Kimi console for the overnight night: 77 k3 calls ($3.18) where the app
  logged 23, because of the old timeout and SDK retry; now fixed.

## Working notes

- **Engine and town:** the backend is to be reused for an entertainment channel (plan in
  [ENGINE.md](ENGINE.md)). When changing or adding anything, keep the mechanics free of Port
  Wexley: names, places, prompts and show details come in through config, the schedule or the
  world, never as literals in engine code. Build work that every channel needs (TTS, parallax,
  the mixer, provider fallback) as engine features from the start.
- **The GPU is shared** (16 GB). Check `nvidia-smi` before loading anything. Kokoro runs on the
  CPU. After a ComfyUI batch, `POST /free` with `unload_models` (it under-reports what it holds).
- **Voices:**
  - Kokoro runs offline (`HF_HUB_OFFLINE=1`). Every voice on disk is in use (presenters and the
    guest pools); advert voiceovers reuse the guest voices.
  - A new voice (`af_sarah`, `af_nova`, `af_sky`, `am_adam`, `am_echo`...) needs a one-time
    `hf_hub_download` with offline mode off, and the user's OK.
- **Scripts:** Claude writes them since 2026-10-26 (Haiku 5.5 for live segments and adverts,
  Sonnet 5.5 for the editor, desk and specials; key in `ANTHROPIC_API_KEY`). Kimi on Moonshot
  (k2.6 live, k3 back office) wrote them before and is still declared.
- **Art:** the user judges by eye. Show a contact sheet (and the art in the real shots) before
  committing. Generated character art was rejected in favour of the code-drawn style.
- **Git:**
  - Commit by explicit paths, never `git add -A`: other sessions share this folder (one has
    uncommitted work in it now).
  - Push only when the user asks.
  - `*.wav` is ignored except under `assets/`, and so is everything the app writes under `data/`
    (the world, cache, tip-line, call logs and adverts).
- **Editing on Windows:** most files are CRLF. A Python edit script that reads bytes, edits with
  `\n` and writes CRLF back keeps diffs small; Git Bash heredocs can mangle `\n` escapes inside
  Python strings, so use the Write tool for scripts with escapes.
