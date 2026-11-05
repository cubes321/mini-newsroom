"""The station's own log file (2026-11-05): the 11-04 night printed only to a window that was then
closed, so the morning's review had no log. Every run now writes data/logs/station-<date>-<time>.log."""
import logging
import sys
import threading

import pytest

from newsroom import __main__ as main


@pytest.fixture
def logs(tmp_path, monkeypatch):
    monkeypatch.setenv("NEWSROOM_LOGS", str(tmp_path / "logs"))
    root = logging.getLogger()
    before = list(root.handlers)
    hooks = sys.excepthook, threading.excepthook
    old_level = root.level
    root.setLevel(logging.INFO)
    yield tmp_path / "logs"
    for h in root.handlers[:]:
        if h not in before:
            root.removeHandler(h)
            h.close()
    sys.excepthook, threading.excepthook = hooks
    logging.captureWarnings(False)
    root.setLevel(old_level)


def test_a_run_writes_its_own_log_and_leaves_the_tts_chatter_out(logs):
    for noisy in main.NOISY:
        logging.getLogger(noisy).setLevel(logging.WARNING)
    path = main.log_to_file(started=1793872800.0)                 # 2026-11-05, mid-morning
    assert path.parent == logs and path.name.startswith("station-2026-11-05-") and path.suffix == ".log"
    logging.getLogger("newsroom.player").info("playing slot 2 bulletin [news] - 'Bonfire stack climbs'")
    logging.getLogger("pocket_tts.models.tts_model").info("starting timer now!")
    logging.getLogger("pocket_tts.models.tts_model").warning("a real problem")
    text = path.read_text(encoding="utf-8")
    assert "Bonfire stack climbs" in text and "a real problem" in text
    assert "starting timer now!" not in text


def test_a_crash_on_a_worker_thread_is_in_the_log(logs):
    path = main.log_to_file()

    def boom():
        raise RuntimeError("the writer fell over")
    t = threading.Thread(target=boom, name="writer-1")
    t.start()
    t.join()
    text = path.read_text(encoding="utf-8")
    assert "unhandled RuntimeError in thread writer-1" in text and "the writer fell over" in text


def test_a_scratch_run_logs_into_its_own_copy(monkeypatch, tmp_path):
    for var in ("NEWSROOM_WORLD", "NEWSROOM_LOGS", "NEWSROOM_ADS", "NEWSROOM_CACHE", "NEWSROOM_TIPLINE",
                "NEWSROOM_CONTINUITY", "NEWSROOM_LLM_CALLS"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("NEWSROOM_WORLD", str(tmp_path / "missing.json"))   # nothing big to copy
    monkeypatch.setenv("NEWSROOM_ADS", str(tmp_path / "no-ads"))
    monkeypatch.setattr(main.tempfile, "mkdtemp", lambda prefix: str(tmp_path / "scratch"))
    (tmp_path / "scratch").mkdir()
    main.redirect_paths(main.parse_args(["--scratch"]))
    assert main.os.environ["NEWSROOM_LOGS"] == str(tmp_path / "scratch" / "logs")
