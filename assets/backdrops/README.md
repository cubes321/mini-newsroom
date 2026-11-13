# Backdrops

Art for the places a picture can be set. The ids, names and one-line
descriptions live in `newsroom/locations.py`; the code that loads, grades
and animates them is `newsroom/backdrops.py`.

Until a file exists here, each backdrop is drawn by a programmatic
placeholder. Dropping in a PNG replaces it, with no code changes:

| File | Used for |
|---|---|
| `<id>_day.png`, `<id>_dusk.png`, `<id>_night.png` | that time of day, as drawn (weather is still graded on top) |
| `<id>.png` | all times of day; dusk and night are tinted in code |

Lookup order is the time-of-day file, then `<id>.png`, then the placeholder.

## Rules for the art

- **320×180 pixels.** The canvas is scaled up with nearest-neighbour, so draw at
  native resolution with hard pixels. Other sizes are scaled to fit, which looks worse.
- **Ground line around y 110–125.** Characters stand on it.
- **Keep the lower-left calm.** The reporter stands at x ≈ 64–116, y ≈ 86–160.
- **Overlays cover two bands:** the lower third (y 128–154, x 8–270) and the ticker
  (y 166–180). Nothing important goes there. The clock sits at the top right
  (x 276–316, y 4–16) and the LIVE badge at the top left.
- **Water** shimmers inside the rectangles listed in `WATER` in `backdrops.py`, but only
  on pixels the art itself paints as water (blue), so boats, ramps and quays drawn there
  stay still. Keep water roughly in those rectangles, or widen them (never into the sky).
- **No people, no text.** Captions are drawn live, and signs would need to change
  with the story.
- **Studio backdrops** (`studio_wide`, `weather_wall`, `studio_interview`, `studio_sofa`,
  `studio_late`, `studio_sports`, `studio_panel`, `studio_kids`, `studio_phonein`, `chamber_press`, `studio_quiz`, and Marina Row's four `marina_*`) are never tinted. The weather scene draws its map at (40, 20, 180, 120) and its side
  panel at (234, 20, 76, 124); the same screen shows a location for the big-picture
  wall shot.

## Interiors

`council_chamber`, `market_shed`, `pub` (the darts pub), and the three where Out and About reviews
(`tea_room`, `dining_room`, `village_hall`, picked by the place's kind in `outabout.INTERIORS`) have no
sky and are never graded for time of day or weather. They follow the location rules above: Meg stands at
the reporter's place on the left, an owner or a player at about (215, 156), and the review's verdict card
covers (176, 24, 136, 62) on her last line, so the place's best piece sits between them.

## Studio sets: who goes where

People are drawn by code on top of the art, so the furniture has to be where
they sit. Marks are in `MARKS` in `newsroom/locations.py` as
(x, baseline y, scale, facing). At scale 2 a person is about 52 px wide and
reaches about 74 px above their baseline.

| Set | Marks | The art needs |
|---|---|---|
| `studio_interview` | host (92, 150), guest (228, 150) | an armchair behind each mark, angled towards each other; a low table between them; a screen or the station ident on the wall between their heads |
| `studio_sofa` | host_a (122, 146), host_b (186, 146), guest (272, 150) | a two-seat sofa behind both hosts; an armchair at the guest's mark; a window onto the harbour above and behind the sofa; warm morning light |
| `studio_late` | host (92, 136), guest (228, 150) | The Last Ferry, lights already down: a desk whose top's back edge is just above the host's baseline (they sit behind it, monologue included) and a tall chair behind the shoulders; a long couch behind the guest; the harbour at night through a window between them |
| `studio_sports` | host (92, 144), guest (228, 150) | the sports corner of the main studio: a small desk the presenter stands behind (its top's back edge just above the host's baseline); a swivel chair behind the guest; the stadium on a big screen and a results board with blank rows above and between their heads; the trophy cabinet on the left, scarves on the right |
| `studio_panel` | host (58, 135), panel_1 and guest (152, 135), panel_2 (212, 135), panel_3 (272, 135) | The Panel: one long desk across the front whose top's back edge is at y 132, 3 px above all four baselines (the chair at the left end, three panellists); a name card on its front at each place; the red channel 7 ident above the chair; a wide screen with the town's skyline behind the panellists |
| `studio_kids` | host (78, 150), gully (134, 158), guest (250, 152) | Rock Pool: a sea-green wall with painted waves and bunting; a painted rock pool with a crab and a starfish, up to the right; a sandy floor from y 140; a craft table with paint pots and an egg box between Gully and the visitor. Nobody sits: Poppy and the visitor stand, Gully comes up from below frame |
| `studio_phonein` | host (92, 144), guest (228, 144) | Have Your Say: one long desk across the frame whose top's back edge is at y 141, 3 px above both baselines; the call board (six lines, a lamp and a blank strip each) on the wall between their heads; a headset on its stand on the desk between them; the red telephone and the line console at the desk's right end, past the lower third; the wall at the top right left plain for the caller's box (`scenes.CALLER_BOX`), which sits above the guest's head |
| `studio_quiz` | host (52, 156), panel_1 and guest (128, 154), panel_2 (178, 154), panel_3 (238, 158), panel_4 (288, 158) | Wexley Wits, Channel 8's pub quiz: a stage in a pub function room; Clive's lectern at the left (top at y 153), the home pair's blue table (151) and the away pair's gold one (155), each 3 px above its marks; a scoreboard ringed with bulbs, its two panels blank, above the teams; a dartboard at the right; plain wall at the top left for the darts window (`oche.BOX`); no channel 7 ident |
| `marina_kitchen` | a (96, 151), c (160, 151), b (224, 151) | Marina Row (Channel 8's soap): Queenie's kitchen; the range, nets and cork floats, a window onto the harbour at dusk, a dresser of blue-and-white plates; everyone behind the oilcloth table (top at y 148). Registered by `entertainment/marina_row.py`, not in locations.py |
| `marina_mermaid` | a (70, 151) behind the bar, b (196, 153) and c (266, 153) at the table | Marina Row: The Mermaid, the Row's pub; the back bar's bottles and optics, a window onto the Row at night, a mermaid painting; the bar counter at the front left (top 148), a pub table at the front right (150) |
| `marina_loft` | a (66, 151) behind the pass, b (200, 153) and c (268, 153) at the table | Marina Row: The Loft, the Lockwoods' restaurant; bare brick, Edison bulbs, a wide window onto the yachts at dusk, wine shelves; the steel pass at the front left (148), a table for two at the front right (150) |
| `marina_row` | a (90, 153), b (204, 153), c (262, 153) | Marina Row: the Row at dusk, lamps lit, painted for its own light (a set, so never graded); Queenie's stone net loft, the converted flats, The Loft's window, the pontoon and yachts; everyone behind the quay wall (top 150) |
| `studio_wide` | anchor (110, 134) | the desk top at about y 130, across the frame |
| `weather_wall` | presenter (270, 152) | the two screens at the rectangles above |
| `council_chamber` | host (160, 104, scale 1), guest and panel_1 (60, 140), panel_2 (276, 140), panel_3 (204, 154) | the other way round: the art came first and the marks were placed on it (approved 2026-11-01). The chair sits small in the high seat under the crest; the councillors stand in front of the horseshoe desks |
| `chamber_press` | host (84, 138) | The Chamber's press seats, from the approved `council_chamber` art: a panelled press bench across the left of the frame whose top's back edge is at y 135, 3 px above Dana's baseline; a desk microphone, a glass of water and notepads on it; an empty press chair further along; the dais, the mayor's chair and the horseshoe behind as in the chamber |

The placeholder painters in `backdrops.py` draw the furniture on these marks;
`--bake studio_interview studio_sofa studio_late studio_sports studio_panel studio_kids studio_phonein chamber_press` gives you templates with them in place.

## Parallax layers

`parallax/` holds the layers for exteriors that drift on a field shot when `[broadcast] parallax` is on
(`newsroom/parallax.py`, `docs/PARALLAX.md`). Each piece slides by how far its foot is below the horizon.

- **The art itself is unchanged.** A backdrop without layers, or a time of day whose art has no plate,
  stays flat. A backdrop with no night art of its own uses its day plate after dark.
- **Per art file** (`harbour`, `harbour_night`):
  - `<art>_plate.png`: the art padded 10 px all round (340×200), with fill behind the near pieces and in
    the border.
  - `<art>_near.png` (optional): the near pieces in their own colours (RGBA).
- **Per backdrop:**
  - `<id>_feet.png`: each plate pixel's foot as a padded row (grey, 0 = sky). Ground pixels stand on their
    own row. Where there's no flat ground (the lighthouse's cliffs, the coast road's hillside), the feet
    come from the depth model per pixel, rounded to 6-row steps so each step moves as one piece. They're
    still foot rows, so the engine reads them the same way.
  - `<id>_near_feet.png`: the near pieces' feet, the same way. One file serves the day and the night:
    a piece only exists where that art's `_near.png` has alpha, so the night's own pieces (the lantern's
    glow, the harbour's breakwater light and chimney tips, the seafront's night boat) are invisible by day.
  - `parallax.json`: the horizon row.
- **Inside the frame the plate is the art pixel for pixel**, except under a near piece. At rest the
  layered shot is the flat one.
- **Up to 5 px of the border can show** at the bottom corners at full swing, so the border follows the
  same rules as the art (no people, no text).
- **Layers are approved like the art,** from a clip and a layer sheet. The harbour and the fish quay were
  approved on 2026-11-03 after the pilot. `python -m newsroom.parallax import LAYERS.npz ID` writes them
  from a trial's layers.

## Tools

```
uv run python -m newsroom.backdrops --sheet sheet.png        # every backdrop at day/dusk/night, plus weather
uv run python -m newsroom.backdrops --bake harbour park       # write placeholders here as templates
```

Baked placeholders are only starting points (for hand clean-up or img2img),
and they take over from the painter as soon as they exist. Don't commit them
unless they've been worked on.
