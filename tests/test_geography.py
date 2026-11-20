"""The gazetteer (newsroom/geography.py): the places hang together, and a Coast Road leg runs one way."""
from newsroom import geography as g
from newsroom import locations


def _leg(*stops):
    """Stops as (the writer's words, backdrop), placed the way the route check places them."""
    return [g.Placed(words, g.place_for(words, backdrop)) for words, backdrop in stops]


def test_every_place_is_on_the_map():
    for p in g.PLACES:
        assert p.side in (g.EAST, g.WEST, g.HEAD), p.id
        assert p.at in g.ORDER, f"{p.id} is passed by {p.at}, which isn't on the coast"
        assert not p.backdrop or p.backdrop in locations.BY_ID, f"{p.id}: no backdrop {p.backdrop}"
    for c in g.COAST:
        assert g.BY_ID[c].at == c, f"{c} is on the coast, so it is its own stop"
    assert len(set(g.COAST)) == len(g.COAST)
    for backdrop, pid in g.BACKDROP_PLACE.items():
        assert backdrop in locations.BY_ID and pid in g.BY_ID


def test_links_join_everything():
    for a, b, miles, how in g.LINKS:
        assert a in g.BY_ID and b in g.BY_ID and miles > 0 and how in ("road", "path", "ferry")
    seen, todo = set(), ["harbour"]
    while todo:
        here = todo.pop()
        if here not in seen:
            seen.add(here)
            todo += [n for n, _, _ in g.NEIGHBOURS[here]]
    assert seen == set(g.BY_ID), f"cut off: {set(g.BY_ID) - seen}"
    assert all(stop in g.BY_ID for stop in g.BUS_ROUTE)


def test_canon_sides():
    """What the town's stories already fix: Saltby across the Grey, Greymouth on its side (came back from
    Greymouth on the Saltby ferry), the ferry from the harbour steps to the Saltby slip."""
    assert g.side("harbour") == g.EAST and g.side("saltby") == g.WEST and g.side("greymouth") == g.WEST
    assert g.side("cliff_road") == g.WEST                  # Cliff Road pupils take the ferry to school
    assert g.side("the_salting") == g.EAST                 # a town ward with the town's bonfire
    assert set(g.FERRY) == {"harbour", "saltby_slip"}
    assert g.neighbours("harbour") and ("saltby_slip", 0.85, {"ferry": g.FERRY_MIN}) in g.neighbours("harbour")


def test_naming_a_place():
    assert g.place_for("The Saltby slip, with the ferry's ring worn shiny", "slipway") == "saltby_slip"
    assert g.place_for("The ferry steps at the town quay", "harbour") == "harbour"
    assert g.place_for("The quay rail above the auction floor", "fish_quay") == "fish_quay"
    assert g.place_for("The row of cottages above the slip", "village") == "saltby"
    assert g.place_for("a farm lane", "farm") is None                  # a farm could be anywhere
    assert g.place_for("the ferry slip", "slipway") is None            # either side of the water
    assert g.place_for("anything", "pub", where="kessick_bay") == "kessick_bay"


def test_the_ferry_leg_of_2026_11_20_is_sent_back():
    """Lorna sailed for Saltby from the town quay, tied up at the fish quay in town, then crossed."""
    stops = _leg(("The ferry steps at the town quay", "harbour"),
                 ("The quay rail above the auction floor", "fish_quay"),
                 ("The Saltby slip, with the ferry's ring worn shiny", "slipway"))
    why = g.check_leg(stops, "The Saltby foot ferry from the town quay, fourteen minutes if the tide is kind")
    assert why and "ferry" in why and "auction" in why


def test_a_ferry_leg_that_boards_at_the_steps_will_do():
    assert g.check_leg(_leg(("the fish quay", "fish_quay"), ("the Quay Steps", "harbour"),
                            ("Saltby green", "village")), "the Saltby foot ferry") is None
    assert g.check_leg(_leg(("Harrow Street market", "market"), ("the Saltby slip", "slipway"),
                            ("Saltby sands", "seafront")), "the ferry") is None


def test_one_way_along_the_coast():
    assert g.check_leg(_leg(("the seafront", "seafront"), ("the lifeboat station", "lifeboat_station"),
                            ("the coast road", "coast_road")), "on foot") is None
    assert g.check_leg(_leg(("the lifeboat station", "lifeboat_station"), ("the seafront", "seafront"),
                            ("the old cannery", "cannery")), "on foot") is None             # the other way
    assert g.check_leg(_leg(("Harrow Street market", "market"), ("Main Street", "main_street"),
                            ("the harbour steps", "harbour")), "on foot") is None           # all in town
    why = g.check_leg(_leg(("the seafront", "seafront"), ("the harbour", "harbour"),
                           ("the lifeboat station", "lifeboat_station")), "on foot")
    assert why and "back the way" in why


def test_round_by_the_bridge():
    assert g.check_leg(_leg(("the Salting", "estuary"), ("Polgrey Bridge", "village"),
                            ("Saltby green", "village")), "the coast bus") is None
    why = g.check_leg(_leg(("Saltby green", "village"), ("the harbour", "harbour"), ("Saltby sands", "seafront")),
                      "a borrowed bike")
    assert why and "back" in why


def test_a_leg_starts_where_the_last_one_ended():
    legs = [("Up Past the Cottages", "on foot", _leg(("Saltby green", "village"), ("the Crown at Saltby", "pub"))),
            ("The Borrowed Bike", "a borrowed bike", _leg(("the old quarry field", "quarry_field"),
                                                          ("the lighthouse rail", "lighthouse")))]
    errors = g.check_legs(legs)
    assert len(errors) == 1 and errors[0].startswith("leg 2 (The Borrowed Bike)") and "Saltby side" in errors[0]
    legs[1] = ("Home on the Ferry", "the ferry home", _leg(("the fish quay", "fish_quay"), ("the seafront", "seafront")))
    assert g.check_legs(legs) == []


def test_unplaced_stops_are_left_out():
    assert g.check_leg(_leg(("a tea room", "tea_room"), ("a farm", "farm"), ("a pub", "pub")), "on foot") is None


def test_for_the_writers():
    assert len(g.lie_of_the_land().split()) < 150
    text = g.coast_text()
    for c in g.COAST:
        assert f"  {c}: " in text
    assert text.index("greymouth_point") < text.index("saltby_slip") < text.index("polgrey") < text.index("harbour")


def test_the_writers_who_place_things_get_the_lie_of_the_land():
    from newsroom import schedule, world as world_mod, writers
    from newsroom.models import SegmentType as T
    w = world_mod.seed()
    _, report = writers.build_prompt(T.field_report, w, target_s=60, show=schedule.get("news"))
    _, review = writers.build_prompt(T.review, w, target_s=60, show=schedule.get("outabout"))
    assert "LIE OF THE LAND" in report and "LIE OF THE LAND" in review
    _, bulletin = writers.build_prompt(T.bulletin, w, target_s=60, show=schedule.get("news"))
    assert "LIE OF THE LAND" not in bulletin
