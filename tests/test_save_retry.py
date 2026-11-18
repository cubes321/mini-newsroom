"""world.save while another program has world.json open (world.replace_file). A temp folder: no station."""
import json
import threading
from pathlib import Path

import pytest

from newsroom import world as world_mod


@pytest.fixture(autouse=True)
def quick(monkeypatch):
    monkeypatch.setattr(world_mod, "_backed_up", {})
    monkeypatch.setattr(world_mod.time, "sleep", lambda s: None)


def test_a_save_gets_through_once_a_reader_lets_go(tmp_path, monkeypatch):
    path = tmp_path / "world.json"
    w = world_mod.seed()
    world_mod.save(w, path)
    real = Path.replace
    tries = []

    def held(self, target):                   # the file held open for the first two goes, as Windows refuses it
        tries.append(1)
        if len(tries) <= 2:
            raise PermissionError(5, "Access is denied")
        return real(self, target)

    monkeypatch.setattr(Path, "replace", held)
    w.broadcast_day = 99
    world_mod.save(w, path)
    assert len(tries) == 3 and json.loads(path.read_text(encoding="utf-8"))["broadcast_day"] == 99


def test_a_file_held_for_good_still_fails_the_save(tmp_path, monkeypatch):
    path = tmp_path / "world.json"
    w = world_mod.seed()
    world_mod.save(w, path)

    def never(self, target):
        raise PermissionError(5, "Access is denied")

    monkeypatch.setattr(Path, "replace", never)
    with pytest.raises(PermissionError):
        world_mod.save(w, path)


def test_a_real_reader_holding_the_file(tmp_path, monkeypatch):
    """On Windows the open handle really does refuse the replace; elsewhere this passes at the first go."""
    monkeypatch.undo()                        # real sleeps: the reader lets go on a timer
    monkeypatch.setattr(world_mod, "_backed_up", {})
    path = tmp_path / "world.json"
    w = world_mod.seed()
    world_mod.save(w, path)
    reader = open(path, "rb")
    threading.Timer(0.2, reader.close).start()
    w.broadcast_day = 42
    world_mod.save(w, path)
    reader.close()
    assert json.loads(path.read_text(encoding="utf-8"))["broadcast_day"] == 42
