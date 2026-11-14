"""The travelogue: Channel 8's factual slot at 20:40, alternating with Tideline (docs/FACTUAL.md, "The travelogue").

Not built yet. This holds what the user has chosen so far, as marina_row.py held the soap's cast before soap.py:
nothing reads it until the series is built.

The first series' host is **Lorna Quayle** (chosen 2026-11-14 from four; data/contact-sheets/2026-11-14-travelogue-hosts.png):
the town's most-seen celebrity, a comedian and singer, whose running story is waiting (fourteen minutes at the Saltby
ferry office for a biscuit; a waiting club). The proposed journey is the coast by every slow way there is,
collecting waiting stories.

- **Her look**: A of three hand-dressed (data/contact-sheets/2026-11-14-lorna-quayle-looks.png), keeping the face and
  ponytail she has had on air. Built, it should be pinned to her by name wherever she appears (scenes.PINNED_LOOKS),
  so she looks the same on Channel 7.
- **Her voice**: `bf_quayle`, a DramaBox design, C of three (data/voice-samples/travelogue-lorna), replacing the guest
  pool's shared `bf_emma`. Built, her Person's voice moves to it once (as soap._cast_actors does for the actors), so
  the town hears her in it everywhere.
"""
from __future__ import annotations

from newsroom.sprites import Look

HOST = "Lorna Quayle"
HOST_VOICE = "bf_quayle"
# A canary-yellow raincoat over a navy top, gold earrings, a ready grin; her skin, hair and ponytail as the town knows them.
HOST_LOOK = Look(skin=(232, 190, 160), hair=(150, 110, 60), top=(232, 190, 40), under=(40, 52, 96),
                 hair_style="ponytail", top_style="jacket", extra="earrings", extra_col=(220, 180, 60), mouth="smile",
                 brows="raised")
