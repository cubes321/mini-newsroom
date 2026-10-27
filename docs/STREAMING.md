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
