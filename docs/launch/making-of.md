# Making-of post: draft

A draft for launch week (`docs/LAUNCH.md`): Show HN on Tue 22 December, r/LocalLLaMA on Wed 23, and
r/proceduralgeneration on Christmas Eve. **Nothing here has been posted.** Fill the `TODO`s, check every
number against the logs before posting, and cut to taste. The long version is for HN and a blog; each
subreddit gets a short opening of its own (at the end) that links to it.

---

## I built a 24-hour TV station for a town that doesn't exist

Port Wexley is a small harbour town somewhere on the coast. It has a mayor, a Town Hall clock that stopped
years ago, ghost tours at the old cannery, a foot ferry to Saltby that won't run near low water, and a baker
who renames his treacle tart after whatever is in the news. None of it is real.

Channel 7 is its local TV station, and it is on air all day, every day: TODO (YouTube) and TODO (Twitch).
Breakfast on the sofa at 06:00, a news phone-in, the fish quay's prices at lunchtime, children's TV with a
seagull puppet, local sport, an evening magazine, a late-night talk show, a fifteen-minute documentary every
night and, every other Thursday, the town council debating four motions live. The news fills the gaps, and
overnight there's a test card, repeats and teletext pages turning under a music bed.

Every word is written by a language model as it airs, and every voice is synthetic. It's pixel art (a
320×180 canvas, scaled up) in a Pygame window, captured by OBS. The code is MIT, so you can build your own town with it; Port Wexley itself stays
mine: TODO (GitHub link).

TODO: a 20-second clip or a grid of screenshots here.

### The one rule: the broadcast never waits on the AI

A model call can take three seconds or a minute, and sometimes it fails. Television can't stop. So the
station is a producer-consumer pipeline with a clock at the end:

- a **producer** keeps about ten minutes of programme planned ahead, slot by slot, from the schedule and each
  show's running order;
- a **worker** scripts each slot (strict JSON, validated with pydantic, one retry, a canned template as the
  last resort), voices every line and stores a mouth envelope for the lip-sync;
- a **player** airs finished segments on the wall clock, never cutting a sentence.

When nothing is ready, the station does what real stations do: an ident, a "Later on Channel 7" card, the
tides and ferry times, a local advert (the model writes those in idle time and they're voiced in advance),
and only then a "we'll be right back" card. On a good night there's no filler at all; the first overnight
run aired 525 segments without any.

### Stories that last for days

The thing I wanted most was a town with a memory. A news channel that forgets everything after each bulletin
is just a random headline generator.

So there's a **story desk**. It keeps a board of up to 40 story threads, each with a phase (emerging,
developing, peak, resolving, closed), the beats aired so far, the people involved, and a planned **next
development**. Writers see the NEXT in their briefing and are told a follow-up has to deliver it, so a story
moves on instead of being retold. The desk opens up to ten new stories a day, a few at a time from 06:00,
and closes the finished ones.

Every two hours a **senior editor** reads the whole board and leaves the desk a memo: these two threads are
the same story, this person turns up in too many, this one needs a new angle. Before it existed the desk had
a habit of steering every story towards one council meeting; on one night 11 of its 24 planning rounds said
"converge". With the editor's memos it was 1 in 31.

A long story whose next development is days away goes into a **running-stories pool**: off the writers'
board, so it isn't reported early or reinvented under a new name, and back with its whole history on its
day. Meanwhile the evening shows can still pick it up for an in-depth interview.

Everything that airs goes into an **archive**, so tomorrow's bulletin can say "as we reported on Tuesday",
and the nightly documentary is researched from it. The researcher reads every archive piece on its subject
and writes notes (a dated timeline marking what's on record and what's background, open questions), and the
documentary can cut to clips of earlier coverage, in black and white, tagged ARCHIVE.

People recur too. A guest the writer invents joins the cast with a fixed voice, a look of their own (drawn in
code from their name, voice and role) and a memory of what they said last time.

### The facts a model gets wrong are done in code

Models are bad at arithmetic and continuity, so the station doesn't ask them. The tides are worked out from a
fixed epoch with a spring-neap cycle, and the ferry timetable follows them. The football, rugby and darts
results and league tables are simulated. The fish auction's prices move day to day. On council nights each
councillor's vote is counted in code before the debate is written, so the debate argues towards a result it
was given, and the result is filed to the stories it decides.

### Three models, split by job

- **Claude Haiku** writes everything live: bulletins, interviews, the sofa chats, the phone-in callers,
  breaking news, adverts. It's fast and reliable at strict JSON.
- **DeepSeek Flash** (with thinking) runs the back office: the story desk, commissioning specials, the
  documentary, booking the evening shows' guests and questions.
- **Claude Sonnet** is the senior editor every two hours, and Flash's fallback.

The cost was the surprise. An all-Claude night (Haiku live, Sonnet in the back office) cost about $2.18 for a
12h50m stretch; the same span with DeepSeek Flash in the back office cost $0.55. With the senior editor
added, a full evening-to-morning night (15h20m) came to about $1.10. Running it around the clock is about
$1-2 a day. Prompt caching helps: on the 7 November night, nearly half of Haiku's input tokens were cache
reads.

The routes are config: any OpenAI-compatible endpoint works too (LM Studio and llama.cpp locally, Kimi in the
cloud), and Kimi k2.6 and k3 ran it for the first nights. I benched local models in LM Studio on the same
prompts: for live scripts every one of them passed the JSON schema 12 out of 12 in 3-9 seconds, but the
thinking back-office calls were slow or came back empty, and a 16 GB card also has to share with the
pictures. TODO: say why you stayed hosted, in your own words.

### Voices on the CPU

The GPU is shared (image generation, other experiments), so every voice runs on the CPU, one line at a time,
while the buffer stays ahead.

I tried Kokoro, Qwen3-TTS, Chatterbox, NeuTTS and Kyutai's **Pocket TTS**, and Pocket won: about 0.25 s of CPU
for each second of audio on one thread, and it clones a voice from a short reference clip. So every voice on
air is Pocket cloning a reference:

- most presenters are clones of their own **Kokoro** voice (Kokoro reads a sentence, Pocket clones it, and the
  clone sounds more natural than Kokoro itself);
- the local guests, the mayor, the six councillors and three presenters were **designed from a text
  description** with Resemble AI's DramaBox ("a man in his late sixties with a broad Cornish accent, an old
  trawler skipper, speaks bluntly"), because the other voice-design models I tried came out American;
- Kokoro still does the continuity announcer and Gully the herring-gull puppet (a pitch effect on a raised
  voice), and phone-in callers go through a telephone band.

### Pictures and sound

The 26 locations and 8 studio sets are pixel-art backdrops made in ComfyUI with Qwen-Image and hand-checked,
graded in code for the time of day and for whatever the last weather report said, with rain, snow, fog and
water animated on top. The people are drawn in code; generated character sprites didn't fit the style.

The station has a five-note sonic logo written down as notes in code, arranged for each show (glockenspiel at
breakfast, strings and funk bass for the magazine, a jazz trio for the late show) and rendered in code, not
generated.

### What went wrong along the way

- The model loved a phrase: "the most Port Wexley thing I've heard all week" turned up in about a hundred
  aired lines. (It's in the promo as a supercut.)
- The story desk once listed the weatherman among a story's people, which created "Gordon Pell, resident", who
  then took the credit for 111 mentions of the actual weatherman. Presenters can no longer be cast as
  residents.
- A reworded headline got a fresh picture every time, which produced a night of about fifteen near-identical
  Remembrance wreaths.
- Every night is recorded and its log read the next day, and the fixes go in before the next night. That loop
  is most of the work.

### How it was built

TODO: say this in your own words. Facts for it: started on 24 October 2026; about 260 commits in the first
two weeks; about 22,000 lines of Python in `newsroom/`; nearly every commit was written with Claude Code,
with me deciding what the town and the shows should be, judging every voice and picture by ear and eye, and
watching the nights.

### Where it's going

A second channel sharing the same town, for light entertainment, is being built on the same engine. Its first
show, *Wexley Wits*, is a pub quiz between two of the town's pubs with a darts round, where every dart is
thrown in code. TODO: anything else you want to promise.

If you'd like to keep the lights on, it costs about $1-2 a day: TODO (Ko-fi). The code, the docs and the
credits: TODO (GitHub).

*Port Wexley is a fictional town. Every programme is written and voiced by AI. Voices: Pocket TTS by Kyutai
(CC BY 4.0) and Kokoro-82M (Apache 2.0); guest voices designed with DramaBox by Resemble AI. Scripts: Claude
and DeepSeek. Full credits: TODO (link to docs/CREDITS.md).*

---

## Openings for each venue

**Show HN** (title, then the first comment)

> Show HN: A 24-hour TV station for a town that doesn't exist

> Channel 7 is the local station for Port Wexley, a made-up harbour town. Eleven programmes a day, all
> written by LLMs as they air and voiced on the CPU, with a story desk that keeps news threads running for
> days. It never waits on the AI: a producer plans ten minutes ahead, and a player airs on the wall clock.
> About $1-2 a day in API calls. Live: TODO. Write-up: TODO. Code (MIT): TODO.

**r/LocalLLaMA** (lead with the voices, the bench and the cost; check the self-promotion rules first)

> I built a 24/7 TV station for a fictional town. All the voices run on the CPU with Pocket TTS (about
> 0.25 s per second of audio, cloning from reference clips) and Kokoro, so the GPU stays free. Scripts are
> Claude Haiku live and DeepSeek Flash for the back office, about $1-2 a day; the routes take any
> OpenAI-compatible endpoint, and I benched local models in LM Studio for it. Here's what worked, what
> didn't, and the numbers: TODO.

**r/proceduralgeneration** (lead with the town that remembers)

> Port Wexley is a procedurally written town that remembers. A story desk keeps 40 threads with phases and
> planned next developments, a senior editor reviews the board every two hours, people recur with fixed
> voices and looks, and the tides, the football and the council votes are simulated in code so the
> scripts stay consistent. You can watch it on its local TV station, 24 hours a day: TODO.
