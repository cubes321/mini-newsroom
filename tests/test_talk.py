"""Town talk (talk.py): last night's Wexley Wits result reaches the writers' briefing as talk, for two days,
once the quiz has really been on air.

The quiz entry is hand-made, as entertainment/quiz.py records one: no model, and none of that channel's code.
"""
from datetime import date, timedelta

from newsroom import llm, talk, world as world_mod

TODAY = date(2026, 11, 9)


def _town(night=TODAY - timedelta(days=1), aired=True, **over):
    w = world_mod.seed()
    w.last_date = TODAY.isoformat()
    quiz = {"date": night.isoformat(), "venue": "The Railway",
            "teams": [{"pub": "the Railway", "name": "The Railway", "members": ["Kev Moyle", "Bev Carne"]},
                      {"pub": "the Harbour Lights", "name": "The Harbour Lights", "members": ["Shirley Vosper", "Dennis Rowe"]}],
            "rounds": [{"kind": "general", "scores_after": [6, 8]}, {"kind": "potluck", "scores_after": [14, 18]},
                       {"kind": "doubles", "scores_after": [24, 21]}],
            "tiebreak": None, "final": [24, 21], "winner": 0, "stand_in": False} | over
    w.quizzes.append(quiz)
    if aired:
        w.archive.append({"date": night.isoformat(), "day": 15, "type": "links", "headline": "The Railway take it",
                          "thread_id": None, "people": [], "text": "And that is the final score.", "show": "wits",
                          "brief": "{close}", "hash": ""})
    return w


def test_last_nights_quiz_is_in_the_briefing_as_talk_after_the_cache_break():
    w = _town()
    said = talk.quiz(w, TODAY)
    assert said == ("Wexley Wits, the television pub quiz, Sunday night at The Railway: The Railway (Kev Moyle and "
                    "Bev Carne) beat The Harbour Lights (Shirley Vosper and Dennis Rowe) 24-21, from behind going "
                    "into the last round.")
    head, _, tail = w.summary_for_prompt().partition(llm.CACHE_BREAK)
    assert "Town talk" in tail and said in tail and "never a headline" in tail and "Wexley Wits" not in head
    assert "Wexley Wits" not in w.summary_for_editor()          # the desk never sees it: no thread grows from talk


def test_the_losers_win_and_a_tiebreak_are_told_as_they_were():
    w = _town(winner=1, final=[21, 22], tiebreak={"winner": 1},
              rounds=[{"kind": "general", "scores_after": [10, 9]}, {"kind": "doubles", "scores_after": [21, 21]}])
    assert "The Harbour Lights (Shirley Vosper and Dennis Rowe) beat The Railway" in talk.quiz(w, TODAY)
    assert talk.quiz(w, TODAY).endswith("22-21, on the tiebreak.")


def test_it_is_talk_for_two_days_and_never_before_it_has_been_on():
    assert talk.line(_town(night=TODAY), TODAY) == ""                           # tonight's: booked, not played
    assert talk.line(_town(aired=False), TODAY) == ""                           # booked, and the station was off
    assert talk.line(_town(night=TODAY - timedelta(days=2)), TODAY) != ""
    assert talk.line(_town(night=TODAY - timedelta(days=3)), TODAY) == ""
    assert talk.line(world_mod.seed(), TODAY) == ""                             # a station with no quiz says nothing
    w = _town()
    w.quizzes.append({"date": "2026-11-08"})                                    # an entry in a shape it can't read
    assert talk.quiz(w, TODAY).startswith("Wexley Wits")


def _kettle_town(night=TODAY - timedelta(days=1), items=("THE RECIPE, part one: {cook}", "ON THE SOFA: {sofa}."),
                 stand_in=False):
    w = world_mod.seed()
    w.last_date = TODAY.isoformat()
    w.kettles.append({"date": night.isoformat(), "stand_in": stand_in, "calls": 3, "question": "Garlic?",
                      "dish": {"dish": "Saffron buns", "cook": "Tegan Moyle", "cook_role": "cook", "why": "winter"},
                      "sofa": {"name": "Ivy Penhallow", "role": "widow", "about": "a jumper for every lifeboat crew."},
                      "expert": {"name": "Sam Lander"}, "callers": [], "notices": []})
    for b in items:
        w.archive.append({"date": night.isoformat(), "day": 15, "type": "interview", "headline": "x",
                          "thread_id": None, "people": [], "text": "x", "show": "kettle", "brief": b, "hash": ""})
    return w


def test_last_nights_kettles_on_is_talk_once_its_items_aired():
    said = talk.kettle(_kettle_town(), TODAY)
    assert said == ("The Kettle's On, the teatime show on Channel 8, Sunday: Tegan Moyle made saffron buns, and Ivy "
                    "Penhallow was on the sofa (a jumper for every lifeboat crew).")
    assert said in talk.line(_kettle_town(), TODAY)
    only_dish = talk.kettle(_kettle_town(items=("THE RECIPE, part one: {cook}",)), TODAY)
    assert "saffron buns" in only_dish and "sofa" not in only_dish                    # the sofa never went out
    assert talk.kettle(_kettle_town(items=()), TODAY) is None                        # booked, never on air
    assert talk.kettle(_kettle_town(stand_in=True), TODAY) is None
    assert talk.kettle(_kettle_town(night=TODAY), TODAY) is None                     # tonight's: not yet
    assert talk.kettle(_kettle_town(night=TODAY - timedelta(days=3)), TODAY) is None


def _road_town(aired_legs=6, last=TODAY - timedelta(days=1)):
    w = world_mod.seed()
    w.last_date = TODAY.isoformat()
    route = [{"title": f"Leg {i + 1}", "stops": [{"place": f"Stop {i + 1}.{k + 1}"} for k in range(3)]}
             for i in range(6)]
    w.travelogue = {"series": [{"host": "Lorna Quayle", "made": "2026-11-14#Lorna Quayle",
                                "title": "Six Slow Ways and a Tin of Parkin", "legs": route}],
                    "legs": [{"date": (last - timedelta(days=2 * (5 - i))).isoformat(), "made": "2026-11-14#Lorna Quayle",
                              "n": i + 1, "aired": i < aired_legs} for i in range(6)]}
    return w


def test_the_coast_road_is_talk_once_as_a_whole_series_when_its_last_leg_has_aired():
    said = talk.coast_road(_road_town(), TODAY)
    assert said == ("The Coast Road, the travelogue on Channel 8, finished on Sunday: Lorna Quayle's whole journey "
                    "round the coast, \"Six Slow Ways and a Tin of Parkin\", in 6 legs from Stop 1.1 to Stop 6.3.")
    assert said in talk.line(_road_town(), TODAY)
    assert talk.coast_road(_road_town(aired_legs=5), TODAY) is None                  # still on the road
    assert talk.coast_road(_road_town(last=TODAY), TODAY) is None                    # the last leg is tonight's
    assert talk.coast_road(_road_town(last=TODAY - timedelta(days=3)), TODAY) is None


def test_the_kettles_on_talk_lasts_when_a_channel_seven_night_has_filled_the_archive():
    """A Channel 7 night writes up to about a thousand archive entries, the archive's whole length: the stamps on the
    booking (kettle.aired) are what the next day's talk reads."""
    w = _kettle_town(items=())
    w.kettles[-1].update(dish_aired=True, sofa_aired=True)
    assert "Tegan Moyle made saffron buns" in talk.kettle(w, TODAY) and "on the sofa" in talk.kettle(w, TODAY)


def _highwater_town(night=TODAY - timedelta(days=1), aired=True, results=None):
    w = world_mod.seed()
    w.last_date = TODAY.isoformat()
    w.highwaters.append({
        "date": night.isoformat(), "stand_in": False, "result_aired": aired,
        "prizes": {"4": {"business": "Tonkin's Bakery", "prize": "a cream tea for two"},
                   "8": {"business": "Harbour Lights", "prize": "dinner for two"},
                   "11": {"business": "Opie Cycles", "prize": "a new bike"}},
        "star": {"business": "Saltby Sands Hotel", "prize": "a weekend away for two"},
        "game": {"results": results or [{"who": "Dev Hocking", "prize": 4, "star": False, "step": 5},
                                        {"who": "Jan Pascoe", "prize": 8, "star": True, "step": 9}]}})
    return w


def test_last_nights_high_water_is_talk_once_its_result_aired():
    said = talk.highwater(_highwater_town(), TODAY)
    assert said == ("High Water, the gameshow on Channel 8, Sunday: Jan Pascoe went home with the star prize, a weekend "
                    "away for two from Saltby Sands Hotel and dinner for two from Harbour Lights, and Dev Hocking went "
                    "home with a cream tea for two from Tonkin's Bakery.")
    assert said in talk.line(_highwater_town(), TODAY)
    nothing = talk.highwater(_highwater_town(results=[{"who": "Ray Opie", "prize": 0, "star": False, "step": 2},
                                                      {"who": "Sue Tonkin", "prize": 11, "star": False, "step": 11}]),
                             TODAY)
    assert nothing.endswith("Sue Tonkin went home with a new bike from Opie Cycles, and Ray Opie went home with nothing.")
    assert talk.highwater(_highwater_town(aired=False), TODAY) is None              # booked, never on air
    stand_in = _highwater_town()
    stand_in.highwaters[-1]["stand_in"] = True                                      # real climbers, stock wording
    assert talk.highwater(stand_in, TODAY) == said
    assert talk.highwater(_highwater_town(night=TODAY), TODAY) is None              # tonight's: not yet
    assert talk.highwater(_highwater_town(night=TODAY - timedelta(days=3)), TODAY) is None
