# Handover

Where Mini Newsroom stands at the end of 2026-10-25, and how to pick it up.
The backlog is [TODO.md](../TODO.md) and the overview is the [README](../README.md).
Everything below is on `master` at `cubes321/mini-newsroom`, last commit `5d234ba`.

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
except one big running story (the most-covered thread at its peak with at
least four pieces of coverage), which they lead with briefly.

## How it fits together

- **The pipeline:**
  - `schedule.show_at(ts)` picks the show for each slot by its *planned* start time.
  - The producer restarts the pattern at each show change, so every show opens on its bumper.
  - Workers script each slot with the LLM, voice it with Kokoro, and cache it.
  - The player plays it on the clock.
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
```

**Soak hygiene:** a run with `NEWSROOM_LLM=off` writes template headlines and threads
into `data/world.json`. Back it up first and restore it afterwards. Delete the cache
files the run made, or overnight may repeat them.

## State of the town

The story bible (`data/world.json`, not in git) is on broadcast day 2:
- 25 open threads and 27 people, many of them vox-pop residents;
- four specials made.

25 open threads is far above `[story] max_open_threads = 8`. Many come from today's test
runs, and the story desk will close some as it plans. If you want a clean start,
back the file up and delete it, and the town re-seeds.

**"Who Gets the Quay?" never aired.** The special finished during a magazine test run.
It is recorded in `world.specials`, but its audio was removed by a test-cache cleanup.
This hides a real gap. A finished special waiting for a news bumper is saved to the cache,
but `resume_partials` only re-queues unfinished checkpoints, so after a restart it never
airs (now in TODO).

## Known gaps (details in TODO)

- **Art:**
  - **Dusk:** dusk on the art is a flat grey multiply, which also hits breakfast's first hour.
  - **Night:** there are no lit windows at night.
  - **Positions:** some are still set for the old placeholder pictures.
  - ***The Last Ferry*** borrows the interview set.
  - **People:** they are blocks drawn in code.
- **Format repetition:** the magazine and talk show loop every 6–8 minutes, so an hour repeats its shape.
- **Length caps:** Kimi overruns some caps once per run and recovers on the retry (Miles over 900 characters, `thread_status` over 160, the desk's `note` over 200).
- **Guest captions:** a presenter as a guest is captioned with their presenter role, not the role in the script.
- **Not yet observed:**
  - an overnight special airing at the first news bumper;
  - the LM Studio provider;
  - a full overnight run.

## Good next steps

1. **Re-queue finished specials on restart.** Small, and it protects the editor's work.
2. **A planned running order per hour** for the magazine and talk show, instead of a short loop.
3. **The dusk grade** (a gradient for exteriors). It helps every show at the edges of the day.
4. **Breaking news and the tip-line**, which the schedule was built to make room for.
5. **Art session:** *The Last Ferry*'s own set, night variants, sprites for the eight presenters.

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
