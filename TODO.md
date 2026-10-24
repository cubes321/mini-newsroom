# To do

Roughly in the order we expect to tackle them. Done items move to the
bottom with the date.

## Art

- [ ] **Backgrounds.** Redo the newsroom background and build a proper library
  of standard backdrops to replace the programmatic placeholders in
  `scenes.py`:
  - **Studio set**: main desk wide shot, anchor close-up, weather wall,
    interview two-shot, a corner for a future sports desk, plus the
    bumper/ident and filler cards in the same style.
  - **Port Wexley locations**: Town Hall (exterior with the clock, council
    chamber), Harrow Street market and the winter shed, the harbour (old
    cannery, slipway, loading dock, lighthouse, lifeboat station), Tidewater
    Stadium, the park, Greymouth Academy, fire and police stations, a
    residential street, the seafront.
  - **Surrounding countryside**: farmland, the coast road and cliffs, woods,
    the estuary, a neighbouring village.
  - **Variants**: day/dusk/night and weather tints so a backdrop matches the
    broadcast clock and the last weather report.
  - Mechanics: `assets/backdrops/<id>.png` at 320×180, a registry replacing
    `BACKDROPS` in `scenes.py`, and the `Backdrop` literal in `models.py`
    grown so writers can pick from the full list. Optionally two layers per
    backdrop for a little parallax. Candidate pipeline: ComfyUI with a
    pixel-art model once the GPU is free, then hand clean-up.
- [ ] Real character sprites for the three presenters and a guest set,
  keeping the `draw_character` signature (idle / talking / gesture states).

## Content

- [ ] Local adverts (15–30 s) for the town's businesses; double as evergreen filler.
- [ ] Tides and ferry times from a deterministic fake tide table, not the model.
- [ ] Vox pops and studio interviews using the guest mechanism.
- [ ] Day-parts and a schedule table: morning show, evening news, late
  bulletin, overnight test card with repeats.
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
- [ ] Leave it on overnight and read the stats.

## Housekeeping

- [ ] Decide on a licence (none at present; MIT is the usual choice).
- [ ] Decide whether the baked placeholder WAVs should stay in the repo.

## Done

- 2026-10-24 Milestone 1: looping broadcast, Kokoro voices, Pygame scenes.
- 2026-10-24 Config-driven providers; Kimi via Moonshot.
- 2026-10-24 Special reports, resumable stages, editor.
- 2026-10-24 Story bible: cast, thread arcs, archive, story desk.
- 2026-10-24 Public GitHub repo with README and screenshots.
