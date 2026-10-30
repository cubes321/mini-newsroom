"""A new story whose headline is an open thread's title in other words continues that thread:
on 2026-10-27 the fire station's case for a second engine ran as twelve threads. The pairs here
are from that night's replay.
"""
from newsroom import world as world_mod, writers
from newsroom.models import BulletinScript, LiveLine, Segment, SegmentType


def _town(*titles: str):
    w = world_mod.seed()
    w.threads = []
    ids = [w.update_thread(None, t, "so far", now=1_790_000_000 + i) for i, t in enumerate(titles)]
    return w, ids


def _bulletin(headline: str, show: str = "news", kind=SegmentType.bulletin):
    seg = Segment(slot_id=1, type=kind, show=show)
    return seg, BulletinScript(lines=[LiveLine(speaker="anchor", text="News.")], headline=headline, lower_third="News")


def test_the_same_story_in_other_words_is_found():
    w, (engine, baker) = _town("Port Wexley fire station pushes for a second engine",
                               "Market baker serves up petition with his sourdough")
    assert w.same_story("Fire station makes its case for a second engine")[0].id == engine
    assert w.same_story("Market baker's petition grows a second sheet")[0].id == baker


def test_stories_that_only_share_a_street_or_the_town_are_not():
    w, _ = _town("Fire Officer Bea Kowalczyk Rebuilds a Wooden Dinghy",
                 "Port Wexley harbour wakes up at first light")
    assert w.same_story("Kit Anand's Harrow Street Coffee Stall Sells Out by Seven") is None
    assert w.same_story("Port Wexley harbour tide due at noon") is None


def test_the_news_follows_it_up_instead_of_opening_another():
    w, (engine,) = _town("Port Wexley fire station pushes for a second engine")
    seg, script = _bulletin("Fire station makes its case for a second engine")
    writers._apply_to_world(seg, script, w)
    assert seg.thread_id == engine and len(w.threads) == 1 and w.thread(engine).mentions == 2


def test_a_faded_story_coming_back_revives_its_thread():
    w, (engine,) = _town("Port Wexley fire station pushes for a second engine")
    w.thread(engine).phase = "faded"
    seg, script = _bulletin("Fire station makes its case for a second engine")
    writers._apply_to_world(seg, script, w)
    assert seg.thread_id == engine and w.thread(engine).phase == "developing"


def test_breaking_news_still_opens_its_own_and_a_closed_thread_stays_shut():
    w, (engine,) = _town("Port Wexley fire station pushes for a second engine")
    seg, script = _bulletin("Fire station makes its case for a second engine", kind=SegmentType.breaking)
    writers._apply_to_world(seg, script, w)
    assert seg.thread_id != engine
    w.thread(engine).phase = "closed"
    assert w.same_story("Fire station makes its case for a second engine")[0].id == seg.thread_id


def test_a_faded_thread_needs_more_of_its_title_to_come_back():
    w, (boats,) = _town("Harbour Boats Lashed Down as Crews Wait on Divers")
    w.thread(boats).phase = "faded"
    assert w.same_story("Lifeboat crew asks small boats to wait for daylight") is None      # 3 of 5
    w.thread(boats).phase = "developing"
    assert w.same_story("Lifeboat crew asks small boats to wait for daylight")[0].id == boats


def test_an_open_thread_wins_a_tie_with_a_faded_duplicate():
    w, (live, old) = _town("Fire station's second engine case: fire crews walk the gap",
                           "Fire crews make their case for a second engine")
    w.thread(old).phase = "faded"
    assert w.same_story("Fire crews walk the gap: case for a second engine")[0].id == live
