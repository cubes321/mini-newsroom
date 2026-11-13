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
  `locations.MARKS` and `assets.IDENTS`.

Channel 7's own shows still use their branches in those modules. They can move onto the registries
when a change touches them anyway, as stage 1 says.

## Channel 8's evening (2026-11-13)

Planned with the user once Cartoon Time's shelf turned out empty (its hour aired the test card):

| Time | Show |
|---|---|
| 18:30 | Cartoon Time, back once the bank has films |
| 19:00 | **The Kettle's On**, the teatime magazine (built 2026-11-13, `entertainment/kettle.py`) |
| 19:40 | **The soap**, when it is built (until then The Kettle's On has the hour) |
| 20:00 | Wexley Wits |
| 20:20 | the closedown |

- **The Kettle's On first**: the cheap one. It reuses Channel 7's interview and phone-in items through the
  registries; the phone-in needed two more (`writers.STUDIO_HOOKS`, `writers.CALLED`).
- **The soap is set on a made-up street with a title of its own**, not on Harbour Row: that is a real street in the
  town (its net menders, sailmaker and clockmaker, and news of its slates), and the soap's fiction is kept apart
  from it. The name is still to be chosen.
- **Head-and-shoulders figures first** (stage A): soap scenes are mostly two or three people across a bar or a
  kitchen table. Walking full figures (stage B) come once the story engine has worked on air.

## The content bank, built (2026-11-07)

`newsroom/bank.py` keeps finished films made offline (the shelf: data/bank and its index) and airs them
with a rule for how soon one repeats; when each aired is the world's, so a scratch run's airings stay in
its copy. A `film` segment carries the soundtrack as its one line and the video in its work; the player's
film mode draws frames from an ffmpeg pipe straight onto the window (`film.py`, `scenes.present`). The
entertainment channel's Cartoon Time is its first user (`entertainment/cartoons.py` makes the films); the
advert and continuity pools and the overnight repeats could move onto it when they are next touched.
