"""A guest the town knows, given another job: asked once, then for someone new, then the captions keep to the record.
On 2026-11-28 Ruth Caddick, a former council engineering accountant, aired on Rock Pool as "market stallholder and
pony keeper" in the wide shot and under her record in the close-ups. The model is stubbed: no network."""
from __future__ import annotations

from newsroom import llm, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def _town():
    w = world_mod.seed()
    w.ensure_person("Ruth Caddick", "former council engineering accountant")
    return w


def _interview(name, role, cap="Hetty the Shetland pony"):
    return {"headline": "Hetty the Pony Comes to Visit", "lower_third": cap, "guest_name": name, "guest_role": role,
            "guest_gender": "f", "guest_memory": "keeps a pony called Hetty on her market round",
            "lines": [{"speaker": "mag_a", "text": "Who have we got today?"},
                      {"speaker": "guest", "text": "This is Hetty, and she loves apples."},
                      {"speaker": "mag_a", "text": "Can I have an apple?"}]}


def _run(monkeypatch, replies):
    w = _town()
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return schema.model_validate(replies[min(len(asked), len(replies)) - 1])
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=257, type=T.interview, show="magazine", target_s=120)
    writers.script_segment(seg, w)
    return w, seg, asked


def test_asked_twice_the_job_goes_to_someone_new(monkeypatch):
    clash = _interview("Ruth Caddick", "market stallholder and pony keeper")
    w, seg, asked = _run(monkeypatch, [clash, clash, _interview("Wenna Treloar", "market stallholder and pony keeper")])
    assert len(asked) == 3 and "Book someone NEW for this item" in asked[2] and "(not Ruth Caddick)" in asked[2]
    assert {l.guest_name for l in seg.lines if l.speaker == "guest"} == {"Wenna Treloar"}
    assert w.person_by_name("Ruth Caddick").role == "former council engineering accountant"


def test_still_clashing_the_captions_keep_to_the_record(monkeypatch):
    clash = _interview("Ruth Caddick", "market stallholder and pony keeper")
    w, seg, asked = _run(monkeypatch, [clash, clash, clash])
    assert len(asked) == 3
    caps = [c.payload.get("subtitle") for c in seg.cues if c.kind == "lower_third"]
    assert caps == ["Ruth Caddick, former council engineering accountant"], caps            # the wide shot
    assert {l.guest_role for l in seg.lines if l.speaker == "guest"} == {"former council engineering accountant"}
    memories = w.person_by_name("Ruth Caddick").memories                                     # and not kept
    assert not any("pony" in (m.get("said") or "") for m in memories)
