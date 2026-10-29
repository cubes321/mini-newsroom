"""Make Channel 7's music stems in assets/music/ from the motif (jingle.py) and Stable Audio 3.

Offline, run by hand; assets.py bakes the bumpers, sting and bed from whatever stems are here.

    python -m newsroom.station_audio --news synth            # the news ident from a code voicing
    python -m newsroom.station_audio --news take.wav         # ...or from an approved SA3 take
    python -m newsroom.station_audio --bed bed.wav           # an approved bed, looped
    python -m newsroom.station_audio --bed-takes DIR --url http://127.0.0.1:7860   # SA3 bed takes to audition
    python -m newsroom.station_audio --band                  # The Last Ferry's house band stings

The other shows' idents and the breaking sting come from their code voicings unless a file is
given (--breakfast, --magazine, --late, --sport, --breaking). Stems are written at 24 kHz mono, the
mixer's own format. SA3 is called through the Pinokio app's Gradio API (`gradio_client` is not
a project dependency: run --bed-takes with `uv run --with gradio_client`).
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import numpy as np
import soundfile as sf

from . import jingle
from .config import CONFIG

log = logging.getLogger(__name__)

SR = CONFIG.tts.sample_rate
MUSIC = CONFIG.paths.assets / "music"
PEAK = 0.89
FADE_S = 0.4
LOOP_XFADE_S = 3.0
SHOWS = ("breakfast", "magazine", "late", "sport", "breaking")     # the voicings besides the news

BED_PROMPT = ("1970s British television continuity music, light and warm, gentle {style}, "
              "in C major, 100 BPM, steady, no vocals, loopable background bed")


def to_stem(audio: np.ndarray, sr: int, fade: bool = True) -> np.ndarray:
    """Mono, resampled to SR, peak-normalised, with a short fade out."""
    mono = audio.mean(axis=1) if audio.ndim == 2 else audio
    if sr != SR:
        n = int(round(len(mono) * SR / sr))
        mono = np.interp(np.arange(n) * sr / SR, np.arange(len(mono)), mono)
    mono = mono / (np.abs(mono).max() or 1.0) * PEAK
    if fade:
        f = int(SR * FADE_S)
        mono[-f:] *= np.linspace(1, 0, f)
    return mono.astype(np.float32)


def loop(audio: np.ndarray, sr: int) -> np.ndarray:
    """Fold the tail into the head so the end runs straight back into the start."""
    x = int(sr * LOOP_XFADE_S)
    out = audio[:-x].copy()
    ramp = np.linspace(0, 1, x)
    if audio.ndim == 2:
        ramp = ramp[:, None]
    out[:x] = audio[:x] * ramp + audio[-x:] * (1 - ramp)
    return out


def write(name: str, audio: np.ndarray) -> Path:
    MUSIC.mkdir(parents=True, exist_ok=True)
    path = MUSIC / f"{name}.wav"
    sf.write(path, audio, SR, subtype="PCM_16")
    log.info("wrote %s (%.1f s)", path, len(audio) / SR)
    return path


def _source(arg: str | None, voicing: str, style: str | None = None) -> np.ndarray:
    """A file if `arg` names one, else the code render (with `arg` as the news style)."""
    if arg and Path(arg).exists():
        audio, sr = sf.read(arg, always_2d=True)
        return to_stem(audio, sr)
    return to_stem(jingle.render(voicing=voicing, style=arg or style), jingle.SR)


def bed_takes(url: str, out: Path, styles: list[str], seconds: int = 90, seed: int = 7) -> list[Path]:
    from gradio_client import Client

    client = Client(url, verbose=False)
    paths = []
    for i, style in enumerate(styles):
        res = client.predict(prompt=BED_PROMPT.format(style=style), negative_prompt="vocals, drums solo",
                             seconds_total=seconds, cfg_scale=1.0, steps=8, seed=seed + i,
                             file_format="wav", file_naming="output.wav", cut_to_seconds_total=False,
                             init_audio=None, batch_size=1, api_name="/generate")
        audio, sr = sf.read(res[0], always_2d=True)
        path = out / f"bed_{i}_{style.split()[0]}.wav"
        out.mkdir(parents=True, exist_ok=True)
        sf.write(path, loop(audio[: seconds * sr], sr), sr, subtype="PCM_16")
        paths.append(path)
    return paths


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--news", help=f"a WAV, or a code style: {', '.join(jingle.NEWS_STYLES)}")
    for show in SHOWS:
        ap.add_argument(f"--{show}", help="a WAV instead of the code voicing")
    ap.add_argument("--bed", help="an approved bed WAV (looped already by --bed-takes)")
    ap.add_argument("--bed-takes", type=Path, help="write SA3 bed takes here to audition")
    ap.add_argument("--styles", default="vibraphone and Rhodes;analog synthesizer;string orchestra",
                    help="bed styles for --bed-takes, separated by ;")
    ap.add_argument("--url", default="http://127.0.0.1:7860")
    ap.add_argument("--band", action="store_true",
                    help="The Last Ferry's house band: band_walkon and band_button from jingle.band")
    args = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    if args.bed_takes:
        for p in bed_takes(args.url, args.bed_takes, args.styles.split(";")):
            print(p)
        return
    if args.news:
        write("ident_news", _source(args.news, "news"))
        for show in SHOWS:
            write("breaking" if show == "breaking" else f"ident_{show}", _source(getattr(args, show), show))
    if args.bed:
        audio, sr = sf.read(args.bed, always_2d=True)
        write("bed", to_stem(audio, sr, fade=False))
    if args.band:                       # chosen by ear 2026-10-27: walkon for a new guest, button after a break
        for kind in ("walkon", "button"):
            write(f"band_{kind}", to_stem(jingle.band(kind), jingle.SR))


if __name__ == "__main__":
    main()
