# Launch: Christmas Eve 2026

Channel 7 goes public on **Thursday 24 December 2026**, live on YouTube (a new Port Wexley channel of its own,
not Cubes Channel: [Port Wexley, @portwexley](https://www.youtube.com/@portwexley), created 15 November) and Twitch, with a shelf of long videos from 20 December, a
Short a day from 1 December and a making-of post in launch week. This is the checklist from Sunday
8 November. **You** marks the steps only the user can do (accounts, uploads, posting); the rest is work for a
session.

Related: [STREAMING.md](STREAMING.md) (OBS, Twitch, restarts, titles), [CREDITS.md](CREDITS.md) (licences),
[launch/making-of.md](launch/making-of.md) (the post), [launch/uploads.md](launch/uploads.md) (the long videos).

## What has to be true on the night

- The station runs all night unattended, on YouTube and Twitch at once.
- Each YouTube part is saved (restarts at 00:00, 09:00, 19:00), and Twitch runs through the restarts.
- Anything bad can be taken off air in seconds (the kill switch), and the content filter is on.
- Every stream, Short, upload and post says the town is fictional and everything is written and voiced by AI.
- The channel has finished things to watch besides the stream: the promo, the making-of video, three
  documentaries and two full programmes ([launch/uploads.md](launch/uploads.md)).
- Nothing on air has a licence problem: no cartoons (MiniMax H3). (The Stable Audio bed was replaced by a
  code bed on 8 November.)

## Week 1: Sun 8 to Sun 15 November, accounts and the quality test

- [x] **You: create the Port Wexley channel** as a Brand Account under your Google account (YouTube →
      Settings → Add or manage your channel(s) → Create a channel), with its handle. Verify it
      (youtube.com/verify) and turn on live streaming: the first time can take up to 24 hours. Then tell a
      session the name and handle, to replace Cubes Channel (@cubes123) in the README and STREAMING.md.
      Created 15 November: **Port Wexley, @portwexley**, a Brand Account managed from the main Google account
      (the README links it; STREAMING.md never named the old channel). Channel ID `UClVRoxPUU-xM--79wcIYo0w`.
      Phone-verified the same evening (on Port Wexley itself: verification belongs to the channel that is active
      when it's done), and live streaming requested at 19:11, so it opens about 19:11 on Mon 16 November.
- [ ] **You: upload the promo to the new channel as the quality test.**
      `E:/recordings/2026-11-08 Channel 7 Promo - final 1440p.mp4`, **Unlisted**. Landscape uploads get a
      sparse quality ladder on YouTube; a 1440p upload should get the better encode, so check on the watch
      page that 1440p is offered and that Auto plays sharp on a desktop. Answer Yes to the altered-content
      question. Keep it unlisted until 20 December. The answer decides whether the long videos are upscaled
      to 1440p before upload ([launch/uploads.md](launch/uploads.md#preparing-each-file)).
      Uploaded 15 November ([watch page](https://youtu.be/zj5Z0-OFUYo), Unlisted, 248.5 s like the file): the
      player offers 1440p, 1080p and 720p. Left: Auto's sharpness full-screen on a desktop, and the
      altered-content answer.
- [x] **You: create a Twitch account** for the channel (the same name as the YouTube channel if it's free)
      and turn on **two-factor authentication** (Settings → Security and Privacy). Done 15 November:
      [twitch.tv/portwexley](https://www.twitch.tv/portwexley), with 2FA. Streaming goes by the stream key,
      not the login.
- [ ] **You: create a Ko-fi page** and turn on 2FA. Set its currency to **US dollars**: the API bills are in
      dollars, so the goal and the bill compare directly (decided 8 November). Link it to the payout account
      (Stripe or PayPal) now: the first payout check can take days. Converting to pounds on payout costs a
      little; allow for it when comparing the month.
      Made 15 November: [ko-fi.com/portwexley](https://ko-fi.com/portwexley), paid out to a PayPal Business
      account (an individual's, category Digital Goods Media, described as voluntary viewer tips, not
      donations). Left: 2FA and the US dollar currency to confirm, the page's About text (still Ko-fi's
      default), and the profile picture (`data/brand/port-wexley-avatar.png`).
- [ ] **You: turn on 2FA** on the Google account behind the YouTube channel and on GitHub, if not already.
      If the channel has never streamed, enable live streaming now: YouTube can take up to 24 hours to
      switch it on.
- [x] **Once Ko-fi exists, add `.github/FUNDING.yml`** to the repo, which puts a Sponsor button on the
      GitHub page:

      ```yaml
      ko_fi: <your-ko-fi-username>
      ```

      and replace the Ko-fi `TODO` in the README and the description templates. Done 15 November
      (`ko_fi: portwexley`; the README, STREAMING.md's templates, launch/uploads.md and launch/making-of.md).
- [x] **The cartoons are not part of the launch** (decided 8 November). The output isn't consistent enough
      yet; the licence comes when it is. The MiniMax H3 licence excludes the UK (and the EU, US and South
      Korea), so rendering or airing them from here needs MiniMax's approval, or another video model
      ([CREDITS.md](CREDITS.md#minimax-h3-ref2va-the-cartoons-entertainmentcartoonspy-not-on-air)).
- [ ] Check that the promo has no cartoon or H3 footage in it (it was cut from station recordings, so it
      shouldn't).

## Week 2: Mon 16 to Sun 22 November, the pieces land

- [x] The kill switch (`python -m newsroom.control testcard|air`, F12) and the content filter are
      committed (both are, since 8 November; on-screen text is checked too since the 9th). Try both on a
      `--scratch` run. Tried 16 November, two four-minute template runs (`NEWSROOM_LLM=off`, `NEWSROOM_CONTROL`
      on a temp file):
  - **Kill switch:** `testcard` at 10:37:41 cut Have Your Say mid-call to the test card ("We'll be back
    shortly") in the same second; `air` at 10:38:41 came back with the next slot, the cut call never resumed.
    No filler, no errors.
  - **Filter**, with "harbour" added in memory for the run: a template bulletin with the word was refused at
    the voice (`tts.synthesize`), marked failed and skipped on air, with no gap. **Found and fixed the same
    day:** a refused line in the station's own continuity (here the lost-property notice, "the Harbour
    Office") was retried every idle second, and since `continuity.bake_one` runs first in the idle work, the
    desk, the senior editor, adverts and specials never had a turn. Now a refused ident, card or notice is
    noted and not tried again that run, and so is a refused seed advert (checked whole before its owner is
    cast); a continuity slide's own words, its title too, are checked as well, since they are never voiced.
    Re-run the same way: each refused once, the desk and editors reached as usual.
  - **Found and fixed the same day:** `--scratch` didn't move `data/control.txt`, so F12 in a scratch
    window held a real station running at the same time. A scratch run now has its own `control.txt`,
    named in its first log line; set `NEWSROOM_CONTROL` to it to use `newsroom.control` on that run.
- [x] Stream restarts at `[stream] restart_at = ["00:00","09:00","19:00"]` are committed; a failed one is
      tried again at the next break ([STREAMING.md](STREAMING.md#stream-restarts-each-saved-part-under-12-hours)).
- [x] **A new music bed rendered in code** (`jingle.bed("vibes")`, 44.1 kHz stereo, 80 s), picked by ear on
      2026-11-08 over "lounge" and "strings"; it replaced the Stable Audio bed. Listen for it on the next
      night: under speech, on the cards and on the test card.
- [ ] **You: a private YouTube test stream through a restart.** Stream **Unlisted** for an hour or two
      across a restart time (or set `restart_at` to a time a few minutes ahead for the test), with Twitch
      running from the obs-multi-rtmp dock. Confirm:
  - [ ] YouTube Studio → Content → Live shows a **new** saved broadcast after the restart, and the old one
        is saved and processing;
  - [ ] Twitch carried on through the restart without a drop;
  - [ ] the restart's gap on air is a few seconds, at a bumper.

  Tried 16 November from 19:37 (`data/stream_test.cmd`: a scratch copy, `--clock 18:35 --minutes 70 --obs`),
  Unlisted on YouTube and on Twitch through the dock. **Found and fixed the same evening:** the restart never
  came, because Coastwide's bumper played at 18:59:26 and only a break at or after 19:00 counted; the next was
  The Inquiry's, after the run's end. Now a new programme opening up to five minutes early takes the restart.
  The restart itself was done by hand at 20:15:54 with `StreamDirector.restart()`: OBS stopped at once and
  streamed again at 20:16:00. Still to see on a run: the restart at a bumper by itself.
- [ ] Thu 19 November is a council night: watch *The Chamber* in the log the next day (no stream needed).
- [ ] **You: watch the launch shelf** ([launch/uploads.md](launch/uploads.md)): the three documentaries,
      *The Chamber* of 5 November and both *Last Ferry* candidates (5 and 6 November; keep the better one).
      Note anything that shouldn't go out. Swap in a reserve if one doesn't hold up.

## Week 3: Mon 23 to Sun 29 November, the public soak night

- [ ] **The soak night: Saturday 28 November**, from 18:30 to the next morning, **Public** on YouTube and
      live on Twitch, with no announcement. The point is to see the real thing with real (few) viewers.
  - [ ] Titles, descriptions and the altered-content setting as in [STREAMING.md](STREAMING.md#titles-and-descriptions).
  - [ ] **Test the kill switch on air once**: `testcard`, count the seconds until the stream shows the
        test card, then `air`. Note the time in the log.
  - [ ] The 00:00 and 09:00 restarts made new saved parts; Twitch ran all night.
  - [ ] Next day: review the night log as usual, plus the content filter's hits, chat (any problems a
        moderator would have had to deal with), and both platforms' stream health graphs.
- [ ] Fix what the soak night found before December.
- [ ] Pick the first week of Shorts from the soak night's saved parts and the November recordings.

## Week 4: Mon 30 November to Sun 6 December, Shorts begin

- [ ] **Tue 1 December: the first Short**, then **one a day** to Christmas Eve (24 in all). Cut with
      `tools/shorts.py`; **you** choose the moments. Every Short gets the disclosure line,
      the Pocket TTS credit and the altered-content Yes ([templates](STREAMING.md#titles-and-descriptions)).
      Schedule them a few days ahead in YouTube Studio so a missed day doesn't break the run.
- [ ] Vary them: a breaking-news cut-in, the fish auction on *Quayside*, a phone-in caller, a council vote,
      Vincent's monologue, Gordon's weather. (Not *Rock Pool*: children's television would have to be marked
      "made for kids".) YouTube judges the channel as a whole for "inauthentic content", and a
      run of near-identical clips is what that policy is about.
- [ ] Thu 3 December is a council night. Stream it publicly if the soak night went well: a second public
      night, and *The Chamber* is the best clip material of the fortnight.

## Week 5: Mon 7 to Sun 13 December, the making-of and the Christmas days

- [ ] Finish [launch/making-of.md](launch/making-of.md): fill the TODOs, check every number against the
      logs, and make the pictures (a screenshot grid, a 20-second clip or GIF).
- [ ] Christmas Eve, Christmas Day and Boxing Day are special days in `newsroom/christmas.py`. Run each on a
      scratch town with `--clock "2026-12-24 06:00"` (and 25th, 26th) and watch a few hours of each. Finish
      what's open there (the Christmas idents; the church has its art since 15 November).
- [ ] Channel pages: the YouTube banner, About text (the disclosure line first), links to Twitch, Ko-fi and
      GitHub; the Twitch About panels; the Ko-fi page text and a monthly goal of the running cost in dollars
      (**$60 a month**, the top of the $30-60 estimate; adjust once a month of real bills is in).
- [ ] Fill every `TODO` link in the README.
- [ ] **The long videos made ready** ([launch/uploads.md](launch/uploads.md#preparing-each-file)): trimmed,
      upscaled to 1440p if the promo test said so, thumbnails, chapters for *The Chamber*, titles and
      descriptions. **You: record the making-of video** (a screen recording of the station, the logs and the
      story board, in your voice), alongside the making-of post.
- [ ] **You: upload the launch shelf as Scheduled** for Sun 20 December, in two playlists: *Port Wexley
      Stories* and *Full programmes*.

## Alongside: the entertainment channel, if it's ready

A possible extra for launch, not a requirement (decided 8 November). Channel 7 launches on Christmas Eve
either way. **Go or no-go on Sunday 6 December**, so there's a week of polish before the station is
left on from 18 December.

- [ ] What it needs before it can be public ([../TODO.md](../TODO.md) under Content, [ENGINE.md](ENGINE.md)):
  - [x] *Wexley Wits*' own quiz set and its own ident (13 November, `e76b832`), with Channel 8's own logo,
        closedown and test card (`newsroom/channel.py`).
  - [x] **The rest of its evening** (13 to 24 November): 18:00 to 22:30, all its own programmes (*High Water*,
        *The Slipway*, *The Kettle's On*, *Wexley Wits*, *Marina Row*, *Tideline* or *The Coast Road*, and the
        TV movie, with *The Late News* after a short film), each with its own ident. The schedule is in
        [SHOWS.md](SHOWS.md#channel-8-wtv-evenings-only).
  - [x] **No cartoons**: *The Slipway*, a teen magazine, took Cartoon Time's half hour (19 November).
  - [x] A whole evening run and reviewed: on a scratch town (19 November) and on the real town, its first
        real night of the whole evening, the TV movie included (24 November, recordings reviewed on the 25th). The
        content filter covers it as it does Channel 7 (every line passes `safety` before it's voiced, the films'
        too).
  - [ ] **The kill switch tried on Channel 8** (`testcard`, then `air`), as on the soak night.
  - [ ] *The Late News* on a real night (only after a short film: *The Last Lot* in the draw), and its ident by
        ear.
- [ ] How it would go out:
  - [ ] **A second station process** (`--channel entertainment`) and a **second OBS** (a second instance,
        `obs64.exe --multi`, with its own profile, scene and stream keys); check the PC holds both
        stations' voicing (Pocket TTS on the CPU) and frame rate. **Not on the same town at once yet:** each
        station saves its whole world from memory, so two on one `data/world.json` overwrite each other
        ([../TODO.md](../TODO.md), "Two stations on one world"). Until that is fixed, the channels take turns.
  - [ ] **Where:** its own YouTube channel or the Port Wexley one, and Twitch (one Twitch channel streams
        one feed). Simplest first step: **scheduled evening blocks**, live only while its programmes are
        on, not 24 hours.
  - [ ] **Cost:** a second channel's scripts roughly double the model bill while it's on. Raise the Ko-fi
        goal to match before launch, not after.

## Week 6: Mon 14 to Sun 20 December, always on

- [ ] Thu 17 December is a council night, the last before launch.
- [ ] **From Fri 18 December, leave the station on.** Public on both platforms around the clock, so by
      launch night there are saved parts on the channel, a few days of Twitch history, and a week of
      real running to catch problems before visitors arrive.
- [ ] Watch the costs in `LLM USAGE` against $1-2 a day.
- [ ] **Sun 20 December: the launch shelf goes public** (scheduled the week before): the promo (set as the
      channel trailer, and linked from the stream descriptions), the making-of video, three documentaries,
      *The Chamber* and *The Last Ferry*.
- [ ] After launch: **one long video every Sunday** from 27 December, preferring the best of the latest week
      over the reserve list.

## Launch week: Mon 21 to Thu 24 December

- [ ] **The making-of post**, posted by **you** (nothing here posts anything):
  - **Tue 22 December, Show HN**, around 15:00 UK (mid-morning on the US east coast, when HN is busiest).
    Title along the lines of "Show HN: A 24-hour TV station for a town that doesn't exist". Link the
    GitHub repo; put the live link in the first comment.
  - **Wed 23 December, r/LocalLLaMA**: lead with the local-model side (Pocket TTS and Kokoro on the CPU,
    the model bench, the cost per night). Check the subreddit's self-promotion rules first.
  - **Thu 24 December, r/proceduralgeneration**: lead with the story desk and the town that remembers.
  - Answer comments for the first few hours of each; that matters more than the post.
- [ ] **Thu 24 December: launch night.**
  - [ ] Morning: back up `data/world.json` and the cache; check the restarts, the filter and the kill
        switch are set; GPU free; API keys present.
  - [ ] The Christmas Eve schedule is on air (`christmas.py`); not a council night.
  - [ ] A YouTube community post and a Twitch "going live" notification in the early evening, linking the
        live stream.
  - [ ] Stay with chat for the evening: answer, moderate, keep the kill switch at hand.
  - [ ] Then Christmas Day and Boxing Day, which are special days too.

## Expectations

- **The first goal is to cover the running costs**, about $1-2 a day ($30-60 a month) in API calls. Not
  wages, not the GPU, not the electricity.
- **Fan money comes first, ad money later.**
  - **Ko-fi**, in US dollars: one-off tips and monthly supporters, open from the first night, no thresholds.
    At $5 a month, six to twelve regular supporters cover the month before fees. The first perk to offer:
    supporters choose which town story gets a Sunday recap.
  - **Twitch**: subs and Bits need Affiliate, which needs a small following, some streamed hours over
    several days and a few average viewers ([check the current criteria](https://help.twitch.tv/s/article/joining-the-affiliate-program)).
    A 24-hour channel gets the hours and days quickly; the average viewers are the hard part. A sub pays
    the streamer roughly half of its price.
  - **YouTube ads** need the YouTube Partner Program. The thresholds last published (2023, not re-checked
    for this doc) are 1,000 subscribers plus either 4,000 public watch hours in 12 months or 10 million
    Shorts views in 90 days, with a lower tier that opens fan funding like memberships and Super Chat
    sooner; confirm them on [YouTube's YPP page](https://support.google.com/youtube/answer/72851). Only saved live parts count towards
    watch hours, which is why the restarts exist. Even inside the programme, ads on a small live stream
    pay little.
- **The channel is judged as a whole.** YouTube's "inauthentic content" policy looks at the whole channel
  for mass-produced, repetitive AI content. What sets Port Wexley apart is that it is one continuous made
  thing with a memory: stories that develop over days, recurring people, a schedule. Keep the Shorts hand-
  picked and varied, keep the disclosure everywhere, and let the making-of show the human work behind it.
- **Launch-day traffic is a spike.** Expect most visitors to come from the making-of post on its day and
  leave. The ones who stay are the ones who come back for a running story; that is the audience to build
  for.
