# Mini Newsroom: notes for Claude

An always-on pixel-art TV station (Channel 7) for the made-up seaside town of Port Wexley, in Pygame.
docs/HANDOVER.md is the current state, docs/ENGINE.md the architecture, docs/SHOWS.md the schedule,
docs/STREAMING.md OBS and audio.

## Running things

- Use `uv run` for everything (`uv run pytest -q`, `uv run python -m newsroom ...`): the global Python's
  packages are too old.
- **Any station run writes the real town**: `data/world.json` and `data/cache`, even with templates instead
  of a model. Test with `--scratch`, or `--world`/`--cache` pointing at copies. `pytest` is isolated by
  tests/conftest.py; a new test module must not set paths itself after importing newsroom.
- Shells started by the Claude desktop app don't have the user-level API keys; copy them in from the User
  environment without printing them, or the station quietly runs on templates. Long runs go in their own
  window (`explorer.exe <a .cmd>`), not the app's terminal, which dies with an app restart.
- Nothing in `data/` is tracked (see .gitignore). Other sessions often share this checkout: commit by explicit
  paths, never `git add -A`, and leave alone changes that aren't yours.

## One-off programmes (tools/one_off.py)

Out-of-canon programmes (a real-world special, an interview with a character from outside the town) live in
`data/one_off/<name>/`: `special.toml` and a hand-written `script.md`, with no model involved, and their own copy
of the world, so the town never hears of them. The script is approved by the user before it is voiced.
`voice` → `preview` (silent frames) → `air --obs` → `cards --video <recording>` → `short` for a YouTube Short.
See the module docstring for the formats: `NAME (mood): text` lines, `[set]` for a set of its own (registered
at runtime only, never in locations.py), `[cast.X.look]` to dress a guest by hand, `[cards] strips`.

## Characters (newsroom/sprites.py)

Characters are drawn in code from a `Look` (the user chose this over generated sprite art). New `Look` fields
must default to "off", so that every existing character draws exactly as before: compare
`python -m newsroom.sprites --sheet` before and after. Adding a field changes `hash(look)`, which sets each
guest's blink and gesture timing, so fix `_beat` to a constant before comparing the images.
Art (backdrops, looks) is shown to the user on a contact sheet and approved before it is committed.

## Recording

OBS records the station's window, and its sound through VB-Cable: the station plays into "CABLE Input"
(`audio_device` in config.toml, or `--audio-device`), and OBS records an Audio Input Capture of "CABLE Output".
A driver reinstall gives the cable new device IDs and can leave both pointing at nothing, so after a
recording check the log for `audio: no output called` and the file with `ffmpeg -af silencedetect`.
