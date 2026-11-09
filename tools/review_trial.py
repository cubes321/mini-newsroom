"""A review made for real on a copy of the town, without the station: to read and hear one before it airs.

    uv run python tools/review_trial.py                          # the week, as at the town's last day, 18:30
    uv run python tools/review_trial.py --clock "2026-11-15 18:30"
    uv run python tools/review_trial.py --kind year --out data/review-trial/year
    uv run python tools/review_trial.py --notes                  # only the notes the writers would get: no model

The world is copied to a temp folder and the clock set (by default to 18:30 on the town's last day, when
the worker would book it). The annals' pages still missing for the days before are written there, reading
the real cache for their keepsakes. Then the review is commissioned and made, stage by stage, with the
real model (the documentary's routes) and the real voices. Everything it writes goes to the temp folder:
its script and audio, the world's saves, the model call log. The real data/ is only read.

In `--out` (data/review-trial/<date>-<kind> by default, not in git):
  <kind>-in-review.md     the research notes it was given, then the script, section by section
  <kind>-in-review.wav    the whole piece in one file, to listen to
  <kind>-in-review.json   the segment as the station would air it

About six minutes and a few pence for a week. It needs the back office's key in the environment
(DEEPSEEK_API_KEY, or ANTHROPIC_API_KEY with `--route deepseek_flash_think=claude_sonnet`).
"""
from __future__ import annotations

import argparse
import dataclasses
import json
import logging
import os
import shutil
import sys
import tempfile
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--kind", choices=("week", "year"), default="week")
    ap.add_argument("--clock", default="", help='"YYYY-MM-DD HH:MM"; default: 18:30 on the town\'s last day')
    ap.add_argument("--out", default="", help="where the script and audio go (default data/review-trial/<date>-<kind>)")
    ap.add_argument("--route", default="", help="as the station's --route, e.g. deepseek_flash_think=claude_sonnet")
    ap.add_argument("--notes", action="store_true", help="print the research notes and stop: no model, no voices")
    a = ap.parse_args(argv)

    data = ROOT / "data"
    scratch = Path(tempfile.mkdtemp(prefix="newsroom-review-trial-"))
    shutil.copy2(data / "world.json", scratch / "world.json")
    if (data / "annals").exists():
        shutil.copytree(data / "annals", scratch / "annals")
    for key, name in (("NEWSROOM_WORLD", "world.json"), ("NEWSROOM_ANNALS", "annals"), ("NEWSROOM_LLM_CALLS", "llm_calls"),
                      ("NEWSROOM_CONTINUITY", "continuity"), ("NEWSROOM_ADS", "ads"), ("NEWSROOM_TIPLINE", "tipline.txt"),
                      ("NEWSROOM_CONTROL", "control.txt"), ("NEWSROOM_PICTURES_DIR", "pictures")):
        os.environ[key] = str(scratch / name)
    os.environ["NEWSROOM_LLM_LOG"] = "1"
    os.environ["NEWSROOM_REVIEW"] = a.kind
    os.environ.pop("NEWSROOM_LLM", None)
    if a.route:
        os.environ["NEWSROOM_ROUTES"] = a.route
    sys.path.insert(0, str(ROOT))
    os.chdir(ROOT)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s: %(message)s", datefmt="%H:%M:%S")
    for noisy in ("httpx", "httpx2", "httpcore", "httpcore2", "openai", "urllib3", "kokoro", "phonemizer", "pocket_tts",
                  "anthropic"):
        logging.getLogger(noisy).setLevel(logging.WARNING)
    log = logging.getLogger("review_trial")

    from newsroom import schedule

    last = json.loads((scratch / "world.json").read_text(encoding="utf-8")).get("last_date") or date.today().isoformat()
    schedule.set_clock(a.clock or f"{last} 18:30")

    from newsroom import annals, documentary, llm, review, special
    from newsroom import world as world_mod
    from newsroom.config import CONFIG
    from newsroom.models import SegmentState

    real = CONFIG.paths
    assert real.world == scratch / "world.json" and real.annals == scratch / "annals", real
    # What the review writes goes to the temp cache; the annals alone read the real one, for their keepsakes.
    object.__setattr__(CONFIG, "paths", dataclasses.replace(real, cache=scratch / "cache"))
    (scratch / "cache").mkdir()
    annals.CONFIG = dataclasses.replace(CONFIG, paths=dataclasses.replace(CONFIG.paths, cache=real.cache))

    w = world_mod.load()
    log.info("the town's day is %s; everything is written under %s", w.last_date, scratch)
    while annals.tick(w):
        pass
    kind = review.tonight(w)
    if kind is None:
        print(f"nothing to review: no day on the page for the {a.kind} to {w.last_date}")
        return 1

    if a.notes:                                        # what the writers would be given, and no more
        research, clips = review.notes(w, kind)
        seg = review.commission(w, kind)
        seg.work.update(research=research.model_dump(), clips=clips)
        print(documentary.notes_for_prompt(seg) + "\n\n" + (documentary.clips_for_prompt(seg) or "(no archive clips)"))
        return 0

    t0 = time.time()
    seg = review.commission(w, kind)
    stages, notes = [], ""
    while seg.state is not SegmentState.ready:
        stages.append(seg.stage)
        if seg.stage == "outline":
            notes = documentary.notes_for_prompt(seg) + "\n\n" + (documentary.clips_for_prompt(seg) or "(no archive clips)")
        seg = special.advance(seg, w, None)
    took = time.time() - t0

    out = Path(a.out) if a.out else data / "review-trial" / f"{w.last_date}-{kind}"
    out.mkdir(parents=True, exist_ok=True)
    stem = f"{kind}-in-review"
    outline, starts = seg.work["outline"], seg.work["starts"]
    names = {c.id: c.name for c in w.characters}
    md = [f"# {seg.work['strand']}: {outline['title']}", "", f"*{outline['standfirst']}*", "",
          f"A trial made {time.strftime('%Y-%m-%d %H:%M')}, with the clock at {a.clock or last + ' 18:30'}: "
          f"{len(seg.lines)} lines, {seg.duration_s / 60:.1f} minutes of audio, {took / 60:.1f} minutes to make "
          f"({', '.join(f'{s} x{stages.count(s)}' for s in dict.fromkeys(stages))}).", "",
          "## The research notes (from the annals, in code)", "", "```", notes, "```", "", "## The script", ""]
    for i, line in enumerate(seg.lines):
        if i in starts:
            sec = outline["sections"][starts.index(i)]
            md += ["", f"### {starts.index(i) + 1}. {sec['heading']}", "",
                   f"*Backdrop {sec['backdrop']}; guest {sec.get('guest_name') or 'none'}; clip "
                   f"{sec.get('archive_clip') or 'none'}. Beats: {'; '.join(sec['beats'])}*", ""]
        who = line.guest_name or names.get(line.speaker, line.speaker)
        md += [f"**{who}**{f' [{line.archive}]' if line.archive else ''}: {line.text}", ""]
    md += ["## Model use", "", "```", llm.usage_summary(), "```"]
    (out / f"{stem}.md").write_text("\n".join(md), encoding="utf-8")
    (out / f"{stem}.json").write_text(seg.model_dump_json(indent=1), encoding="utf-8")

    try:                                               # one file to listen to, a short breath between lines
        import numpy as np
        import soundfile as sf

        sr, parts = None, []
        for line in seg.lines:
            audio, rate = sf.read(str(line.wav_path), dtype="float32")
            if audio.ndim > 1:
                audio = audio.mean(axis=1)
            sr = sr or rate
            if rate != sr:
                audio = np.interp(np.linspace(0, len(audio) - 1, int(len(audio) * sr / rate)), np.arange(len(audio)), audio)
            parts += [audio.astype("float32"), np.zeros(int(sr * 0.25), dtype="float32")]
        sf.write(str(out / f"{stem}.wav"), np.concatenate(parts), sr, subtype="PCM_16")
    except Exception as e:  # noqa: BLE001
        log.warning("could not stitch the audio into one file: %s", e)

    print(json.dumps({"title": outline["title"], "sections": [s["heading"] for s in outline["sections"]],
                      "lines": len(seg.lines), "minutes": round(seg.duration_s / 60, 1),
                      "made_in_min": round(took / 60, 1), "clips": [l.archive for l in seg.lines if l.archive],
                      "out": str(out), "scratch": str(scratch)}, indent=1, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
