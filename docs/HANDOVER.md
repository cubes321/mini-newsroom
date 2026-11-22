# Handover

## Picking up after the Channel 7 night of 2026-11-21

A real Channel 7 night on the real town, started 18:34 from `data/night_channel7.cmd` with the pictures on. The backup
is `data/world.backup-2026-11-21-pre-night.json`, the log `data/logs/station-2026-11-21-1834.log`. It ran the code as
it stood at 18:34: none of that evening's work (the council fixes, The Chamber's turns, the weather map, the travel
board, the route map, the town close up) was in it.

### The night's review (2026-11-22 morning)

It ran 18:34 to 06:34 and exited cleanly: 660 segments, 48 adverts, no filler, no fallbacks, no stand-ins, worst p99
12.0 ms. Sound is in all seven recordings checked (Full Time, Coastwide, The Inquiry, The Panel, The Last Ferry,
Seventext, Morning Tide: mean -26.6 to -31.6 dB, no silence of five seconds).

- **As intended:**
  - The senior editor reviewed at 18:52, 20:52, 22:52 and 00:52, and held off at 18:38 and 02:52. Eight merges.
  - The desk made 24 rounds, six of them with nothing to do; nine seeds; stories moved in the pool.
  - The editors' meeting at 18:41, four turns and the minutes.
  - 173 overnight repeats, in line with the nights before (175, 188, 184).
- **Both of the 20th's fixes aired and worked:**
  - **The Last Ferry booked nine guests, each once** (an interview and its second part). No guest came back.
  - **The closes waited for their endings.** t506 (the row) closed at 19:09, after the 18:35 bulletin on it. t586
    (the match) was held at 19:09 ("is to close once its ending at 15:00 has been reported") and closed at 21:09,
    once the desk had folded the result's own thread into it. t606 (half-time, no clock time) was held twice and
    closed at 21:39.
- **Miles's report was the hake fourteen times running.** "Hake Glut Keeps Fish Quay Busy Into the Night", from the
  fish quay, was written for every field report from 23:06 to 23:48, and went out again in the repeats (13 times).
  - The prompt listed it three times under MILES'S LAST REPORTS, "this one goes to a different story and place".
  - Nothing asked again: one item a cycle never makes two of the news's last four (`_same_story_again`).
  - **Fixed the same morning:** a field report that tells one of his last three again, by its thread or its
    headline's words, gets one more ask, and the code names the story he goes to: the first quiet one he hasn't just
    done (`writers._reported_already`, `_send_miles`). Replayed with Haiku on a copy of the town, from three hake
    reports: eight reports, eight different headlines, the new ask twice. Not aired yet.
- **Two templates:** Coastwide's interview at 19:29 (Dev Ramachandran: no valid output in two attempts), and The
  Inquiry's feature at 20:14 (it booked THE GUEST, Gerald Thorne, for an item that isn't his).
- **The pictures** (shadow mode): ComfyUI came up at 18:37 and the painter made 101 pictures, the last at 06:26; 47
  more were skipped as the same story again. The launcher stopped ComfyUI at the end and the card is free.
- **Model use:** Haiku 575 calls (7 failed validation once), 3.59M tokens in (1.70M read from the cache) and 294k
  out; DeepSeek thinking 102 calls, 796k in and 251k out; Sonnet 7 calls, 130k in and 17k out.
- **Small:** in the replay Haiku put "the Ferryman bar" in Saltby; the Ferryman is by the Quay Steps on the new map.

### The night's scripts, read closely (2026-11-22)

All 325 scripts first aired that night (about 65,000 words; the 173 repeats left out) were checked mechanically
and read line by line, a reader a show, against a sheet of the station's own facts. The claims below were checked
against the scripts. None is fixed yet, except the hake.

1. **The tides and the ferry are wrong in nearly every forecast.** 13 of the evening news's 14 weathers, 4 of the 6
   late ones, and Coastwide's.
   - Saturday's table is given as "tomorrow" ("High water tomorrow comes at twenty to five in the morning, five
     point one metres": Sunday's was 05:00, 5.3 m). `tides.for_prompt` gives today's table only.
   - Times already past are told as to come ("high water at sixteen thirty-five" at 19:06), and the reverse.
   - The ferry sails in its low-water gap (none 21:58 to 23:38): Miles is "out here on the last ferry" at 22:24 on
     The Last Ferry; Morning Tide has it "running since seven" at 06:20.
2. **Results and people change between items.**
   - Coastwide gave the Tides' result three ways in twenty minutes: "at home to Saltby Rovers this afternoon" (19:00),
     "shared the points" and "draw one apiece" (19:03 to 19:20), then three-one. The news and Full Time had it right.
   - Full Time: Shore and Price given two goals each, a "clean sheet" in a 3-1, the Wreckers' win "a fortnight ago".
   - Coastwide's interview captioned Ruby Tennant (19:36) has "Ned Carrow, retired ferry deckhand" answering as
     the rower.
   - The rope is fitted at 18:41 and "on order from the chandler in Greymouth" at 21:58; the red spinnaker has
     flown, will fly on Sunday, and stays wrapped; the hospice tin is counted before its Tuesday count.
3. **Council business is made up.** The Inquiry's guest says the budget committee "agreed the two-panel booking.
   That was a decision", with minutes, none of it in the story; its close then says "what we have not been able to
   establish is who drew that limit". The Panel has "Gerald Thorne's committee decides on the twelfth".
4. **No sense of the hour or the day.**
   - The overnight documentaries tell Sunday morning as past at 01:00 to 03:30 ("By ten past eight the slip was
     empty"; "The mayor came down the steps at half past ten").
   - Morning Tide on Sunday is a weekday: a school run at 06:07 ("Parents are queuing at the gates by the Academy"),
     shops selling out "before nine" at 06:31.
   - Thursday's darts is live tonight; the match crowd is still arriving at 21:01.
5. **Who is speaking.**
   - A presenter thanks themselves at a hand-over, 22 times: Fran ("Thanks, Fran here at the sports corner"), Pat,
     Dana, Rosie.
   - Lines go to the wrong mouth: The Last Ferry's second-guest items give the host's line to the guest (4 of 8);
     Gordon and Miles speak a guest's answer.
   - On Morning Tide Rosie reads every headline and Dana never speaks: check whether that is meant.
   - The briefing is read out: "Full council sits on Thursday the third of December, live on The Chamber at eight"
     on The Panel, which then signs off "Back on the third of December, live on The Chamber at eight".
6. **The loops repeat, as The Chamber's did.**
   - The Last Ferry is one five-item cycle five times: the same viewer's letter five times, the papers four, and two
     second halves that rerun the first half nearly line for line.
   - The Panel asks its four questions, says "our final round of the evening", then runs six more items, the first
     question again as "the first question tonight".
   - The Inquiry's four questions are all asked by 20:07 and put again to six more guests; its guest is trailed four
     times after he has gone.
   - Full Time's round-up airs three times; all three guests are Tides players.
   - Coastwide: ten links under one caption, about 25 subjects in 61 items, and a close that is an opening ("Good
     evening, and welcome to Coastwide").
   - The news: the Tides' result in about 34 of the evening's 75 items.
7. **The same few people and tics.** Dolores Finch in about 28 evening news items; Marjorie Pell in 18 scripts on four
   shows; Brenda Fisk four times in seven minutes of Morning Tide. Miles "out of breath" 22 times. Seven Ruths on
   Coastwide, five on The Inquiry; a Coastwide guest named Gordon Pell.
8. **Writing.** The 24-hour clock read aloud ("kick-off fifteen hundred", "twenty-two forty-eight"); "back to the
   rolling news" (6); lines that mean nothing ("Sit in the tea urn and wait for it").

Came back clean: the greetings fit the hour, nobody gives the wrong name for themselves, and the news never had the
score wrong. The Last Ferry's empty first lines are the band's sting. Two flags were the sheet's fault, not the
scripts': The Inquiry is Pat's, and the sheet's 11 degrees was the night before's.

**Fixes, in the order they would pay:** the tides and ferry in the prompts (tomorrow's table, and what has passed);
the hand-over that thanks the speaker; turns in code for the other loops, as for The Chamber; the hour and the day
for the documentaries and for Sunday; why Coastwide had the match as still to come.

## Picking up on the evening of 2026-11-20

**Tonight** is a real Channel 7 night on the real town, started 20:51 from `data/night_channel7_nopictures.cmd`: the usual
launcher with `$pictures = $false`, because the user wanted no ComfyUI tonight. That copy is a one-off; the normal
`night_channel7.cmd` still makes the pictures. The backup is `data/world.backup-2026-11-20-pre-night.json`. It is the
first airing of the news locator (b645a77). Review its log with the checks in "The overnight run" below.

### The night's review (2026-11-21 morning)

It ran 20:51 to 08:51 (`data/logs/station-2026-11-20-2051.log`) and exited cleanly: 710 segments, 72 adverts, no
filler, no stand-ins, no fallbacks, worst p99 14.7 ms. Four Haiku calls failed validation once and passed on the second ask.
DeepSeek refuses strict json_schema now and drops to json_object mode at the first call, as it did on the 19th.
Sound is in every recording checked (The Panel, The Last Ferry, Seventext, Morning Tide; mean -26 to -32 dB, no
silences of five seconds).

- **As intended:**
  - The senior editor reviewed at 21:09, 23:10, 01:10 and 06:45, then 08:45, and held off at 20:58 and 03:10.
  - Each memo's crowded day was a different one, and the desk moved stories in the pool (t529, t594, t430, t454, t445).
  - Seven quiet rounds, eight seeds, and the editors' meeting at 20:58.
  - The overnight repeats were in line with the 18th and 19th (184 against 175 and 188).
- **The locator works:** on Morning Tide's 06:02 fish quay report it went up top right for its first seconds and
  cleared. It stays off when it isn't sure: the 06:22 report was "the Quay Steps by the lifeboat slipway" in its
  words, filmed on the cannery slipway. By headline alone, 15 of the 27 field reports have a place (more with their
  briefs and backdrops). The news itself isn't recorded, so the studio wall's locator hasn't been seen on air yet.
- **The Last Ferry booked Dev Ramachandran four times in one show** (slots 115, 117, 137 and 139). He had also just
  been on The Panel. At slot 137, "Jo Pascoe was just on" was asked again and the answer, Dev, wasn't checked again.
  The "has been on before" ask then booked Owen Kersey instead, so "keeping the script before" kept Dev. Ruth Averill
  was picked again three times too (slots 129, 140 and 146), and caught each time. **Fixed the same morning:** the
  replacement guest is checked too, with one more ask that names everyone who is out. And when the "has been on
  before" ask comes back with someone new, the new guest is kept if the one before was just on.
- **A close stood on a morning preview:** t506 (Ruby Tennant's row) was held "to close once its ending for Saturday
  21 November has been reported". At 07:58 the desk closed it with "comes back up the slip at ten past four", the
  time and the £2,880 written as done. The night ran the code from before df60ba6 (committed at 21:02, after the
  20:51 start), so the note's lack of a day let it stand. With df60ba6 `_kept` would have held it, but the breakfast
  previews ("Nears the Finish", "Keeps Rowing") would still have counted as the ending. t569, t586, t604 and t606 were
  still held when the run ended, waiting on this afternoon. **Fixed the same morning:**
  - `world.due_time` reads the time of day a NEXT names ("ten past four", "kick off at three", "by ten", "this
    evening"), and `Thread.covered_ts` is when a piece on the story was last written.
  - When today's closing note, or the NEXT it was held with, names a time, the close stands only once a piece has
    been written at or after it. Until then the story keeps its ending-to-come as its NEXT ("is to close once its
    ending at 16:10 has been reported").
  - **Still open:**
    - An ending with no time ("at half-time", t606) still closes on any piece that day.
    - A close naming no day, for a story that was never held, still stands, unless the story's own NEXT has its
      ending today (fixed 2026-11-21, 47aee0c; t586).
    - Threads from before this change have no `covered_ts`, so their first close today waits for a new piece.
  - **In the real town:** t506 was closed with this afternoon's finish written as done. At the user's word it was
    reopened at 09:15 on 2026-11-21. It is now resolving, held for that day, and last covered at 06:45. Its NEXT is
    the finish still to come: the held NEXT's full text wasn't kept anywhere, so it was rewritten from the closing
    note, without the figures. Nothing else in the town carried the close. The backup from before the edit is
    `data/world.backup-2026-11-21-before-t506-reopen.json`. Replayed on a copy: a close after another morning
    preview is held, and one after a piece at 16:40 stands. If the next run is after Saturday, the day has gone by
    and the desk's next close stands as before.
- **Morning Tide's field reports go round the same few things:** 27 in under three hours on a quiet Saturday. Eight
  were on the big tides, four on the lifeboat crew at the slipway, and three on the morning rush.

### The second scratch Channel 8 evening (2026-11-21, 09:34 to 12:54 real time)

17:45 to 21:05 on its clock, from `data/afternoon_channel8_scratch.cmd`. The log is
`%TEMP%\newsroom-scratch-m3xxj256\logs\station-2026-11-21-0934.log`, the model calls are in `llm_calls/` beside it, and
the recordings are `E:/recordings/2026-11-21 *.mp4`. It exited cleanly: 144 segments, 49 adverts, no filler, worst
p99 5.3 ms. Every show ended on time. All eight recordings have sound, with no silences of three seconds. The desk ran
on the scratch copy and held t506 ("closed again without its day; the hold stands"). The real town is untouched:
`data/world.json` was last written at 09:13, and `data/travelogue/lorna_quayle.json` on 11-14. The run did read that
saved route from the real `data/`.

- **As intended:**
  - **High Water:**
    - rounds of 190, 193, 212 and 195 s;
    - two chats;
    - the banner gone by six seconds;
    - the whole gauge in view, with the tide and the climbers' marks right;
    - no result on the ticker before it aired, in the frames checked.
  - **Wexley Wits:** the banner shows the round's tag ("Round 4: The Week's News"), never the score.
  - **The Kettle's On:**
    - 16 calls, with no pet name twice;
    - Cyril on the sofa at 19:15 and 19:29;
    - two duels (tea, egg);
    - the dish out at 19:58.
  - **The Coast Road:** a Sonnet route that passes the map check. The saved route didn't, so it was planned again.
  - **The Slipway:** the booked guests each came once (Wren twice, with Have a Go), none came back in the loop, no
    pasty, and the goodbye named The Kettle's On.
- **Items run short and the loops pad them,** on four shows:
  - **The Slipway** had eight of Tegan and Elis's bits (slots 33 to 40), not four. Its booked items came to about
    780 s against 1240 of targets.
    - **Why: the line cap.** `LINE_CAPS["slipway"] = 16` was set to lift the links from 12, but an interview's own
      cap was 16 already, so the interviews never got more. 16 + 2 lines is about 150 s here: 14 lines ran 112 s
      (the feature) and 16 ran 140 s (Have a Go). The targets are 220, 200 and 160 s.
    - The how-to (Ned Carver) came back at 21 lines twice, about right for its 200 s, and was thrown out both times
      for a 15 s template. That one cap likely explains both the template and most of the padding.
    - **Fixed the same afternoon** (16975e8): a show's line cap can be one per item type (`writers.line_cap`), and
      The Slipway's interviews have 28, its links still 16. Rehearsed on a copy of the town
      (`rehearsal-1119/rehearsal-slipway-cap28.log`): the feature at 19 lines (~234 s of 220) and the how-to at 19
      (~168 s of 200), no template, the booked items ~1200 s of 1240 by the rehearsal's estimate. Not aired yet.
    - The bits contradicted each other. They also carried results as chat ("Tides 3-1 Saltby", Darren Rodda's 83
      checkout); the desk had the same match one apiece.
  - **The Coast Road** had three visits, then six near-identical waits on the promenade: flask, parkin, gulls. One of
    them (slot 134, 3 lines) was only Lorna's half of a talk with Ruth and an unmet boatman.
  - **Wexley Wits** had five chats after the rounds, inventing questions nobody was asked. Both darts rounds aired as
    templates (38 s each): the model gave a thrower's first dart to the thrower, not to Clive. The check is right, but
    it isn't asked again.
  - **Marina Row** kept its plan (nine scenes and the three spares: the pint, the gansey, the oilskins), but its scenes
    ran 24 to 113 s. The rest of its 19 minutes went to eight unplanned scenes, three of them stock quiet moments, in
    20 scenes in all.
- **High Water:**
  - The spring tide's script ended with Des putting Ada's first question to Ruben, who doesn't play it.
  - Round four said the swap backwards: "the step-four prize... that's yours now".
  - The chats gave Ruben a "Hal" in one and a wife Ellen in the next.
  - The meets ran 56 and 80 s of 120, and the Harbourmaster's round 128 of 180.
- **The Coast Road's route:**
  - The creative editor sent Sonnet's first route back for doubling back on itself.
  - The second attempt hit the 32000-token cap with broken JSON. The third (31755 tokens out, 224 s) was taken without
    another look. By its leg titles it still doubles back: "East to the End of the Line", then "West Again to the
    Lighthouse". The stops weren't checked.
  - About 84k Sonnet output tokens for one route, and the one taken came within 245 tokens of the cap. If both
    attempts are cut off, the stand-in route made in code takes the series (`travelogue.plan_route`).
- **The desk closed t586 (the Tides v Saltby match) with no report of it** (10:06:59; 18:06 on its clock). The closing
  note gave the result, "ended one apiece", and named no day. The story had never been held, so the close stood: the
  open gap "a close naming no day, for a story that was never held". Its NEXT had the day and "kick off at three". In
  the real town t586 is at its peak for today, and a real night tonight could close it the same way.
  - **Fixed the same afternoon** (47aee0c): a close naming no day takes its day from the story's own NEXT when that
    names today, and the time gate then holds it until a piece is written after the ending's time. Replayed on a copy
    of the real town: held at 18:06 ("is to close once its ending at 15:00 has been reported"), closed after a report
    written at 18:30. A NEXT with no day, or another day, leaves such a close standing as before.
  - Small, and as before for held stories: when the close then stands, the story keeps the held NEXT (the kick-off),
    not the desk's closing note.
- **Wren Ashdown was on three times in one evening:** The Slipway's feature, its Have a Go, and The Coast Road's first
  visit. The creative editor named her as an example to the route planner.
- **The creative editor's marks:**
  - fair: High Water, The Slipway, The Kettle's On, Marina Row;
  - weak: Wexley Wits (last week's notes unheeded: vague news questions, one story in two rounds, stock chestnuts) and
    The Coast Road.

### What changed on 2026-11-20 (all pushed, `ba6d6de..153d902`)

- **High Water's art and sound**, done and approved:
  - Des's look, A (9a59c3d), with a new `Look.bow` that is off by default;
  - the tide gauge, `entertainment/tidegauge.py` (4e58096);
  - the two sets (60db5ad);
  - the three presenters' voices and the idents (0e19fea, from the side sessions).
- **High Water's result in the town's talk** (9e2de9d): `talk.highwater`, from a stamp `highwater_show.aired` sets.
- **A scratch Channel 8 evening** (17:45 to 21:05 on its clock, real models, OBS; recordings
  `E:/recordings/2026-11-20 10-40 High Water.mp4` and on) found these, all now fixed:
  - Results ahead of play: Wits' and High Water's round results were in the banner as the round began (497a44c),
    and High Water's were on the ticker too. The Chamber's votes were on the ticker as each motion was called
    (a7b9be9). `player.TICKER_AFTER` holds them till the item ends, and the banner shows the item's tag instead.
  - The banner hid the gauge's bottom four steps: High Water's banner now clears after six seconds (`player.BANNER_S`,
    edc6b0e).
  - The Slipway ran out of booked material at a quarter to seven and brought its guests back for a quick five.
    Now it books ONE TO WATCH and YOU ASKED as well, the loop is Tegan and Elis's bits only, the breaks are two
    minutes, and the line cap is 16 (8658225). Rehearsed: about four bits at last night's lengths.
  - High Water's rounds came back terse and four chats filled the gap; the chats invented waves; the close seemed to
    lose Hector's tap. Now a round's brief asks for about five lines a question turn, the chats get the game so far
    (`{sofar}`), the swap to a better prize is said, and the booking asks grown-up questions with checked answers
    (0373a26). Rehearsed: rounds of 170 to 204 s.
  - A guest's line that started "Ruth Hollis: 1066." loses the name, on every interview-shaped script (6af3be1).
  - The Coast Road's waits put Lorna back on the ferry after she had landed. They are now at the last stop
    (bb61d5c).
  - A recording's name was "The Kettle'S On" (2e422ed).
- **The town's map**, in the side session "A defined map of Port Wexley and the coast": `newsroom/geography.py`, its
  drawing (approved), and a route check for The Coast Road (2e4cbcf, c5fab51, a881af5). Also **the news locator**:
  a Channel 7 item's place on the map, briefly (b645a77). See docs/ENGINE.md, "The map of the town".
- **The Coast Road's route is planned by Sonnet** (153d902). On The Chamber's route, DeepSeek spent its whole
  32000 tokens thinking and answered nothing. Rehearsed: a six-leg route on the map at the first try, home to the
  town hall steps. The real town has no route yet; the one saved on 2026-11-14 goes against the map and will be
  planned again.

### To do next, in order

1. **The 2026-11-20 night's review** (above): both of its fixes are in (The Last Ferry's double booking, the close on
   a preview). Neither has aired yet. t506 is reopened in the real town.
2. **Fix what the 2026-11-19 council night's review found.** The station itself ran cleanly: no errors, no filler, sound
   in every recording checked, memos, pool moves, quiet rounds and seeds all as intended. But:
   - **The Chamber ran on the stand-in's four motions** (log line 224, 18:53): already fixed in ba6d6de. Its four
     generic promises (p001-p004, due 3 December) are in the real town.
   - **The news said council "sits tonight" until 05:42**: 20 airings after it had risen, and one invented a result
     ("Ferry Rail Costings Sent Back Again", t585, never on the agenda). `council.calendar_line` keeps "(tonight)" all
     day; the briefing never says the meeting is over.
     **Fixed 2026-11-21 evening:**
     - From eight on a council night the briefings (writers, desk, editors) say the meeting is over and give its votes
       from the night's record, "and nothing else"; with no record (Channel 8's night, a late start) they say to
       report no result. The Chamber's own items still get "(tonight)" (`summary_for_prompt(sitting=True)`), and
       Seventext's notices a short "met tonight".
     - The overnight repeats leave out a piece that mentions the council and was written before the meeting began
       (`workers.before_council_sat`): 02:10 and 02:57's "council sits tonight" were repeats. "Council" matches
       "councillor" too, so on a council night an earlier piece with a councillor in it isn't repeated either. The
       repeats up to 05:42 were of pieces written after eight, which the briefing now covers.
     - Replayed with Haiku on a copy of the town at 23:06 on the 19th: none of 8 bulletins had the council still to
       sit, 7 reported the four votes as carried 5-0, and none gave a vote that wasn't taken. Not aired yet: the
       next full council is Thursday 3 December.
     - Still open: the day after, the briefing has only the next meetings, not last night's votes (the stories carry
       them).
   - **The Chamber's second half repeated itself**: Hammond's question (slots 98 and 110) and the harbour office
     accounts (104 and 116) written twice, and links still saying "bowling green left" after motion 4 was debated.
     **Fixed 2026-11-21 evening.** The cause: the loop's six interview briefs came round two or three times in the
     hour (14 loop interviews), word for word the same, and the same brief got the same item whatever "do NOT do
     these again" listed.
     - **The code takes the turns** (`chamber._in_turn`, marks in the loop's briefs): `{who}` is the next councillor
       round the table, `{vote}` the next of tonight's motions, `{report}` the next of three officers' reports,
       `{ward}` the next ward to bring a petition, `{story}` the next story off the agenda, `{resident}` somebody who
       hasn't spoken. A brief that has been round before is told the headlines it made then.
     - **The agenda says where each motion stands** ("VOTED: CARRIED 5-1" or "not yet voted on", and "no motion is
       left to come" once all are).
     - **The writer's repeat check covers the loop** (`writers._repeated`): one more ask when a headline is 0.4 like
       an earlier item's (links: 0.5, same brief). Not the motions, nor a question on one.
     - **Replayed twice with a real booking and Haiku**, the whole hour on a copy of the town from before that night
       (37 and 39 items). In the second: six councillors took the six turns, three different reports, seven
       different people at the lectern, two petitions from two wards, and no link had a vote still to come. One
       pair alike: the Cannery plaque quote, at 20:16 and 20:34.
     - **Still open:**
       - A question on a vote can leave its vote: in both replays the second `{vote}` turn, on the fire engine, went
         elsewhere (Dev Ramachandran's winter market; the Cannery plaque again). The second time it had been
         re-asked for "a different subject", so a `{vote}` question is no longer re-asked; the first time it hadn't,
         so that isn't the whole cause. Perhaps "no motion debated twice" in the so-far list. Not replayed since.
       - The loop's items follow stories up: `{story}` and `{vote}` name a story by id, and seven loop items in the
         second replay filed under one (t484's and t525's status lines were rewritten by a resident's question; their
         NEXT and promises stood). Worth a look with the senior editor's undoing of the votes.
       - Miles's gallery has regulars: Dougal Crane and Ruth Penhaligon were asked four or five times each.
       - Dana's recap links are alike by nature ("Four Votes Carried, ..." three times).
       - A councillor's "not on tonight's agenda" question still strays onto the agenda (the harbour wall).
       - The items run at about 40% of their targets (interviews ~125 s of 330, 7 to 14 lines, under the cap of
         24), which is why the loop goes round so often.
       - "Who has spoken" comes from the names found in each item's first 400 characters, so it also lists people
         only mentioned.
   - **The senior editor undid the votes within the hour**: its 20:52 memo had t476 closed (p004 lapsed) and t447 moved
     to 4 December while p002 stands for the 3rd.
     **Fixed 2026-11-22.** The senior editor was told nothing of the council's promises, and nothing stopped the
     desk acting on its memo.
     - **The desk can't** (`desk._promise_stands`): while a story's promise is open and not yet due, an update that
       closes the story, or gives it a NEXT for a day past the promise's, is dropped. A verdict on the promise in
       the same plan lets either through; an overdue promise no longer holds its story.
     - **The senior editor is told** (`promises.for_senior`): every open promise, and that those stories keep their
       day. The desk's own promise note says the same.
     - **Replayed on a copy of the town from before that night:** the four motions carried, then the memo from the
       real model (it left all four alone: "No council steps before 3 December except t433") and the desk's two
       updates of that night, both dropped. All four promises still open. One memo only, so watch the next council
       night (Thursday 3 December).
     - **Two holes closed the same morning:** a verdict the desk then skips (on a story only within the memo's
       reach, the way t447 and t476 came on the 19th) no longer lets a close through; and a promise that came with
       a story folded into another holds the story it joined.
     - **Two real desk rounds under that night's own memo** ("Move t447 to Friday 4 December, off the council day
       ... Take t476 off the 3 December council: close it quietly"): both times the desk gave t447 a NEXT for the
       4th and it was dropped; no verdict was given early; all four promises stayed open.
     - **Still open:** a promised story left on the board that goes quiet still fades, and its promise lapses with
       it, as before. The four of the 19th all wait in the pool for their days, where nothing fades.
     - **In the real town:** t447 had been left waiting for Friday 4 December with its promise (p002) due on the
       3rd. At the user's word it was repaired on 2026-11-22, with the station off: it waits for Thursday 3 December
       and its NEXT is the officers' report to full council. The NEXT it had (Marjorie Pell and Winifred Cobb putting
       the front-row woman down as a Denshaw) is in the backup,
       `data/world.backup-2026-11-22-before-t447-repair.json`. Nothing else in the town was changed. p004 lapsed
       when t476 was closed, and stays lapsed: the story is gone.
   - **Fixed 2026-11-20 evening** (`Thread.closes_on`, `desk._kept`): **the close hold was bypassed**: t513, t558 and t560, held at 19:22 till their days, were closed at 21:22 after a
     memo's "close them on the board now", with closing notes naming no day; two never aired again.
   - Small: one sport stand-in (a line over 900 characters, 23:34); t587 held for Friday's thaw, never covered.
3. **The second scratch Channel 8 evening ran on 2026-11-21** (above). High Water's, Wits' and The Kettle's On's
   checks pass. Still open:
   - The Slipway's padding, to see on air now its interviews' cap is 28 (16975e8);
   - The Coast Road's six waits;
   - Wits' darts templates and its five chats;
   - High Water's stray spring-tide line;
   - Wren on three times in one evening;
   - the route taken without a second look.
4. **Not fixed:** High Water's Harbourmaster's round and its two meets run at about half their targets (90 s of
   180, 60 of 120). The rounds and chats fill the time now.
5. **The map's next uses**, as the user ranked them after the locator: travel news and the weather, then the rest
   (Out and About's walks, Full Time's away grounds, the callers' streets).
   - **The weather map is built** (2026-11-21, `newsroom/weathermap.py`; docs/ENGINE.md, "The map of the town"):
     the wall screen drawn from the gazetteer, four spots with temperatures worked out in code from the script's
     one, every sky moving. Approved on `data/contact-sheets/2026-11-21-weather-map.png` as stills; the motion
     hasn't been seen. The weather scene renders in 0.2 ms (p99 0.4).
     - Gordon is told the spots in words only. Told the rules and asked for figures, Haiku named a spot in all six
       trial forecasts and got one figure wrong; told "a degree or two colder" and one place at most, two of six
       named one, both rightly, with no figure.
     - Not aired yet: look at the first weather of the next run.
   - **The travel board is built** (2026-11-21, `newsroom/travelboard.py`): on the wall while Jonah reads Have Your
     Say's travel, with the bus, the ferry and the tide from code. Morning Tide has no travel item, so it isn't
     there; one could be added. Approved as stills on
     `data/contact-sheets/2026-11-21-travel-board-and-route-map.png`. Not aired yet.
   - **The Coast Road's route map is built** (2026-11-21, `newsroom/routemap.py`): the journey in the corner for the
     first line of the opening and of each road item. Approved on the same sheet, drawn from the stand-in route.
     The saved route in `data/travelogue/lorna_quayle.json` is the one that failed the map check, and its stops
     place oddly (leg 2 all at Saltby, leg 3 from the Quarry Field to Greymouth Point). Not aired yet.
   - **The locator reads the report's own location first** (f6865d0): expect it up on nearly every one of Miles's
     reports now, not about half. Look at where it puts them on the next night.
     A name inside a longer one still counts: "Harbour Row" (5 of the 118) is captioned Port Wexley harbour, and
     "the Cannery Tap" the old cannery. Both are a few hundred yards out; a more detailed town map would fix it.
   - Checked 2026-11-21: this morning's planned route places 18 of its 18 stops; both graphics render in under
     half a millisecond; whoever reads the travel stays at the wall between lines.
   - **The town close up is built** (2026-11-21; docs/ENGINE.md, "The map of the town"): 18 more places, the
     town in streets and blocks with 29 unnamed side streets, and the locator a mile across in the old town.
     Approved on `data/contact-sheets/2026-11-21-town-plan.png`. Not aired yet. To watch for on the next night:
     - a pub's name read as its pub when it wasn't meant ("the ferryman" on the ferry, "the lantern"). Each was
       put where a stray match is still about right, but look at where the locator lands;
     - "the Railway" is the pub now, not the station (they are next door);
     - The Coast Road's planner is told the new places as "Nearby" to each stop (`geography.coast_text`).
   - **Next on the list:** Out and About's walks, Full Time's away grounds (some league towns aren't in the
     gazetteer), the callers' streets; and, new: The Chamber's wards, breaking news, Tideline, Seventext's coast.

## Picking up after the Channel 7 council night of 2026-11-19

The night of Thursday 19 November was a real Channel 7 run on the real town: full council, The Chamber live at
20:00. It was started at 18:45 from `data/night_channel7.cmd`, and its pre-night backup is
`data/world.backup-2026-11-19-pre-night.json`. Review its log first, with the usual checks below ("The overnight
run").

### What changed on 2026-11-19 (all pushed to origin/master, `64b25ed..d8c2be3`; none of it has aired)

A scratch Channel 8 run that afternoon (`data/afternoon_channel8_scratch.cmd`, a temp copy of the town) led to:

- **Two bugs fixed.** The Chamber and Have Your Say are booked only when their show airs on the channel that's on
  (8f2e67e). Wits' Who Said That reads only whole sentences (6eeea8a). Wits' scoreboard no longer freezes when a
  question is offered over and nobody takes it (d5dc5ea).
- **Marina Row** plans 9 scenes asked at 100 s and 9 side scenes, and every planned scene airs before the
  cliffhanger (`Show.whole_order`) (a985783). The plan call has 32k tokens, because Sonnet's thinking counts against
  max_tokens. Haiku writes a scene's beat and stops, so the story's length comes from the number of scenes; twelve
  rehearsed shorter than nine.
- **The Coast Road** has 210 s meetings and 100 s roads, so a leg has about three waiting moments (d647fcd).
- **The Kettle's On**:
  - one call a block, the sofa guest twice, the problems spread, a pet name for each call (`PET_NAMES`) (0fe81ba);
  - a check (`kettle.check` with `llm.AskAgain`) that asks once more for an item with the wrong guest (0fe81ba);
  - in the last half hour, Maggie v Nigel duels and the cook at the counter take turns with the expert's spots
    (3309fff).
- **The Slipway**, a new teen magazine at 18:30 in Cartoon Time's place (fda616a): Tegan Trevenna (`slip_a`) and
  Elis Pengilly (`slip_b`), with looks A and A approved on `data/contact-sheets/2026-11-19-slipway-presenters.png`.
- **High Water**, a new gameshow at 18:00 (b6a9444, d8c2be3), described in docs/ENGINE.md, "High Water":
  - Des Kneebone (`hw_host`) hosts; two residents climb the harbour steps against the tide;
  - the Harbourmaster's round at halfway, for life rings;
  - three two-minute ad breaks (`adverts.break_segment` now sizes a break by its target).

Channel 8 now runs **18:00 to 21:00**: High Water, The Slipway, The Kettle's On, Wexley Wits, Marina Row, then
Tideline or The Coast Road. The closedown says "back tomorrow at six, with High Water". Tests: 1044, all passing.

### To do next, in order

The GPU is shared (memory: gpu-is-shared). The Channel 7 night starts ComfyUI for its shadow pictures and stops it
at the end, so check `nvidia-smi` before loading DramaBox or a ComfyUI model.

1. **Done 2026-11-20**:
   - Des's look: A, a red blazer and a navy bow tie, from a new `Look.bow` field that is off by default (9a59c3d);
   - the tide gauge, `entertainment/tidegauge.py` (4e58096; its sheet is `data/contact-sheets/2026-11-20-highwater-gauge.png`);
   - High Water's winner in the town's talk (9e2de9d).

   Both art items were approved by the user on contact sheets.
2. (folded into 1)
3. **Done 2026-11-20**: the two sets, `studio_slipway` and `set_highwater`, approved on contact sheets and committed in 60db5ad.
   The marks didn't move, and the gauge sits on a plain low wall.
4. **Done 2026-11-20**: Tegan's, Elis's and Des's own DramaBox voices (`bf_trevenna`, `bm_pengilly`, `bm_kneebone`), chosen by ear.
5. **Done 2026-11-20**: The Slipway's, High Water's and the closedown idents, rebaked in those voices and approved by ear.
   Items 4 and 5 are both in 0e19fea.
6. (done: see 1)
7. **Done 2026-11-20** (see above): **A scratch Channel 8 run of the whole evening.** The evening now starts at 18:00, so edit
   `data/afternoon_channel8_scratch.ps1` to `--clock 17:45 --minutes 200`. Run it from its .cmd in its own window,
   with OBS open. Check:
   - **High Water**: every round airs, and only a few chats; no `asking once more`, or rare; no `using template`.
     Check that Des's opening is in short lines and that the half hour ends near 18:30.
   - **The Slipway**: the guests are the booked ones, Quick Five comes at most once per guest, the goodbye names The
     Kettle's On, and it ends by 19:00.
   - **The Kettle's On**: about 17 calls, no pet name twice, the sofa guest twice (about 19:12 and 19:26), two duels
     and two cook visits, and the dish out at about 19:55.
   - **Marina Row**: nine scenes, the plan's own side scenes, and at most one stock quiet moment.
   - **The Coast Road**: about three waiting moments.
   - The creative editor's reviews of all six programmes.

### How to rehearse without a station

The scripts that measured all of the above are in `data/creative-trial/rehearsal-1119/scripts/`:

- `rehearse_highwater.py`, `rehearse_slipway.py`, `rehearse_lengths.py` (Marina Row and The Coast Road),
  `rehearse_kettle.py`: each writes a show's items with the real models on a copy of the town and prints lines, words
  and estimated airtime;
- `hw_sim.py`: plays thousands of High Water games for the balance;
- `hw_passrate.py`: drafts each round several times to count missing questions.

To run one:

- Copy a world backup to `data/creative-trial/rehearsal-1119/world.json`.
- Point every `NEWSROOM_*` path variable into that folder (`NEWSROOM_ADS` may point at the real `data/ads`).
- Copy the API keys in from the User environment.
- Run with `uv run python <script>`.

Each script refuses a world path without "rehearsal-1119" in it.

## Picking up on the evening of 2026-10-30

Everything is on `master` (last pushed `e4a984a`). Since the 2026-10-29 DeepSeek night: the back
office runs on DeepSeek Flash with Sonnet as a two-hourly senior editor and as Flash's fallback; a
daily allowance of new stories (8) replaced the open-thread cap; six new shows went on the
schedule (*Have Your Say* 10:00, *Quayside* 13:00, *Out and About* 15:00, *Rock Pool* 16:00, *The Inquiry* 20:00, *The Panel* 20:30); Tamsin Jago is *Full Time*'s
reporter; *Coastwide* remembers its evening; the specials' sections no longer restate or foretell.
Tonight is two jobs, in this order.

### 1. A better TTS than Kokoro: Pocket TTS for the local guests (done 2026-10-30 evening)

Bake-off of Kokoro, Qwen3-TTS (design and clone, GPU, slower than real time), Chatterbox (GPU, 0.45
RTF), Pocket TTS (Kyutai, CPU, 0.23 RTF on one thread) and NeuTTS Air/Nano (CPU, 1.4-2.5 RTF);
samples in `data/voice-samples/tts-bakeoff/`. The user chose Pocket, and it runs from tonight for
**everyone but Gully and the continuity announcer** (`[tts] backend = "pocket"`):

- **Presenters**: Pocket clones of their own Kokoro voices (Kokoro reads a reference at the
  presenter's speed and pronunciation; the user judged the clones more natural, 2026-10-30).
  Samples in `data/voice-samples/kokoro-clones/`.
- **Local guests**: the 13 Kokoro guest voices each have a clip designed with Qwen3-TTS
  VoiceDesign; a guest whose clip is the wrong age gets one of their gender and age.

Clips are `assets/voices/<kokoro voice>.<lang>.wav`, with what each is in `voices.toml`. Visitors
(American pronunciation), anyone with no accent, Gully (a pitch effect) and the announcer
(`bf_isabella`) stay Kokoro's. `backend = "kokoro"` puts everyone back. Every line now costs about
0.25 s of CPU per second of audio, one at a time, against Kokoro's 0.07: watch the buffer depth in
STATS. In the night log: `pocket voices ready: 27` near the start, and `pocket failed on ... Kokoro
takes the line` for any line it couldn't do. To hear it afterwards, pull segments from the cache.
Next steps are in TODO.

The voices still to choose by ear (now possibly as Pocket clips):

To hear and choose on the same listening page (`newsroom/station_audio.py`, as for Fran and the
stings), whichever engine wins:

- **Tamsin Jago** (`sport_reporter`, *Full Time*'s reporter, twenty-five, Port Wexley born):
  provisional `af_sarah`, British. Try it against `af_bella`, `af_nova` and `af_sky`.
- **Howard Lanyon** (`business`, *Quayside*, a retired bank manager in his sixties): provisional
  `am_echo`, British, speed 0.95.
- **The new shows' bumpers**: *Quayside*, *The Inquiry* and *The Panel* use the news arrangement
  of the station tune (`jingle.VOICINGS` has no entry for them). Give each its own, as *Full Time*
  got "drive".

The chosen voice goes in `config.toml` `[tts.voices]`, and leaves `GUEST_VOICES_F`/`_M` in
`world.py`; guests who had it are recast on the next start.

### 2. The overnight run

The first night on the new back office, and the first airing of *The Inquiry* and *The Panel* (both
booked in idle time from 18:30). The routes are in `config.toml` now, so no `NEWSROOM_ROUTES`.
Run it in **its own PowerShell window**, not a Claude app terminal tab: an app update closed the
2026-10-29 night at 08:21.

```powershell
Set-Location 'E:\programming\mini newsroom'
$env:ANTHROPIC_API_KEY = [Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY', 'User')
$env:DEEPSEEK_API_KEY = [Environment]::GetEnvironmentVariable('DEEPSEEK_API_KEY', 'User')
$env:PYTHONIOENCODING = 'utf-8'
$day = Get-Date -Format 'yyyy-MM-dd'
Copy-Item data\world.json "data\world.backup-$day-pre-night.json"
uv run python -m newsroom --clock 18:30 --log-llm --minutes 930 --obs
```

Since 2026-11-05 the station writes its own log, `data\logs\station-<date>-<time>.log` (the first
line in the window names it), so the old `> data\night-$day.log 2>&1` redirect isn't needed.

`--obs` records the programmes (not the rolling news) with OBS, one file each in OBS's recording
folder. Have OBS open first, with its WebSocket server on and a window capture of "Mini Newsroom". If
OBS isn't there, the night runs anyway and the log says "obs: not recording". Leave `--obs` off to
record from a second window instead (`uv run python tools/obs_record.py` with that log's path). For
recording without the sound in the room, see "Silent recording" in `docs/STREAMING.md`.

What to check, against the 2026-10-29 night (`data/measure-deepseek-2026-10-29.log`) and the
all-Claude 2026-10-28 one (`data/measure-2026-10-28.log`):

- **The senior editor**: its memos ("senior editor:" lines) and whether the desk's notes stop
  converging on one meeting (11 of 24 rounds said "converge" on 2026-10-29).
- **Stories moved in the pool** (since 2026-11-15): a story waiting in the running-stories pool that the memo
  names is put within the desk's reach once per memo ("from the pool t454, ..." on the desk's line), and a new
  dated NEXT moves its day ("moved in the pool: Monday 16 November -> Monday 23 November"). Until then a memo
  could ask for a crowded day to be thinned and nothing could do it: on the 2026-11-14 night four memos asked,
  and Monday 16 kept its eight stories. Check that a memo's "still N deep" is not repeated in the next one.
- **Reviews only once the town has moved** (since 2026-11-15): after its two hours the senior editor reviews only
  on a new day or once `[story] review_min_pieces` (6) news pieces have aired on stories since its last memo;
  documentaries and specials don't count. A held review is logged once ("no review until the town moves").
  Replayed against the 2026-11-14 night: reviews at 22:08, 00:08, 06:29 and 08:29, not six. Expect one review
  between midnight and breakfast, and the first of the morning about half an hour into Morning Tide.
- **Rounds with nothing to do** (since 2026-11-15): the desk plans a story again only when something has changed
  for it (it aired, a new day, the memo names it, it is going quiet), and makes no call when nothing has
  ("story desk: nothing has changed ...; no call"). On the 2026-11-14 night two stories were planned in 22 rounds
  of 24. Expect a few rounds overnight (the day's turn, and one per memo), not one every half hour, and check
  that by day a story the bulletins keep covering is still planned after each airing.
- **A story closes once its ending has been reported** (since 2026-11-15): a close whose NEXT names today or a
  later day is held as resolving until the story is covered ("is to close on Monday 16 November, not before"
  when it waits in the pool for a later day, whatever its length; "is to close once its ending for ... has been
  reported" when the day is today). On the 2026-11-14 night t515 was closed on the Sunday with Monday's ending,
  and t349 and t469 within forty minutes of coming back from the pool, each with that day's ending; none was
  covered again. A close with no day, or a day gone by, stands as before. Check that a held story is covered
  and then closed by the desk's next round, and that none stays resolving until it fades.
- **New stories**: how many the desk and the senior editor seed ("seeded thread"), up to 10 a day, none before 06:00 and the rest released through the day (since 2026-11-01),
  and whether they air.
- **The editors' meeting** (since 2026-11-14, from 16:00 on either channel's night): four "editors' meeting:" turns and
  the minutes, then whether the desk acts on its actions and takes the offered story ("the desk took the offered
  story"). `uv run python -m newsroom.meeting minutes` prints it. A station that comes on the air after the
  afternoon holds it then, and since 2026-11-15 the editors are told so (the senior editor said "Morning" at 22:08).
- **The creative editor** (Channel 8 nights): "creative editor: passed" or "sent back" at the bookings, a review per
  programme after it has aired, and `uv run python -m entertainment.creative notes` the morning after.
- **The fallback**: how often "falling back to" fires, and why.
- **The Inquiry** (20:00): the story and guest it booked ("inquiry: tonight"), and whether Pat's
  questions run across both halves of the interview.
- **The Panel** (20:30): the lineup ("panel: tonight"), four separate voices at the desk, one
  question per debate.
- **Full Time**: Tamsin at the stadium and the darts pub, the Wreckers' vox pop at the Quarry Field.
- **Coastwide**: repeats across the hour (list what aired 19:00–20:00, as for the recording).
- **Cost**: DeepSeek's usage export against the call log, and the night against $0.55 (Flash) and
  $2.18 (all Claude) for the same span.
- **The usual**: no filler in STATS, tracebacks, failed calls, the title-match continuations.

*Quayside* is at 13:00 and a night run ends mid-morning, so it needs its own run (`--clock 12:45`
for an hour or so) to be seen on air.

### The shows still to build

From the 2026-10-30 brainstorm; the full plan, a day's schedule and the reasons are in
[SHOWS.md](SHOWS.md). *Have Your Say* (10:00) was built on the evening of 2026-10-30: Jonah's phone-in,
with the `call` item (a caller through a telephone band, a box with a waveform instead of a face). It
needs a morning run to be seen on air (`--clock 09:45`), as *Quayside* does. *Out and About* (15:00)
followed the same evening: Meg Trethewey (`travel`, a coast-path ranger, chosen on a contact sheet)
on location all the way through, and the `review` item, with stars on a card that the town
remembers. Meg's voice is provisional (af_river). *Rock Pool* (16:00) came last that evening: Poppy
Tregenza (`kids`, af_bella) and Gully, a herring-gull puppet drawn in code and voiced by
`bm_fable@puppet` (Fable raised a third), on a children's set painted in code. Still to build, put off
to 2026-10-31 or the day after, once a night or two has shown how the senior editor and the story
allowance end stories:

1. **The Chamber** (council nights, 20:00 to 21:00): BUILT 2026-11-01 (`council.py`, `chamber.py`; the
   details are in SHOWS.md). Full council every other Thursday from 5 November, with four booked
   motions and every councillor's vote, the result filed to each story. To see it on any night, run
   with `$env:NEWSROOM_COUNCIL_NIGHT = '1'` and `--clock 18:15` (the agenda is booked from 18:30), after
   backing up `data\world.json`: the votes move real stories.
The day's schedule leaves the news at 09:00, 11:00, 13:30, 15:45, 16:45, 21:00 and 23:00 once all
seven are on. *The Kettle's On*, *Harbour Row* and *Wexley Wits* are kept for the entertainment
channel (`docs/ENGINE.md`).

Art waiting for ComfyUI: Rock Pool's set (`studio_kids`, painted in code), a proper set for *The Panel* (`studio_panel` is painted in code) and a
fish quay backdrop for *Quayside* (Miles reports the auction from the harbour until then).

## Where it stood on 2026-10-26

Where Mini Newsroom stands at the end of 2026-10-26, and how to pick it up.
The backlog is [TODO.md](../TODO.md) and the overview is the [README](../README.md).
Everything below is on `master` at `cubes321/mini-newsroom` (last pushed: `41145d9`), except
the work in progress listed under **In flight**.

Today's work: the first overnight run and the fixes it led to (specials, story-desk timeouts,
breakfast variety); a local-model bench; refined code-drawn characters with a look for every
guest; guest captions from the script; people lit by their location; a retry for empty desk
plans; tides and the Saltby foot ferry; local adverts that cover the gaps; fresh README
screenshots.

## Routing (decided 2026-10-26)

The Claude bench was committed in `3bf3527`, and the routes now use it: `claude_haiku` (Haiku
5.5, thinking off) writes every live segment, breaking news and adverts; `claude_sonnet`
(Sonnet 5.5, thinking on) ran the story desk, editor and specials until 2026-10-30, when they moved
to `deepseek_flash_think` (a quarter of the price) with Sonnet as the senior editor (`senior.py`)
and Flash's fallback. Haiku stays off the editor
(in the bench it re-commissioned an aired special). The story desk plans every 30 minutes
(`plan_every_s = 1800`). This holds until DeepSeek is benched for comparison; the Kimi
providers are still declared, so switching back is a change to `[llm.routes]`.

## What it is now

An always-on pixel-art TV station for the made-up town of Port Wexley. It runs a
full day on a schedule (`newsroom/schedule.py`):

| From | Show | Presenters | Set |
|---|---|---|---|
| 00:00 | overnight: test card and repeats | — | test card |
| 06:00 | *Morning Tide* (breakfast) | Rosie Treloar `host_a`, Jonah Pike `host_b` | `studio_sofa` |
| 09:00 | the news | Dana Ferris `anchor` | `studio_wide` |
| 19:00 | *Coastwide* (magazine) | Pat Holloway `mag_a`, Clive Ashdown `mag_b` | `studio_interview` |
| 20:00 | the news | Dana | `studio_wide` |
| 22:00 | *The Last Ferry* (talk show) | Vincent Marr `late_host` | `studio_interview`, lights down |
| 23:00 | the late news | Dana | `studio_wide` |

Gordon Pell (`weather`) and Miles Okafor (`reporter`) work across the shows.
Breakfast, the magazine and the talk show are `light=True`: gentler stories,
except one big running story, which they lead with briefly. That is a story
that broke as breaking news today, or else the most-covered thread at its peak
with at least four pieces of coverage. In the magazine and the talk show only
the opening item leads with it; later items mention it in passing at most.

**Breaking news** can cut into any of these, and **local adverts** fill any gap when the next
segment isn't ready (see below).

## How it fits together

- **The pipeline:**
  - `schedule.show_at(ts)` picks the show for each slot by its *planned* start time.
  - The producer restarts the pattern at each show change, so every show opens on its bumper.
  - The producer's cursor (when the next planned slot will start) is worked out on every tick:
    now, plus what is left on air (`player.time_left`), plus the unplayed queue (real lengths
    once voiced, targets before).
  - The producer keeps its show until that show's own end (`schedule.show_end`), and only then asks
    the schedule what is next.
  - Workers script each slot with the LLM, voice it with Kokoro, and cache it.
  - The player plays it on the clock.
- **Running orders:**
  - The news and breakfast loop a short `pattern`.
  - *Coastwide* and *The Last Ferry* have a written-out hour order. Entries are a type or an
    `Item(type, part, brief)`.
  - `loop_from` is where the order wraps if it runs out; it never wraps back to the bumper.
  - `closing` is planned once when less than half of the next item would fit before the hour.
    A guest's second part is never cut.
  - Parts: `open` (the only item that leads with the big story), `cont` (the same guest after
    the break, given part one's transcript), `close` (the sign-off).
  - `brief` is the angle given to the writer. A show can list `briefs` per type, handed out in
    turn; breakfast uses this so every sofa chat and report gets a different angle.
  - Each breakfast sofa chat is told this morning's earlier chats, and that a date or age said
    once is settled. Overnight repeats skip breakfast segments.
- **Per-show casts:** `Show.cast` / `Show.cast_for(type)` say who may speak;
  `models.script_schema(type, cast)` narrows the JSON speaker enum; `world.summary_for_prompt(cast)`
  lists only that cast.
- **Prompts** live in `writers.py`, one table per show (`_SYSTEM`, `_BREAKFAST`, `_MAGAZINE`,
  `_LATE`). Each LLM-scripted type has a canned template for when the model fails.
- **Segment types:**
  - Live: `bumper`, `weather`, `bulletin`, `field_report`, `sofa`, `interview`, `links`, `feature`,
    `vox_pop`, `consumer`, `monologue`.
  - Overnight: `testcard`, `repeat`.
  - Outside the rundown (no slot the producer plans): `documentary` (specials), `breaking`,
    `advert`.
- **Guests:**
  - The writer books guests from the cast or invents them. Once booked, they join `world.people`
    with a fixed voice. `ensure_person` upgrades a generic "resident" role when a later script
    (or an advert) names what they do.
  - A guest who was just on triggers one retry for someone else.
  - A presenter can be a guest and appears as themselves (Gordon runs the cannery ghost tours).
  - **Captions** use the role today's script gives them (`Line.guest_role`), also for a
    presenter booked as a guest.
- **Characters** (`sprites.py`):
  - Drawn in code, chunky on purpose: the user preferred this to generated PNG sprites (tried
    and set aside), because it suits the backdrops and varies for any guest.
  - A `Look` is skin, hair style and colour, facial hair, glasses, top style, tie, one accessory
    and a resting mouth. The eight presenters are in `LOOKS`, from agreed descriptions.
  - `guest_look(name, voice, role)` gives each guest a stable look: the voice decides whether
    they read as a woman or a man; role words dress them (`COSTUMES`: fire, police, lifeboat,
    harbour, chef, mayor, vicar, farmer, GP, councillor, teacher, celebrity, student).
  - The player puts every guest in shot on `View.guests` (name -> voice, role).
  - Three-quarter faces mirror with `facing`; the footprint is 26×37 units, as the sets expect.
  - On location people take half the backdrop's time-of-day and weather grade
    (`backdrops.person_light`); the late show's guests sit in its lights-down look.
  - `python -m newsroom.sprites --sheet out.png` draws every presenter and a crowd of guests.
- **Story threads:** only bulletins, field reports, interviews and features may open new ones.
  The thread cap drops closed threads first and never an open one.
- **Story desk** (`desk.py`): plans a batch of 8 threads per call on k3 (240 s, no SDK retry).
  A plan that updates none of the round's threads is asked for once more, then left for the
  next round.
- **Tides and the foot ferry** (`tides.py`): arithmetic from a fixed epoch, not the model. A
  semi-diurnal tide about 50 minutes later each day with a spring-neap cycle; the Saltby foot
  ferry across the Grey estuary every half hour from 07:00, the last at 23:15, none near low
  water or in a storm or fog. Weather, breakfast and late-show prompts get the day's times.
  `python -m newsroom.tides 2026-11-02`.
- **Shots:**
  - The interview set seats whoever is in `View.people`; close shots crop round the speaker.
  - Outside pieces open at the big-picture wall with the presenter who introduces them.
  - The sofa uses a LIVE inset box instead.
  - A resident on location faces Miles.
- **Breaking news and the tip-line** (`tipline.py`, `breaking.py`):
  - Tips are lines in `data/tipline.txt` (`python -m newsroom.tipline "..."`, `--list`).
  - A plain tip is offered to the next bulletins as VIEWER TIPS; `tip_used` spends it; unused
    tips expire after six hours.
  - A `BREAKING:` line becomes a segment outside the rundown, scripted with Dana at the desk,
    with the sting as a silent first line. The player sets the segment on air aside at the next
    line boundary, airs the breaking news, then resumes. A replay or an advert is dropped
    rather than resumed.
  - A second `BREAKING:` within `[breaking] cooldown_s`, or an old one at a restart, becomes a
    plain tip.
- **Specials:** they have their own cache key, survive restarts (`special.resume_ready`), are
  marked aired with `data/cache/<hash>.aired`, air after the test card overnight and after a
  news bumper in the day, and a failed stage is retried once.
- **The nightly documentary** (`documentary.py`, `[documentary]`, 2026-10-26): a special with
  `work["format"] = "documentary"`, 900 s. `should_commission`: once per broadcast day
  (`last_documentary_date`), from `commission_from` (18:00) until `airs_at` (21:00), never while a
  special is in hand; the editor goes on commissioning specials while a documentary is in hand. Stages: research (archive
  pieces on the thread plus `search_archive`, then `DocumentaryResearch` notes) -> outline
  (`DocumentaryOutline`, 6–10 sections) -> sections -> voice (10 lines a turn, `VOICE_LINES_PER_TURN`,
  for specials too) -> finish (`world.documentaries` gets the timeline and sections; no special
  cooldown). The buffer's side pocket is filtered by format (`buffer.seg_format`); the player pops a
  documentary only at a news bumper within `window_s` of `airs_at` on a day none has aired
  (`last_documentary_aired`). Routes: `documentary_commission` and `documentary_research` on Sonnet;
  the outline and sections reuse the special routes. `--documentary-now` forces a commission.
  First real run (scratch town, Claude, `--clock 20:35`): commissioned at once on t030 (59 pieces),
  researched from 42 archive pieces (8 timeline entries, 7 on record), outlined in 9 sections and
  made in about four minutes; 2,528 words, 838 s; aired at the 21:00 bumper and the news carried on
  after it with no filler. About $0.30 on Sonnet. Not yet seen in the window.
- **Adverts** (`adverts.py`, `data/ads/`, `[adverts]` in config.toml):
  - When the next slot isn't ready the player airs one, outside the rundown, up to
    `max_in_a_row` (3), then the filler card and the weather replay.
  - Eight hand-written `SEEDS` are voiced on the worker's first idle ticks, whatever the buffer
    and with or without a model; the model writes one every `make_every_s` (30 min) in healthy
    idle time, up to `pool_size` (40). A model-written one voiced past 32 s is dropped.
  - An owner who speaks joins the cast. Voiceovers use the guest voices, never the owner's.
  - The scene: the business's place, the owner on screen, an end card, no lower third or ticker.
  - `python -m newsroom.adverts` lists the pool; `--make` writes and voices one.
  - **Ad breaks** (2026-10-26): `ad_break` items in the light shows' orders (breakfast before each
    round of headlines, the magazine between blocks, the talk show between a guest's two parts),
    60 s targets. The worker only marks the slot ready; the player fills it with `BREAK_ADS` (2)
    adverts as it airs, so the pool and the "least recently aired" order are current. An empty
    pool (the first minute of a run) means the break is passed straight over. The producer never
    closes on a break that sits between a guest's parts.
- **Overnight:** repeats come from the last 48 hours of `data/cache/`, with no model calls; the
  story desk and editor keep working.
- **Kimi** (via Moonshot) doesn't get the JSON schema enforced, so the code is tolerant:
  `writers._keys_hint` puts the keys in the system prompt; the schemas accept `speaker_id`,
  guest details on each line and "female"/"male"; short card and status text is clipped on
  parse instead of failing.
- **LM Studio:** thinking is turned off with `extra_body = { reasoning_effort = "none" }`
  (`enable_thinking` is ignored).

## Running and testing

```bash
uv run python -m newsroom                                   # the station, at the real time
uv run python -m newsroom --clock 19:00 --debug             # any show at any hour
uv run python -m newsroom --scratch --clock 22:10 --minutes 3   # on a temp copy of the town
uv run python -m newsroom --log-llm                         # every prompt and reply to data/llm_calls/
NEWSROOM_LLM=off uv run python -m newsroom --scratch ...    # canned scripts only, no model calls
uv run pytest                                               # 73 tests on a temp town, no model, no TTS
uv run python -m newsroom.schedule                          # the day's table
uv run python -m newsroom.llm vox_pop --show magazine --dry-run   # a prompt and its schema
uv run python -m newsroom.workers interview --show news     # one real segment end to end
uv run python -m newsroom.backdrops --sheet sheet.png       # every backdrop, day/dusk/night
uv run python -m newsroom.sprites --sheet people.png        # every presenter and a crowd of guests
uv run python -m newsroom.tides                             # today's tides and ferry
uv run python -m newsroom.adverts                           # the advert pool
uv run python -m newsroom.tipline "BREAKING: Smoke over the old cannery"   # interrupt whatever is on
```

**Off-screen runs:** `SDL_VIDEODRIVER=dummy SDL_AUDIODRIVER=dummy` runs the windowed loop
without a window or sound, with `--snap DIR` saving a frame every 10 s. The `--no-window` mode
doesn't build views, so it doesn't exercise the scenes or the player's view code.

**Soak hygiene:** use `--scratch`. It copies the world, the tip-line and the advert pool to a
temp folder and runs on the copies with an empty cache, so a test run can't touch the town's
canon or feed the overnight repeats. Without it, a run writes to `data/world.json` and
`data/cache/`. `pytest` uses temp paths through `tests/conftest.py`; bare
`unittest discover` doesn't, so don't use it.

## State of the town

The story bible (`data/world.json`, not in git) is on broadcast day 3 (2026-10-26):
- 32 threads, 27 of them open (far above `[story] max_open_threads = 8`; the desk closes them
  slowly);
- 59 people, many of them vox-pop residents;
- 8 specials made, 411 items in the archive.

**`data/ads/` doesn't exist yet.** The next real run voices the eight seed adverts in its first
idle moments (about 20 s of CPU), and writes the town into them: Jasper Fowle (hardware),
Kenji Okonkwo (taxis) and Nuala Brennan (the Lighthouse Café) get those roles, Gordon's ghost
tours become "Pell's Cannery Ghost Tours", and Dev's treacle tart is "the Thirteen O'Clock
Tart". Then one Kimi k2.6 call every 30 minutes adds a new advert.

**The Gordon Pell mix-up (fixed 2026-10-26):** the story desk had named him among a thread's
people, which made a "Gordon Pell, resident" entry (p010) that took the credit for 111 mentions
of the weatherman. `ensure_person` now refuses a presenter's name, and `load()` removes such
entries and their ids. p010 and the archive's "Gordon Pell turns forty with cannery cake" (his
agreed look is early 60s) are gone from the real town; the backup is
`data/world.backup-2026-10-26-gordon.json`. Presenters' ages aren't in the prompts.

## Known gaps (details in TODO)

- **Art:** 14 exteriors have lit night art and 8 keep the tint on purpose; some positions are
  still set for the old placeholder pictures (lighthouse beam, slipway water, the crane and
  drill tower behind the clock).
- **Adverts:** a gap advert plays out even if the slot it covers becomes ready a second in, so
  a gap costs up to one advert's length. Breaks aren't seen with a real model yet.
- **Format repetition:** the magazine's and talk show's hour orders wrap once, after about 33
  minutes.
- **Breaking news** comes only from the tip-line; there is no follow-up report from Miles yet.
- **Length caps:** a spoken line over 900 characters (Miles) still fails once and recovers on
  the retry.
- **Not yet seen with a real model:** tides in the scripts, the new guest captions, adverts
  written in a live run (one was written by hand with `--make`), and the LM Studio provider
  through the app's own config.

## Good next steps

1. **A `--log-llm` night on Claude**, the routing chosen on 2026-10-26 (Haiku live, Sonnet
   for the back office, desk every 30 minutes), to get real token counts and costs. Then the
   DeepSeek bench for comparison.
2. **A real-model evening** to see today's features in real scripts: tides and the ferry at
   breakfast and on *The Last Ferry*, guest captions, and adverts in gaps.
3. ~~Small fixes~~: the test-card flash and the Gordon Pell mix-up, done 2026-10-26.
4. ~~Ad breaks inside the light shows~~, done 2026-10-26.
5. ~~Art session~~, done 2026-10-26: `studio_late` for *The Last Ferry*, and 11 more night
   exteriors (14 in all; the other 8 keep the tint on purpose).
6. ~~The world-state lock~~, done 2026-10-26: `World.lock`; `--workers N` works; a special is
   archived when it airs. One worker is still the default.
7. ~~The documentary, part 2~~, done 2026-10-26: archive footage (`documentary.find_clips`,
   `archive_clip` on a section, `Line.archive`). Follow-ups are in TODO.

## Verified

- **The first real documentary**, 2026-10-26 22:05–22:50 on a scratch town (`--scratch --clock 20:30
  --documentary-now --log-llm --minutes 45`, Claude routes): Sonnet chose t030, the baker's petition
  for a second engine (59 pieces); research found 42 archive pieces, 9 timeline entries (6 on record)
  and 2 clips; the outline gave 8 sections with both clips placed; the sections stayed with what is on
  record ("reports differ on the exact time... so we say only that it happened at the fire station").
  13 Sonnet calls, about 83k tokens in and 18k out, and ready about 4 minutes after the commission. It
  aired at the first bumper after 21:00 (844.7 s, 61 lines); the user watched it and liked it. The same
  evening found the four fixes listed in TODO (blank captions, voices on Dana's close-up, cut
  headlines, a thread that led every bulletin) and the weather now comes once a news loop.
- **The first overnight run** (2026-10-25 22:28 to 2026-10-26 07:33): 525 segments, no filler;
  k2.6 made 179 calls, all fine. It found the story-desk timeouts (now 240 s with no retry), the
  specials bugs (now fixed) and breakfast repetition (now fixed).
- **Real Kimi scripts, 2026-10-25 evening:** *Coastwide*'s and *The Last Ferry*'s hours signed
  off within seconds of the hour; breaking news cut in at line boundaries and the programme
  resumed; breakfast was seen with real scripts in the overnight run.
- **2026-10-26, template runs on a scratch town** (`--scratch`, `NEWSROOM_LLM=off`, off-screen):
  three-minute runs in *The Last Ferry*, *Coastwide* and *Morning Tide* with no errors; guests in
  costume (a baker in chef's whites); the startup gap covered by an advert, with 0 s of filler.
- **One real advert from Kimi** ("Buchanan's Boatyard Chandlery", with Tam Buchanan), valid on
  the second attempt; it ran 36 s, which led to the 40–55 word brief and the 32 s cut.
- **Costs** from the Kimi console for the overnight night: 77 k3 calls ($3.18) where the app
  logged 23, because of the old timeout and SDK retry; now fixed.

## Working notes

- **Engine and town:** the backend is to be reused for an entertainment channel (plan in
  [ENGINE.md](ENGINE.md)). When changing or adding anything, keep the mechanics free of Port
  Wexley: names, places, prompts and show details come in through config, the schedule or the
  world, never as literals in engine code. Build work that every channel needs (TTS, parallax,
  the mixer, provider fallback) as engine features from the start.
- **The GPU is shared** (16 GB). Check `nvidia-smi` before loading anything. Kokoro runs on the
  CPU. After a ComfyUI batch, `POST /free` with `unload_models` (it under-reports what it holds).
- **Voices:**
  - Kokoro runs offline (`HF_HUB_OFFLINE=1`). Every voice on disk is in use (presenters and the
    guest pools); advert voiceovers reuse the guest voices.
  - A new voice (`af_sarah`, `af_nova`, `af_sky`, `am_adam`, `am_echo`...) needs a one-time
    `hf_hub_download` with offline mode off, and the user's OK.
- **Scripts:** Claude writes them since 2026-10-26 (Haiku 5.5 for live segments and adverts,
  Sonnet 5.5 for the editor, desk and specials; key in `ANTHROPIC_API_KEY`). Kimi on Moonshot
  (k2.6 live, k3 back office) wrote them before and is still declared.
- **Art:** the user judges by eye. Show a contact sheet (and the art in the real shots) before
  committing. Generated character art was rejected in favour of the code-drawn style.
- **Git:**
  - Commit by explicit paths, never `git add -A`: other sessions share this folder (one has
    uncommitted work in it now).
  - Push only when the user asks.
  - `*.wav` is ignored except under `assets/`, and so is everything the app writes under `data/`
    (the world, cache, tip-line, call logs and adverts).
- **Editing on Windows:** most files are CRLF. A Python edit script that reads bytes, edits with
  `\n` and writes CRLF back keeps diffs small; Git Bash heredocs can mangle `\n` escapes inside
  Python strings, so use the Write tool for scripts with escapes.
