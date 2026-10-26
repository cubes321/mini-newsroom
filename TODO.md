# To do

Roughly in the order we expect to tackle them. Done items move to the
bottom with the date.

## Art

- [ ] **Night variants** for the other exteriors (village and residential_street
  would gain most). Harbour, high street and Town Hall are done; make the rest
  the same way (Qwen-Image-Edit with the ref-latent fix, contact sheet first).
- [ ] Re-fit positions set for the placeholders to the art: the lighthouse
  beam origin, the `WATER` shimmer rectangles (the slipway's top strip), and
  the crane and drill tower behind the clock box.
- [ ] Studio sets still to come: a sports corner; bumper and filler cards in
  the same style as the art.
- [ ] Optional parallax: two layers per backdrop.
- [ ] More guest costumes in `sprites.COSTUMES` as new roles turn up (the
  first match on a role word wins), and perhaps gesture states for presenters.

## Content

- [ ] Ad breaks inside *Morning Tide*, *Coastwide* and *The Last Ferry* (adverts
  air only in gaps now): an ad-break item in the running orders that the
  producer plans around.
- [ ] *The Last Ferry*: its own set (a late-night desk and couch, made in
  ComfyUI with a contact sheet) to replace the interview set with the lights
  down; perhaps a house band sting and a second, shorter guest.
- [ ] Breakfast extras: a guest in the sofa armchair (the `guest` mark is free).
- [ ] Breaking news from the story desk or the editor (now tip-line only),
  and a follow-up field report from Miles once a breaking story is confirmed.
- [ ] A model-planned running order for the magazine and the talk show (a
  theme and a topic per item) on top of the fixed hour orders.
- [ ] Schedule: whether specials (or later documentaries) get their own
  scheduled slots rather than only after news bumpers.
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
- [ ] `record_aired` for a special runs when it is finished, not when it airs, so
  the archive says it aired early. Moving it means a world write from the main
  thread (wait for the world-state lock).
- [ ] Kimi sometimes writes a spoken line over 900 characters (Miles) and the
  script fails validation once; the retry usually works. Status notes are now
  clipped on parse (`models._clip`); spoken lines aren't, since cutting speech
  mid-sentence is worse than a retry. (Kimi doesn't get the JSON schema
  enforced; `writers._keys_hint` spells out the keys, and the schemas accept
  `speaker_id`, per-line guest details and "female"/"male".)

## Housekeeping

- [ ] Decide on a licence (none at present; MIT is the usual choice).
- [ ] Decide whether the baked placeholder WAVs should stay in the repo.

## Done

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
