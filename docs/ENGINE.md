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
- **Harbour Row**: a fifteen-minute daily soap with the town's residents (Winifred, Dev, Brenda,
  Jasper) in a continuing story with cliffhangers; needs a drama item and a memory of each episode.
- **Wexley Wits**: a pub quiz from a darts pub, Clive Ashdown asking, the darts league's pub teams
  playing, the score kept in code, a local-history round from the archive.

The phone-in's `call` item and the `review` item from `docs/SHOWS.md` would serve them too.

## When, and in which world (2026-11-06)

**The entertainment channel shares Port Wexley.** It is the town's second channel: the same
`world.json`, residents and calendar. Harbour Row's cast are people the news has met, the quiz teams
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

**Open:** whether both channels run at once (CPU text-to-speech, one GPU, one OBS output, double
the LLM cost) or take turns, for example entertainment in the daytime that the news night run
doesn't cover. Measure a night's CPU headroom before deciding.
