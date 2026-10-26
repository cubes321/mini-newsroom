# To do

Roughly in the order we expect to tackle them. Done items move to the
bottom with the date.

## Art

- [ ] Re-fit positions set for the placeholders to the art: the lighthouse
  beam origin, the `WATER` shimmer rectangles (the slipway's top strip), and
  the crane and drill tower behind the clock box.
- [ ] Studio sets still to come: a sports corner; bumper and filler cards in
  the same style as the art.
- [ ] Better station audio, when the user can listen: the four bumpers (a synth sting
  and the lead's spoken ident), the breaking sting and the music bed are code-made
  placeholders in `assets/` (`assets.py`). A file dropped in under the same name
  replaces one; the placeholders stay in the repo until then (decided 2026-10-26).
- [ ] Optional parallax: two layers per backdrop.
- [ ] More guest costumes in `sprites.COSTUMES` as new roles turn up (the
  first match on a role word wins), and perhaps gesture states for presenters.

## Content

- [ ] *The Last Ferry*: perhaps a house band sting and a second, shorter guest.
- [ ] Breakfast extras: a guest in the sofa armchair (the `guest` mark is free).
- [ ] Breaking news from the story desk or the editor (now tip-line only),
  and a follow-up field report from Miles once a breaking story is confirmed.
- [ ] A model-planned running order for the magazine and the talk show (a
  theme and a topic per item) on top of the fixed hour orders.
- [ ] Schedule: whether specials (or later documentaries) get their own
  scheduled slots rather than only after news bumpers.
- [ ] Sport: a fourth presenter and the Tidewater Stadium.
- [ ] Documentary follow-ups: give the writers and the story desk what documentaries
  established (`world.documentaries`), a repeat of the night's documentary in the
  overnight block, and the documentary's own presenter for history pieces.
- [ ] Optional real-weather hook mapping the user's city onto Port Wexley.

## Engineering

- [ ] Evergreen pool: pre-bake idents, "coming up" promos and notices in idle
  time so filler is never a bare card.
- [ ] Give section writers the thread's dates and beats (the editor already
  sees them) to keep timelines straight.
- [ ] Guest casting: gender hint is in; consider age/accent hints and a wider voice pool.
- [ ] LM Studio provider: thinking is off with `reasoning_effort: "none"` and
  the local bench is done (qwen3.6-35b-a3b the most coherent, gemma-4-26b-a4b
  the fastest, qwen3.8-flash-next the best writer but about 15 s a script).
  Still to do: an end-to-end run through the app's own provider config rather
  than a rerouting script.
- [ ] Hybrid routing as config: live segments on LM Studio, the story desk,
  editor and specials on Kimi k3. A one-hour trial with a scratchpad reroute
  ran 93 jobs cleanly; sofa chats took about 27 s on qwen3.8 (Kokoro competes
  for the CPU), and the back office would cost about $0.9 a night on k3.
- [ ] Try DeepSeek (needs credits and `DEEPSEEK_API_KEY`): `deepseek-flash` for
  live with `thinking = { type = "disabled" }`, `deepseek-v4-pro` for the desk,
  editor and specials (240 s, `max_retries = 0`). Run the bench prompts first,
  then a `--log-llm` night. It's about 3–7× cheaper than Kimi, and half price
  off-peak (outside 01:00–04:00 and 06:00–10:00 UTC on weekdays).
- [ ] Claude on the `anthropic` route. Benched 2026-10-26 on the Kimi bench
  prompts (the route now takes `thinking` and `effort` from `extra_body`, plus
  timeout and retries): Sonnet 5.5 passed 20/20 and writes at least as well as
  Kimi, with real quotes and jokes, and its story desk moves stories on instead
  of restating the next step; 5 s live, 7 s for the desk with thinking. Haiku 5.5
  wrote lively live scripts (12/12, 3.5 s; one empty headline), but its story
  desk listed more than 4 `people` (now fixed: the anthropic path shares the
  validation retry and the desk prompt states the limit, so it passes first
  time), and with thinking off its editor re-commissioned the aired "Same Ink"
  special both times, so keep Haiku off the editor. Claude counts about twice
  Kimi's input tokens for the same prompt (the schema goes into the prompt).
  `claude_haiku` (live) and `claude_sonnet` (desk, editor, specials) are the
  routes since 2026-10-26, with the story desk every 30 minutes
  (`plan_every_s = 1800`, 48 plans a day), until DeepSeek is benched. Estimated 24 h: about
  $3.40–4.35 on that mix against $8–9.50 on Kimi. The story desk is the biggest
  item on both (72 plans a day at `plan_every_s = 1200`, about $2 on Sonnet);
  hourly plans would take Claude's day to about $2.10–3.00. Next: a `--log-llm`
  day on Claude for real costs, then the DeepSeek bench to compare. The back office could use
  the Batch API at half price.
- [ ] Price the calls the app abandons. Since 4ba630a a timeout is already a row
  in the `--log-llm` file (with its error) and a `failed` call in LLM USAGE, but
  with no token counts: the reply never arrives, yet providers bill it in full.
  On the 2026-10-25 night Kimi billed 77 k3 calls ($3.18) where the log showed 23
  (each desk timeout was sent twice by the SDK retry; k3 now has
  `max_retries = 0`). Left to do: an estimate for those rows (prompt size, and
  max_tokens as the ceiling), or a check against the provider's dashboard.
- [ ] Kimi sometimes writes a spoken line over 900 characters (Miles) and the
  script fails validation once; the retry usually works. Status notes are now
  clipped on parse (`models._clip`); spoken lines aren't, since cutting speech
  mid-sentence is worse than a retry. (Kimi doesn't get the JSON schema
  enforced; `writers._keys_hint` spells out the keys, and the schemas accept
  `speaker_id`, per-line guest details and "female"/"male".)

## Done

- 2026-10-26 Fixes from the first look at Claude on screen: a headline, location or strap can't
  be empty (Haiku once sent all three blank, and "Live from" aired bare); the news bulletin is
  cast as the anchor and Miles only, and its close-up is cut to on Dana's own lines only (Gordon's
  and Miles's voices had come out of her mouth); a headline too long for the strap drops to the
  8 px font and is cut at a word with an ellipsis (the old cut never added one); the briefing's
  threads rotate (of the day's ties, the one followed up least today first: the cannery ghost tour
  had led six of nine bulletins); the news has the weather once a loop (about every ten minutes);
  t016's "Gordon Pell turns forty" beat and headline were scrubbed from the real town.
- 2026-10-26 The documentary, part 2: archive footage. Archive entries now record their
  cache key (older ones are matched by their text, an exact prefix of the segment's).
  The research stage offers the outline up to eight clips (one line each: a guest's
  quote, or else Miles in the field, 3–45 s); the outline places up to three, one per
  section; the section is written around it, and the clip's audio is copied into the
  documentary's own files. It airs black and white, tagged ARCHIVE, captioned with the
  speaker and the date.
- 2026-10-26 The nightly documentary, part 1 (`documentary.py`): fifteen minutes, *Port
  Wexley Stories*, once a day on a long-running thread or the town's history, chosen by
  the documentary editor from 18:00. A research stage writes notes from the archive (every
  piece on the thread plus a keyword search: a dated timeline marked on record or
  background, people, details, open questions) that the outline (6–10 sections) and each
  section keep to. Voiced ten lines a stage. It airs at the first news bumper from 21:00,
  within the hour, never at a special's break; its canon goes into `world.documentaries`.
- 2026-10-26 MIT licence (`LICENSE`, `pyproject.toml`, README).
- 2026-10-26 Art: *The Last Ferry*'s own set (`studio_late`, a late-night desk and
  couch) and night art for eleven more exteriors (village, residential_street,
  police_station, fire_station, seafront, lighthouse, lifeboat_station, stadium,
  market, cannery, loading_dock), approved on contact sheets; 14 exteriors now have
  their own night art and the other 8 keep the tint on purpose.
- 2026-10-26 A lock around world state (`World.lock`, an RLock taken by every World
  method that reads or changes shared state, and by `save()` for its snapshot), so
  `--workers N` works: one worker at a time reads the tip-line and does the idle work,
  TTS runs one line at a time, and a guest's second part waits for the first. A special
  is archived when it airs (on the main thread, under the lock), not when it is finished;
  the world is saved once more at exit. Without the lock, four threads adding people and
  threads gave dozens of duplicate ids every time.
- 2026-10-26 Ad breaks in *Morning Tide*, *Coastwide* and *The Last Ferry*: `ad_break`
  items in the running orders (before breakfast's headlines, between the magazine's
  blocks, between a talk-show guest's two parts), filled with two adverts from the pool
  as they air. The producer counts a guest's break as part of the guest's run and never
  closes on it.
- 2026-10-26 No frame of test card at a join: when a segment ends, `Player.update` starts
  what follows in the same tick. A presenter can't become one of the people
  (`ensure_person` returns None; the desk skips them), `load()` removes any that did
  (Gordon Pell as p010, credited with 111 mentions), and person ids count on from the
  highest used.
- 2026-10-26 Prompt caching on the Claude route: the top of every briefing (town,
  presenters, public figures, now listed in a fixed order) is cached for an hour
  together with the system prompt and schema (`llm.CACHE_BREAK`, `cache_ttl` per
  provider). Live scripts read 1,800–2,300 cached tokens of about 3,600–4,600, and the
  last four sections of a special 1,750 of 3,600. Cache reads and writes are on each
  call's log line and in LLM USAGE; "in" stays the whole prompt.
- 2026-10-26 Local adverts (`adverts.py`): an evergreen pool of voiced 15–30 s
  ads in `data/ads/` that the player airs when the next segment isn't ready
  (up to three in a row, then the filler card). Eight hand-written ones are
  always voiced; the model writes one every half hour in idle time, up to 40.
  Owners join the cast. `python -m newsroom.adverts [--make]`.
- 2026-10-26 Tides and the Saltby foot ferry from arithmetic (`tides.py`,
  `python -m newsroom.tides`): a semi-diurnal tide about 50 minutes later each
  day with a spring-neap cycle, and a half-hourly foot ferry across the Grey
  estuary (last one 23:15) that can't cross near low water or in a storm or
  fog. Weather, breakfast and late-show scripts are given the day's times.
- 2026-10-26 An empty story-desk plan (none of the round's threads) is asked
  for once more, then left for the next round instead of being stamped done.
- 2026-10-26 People on location take its light (`backdrops.person_light`: half
  the backdrop's time-of-day and weather grade, as if lit by the crew), and the
  late show's guests sit in its lights-down look.
- 2026-10-26 A guest's caption is the role today's script gives them, also for
  a presenter booked as a guest (Gordon on his ghost tours).
- 2026-10-26 Refined code-drawn characters (`sprites.py`): a `Look` per
  presenter from agreed descriptions (hair, facial hair, glasses, clothes, an
  accessory), outlines, three-quarter faces that mirror with `facing`, and a
  look for every guest from their name, voice and role (`guest_look`: the
  voice decides whether they read as a woman or a man, and role words dress
  them, from a firefighter's stripe to a mayor's chain).
  `python -m newsroom.sprites --sheet out.png`. Generated PNG sprites were
  tried first and set aside: the blocks suit the backdrops better and can be
  varied for any guest.
- 2026-10-26 LM Studio thinking turned off with `reasoning_effort: "none"`
  (`enable_thinking` is ignored); local models benched against Kimi.
- 2026-10-26 The thread cap drops closed threads first and never an open one
  (a template smoke run had evicted ten real threads); `--world`, `--cache`
  and `--scratch` keep test runs off the real town.
- 2026-10-26 Specials have their own cache key (a restarted slot number made
  "Baker's Petition" replay the aired "Same Ink, Same Harbour"), honour
  `.aired`, air after the test card overnight so the editor doesn't idle all
  night, and retry a failed stage once.
- 2026-10-26 Story desk in batches of 8 threads, a 240 s k3 timeout with no
  SDK retry (each timeout had been billed twice), token counts per call and
  LLM USAGE totals, full call logs with `--log-llm`.
- 2026-10-26 First overnight run (22:28–07:33): 525 segments and no filler.
  It found the story-desk timeouts, the specials bugs and breakfast repetition.
- 2026-10-26 Breakfast variety, from the first real-Kimi morning (61 sofa chats,
  the town's 155th birthday six times, ages that changed between chats): each
  sofa chat is told this morning's sofa headlines, how the earlier chats on its
  angle began, and that an anniversary, birthday, age or date said once is
  settled. Overnight repeats skip breakfast segments (`Show.repeats_overnight`).
  First unit tests: `uv run pytest` (bare `unittest discover` skips
  `tests/conftest.py`, so it doesn't redirect the town to a temp dir).
- 2026-10-25 Breakfast runs a pattern with briefs handed out in turn (twelve
  sofa angles, six report angles), headlines that always lead with the big
  story, and a goodbye before the news.
- 2026-10-25 The producer's planning clock is worked out each tick from what is
  really queued; the old per-slot retime double-counted drift and ran an hour
  ahead in a real run, signing the magazine off at 19:32.
- 2026-10-25 Bulletins lead with a story for two hours after it broke as
  breaking news (as the follow-up of its own thread); breaking news always
  opens a new thread; status notes are clipped instead of failing validation.
- 2026-10-25 Thread ids count on from the highest used: with the list capped at
  40, every new thread had been getting `t041`, and follow-ups landed on the
  wrong story. The ten duplicates in `data/world.json` were renumbered
  `t042`–`t050`.
- 2026-10-25 The cache key includes a slot's running-order part and brief, so a
  restart can't replay a slot planned another way.

- 2026-10-25 Night art for the harbour, high street and Town Hall
  (`<id>_night.png`): lit windows, shop fronts, lamps, the clock face and boat
  lights, from Qwen-Image-Edit 2511 with the reference latent at the output size
  (the stock graph zoomed by 1-4 px). MOSS Edit HQ v4 kept the layout too, but
  went saturated blue and left the clock and shop fronts dark.
- 2026-10-25 Breaking news and the viewer tip-line: lines in `data/tipline.txt`
  (`python -m newsroom.tipline "..."`) go to the next bulletins as viewer tips;
  `BREAKING:` lines interrupt whatever is on at the next sentence, with a sting
  and Dana at the news desk, then the programme resumes. The story broke today
  is the light shows' big running story.
- 2026-10-25 Hour-long running orders for *Coastwide* and *The Last Ferry*: a
  written-out order with a brief per item, the big story only at the top, two-part
  guests on the talk show, and a sign-off before the next show.
- 2026-10-25 Dusk grade: a sunset tint (purple sky to an orange horizon, violet
  water) for art without its own dusk picture; fixes breakfast's first hour too.
- 2026-10-25 Finished specials survive a restart and air once (`<hash>.aired`).

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
