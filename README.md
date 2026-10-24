# Mini Newsroom

A pixel-art, always-on TV newsroom for the fictional town of **Port Wexley**.
An LLM writes the scripts, Kokoro voices them on the CPU, and a Pygame window
plays them out like a small local station: bumpers, weather, bulletins and
on-site field reports, looping forever.

The one rule the whole design hangs on: **the broadcast never waits on the AI.**
A producer plans the rundown minutes ahead, worker threads fill a buffer with
finished audio, and the player consumes that buffer on the wall clock. When the
buffer runs dry it plays filler and replays the last weather until new content
lands.

## Run it

```bash
uv sync
uv run python -m newsroom
```

Scripts come from whichever provider `[llm.routes]` in `config.toml` names.
Providers are declared under `[llm.providers.<name>]`; any OpenAI-compatible
endpoint works (`kind = "openai"`), plus the Anthropic SDK (`kind = "anthropic"`).
Shipped entries: `moonshot` (Kimi, needs `MOONSHOT_API_KEY` in the environment),
`lmstudio` (local, `http://localhost:1234`), `anthropic`. Set
`NEWSROOM_LLM=<name>` to force one provider for every task, or `NEWSROOM_LLM=off`
to run entirely on canned template scripts with no model at all.

Flags: `--debug` draws slot/buffer status, `--minutes N` auto-exits,
`--no-window` runs the producer, workers and a simulated player headless,
`--snap DIR` saves a frame every 10 s.

Expected cold start: filler card → bumper → short filler while Kokoro loads →
weather → bulletin → field report → bumper → … After the first loop the buffer
stays ahead and there is no more filler.

## The story bible

`data/world.json` is the town's memory and cast list:

- **Presenters**: Dana Ferris (anchor), Gordon Pell (weather), Miles Okafor
  (field reporter), with fixed voices.
- **People**: seeded public figures and worthies (the mayor, police and fire
  chiefs, the MP, the harbourmaster, a head teacher, the lifeboat coxswain,
  the historical society chair) plus residents promoted from special-report
  guests. Each has a stable voice, speaking speed and look so they can recur.
  Appearances are counted whenever a script names them.
- **Threads**: story lines with a phase (emerging → developing → peak →
  resolving → closed), the beats aired so far, the people involved and a
  planned NEXT development. Writers see the NEXT in their briefing and are told
  a follow-up must deliver it, so stories move instead of repeating.
- **Archive**: every segment aired, searchable, for callbacks now and for
  documentary research later.

The **story desk** (`desk.py`, `kimi-k3`) runs every `plan_every_s` when the
worker is idle and the live buffer is healthy. It assigns phases, writes next
developments, closes finished threads and occasionally seeds a new one.

```bash
uv run python -m newsroom.desk plan --dry      # see what the desk would do
uv run python -m newsroom.desk plan            # apply it
uv run python -m newsroom.world editor         # the fuller briefing the desk sees
uv run python -m newsroom.world archive        # last 20 archive entries
```

## Special reports

The first step towards documentaries. The editor (`kimi-k3`, thinking on)
reads the open threads every `check_every_s` and decides whether one has
earned a five-minute piece; usually the answer is no. A commissioned special
is a **resumable** low-priority job: outline, then one section per stage,
then voicing, then finish. After each stage it re-queues itself, so live
slots are served in between and the longest uninterruptible unit is one
model call. Progress is checkpointed to `data/cache/*.partial.json`. A
finished special waits for the next bumper. Background work only runs when
the live buffer is above `min_buffer_frac` of the horizon. Knobs live under
`[special]` and `[story]` in `config.toml`.

```bash
uv run python -m newsroom.special decide                       # ask the editor now
uv run python -m newsroom.special make --thread t002           # write one for a thread
uv run python -m newsroom --special-now                        # run with the editor triggered at start
```

## Layout

| file | job |
|---|---|
| `config.toml` / `config.py` | models, voices, buffer horizon, paths |
| `models.py` | `Segment`, `Line`, `VisualCue`, and the per-type LLM schemas |
| `world.py` | persistent town state: characters, threads, headlines, last weather |
| `llm.py` | one `complete_json()` door; LM Studio or Anthropic; strict JSON + one retry |
| `writers.py` | prompts per segment type and template fallbacks |
| `special.py` | the editor decision and the resumable special-report stages |
| `desk.py` | the story desk: phases, next developments, new threads |
| `tts.py` | Kokoro on CPU → 24 kHz mono WAV + mouth envelope |
| `assets.py` | bakes the placeholder bumper and music bed on first run |
| `buffer.py` | priority intake queue + ready-by-slot dictionary |
| `producer.py` | plans slots ahead, retimes when real durations land |
| `workers.py` | generation thread(s), content cache, watchdog |
| `player.py` | consumes the buffer, drives audio, builds the `View` |
| `scenes.py` / `sprites.py` | draws the `View` on a 320×180 canvas scaled up |

## Dev commands

```bash
uv run python -m newsroom.tts "Good evening"          # synth one line and play it
uv run python -m newsroom.llm weather --dry-run        # show prompt + schema, no call
uv run python -m newsroom.llm weather                  # live call to LM Studio
uv run python -m newsroom.world                        # print the prompt summary
uv run python -m newsroom.workers field_report         # one segment end to end
uv run python -m newsroom --no-window --minutes 3      # headless soak
```

Generated audio and segment JSON live in `data/cache/`, keyed by
(type, date, slot, town, day). Delete the folder to force regeneration.

## Notes

- Python is pinned to 3.12 because `kokoro`/`misaki` do not install on 3.13.
- Kokoro runs on CPU on purpose so the GPU is free for LM Studio.
- Kimi k2.6 is a thinking model: with thinking disabled it only accepts
  temperature 0.6; with it enabled, only 1.0 and it needs ~4000 `max_tokens`
  to leave room for reasoning. The shipped config disables thinking.
- The LM Studio entry disables Qwen thinking per request; `<think>` blocks are
  stripped defensively regardless of provider.
- Generated content is cached per provider, so switching providers never
  replays another provider's scripts.
- Longer documentaries with real research, a 24 h schedule, breaking-news
  interrupts and real sprite art are not here yet; specials are the template
  for the first of those.
