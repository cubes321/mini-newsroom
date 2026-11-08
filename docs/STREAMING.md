# Streaming Channel 7 on YouTube and Twitch

How to put Mini Newsroom on a YouTube live stream with OBS, with the same picture going to Twitch at the
same time. YouTube is OBS's own stream; Twitch is a second output from the obs-multi-rtmp plugin.

## Before the night

1. **Back up the town.** Every run writes the real `data/world.json`, the cache and the ad pool:

   ```powershell
   $stamp = Get-Date -Format yyyyMMdd-HHmm
   Copy-Item data\world.json "data\world.$stamp.json"
   Compress-Archive data\cache "data\cache.$stamp.zip"
   ```

2. **Picture size.** In `config.toml`, `[broadcast]`:

   ```toml
   width = 1920     # exactly 6x the 320x180 canvas, so the pixels stay square and sharp
   height = 1080
   fps = 30         # matches the stream; 60 only costs CPU
   ```

   If your monitor is 1080p, the window won't fit with its title bar. Use `1280 x 720` (4x) and let OBS scale it up to 1080p with the **Point** filter (see below).

3. **The model key.** The app routes to Claude (`ANTHROPIC_API_KEY`, a User environment variable). A terminal opened before the key was set won't have it:

   ```powershell
   $env:ANTHROPIC_API_KEY = [Environment]::GetEnvironmentVariable("ANTHROPIC_API_KEY", "User")
   ```

4. **Free the GPU** if Stable Audio 3 or ComfyUI is still loaded. The app itself runs Kokoro on the CPU, but the CPU is busy enough with voices.

## Run

```powershell
uv run python -m newsroom --log-llm
```

- Start it about five minutes before going live. The first bumper hides Kokoro's start-up, and the producer then fills ten minutes ahead.
- Leave `--debug` off; it draws a status line on the picture.
- `--clock HH:MM` starts the schedule at another time, for example `--clock 21:55` to open on the documentary slot and the late show.
- Breaking news on cue:

  ```powershell
  uv run python -m newsroom.tipline "BREAKING: ..."
  ```

- Esc or closing the window ends the run, and the world is saved on exit.

**The kill switch.** If something on air must come off now, hold the station on the test card:

```powershell
uv run python -m newsroom.control testcard    # off air at once; what was playing never resumes
uv run python -m newsroom.control air         # back on air
```

F12 in the station's window does the same. The stream keeps running on the test card, so neither YouTube nor
Twitch sees a drop. Test it on the soak night (`docs/LAUNCH.md`) before the public launch.

## OBS

**Scene and sources**
- Window Capture → "[python.exe]: Mini Newsroom".
  - Capture method: Windows 10 (1903 and up).
  - Untick "Capture Cursor".
- Right-click the source → Scale Filtering → **Point**, so the pixel art stays crisp if OBS resizes it.
- Fit it to the canvas with Transform → Fit to screen (Ctrl+F).
- Application Audio Capture → python.exe, for the station's sound only.
  - Mute Desktop Audio and the Mic in the mixer unless you want to talk over it.

**Settings**
- Video: Base and Output resolution 1920×1080, 30 fps.
- Output (Simple):
  - Video bitrate 6000 Kbps, audio 160 kbps.
  - Encoder: NVENC H.264, or x264 "veryfast" if the GPU is busy.
- Audio: 48 kHz. The app plays 24 kHz mono and OBS resamples it.
  - Keep the meter peaking around -6 dB. Bumpers and adverts are the loudest things.

**Recording each programme**
- `uv run python -m newsroom --obs` starts a new file in OBS's recording folder at each programme's
  bumper and stops it at the news, named like `2026-11-03 18-14 Rock Pool.mp4`.
- Turn on OBS's WebSocket server first (Tools → WebSocket Server Settings → Enable). The station reads the
  port and password from OBS's own config.
- If OBS isn't running, the station carries on without it and logs "obs: not recording". If OBS stops
  answering partway through, the programme on air isn't recorded, and recording picks up at the next bumper.
- Don't start a recording by hand as well: the next bumper stops it, names it after that programme and
  starts a new file.

**Silent recording** (record a night without hearing it)

Application Audio Capture records what python.exe plays, so muting python in the Windows mixer mutes the
recording too. Send the station's sound to a virtual cable instead:
1. Install VB-Audio Virtual Cable (vb-audio.com) and restart. It adds an output for the station to play
   into and an input ("CABLE Output") for OBS to record. Windows sometimes makes the cable its default
   output after the install, which silences everything else, so check Settings → Sound afterwards.
2. `uv run python -m newsroom --devices` lists the cable's output. Older versions call it
   "CABLE Input (VB-Audio Virtual Cable)". Newer ones call it "Speakers (VB-Audio Virtual Cable)", and also
   add a 16-channel "CABLE In 16 Ch", which you don't need. Windows may put a number in front of the name,
   as in "Speakers (2- VB-Audio Virtual Cable)".
3. Set `audio_device` under `[broadcast]` in `config.toml` to that name exactly as `--devices` prints it, or
   pass `--audio-device "<name>"` for one run. Any part of the name will do, but the first device that
   contains it wins: "VB-Audio" alone would pick the 16-channel one. If the name isn't found, the station
   plays on Windows' default output and logs a warning.
4. In OBS, swap Application Audio Capture for an Audio Input Capture of "CABLE Output", and keep Desktop
   Audio muted. Some versions call it "Microphone (VB-Audio Virtual Cable)" instead.
5. To listen in, set that source's Advanced Audio Properties → Audio Monitoring to "Monitor and Output".

## YouTube

YouTube is OBS's main output: Settings → Stream.

- Create → Go live → **Stream** (the stream-key tab, not "Manage").
- Visibility **Unlisted** for tests, so only people with the link can watch. **Public** from the soak night on.
- Copy the stream key into OBS → Settings → Stream (Service: YouTube - RTMPS).
- In the stream's settings, leave **Auto-start** and **Auto-stop** on. Auto-stop is what ends one saved
  broadcast when OBS stops streaming, so the next start opens a new one (see the restarts below).
- Turn on live chat for the comments. Turn latency to "Low" so replies to the chat feel live.
- **Altered or synthetic content.** Answer **Yes** to YouTube's question about altered or synthetic content
  (labelled "Altered content", or "AI use" under Attributes in newer versions of YouTube Studio). Set it in
  the stream's details before going live, and check it on each saved part afterwards (Studio → Content →
  Live). Strictly, YouTube asks for disclosure when content "seems realistic", and a pixel-art town might not
  qualify, but the voices are realistic synthetic speech and YouTube judges a channel as a whole for
  "inauthentic content", so being open about it is the safe side. YouTube's help page says disclosing AI
  content alone "won't limit a video's audience or impact its eligibility to earn money"
  ([Disclosing use of altered or synthetic content](https://support.google.com/youtube/answer/14328491)).
  The disclosure line also goes at the top of every description (templates below); the DramaBox and DeepSeek
  licences require that anyway (`docs/CREDITS.md`).
- Send your friends the watch link once YouTube shows "Excellent connection".

## Stream restarts: each saved part under 12 hours

YouTube may not save a live stream that runs longer than 12 hours, and a stream that isn't saved stays off
the channel afterwards and doesn't count towards the Partner Programme's watch hours. So the station stops
and restarts OBS's stream (YouTube only) three times a day, and every saved broadcast is a part of the day
under 12 hours:

| restart | part | length | what it holds |
|---|---|---|---|
| 00:00 | overnight to breakfast | 9 h | test card, repeats, SEVENTEXT, *Morning Tide* |
| 09:00 | the daytime | 10 h | the news, *Have Your Say*, *Quayside*, *Out and About*, *Rock Pool*, *Full Time* |
| 19:00 | the evening | 5 h | *Coastwide*, *The Inquiry* or *The Chamber*, *The Panel*, the documentary, *The Last Ferry*, the late news |

The times sit on programme changes, so a saved part opens on a bumper and the gap of a few seconds falls
where nothing is lost. The evening part is the short one on purpose: it is the best of the day and the
easiest to clip for Shorts.

**Being built** by another session: the schedule goes in `config.toml` as

```toml
[stream]
restart_at = ["00:00", "09:00", "19:00"]
```

and the station asks OBS (through the WebSocket server, as `--obs` does) to stop and start its stream at
those times. Until that lands, there are no automatic restarts.

**Check before launch** (a private test stream, `docs/LAUNCH.md`): after a restart, YouTube Studio → Content →
Live should show a **new** saved broadcast, and the old one should be processing. If the restart reconnects
into the same broadcast instead, check that Auto-stop is on, and that the gap is long enough for YouTube to
notice the end (YouTube waits a little before ending a broadcast; the restart may need a longer pause).

## Twitch, through obs-multi-rtmp

OBS sends one stream on its own. The [obs-multi-rtmp](https://github.com/sorayuki/obs-multi-rtmp) plugin adds
more outputs in a dock, each with its own server, key and (optionally) encoder.

1. Install the plugin for your OBS version from its GitHub releases page, and restart OBS. The dock is
   called "Multiple output"; if it doesn't show, Docks → Multiple output.
2. In the Twitch dashboard: Settings → Stream → copy the **Primary Stream key**. Keep it private.
3. In the dock: **Add new target**.
   - Name: Twitch.
   - Server: `rtmp://live.twitch.tv/app` (or the nearest ingest from Twitch's list).
   - Key: the Twitch stream key.
   - **Untick "Sync start with OBS"** (some versions say "sync start/stop"). This is the important setting.
     Synced, the Twitch output starts and stops with OBS's own stream, so every YouTube restart would drop
     Twitch as well. Unsynced, Twitch runs on through the restarts. A forum report says the tick can come
     back after OBS restarts, so check it each time OBS opens.
   - Encoder: give Twitch **its own** encoder rather than sharing OBS's (NVENC H.264, 6000 Kbps CBR,
     keyframe interval 2 s, audio AAC 160 kbps). A shared encoder belongs to the YouTube output and may stop
     with it at a restart.
4. Start Twitch from the dock's **Start** button after OBS's own Start Streaming. They are now independent:
   OBS's button (and the station's restarts) only touches YouTube.
5. **Twitch ends any single broadcast at 48 hours.** Restart the Twitch output by hand once a day at a
   quiet moment (Stop, then Start in the dock), for example at the morning check after 09:00, so the cut
   never happens unattended in the middle of a programme. Twitch doesn't have the 12-hour question: its
   past broadcasts are saved as VODs for 7 days (longer for Affiliates and Partners), and Highlights stay.

**Twitch settings**
- Category: look for an **Always On** (or similar 24/7) category; a vendor guide says Twitch has had one
  since 2017, but that wasn't checked. Otherwise **Just Chatting**. Tags, up to ten: `AI`, `24Hours`,
  `PixelArt`, `News`, `English`, `British`, `Cozy`, `Chill`.
- Turn on "Store past broadcasts" (Settings → Stream → VOD Settings), so clips can be made from them.
- Don't mark the stream as a rerun: the station is live, written as it airs. The overnight block (about six
  hours of the day's segments replayed) is the grey area, since Twitch's rerun rule is about prerecorded
  content presented as live. It's a judgement call, and what makes it defensible is the on-screen repeat
  label and the published schedule; keep both.
- Affiliate needs a small following, some hours streamed on several days and a few average viewers: check
  the current numbers at sign-up ([Joining the Affiliate Program](https://help.twitch.tv/s/article/joining-the-affiliate-program)).

## Titles and descriptions

Every title or description carries the disclosure line, and every description the Pocket TTS credit.
`docs/CREDITS.md` has the full credits block. Replace `TODO` with the real links.

**YouTube live stream** (copied to each saved part by YouTube; add the date range to a saved part's title
afterwards if you like)

```text
Title (max 100 characters):
Channel 7 LIVE · Port Wexley, an AI-run TV station for a town that doesn't exist · 24/7

Description:
Port Wexley is a fictional town. Every programme is written and voiced by AI.

Channel 7 is Port Wexley's local TV station, on air around the clock: breakfast on the sofa, the news,
a phone-in, the fish quay's prices, children's TV with a seagull puppet, local sport, the evening
magazine, a late-night talk show, a nightly documentary and, every other Thursday, the town council
live. Stories run for days, the same people come back, and the foot ferry runs to the tides.

Today's schedule: 06:00 Morning Tide · 10:00 Have Your Say · 13:00 Quayside · 15:00 Out and About ·
16:00 Rock Pool · 18:45 Full Time · 19:00 Coastwide · 20:00 The Inquiry · 20:30 The Panel ·
21:00 the news and Port Wexley Stories · 22:00 The Last Ferry · the news in between (UK time).

Also live on Twitch: TODO
Support the station (it costs about $1-2 a day to run): TODO (Ko-fi)
How it's made, and the code: https://github.com/cubes321/mini-newsroom

Voices: Pocket TTS by Kyutai (CC BY 4.0, https://huggingface.co/kyutai/pocket-tts) and Kokoro-82M (Apache 2.0).
Scripts: Claude and DeepSeek. Full credits: https://github.com/cubes321/mini-newsroom/blob/master/docs/CREDITS.md
```

**Twitch**

```text
Title (max 140 characters):
Channel 7 LIVE 24/7 · AI-written local TV for Port Wexley, a town that doesn't exist (fictional, written and voiced by AI)

About panel (a panel under the stream):
Port Wexley is a fictional town. Every programme is written and voiced by AI.
[the same "Channel 7 is..." paragraph and schedule as YouTube]
Voices: Pocket TTS by Kyutai (CC BY 4.0) and Kokoro-82M (Apache 2.0). Full credits: [CREDITS.md link]
Support: TODO (Ko-fi)
```

**Shorts** (one moment from a saved part or a recording; `tools/shorts.py` is being built to cut them)

```text
Title (max 100 characters; the moment first):
The mayor has had enough of the gulls 😤 | Channel 7, Port Wexley #shorts

Description:
Port Wexley is a fictional town; written and voiced by AI.
From <programme>, <date>. Channel 7 is live around the clock: TODO (live link)
Voices: Pocket TTS by Kyutai (CC BY 4.0). Credits: https://github.com/cubes321/mini-newsroom/blob/master/docs/CREDITS.md
#AI #PixelArt #LocalNews #PortWexley
```

For a Short, answer the altered-content question **Yes** at upload as well. Keep the title about the moment
("the ferry is cancelled again"), not about the AI: the disclosure is in the description and the label.

## If something goes wrong

- **Something on air that shouldn't be.** `uv run python -m newsroom.control testcard` (or F12), then look.
- **A frozen or blank picture.** OBS stopped capturing the window, which happens when it is minimised. Keep the window open behind OBS, not minimised.
- **Silence with the picture moving.** Check that Application Audio Capture still points at python.exe. It loses the process if the app restarts.
- **"We'll be right back" for a long time.** The model calls are failing; check the terminal.
  - Channel 7 fills a gap with adverts and idents first, then the card.
  - A restart keeps the town (the world is saved), and the first bumper covers the start.
- **Twitch dropped at a YouTube restart.** "Sync start with OBS" is ticked on the Twitch target, or Twitch
  shares OBS's encoder. Untick it, give Twitch its own encoder, and start it again from the dock.
- **Twitch stuck on "stopping"** in the dock. Forum reports describe this after Twitch drops a connection.
  Restart OBS (the YouTube part is saved, and the station keeps running), then start both again.
