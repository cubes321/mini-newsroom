"""Which channel is on air: its number, its name as written and as said, its wordmark and its group.

Channel 7 unless another channel's package swaps itself in (`entertainment.use()` puts out Channel 8).
The logo, the test card, the continuity announcer and the programme card read `CURRENT` when they
draw or speak, so they name whichever channel is on. Both of Port Wexley's channels belong to
Wexley Television, WTV (the user's name for the group, 2026-11-13), which the test card credits.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Channel:
    number: str = "7"                            # the numeral in the roundel, the bug and the stripes' count
    name: str = "Channel 7"                      # as written: cards, the announcer's script
    said: str = "channel seven"                  # as the writers are told it, in a prompt
    wordmark: str = "CHANNEL 7 · PORT WEXLEY"    # under the roundel, in the logo's own face
    group: str = "A WTV SERVICE"                 # on the test card, under when programmes resume


SEVEN = Channel()
CURRENT = SEVEN


def use(channel: Channel) -> Channel:
    """Put `channel` on air; returns the one it replaced (for an undo)."""
    global CURRENT
    before, CURRENT = CURRENT, channel
    return before
