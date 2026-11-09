# Cut-out cartoons: where they stand

Notes on "Gully and the Chip Lift" (`data/cartoons/gully/gully-and-the-chip-lift-3`), reviewed and rebuilt
twice on 2026-11-09. The user's verdict on the first rebuild: "it's definitely better". They then asked for
another attempt that took in the "things worth thinking about" below. That attempt is `episode.mp4`; the one
before it is kept beside it as `episode.attempt2.mp4`. The script and the recorded sound are the same in both.

## First rebuild: the faults that were fixed

| Fault in the earlier render | What the engine does now | Where |
|---|---|---|
| Props tiny and thin-lined | A prop's drawing is shrunk to the cast's pixel scale before it is cut out, so the paper edge and outline match. Sizes: small 3.2 units, default 4, at most 6 wide (Gully's drawing is about 8 tall). | `kit.fit_prop` |
| A prop floating beside the wrong hand | A hold point per pose (`pose_anchors` in kit.json), and a row of puppets is spread until nobody overlaps. | `Kit.anchor`, `writer._spread` |
| A prop jumping into a hand | A taken prop travels there over six frames. | `layout.plan` (`carry`) |
| No way to put a prop down | A holder's `drop` lets go: onto a spot in reach, else it falls and bounces; value "off" and it is gone (eaten). | `Actor.off_at`, `off_out` |
| Rope loop left behind | The loop and the rope's end follow the puppet every frame. | `layout.plan`, `blender_play.rope` |
| Hanging from nothing | A puppet spun 180 hangs from a rope that runs up out of the shot. | `Rope.up`, `writer.stage` |
| Standing in mid-air | "Raised" is the nearest named spot on the backdrop, or the ground. Whatever is on a spot moves with the backdrop. | `places/spots.json`, `writer.stage` |
| A crate sliding off sideways | A `drop` beat for props, and a thrown prop flies in an arc. | `layout._card` |
| Heads cropped, close-ups of feet | A medium or close shot takes in whole any neighbour it would cut through, keeps heads in, and shows a hanging puppet whole. Tilts are now a push or a pull. | `layout.plan` (`view`, `held`) |
| Frozen puppets, the same framing six times | The stager's brief: vary the framing, at least two beats in a shot over four seconds, stage only what a puppet can do. | `writer.STAGER` |

## Second rebuild: the things worth thinking about

| The point | What was done | What is left |
|---|---|---|
| **Scale.** The cast were foreground giants, so Gully on the chip-shop sill was as tall as the shop front. | Each spot has a scale (`spots.json`: x, y, scale). Whoever is on a spot is drawn that small and sits behind the near cast; a flight to a spot shrinks on the way, a prop put down on one shrinks into place, and a camera on a far puppet closes in to match. The harbour wall is a spot again (0.3). | The cast on the ground are still large against the buildings behind them. Only repainted backdrops with a nearer foreground would change that. The scales are my judgement by eye. |
| **Movement.** Scripts asked for pointing, eating and looking that no puppet had. | New drawings: Gully `point` and `peck`, an `up` face for both, Biscuit `paw` and `nibble`, and a `down` face. | Biscuit's `paw` and `nibble` and Gully's `peck` are whole new drawings, so they cannot talk. The kit sheets have not been approved. |
| **Props tipping.** A held prop hung dead upright. | A held prop tips with its holder's lean and scales with them; a prop spun 90 lies on its side on the ground. | Still one drawing per prop (no empty chip paper, no broken crate). Props never go behind part of the backdrop. A prop is kept off any spot smaller than 0.4, where it was a speck. |
| **A camera move cutting through a neighbour.** | A move that would slice somebody on the way is made inside the looser of its two framings. | |
| **No depth.** | Whoever walks past somebody passes behind them (`Actor.depth`, set by `writer.stage`). | Only walkers. Nobody stands behind anybody. |
| **A staging nobody checks.** | `writer.problems`: a prop the action is about left off the stage, somebody seen left out, a long shot with fewer than two beats. A shot with a problem goes back to the stager once, with what was wrong. | It reads the words, not the picture. |
| **Sound and picture timed apart.** | The stager is given each shot's effects with their times and told to time the beat that makes a sound at that sound. | Nothing checks that it did. |
| **Nobody reacts to an off-screen line.** | At every off-screen line and effect, whoever is on stage, silent and not already moving gives a small start (`layout.plan`, `cues`). | The start is the same every time. A flinch pose would be better. |

## Known faults in the current episode

- **Shot 13 and 14:** the crate is "on the edge of the wall" in the script and on the sand beside Gully in the
  picture, because the wall is too far off for a prop. When he shoves it, it is knocked over and flung out
  of the side of the shot.
- **Shot 20:** Biscuit nibbles at a crumb drawn into her pose while the chips sit beside her.
- **Shot 10:** Dot stands alone in a wide street with the bucket small on the stall behind her.
- **Not checked:** the film played with its sound. Both reviews were of frames.

## How to look at a change quickly

```bash
uv run python -m entertainment.cartoons restage data/cartoons/gully/<episode>
```

```bash
uv run python -m entertainment.cartoons stills data/cartoons/gully/<episode> --engine cutout
```

```bash
uv run python -m entertainment.cartoons render data/cartoons/gully/<episode> --engine cutout
```

```bash
uv run python -m entertainment.cartoons assemble data/cartoons/gully/<episode>
```

- `restage` keeps the script and the sound and writes every shot's stage afresh (it needs the Anthropic key;
  about two minutes). The stages it replaces are kept in `stages.K/`.
- Stills are frame 1 only, and a held camera frames the whole shot, so a still can look loose.
- All 26 shots render in about 8 minutes of Blender with no GPU. `render` only replays a shot whose layout,
  sound or pieces are newer than its video, and `relayout` leaves a layout that hasn't changed alone: touch
  `sceneNN.layout.json` after an engine change that the layout doesn't show.
- A new pose is one entry in the puppet's `kit.json` (`variants`, `poses`, and `pose_anchors` for where it
  holds things), then `cartoons kit gully <who> --draw` with ComfyUI running.
