# To do

Roughly in the order we expect to tackle them. Done items move to the
bottom with the date.

## Art

- [x] Voices by ear for Howard Lanyon, Tamsin Jago, Meg Trethewey, the six councillors and Helen Strand (2026-11-01):
  DramaBox designs (`bf_jago`, `bm_lanyon`, `bf_trethewey`, `council.VOICES`), cloned live by Pocket, each with a
  Kokoro stand-in in voices.toml (`tts.kokoro_voice`). Qwen3-TTS VoiceDesign was tried first and every "West
  Country" voice came out American (Pocket keeps whatever accent its reference has); Kokoro blends of its eight
  British voices were British but all one family. Listening pages: data/voice-samples/council-presenters/.
- [x] **The local guests recast with DramaBox** (2026-11-01). The 13 Qwen clips had made every "local" guest American
  since Pocket went live (2026-10-30). Now 24 DramaBox voices, four per gender and age (the 13 under their old keys,
  11 new: Wenna, Tamara, Jenifer, Elowen, Morwen, Jowan, Kit, Hedley, Ross, Jory, Bernard), all kept by ear. A new
  guest is cast by gender, age and name (`world.guest_pool`); a town saved before is spread once (`GUEST_CAST`,
  `_recast_guests`): 473 of the real town's 528 moved, nobody changed gender, and bf_isabella's nine residents
  left the announcer's voice. Listening page: data/voice-samples/guests-dramabox/.
- [ ] Visitors' voices: someone "from away" (`accent` american) still speaks Kokoro's American voices with no clip.
  DramaBox could design a few `.a.wav` visitors the same way, if they should sound less like Kokoro.
- [x] The new shows' own bumper arrangements (Quayside, The Inquiry, The Panel, Have Your Say, Out and About
  and Rock Pool use the news one). Music chosen by ear 2026-11-04 (`jingle.SHOW_STYLE`: Quayside ticker, Have
  Your Say bright, Out and About folk, Rock Pool toy, The Panel synth, The Chamber organ, The Inquiry cello in
  the minor) and their stems written; each show has its own line in `assets.IDENTS`. The voiced
  bumpers were baked the same night (the voices are on the CPU) and approved by ear.
- [x] Art for Rock Pool's set (`studio_kids`), 2026-11-01 (701e449): ComfyUI art, a sea-green wall with painted
  waves and bunting, a rock pool with a crab and a starfish, a craft table. Gully stays code-drawn
  (`sprites.draw_gully`), like every character.
- [x] Interiors for Out and About's reviews: a tea room, a dining room and a village hall (b4e6d29, 2026-11-02).
- [x] A phone-in desk for Have Your Say (`studio_phonein`, b4e6d29, 2026-11-02). The caller box is still drawn in code.
- [x] Art for The Panel's set (`studio_panel`), 2026-11-01 (701e449): ComfyUI art, a long desk with four places,
  a wide screen and the channel 7 ident; its marks moved up three pixels to sit at the desk.
- [x] A fish quay backdrop for Quayside, 2026-11-01 (e977fc2): boxes on ice, the auctioneer's chalk board, the
  fish vans (`fish_quay`). Quayside's field report is always there, unless breaking news sends Miles out.
- [ ] Station audio follow-ups: a 44.1 kHz stereo mixer (everything plays at 24 kHz mono, so
  the music stems are exported that way; Kokoro would need resampling on load); a bed per show
  (the bed is loaded once at start).
- [ ] Parked (2026-10-27): parallax. True parallax needs the camera to move, and every backdrop is
  exactly screen-sized, so each exterior (24 days, 14 nights) would have to be redrawn wider in
  ComfyUI with its far layer painted separately: several sessions of art. The cheap version, about an
  evening and no ComfyUI: drifting skies. Lift the sky out of each picture by colour, rebuild it as
  an endless strip with the same gradient and clouds, and let the clouds drift behind the buildings.
  It wouldn't reach the studio sets; check hazy horizons by eye; show before/after first.
  Drifting skies built 2026-10-29 on branch `drifting-skies` (`skies.py`): every exterior, day and
  night art, graded for dusk and weather; the wind hurries the clouds. Approved and merged
  2026-10-30. Finding a sky takes about 50 ms
  the first time a backdrop is drawn; if that shows as a hitch on air, warm them at start-up.
  True parallax (a moving camera over wider art) is still parked. A cheaper route was trialled on 2026-11-03
  on the harbour, Main Street and the fish quay (a foot row per pixel, a gentle drift drawn at window size;
  clips in E:\recordings\parallax-trial) and the user asked for it to be planned: `docs/PARALLAX.md`
  (triage the 24 exteriors by depth, the engine behind `[broadcast] parallax`, a pilot evening, then the art).
  Triage done (12 chosen) and the engine built the same day (`newsroom/parallax.py`, off by default); next
  the pilot evening with `--parallax` on the trial's harbour and fish quay.
- [ ] More guest costumes in `sprites.COSTUMES` as new roles turn up (the first match on a role word
  wins). On 2026-10-28 every role the town had cast matched one.
- [ ] **Graphics made live by ComfyUI** (the user's idea, 2026-11-03; brainstormed 2026-11-04, build after the
  11-05 log is checked). Decided: **shadow mode first**: the back office makes the pictures for a few nights
  but nothing shows them, and each night's go on a contact sheet to judge how they would fit. Then decide
  where they show (and whether Phase 0, a library approved by the user, comes first).
  - The GPU is free during a run: the voices are on the CPU (`[tts] device = "cpu"`); on the 11-04 night
    the card sat at 1.4 of 16 GB. Qwen-Image-Edit int8 needs ~12 GB, ~6 s a picture warm.
  - The writer names the picture: an optional `picture` line in the script (what to show, no text in it).
    A picture worker beside the station sends it to ComfyUI's HTTP API; items are planned ~10 min ahead.
  - Never waits: if a picture isn't ready, or ComfyUI isn't up, the slot shows what it shows now.
  - Reused by story id, and Rock Pool's by name (Biscuit the cat is always the same Biscuit): a few dozen
    new pictures a day, not hundreds.
  - In the backdrops' pixel-art style, downscaled to the canvas and its palette.
  - Polite on the GPU: check free memory first, stand aside when an art session has ComfyUI busy,
    `/free` when idle, a switch in config.
  - Candidates, most value first: Rock Pool (the animal visitor, the make, children's drawings in crayon,
    story time); the news wall screen (`WALL_SCREEN`) and the sofa handover box (`SOFA_INSET`), one per
    story; Coastwide and Out and About cutaways; sepia "archive photographs" for documentaries and The
    Inquiry; product shots for adverts. Never real people, brands or readable text; the user to decide
    whether serious stories (fires, accidents) get pictures at all.

## Content

- [x] **Wexley Wits, built 2026-11-07**: the entertainment channel's first show, in a new `entertainment/`
  package (`--channel entertainment`; docs/ENGINE.md). 20:00 to 20:30: two darts pubs' regulars, Clive
  Ashdown asking, four rounds of six (general, Port Wexley, the week's news, pot luck) booked in one back-office call
  on The Chamber's route, every answer drawn on pub strength and the score kept in `entertainment/quiz.py`;
  each round's brief carries its result. The engine takes another channel's shows through registries
  (`writers.SHOW_SYSTEMS` and the hooks beside it, `workers.IDLE_JOBS`, `scenes.SHOW_SETS`, `player.SEATS`).
  Scratch run the same day: every score Clive read matched the booking; four-question rounds came in at
  70-85 s and chats filled the rest of the half hour, so there are now four rounds of six, a word between
  questions, and six chat angles for whatever time is left.
- [ ] Wexley Wits, next:
  - **A quiz set** (art, the user's approval): the darts pub backdrop stands in, Clive at the bar end and
    both pairs across the floor (`wits.MARKS`). A set of its own: a quizmaster's lectern, two team tables,
    the scoreboard.
  - **Its own ident**: the bumper is a placeholder sting with Clive's voice (`bumper_wits.wav`), listen-then-commit.
  - **The rest of the channel's evening**: outside 20:00-20:30 it is the overnight test card, which still
    carries Channel 7's ident and would repeat Channel 7's cache. The content bank (ENGINE.md) is the answer.
  - The channel still wears Channel 7's logo and name in places.
  - A darts round (three darts each, scored in code from `darts.py`) if rounds still come in short.
  - The result as town talk: the news or Coastwide mentioning who won.
- [ ] Watch a real evening for what the 2026-10-27 scratch run couldn't show: a British-pronounced local
  guest on air (only heard in samples), a main guest's second part that hands over to the couch
  instead of saying goodnight (`stays_on`, added after the run), the trail and notice prompts after
  their fixes (no repeated title, notices for the public, slide lines cut at a word past 190
  characters), and a special waiting for its hour and then airing.
- [x] The Chamber, the last of the 2026-10-30 brainstorm's seven new shows (`docs/SHOWS.md`): built
  2026-11-01, full council live every other Thursday from 5 November, with a council calendar, six
  councillors and booked votes that settle stories. All seven are built. The Kettle's On, Harbour Row and
  Wexley Wits go to the entertainment channel (`docs/ENGINE.md`).
- [ ] The Chamber's first night (Thursday 5 November, or a test run with `NEWSROOM_COUNCIL_NIGHT=1`):
  whether the agenda picks stories really due at council, the debates read their booked results
  exactly, the votes split believably, the hour fills without the loop repeating itself, and what the
  desk does with the stories afterwards (resolving, then closed?). The 2026-11-01 test run (started at
  19:40) opened on the stand-in, the documentary's stages ahead of the booking (the bookings now come
  first); a booking made by hand on the same world split 4-1-1, 3-2-1, 3-2-1 and 2-3-1 lost. Its debates
  ran about two minutes against 330 s, so the loop came round three times with the same items ("SO FAR
  TONIGHT" is now as strict as Coastwide's); if it still repeats, shorter debate targets with more loop
  angles, or more motions.
- [x] "Later on Channel 7" once an hour in the rolling news (the user's idea, 2026-11-01): the programme
  card was baked every hour but aired only in a gap, and on 2026-10-31 the buffer never ran dry. It now
  also airs ahead of a news bumper when an hour has passed since it last aired (`continuity.PROGRAMMES_EVERY_S`).
- [x] Moods on air (2026-11-01): eight faces (`sprites.MOODS`, chosen on a contact sheet), a `mood` on every
  live script line (`models.Mood`; the model's own words mapped to the nearest, or dropped), and the player
  passing the line's to the speaker's face; the others on screen react (`sprites.REACT`: a smile at a laugh).
  Asked for on two or three lines an item: the first try had Ada Quarrie laughing on four lines of twelve
  and Vincent smiling on four more.
- [x] Moods, watched on the 2026-11-01 night (2026-11-02, 2103b55). The news kept to about one an item, but
  Dana's were 53 "smug" of 78, mostly on dry sign-offs, and the long two-handers ran past "two or three an
  item" (Morning Tide's interviews 5.4, one on the late show 8). Coastwide's clashing pair, Pat and Clive,
  was the most watchable thing on air. Now a script keeps three (`writers.ration_moods`, the rarer faces
  first), the newsreader's last line is plain, and the mood help says smug is a gloat or a dig. Replayed
  on that night's scripts, Dana's smug faces fall from 47 to 24 on the cap alone; check the next night
  for what the new help does.
- [x] Moods, next: in a wide shot only laughing, surprised and a hanging head read: body poses (arms up, a slump)
  would carry it there. Done 2026-11-04, approved on a contact sheet (`sprites.POSES`, `python -m newsroom.sprites
  --poses`): lean, laugh, slump, hands up, arms folded (leaning in or back), a fist to the chin, a hand behind
  the head; easing in and out over 0.3 s, arms only for whoever is talking. Watch on air whether the hand behind
  the head reads as embarrassed. Movement (entrances, crossing to a mark) waits for *Harbour Row* on the
  entertainment channel, with full figures: the poses' easing is the first piece of it.
- [x] Dana's links on The Chamber from the press seats (`chamber_press`, b4e6d29, 2026-11-02).
- [x] Built 2026-11-01 as SEVENTEXT (`teletext.py`): thirteen pages from the world in code, a block of
  about two minutes every eight overnight, the first two blocks a night recorded (`obs_record.py --teletext`).
  Still open: a model-written page or two (a "from the archive" page), and whether eight minutes is too often:
  on the 2026-11-01 night it aired 46 times, 130 s about every 7 minutes, near a third of the small hours
  (the two recorded blocks are in E:\recordings, 02-34 and 02-46).
  Teletext pages overnight (the user's idea, 2026-10-31): between the test card and the repeats,
  the station's teletext service cycles its pages under a music bed, as British TV filled the small
  hours in the 1980s. A 40 × 24 character grid in the eight teletext colours, double-height headings,
  chunky block graphics, a page number and clock in the header row, and pages that turn on their own:
  a news index and one page per story from the day's headlines (short excerpts in teletext's clipped
  style, a few lines each, from the archive), the weather with a block-graphic map, the tides, the
  sport results and Full Time's table, what's on Channel 7 tomorrow, and the town's notices. Drawn in
  code on the 320 × 180 canvas like the rest; the text could come straight from the archive and
  `world`, or from one cheap call per night to rewrite the stories as teletext pages. A silent item
  (no TTS), so it costs nothing to voice and fills time the repeats leave over.
- [ ] A model-planned running order for the magazine and the talk show (a
  theme and a topic per item) on top of the fixed hour orders.
- [ ] Optional real-weather hook mapping the user's city onto Port Wexley.

## Engineering

- [x] **The findings in PROJECT_REVIEW.md** (2026-11-02), fixed 2026-11-03 (1442823, 5337392, 4400242, e55bb8c).
  The archive had recorded every segment when it was scripted, so the ten minutes of buffer at each shutdown
  (and any failed voice or skipped slot) became coverage nobody saw. The writers still make the entry when they
  write, marked `aired: false`, as the next writers have to see what is about to air. The player confirms it
  when the segment finishes (`world.confirm_aired`), and an entry never confirmed is dropped after an hour, and
  at load. Thread beats, guest memories and council results still land at script time: they are planning, or
  facts about the town. Also: `world.save` snapshots inside its lock (an older town could overwrite a newer
  one); exit waits up to 30 s for the workers; a dropped advert's WAVs get their hour from the drop; the
  segment on air no longer counts as buffer for the healthy check; the transition history keeps the last 5000.
  A 6-minute scratch run: 15 written segments aired, 15 entries confirmed, 31 left waiting at exit.
- [x] **A town events calendar**, from the review's extras (agreed 2026-11-02): `calendar.py` built like
  `council.py` and `sport.py`, hand-written annual events plus rules from the date, no model, nothing saved.
  One or two upcoming events per writer, a date for the desk's NEXT, a What's On page in SEVENTEXT. Draft the
  event list for approval first. Built 2026-11-03: 32 events approved by the user (festivals, school terms
  and half-terms, civic dates, anniversaries), each a rule from the year; budget night and mayor-making
  come from the council's meetings, the elections every four years from 2027. It sets canon: the charter of
  14 March 1871, the Mariner's Gale of 9 December 1910, the cannery's last shift on 25 September 1981 and
  Market Day (since 1890). Each writer gets at most two events in the next five days that suit its show,
  nearest first, and is told to invent none (`for_prompt`; not breaking news). The back office's briefing
  (`summary_for_editor`) has the fortnight with full council, the Tides', the rugby's and the darts'
  matches and the auction's return after a weekend (`coming_up`), and the desk may set a NEXT for one of
  those days; `calendar.due` reads the date back for the long-running pool. SEVENTEXT page 180 is What's
  On. Bonfire Night falls on the first council night (Thu 5 Nov); the fortnightly council also lands on New
  Year's Eve and on election day 2027, left for the user to decide.
- [x] **Special nights**, the user's idea (2026-11-03): New Year's Eve and election day get programmes of
  their own, and Bonfire Night too. Draft agreed the same day, built in order. Done 2026-11-03: council
  doesn't meet on New Year's Eve or election day (`council.cancelled`; the meeting is dropped, not moved).
  **Coastwide at the Bonfire** takes 19:00 to 20:00 on 5 November, every year (`schedule.BONFIRE`, a
  variant of Coastwide with its id, chosen by the calendar through `SPECIAL_NIGHTS`). It is all on
  location: the estuary set as the Salting, graded to night (the user picked it over dusk on a contact
  sheet), with a bonfire and, from 19:30 to 19:50 on the clock, fireworks drawn in code
  (`scenes.draw_bonfire`, `draw_fireworks`). Running order: the lighting, a crowd vox pop, Bea Kowalczyk on
  safety, the guy competition, Gordon's forecast from the studio, Dev's renamed parkin, the bonfire
  builders, the volunteers, the cost of sparklers. The writers are told it's on location and where the
  fireworks have got to by the clock (`schedule.on_location`). `NEWSROOM_SPECIAL_NIGHT=1` forces it for a
  test run. A template scratch run at 19:24 showed it live at the bonfire and the fireworks up from 19:31;
  the briefs still need a live run with the model.
- [ ] **New Year's Eve: The Last Ferry: New Year's Eve** (build in December): 22:00 to half past
  midnight in place of The Last Ferry and the 23:00 news. Vincent and the house band; a monologue on the
  year; Port Wexley's Year (the most-covered stories, told back by Dana from the archive); guests from the
  year back; Gordon's forecast for the fireworks; Miles at the harbour wall from 23:30; the countdown, the
  Town Hall clock striking twelve, fireworks off the harbour wall. Needs an item the player holds to the
  real clock so midnight lands on the second (the producer only changes shows at segment boundaries), and
  the chimes and the band's midnight number on a listening page first. Reuse `SPECIAL_NIGHTS`, `location`
  and `draw_fireworks`.
- [ ] **Election night: Port Wexley Decides** (build in spring 2027, for Thu 6 May): 22:00 to 02:00. Dana
  anchors, Miles at the count in the Town Hall, Gordon on the swingometer; results declared ward by ward,
  worked out in code like the football (candidates, votes, turnout from a seeded draw on each ward's
  leanings), Helen Strand's seat last. No campaign coverage while the polls are open (07:00 to 22:00).
  Each ward's slate goes to the user for approval first. Still to decide: whether seats can change hands
  (a new councillor needs a voice by ear, and the council roll would change with the date).

- [x] **The 2026-11-02 night and daytime runs, reviewed 2026-11-03** (0481941, 57046c4). The night ran clean: 968
  segments, no filler or templates, and the mood ration held (Dana 18 smug faces on air, none on a closing line).
  Daytime news field reports opened "Good evening" 26 times over two mornings: Dana's card said "evening news
  anchor", and Haiku followed it over the brief; her role and the brief's greeting are fixed. Quayside's loop
  aired one feature four times in ten minutes with no memory; Out and About's six feature angles put an item's
  own angle out of the last four shown; Have Your Say's caller kinds named people, who rang every lap. Every
  looped show now remembers its day, each item sees the earlier ones on its own brief, a caller kind is a
  description, and a call sees every earlier call of its kind. A Quayside scratch run on the fix had three
  businesses over four features. Its "how they began" excerpts were Howard's same hello (now a middle-of-show
  item says none); watch whether the excerpts name the subject.
- [x] **The rolling news writes the quay auction into almost every bulletin.** On the 2026-11-02 night one auction
  headline aired eight times between 10:21 and 10:40, and the 23:49-00:45 news was nearly all "five boats out";
  on 11-03, 76 of 363 news items. Fixed 2026-11-04: the auction is news once, then leaves the news's briefing,
  and a bulletin or report that leads on it anyway is asked again (`writers._auction_on_news`); the news's
  words for it count too (`quay.about_the_auction`). Morning Tide's lead bulletin and six-minute weather
  still repeat in a milder way (40 repeats in 180 items): watch.
- [x] **Coastwide ran the same items every lap** (2026-11-03): its 19-slot loop came round three times with the
  same briefs, and Haiku wrote the same redshank count, roof-survey scam and parking rise each lap though the
  prompt listed them. Fixed 2026-11-04: a brief per lap (`Item.brief` as a tuple, `Show.item`), angles in turn
  for the vox pops, and a near-repeat headline is asked again (`writers._repeated`).
- [x] **The Inquiry thanked viewers for watching Coastwide** (every night 10-31 to 11-02: the briefing has Pat as
  Coastwide's presenter) and **put THE GUEST back in four "other" interviews** (11-03): asked about a returning
  guest, the third call had lost the "NOT them" note. Fixed 2026-11-04: every goodbye names its own programme,
  later asks keep the earlier notes, a returning-guest ask that books someone else is dropped, and The Inquiry's
  films and vox pops can't book THE GUEST either.
- [x] **Silent recording**: VB-Audio Virtual Cable, OBS recording CABLE Output with Desktop Audio muted, and
  monitoring on or off to listen. Don't mute python in the mixer: that silences the capture too. The station
  side is built (2026-11-03): `[broadcast] audio_device` or `--audio-device`, and `--obs` records each
  programme without a second window (`docs/STREAMING.md`). The cable was installed on 2026-11-04. On this PC its
  output is "Speakers (2- VB-Audio Virtual Cable)", and config.toml is set to it. Still to do: point OBS at
  CABLE Output and record a night on it. Done: OBS records CABLE Output, and the 2026-11-05 night's
  recordings came out fine for sound (the user listened, 2026-11-06).

- [x] **The Inquiry and The Panel ran out after ten minutes** on 2026-10-30: items come in near half their
  targets, and each show reached a one-item loop and repeated it (17 "Waiting on the Mud" films, 10 quick-fire
  rounds). Fixed 2026-10-31: both loops are blocks of bare items that take the angles in the show's `briefs`
  in turn, and The Panel books four questions. The Inquiry's guest part two had been written as a fresh
  interview (the producer pointed "cont" at the vox pop before it; now only interviews count), and its "other
  side" booked THE GUEST: "other" items and its films are told not to, and checked after. A scratch run
  (`data/scratch-evening-2026-10-31.log`, from 19:50) filled both: The Inquiry 25 items in 31 minutes with an
  engineer, a councillor and a resident among its voices, The Panel four debates of 150 to 200 s, a vox pop, a
  quick-fire round and a viewer's email.
- [x] **The Panel takes its questions out of order.** The vox pop briefed for the SECOND question took another
  (the third on 2026-10-30, the third again in the 10-31 scratch run, the first on the 10-31 night), and on the
  night of 10-31 the loop after the four debates put the last question (hake and harbour dues) five more times:
  the interview prompt made every item "ONE question THIS ITEM names", so "the week ahead" became hake too.
  Fixed 2026-11-01: a brief's "{q2}" is the second question in its own words (`panel.brief_for`), the viewer's
  email takes the first, and a round that names no question is that round, not a rerun.
- [x] **The Inquiry's "other" voices are THE GUEST again.** On the 2026-10-31 night Helen Strand was in the
  chair for four of the six "other" interviews (slots 123, 125, 130, 135). `script_segment` caught her each
  time and asked again, but the second answer wasn't checked, and it named her too: the interview prompt
  had Pat ask THE QUESTIONS, which are written for THE GUEST. Fixed 2026-11-01: anyone else is asked about
  what THIS ITEM says they bring, the retry names someone else on the story (`_other_voice`), and THE
  GUEST booked a second time fails the item.
- [x] **The day's new stories were all seeded in the small hours.** On 2026-11-01 all eight went between
  00:04 and 03:34 station time (a green bottle, frost on the Salting path, kippers for the Tides), into the
  overnight repeats, and breakfast, the day and the evening had none left. Fixed 2026-11-01: none before
  `[story] seeds_from` (06:00), then `seeds_per_day` (raised to 10) released evenly over `seeds_over_h` (18),
  one every 1.8 hours (`World.seeds_left`).
- [x] **Overlong captions failed whole scripts.** 30 attempts failed validation on the 2026-10-31 night: 7 on
  a field report's or vox pop's `location` past 60 characters, 3 on a reason, 4 on a headline, caption, vox
  pop question or stance. One sent the editor to Sonnet. Fixed 2026-11-01: headlines, captions, locations,
  the vox pop's question and the documentary's stances are cut at a word (`Headline`, `Caption` in
  `models.py`), and the reasons are clipped like status notes. An empty headline (8 that night) still fails
  and gets the retry, on purpose (`test_captions.py`).
- [x] **A pool for long-running stories** (the user's idea, 2026-11-01). Built 2026-11-04 (`world.pool_threads`,
  `[story] pool`). By then the problem had changed shape: the senior editor had the longest stories closed as
  stalled (t220 at 117x, t298 and t338 at 52x) and the harbour wall came back as t372 with none of its history.
  A long story (open two days or covered ten times) whose NEXT names a later day now waits for it: off the
  writers' board and the desk's rounds, never faded for quiet, not counted as live; the writers see a short
  list of what is waiting, the deep-dive shows still take them, and on its day it is back. On the 11-04 town
  it would have parked 8 of 17. Watch on the first night: "to the pool until", "back from the pool", whether
  the board (7 left on the 11-04 town) feels thin, and whether a waiting story still comes back under a new id.
- [x] **Quayside says "this morning's auction" at the weekend.** Fixed 2026-11-01: its briefs say "the latest
  auction", and QUAY FACTS give the day. It airs every day at 13:00, but the auction
  is weekdays only, so on Saturday and Sunday the figures are Friday's (`schedule.py`, its open and the
  quay report's briefs). Say "the latest auction", or name the day.
- [x] **The Inquiry's stock interview is off the story.** Fixed 2026-11-01: Pat to camera on the questions
  still open; The Chamber's is Helen Strand reading the booked vote. The recorder also skips the
  documentary's overnight repeat now (`special.REPEAT_SLOT`). Slot 133 on 2026-10-31 ("Dev Ramachandran on the
  week in town", 20 s) aired in the middle of The Inquiry after two too-long answers; a failed "other" item
  now lands there too. Give The Inquiry a stock item of its own (Pat to camera on the questions still
  open), or skip to the next item.
- [x] **A thread's people only grow.** `desk.py` appends the people the desk lists, so the prompt's
  "at most four per thread" can never shrink a list: t220 has 22 people, t243 21, t248 16. The senior
  editor asked for three a thread in four memos running (all eight on the 2026-10-31 night), and the desk
  said it had complied. Fixed 2026-11-01: the desk's list replaces the old one, and an aired item or a
  merge only fills a list up to `THREAD_PEOPLE` (four). The long lists shrink as the desk next plans them.
- [x] **The auction became a thread.** `QUAY_LABEL` kept the quay off the leads, but an aired auction
  item with no thread opens one (`World.update_thread`): t260 "Quay auction tops fifteen thousand", plus
  four more the desk folded into it. 38 of 159 bulletins and 22 of 104 field reports on 2026-10-30
  mentioned the auction or hake (33 of 166 news items on the 10-31 night). The desk closed t260 on
  10-31, but t313 "...as Auction Takes Fifteen Thousand Pounds" opened the next morning. Fixed 2026-11-01:
  an auction headline may follow a story up but never opens one (`quay.about_the_auction`), and the
  label says "the latest auction", since at the weekend it is Friday's.
- [x] Pocket warned that a chunk passed its 50 tokens ("generation may skip words"), six times on the
  2026-11-01 night. Fixed 2026-11-02: Pocket splits a long sentence only at a comma, semicolon or colon, so a
  dash now becomes a comma and a clause still past 46 tokens gets a comma before its joining word nearest the
  middle (`tts.pocket_text`). All six lines then fit, by Pocket's own tokenizer.
- [x] **A night on the new back office** (Flash, the Sonnet senior editor and fallback, and the first
  night on Pocket voices): 2026-10-30 21:00 to 10-31 12:29, `data/night-2026-10-30.log` and `-b.log`.
  It stopped at 22:05 on a dropped advert's deleted audio (fixed in bc1e28b) and restarted at 22:09 with
  `--clock 19:39`. 941 segments, 0 s filler, no traceback after the fix, no line fell to Kokoro; the
  buffer's median was 661 s. The senior editor broke the convergence: 1 of 31 desk notes said
  "converge" (11 of 24 on 2026-10-29), and the desk quoted its memos back ("Friday 6 Nov kept clear for
  the wall report"). Its memos kept finding date pile-ups and duplicate threads, and merged 4. 16 new
  threads were seeded (6 from guests' loose ends, 5 by the senior editor). "Falling back to" never
  fired; Haiku's 22 failures were first attempts that passed on the retry, and only two adverts gave up.
  Cost, scaled from the earlier nights' bills (DeepSeek's export not checked): about $1.10 over 15h20m,
  Haiku $0.50, Flash $0.29, Sonnet $0.30; about $0.92 for the 12h50m span, against $0.55 (Flash
  without the senior editor) and $2.18 (all Claude). The "documentary" at 18:30 was a 5-minute special
  left over from an earlier run, airing at the next bumper as designed; the nightly documentary aired
  at 21:01. Flash commissioned 9 specials overnight, about one an hour. Full Time had Tamsin at the
  Tides' training and the Lantern's darts, and three Wreckers vox pops at the Quarry Field; its table
  item came round three times. Coastwide repeated only its weather and a bond-letter scam warning (three
  times). The "£" mojibake wasn't in the logs (the console's encoding).
- [ ] The night run ends at 10:00, so the daytime shows need runs of their own: Have Your Say (`--clock
  09:45`: the booking, the callers' variety across the hour, ring-backs), Quayside, and Out and About
  (`--clock 14:50`: whether places rest a fortnight, revisits, an owner answering back on Coastwide),
  and Rock Pool (`--clock 15:52`: story time's legends across the hour, the makes, the visitors: the
  lifeboat station brought its cat twice in each first run, Biscuit being town canon).

- [ ] Watch the next run's log for how the thread and guest changes land: "continues thread" (the
  title match), "story desk merged" (are the merges right, and do they keep up?), "from ...'s loose
  end" (does the desk make news of a loose end, and is it news?), "has been on before" (how often
  a writer rebooks a remembered guest; each costs a second call).

- [ ] LM Studio provider: thinking is off with `reasoning_effort: "none"` and
  the local bench is done (qwen3.6-35b-a3b the most coherent, gemma-4-26b-a4b
  the fastest, qwen3.8-flash-next the best writer but about 15 s a script).
  Still to do: an end-to-end run through the app's own provider config rather
  than a rerouting script.
- [ ] Hybrid routing as config: live segments on LM Studio, the story desk,
  editor and specials on Kimi k3. A one-hour trial with a scratchpad reroute
  ran 93 jobs cleanly; sofa chats took about 27 s on qwen3.8 (Kokoro competes
  for the CPU), and the back office would cost about $0.9 a night on k3.
- [ ] Try DeepSeek (needs credits and `DEEPSEEK_API_KEY`). `deepseek_pro` (v4-pro, thinking on)
  and `deepseek_flash` are declared in config.toml but not routed; `--route
  claude_sonnet=deepseek_pro` moves the back office to it for one run. On 2026-10-28 prices
  (third-party listings; confirm on the console) v4-pro is $0.66 in / $1.98 out per million
  off-peak, double at peak (01:00–04:00 and 06:00–10:00 UTC), against Sonnet 5.5's $2 / $10: the
  back office is where it could save (Sonnet was about $4.80 of a $5.20 day on 2026-10-27).
  Flash, about $0.15 / $0.60, is dearer than Haiku 5.5 live. First a dry desk plan on the real
  world, to set beside Sonnet's ten right merges, then a scratch hour with a special and the
  documentary commissioned; judge the desk plans, the special and the documentary by reading.
  Done 2026-10-28: Flash (thinking on) ran the back office for an hour for $0.043 (the DeepSeek
  export matched our logs; reasoning bills as output; 43% of input was its own cache hits), against
  about $0.45 for Sonnet's first 40 minutes that night. The desk merges were sound on all three
  models (v4-pro put the Harrow Street letter, t126, into the baker's petition rather than the
  fire-station thread, and that's defensible: the baker's petition *is* the second-engine
  petition). Flash's first documentary section recited the world brief. The all-Claude baseline
  night (2026-10-28 19:43 to 10-29 11:13, data/measure-2026-10-28.log) cost about $2.60 at list
  prices: Sonnet about $2.20 for 89 calls, Haiku about $0.40 for 692. The DeepSeek night
  (2026-10-29 19:26 to 10-30 08:21, data/measure-deepseek-2026-10-29.log; a Claude desktop update
  closed the terminal tab running it, so run long nights in their own window) cost $0.55 over
  12h50m against $2.18 for the same span of the baseline: Flash $0.23 by DeepSeek's export (which
  matched the log to the token; peak hours, 01:00–04:00 and 06:00–10:00 UTC, double Flash too and
  were half its bill), Haiku $0.32. No call failed for good and nothing fell to filler; Flash's median
  call was 8 s (54 s at worst, unseen behind a 10-minute buffer). Flash commissioned 9 specials to
  Sonnet's 4 and raised a breaking story, but made 12 merges to 17 and steered 11 of 24 rounds onto one
  council meeting (Sonnet 1; Sonnet instead held the same eight threads all night). Neither desk could
  open threads once the board passed `max_open_threads` (8; 11 to 17 were open, so the prompt said
  "seed at most 0"); Sonnet's 3 came in its first two rounds. Built 2026-10-30: Sonnet as the fallback
  for a call DeepSeek fails, and the senior editor (`senior.py`) every two hours. The back office moved
  to Flash in `[llm.routes]` the same day (`--route deepseek_flash_think=claude_sonnet` puts it back
  for a run). Next: a night on it, to see whether the memo breaks the convergence and how often the
  fallback fires.
- [ ] Split the reusable backend from Port Wexley when the entertainment channel starts: plan in
  `docs/ENGINE.md`. Until then, keep town details out of the mechanics when touching a module.
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
- [ ] Pocket TTS, what's left. Tried 2026-10-30 against Kokoro, Qwen3-TTS, Chatterbox and NeuTTS
  (samples in data/voice-samples/tts-bakeoff/): the user chose Pocket (Kyutai, CPU, 0.23 RTF on one
  thread, cloning from a few seconds of audio). Wired in that night: presenters clone their own Kokoro
  voices (judged more natural by ear), the local guests clone DramaBox clips since 2026-11-01 (24 of
  them, `assets/voices/`, `voices.toml`), cast by gender and age. Pocket ignores `speed` but keeps its
  reference's pace, so a voice is quickened by stretching its clip (Tamsin's, 8%, pitch kept). Left:
  visitors' clips (`.a.wav`, they're still Kokoro's American voices); and throughput if the buffer
  runs short, since lines are voiced one at a time (Pocket is single-threaded, so two could run on
  two cores if its model state is safe to share). Weights are gated (accept the terms on
  huggingface.co/kyutai/pocket-tts, then `hf auth login`) and CC-BY-4.0.

## Done

- 2026-10-30 Rock Pool at 16:00 (`docs/SHOWS.md`): children's television with Poppy Tregenza (`kids`), six years
  teaching Year Two at Saltby primary, and Gully (`gully`), the herring-gull puppet on her arm, who speaks
  for himself. Both chosen on a contact sheet (A of three, with the herring-gull Gully) and by ear: Poppy
  af_bella, Gully `bm_fable@puppet`, Fable spoken slower and raised a third (`tts.PUPPET`), so no guest
  loses Fable. Gully is drawn in code (`sprites.draw_gully`): a crown, a grey back, an orange-ringed eye,
  a lower beak that drops as he talks, a bob in his puppeteer's hand. In the studio throughout, on a set
  painted in code (`studio_kids`) with Poppy, Gully and one visitor's seat: the make, an animal visitor,
  letters and drawings, story time with Hugh, a guest with a job children love, Gully's poem. No ad
  breaks, no news, no threads, no grown-ups booked back for their loose ends; its canned pieces are Poppy
  and Gully's. First runs (scratch, `--clock 15:52` and `15:57`): a paper-plate owl, Biscuit the lifeboat
  cat, letters from Lily (six) and Oscar (five), Hugh's giant who built the harbour wall "in a curve, like
  a smile". Fixed from them: Poppy and Gully's back-and-forth ran past a bulletin's ten lines, so two makes
  and a story fell to Coastwide's canned links ("your money"), and two visitors past an interview's
  sixteen; their pieces and visitors now take 24 lines (`ChatterScript`, `ChatterInterviewScript`) and
  have canned ones of their own. A visitor's dog was taken for the guest, twice: the animal never is.

- 2026-10-30 Out and About at 15:00 (`docs/SHOWS.md`): Meg Trethewey (`travel`), late 40s, twenty years a
  ranger on the Greymouth coast path (A of three people on a contact sheet: red waterproof, a greying
  plait), presents days out, culture and food, all on location: her pieces to camera are field reports
  with no studio to hand back to, features have a local showing her round, and a new `review` item
  (`ReviewScript`, `outabout.py`) visits a place to eat or a show and gives it stars out of five, on a card
  that goes up as she gives them. The town keeps the reviews (`World.reviews`): a place rests a fortnight,
  an older one may be revisited, and on Coastwide an owner reviewed in the last week may answer back.
  Light, but not the news: no big running story, no threads, and breaking news never sends Meg. A canned
  piece is Meg alone, and isn't remembered. Her voice is provisional (af_river, British). First run
  (scratch, `--clock 14:52`): the Gull's Cove walk, the Gull's Nest tea room (four stars, honest about the
  slow service), the Wexley Players, Dev Ramachandran's soup from the market shed, a choir, the estuary
  hides. Fixed from it: the verdict repeated the stars ("Four stars: ...") under the drawn stars, places
  ended ", Port Wexley", a feature's location and caption over 60 characters each cost a retry (now cut at
  a word, for every show's features), a rehearsal feature was followed by a review of the same play
  (the amateur dramatics are the reviews' now), and two reviews a lap at about 50 s each would have made
  about nine places an afternoon (now one a lap, with the targets at 150 s, for four or five). The
  fortnight's rest now covers every review, not only the eight shown to the writer.

- 2026-10-30 Have Your Say at 10:00 (`docs/SHOWS.md`): Jonah Pike's news phone-in. From 08:30 `phonein.py`
  books the day's question, the studio guest at the heart of it and four to six kinds of caller with
  different views; each call takes the next in turn (a second lap brings someone new with a new point),
  and someone who rang on an earlier day may ring again. A new `call` item (`CallScript`): the caller is
  cast like a vox pop's passer-by, voiced through a telephone band (`tts.telephone`, 300-3400 Hz), and
  shown as a box with their name, where they're ringing from and their voice's waveform, while the studio
  guest stays in the armchair all hour. A call files under the question's thread without moving it and
  never opens one. Dana reads the headlines from the news desk; Jonah does the travel with the tides.
  A viewer tip can become a caller. First run (scratch, `--clock 09:40`): Flash booked the harbour's
  missing £410 phone bid with Ivy Marchetti and six callers (Bernard Moss the sailmaker, the Kessick Bay
  bidder, Dolores Finch, Dev Ramachandran, a retired accountant, a young fisherman); the first six calls
  took them in turn and Ivy answered in five. Fixed from it: calls ran about 55 s to a 100 s budget (now
  130), the second lap repeated the first word for word (Tomas Reid came back as Tomas Reilly), the caller descriptions were cut at 140
  characters, and "Harbour Row, Port Wexley" didn't fit the box. A sample call is in
  `data/voice-samples/phonein-first-call-2026-10-30.wav`.

- 2026-10-30 The Panel at 20:30 (`docs/SHOWS.md`): Dana Ferris chairs three panellists on three questions,
  booked in idle time from 18:30 (`panel.py`) to disagree (an official, a worthy or a business, a resident),
  never tonight's Inquiry story or guest; a stand-in lineup covers a failed booking. Each debate is an
  interview item with `PanelScript`: every panellist's line carries their name, so each has their own
  voice, caption and seat at the long desk (`studio_panel`, painted for now). A question from the public
  (a vox pop) leads into the second debate. The documentary still opens the news at 21:00, and the
  programme card puts it in that line. In the first trial one debate took all three questions; the
  writers are now told one question each.

- 2026-10-30 Quayside at 13:00 (`docs/SHOWS.md`): Howard Lanyon (`business`), thirty years the Harrow Street
  bank manager (look B of three: silver hair, a grey beard, a navy blazer), on the morning's fish auction,
  a business in the armchair, the jobs board, prices and a local firm. `quay.py` works the auction out
  from the date like the scores: twelve boats, twelve species in season, rough days that keep the small
  boats in, prices that rise when the landing is thin, and last week's for comparison; every writer's
  briefing has a Quay line. Haiku's trial items kept to the figures exactly. Voice provisional (see Art).

- 2026-10-30 The Inquiry at 20:00 (`docs/SHOWS.md`): Pat Holloway on one story in depth, chosen from
  18:30 with its questions and guest (`inquiry.py`), then 20:30 is news until The Panel is built. In a
  trial on the real town Flash chose the cannery slipway names, Pat pushed ("That's not quite what I
  asked") and Marjorie Pell admitted the families were written to after the decision. Its bumper
  uses the news arrangement; its own is for when the station sound can be heard.

- 2026-10-30 Small fixes and the thread cap.
  - New stories: `[story] max_open_threads = 8` only ever decided whether the desk could seed, and the
    writers keep 11 to 17 threads open, so on both measured nights it was told to seed none. Now the
    desk may seed one a round (two while fewer than `thin_board = 8` are open), and the desk and the
    senior editor share `seeds_per_day = 8` (`world.seeded`, `world.seeds_left`). The board's size is
    still `max_live_threads` and fading.
  - The title match (`world.same_story`) revives a faded thread only on three-quarters of the shorter
    title, and prefers an open thread on a tie: on 2026-10-28 "Lifeboat crew asks small boats to wait
    for daylight" revived a faded harbour-wall thread on boat, crew and wait.
  - Every exterior's sky is found on a thread at start-up (`backdrops.warm_skies`, 38 in 0.7 s), not
    on the frame a backdrop first airs.
  - Haiku's empty headline needed nothing: a headline must have four characters since 5e5eb87
    (2026-10-26), and none was empty in about 2,100 scripts since.

- 2026-10-30 Tamsin Jago, Full Time's reporter (`sport_reporter`): twenty-five, Port Wexley born, played
  for the Tides' women's side; long dark brown hair, a green waterproof and a Tides-blue scarf (look A of
  three on a contact sheet). She goes live from Tidewater Stadium and from a darts pub (the darts desk
  piece became her report) and asks the Wreckers' supporters at the Quarry Field, so the new backdrops
  are used and Miles is off Full Time (he was on three shows an evening). The field scene draws whoever
  is out on location (`View.reporter`, `models.FIELD_REPORTERS`). Haiku's trial darts report and Quarry
  Field vox pop chose the right backdrops and kept to the darts facts. Voice provisional (see Art).

- 2026-10-30 Coastwide remembers its evening (`writers._show_so_far`), as the breakfast sofa remembers its
  morning: each links, feature, interview, vox pop and consumer item sees tonight's items on the show
  (the last 30) and how the last four of its own kind began, and the goodbye gets the list for its nod.
  In the recorded hour of 2026-10-29 the chip-shop vox pop came round five times in eleven, Dev's
  starter three times, and Biscuit the cat, the darts, the estuary birds, the rogue roofer and Oliver
  Fenwick-Hale twice each. Against that hour's real archive Haiku then wrote four vox pops on four new
  subjects (shop windows, Friday nights, late October, the covered stalls); one feature in four was the
  darts again, and the links' odd fact still leans on the Town Hall clock (a landmark in the briefing).

- 2026-10-30 Special and documentary sections, after reading Flash's ten pieces from the 2026-10-29 night
  (lively, with real voices: "They don't read like a memorial. They read like wages."). Four faults, three
  of them the prompts': a thread's planned NEXT step is marked as not yet happened (it had been told as
  done, "on Saturday she called at Winifred's" on a Thursday, or foretold by a guest); each section gets
  what the piece has already said (`special._already_said`, up to 2,500 words; the documentary had
  restated "eighty-one years on Harbour Row" in five of eight sections, and Sonnet repeats itself too);
  a section gets only the location's name, as told not to Flash still recited the description ("the
  horseshoe of desks" in five specials); and a speaker label written into a line ("Dana: Tonight, ...")
  is stripped before it's voiced (`special.spoken`). Three trial specials on the real town came out
  clean. The standfirst takes up to 180 characters (three lines of the title card hold about 200 in
  Bahnschrift) and is cut at a word past that, so Flash's 141-150 no longer retries the whole outline.

- 2026-10-30 A senior editor and a fallback for the back office. A provider with `fallback` (both
  DeepSeek back-office providers: `claude_sonnet`) hands a call it fails, unreachable or twice invalid,
  to that provider once, from a fresh prompt (`fallback_from` in the call log); not when NEWSROOM_LLM pins
  a provider. The senior editor (`senior.py`, task `senior_editor` on Sonnet, `[story] review_every_s =
  7200`) reads the whole board and the desk's last dozen rounds (`world.desk_notes`), merges duplicates,
  may open one story past the desk's cap, and leaves a memo the desk reads every round until the next.
  Dry run on the real town: it named the four threads converging on the reserves line and the 6 November
  finance meeting and gave each another way on, asked five restating threads for a real event or
  closure, and opened a charity harbour swim from a guest's loose end (10 s, about $0.02 a review).

- 2026-10-30 On-screen text is drawn at the window's size in Bahnschrift (`scenes.present`): text is laid
  out on the 320x180 canvas but queued and drawn over the scaled frame, since viewers found the 8 px
  Consolas scaled 3x hard to read. `logo.py`'s audition sheet renders the canvas alone, so it shows no
  text.

- 2026-10-30 Pieces know their place in the show (`writers._PLACE`): Full Time's and Coastwide's openers
  welcome, the middle pieces don't welcome or say goodbye (Coastwide never trails itself as "next"), the
  Last Ferry leaves goodnight to Vincent's close, and the rolling news has no sign-offs. On 2026-10-28
  every Coastwide middle link welcomed viewers again, and about one bulletin in four said goodnight.

- 2026-10-29 Full Time's own arrangement of the station tune and a new breaking sting, chosen by ear on a
  listening page. Full Time ("sport" voicing, a tone up and 15% quicker): a 70s synth lead in octaves, a
  pulsing root bass and four on the floor (`SPORT_STYLE = "drive"`, over funk and disco). The sting drops
  the brass for the news ident's vibes and Rhodes in minor, a low piano hit and a clock ticking under the
  chord (`BREAKING_STYLE = "vibes"`). Fran keeps `af_jessica`. Stems `ident_sport.wav` and `breaking.wav`.

- 2026-10-28 Full Time has more than the Tides: Port Wexley RFC ("the Wreckers") in Coastal Counties One
  on Saturdays (`rugby.py`: tries, conversions, penalties, bonus points) and the Wexley & District pub
  darts league on Tuesday and Thursday nights (`darts.py`: nine games a match, a point a game, the
  regulars' 180s and checkouts), worked out like the football so every show agrees. Both are in every
  writer's sport line and in the sports desk's facts, and Full Time covers them before its order wraps;
  the darts gives a fresh result most weekday evenings.

- 2026-10-28 The story desk merges duplicate threads (`StoryPlan.merges`, `world.merge_thread`): one
  story under different titles folds into the thread it keeps, with its beats, coverage and people;
  its archive entries and specials point there, and a later follow-up of it goes there too
  (`Thread.merged_into`). The prompt asks for every duplicate: worded "most rounds have none", a dry
  run on the real world merged 3; asking for each, 10, all right (four fire-engine threads into
  t058, the harbour wall's two into t116, three "boats out early" fillers into one). The desk's
  next steps are clipped at 300 characters instead of failing the plan (a Sonnet retry each time).
- 2026-10-28 Guest memory follow-ups. The story desk sees the five newest loose ends guests left and
  may seed one as a news thread (`NewThread.from_guest`): the guest joins it, and their loose end
  is spoken for, so a chat show won't also ask. A writer who books a remembered guest of their own
  accord (not the offered return visit, not the guest staying on the couch) is asked once more with
  what they said before, and their loose end if one is waiting; asked, it is used up.

- 2026-10-28 A new story continues the thread it already is (`world.same_story`): when a news
  writer leaves thread_id empty, a headline sharing three telling words, and 60% of the shorter
  title's, with an open or faded thread's title follows that thread up (a faded one revives).
  Breaking news still opens its own. Replayed over the 160 threads of 2026-10-27: 38 would have
  joined, near enough all the same story (the market petition, the estuary tide, the fire engine
  twice word for word). The writer logs "continues thread".
- 2026-10-28 An outage's canned scripts (`Segment.fallback`) are not replayed from the cache or
  repeated overnight: a six-minute outage's interview aired seven times. The night's 16 were
  marked in the cache by hand.

- 2026-10-28 Hugh Tremayne (`historian`), approved on a contact sheet: a former history teacher in his
  sixties, white hair receding, round glasses, a brown corduroy jacket and a mustard tie. Voice
  `am_santa` (out of the guest pools) with British pronunciation at 0.92: presenters can now have
  their own `speed` and `lang`. He presents the documentaries on the town's history; Miles keeps
  those on a running story (`documentary.presenter`), and a section line the model gives "reporter"
  in a history piece is his. He is a character of the town, saved with the world, for the
  entertainment channel planned in `E:\programming\mini-TVChannel` too.
- 2026-10-28 What documentaries establish is canon for the rest of the station
  (`World._history`). The story desk, the editor and the documentary editor see the last five in
  full: each standfirst and up to four background facts. Every writer's briefing lists the six
  newest background facts dated before their documentary (the town's founding in 1871), in the
  cached head; what a documentary expected to happen ("Scheduled: ... on Thursday") stays with the
  desk. The night's documentary repeats overnight (`[documentary] repeat_at = "02:00"`) after the
  first test card from then, from its cache entry, labelled REPEAT, once, and only if it aired
  within twelve hours; a repeat is not recorded as an airing, so it can't block the next evening's.
- 2026-10-28 Sport. Fran Kellaway (`sport`, a former county footballer in the Tides' blue track top)
  fronts *Full Time*, fifteen minutes from the sports corner at 18:45 before *Coastwide* (headlines,
  Miles at a ground, a guest on the sports desk, the league, then supporters and the smaller clubs,
  and the games coming up), and the sport in the news once in three loops (`T.sport`, about every half
  hour). Every score, scorer, fixture and table position comes from `sport.py`, and every writer's
  briefing has a line on the Tides. *Full Time* is light (no threads), isn't repeated overnight, and
  has no big-running-story line. Fran's voice is `af_jessica` (kept by ear over seven others, 2026-10-29).
- 2026-10-28 Seventeen more costumes, approved on a contact sheet: the publican's bar towel, the
  docker's donkey-jacket yoke, the lighthouse keeper's white peaked cap, aprons for the stallholder, the
  groomer and the lamp-oil maker, the ghost-tour guide's dark coat, the sea-glass collector's anorak, the
  milliner and shoemender folded into the tailor and the cobbler, the pasty maker into the chef; and
  for sport the bowls whites, the rowing and swimming clubs, a referee in black and the Tides' blue.
  The sport and outdoor rules come last, so a coach driver or a ticket collector keeps their uniform.
- 2026-10-28 Gestures, approved on a contact sheet: whoever is talking brings a hand up (about 1.6 s in
  every 5.5, every third time pointing), and whoever has been quiet a moment nods (the head dips one
  unit, about every 4 s), each on their own beat. The mouth the player already passes says who is
  talking (`sprites._gesture`), so every set has them; `draw_character(gesture=...)` fixes one for a sheet.
- 2026-10-28 The schedule can start a show on the quarter ("18:45"): show changes, a show's end, the
  test card's next start and "Later on Channel 7" follow it, and the announcer says "a quarter to seven".
- 2026-10-28 Guests remember. Every guest script (interview, couch, consumer, feature) has
  `guest_memory`, one line on what we learned, and `ask_next_time`, usually null, written in the same
  call. They go on the person (`Person.memories`, the last four; `loose_ends`, broadcast clock,
  forgotten after a week). Once a loose end has waited 12 hours of air time, a chat-show interview on
  *Morning Tide*, *Coastwide* or *The Last Ferry* is offered that guest back (`writers._return_offer`:
  what they said last time and what to ask), once a day per show (`world.guest_returns`), never
  someone among the recent guests. Booking them uses the loose end up. A guest chat no longer
  opens a news thread, so this is where it goes: Hollis Byrne's Saturday stadium gig, Maureen Tapp's
  shortbread tin.
- 2026-10-28 A news field report is offered up to four QUIET STORIES (`writers._quiet_threads`): open
  threads the briefing's five don't show, minus Miles's last three and any he has reported from the
  scene, those with a planned NEXT first and then the longest quiet. It picks one up before starting
  a new story. Told to leave Miles's last three alone with only five to choose from, field reports
  had opened 35 threads on the first evening run, among them four on the second fire engine and five
  on the estuary tide in the wind. Not on the light shows, which can't open a story anyway.
- 2026-10-28 The light shows (*Morning Tide*, *Coastwide*, *The Last Ferry*) follow stories up but
  never open one: every segment type, field reports included, not only guests. Breaking news still
  opens its own thread whatever is on. On the first evening run 44 of the 108 open threads were
  Last Ferry and Coastwide guest chats (Priya Anand's cat, Sadie Quill's rabbit) and five were
  breakfast field reports.
- 2026-10-28 Threads fade off the air when they stop moving (`world.fade_threads`, run before every
  segment and every desk round). The windows are hours of air time since the last beat
  (`moved_ts`, broadcast clock): 8 for a one-off covered once or twice, 24 for most, 12 when
  resolving, 72 at a peak. Past `[story] max_live_threads = 40` open, the stalest fade too, never a
  peak or a story that broke in the last two hours. A faded thread leaves the writers' and the
  desk's boards but stays in the list (now 120, closed then faded evicted first). It comes back on
  a follow-up, or when the desk revives it: the desk sees the five most recently faded, and threads
  GOING QUIET six hours before they fade, to give them a next step or close them. The documentary
  can still pick a faded one. The first evening run left 108 open, nothing ever retiring them; a
  world saved before this gets a full window from load, and `python -m newsroom.world fade [--dry]`
  retires such a backlog by its dates (never while the station runs: it saves the world).
- 2026-10-27 `--clock` moves the town's day too: the day roll (`world.roll_day_if_needed`), the
  writers' "Today is" line and the segment cache key read the broadcast clock, not the real date.
  A run started at `--clock 18:30` at 22:50 had been due to turn Wednesday at real midnight, about
  20:10 on air, with a fresh day's desk break and documentary. The LLM call logs keep the real date.
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
