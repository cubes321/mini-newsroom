"""A looped show doesn't run the same item again: on 2026-11-03 Coastwide's 19-slot loop came round three
times, each lap with the same briefs, and Haiku wrote the same redshank count, roof-survey scam and parking
rise every time, though the prompt listed them as done. The model is stubbed: no network."""
from __future__ import annotations

from newsroom import llm, schedule, world as world_mod, writers
from newsroom.models import Segment, SegmentType as T


def test_each_lap_of_coastwide_has_its_own_briefs():
    show = schedule.get("magazine")
    n, lap = len(show.pattern), len(show.pattern) - show.loop_from
    for pos in range(show.loop_from, n):
        laps = [show.item(pos + k * lap).brief for k in range(3)]
        if schedule.as_item(show.pattern[pos]).brief:
            assert len(set(laps)) == 3, laps
        assert all(isinstance(b, str) for b in laps)
    vox = [show.item(p) for p in range(n * 3)]
    assert all(isinstance(i.brief, str) for i in vox)


def test_a_plain_brief_is_the_same_every_lap():
    show = schedule.get("late")
    pos = next(p for p in range(show.loop_from, len(show.pattern)) if schedule.as_item(show.pattern[p]).brief)
    lap = len(show.pattern) - show.loop_from
    assert show.item(pos).brief == show.item(pos + lap).brief


def test_a_headline_already_on_the_show_today_is_asked_for_again(monkeypatch):
    w = world_mod.seed()
    show = schedule.get("magazine")
    w.record_aired("feature", "Counting redshank on the estuary, one cold morning at a time", None, "...",
                   show="magazine", aired=False)
    w.record_aired("feature", "Counting redshank on the estuary", None, "...", show="news")   # another show's
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        head = ("Counting redshank on the estuary, one cold morning at a time" if len(asked) == 1
                else "The coast path above Saltby, with the warden")
        return schema.model_validate({
            "headline": head, "lower_third": "Coastwide", "location": "the coast path", "backdrop": "coast_road",
            "lines": [{"speaker": "mag_a", "text": "Off we go."}, {"speaker": "reporter", "text": "Windy up here."},
                      {"speaker": "mag_b", "text": "Hold on to your hat."}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=31, type=T.feature, show="magazine", target_s=100, brief="a walk")
    writers.script_segment(seg, w)
    assert len(asked) == 2 and 'NOT "Counting redshank on the estuary, one cold morning at a time"' in asked[1]
    assert seg.headline == "The coast path above Saltby, with the warden"


def test_what_counts_as_a_repeat():
    w = world_mod.seed()
    show = schedule.get("magazine")
    w.record_aired("consumer", "Beware the doorstep roof survey pushing for a deposit", None, "...", show="magazine")
    w.record_aired("weather", "Clear, cold and frosty for the bonfire week", None, "...", show="magazine")
    assert writers._repeated("Beware the doorstep roof survey asking for a deposit", w, show, T.consumer)
    assert not writers._repeated("Roofers on Harbour Row after the gales", w, show, T.feature)
    assert not writers._repeated("Clear, cold and dry for the bonfire week", w, show, T.feature)   # weather aside
    assert not writers._repeated("Beware the doorstep roof survey asking for a deposit", w,
                                 schedule.get("news"), T.interview)                         # a show without the memory


def test_a_story_time_already_told_is_asked_for_again_and_the_letters_keep_their_title():
    """2026-11-06: Rock Pool's five story times were the giant who built the harbour wall twice and "Mabel the
    Seal and the Quay Bell" three times; its pieces are links, which the check used to leave out."""
    w = world_mod.seed()
    show = schedule.get("rockpool")
    story, poem, letters = (show.item(p).brief for p in (5, 7, 4))
    assert "STORY TIME" in story and "POEM" in poem and letters in schedule.SAME_TITLE_BRIEFS
    w.record_aired("links", "Story Time: Barnaby Tusk and the Harbour Wall", None, "...", show="rockpool",
                   brief=story)
    w.record_aired("links", "Story Time: Mabel the Seal and the Quay Bell", None, "...", show="rockpool", brief=story)
    w.record_aired("links", "Letters and drawings from Rock Pool viewers", None, "...", show="rockpool", brief=letters)
    w.record_aired("links", "Gully Reads His Very First Beach Poem", None, "...", show="rockpool", brief=poem)
    assert writers._repeated("Story Time: Mabel the Seal and the Quay Bell", w, show, T.links, story)
    assert writers._repeated("Story Time: the giant who built the harbour wall", w, show, T.links, story)
    assert not writers._repeated("Story Time: the mermaid of Gull Rock", w, show, T.links, story)
    assert writers._repeated("Gully shares his very first beach poem", w, show, T.links, poem)
    assert not writers._repeated("Letters and drawings from Rock Pool viewers", w, show, T.links, letters)
    assert not writers._repeated("Story Time: Mabel the Seal and the Quay Bell", w, show, T.links, poem)  # another brief
    assert not writers._repeated("Story Time: Mabel the Seal and the Quay Bell", w, show, T.links)       # no brief
    # 2026-11-13: the same story retold shares fewer words than a repeated headline (3 of 7), so stories are stricter
    w.record_aired("links", "Biscuit the dog outwits the harbour smugglers", None, "...", show="rockpool", brief=story)
    assert writers._repeated("Biscuit the dog outwits smugglers with the Town Hall clock", w, show, T.links, story)
    w.record_aired("links", "Gully reads a silly beach poem", None, "...", show="rockpool", brief=poem)
    assert not writers._repeated("Gully reads a snail poem from the rocks", w, show, T.links, poem)   # poems as before


def _bulletin(head, tid):
    return {"headline": head, "lower_third": "News", "thread_id": tid, "thread_status": None, "tip_used": None,
            "lines": [{"speaker": "anchor", "text": "Good afternoon."}, {"speaker": "anchor", "text": "More soon."}]}


def test_the_news_moves_on_after_a_bulletin_and_its_report(monkeypatch):
    """2026-11-06: 27 news items in a row on the Salting choir's programmes in the morning, and four of the
    first five on a coffee stall in the afternoon, with the headlines listed as "do NOT repeat"."""
    w = world_mod.seed()
    stall = w.update_thread(None, "Harrow Street Coffee Stall Fights the Cold Snap", "queue round the corner")
    ferry = w.update_thread(None, "Cyril Dunmore's model ferry finds a winter case", "the case is ordered")
    news = schedule.get("news")
    now = schedule.now()
    w.record_aired("bulletin", "Harrow Street Coffee Stall Fights the Cold Snap", stall, "...", show="news", aired=False)
    assert writers._same_story_again(stall, w, news, T.field_report, now) is None       # its report: fine
    w.record_aired("field_report", "Harrow Street Coffee Stall Keeps the Cold at Bay", stall, "...", show="news",
                   aired=False)
    w.record_aired("weather", "Cold northerly", None, "...", show="news", aired=False)   # not a story item
    assert writers._same_story_again(stall, w, news, T.bulletin, now) == stall          # a third: another story
    assert writers._same_story_again(ferry, w, news, T.bulletin, now) is None
    assert writers._same_story_again(None, w, news, T.bulletin, now) is None
    assert writers._same_story_again(stall, w, schedule.get("magazine"), T.interview, now) is None   # the news only
    w.thread(stall).breaking_ts = now - 600                                            # broke ten minutes ago
    assert writers._same_story_again(stall, w, news, T.bulletin, now) is None
    w.thread(stall).breaking_ts = None
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return schema.model_validate(_bulletin("Harrow Street Coffee Stall Holds Out Against the Cold", stall)
                                     if len(asked) == 1 else
                                     _bulletin("Cyril Dunmore's model ferry finds a winter case", ferry))
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=5, type=T.bulletin, show="news", target_s=75.0)
    writers.script_segment(seg, w)
    assert len(asked) == 2 and f"NOT [{stall}]" in asked[1]
    assert seg.headline == "Cyril Dunmore's model ferry finds a winter case"


def test_the_news_check_sees_a_story_by_its_headline_and_one_that_alternates(monkeypatch):
    """2026-11-07: "Frost Keeps Harrow Street Busy as Remembrance Nears" took every other news item for twenty
    minutes, often with thread_id null and filed under the story by its headline afterwards."""
    w = world_mod.seed()
    frost = w.update_thread(None, "Frost Keeps Harrow Street Busy as Remembrance Nears", "busy")
    other = w.update_thread(None, "Cyril Dunmore's model ferry finds a winter case", "the case is ordered")
    for head, tid in (("Frost Keeps Harrow Street Busy as Remembrance Nears", frost), ("Model ferry", other),
                      ("Frost Keeps Harrow Street Busy as Remembrance Nears", frost)):
        w.record_aired("bulletin", head, tid, "...", show="news", aired=False)
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return schema.model_validate(_bulletin("Frost Keeps Harrow Street Busy as Remembrance Nears", None)
                                     if len(asked) == 1 else
                                     _bulletin("Cyril Dunmore's model ferry finds a winter case", other))
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=6, type=T.bulletin, show="news", target_s=75.0)
    writers.script_segment(seg, w)                                   # frost, other, frost: no frost next
    assert len(asked) == 2 and f"NOT [{frost}]" in asked[1]


def test_the_news_check_sees_one_story_split_across_threads(monkeypatch):
    """2026-11-08: "Remembrance wreath laid on the harbour water" aired eleven times in 26 minutes. The desk
    closed its thread, and the items filed under new threads and under two other stories' (Tessa's row)."""
    w = world_mod.seed()
    wreath = w.update_thread(None, "Remembrance wreath laid on the harbour water this morning", "laid")
    row = w.update_thread(None, "Tessa Brannock Plans Four Hours Round the Lighthouse", "rowing at nine")
    ferry = w.update_thread(None, "Saltby ferry readies first school run for Cliff Road pupils", "Wednesday")
    news, now = schedule.get("news"), schedule.now()
    w.record_aired("bulletin", "Remembrance wreath laid on the harbour water this morning", wreath, "...",
                   show="news", aired=False)
    w.thread(wreath).phase = "closed"                                  # the desk closed it
    w.record_aired("field_report", "Lifeboat crew lay Remembrance wreath on the harbour water", row, "...",
                   show="news", aired=False)                            # filed under Tessa's row
    head = "Wreath laid on the harbour water this Remembrance Sunday"
    assert writers._same_story_again(None, w, news, T.bulletin, now, head) == \
        "Lifeboat crew lay Remembrance wreath on the harbour water"     # by headline, on no thread of its own
    assert writers._same_story_again(ferry, w, news, T.bulletin, now, head) == \
        "Lifeboat crew lay Remembrance wreath on the harbour water"     # whatever thread it names: not the ferry
    assert writers._same_story_again(ferry, w, news, T.bulletin, now,
                                     "Saltby ferry readies first school run for Cliff Road pupils") is None
    assert writers._same_story_again(None, w, news, T.bulletin, now, "Harbour water clears for Sunday") is None
    w.thread(row).breaking_ts = now - 600                             # one of them broke ten minutes ago
    assert writers._same_story_again(None, w, news, T.bulletin, now, head) is None
    w.thread(row).breaking_ts = None
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return schema.model_validate(_bulletin(head, None) if len(asked) == 1 else
                                     _bulletin("Saltby ferry readies first school run for Cliff Road pupils", ferry))
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=7, type=T.bulletin, show="news", target_s=75.0)
    writers.script_segment(seg, w)
    assert len(asked) == 2 and f'("{head}")' in asked[1] and "on another subject" in asked[1]
    assert seg.headline == "Saltby ferry readies first school run for Cliff Road pupils"


def test_rock_pool_tells_no_story_twice_and_brings_no_animal_or_make_twice():
    """2026-11-27, Rock Pool's first real afternoon: Nettle the gull in three of Hugh's five stories, Nell's button
    twice, a hundred-year-old tortoise twice and owls made twice, all under titles too unlike for `_repeated`."""
    w = world_mod.seed()
    show = schedule.get("rockpool")
    story, visitor, make, poem = schedule._STORY, schedule._VISITOR, schedule._MAKE, schedule._POEM
    for brief, head in ((story, "Hugh's Story of Nell and the Blue Button"),
                        (story, "Nettle the Gull and the Town Hall Clock"),
                        (visitor, "Dolores Finch Brings Tuppence, a Hundred-Year Tortoise"),
                        (make, "Paper Plate Owl To Make At Home"),
                        (poem, "Gully Shares a Silly Crab Poem")):
        w.record_aired("links" if brief != visitor else "interview", head, None, "...", show="rockpool", brief=brief)
    same = lambda head, brief: writers._same_subject(head, w, show, brief)   # noqa: E731
    assert same("Hugh Tells the Legend of Nettle's Blue Shell", story) == (
        "Nettle the Gull and the Town Hall Clock", ["nettle"])
    assert same("Hugh Tells the Legend of Nell and the Brass Button", story)[1] == ["button", "nell"]
    assert same("Dumpling the Hundred-Year Tortoise Visits Rock Pool", visitor)[1] == ["hundred", "tortoise", "year"]
    assert same("Loo Roll Tube Owls To Make At Home", make)[1] == ["owl"]
    # something else on the same brief, or the same thing on another, is fine
    assert same("Hugh Tells the Legend of the Mermaid of Kessick Bay", story) is None
    assert same("Winston Barrow Brings Pebble the Hedgehog", visitor) is None
    assert same("Egg Box Birds To Make At Home", make) is None
    assert same("Gully Shares a Crab Poem From the Rocks", poem) is None                 # poems keep _repeated's rule
    assert same("Nettle and the Town Hall Clock", visitor) is None


def test_the_job_guest_is_checked_and_places_and_job_words_are_not_subjects():
    """2026-11-28: the fire station twice running (the job guest had no check), and a rabbit "From Harrow Street
    Market" would have been the "Harrow Street Pony" by the street's name."""
    w = world_mod.seed()
    show = schedule.get("rockpool")
    guest, visitor = schedule._GUEST, schedule._VISITOR
    w.record_aired("interview", "Fire Station Visitor Shows Off The Big Ladder", None, "...", show="rockpool",
                   brief=guest)
    w.record_aired("interview", "Harrow Street Pony Hetty Carries Apples Up The Hill", None, "...", show="rockpool",
                   brief=visitor)
    same = lambda head, brief: writers._same_subject(head, w, show, brief)   # noqa: E731
    assert same("Fire Station Crew Member Shows Off Her Boots", guest)[1] == ["fire"]
    assert same("Lifeboat Helper Shows Off Her Dry Socks", guest) is None
    assert same("Lighthouse Keeper Shows How The Light Goes Round", guest) is None
    assert same("Clementine The Rabbit Visits From Harrow Street Market", visitor) is None
    assert same("Hetty The Pony Comes Back With Her Carrots", visitor)[1] == ["hetty", "pony"]


def test_gullys_poems_are_known_by_what_they_are_about():
    """2026-11-28: "Gully Shares A New Harbour Poem" was taken for "... A Brand New Beach Poem" twice."""
    w = world_mod.seed()
    show = schedule.get("rockpool")
    poem = schedule._POEM
    for head in ("Gully Shares A Brand New Beach Poem", "Gully Reads His Silly Chip Poem"):
        w.record_aired("links", head, None, "...", show="rockpool", brief=poem)
    assert not writers._repeated("Gully Shares A New Harbour Poem", w, show, T.links, poem)
    assert not writers._repeated("Gully Shares A Poem About Beach Crabs", w, show, T.links, poem)
    assert writers._repeated("Gully Reads A Silly Little Chip Poem", w, show, T.links, poem)
    w.record_aired("links", "Gully Shares A Poem About Beach Crabs", None, "...", show="rockpool", brief=poem)
    assert writers._repeated("Gully Reads His Poem About Crabs", w, show, T.links, poem)


def _make(head):
    return {"headline": head, "lower_third": "Rock Pool: The Make",
            "lines": [{"speaker": "kids", "text": "Let's make something!"}, {"speaker": "gully", "text": "Glue!"},
                      {"speaker": "kids", "text": "Ask a grown-up for the scissors."}]}


def test_the_retry_is_checked_too(monkeypatch):
    """2026-11-28: sent back for paper, Haiku came back with a paper plate; sent back for the sock boat, with a tube
    rocket after a loo-roll rocket. Nothing checked the retry."""
    w = world_mod.seed()
    w.record_aired("links", "Make A Paper Egg Box Bird At Home", None, "...", show="rockpool", brief=schedule._MAKE)
    heads = ["Make A Paper Egg Box Bird At Home", "Make A Paper Plate Shaker At Home", "Make A Sock Pot Holder"]
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        return schema.model_validate(_make(heads[len(asked) - 1]))
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=41, type=T.links, show="rockpool", target_s=180, brief=schedule._MAKE)
    writers.script_segment(seg, w)
    assert len(asked) == 3 and seg.headline == "Make A Sock Pot Holder"
    assert "Nothing with paper in it" in asked[2]
    # and no more than REPEAT_ASKS times: the last comes as it is
    heads[:] = ["Make A Paper Egg Box Bird At Home"] * 5
    asked.clear()
    seg = Segment(slot_id=42, type=T.links, show="rockpool", target_s=180, brief=schedule._MAKE)
    writers.script_segment(seg, w)
    assert len(asked) == 1 + writers.REPEAT_ASKS


def test_a_story_with_the_same_hero_is_asked_for_again_naming_the_hero(monkeypatch):
    w = world_mod.seed()
    w.record_aired("links", "Nettle the Gull and the Town Hall Clock", None, "...", show="rockpool",
                   brief=schedule._STORY)
    asked = []

    def write(task, schema, system, user):
        asked.append(user)
        head = "Hugh Tells the Legend of Nettle's Blue Shell" if len(asked) == 1 else "The Mermaid of Kessick Bay"
        return schema.model_validate({
            "headline": head, "lower_third": "Rock Pool: Story Time",
            "lines": [{"speaker": "kids", "text": "Story time!"}, {"speaker": "historian", "text": "Once, long ago..."},
                      {"speaker": "gully", "text": "Was there a chip in it?"}]})
    monkeypatch.setattr(llm, "complete_json", write)
    seg = Segment(slot_id=40, type=T.links, show="rockpool", target_s=240, brief=schedule._STORY)
    writers.script_segment(seg, w)
    assert len(asked) == 2 and "this one has nettle in it too. Nothing with nettle in it" in asked[1]
    assert seg.headline == "The Mermaid of Kessick Bay"
