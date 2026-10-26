"""A presenter is never also one of the town's people, and removing a person can't make ids collide.

No model, no network.
"""
from newsroom import desk, world as world_mod


def test_a_presenter_is_not_added_as_a_resident():
    w = world_mod.seed()
    n = len(w.people)
    assert w.ensure_person("Gordon Pell", "resident") is None
    assert len(w.people) == n


def test_the_desk_skips_a_presenter_it_names():
    w = world_mod.seed()
    marjorie = w.person_by_name("Marjorie Pell")
    assert desk._resolve_people(w, ["Gordon Pell", "Marjorie Pell"]) == [marjorie.id]


def test_a_duplicate_presenter_is_removed_everywhere():
    w = world_mod.seed()
    # How the real town got one: an entry made before the guard existed.
    dupe = world_mod.Person(id=w._new_person_id(), name="Gordon Pell", role="resident", kind="resident",
                            voice="bm_george")
    w.people.append(dupe)
    t = w.seed_thread("Ghost tours", "known so far", "", [dupe.id, w.people[0].id])
    w.archive.append({"headline": "Gordon Pell turns forty", "people": [dupe.id], "thread_id": t.id})
    w.drop_presenter_people()
    assert w.person(dupe.id) is None
    assert t.people == [w.people[0].id] and w.archive[-1]["people"] == []


def test_new_ids_count_on_from_the_highest():
    w = world_mod.seed()
    last = w.people[-1].id
    w.people.pop(0)
    new = w.ensure_person("Rhona Day", "kayak instructor")
    assert new.id != last and int(new.id[1:]) == int(last[1:]) + 1
