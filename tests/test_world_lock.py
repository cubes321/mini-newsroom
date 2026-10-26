"""The world is safe to share between workers and the player, and a special is archived when it airs.

No model, no TTS: a temp town (conftest.py).
"""
import json
import sys
import threading

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
