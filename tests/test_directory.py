"""The business directory the advert writer draws on: known businesses come back with fresh adverts, new ones
are invented now and then and join it, and nobody is handed a trade that isn't theirs.

Kokoro and the model are stubbed: no audio is synthesised, no network.
"""
import random

import pytest

from newsroom import adverts, directory, llm, world as world_mod
from newsroom.locations import BACKDROP_IDS
from newsroom.models import AdvertScript
from newsroom.tts import SynthResult


@pytest.fixture
def pool(tmp_path, monkeypatch):
    def synth(text, voice, out, speed=1.0, lang=None):
        out.write_bytes(b"RIFF")
        return SynthResult(wav_path=out, duration_s=len(text.split()) / 2.5, mouth_env=[0.5])
    monkeypatch.setattr(adverts.tts, "synthesize", synth)
    p = adverts.AdPool(tmp_path / "ads")
    monkeypatch.setattr(adverts, "_pool", p)
    monkeypatch.setattr(adverts, "_last_try", 0.0)
    return p


@pytest.fixture
def world():
    return world_mod.seed()


def _script(business="Whatever It Said", owner=None, role=None, tagline="Some tagline", where="Somewhere",
            lines=None):
    lines = lines or ([{"speaker": "owner", "text": "Come and see us, we're lovely."}] if owner else []) + [
        {"speaker": "voiceover", "text": "Open every day but Sunday, and Sundays too in summer."},
        {"speaker": "voiceover", "text": f"{business}. {tagline}."}]
    return AdvertScript(business=business, tagline=tagline, where=where, backdrop="harbour", owner_name=owner,
                        owner_role=role, lines=lines)


def _writer(monkeypatch, script):
    prompts = []

    def write(route, schema, system, user, **k):
        prompts.append(user)
        return script.model_copy(deep=True)
    monkeypatch.setattr(llm, "complete_json", write)
    return prompts


def test_the_core_is_tidy():
    every = directory.SEED_BUSINESSES + directory.CORE
    names = [b.name for b in every]
    assert len({n.lower() for n in names}) == len(names)
    for i, a in enumerate(names):                             # no two the same business under two names
        assert not [b for b in names[i + 1:] if directory.near(a, b)], a
    owners = [b.owner for b in every if b.owner]
    assert len(set(owners)) == len(owners)                    # one business each
    for b in every:
        assert not directory.formulaic(b.name), b.name
        assert len(b.name) <= 40 and len(b.where) <= 48 and len(b.tagline) <= 48, b.name
        assert b.backdrop in BACKDROP_IDS, b.name
    assert len(directory.CORE) > 40                           # more than the pool's model-written slots, so some are off air


def test_the_old_shapes_are_caught():
    assert directory.formulaic("Wexley Lantern & Wick Repairs")
    assert directory.formulaic("Port Wexley Chimney and Flue Sweeps")
    assert not directory.formulaic("Wexley Park Bowls Club")
    assert directory.near("Wexley Pie & Pasty Hatch", "Wexley Pasty & Pie Hatch")
    assert not directory.near("Harrow Street Pharmacy", "Harrow Street Smokehouse")


def test_a_known_business_comes_back_as_itself(pool, world, monkeypatch):
    """The model is asked for a named business; whatever it calls it, the advert is the directory's."""
    prompts = _writer(monkeypatch, _script("Brenda's Stitch Shack", owner="Nora Ellison", role="pie maker",
                                           tagline="New words"))
    ad = adverts.make(world, "known")
    assert ad is not None
    b = directory.find(world, ad.script.business)
    assert b.name in {c.name for c in directory.CORE}        # never tried before: a core business
    assert "THE BUSINESS TO ADVERTISE" in prompts[0] and b.name in prompts[0]
    assert ad.script.where == b.where
    if b.owner:
        assert ad.script.owner_name == b.owner                # not the night nurse
    if b.tagline:
        assert ad.script.tagline == b.tagline
    rec = world.directory[b.name.lower()]
    assert rec["adverts"] == 1 and rec["last_lines"] and rec["tried"]


def test_the_rotation_goes_round_the_ones_off_air_longest_ago(pool, world, monkeypatch):
    _writer(monkeypatch, _script())
    made = [adverts.make(world, "known").script.business for _ in range(5)]
    assert len(set(made)) == 5
    for name in made:                                         # each is on air now, so not chosen again
        assert directory.choose(world, pool.businesses(), mode="known").known.name not in made
    # Once it's off air, its next advert hears what the last one said.
    first = made[0]
    for f in pool.dir.glob("*.json"):
        if first in f.read_text(encoding="utf-8"):
            f.unlink()
    pool.load()
    for b in directory.businesses(world):                     # everything else was tried more recently
        if b.name != first:
            directory.tried(world, b.name)
    prompts = _writer(monkeypatch, _script())
    again = adverts.make(world, "known")
    assert again.script.business == first
    assert "Its last advert said: Open every day" in prompts[0]
    assert world.directory[first.lower()]["adverts"] == 2


def test_an_advert_that_fails_still_moves_the_rotation_on(pool, world, monkeypatch):
    long = _script(lines=[{"speaker": "voiceover", "text": "Waves crash on the shore. " * 10}] * 3)
    _writer(monkeypatch, long)
    assert adverts.make(world, "known") is None               # over 32 seconds
    tried = [r["name"] for r in world.directory.values() if r.get("tried")]
    assert len(tried) == 1
    assert all(directory.choose(world, [], random.Random(i), mode="known").known.name != tried[0] for i in range(20))


def test_going_off_the_list_invents_a_trade_the_town_lacks_and_keeps_it(pool, world, monkeypatch):
    prompts = _writer(monkeypatch, _script("Scissor Sisters of Quay Lane", owner="Tamsin Ogle", role="hairdresser"))
    ad = adverts.make(world, "new")
    assert ad is not None and "INVENT A NEW LOCAL BUSINESS" in prompts[0]
    trade = prompts[0].split("INVENT A NEW LOCAL BUSINESS: a ")[1].split(".")[0]
    assert trade in directory.TRADES
    b = directory.find(world, "Scissor Sisters of Quay Lane")
    assert b and b.kind == trade and b.owner == "Tamsin Ogle"
    # It is a known business now, and comes back as itself once it's off air.
    assert b in directory.businesses(world)
    assert world.person_by_name("Tamsin Ogle")


@pytest.mark.parametrize("script, why", [
    (_script("Wexley Rope & Tackle Co."), "formulaic"),
    (_script("Gull's Rest Fish Bar & Chips"), "too close to Gull's Rest"),
    (_script("Brenda's Pies", owner="Brenda Fisk", role="pie maker"), "a resident with a trade already"),
    (_script("Moss & Daughter", owner="Pete Jago", role="baker"), "a directory owner"),
])
def test_an_invented_business_must_be_new_and_its_owner_too(pool, world, monkeypatch, script, why):
    world.ensure_person("Brenda Fisk", "tailor and alterations, Main Street")
    _writer(monkeypatch, script)
    assert adverts.make(world, "new") is None, why
    assert not pool.businesses()


def test_a_pub_keeps_the_landlord_its_first_advert_gave_it(pool, world, monkeypatch):
    _writer(monkeypatch, _script(owner="Maggie Treloar", role="landlady"))
    pub = next(b for b in directory.CORE if b.kind == "pub" and not b.owner)
    for b in directory.businesses(world):                     # the pub is the one off air longest
        if b.name != pub.name:
            directory.tried(world, b.name)
    ad = adverts.make(world, "known")
    assert ad.script.business == pub.name
    assert directory.find(world, pub.name).owner == "Maggie Treloar"
    assert directory.find(world, pub.name).tagline == "Some tagline"
    # Next time she is who speaks, whoever the model names.
    for f in pool.dir.glob("*.json"):
        f.unlink()
    pool.load()
    _writer(monkeypatch, _script(owner="Someone Else", role="landlord", tagline="Other words"))
    for b in directory.businesses(world):
        if b.name != pub.name:
            directory.tried(world, b.name)
    ad = adverts.make(world, "known")
    assert ad.script.owner_name == "Maggie Treloar" and ad.script.tagline == "Some tagline"


def test_mostly_known_and_fewer_new_once_the_town_is_full(world):
    rng = random.Random(7)
    new = sum(not directory.choose(world, [], rng).known for _ in range(2000))
    assert 0.2 < new / 2000 < 0.3
    for i in range(directory.SLOW_AT):                        # a town with plenty of businesses
        world.directory[f"made-up {i}"] = {"name": f"Made Up Number {i}", "kind": "shop", "invented": "2026-11-27"}
    new = sum(not directory.choose(world, [], rng).known for _ in range(2000))
    assert 0.06 < new / 2000 < 0.14


def test_with_everything_on_air_it_invents(world):
    on_air = [b.name for b in directory.businesses(world)]
    assert directory.choose(world, on_air, mode="known").trade


def test_the_seeds_are_never_chosen(world):
    seeds = {b.name for b in directory.SEED_BUSINESSES}
    rng = random.Random(3)
    assert not any((c := directory.choose(world, [], rng, mode="known")).known and c.known.name in seeds
                   for _ in range(300))


def test_the_directory_survives_a_save(world, tmp_path):
    directory.tried(world, "Jago's Butchers")
    world.directory["jago's butchers"]["tagline"] = "Bangers you can trust"
    world_mod.save(world, tmp_path / "w.json")
    again = world_mod.load(tmp_path / "w.json")
    assert directory.find(again, "Jago's Butchers").tagline == "Bangers you can trust"
