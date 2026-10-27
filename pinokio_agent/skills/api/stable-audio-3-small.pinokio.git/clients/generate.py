"""Text-to-audio (optionally from init audio) against a running Stable Audio 3 Gradio app.

    uv run --with gradio_client --with soundfile python generate.py --url <base> --prompt "..." --seconds 6 \
        --out take.wav [--init motif.wav --noise 0.7] [--seed 7] [--steps 8] [--cfg 1.0]

Prints the path written. The base URL comes from the launcher's status at run time.
"""
import argparse
from pathlib import Path

import soundfile as sf
from gradio_client import Client, handle_file


def generate(url: str, prompt: str, seconds: float, out: Path, init: Path | None = None,
             noise: float = 0.9, seed: int = -1, steps: int = 8, cfg: float = 1.0,
             negative: str = "") -> Path:
    client = Client(url, verbose=False)
    result = client.predict(
        prompt=prompt,
        negative_prompt=negative,
        seconds_total=int(round(seconds)),
        cfg_scale=cfg,
        steps=steps,
        seed=seed,
        file_format="wav",
        file_naming="output.wav",
        cut_to_seconds_total=False,   # the app's own cut fails on a float length; cut below
        init_audio=handle_file(str(init)) if init else None,
        init_noise_level=noise,
        batch_size=1,
        api_name="/generate",
    )
    audio = result[0] if isinstance(result, (list, tuple)) else result
    if isinstance(audio, dict):
        audio = audio.get("path") or audio.get("value")
    out.parent.mkdir(parents=True, exist_ok=True)
    data, sr = sf.read(audio, always_2d=True)
    sf.write(out, data[: int(seconds * sr)], sr, subtype="PCM_16")
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", required=True)
    ap.add_argument("--prompt", required=True)
    ap.add_argument("--negative", default="")
    ap.add_argument("--seconds", type=float, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--init", type=Path)
    ap.add_argument("--noise", type=float, default=0.9)
    ap.add_argument("--seed", type=int, default=-1)
    ap.add_argument("--steps", type=int, default=8)
    ap.add_argument("--cfg", type=float, default=1.0)
    a = ap.parse_args()
    print(generate(a.url, a.prompt, a.seconds, a.out, a.init, a.noise, a.seed, a.steps, a.cfg, a.negative))


if __name__ == "__main__":
    main()
