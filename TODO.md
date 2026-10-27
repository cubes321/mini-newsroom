# To do

Roughly in the order we expect to tackle them. Done items move to the
bottom with the date.

## Art

- [ ] Station audio follow-ups: a 44.1 kHz stereo mixer (everything plays at 24 kHz mono, so
  the music stems are exported that way; Kokoro would need resampling on load); a bed per show
  (the bed is loaded once at start); perhaps a new breaking sting (still the brass version, in
  minor; the user kept it for now).
- [ ] Optional parallax: two layers per backdrop. A big job: every backdrop is one flat picture, so
  each (24 days, 14 nights, the studio sets) needs a far layer redrawn without the foreground in
  ComfyUI and approved by eye, and it only shows when the camera moves, which no shot does yet.
- [ ] More guest costumes in `sprites.COSTUMES` as new roles turn up (the first match on a role word
  wins; on 2026-10-27 every role in the town had one but the sea-glass collector), and perhaps gesture
  states for presenters.

## Content

- [ ] Watch a real evening for what the 2026-10-27 scratch run couldn't show: a British-pronounced local
  guest on air (only heard in samples), a main guest's second part that hands over to the couch
  instead of saying goodnight (`stays_on`, added after the run), the trail and notice prompts after
  their fixes (no repeated title, notices for the public, slide lines cut at a word past 190
  characters), and a special waiting for its hour and then airing.
- [ ] Brainstorm new shows for the schedule. The news loop runs ten hours straight from 09:00 (after
  *Morning Tide*) to 19:00 (*Coastwide*): one or more daytime shows to break it up. And something mid
  evening: from 20:00 it is the news again until *The Last Ferry* at 22:00, apart from the 21:00
  documentary. Ideas to start from:
  - A morning magazine straight after *Morning Tide*, say 09:00 or 10:00: slower and longer items
    than breakfast and more homely than *Coastwide* (cookery, phone-ins, a guest on the sofa).
  - A lunchtime business show around 12:00 or 13:00: the harbour and the port trade, local firms,
    shop openings and closures, jobs, prices on the high street.
  - An investigative show in the evening, maybe 20:00: one story taken in depth over the half hour
    or hour, a reporter's own film and a studio interview that pushes back; the opposite of the
    magazine and the talk show, which are kept `light`.
- [ ] A model-planned running order for the magazine and the talk show (a
  theme and a topic per item) on top of the fixed hour orders.
- [ ] Sport: a fourth presenter and the Tidewater Stadium.
- [ ] Documentary follow-ups: give the writers and the story desk what documentaries
  established (`world.documentaries`), a repeat of the night's documentary in the
  overnight block, and the documentary's own presenter for history pieces.
- [ ] Optional real-weather hook mapping the user's city onto Port Wexley.

## Engineering

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
  hourly plans would take Claude's day to about $2.10–3.00. Measured on the
  2026-10-26 night (see Done): about $3.70 a day, about $2.80 with the editor every 30
  minutes. Next: the DeepSeek bench to compare. The back office could use the Batch API
  at half price.
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

- 2026-10-27 Art fits: the water shimmer only touches the art's own water pixels inside the `WATER`
  rects (`backdrops._water_mask`, from the day picture), so it keeps off the loading dock's containers,
  the slipway's ramp and boat, and the cannery's quay; the slipway and estuary rects now take in all
  their water (the slipway's channel, the estuary's pool). The fire station's drill tower is one window
  bay shorter in its day and night art, so it clears the clock box. The lighthouse beam already started
  at the lamp. Costumes for the town's trades (`sprites.COSTUMES`, approved on a contact sheet): bib
  aprons in a trade's colours (leather, chip-shop white, coffee, ink, canvas, mechanic's denim), hi-vis
  vests, a tailor's tape measure, a club scarf, a peaked cap for taxis, tickets and the post office,
  the sweep's soot, the clockmaker's loupe; the MP gets the suit.
- 2026-10-27 The loading dock redrawn in ComfyUI (Qwen ref-latent, day seed 101, night seed 404, chosen
  on a before/after sheet) with the whole crane in the picture, its top at y 22, clear of the clock.
- 2026-10-27 The sports corner set, `studio_sports` (Qwen seed 202, picked from four): a small sports desk
  the presenter stands behind (host mark (92, 144)), a swivel chair for a guest (228, 150), the stadium on
  the big screen, a results board, the trophy cabinet and scarves. No show uses it yet (see Sport).

- 2026-10-27 *The Last Ferry*'s couch and house band. The hour order now has a shorter second guest after
  each main guest's two parts (`Item.target_s`, 100 s, part `couch`), and the main guest stays on for it:
  the producer tells their second part not to say goodbye (`stays_on`), and the couch script names the
  speaker on each guest line (`CouchScript`), so the two guests talk to each other as well as to Vincent.
  They sit side by side on the couch (`guest_near`, `guest_far`), and the close shot finds whoever is
  talking. Seen on a scratch town: Dougal Crane came on, and Ivy Marchetti, the harbourmaster, teased him
  about the oars he lent. The house band is a jazz trio on *Beacon* (`jingle.band`: piano, upright bass,
  brushes, no brass), chosen by ear: `walkon` plays each new guest on, `button` comes back from a break,
  as a silent first line (`assets.band_line`). Stems with `python -m newsroom.station_audio --band`.
- 2026-10-27 Specials have an air time: a finished special waits for the first news bumper from the next
  top of the hour that airs specials (`schedule.special_slot`, `work["airs_from"]`); overnight it still
  airs after the next test card.
- 2026-10-27 Model-written continuity (`continuity.make`, route `promo`, in healthy idle time): a trail for
  each finished special and tonight's documentary, valid until it airs ("Tonight at ten o'clock on
  Channel 7: a special report, Two Engines or One?", with the time and title from code and the pitch from
  the model, or the standfirst without one), and up to four community notices a day from the open
  stories (`[continuity]`, every 45 minutes), addressed to the public and valid until midnight.
- 2026-10-27 Guest casting: scripts give `guest_age` (young, middle, old) and `guest_accent` (british,
  american) beside the gender, normalised from whatever the model writes. Age sets the voice's speed and
  the look (grey hair for the old) and lets an old man get `am_santa`; nine new Kokoro voices widen the
  pool (af_sarah, af_nova, af_sky, af_jessica, af_river, af_alloy, am_adam, am_echo, am_santa), and
  bf_isabella is the continuity announcer's alone. Local guests get Kokoro's British pronunciation
  (`[tts] british_guests`, chosen by ear; a second pipeline shares the model). Guests already cast keep
  their voices. A missing `ANTHROPIC_API_KEY` is now "unavailable" (templates) instead of a crash.

- 2026-10-27 Channel 7's station sound and logo, for the first stream. An original five-note tune
  (*Beacon*: C G C E, then a held G, `jingle.py`) chosen by ear from four. Every show plays it in its own
  arrangement: news on vibes and Rhodes (the code render was preferred to the Stable Audio 3 takes),
  breakfast glockenspiel and marimba, Coastwide strings and funk bass, The Last Ferry lounge piano, and
  breaking news brass in minor. Stems in `assets/music/` (`python -m newsroom.station_audio`); `assets.py`
  bakes the bumpers, sting and bed from them and rebuilds one older than its stem. The bed is a Stable
  Audio 3 Medium take (vibraphone and Rhodes, 87 s, looped). Brass and timpani for the news were turned
  down; SA3 restyles of the code tune changed its notes (it was checked note by note), except at low noise.
  The logo (`logo.py`, approved on a contact sheet) builds a piece on each note in the bumper and idents,
  sits on the filler and test cards, and a corner bug shows during programmes.
- 2026-10-27 The evergreen pool (`continuity.py`): a gap runs ident, advert, card, advert, advert,
  ident, card before the filler card. Idents are the logo and the show's tune with a line from a
  continuity announcer (Kokoro bf_isabella); the card is "Later on Channel 7" (the next shows and tonight's
  documentary, valid until the first starts) or a notice: today's tides and Saltby ferry, and five
  hand-written town notices. All baked in idle time without the model, in `data/continuity/`. Never an
  ident straight after a bumper. `docs/STREAMING.md` has the OBS and YouTube setup.
- 2026-10-27 A special's outline and every section writer get the story so far
  (`special.story_so_far`): when the thread opened, each beat once with its date, broadcast day
  and what was known then, the people involved, where it stands and what's planned next, with
  "keep to its dates". Sections had only the briefing's opening date and last beat. Documentaries
  keep their research notes instead. Sampled on the cannery ghost tour: five sections in the
  record's order, from the unvetted tour to Friday's inspection and Saturday's Halloween run.
- 2026-10-27 A field report sees Miles's last three on its show (`writers._field_so_far`, with
  their threads) and goes to another story and place: two in a row had taken the harbour-wall
  pupils, then the one fire engine. The scene report after breaking news is exempt. Three Haiku
  samples after two fire-engine reports went to the coast road, the stadium and Main Street, each
  a new story; watch a night for whether threads still get followed through.
- 2026-10-27 The story desk can break a story itself: when `breaking.desk_may_break` allows (out of
  the cooldown, `[breaking] desk_per_day = 1`, never overnight) its plan may carry something sudden
  (`StoryPlan.breaking`), told it's rare; it airs like a tip-line BREAKING line, from "the
  newsroom's own sources", as a new thread. After any breaking story, the first field report
  scripted within `scene_window_s` (45 min) sends Miles to the scene, once: it replaces the rota's
  angle, is filed on the breaking thread, and its status says what is now confirmed.
  `--breaking-now` asks the desk at its next idle moment. Seen on a scratch town at 10:00: the desk
  broke a fryer-vent fire at Gull's Rest on the quay (tying it to the one-engine story), it aired
  43 s later, and Miles's report from the quay aired 13½ minutes after that and confirmed it:
  nobody hurt, cause unknown. The next field reports all went back to the fire (with bulletins
  leading with it in between), so for the two hours the bulletins lead with a breaking story, a
  field report after the scene report is told to cover another. The editor stays on specials.
- 2026-10-27 `--scratch` keeps the `--log-llm` call log in its temp folder (`llm_calls/` there,
  `NEWSROOM_LLM_CALLS`; the tests use their own too): the 2026-10-26 documentary check had written
  its 65 Claude calls into the real `data/llm_calls/2026-10-26.jsonl`.
- 2026-10-27 *Morning Tide* books a guest for the sofa armchair, about one every seventeen minutes
  (the breakfast loop is two laps, with an `interview` on the first). Each booking takes the next
  of nine breakfast-show kinds in turn: an author with a book out, an inspiring story, a funny
  guest, an actor plugging a film or series, a charity challenge, a band or choir, a chef, someone
  kind, a sportsperson. Both hosts talk to them; anything plugged is invented, with a when and a
  where. The writer sees this morning's guests so titles don't repeat, the goodbye thanks them,
  and the guest chat doesn't get the tide table (Rosie read Marjorie Pell the ferry's low-water
  gap mid-book). Seen on a scratch town: Marjorie Pell's *The Cannery Years*, then Freya Lusk's
  harbour swim, 13 minutes apart.
- 2026-10-27 The first `--log-llm` night on Claude (22:51–09:31, real town): 699 segments, no
  errors, 12 s of filler, 7 of 327 Haiku calls retried once. $1.64 for the 10.7 hours (about
  $3.70 a day): Haiku wrote every on-air script for $0.16; Sonnet's editor was $0.82 (39 checks,
  38 of them "no"), the story desk $0.58 and the one special $0.08. The editor now checks every
  30 minutes, like the desk (`special.check_every_s = 1800`), about $0.40 a night less.
- 2026-10-26 Fixes from the first look at Claude on screen: a headline, location or strap needs
  four characters (Haiku once sent all three blank, and "Live from" aired bare; later "x" for all
  three, which opened a thread called "x"); the news bulletin is
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
