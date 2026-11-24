"""The Late News on Channel 8: Channel 7's news, borrowed for the end of a short film's slot (the user, 2026-11-24).

A film too short for 21:00 to 22:30 (The Last Lot, 57 minutes with its cards) leaves twenty minutes that adverts
can't fill. After its credits, the film's show hands over to this one (Show.then, producer.THEN_MIN_S) until 22:30:
Dana Ferris at Channel 7's news desk, with Gordon's weather, a reporter's piece and a studio guest, as the rolling
news, then a last round-up and goodnight before the closedown. It is the town's own news, filed as Channel 7's is
(not fiction, unlike the film): the desk's stories, read for Channel 8's viewers.

The ident is the continuity announcer over Channel 7's news tune, borrowed with the rest.
"""
from __future__ import annotations

from newsroom.models import SegmentType as T
from newsroom.schedule import Item as I, Show

SHOW = "latenews"
IDENT = "On Channel 8, the late news from WTV, with Dana Ferris."
COLOUR = (200, 30, 30)              # the news's red

SHOW_DEF = Show(
    SHOW, "THE LATE NEWS", "NEWS", COLOUR,
    # The opening bulletin greets the viewers coming over from the film; the middle loops as the rolling news does
    # (a lap is about ten minutes, with the weather once in it, as Channel 7's), so the film's own length decides how
    # much of it airs; the close is planned once as 22:30 comes.
    pattern=(T.bumper, I(T.bulletin, "open"), T.field_report, T.weather,
             T.bulletin, T.interview, T.bulletin, T.field_report, T.sport, T.bulletin, T.field_report, T.weather),
    loop_from=4,
    closing=(I(T.bulletin, "close"),),
    target_s={T.bumper: 8.0, T.weather: 60.0, T.bulletin: 75.0, T.field_report: 90.0, T.interview: 90.0,
              T.sport: 60.0},
    cast=("anchor", "weather", "reporter"), lead="anchor",
    cast_by_type={T.interview: ("anchor", "guest"), T.bulletin: ("anchor", "reporter"), T.sport: ("sport",)},
    station=("The Late News on Channel 8, WTV's second channel: Dana Ferris reads the Port Wexley news from Channel "
             "7's newsroom, after tonight's film"),
    tone="warm, dry, local",
    repeats_overnight=False,
)

PLACE = {
    (SHOW, T.bulletin): {
        "open": ("PLACE IN THE SHOW: this OPENS The Late News on Channel 8, straight after tonight's film: a brief good "
                 "evening to the viewers staying with us after the film, then the top story."),
        "close": ("PLACE IN THE SHOW: this CLOSES The Late News on Channel 8: the night's main story in a sentence or "
                  "two, then Dana says goodnight from all at WTV. Nothing follows but the end of Channel 8's evening."),
    },
}


def register():
    """The show on the engine, with Channel 7's news habits (writers' same-story and auction rules) and its ident.
    Returns an undo."""
    from newsroom import assets, continuity, schedule, writers

    schedule.SHOWS[SHOW] = SHOW_DEF
    writers._PLACE.update(PLACE)
    writers.SAME_STORY_SHOWS[SHOW] = writers.SAME_STORY_SHOWS["news"]
    saved_news = writers.NEWS_SHOWS
    writers.NEWS_SHOWS = (*saved_news, SHOW)                  # the auction is news once, across both
    assets.IDENTS[SHOW] = (assets.CONFIG.paths.assets / "bumper_latenews_8.wav", IDENT)
    assets.IDENT_MUSIC[SHOW] = "news"
    assets.IDENT_VOICES[SHOW] = continuity.VOICE

    def undo() -> None:
        schedule.SHOWS.pop(SHOW, None)
        for k in PLACE:
            writers._PLACE.pop(k, None)
        writers.SAME_STORY_SHOWS.pop(SHOW, None)
        writers.NEWS_SHOWS = saved_news
        for reg in (assets.IDENTS, assets.IDENT_MUSIC, assets.IDENT_VOICES):
            reg.pop(SHOW, None)
    return undo
