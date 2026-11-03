"""The world is safe to share between workers and the player, and a special is archived when it airs.

No model, no TTS: a temp town (conftest.py).
"""
import json
import sys
import threading
import time

from newsroom import special, world as world_mod
from newsroom.buffer import Buffer
from newsroom.models import Line, Segment, SegmentState, SegmentType
from newsroom.workers import WorkerPool


def test_the_lock_is_not_saved(tmp_path):
    w = world_mod.seed()
    world_mod.save(w, tmp_path / "w.json")
    back = world_mod._from_dict(json.loads((tmp_path / "w.json").read_text(encoding="utf-8")))
    assert "lock" not in json.loads((tmp_path / "w.json").read_text(encoding="utf-8"))
    assert back.lock is not w.lock and back.lock.acquire(blocking=False)


def test_writers_readers_and_saves_at_once_lose_nothing(tmp_path):
    w = world_mod.seed()
    errors, n = [], 60

    def write(k):
        try:
            for i in range(n):
                tid = w.update_thread(None, f"story {k}-{i}", "known so far")
                w.ensure_person(f"Resident{k} Number{i}", "baker")
                w.record_aired("bulletin", f"headline {k}-{i}", tid, f"Resident{k} Number{i} spoke")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    def read():
        try:
            for i in range(n):
                w.summary_for_prompt()
                w.summary_for_editor()
                w.person_by_name("Marjorie Pell")
                if i % 10 == 0:
                    world_mod.save(w, tmp_path / "w.json")
        except Exception as e:  # noqa: BLE001
            errors.append(e)

    threads = [threading.Thread(target=write, args=(k,)) for k in range(3)] + [threading.Thread(target=read)
                                                                                for _ in range(2)]
    old = sys.getswitchinterval()
    sys.setswitchinterval(1e-6)              # switch threads constantly: without the lock, ids collide every time
    try:
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    finally:
        sys.setswitchinterval(old)
    assert errors == []
    ids = [p.id for p in w.people]
    assert len(ids) == len(set(ids))                       # no two new people got the same id
    assert sum(1 for p in w.people if p.name.startswith("Resident")) == 3 * n


def test_a_later_save_is_never_overwritten_by_an_earlier_snapshot(tmp_path, monkeypatch):
    """Saver A gets as far as the save lock and stalls there until saver B has taken its snapshot.
    With the snapshot outside the lock, A wrote the town it saw before B's change over B's file."""
    w, path = world_mod.seed(), tmp_path / "w.json"
    a_at_lock, b_snapped = threading.Event(), threading.Event()
    real_lock, real_to_dict = threading.Lock(), world_mod._to_dict

    class StallA:
        def __enter__(self):
            if threading.current_thread().name == "A":
                a_at_lock.set()
                b_snapped.wait(2)
            real_lock.acquire()

        def __exit__(self, *exc):
            real_lock.release()

    def to_dict(world):
        d = real_to_dict(world)
        if threading.current_thread().name == "B":
            b_snapped.set()
        return d

    monkeypatch.setattr(world_mod, "_SAVE_LOCK", StallA())
    monkeypatch.setattr(world_mod, "_to_dict", to_dict)
    a = threading.Thread(target=world_mod.save, args=(w, path), name="A")
    a.start()
    assert a_at_lock.wait(2)
    w.record_headline("Harbour wall reopens")
    b = threading.Thread(target=world_mod.save, args=(w, path), name="B")
    b.start()
    a.join(5), b.join(5)
    assert "Harbour wall reopens" in json.loads(path.read_text(encoding="utf-8"))["headlines"]


def test_shutdown_waits_for_a_worker_to_finish_its_job():
    pool = WorkerPool(Buffer(), world_mod.seed())
    finished = threading.Event()

    def job():
        pool.stop.wait()
        time.sleep(0.2)                      # the end of a job in hand
        finished.set()

    pool._threads = [threading.Thread(target=job, daemon=True)]
    pool._threads[0].start()
    pool.shutdown()
    assert finished.is_set()


def test_shutdown_gives_up_on_a_worker_that_will_not_finish(caplog):
    pool = WorkerPool(Buffer(), world_mod.seed())
    release = threading.Event()
    pool._threads = [threading.Thread(target=release.wait, name="worker-0", daemon=True)]
    pool._threads[0].start()
    t0 = time.monotonic()
    pool.shutdown(wait_s=0.2)
    assert time.monotonic() - t0 < 1.0
    assert "worker-0 still busy at exit" in caplog.text
    release.set()


def test_a_special_is_archived_when_it_airs():
    w = world_mod.seed()
    seg = Segment(slot_id=100_001, type=SegmentType.documentary, headline="Working title", state=SegmentState.ready,
                  work={"outline": {"title": "Same Ink, Same Harbour", "standfirst": "s", "intro": "i",
                                    "outro": "o", "sections": []}},
                  lines=[Line(speaker="anchor", text="Tonight, the cannery.")])
    before = len(w.archive)
    special.mark_aired(seg, w)
    assert len(w.archive) == before + 1 and w.archive[-1]["type"] == "special"
    assert w.archive[-1]["headline"] == "Same Ink, Same Harbour"
    assert w.headlines[-1] == "Special report: Same Ink, Same Harbour"


def test_a_second_part_waits_for_its_first():
    buf = Buffer()
    pool = WorkerPool(buf, world_mod.seed())
    first = Segment(slot_id=4, type=SegmentType.interview, show="late")
    cont = Segment(slot_id=6, type=SegmentType.interview, show="late", part="cont", work={"first_part": 4})
    buf.submit(first)
    assert pool._first_part_pending(cont)
    buf.mark(first, SegmentState.scripted)
    assert not pool._first_part_pending(cont)
    buf.mark(first, SegmentState.failed)
    assert not pool._first_part_pending(cont)              # a failed first part doesn't hold it up
