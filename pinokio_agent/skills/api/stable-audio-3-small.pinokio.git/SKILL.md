---
name: api-stable-audio-3
description: Generate music or sound effects (text-to-audio, or restyling an init audio clip) with the Stable Audio 3 Pinokio app's Gradio API.
---

# Stable Audio 3 API

## Clients
- `clients/generate.py`: one call to the `/generate` endpoint; copies the returned file to `--out`.
  Run with `uv run --no-project --with gradio_client --with soundfile python clients/generate.py ...` (gradio_client is not an app dependency).

## Operations
- `/generate` (keyword arguments): `prompt`, `negative_prompt`, `seconds_total`, `cfg_scale` (1.0), `steps` (8),
  `seed` (-1 random), `sampler_type` ("pingpong"), `file_format` ("wav" …), `file_naming` ("output.wav"),
  `cut_to_seconds_total`, `init_audio` (a file via `handle_file`), `init_noise_level` (0.9 default; lower keeps
  more of the init audio), `batch_size`. Returns (audio filepath, spectrogram gallery).
- `/gradio_api/info` lists the full schema; check it again if a call fails with 400/422.

## Runtime Inputs
- The base URL of the running app; which model it serves depends on the start option (Small Music, Small SFX,
  Medium). Medium is the higher-quality music model and needs an NVIDIA GPU (about 6 GB peak).

## Outputs
- 44.1 kHz stereo WAV for the wav format.

## Notes
- The app's own `cut_to_seconds_total` fails when `seconds_total` arrives as a float: send an int and cut the file client-side.
- Steps 8 and CFG 1.0 are the distilled defaults; more steps rarely help.
