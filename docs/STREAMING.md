# Streaming Channel 7 on YouTube

How to put a night of Mini Newsroom on a YouTube live stream with OBS.

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

**YouTube**
- Create → Go live → Stream.
- Visibility **Unlisted**, so only people with the link can watch.
- Copy the stream key into OBS → Settings → Stream (Service: YouTube - RTMPS).
- Turn on live chat for the comments. Turn latency to "Low" so replies to the chat feel live.
- Send your friends the watch link once YouTube shows "Excellent connection".

## If something goes wrong

- **A frozen or blank picture.** OBS stopped capturing the window, which happens when it is minimised. Keep the window open behind OBS, not minimised.
- **Silence with the picture moving.** Check that Application Audio Capture still points at python.exe. It loses the process if the app restarts.
- **"We'll be right back" for a long time.** The model calls are failing; check the terminal.
  - Channel 7 fills a gap with adverts and idents first, then the card.
  - A restart keeps the town (the world is saved), and the first bumper covers the start.
