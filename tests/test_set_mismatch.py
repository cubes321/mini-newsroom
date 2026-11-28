"""The caption and the set agree. On the 2026-11-28 afternoon "Report from Quarry Ridge studio" went out over the
harbour front, "Quarry Ridge Gallery" over the market shed, and Quayside put Brenda Fisk's shop on Harrow Street
under a caption from her record, "tailor and alterations, Main Street". The model is stubbed: no network."""
from __future__ import annotations

from types import SimpleNamespace as NS

from newsroom import llm, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def _town():
    w = world_mod.seed()
    w.ensure_person("Brenda Fisk", "tailor and alterations, Main Street")
    return w


def test_a_room_no_set_shows_is_sent_back():
    w = _town()
    odd = lambda loc, bd, kind=T.feature, guest=None: writers.set_mismatch(   # noqa: E731
        NS(location=loc, backdrop=bd, guest_name=guest), w, kind)
    assert "inside a studio" in odd("Quarry Ridge studio, Dunmore Lane, Port Wexley", "harbour")
    assert "inside a gallery" in odd("Quarry Ridge Gallery, Dunmore Lane", "market_shed")
    # outside it, or the set that is the place, is fine
    assert odd("outside the gallery on Main Street", "main_street") is None
    assert odd("the harbour wall, by Hester's studio", "harbour") is None
    assert odd("the exhibition in Saltby village hall", "village_hall") is None
    assert odd("the bottom of the cliff path below the Bay Window tea room", "tea_room") is None
    assert odd("the harbour front", "harbour") is None
    assert odd("Quarry Ridge studio", "studio_wide") is None                 # the studio itself: not a location


def test_a_feature_visits_someone_at_their_place():
    w = _town()
    odd = lambda loc, bd, kind=T.feature, show="quayside": writers.set_mismatch(   # noqa: E731
        NS(location=loc, backdrop=bd, guest_name="Brenda Fisk"), w, kind, show)
    assert "Their place is Main Street" in odd("Harrow Street, Port Wexley", "main_street")
    assert odd("Main Street, Port Wexley", "main_street") is None
    assert odd("Harrow Street market, winter shed", "market_shed") is None   # her stall: away from the shop
    assert odd("Harrow Street, Port Wexley", "main_street", T.interview) is None   # only a feature visits
    assert odd("Harrow Street, Port Wexley", "main_street", show="inquiry") is None   # a film, not a visit
    assert writers.set_mismatch(NS(location="Harrow Street", backdrop="market", guest_name="Wenna New"), w,
                                T.feature, "quayside") is None               # nobody the town knows


def test_the_place_and_the_set_are_asked_again(monkeypatch):
    w = _town()
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        loc, bd = (("Quarry Ridge studio, Dunmore Lane", "harbour") if len(asked) == 1 else
                   ("the harbour wall, where Hester paints", "harbour"))
        return schema.model_validate({
            "headline": "Hester Quayle's Harbour Light", "lower_third": "Hester Quayle, painter",
            "location": loc, "backdrop": bd, "guest_name": None,
            "lines": [{"speaker": "travel", "text": "Here with a painter."},
                      {"speaker": "travel", "text": "The light is everything."},
                      {"speaker": "travel", "text": "Worth a look."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=7, type=T.feature, show="outabout", target_s=150)
    writers.script_segment(seg, w)
    assert len(asked) == 2 and "THE PLACE AND THE SET DISAGREE" in asked[1] and "inside a studio" in asked[1]
    assert any(c.payload.get("title") == "Hester Quayle, painter" and "harbour wall" in c.payload.get("subtitle", "")
               for c in seg.cues if c.kind == "lower_third")


def test_only_the_place_after_the_job_is_theirs():
    """Replayed over the afternoon: Ruth Penhallow, "Harbour campaigner and retired ferry deckhand", at the old
    cannery was no mismatch; Bernard Moss, "sailmaker, Harbour Row", making a sail at Tidewater Stadium was."""
    w = _town()
    w.ensure_person("Ruth Penhallow", "Harbour campaigner and retired ferry deckhand")
    w.ensure_person("Bernard Moss", "sailmaker, Harbour Row")
    odd = lambda guest, loc, bd: writers.set_mismatch(NS(location=loc, backdrop=bd, guest_name=guest), w, T.feature,  # noqa: E731
                                                      "outabout")
    assert odd("Ruth Penhallow", "the old cannery sheds", "cannery") is None
    assert "Their place is Harbour Row" in odd("Bernard Moss", "Tidewater Stadium", "stadium")
