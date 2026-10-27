"""A --scratch run keeps everything it writes in its temp folder, the --log-llm call log too:
the 2026-10-26 documentary check wrote its 65 Claude calls into the real data/llm_calls.

CONFIG is built when newsroom.config is first imported, so this runs in a fresh interpreter.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROBE = """
import json, sys
from newsroom.__main__ import parse_args, redirect_paths
redirect_paths(parse_args(["--scratch", "--log-llm"]))
from newsroom.config import CONFIG
print(json.dumps({k: str(getattr(CONFIG.paths, k)) for k in ("world", "cache", "tipline", "ads", "llm_calls")}))
"""


def test_a_scratch_run_logs_its_calls_in_its_own_folder():
    env = {k: v for k, v in os.environ.items() if not k.startswith("NEWSROOM_")}
    out = subprocess.run([sys.executable, "-c", PROBE], cwd=ROOT, env=env, capture_output=True, text=True, check=True)
    paths = {k: Path(v) for k, v in json.loads(out.stdout.strip().splitlines()[-1]).items()}
    scratch = paths["world"].parent
    try:
        assert scratch.name.startswith("newsroom-scratch-")
        assert paths["llm_calls"] == scratch / "llm_calls"
        assert all(p.is_relative_to(scratch) for p in paths.values())
    finally:
        if scratch.name.startswith("newsroom-scratch-"):
            shutil.rmtree(scratch, ignore_errors=True)
