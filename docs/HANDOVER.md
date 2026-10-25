# Handover

Where Mini Newsroom stands at the end of 2026-10-25, and how to pick it up.
The backlog is [TODO.md](../TODO.md) and the overview is the [README](../README.md).
Everything below is on `master` at `cubes321/mini-newsroom`. Updated at the end of the day with
the second session's work: finished specials survive restarts, the dusk grade, hour-long running
orders for the magazine and the talk show, and breaking news from a viewer tip-line.

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

**Breaking news** can cut into any of these (see below).

## How it fits together

- **The pipeline:**
  - `schedule.show_at(ts)` picks the show for each slot by its *planned* start time.
  - The producer restarts the pattern at each show change, so every show opens on its bumper.
  - The producer keeps its show until that show's own end (`schedule.show_end`), and only then asks
    the schedule what is next. Retime can pull the planning cursor back across the hour, and a show
    once left must stay left.
  - Workers script each slot with the LLM, voice it with Kokoro, and cache it.
  - The player plays it on the clock.
- **Running orders:**
  - The news and breakfast loop a short `pattern`.
  - *Coastwide* and *The Last Ferry* have a written-out hour order. Entries are a type or an
    `Item(type, part, brief)`.
  - `loop_from` is where the order wraps if it runs out; it never wraps back to the bumper.
  - `closing` is planned once when less than half of the next item would fit before the hour.
    A guest's second part is never cut. If the hour turns mid-item, the goodbye runs a little
    over. Then the next show starts straight away.
  - Parts:
    - `open`: the only item that leads with the big story.
    - `cont`: the same guest after the break. Writers pass part one's transcript and skip the
      "recently booked" check. It falls back to a fresh interview if part one wasn't the slot
      just before, e.g. after a restart.
    - `close`: the sign-off.
  - `brief` is the angle given to the writer ("an animal story").
- **Per-show casts:**
  - `Show.cast` and `Show.cast_for(type)` say who may speak.
  - `models.script_schema(type, cast)` narrows the JSON speaker enum to that cast.
  - `world.summary_for_prompt(cast)` lists only that cast in the briefing.
- **Prompts:**
  - They live in `writers.py`, as one table per show: `_SYSTEM` (news), `_BREAKFAST`, `_MAGAZINE` and `_LATE`.
  - Each LLM-scripted type has a canned template, used when the model fails.
- **Segment types:**
  - Live: `bumper`, `weather`, `bulletin`, `field_report`, `sofa`, `interview`, `links`, `feature`, `vox_pop`, `consumer`, `monologue`.
  - Overnight: `testcard`, `repeat`.
  - Specials: `documentary`.
- **Guests:**
  - The writer books guests from the cast or invents them. Once booked, they join `world.people` with a fixed voice and look.
  - A guest who was just on triggers one retry for someone else.
  - A presenter can be a guest and appears as themselves. The story desk has made Gordon the cannery ghost-tour operator, and Kimi likes to book him.
- **Story threads:** only bulletins, field reports, interviews and features may open new ones.
- **Shots:**
  - The interview set seats whoever is in `View.people`, and the close shots crop round the speaker.
  - Outside pieces open at the big-picture wall with the presenter who introduces them, tagged LIVE, REPORT or VOX POP.
  - The sofa uses a LIVE inset box instead.
- **Breaking news and the tip-line** (`tipline.py`, `breaking.py`):
  - Tips are lines in `data/tipline.txt`, added with `python -m newsroom.tipline "..."` (`--list`
    shows the state).
  - The worker reads new complete lines before each job. The byte offset, pending tips and last
    breaking time live in `data/tipline.state.json`.
  - A plain tip is offered to the next bulletins as VIEWER TIPS. The bulletin schema's `tip_used`
    spends the one it used; unused tips expire after six hours.
  - A `BREAKING:` line becomes a segment outside the rundown: slot numbers from 2,000,000, at the
    front of the job queue, `show="news"`.
  - It is scripted with Dana at the desk (Miles may phone in), opens a thread marked `breaking`
    with phase `peak`, is voiced, and gets the sting (`assets/breaking_sting.wav`) as a silent
    first line.
  - The player sets the segment on air aside at the next line boundary and airs the breaking news:
    a red BREAKING NEWS card over the sting, then red captions. Then it resumes from the next line,
    with cues back-dated.
  - The test card is cut at once, a replay is dropped, and a bumper plays out.
  - Breaking news doesn't move the rundown, so a special can still follow the bumper before it.
  - A second `BREAKING:` within `[breaking] cooldown_s`, or one already old when first read (a
    restart), becomes a plain tip.
- **Specials across restarts:** `special.resume_ready` puts finished, unaired specials from the
  last 48 hours back in the side pocket. The player marks an aired special with an empty
  `data/cache/<hash>.aired`.
- **Overnight:**
  - Repeats come from the last 48 hours of `data/cache/`, with no model calls.
  - The story desk and editor keep working.
  - Specials only air after a news bumper.
- **Kimi** (via Moonshot) doesn't get the JSON schema enforced, so the code is tolerant:
  - `writers._keys_hint` puts the expected keys in the system prompt.
  - The schemas accept `speaker_id`, guest details on each line, and "female"/"male".

## Running and testing

```bash
uv run python -m newsroom                                   # the station, at the real time
uv run python -m newsroom --clock 19:00 --debug             # any show at any hour
uv run python -m newsroom --no-window --clock 21:58 --minutes 6   # headless soak across a show change
NEWSROOM_LLM=off uv run python -m newsroom --no-window ...  # canned scripts only, no model calls
uv run python -m newsroom.schedule                          # the day's table
uv run python -m newsroom.llm vox_pop --show magazine --dry-run   # a prompt and its schema
uv run python -m newsroom.workers interview --show news     # one real segment end to end
uv run python -m newsroom.backdrops --sheet sheet.png       # every backdrop, day/dusk/night
uv run python -m newsroom.tipline "BREAKING: Smoke over the old cannery"   # interrupt whatever is on
uv run python -m newsroom.llm interview --show late --part cont --brief "..." --dry-run
```

**Soak hygiene:** a run with `NEWSROOM_LLM=off` writes template headlines and threads
into `data/world.json`. Back it up first and restore it afterwards. Delete the cache
files the run made, or overnight may repeat them. A tip-line test also leaves
`data/tipline.txt` and `data/tipline.state.json`; delete both for a clean start.

## State of the town

The story bible (`data/world.json`, not in git) is on broadcast day 2:
- 25 open threads and 27 people, many of them vox-pop residents;
- four specials made.

25 open threads is far above `[story] max_open_threads = 8`. Many come from today's test
runs, and the story desk will close some as it plans. If you want a clean start,
back the file up and delete it, and the town re-seeds.

**"Who Gets the Quay?" never aired.** The special finished during a magazine test run.
It is recorded in `world.specials`, but its audio was removed by a test-cache cleanup.
The gap that hid (finished specials lost on restart) is now fixed. The three specials from
2026-10-24 have `.aired` markers so they don't air again.

## Known gaps (details in TODO)

- **Art:**
  - **Dusk:** a sunset tint for art without its own `_dusk.png` (purple sky, orange horizon,
    violet water). Horizons per location are in `backdrops.HORIZON`.
  - **Night:** there are no lit windows at night.
  - **Positions:** some are still set for the old placeholder pictures.
  - ***The Last Ferry*** borrows the interview set.
  - **People:** they are blocks drawn in code.
- **Format repetition:**
  - Breakfast still loops a 6-item pattern for three hours.
  - The magazine's and talk show's hour orders wrap once, after about 33 minutes.
- **Breaking news** comes only from the tip-line: the story desk can't raise it, and there is no
  follow-up report from Miles yet.
- **Special archive timing:** `record_aired` for a special runs when it is finished, not when it
  airs.
- **Length caps:** Kimi overruns some caps once per run and recovers on the retry (Miles over 900 characters, `thread_status` over 160, the desk's `note` over 200).
- **Guest captions:** a presenter as a guest is captioned with their presenter role, not the role in the script.
- **Not yet observed:**
  - an overnight special airing at the first news bumper;
  - the LM Studio provider;
  - a full overnight run.

## Good next steps

1. **A long real-Kimi run** across 19:00–20:00 and 22:00–23:00 to see the hour orders, the
   two-part guests and the sign-offs with real scripts. Add a breaking tip mid-show.
2. **Art session:** *The Last Ferry*'s own set, night variants, sprites for the eight presenters.
3. **Breakfast's hour order**, the same way as the magazine's.
4. **Breaking follow-ups:** Miles reporting from the scene in the next bulletin; the story desk
   raising breaking news itself.
5. **The world-state lock**, which would allow more than one worker and moving world writes
   (like a special's `record_aired`) to the main thread.

## Working notes

- **The GPU is shared** (16 GB). Check `nvidia-smi` before loading anything. Kokoro runs on the CPU.
- **Voices:**
  - Kokoro runs offline (`HF_HUB_OFFLINE=1`), and every voice in use is already cached.
  - A new voice needs a one-time `hf_hub_download` with offline mode off, and the user's OK.
  - Unused English voices now include `af_sarah`, `af_nova`, `af_sky`, `am_adam` and `am_echo`.
- **Scripts:** Kimi on Moonshot writes them (k2.6 for live segments, k3 for the editor, desk and specials). The user is happy to spend that credit.
- **Art workflow:** generate in a separate session, show the user a contact sheet, and commit only after approval.
- **Git:**
  - Commit by explicit paths, never `git add -A`: other sessions share this folder.
  - Push only when the user asks.
  - `*.wav` is ignored except under `assets/`. The baked bumpers are tracked.
- **Editing on Windows:** Git Bash heredocs can mangle `\n` escapes inside Python strings. Write edit scripts with the Write tool instead.
