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
