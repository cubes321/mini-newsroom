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
- **Water** shimmers in the rectangles listed in `WATER` in `backdrops.py`.
  Keep water in roughly the same place, or update those rectangles.
- **No people, no text.** Captions are drawn live, and signs would need to change
  with the story.
- **Studio backdrops** (`studio_wide`, `weather_wall`, `studio_interview`, `studio_sofa`)
  are never tinted. The weather scene draws its map at (40, 20, 180, 120) and its side
  panel at (234, 20, 76, 124); the same screen shows a location for the big-picture
  wall shot.

## Studio sets: who goes where

People are drawn by code on top of the art, so the furniture has to be where
they sit. Marks are in `MARKS` in `newsroom/locations.py` as
(x, baseline y, scale, facing). At scale 2 a person is about 52 px wide and
reaches about 74 px above their baseline.

| Set | Marks | The art needs |
|---|---|---|
| `studio_interview` | host (92, 150), guest (228, 150) | an armchair behind each mark, angled towards each other; a low table between them; a screen or the station ident on the wall between their heads |
| `studio_sofa` | host_a (122, 146), host_b (186, 146), guest (272, 150) | a two-seat sofa behind both hosts; an armchair at the guest's mark; a window onto the harbour above and behind the sofa; warm morning light |
| `studio_wide` | anchor (110, 134) | the desk top at about y 130, across the frame |
| `weather_wall` | presenter (270, 152) | the two screens at the rectangles above |

The placeholder painters in `backdrops.py` draw the furniture on these marks;
`--bake studio_interview studio_sofa` gives you templates with them in place.

## Tools

```
uv run python -m newsroom.backdrops --sheet sheet.png        # every backdrop at day/dusk/night, plus weather
uv run python -m newsroom.backdrops --bake harbour park       # write placeholders here as templates
```

Baked placeholders are only starting points (for hand clean-up or img2img),
and they take over from the painter as soon as they exist. Don't commit them
unless they've been worked on.
