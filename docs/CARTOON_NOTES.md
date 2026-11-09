# Cut-out cartoons: where they stand

Notes from the 2026-11-09 review of "Gully and the Chip Lift" (take 3, `data/cartoons/gully/gully-and-the-chip-lift-3`).
The user's verdict on the re-render: "it's definitely better". This is the list to think from.

## What was fixed on 2026-11-09

| Fault in the earlier render | What the engine does now | Where |
|---|---|---|
| Props tiny and thin-lined | A prop's drawing is shrunk to the cast's pixel scale before it is cut out, so the paper edge and outline match. Sizes raised: small 3.2 units, default 4, at most 6 wide (Gully's drawing is about 8 tall). | `kit.fit_prop` |
| A prop floating beside the wrong hand | A hold point per pose (`pose_anchors` in kit.json), and a row of puppets on the ground is spread until nobody overlaps. | `Kit.anchor`, `writer._spread` |
| A prop jumping into a hand | A taken prop travels there over six frames. | `layout.plan` (`carry`) |
| No way to put a prop down | A holder's `drop` lets go: onto a spot within 4.5 units, else it falls and bounces; value "off" and it is gone (eaten). | `Actor.off_at`, `off_out` |
| Rope loop left behind | The loop and the rope's end follow the puppet every frame. | `layout.plan`, `blender_play.rope` |
| Hanging from nothing | A puppet spun 180 hangs from a rope that runs up out of the shot. | `Rope.up`, `writer.stage` |
| Standing in mid-air | "Raised" is the nearest named spot on the backdrop, or the ground. Whatever is on a spot moves with the backdrop. | `places/spots.json`, `writer.stage` |
| A crate sliding off sideways | A `drop` beat for props, and a thrown prop flies in an arc. | `layout._card` |
| Heads cropped, close-ups of feet | A medium or close shot takes in whole any neighbour it would cut through, keeps heads in, and shows a hanging puppet whole. Tilts are now a push or a pull. | `layout.plan` (`view`, `held`) |
| Frozen puppets, the same framing six times | A new stager brief: vary the framing, at least two beats in a shot over four seconds, stage only what a puppet can do. | `writer.STAGER` |

`python -m entertainment.cartoons restage <episode>` stages an episode again and keeps its script and recorded
sound. The stages it replaces are kept in `stages.K/`.

## Known faults still in the Chip Lift

- **Shot 3:** the push-in onto Gully slides past Biscuit and cuts through her for a moment.
- **Shots 11 and 12:** Gully on the chip-shop sill is very large against the shop front.
- **Shot 1:** Mr Trethewey starts on the doorstep spot. The brief says people stand on marks, but the stager
  still does this now and then; the engine only refuses a spot that would put someone out of the frame.
- **Not checked:** the beats against the sound, by ear. The review was of frames, not of the film playing.

## Things worth thinking about

### Scale between the cast and the backdrops
The puppets are foreground giants: Gully stands 10 units and the chip shop's door is about 4. That is why only
foreground features can be spots (the harbour beach, place 1, has none) and why Gully looks wrong on the sill.
Three ways out, each a different amount of work:
- Paint the backdrops with a bigger, closer foreground (a sill, a wall top or a rail at puppet scale).
- Give a spot its own scale, so a puppet on a far wall is drawn smaller.
- Keep perching for props only, and have Gully land beside things.

### Movement the puppets don't have
The stager is told to play missing business as a lean, a hop or a turn. The ones the scripts keep asking for:
- pointing (Gully has `wave`, which reads as a wave);
- eating or pecking (a head-down pose, and a chips drawing with fewer chips);
- looking up or down (Gully has a `down` face; Biscuit has none);
- Biscuit doing anything but sitting (her walk exists; a paw swipe and a yawn would carry a lot of deadpan).
Each is one Qwen drawing per pose, then `cartoons kit gully <who> --draw`.

### Props
- A prop has one drawing. A bucket on its side, an empty chip paper or a broken crate would each be a second
  pose of the prop's kit, which the engine already supports for characters.
- A held prop always hangs upright from its grip. It does not tip when the holder leans.
- Props never go behind anything on the backdrop (a parcel "in" the hatch sits in front of it).
- cone, hook, sandwich and feather were drawn before the new sizing. `fit_prop` refits one when an episode's
  `props.json` names it with the look it was drawn from.

### Staging and camera
- A move's two ends each frame their half of the shot, but nothing stops the move from cutting through a
  neighbour on the way (shot 3). Either both ends keep the same neighbours, or the cut becomes two shots.
- There is no depth: everyone stands on one line. `Actor.depth` exists and the writer never uses it, so
  nobody walks behind anybody.
- The stager works eight shots at a time and can't see the picture. A check after staging (does the shot's
  action appear in its beats, is the prop it mentions in frame) would catch the frozen and empty shots
  before a render.

### Sound against picture
- Effects are timed by the writer against the lines, and the stager times beats the same way, but the two are
  written in separate calls. A `drop` and its "clang" can drift apart.
- Off-screen lines play over whoever is on screen. Nothing makes that character react when the line lands.

## How to look at a change quickly

```bash
uv run python -m entertainment.cartoons stills data/cartoons/gully/<episode> --engine cutout
```

```bash
uv run python -m entertainment.cartoons render data/cartoons/gully/<episode> --engine cutout
```

```bash
uv run python -m entertainment.cartoons assemble data/cartoons/gully/<episode>
```

Stills are frame 1 only, and a held camera frames the whole shot, so a still can look loose. All 26 shots
render in about 8 minutes of Blender with no GPU. `render` only replays a shot whose layout, sound or pieces
are newer than its video: touch `sceneNN.layout.json` after an engine change that the layout doesn't show.
