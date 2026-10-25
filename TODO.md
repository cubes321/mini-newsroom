# To do

Roughly in the order we expect to tackle them. Done items move to the
bottom with the date.

## Art

- [ ] **Dusk grade.** On PNG art, dusk is a whole-picture multiply, so blue
  skies go flat grey instead of turning to sunset. Either a vertical gradient
  grade for exteriors (purple at the top, orange towards the horizon) or
  `<id>_dusk.png` files for the busiest places. This also fixes breakfast's
  first hour, since 06:00 grades as dusk.
- [ ] **Night variants.** Lit windows and lamps exist only on the placeholders;
  hand-made `<id>_night.png` for the harbour, high street and Town Hall first.
- [ ] Re-fit positions set for the placeholders to the art: the lighthouse
  beam origin, the `WATER` shimmer rectangles (the slipway's top strip), and
  the crane and drill tower behind the clock box.
- [ ] Studio sets still to come: a sports corner; bumper and filler cards in
  the same style as the art.
- [ ] Optional parallax: two layers per backdrop.
- [ ] Real character sprites for all eight presenters (Dana, Gordon, Miles,
  Rosie, Jonah, Pat, Clive, Vincent) and a guest set, keeping the
  `draw_character` signature (idle / talking / gesture states).

## Content

- [ ] Local adverts (15–30 s) for the town's businesses; double as evergreen filler.
- [ ] Tides and ferry times from a deterministic fake tide table, not the model.
- [ ] *The Last Ferry*: its own set (a late-night desk and couch, made in
  ComfyUI with a contact sheet) to replace the interview set with the lights
  down; perhaps a house band sting and a second, shorter guest.
- [ ] Magazine and talk-show loops repeat their format every 6–8 minutes, so
  an hour sees the same shape (and often the same big story) several times.
  Consider longer patterns, or the hour as one planned running order.
- [ ] Breakfast extras: tides and adverts on *Morning Tide*; a guest in the
  sofa armchair (the `guest` mark is free).
- [ ] Schedule: whether specials (or later documentaries) get their own
  scheduled slots rather than only after news bumpers.
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
- [ ] Kimi overruns string caps and fails validation once (the retry
  usually works): Miles's lines over 900 characters, `thread_status` over
  160, the story desk's `note` over 200. Truncate on parse instead, or raise
  the caps. (Kimi doesn't get the JSON schema enforced; `writers._keys_hint`
  spells out the keys, and the schemas accept `speaker_id`, per-line guest
  details and "female"/"male".)
- [ ] A presenter booked as a guest (Gordon on his ghost tours) is captioned
  with their presenter role; use the script's `guest_role` instead.
- [ ] 06:00 grades as dusk, so breakfast field reports in the first hour look
  flat grey on the art (the dusk-grade item under Art cures it).

## Housekeeping

- [ ] Decide on a licence (none at present; MIT is the usual choice).
- [ ] Decide whether the baked placeholder WAVs should stay in the repo.

## Done

- 2026-10-25 Day-parts, part 2: studio interviews (in the news every third
  loop, on `studio_interview`), *Coastwide* the early-evening magazine (Pat
  Holloway and Clive Ashdown: links, filmed features, studio guest, vox pops,
  consumer slot) and *The Last Ferry* late-night talk show (Vincent Marr:
  monologue and guest chats, a night look on the interview set), and the
  23:00 late news. Guests join the cast, aren't rebooked straight away, and a
  presenter can be a guest.
- 2026-10-25 Day-parts, part 1: `schedule.py` with a normal day (overnight test
  card and repeats, *Morning Tide* breakfast on the sofa with Rosie Treloar and
  Jonah Pike, the news, the magazine slot), per-show casts and schemas, lighter
  breakfast weighting with a big-running-story exception, `--clock HH:MM`.
- 2026-10-25 Studio sets: the interview set and the breakfast sofa, with
  character marks and art.
- 2026-10-25 Backdrop art: ComfyUI pixel art for all 24 locations plus
  `studio_wide` and `weather_wall`, approved on contact sheets.
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
