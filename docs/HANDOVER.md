# Handover: 2026-10-25

## Update: day-parts, part 1 (later the same day)

Item 1 of "What next" below is half done: the schedule and the breakfast show.

- **`schedule.py`** holds the shows and a normal day: overnight 00–06, *Morning
  Tide* 06–09, the news 09–19, the magazine 19–20 (not built, so the news stands
  in, via `STAND_INS`), then the news 20–24. The producer picks each slot's show
  from its planned start time and restarts the pattern when the show changes.
  `--clock HH:MM` moves the broadcast clock, so any show can be tested at any hour.
- **Breakfast:**
  - **Presenters.** Rosie Treloar (`host_a`, voice `bf_lily`) and Jonah Pike (`host_b`, `am_eric`) on `studio_sofa`. Gordon and Miles keep their jobs.
  - **Segment types.** New `sofa` chats, with the headlines, weather and field reports in breakfast versions.
  - **Shots.** Close-ups crop round the speaking host. Handovers show a LIVE inset box.
  - **Branding.** An orange *Morning Tide* bumper, with its ident voiced by Rosie.
- **Lighter shows.** `Show.light` adds a weighting rule to the prompt. The one exception, the "big running story", is chosen in code: the most-covered thread at its `peak` (`writers.big_story`). The magazine should set `light=True` too.
- **Casts.** `script_schema(type, cast)` narrows the speaker enum per show, and `summary_for_prompt(cast)` lists only that cast. The sofa allows only the two hosts.
- **Overnight:**
  - **Picture.** A test card ("programmes resume at 06:00") alternates with repeats drawn from the last two days of `data/cache/`. Repeats make no model calls and are tagged REPEAT.
  - **Background work.** The editor and story desk keep running. Specials only air after a bumper in a show with `airs_specials`, which is the news.
- **Smaller changes:**
  - The show is part of the cache key. News keeps its old key, so the existing cache is still valid.
  - The day now rolls over while running.
  - Old `world.json` files gain the new presenters on load.
- **Verified:**
  - A template soak across 06:00 and a real Kimi soak across 09:00, with no failed jobs.
  - Windowed snapshots of the sofa, close-ups, the inset and the test card.
  - The real breakfast scripts are lighter, and led with the quay story.
- **Not committed:** `assets/bumper_breakfast.wav`, which is baked on first run. Whether baked WAVs belong in the repo is still open in TODO.

**Next:** the magazine, which needs studio interviews (item 2 below) first.

## Update: day-parts, part 2 (later again)

Items 1 and 2 of "What next" below are done.

- **The full day:**

  | From | Show |
  |---|---|
  | 00:00 | overnight |
  | 06:00 | *Morning Tide* |
  | 09:00 | the news |
  | 19:00 | *Coastwide* (magazine) |
  | 20:00 | the news |
  | 22:00 | *The Last Ferry* (talk show) |
  | 23:00 | the late news |

  `STAND_INS` is now empty.
- **New segment types:**
  - `interview`, `links`, `feature`, `vox_pop`, `consumer` and `monologue`, with schemas `InterviewScript`, `FeatureScript` and `VoxPopScript` (with `GuestLine` and `VoxLine`).
  - `script_schema` narrows whichever line type a schema uses.
  - Prompts live per show in `writers.py`: `_SYSTEM`, `_BREAKFAST`, `_MAGAZINE` and `_LATE`.
- **The news** swaps its field report for a studio interview with Dana every third loop.
- **Presenters:**
  - Pat Holloway (`mag_a`, `bf_alice`) and Clive Ashdown (`mag_b`, `am_liam`) on *Coastwide*.
  - Vincent Marr (`late_host`, `am_onyx`) on *The Last Ferry*.
  - The voices were downloaded once into the Kokoro cache.
- **Interview set:**
  - The player works out who sits there (`View.people`), and the close shots crop round the speaker.
  - *The Last Ferry* uses the same set with the lights down (`scenes._night_look`).
  - Outside pieces open at the big-picture wall with that presenter, tagged LIVE, REPORT or VOX POP.
- **Guests:**
  - Guests are promoted into the cast. Vox-pop passers-by are too, so they can recur as residents.
  - A guest who was just on triggers one retry for someone else.
  - A presenter can be a guest and is voiced and drawn as themselves. The story desk has made Gordon the ghost-tour operator, and the model loves booking him.
  - Only bulletins, field reports, interviews and features may open new threads.
- **Kimi tolerance.**
  - **Why:** Moonshot doesn't enforce the JSON schema.
  - **The fix:** `_keys_hint` lists the expected keys in the system prompt, and the schemas accept `speaker_id`, guest details on each line, and "female"/"male".
  - **Result:** the last real runs scripted every *Coastwide* and *Last Ferry* item with no template fallbacks.
- **Known:**
  - Kimi still overruns some string caps once per run (see TODO).
  - The magazine and talk-show loops repeat their format several times an hour.

---

This covers where Mini Newsroom stands after the backdrop session and what to
do next. The backlog is in [TODO.md](../TODO.md) and the project overview in
the [README](../README.md).

## What this session did

All of it is pushed to `cubes321/mini-newsroom`, branch `master`.

| Commit | What |
|---|---|
| `19caab0` | **Backdrop system.** `locations.py` is the registry: 24 writer-selectable locations plus studio sets. `backdrops.py` loads PNG art or falls back to a placeholder painter, grades for time of day and weather, and animates water, rain, snow, fog, wind and the lighthouse beam. Writers see a LOCATIONS list in their prompts. |
| `f4aa387` | **Studio shots.** The player picks a framing for each line (`View.shot`): bulletins cut wide → close → wide, and field-report handovers and special intros put the anchor at the big-picture wall with the location on screen. |
| `7976343` | **Backdrop art.** Pixel-art PNGs for every location and for `studio_wide` and `weather_wall`, made in ComfyUI from the placeholders and approved by the user on contact sheets. |
| `c71c710` | **README screenshots** re-shot with the new art and shots, plus a strip of six locations. |
| `e7dd1c9` | **Two new studio sets**, `studio_interview` and `studio_sofa`, with character marks (`MARKS` in `locations.py`) and art. Nothing uses them on air yet. |

## How the visuals fit together

- **`locations.py`** holds data only (no pygame): id, name, the one-line description writers see, kind (town, country or studio), and colours. `BACKDROP_IDS` becomes the `Backdrop` literal in `models.py`, so the JSON schema enum and the registry can't drift apart. `MARKS` says where people sit on studio sets as (x, baseline y, scale, facing).
- **`backdrops.py`** is the only place backdrop I/O happens.
  - **Lookup order:** `<id>_<tod>.png`, then `<id>.png`, then a painter.
  - **Grading:** a numpy pass for time of day and the last weather report. Exteriors only; studio sets are never tinted.
  - **Caching:** a small LRU per (id, tod, weather).
  - **Per frame**, `draw()` blits the cached picture and adds the animated touches.
  - **`picture()`** gives a cropped, smooth-scaled copy for the big-picture wall screen.
- **`player.py`** gives `View` the time of day (`tod`), the last weather report (`weather`, taken from `world.last_weather`, so it survives restarts), and the framing (`shot` and `wall_label`).
- **`scenes.py`** stays pure. Field reports and specials call `backdrops.draw`, and the studio dispatches on `v.shot`.
- **Art rules** are in [assets/backdrops/README.md](../assets/backdrops/README.md): 320×180, the ground line, the areas overlays cover, the water rectangles, and who sits where on each studio set.

## Known gaps

- **Dusk on PNG art looks grey.** The grade is a whole-picture multiply, so blue skies go flat grey instead of turning to sunset. The placeholders didn't have this problem because they paint their own sky. Two fixes: a vertical gradient grade (purple at the top, orange towards the horizon) for exteriors, or `<id>_dusk.png` files for the busiest places. The README screenshots avoid dusk on the art for this reason.
- **Night on PNG art has no lit windows.** Window and lamp lights only exist for placeholders, which declare them. The fix is hand-made `<id>_night.png` variants, starting with the harbour, high street and Town Hall.
- **Positions in the code were set for the placeholders, not the art.**
  - The lighthouse beam comes from the fixed `LIGHTHOUSE_LAMP = (251, 21)`, while the art's lantern looks nearer (242, 16).
  - The `WATER` shimmer rectangles need re-fitting. On `slipway`, the top strip (120, 106, 200, 10) covers the head of the ramp, so about 40 px of stone shimmers.
  - The crane on `loading_dock` and the drill tower on `fire_station` reach up behind the clock box at (276–316, 4–16).
- **The art scripts are gone.** They lived in the art session's scratchpad. How to rebuild them, plus the exact ComfyUI models, prompt pattern and pixelation steps, is in Claude's project memory (`backdrop-art-pipeline`). Rebuilding is about 300 lines in total.
- **The two new studio sets aren't on air.** They're waiting for the features that use them (see below).
- **A few older cached segments** still carry "Live from loading_dock" captions, written before the prompt was fixed to keep the spoken place name separate from the backdrop id. New scripts are fine. Delete `data/cache/` to regenerate.
- **`docs/screenshots/filler.png`** is no longer shown in the README.
- **Bulletins sometimes fail validation once** and succeed on the retry. This happened before the backdrop work and is unrelated to it.

## What next

The user's ideas from this session, in the suggested order:

1. **Day-parts, with a breakfast show and an early-evening magazine.** This is the next real milestone; it's in TODO under Content.
   - **Breakfast** on the `studio_sofa` set needs two new presenters: characters in `world.py`, unused Kokoro voices, sprite palettes and traits. Gordon Pell could do the breakfast weather.
   - **The magazine** is in the spirit of the BBC's *Nationwide*: features rather than headlines, a consumer slot, a resident in the studio on `studio_interview`, and filmed pieces introduced at the big-picture wall.
   - **A schedule table** picks the show by the clock. `locations.time_of_day()` already gives the scenes the hour.
2. **Studio interviews and vox pops** using the guest mechanism, which puts `studio_interview` on air.
3. **The dusk grade fix** and a few `_night.png` variants.
4. Everything else in TODO: adverts and tides, breaking news, the tip-line, sport, longer documentaries.

## Working notes

- **The GPU is shared** (16 GB). Check `nvidia-smi` before loading anything. After ComfyUI batches, free its VRAM with `POST http://127.0.0.1:8188/free`. Kokoro stays on CPU.
- **Scripts come from Moonshot** (Kimi) at the moment, because the user is using up that credit. Real runs use it, which is fine.
- **Art workflow:** generate in a separate session, show the user a contact sheet, and commit PNGs only after approval. That session shares this folder, so commit by explicit paths, never `git add -A`.
- **Push only when the user asks.**

## Checks that work

```bash
uv run python -m newsroom.backdrops --sheet sheet.png         # every backdrop at day, dusk and night, plus weather
uv run python -m newsroom.llm field_report --dry-run          # see the LOCATIONS block and the schema enum
uv run python -m newsroom --minutes 4 --debug --snap DIR      # real window, a frame every 10 s
uv run python -m newsroom --no-window --minutes 2             # headless soak
```

Last measured: frame p99 1.6–5.5 ms in the window, with no failed jobs in the headless soak.
