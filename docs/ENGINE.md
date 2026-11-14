# The engine and the channels

The backend is meant to outlive Port Wexley: the plan is to reuse it for an entertainment
channel, and it would make a good basis for other always-on channels too. This note records how
we intend to split it, and when. Agreed 2026-10-28.

## The decision

Split the reusable backend into its own project **when a second channel actually uses it**, not
before. Until then there is one user of the engine, so any boundary drawn now is a guess, and the
engine still changes daily (`llm.py` changed twice on 2026-10-28). A separate repository would turn
every such change into two repos, a version bump and a reinstall.

The sport work shows the pattern: `sport.py`'s private helpers only became public (`round_robin`,
`poisson`, `first_weekday`) once rugby and darts needed them. A second user shows which parts are
general and they don't have to be guessed.

## In stages

1. **Now, at no cost.** When a module is touched anyway, keep the town out of the mechanics:
   names, places, prompts and show details come in through config or the world, not as literals.
   Config-driven providers and the `CACHE_BREAK` briefing split already work this way.
   Engine-wide work (TTS, parallax, the mixer, provider fallback) should be built as engine
   features from the start.
2. **When the entertainment channel starts.** Build it as a second package in this repository, for
   example `newsroom/` (the engine), `portwexley/` and `entertainment/`. Moving code between them
   is still an ordinary refactor in one commit, and one test suite covers both. The first step is
   to map which engine pieces the new channel needs: that map is the outline of the split.
3. **When the boundary has stopped moving** (or a third project wants it). Lift the engine into
   its own repository and install it as a package. Its API will then have been proven by two real
   users.

## Where the code stands (2026-10-28, about 11,900 lines in 30 modules)

| Mostly engine already | Mixed: machinery tangled with Port Wexley | Port Wexley content |
|---|---|---|
| `llm`, `tts`, `buffer`, `workers`, `config`, `producer`, `station_audio`, `tipline`, `breaking`, `models` | `player`, `scenes`, `special`, `documentary`, `continuity`, `adverts`, `schedule`, `desk`, `world`, `writers`, `jingle`, `logo` | `sport`, `rugby`, `darts`, `tides`, `locations`, `backdrops`, the looks in `sprites` |

The middle column is the real work. The biggest modules there are `writers.py` (scripting and
schema checks mixed with the town's voice) and `world.py` (threads, phases and the archive mixed
with the town's people and places). The parts most likely to carry over unchanged to any
channel:

- the buffer and worker pipeline (script ahead, render, play, never dead air);
- per-task LLM routing with usage accounting (and, planned, a fallback provider);
- the cached TTS.

## Engine-wide work queued

These matter for every channel, so they belong to the engine (details in `TODO.md`):

- a better TTS than Kokoro, if one can keep up live;
- parallax / camera movement for the backdrops;
- a 44.1 kHz stereo mixer;
- a fallback provider when one doesn't respond (e.g. Sonnet behind DeepSeek), and an occasional
  supervisor pass, once the overnight cost figures are in.

## A content bank (idea, 2026-10-28)

The entertainment channel could air pre-generated films from a bank that is reused, made offline
(for example with the local video models) rather than live. Port Wexley already has four
one-off versions of this pattern: the advert pool, the continuity pool, the 00:00–06:00 repeats
and finished specials that survive a restart. A bank would be one engine feature that serves all
of them: items made ahead and stored, airings recorded, rules for how soon something may repeat,
and retirement. That makes it a good first thing to generalise when the channel starts.

## Shows kept for the entertainment channel (2026-10-30)

From the brainstorm that produced `docs/SHOWS.md`, three ideas suit the entertainment channel better
than the news channel:

- **The Kettle's On**: a homely morning magazine: a recipe from a local kitchen, a phone-in with a
  studio expert (gardening, pets), a guest on the sofa, the community noticeboard.
- **Harbour Row**: a fifteen-minute daily soap, a continuing story with cliffhangers; needs a drama
  item and a memory of each episode. Its characters are fictional, played by actors (see below).
- **Wexley Wits**: a pub quiz from a darts pub, Clive Ashdown asking, the darts league's pub teams
  playing, the score kept in code, a local-history round from the archive.

The phone-in's `call` item and the `review` item from `docs/SHOWS.md` would serve them too.

## When, and in which world (2026-11-06)

**The entertainment channel shares Port Wexley.** It is the town's second channel: the same
`world.json`, residents and calendar. Harbour Row's actors live in the town, the quiz teams
come from the darts league, and something that happens in the soap or the quiz can become news.
Because of this, the first split runs between the *channels* (schedules, shows, looks, idents)
rather than between the engine and the town. The town's content stays shared and takes no
separate package of its own. A different setting is kept for a later project, which is when the
town gets lifted out of `writers.py` and `world.py`.

**When to start:** once the morning reviews of a few nights in a row find matters of taste and no
mechanical faults (two to four of those a night as of early November). The faults found until then are
engine lessons the second channel would otherwise relearn: clock knowledge, repeat rules, show
memory and cold starts.

**What first:** the content bank (above) and **Wexley Wits**: the cheapest real show, one set and a
score kept in code. **Harbour Row** comes second and brings the full-figure sprites that walk.
**The Kettle's On** whenever it's wanted.

**Testing: alternate nights** (the user, 2026-11-06). One night Channel 7, the next the
entertainment channel (not yet named), on the same machine, stream and world. That keeps one
station's load and cost at a time and leaves running both at once until later. It works well for the
soap: an episode's cliffhanger airs on an entertainment night, Channel 7's night in between talks it
over, and the next entertainment night answers it. The open point is the town's news on the
entertainment nights. The story desk should keep running then, or a thread's NEXT development dated
that day passes unreported. Channel 7's next night can then catch up on what happened.

## Harbour Row and the town (2026-11-06)

*The soap became **Marina Row** on 2026-11-13 (docs/MARINA_ROW.md): Harbour Row is a real street in the town. What
follows holds for it under its new name.*

**Actors and characters, as in real soaps.** Harbour Row is a drama with its own fictional
characters, played by actors who live in Port Wexley. Its storylines are fiction inside the
town, so a soap theft is never a crime the news has to report, and the news can still interview
"the actress who plays Brenda". Its characters stay out of the town's people list. Its actors go
in it, as residents.

**Cliffhangers become the town's talk**, as soaps do in real life:
- Each episode ends by writing its cliffhanger into the world as a *talking point*: the question
  ("Will Brenda tell Jasper?") and the date of the episode that answers it.
- Coastwide can run a "Harbour Row watch" (Pat and Clive's theories). Vox pops can ask who did it,
  and Have Your Say can make a big cliffhanger the day's question. The news covers the soap only now
  and then: when it takes up a real town story, or when one of its actors is in the news.
- No spoilers: the other writers see only what has aired. The soap's arc plan stays out of their
  briefings.
- When the answer airs, the talking point closes, and the next day's shows can react to it.
- The other way round, the soap can borrow from the town (a Bonfire Night episode, a council vote),
  as real soaps do topical scenes.

## The first split: entertainment/ (2026-11-07)

Wexley Wits made the second package: `entertainment/` holds the channel's day (`SCHEDULE`) and its
shows, and `entertainment.use()` puts it on air (`python -m newsroom --channel entertainment`). The
engine never imports it. Instead a show from outside plugs into registries the engine reads by show id:

- `writers`: `SHOW_SYSTEMS` (its prompts), `BRIEF_HOOKS` (tokens in a brief, like The Chamber's
  "{m2}"), `PROMPT_HOOKS` (its booking in every prompt), `TEMPLATE_HOOKS` (a stand-in script when
  the model is down), `SEAT_HOOKS` and `CAPTION_HOOKS` (who sits on the set, under which caption),
  and `BOOKED_SHOWS`, `DEBATE_SHOWS` and `UNFILED_SHOWS`;
- `workers.IDLE_JOBS` (its bookings, after Channel 7's), `scenes.SHOW_SETS`, `player.SEATS`,
  `locations.MARKS` and `assets.IDENTS`;
- added for Channel 8's factual slot (2026-11-14): `player.VIEW_HOOKS` (a show's say over the view), `scenes.SCENES`
  (a view mode of its own: Tideline's hide, The Coast Road's road), `player.AIRED_HOOKS` (a record stamped as a
  segment goes out, for what must outlive the archive), and `schedule.ROTATIONS` (a slot two shows share in turn,
  read through `world.current()`);
- added for Wexley Wits' scoreboard (2026-11-14): `scenes.DRESSINGS` (what a show draws on its own set, behind
  the people, in pixels with `logo.draw_text`, never `scenes.text`: queued text is laid over the finished frame
  and would not zoom with a close shot). The score comes from `quiz.board` (`seg.work["board"]`, set as the item
  is written) through `quiz.view`: it goes up answer by answer, each time on Clive's verdict so the board is never
  ahead of him, and ends every round on the score he reads out.

Channel 7's own shows still use their branches in those modules. They can move onto the registries
when a change touches them anyway, as stage 1 says.

## Channel 8's evening (2026-11-13)

Planned with the user on 2026-11-13, in two sittings. The first, once Cartoon Time's shelf turned out empty (its
hour aired the test card), put The Kettle's On at 19:00. The second filled the rest of the evening:

| Time | Show | Built on |
|---|---|---|
| 18:00 | **A gameshow with prizes** (until Cartoon Time is back, the hour) | Wits' pattern: rules and scores in code |
| 18:30 | Cartoon Time, back once the bank has films | the content bank |
| 19:00 | **The Kettle's On**, the teatime magazine, an hour (built 2026-11-13, `entertainment/kettle.py`) | Channel 7's items |
| 20:00 | Wexley Wits | |
| 20:20 | **The soap**, 20 minutes: titles, five or six scenes, the cliffhanger and credits, no break | the scene engine |
| 20:40 | **Factual**: *Tideline*, coastal wildlife with Rowan Polglase (built 2026-11-14, `entertainment/wildlife.py`), alternating with a town celebrity's travelogue (docs/FACTUAL.md) | The Kettle's On's booking, the soap's episode shape |
| 21:00 | **The TV movie**, an hour | the scene engine |
| 22:00 | **Comedy**, a different kind each night | the monologue, the panel, the scene engine |
| 22:30 | **Late-night drama**: an anthology first | the scene engine |
| 23:00 | the closedown (midnight once there is something good for the last hour) | |

- **The Kettle's On first**: the cheap one. It reuses Channel 7's interview and phone-in items through the
  registries; the phone-in needed two more (`writers.STUDIO_HOOKS`, `writers.CALLED`). It keeps the whole hour (the
  user): the soap goes after Wits, not at 19:40, so nothing overlaps.
- **The soap first of what's left**: its "scene" item (characters on a set, cuts between scenes, no presenter) is
  the drama engine the TV movie, the sitcom, the anthology and later drama series all use.
- **The gameshow**: simple at first, to iron out the bugs; one or two original formats before any more. Local
  prizes (a hamper, a weekend away) give Channel 7's town talk something to say.
- **The TV movie**: a bank of TV movies planned ahead (outline, cast, sets) and played out live by the engine, in the
  soap's full-figure format (stage B below). Later, "blockbusters" rendered offline into the content bank for
  special nights.
- **Comedy**, in this order: a stand-up night (the monologue item), a comedy panel game (the panel item), then a
  sketch show with recurring sketches, and the sitcom once the soap and the TV movie are done.
- **Late-night drama**: an anthology first, a self-contained strange tale of the coast each night, cast from the
  guest pools on the town's own backdrops; recurring series later, on what the soap and the movie have built.
- **Rotations go by Channel 8 night, not by weekday**, while the channels alternate: otherwise a weekday's show airs
  once a fortnight. They can move to weekdays when both channels run every night.
- **The soap is Marina Row** (the user, 2026-11-13), a television street and not Harbour Row: that is a real street
  in the town (its net menders, sailmaker and clockmaker, and news of its slates), and the soap's fiction is kept
  apart from it. Its cast, actors, places and opening storylines are in docs/MARINA_ROW.md, the series bible.
- **Head-and-shoulders figures first** (stage A): soap scenes are mostly two or three people across a bar or a
  kitchen table. Walking full figures (stage B) come once the story engine has worked on air.

## The soap engine, built (2026-11-13)

`entertainment/soap.py` plays a series (Marina Row first: `entertainment/marina_row.py`, docs/MARINA_ROW.md) one
episode a Channel 8 night, on the interview item with every line a character, like Wits' rounds. The engine gained
small generic hooks for it, all filled by `soap.register` and undone with `entertainment.use()`'s undo:
`writers.FICTION_SHOWS` (nothing of the show reaches the town; `world.record_aired(fiction=True)` keeps only that it
aired, and the archive search and the annals skip it), `world.PINNED_VOICES` and `scenes.PINNED_LOOKS` (a character
speaks and looks like their actor), `player.BARE_SHOWS` (no lower third, ticker or clock, and no ticker entries),
an item's own set (`seg.work["set"]`, `View.set_id`), and marks named a, b, c. `talk.soap` gives Channel 7 an aired
episode's cliffhanger, the question only. The TV movie, the sitcom and the anthology are meant to reuse it.

## The creative editor, built (2026-11-14)

`entertainment/creative.py` is Channel 8's editor, as the senior editor is Channel 7's: it keeps the made-up and the
light programmes good. It runs on the `creative` route (Opus; the senior editor's route if config.toml has none) and
only in the back office, a few calls a Channel 8 night. Nothing of it is on the live writer path.

- **A registry.** A programme enrols with `creative.register(show_id, title, kind=..., brief=..., decides=...,
  vetted=..., digest=..., aired=..., books=...)`: what it is, what its planner decides, how to read a night's plan and
  which nights aired. Marina Row, Tideline and The Coast Road are vetted; The Kettle's On and Wits get notes only. A
  programme not built yet (the comedy, the drama, the TV movie) joins with that one call.
- **After air**, one review per programme in idle time, the same night (`workers.IDLE_JOBS`, last): the plan as
  booked and the words that went out, read from the archive entry's cached segment. A night missed because the station
  was closed is caught up at the next Channel 8 start, and ahead of that programme's booking if there is time. It
  keeps, in `World.creative`: `notes` for the next planner, a `ledger` (told, established, and for a drama what is set
  up and not yet paid off), a `log` of marks with remarks for the owner, and `vets`.
- **Before air**, `creative.redraft` wraps a planner's result: the editor may send a plan back once with notes, the
  planner plans again on its own model, and a second draft that fails the module's own check gives way to the first.
  No plan is read within 30 minutes of air.
- **Notes go to planners only** (`creative.for_planner`, at the end of each booking prompt), never to
  `writers.PROMPT_HOOKS`: what is in every item's prompt is said in every item.
- **The rests stay in code** as hard limits; the editor judges what code can't.
- With the models off or its model out of reach it does nothing, and every planner runs as before.

`python -m entertainment.creative notes` prints each programme's latest mark, notes, remarks and ledger;
`review --dry` reads a night without keeping anything. The soap's episodes are now stamped aired on the episode
(`soap.stamp`, through `player.AIRED_HOOKS`): the archive keeps about two and a half nights, and the arc counts
aired episodes for weeks.

## The editors' meeting, built (2026-11-14)

Once a day the two editors meet (`newsroom/meeting.py`; the user's idea, 2026-11-14): Channel 7's senior editor and
Channel 8's creative editor, each speaking as themselves on their own model (Sonnet and Opus), two rounds, and then
the minutes (Sonnet). One call per idle tick from 16:00, after any booking already due.

- **Its four jobs:** keep the channels out of each other's way (a resident in a hard news story is not tonight's
  jolly guest; code hands both editors the residents on both channels), pass stories between them, guard the shared
  canon, and a joint look at the day.
- **Seats, not channels.** `meeting.seat(name, title, task=..., persona=..., brief=..., people=...)` gives an editor
  a seat; the module knows nothing of the other channel's code. The news seat is its own. The creative editor's is
  registered by `entertainment.attend()`, which `use()` calls on Channel 8 nights and the launcher on Channel 7
  nights, so the meeting is held every day. Its brief reads the world alone.
- **Where the minutes go.** Actions are addressed to a seat. The news side's reach the story desk and the senior
  editor beside the senior memo (`meeting.for_desk`). Channel 8's reach its planners through `creative.for_planner`:
  the ones that name a programme go to that programme, the rest to every programme set in the town. They stand for
  two days, since the channels take turns.
- **One story may be offered to the desk**, which may seed it from the day's allowance as it may a guest's loose
  end. This is the first way a Channel 8 happening can become news; town talk (`talk.py`) is still only talk. The
  offer goes once the desk takes it, after four rounds, or with the day.
- **The drama's story stays out of the room.** The minutes sit in the desk's prompt. The creative editor's seat
  brings only what the town already knows of Marina Row: that it aired, its mark, and the question it left. Never
  the arc, an unaired plan or the fiction ledger; and the only meeting actions the soap's planner hears are ones
  that name it.
- A turn that fails is tried once more; then the day has no meeting and nothing changes. With one seat or a model
  off there is none.

`python -m newsroom.meeting minutes` prints the meeting as held; `hold --dry` holds one now without keeping it.

## The content bank, built (2026-11-07)

`newsroom/bank.py` keeps finished films made offline (the shelf: data/bank and its index) and airs them
with a rule for how soon one repeats; when each aired is the world's, so a scratch run's airings stay in
its copy. A `film` segment carries the soundtrack as its one line and the video in its work; the player's
film mode draws frames from an ffmpeg pipe straight onto the window (`film.py`, `scenes.present`). The
entertainment channel's Cartoon Time is its first user (`entertainment/cartoons.py` makes the films); the
advert and continuity pools and the overnight repeats could move onto it when they are next touched.
