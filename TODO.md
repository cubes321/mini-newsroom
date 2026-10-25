# To do

Roughly in the order we expect to tackle them. Done items move to the
bottom with the date.

## Art

- [ ] **Backdrop art.** The mechanics are done (see Done). Next is real art
  for the 24 locations plus `studio_wide` and `weather_wall`, dropped into
  `assets/backdrops/` following the rules in its README. Candidate pipeline:
  ComfyUI with a pixel-art model once the GPU is free (img2img from
  `--bake` templates), then hand clean-up. Night variants (`<id>_night.png`)
  are worth doing by hand for the busiest places.
- [ ] Studio sets still to come: the interview set (with studio interviews,
  below), a breakfast sofa set, a sports corner; bumper and filler cards in
  the same style as the new art.
- [ ] Optional parallax: two layers per backdrop.
- [ ] Real character sprites for the three presenters and a guest set,
  keeping the `draw_character` signature (idle / talking / gesture states).

## Content

- [ ] Local adverts (15–30 s) for the town's businesses; double as evergreen filler.
- [ ] Tides and ferry times from a deterministic fake tide table, not the model.
- [ ] Vox pops and studio interviews using the guest mechanism.
- [ ] **Early-evening magazine** (19:00–20:00 in `schedule.SCHEDULE`; the
  news stands in until it exists) in the spirit of the BBC's *Nationwide*:
  features rather than headlines, `light=True` like breakfast. Quirky local
  items, a consumer slot, a resident in the studio on `studio_interview`, and
  a filmed piece introduced at the big-picture wall. Needs studio interviews.
- [ ] Breakfast extras: tides and adverts on *Morning Tide*; a guest in the
  sofa armchair (the `guest` mark is free).
- [ ] Schedule: a late bulletin, and whether specials (or later documentaries)
  get their own scheduled slots rather than only after news bumpers.
- [ ] Breaking news: pre-empt at a line boundary with a sting; driven by the
  editor or the tip-line.
- [ ] Viewer tip-line: a text file the producer reads and hands to the next bulletin.
- [ ] Sport: a fourth presenter and the Tidewater Stadium.
- [ ] The 15–30 minute documentary: specials plus a research step over the
  town's own archive (`world.search_archive`), more sections, archive "footage".
- [ ] Optional real-weather hook mapping the user's city onto Port Wexley.

## Engineering

- [ ] Evergreen pool: pre-bake idents, "coming up" promos and notices in idle
  time so filler is never a bare card.
- [ ] Lock around world state so more than one worker is safe.
- [ ] Give section writers the thread's dates and beats (the editor already
  sees them) to keep timelines straight.
- [ ] Guest casting: gender hint is in; consider age/accent hints and a wider voice pool.
- [ ] LM Studio provider: verify end to end when the GPU is free; tune the
  9B model's prompt compliance.
- [ ] Leave it on overnight and read the stats (now with the overnight
  test card, repeats and the editor working through the night).
- [ ] Field reports often fail validation once: Miles writes a line over the
  900-character cap. Raise the cap or ask for shorter lines.
- [ ] 06:00 grades as dusk, so breakfast field reports in the first hour look
  flat grey on the art (the dusk-grade fix, under Art, would cure it).

## Housekeeping

- [ ] Decide on a licence (none at present; MIT is the usual choice).
- [ ] Decide whether the baked placeholder WAVs should stay in the repo.

## Done

- 2026-10-25 Day-parts, part 1: `schedule.py` with a normal day (overnight test
  card and repeats, *Morning Tide* breakfast on the sofa with Rosie Treloar and
  Jonah Pike, the news, the magazine slot), per-show casts and schemas, lighter
  breakfast weighting with a big-running-story exception, `--clock HH:MM`.
- 2026-10-24 Milestone 1: looping broadcast, Kokoro voices, Pygame scenes.
- 2026-10-24 Config-driven providers; Kimi via Moonshot.
- 2026-10-24 Special reports, resumable stages, editor.
- 2026-10-24 Story bible: cast, thread arcs, archive, story desk.
- 2026-10-24 Public GitHub repo with README and screenshots.
- 2026-10-25 Studio shots: an anchor close-up cut into bulletins, and a big-picture
  wall (the weather wall showing the location) for field-report and special handovers.
- 2026-10-25 Backdrop system: 24 writer-selectable locations (town and
  countryside) plus studio sets, PNG-or-placeholder loading, day/dusk/night
  and weather grading, animated water and weather, contact sheet and bake tools.
