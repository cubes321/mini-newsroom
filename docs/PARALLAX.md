# Parallax on location: the plan

Agreed with the user on 2026-11-03 after a trial on three backdrops. The trial's clips, layer sheet and
notes are in `E:\recordings\parallax-trial\` (`NOTE.md`), and its scripts are in
`%APPDATA%\Claude\side-session-notes\local_09ea71c9-...\parallax-trial-scripts\` (`spec.py`, `fill.py`,
`render.py`, `da2cmp.py`).

## What the trial settled

- **Rows, not layers.** Every art pixel gets a *foot row*, the screen row it stands on. A sideways camera
  move shifts it by `k * (foot - horizon)`. The ground shears row by row, and an upright thing (a boat, a
  lamp post, the van) moves as one piece at its foot's offset. A near/mid/far cut would have to slice the
  ground somewhere, and that seam slides. In this model it never opens.
- **The swing:** the bottom row moves ±5 art px on an 8 s sine, and the sky ±0.15 px. It has to be drawn
  at window resolution, because at 320×180 a slow drift steps a whole art pixel at a time.
- **People have to move with their ground.** Held still on screen, the reporter slides about 4 px against
  the quay at full swing.
- **Not much fill:** a 10 px border all round, plus the gap behind anything that stands well forward (the
  harbour's bollards, rope coil and post). Qwen-Image-Edit fills it, but only its border and hole pixels
  are kept: it redraws the rest and can shift it by a pixel.
- **Depth Anything V2 Small** (downloaded for the trial) finds the sky, the ground, the horizon and each
  object's foot row to within 0.9 px. It can't draw object outlines, so which pixels belong to which object
  stays by hand, from the art's own edges and colours.
- **It only pays where the picture has depth.** The harbour reads best; the fish quay reads through its
  puddles and manhole; Main Street, all shopfronts square to the camera on a 6 px pavement, barely shows it.

## Scope

- **In:** field reports and vox pops on the 24 exteriors (`scenes.draw_field`), for the backdrops picked in
  step 1.
- **Out, for now:**
  - Studio sets and interiors: no parallax indoors.
  - Specials: they grey the canvas for archive footage and wash it, which a backdrop drawn outside the
    canvas wouldn't get.
  - Adverts, and the weather wall's picture.

  These all keep the flat art, as does any backdrop without parallax data.
- **Behind a switch:** `[broadcast] parallax = false` until the user has watched it on air (`--parallax`
  turns it on for one run).

## Steps

### 1. Triage (art side session, about an hour)

Run DA2 Small on all 24 day exteriors and score each by depth: the spread of ground offsets, and how much
upright detail stands at different rows. Show a sheet of the 24 with their depth maps and scores. The user
picks the set, expected to be 10–14. Likely in: harbour, seafront, slipway, estuary, lighthouse,
lifeboat_station, loading_dock, fish_quay, coast_road, park, farm, quarry_field. Likely out: main_street,
town_hall, school, fire_station, police_station, residential_street.

**Done 2026-11-03** (`E:\recordings\parallax-trial\triage\`: `TRIAGE.md`, `parallax_triage.png`, `scores.json`). The
user chose the suggested 12: woods, loading_dock, lighthouse, harbour, lifeboat_station, slipway, cannery, coast_road,
seafront, farm, estuary and park. Outlining them is about 2 hours; the harbour is already done. Main Street and the
other eleven stay flat. The fish quay is built for the pilot, and whether it stays is decided after watching that.
**The lighthouse and coast road have no flat ground** (a cliff, a hillside), so the foot-row fit fails there. Their
offsets come straight from the DA2 depth per pixel (offset = 5 px × depth ÷ the bottom row's depth), with the hand
outlines only for the lighthouse tower and cottage. So the engine has to take a per-pixel offset map as well as foot
rows: store either the foot row or the offset in `<id>_feet.png`, with a flag in the README.

### 2. The engine (main session; after the session editing `scenes.py` and `player.py` has committed)

- **Data:** per backdrop, PNGs in `assets/backdrops/parallax/`:
  - `<id>_plate.png`: the art padded to 340×200, with the fill;
  - `<id>_feet.png`: the foot row per pixel, 8-bit, 0 = sky;
  - `<id>_sky.png`: the clean sky plate;
  - `<id>_sprites.png`: optional, near pieces lifted out, alpha-masked, with their foot rows in
    `assets/backdrops/README.md`.

  Night art has its own plate and fill, but shares the day's feet and sprites, since the ref-latent night
  art lines up. PNGs rather than `.npz`, so they're reviewable and fit the art contract.
- **`backdrops.layered(id, tod, wx)`:** loads the plates and grades them like the flat art (`_grade_art`;
  `_dusk_grade` with its horizon moved down by the 10 px padding). It splits each row into its pieces,
  farthest first, each carried 3 px under the nearer ones, as `render.py` does.
- **Drawing at window size:**
  - The backdrop is drawn on the screen first, at window scale (3× at 960×540), offset in window pixels.
  - Then the canvas is scaled on top of it, with a clear background where the backdrop was.
  - `scenes.present` already draws queued pictures at full size, so the layered backdrop is one more
    queued item, drawn first.
  - To keep the frame cheap, the composed backdrop is cached and rebuilt only when its offsets move by a
    whole window pixel: about 16 times a second at full swing.
- **People:** each character on location is drawn on its own small layer and offset by its own foot row
  (the reporter at 160, a resident at 156, the small figure at `FAR_Y`). The mic moves with the reporter's
  layer. Lower thirds, the ticker, the clock, the LIVE badge, the verdict card and the caller box stay put.
- **The rest of the scene:**
  - Water shimmer: shifted by its row's offset, so it rides the water.
  - Clouds: as now, since the sky is all but still.
  - Fireworks, the bonfire and the weather effects: stay on the canvas.
- **Camera:** one number per frame, a slow sine. It starts at zero and eases in on each new item, so a cut
  never jumps. It may swing wider in wind.
- **Budget:** STATS frame p99 within about 2 ms of today's, at 960×540 and at full screen. Check it before
  any art goes in.
- **Tests:** the offset maths, falling back to flat (no data, the switch off, indoors, specials), the people
  following their rows, and the fixed overlays staying fixed.

**Built 2026-11-03** (`newsroom/parallax.py`, `scenes._Layered`, `tests/test_parallax.py`). What changed from
the sketch above, and why:

- **No sky PNG.** The sky behind everything is each row's sky colour, from the art with its clouds lifted out
  (`skies.Sky.clean`, masked). `clean` itself still has the buildings in it. The clouds drift over it as on
  the flat art.
- **Pieces, not per-row pieces.** The ground is one surface, drawn in bands of rows that share a shift (one
  band at rest, about sixteen at full swing). Each upright foot is one cropped surface, drawn farthest
  first. The 3 px carry under nearer pieces is baked in when the scene is built. A scene takes about
  0.05 s to build, on a thread; the shot stays flat until it's ready.
- **The canvas becomes the overlay.** On a parallax shot, `render()` draws the scene's effects, tags, lower
  third, ticker and clock on a clear 320×180 overlay, and each person on a layer of their own.
  - `present()` draws the place at 3x, the people moved by their own feet, then only the overlay's top
    and bottom strips.
  - The real canvas still gets the whole frame, flat, so `logo.py` and the tests can read it.
  - The weather, the fireworks and the bonfire are on the overlay, so they're drawn over the people.
- **The shimmer rides the water:** it's drawn in the ground's bands. Clouds and shimmer are cached at window
  size until they move a whole canvas pixel.
- **Night stays flat** until the night art has a plate; the dusk grade takes the padding's row offset.
- **Cost**, render plus present at 960×540: flat p99 0.6–0.8 ms, parallax 1.9–2.4 ms.
- **At rest** the window is the flat picture pixel for pixel. A test holds that, as does banded against
  row-by-row drawing.
- **The pilot data:** `python -m newsroom.parallax import LAYERS.npz ID` converts the trial's harbour and
  fish quay. Inside the frame it keeps the art's own pixels wherever a near piece doesn't stand, because the
  trial's fill reached a pixel or two past the pieces. Those plates are new art (Qwen fill), so they stay
  uncommitted until the user has watched the pilot.

### 3. Pilot (main session)

**Done 2026-11-03.** A windowed `--scratch --parallax --clock 12:58` run, log
`data/day-parallax-pilot-2026-11-03.log`, recorded as `E:\recordings\2026-11-03 15-42 Quayside.mp4` (excerpt
in `E:\recordings\parallax-trial\pilot\`).
- Clean: 34 segments, no filler, no failed builds.
- The median STATS p99 was 2.3 ms, the same as the flat Quayside run on 11-02.
- On air, the fish quay's water row drifted ±7.5 px at 1080p over the 8 s period, as the engine gives it.
- The harbour wasn't on screen while recording.
- The user approved both layer sets, and they are committed. Still to judge on a later run: the harbour on
  air, and whether the fish quay earns its place.

The original step:

Convert the trial's harbour and fish quay into the PNG format and run a `--scratch` evening with the switch
on, recorded by OBS, field reports included. The user watches it, and checks the frame times in the log.
Main Street stays flat, as the comparison.

### 4. The rest of the set (art side session)

For each picked backdrop:
- DA2 suggests the horizon and the foot rows; the outlines are drawn by hand, about 5 minutes each.
- Qwen fills the border and holes: two seeds, one picked by eye.
- A 15 s clip and a layer sheet for the user's approval, in batches, like the art.

Then the night plates. Commit only approved sets, by explicit paths.

## Risks

- **Frame time** at full screen: the window-size draw and the alpha-blended canvas are new costs. Measure in
  step 2, before any art.
- **Colour masks** were the fragile part of the trial, taking three rounds of fixes found as tears or ghosts
  in single frames. The per-backdrop clip is where they're caught.
- **The art rules grow:** up to 5 px of outpaint can show at the bottom corners, so the border comes under
  the same rules as the art (`assets/backdrops/README.md`).
- **The marks:** a new backdrop's reporter mark and resident marks must stand on rows the foot map knows.
