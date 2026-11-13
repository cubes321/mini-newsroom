# Marina Row: the series bible

Channel 8's soap, agreed with the user on 2026-11-13. Twenty minutes at 20:20, after Wexley Wits, one episode
each Channel 8 night. It is not built yet: this is what the writers will be given (docs/ENGINE.md, "Channel 8's
evening", has where it sits and what it is built on).

## A street on television, not in the town

Marina Row is a **television street**: a set at WTV's studios. Nobody in Port Wexley lives there, and nothing
that happens there happens in the town. It is not **Harbour Row**, the real street by the harbour where the net
menders, the sailmaker and the clockmaker work. Every prompt that mentions the soap says so: its writers, and
Channel 7's writers when the soap comes up in town talk.

- Its **characters** are fiction and never join the town's people list.
- Its **actors** are Port Wexley residents, and they do join it. The news can interview "the actress who plays
  Queenie", never Queenie.
- Its storylines are never news: a soap theft is not a crime the news reports.

## The premise

The old net lofts on Marina Row have just been turned into flats and a restaurant beside a new pontoon for yachts.
The last crabbing family on the Row now lives next door to money from away: the old town against the new, which
soaps can run on for years. ("Row" rhymes with "go"; Channel 7 can still have its fun with "the Marina row".)

## The characters

| Household | Character | Who they are | Clashes with |
|---|---|---|---|
| **The Kernicks**, the old fishing family | **Queenie Kernick**, 70s | A skipper's widow. Sharp-tongued and immovable, she owns the last unconverted net loft and won't sell it. | Harriet |
| | **Davey Kernick**, 40s | Her son, skipper of the last crabber on the Row. Stubborn, decent, and behind on the boat's loan. | Tristan |
| | **Kerra Kernick**, 19 | Davey's daughter. She wants out of Port Wexley and is secretly working at the Lockwoods' restaurant. | Queenie |
| **The Lockwoods**, incomers from London | **Harriet Lockwood**, 40s | Has just opened **The Loft**, a small-plates restaurant in a converted loft. Charming and ambitious, she wants Queenie's loft next door. | Queenie |
| | **Tristan Lockwood**, 40s | Works from home and is desperate to be liked by the locals. He keeps making it worse. | Davey |
| **The Mermaid**, the Row's pub | **Sal Annear**, 50s | The landlady. Knows everything about everyone, and has history with Davey. | everyone, gently |

## The actors

Port Wexley residents, cast with British voices. They become residents of the town when the soap is built.

| Actor | Plays | About them |
|---|---|---|
| **Margery Trethowan**, 74 | Queenie | Forty years in the town's amateur operatic society; her first television part |
| **Dominic Carthew**, 46 | Davey | A former lifeboat volunteer, and a pantomime dame at the village hall for years |
| **Isla Glasson**, 19 | Kerra | A drama student at Greymouth College |
| **Philippa Moyse**, 44 | Harriet | Moved from Bristol; runs a Saturday drama school |
| **Rupert Kinsman**, 47 | Tristan | A voice-over artist: he does the ferry's safety announcements |
| **Gaynor Pawley**, 52 | Sal | A dental receptionist, and a karaoke regular at the Harbour Lights |

Every name was checked against the town on 2026-11-13: none is a resident's, a darts pub's or a business's.

## The places (the sets, chosen 2026-11-13)

Drawn by ComfyUI over layouts painted in code, picked on a contact sheet
(data/contact-sheets/2026-11-13-marina-row-sets.png), and registered at run time by `marina_row.register_sets` as
`marina_kitchen`, `marina_mermaid`, `marina_loft` and `marina_row`. They are studio sets, lit as painted; each has a
table, counter or wall across the front, with up to three marks (a, b, c) behind it.

- **Queenie's kitchen**, behind the net loft: a range, a dresser of plates, nets on the wall.
- **The Mermaid**: the bar, its regulars' corner and a window onto the Row.
- **The Loft**: bare brick, Edison bulbs, small plates, a view of the yachts.
- **The Row**: the quay at dusk, lamps lit: Queenie's net loft, the converted flats, The Loft's window, the pontoon.

## Opening storylines

1. **The pontoon**: Tristan's petition to extend the yacht pontoon would take the crabbers' moorings, and with
   them Davey's living.
2. **The loft**: Harriet offers for Queenie's net loft. Queenie says no. Harriet raises the offer.
3. **Kerra's secret**: she is working at The Loft, saving to leave.

**The first cliffhanger:** Queenie, out with the bins, sees her granddaughter through The Loft's window in one of
Harriet's aprons.

## Later

- **A guest star:** Imogen Vance-Ross, a visiting film actress already in the town (she fell into the harbour twice
  filming *Salt Row*), could join for a run of episodes, which would make a story for Channel 7. She is American,
  which would suit an incomer storyline.
- **Seasonal episodes**: the soap borrows the town's calendar (Bonfire Night, Christmas Eve), as real soaps do.

## How it airs (entertainment/soap.py, built 2026-11-13)

- **Planning**, from 18:30, on the "soap" route (Sonnet): every six aired episodes an arc (two or three storylines,
  a beat an episode); each night the episode: six scenes (set, characters, who knows what, what happens, what it
  ends on), five or six spare side scenes that change nothing, the cliffhanger's question and the exact closing line
  and who says it, and a summary. It answers the last aired cliffhanger first. A plan naming anyone outside the
  cast, or a set we don't have, gives way to the stand-in (the bible's first night).
- **On air**, 20:20 to 20:40: the titles, five scenes, then the spare minutes as side scenes (three, then a break,
  then quiet moments in turn), and the sixth scene, the cliffhanger, last, at the end of the slot. Each scene is
  written live (Haiku) to its plan and to what the scenes before it say; every line is a character. No captions,
  ticker or clock; each scene on its own set with its cast on their marks, in their actors' looks and voices.
- **Fiction**: no character becomes a resident, no headline or story comes of it, and its archive entries keep
  only that they aired. Its actors are residents, with their own voices.

## How the town hears of it (docs/ENGINE.md, "Harbour Row and the town")

- Each episode's cliffhanger becomes **town talk**: the question ("Will Queenie tell Davey?") and the Channel 8 night
  that answers it. Coastwide, the vox pops and Have Your Say can pick it up; it closes when the answer airs.
- **No spoilers**: the arc plan stays out of every other writer's briefing. The town knows only what has aired.
