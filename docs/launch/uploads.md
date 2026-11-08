# Uploads: the long videos for launch

Recorded programmes to put on the new Port Wexley channel as ordinary (non-live) videos: a few ready on launch
night, then one a week. Shortlisted on 2026-11-08 from `E:/recordings` (the `--obs` per-programme files), by
length, date and subject from the night logs. A frame of each is on the contact sheet
`data/launch/uploads-shortlist.png`. **Nothing here has been watched end to end yet: watch each one before it
goes up** (what to listen and look for is under "Preparing each file").

Why bother, when there's a live stream: public long videos count towards the Partner Programme's 4,000 watch
hours and keep earning them; they give a visitor (and YouTube's whole-channel review) something finished to
judge; and a documentary is easier to recommend than a stream someone joins halfway through.

## The launch shelf: public by Sunday 20 December

| # | video | file in `E:/recordings` | length | why |
|---|---|---|---|---|
| 1 | **The Channel 7 promo** (the channel trailer) | `2026-11-08 Channel 7 Promo - final 1440p.mp4` | 4:08 | The tour. Set it as the trailer for visitors who haven't subscribed. |
| 2 | **The making-of**, in your voice | not made yet | 5-10 min | A screen recording of the station running, the logs and the story board, narrated by you. The single best answer to "is this AI slop?" |
| 3 | **Six Minutes Slow: The Town Hall Clock** (*Port Wexley Stories*, 3 Nov) | `2026-11-03 23-46 Port Wexley Stories.mp4` | 13:33 | The stopped Town Hall clock is the town's emblem; the best introduction to the place. |
| 4 | **The Boxing Day Tray: Forty-Four Portions for the Lifeboat** (4 Nov) | `2026-11-04 21-35 Port Wexley Stories.mp4` | 13:42 | A Christmas story, for a Christmas launch. |
| 5 | **The Shed Behind the Cannery: Brake Lessons and a Plaque** (5 Nov) | `2026-11-05 21-45 Port Wexley Stories.mp4` | 14:22 | The most recent documentary. Mostly the presenter over a foggy harbour: check it holds the eye. |
| 6 | **The Chamber**, the first council night (5 Nov) | `2026-11-05 20-42 The Chamber.mp4` | 60:43 | The show nobody else has: full council, six councillors and the mayor, four motions, real votes counted in code (the second-engine costing carried 4-1, the harbour-wall paperwork lost 2-3, and two more). Add chapters for the four motions from the night log. |
| 7 | **The Last Ferry**, one episode (5 or 6 Nov) | `2026-11-05 22-44 The Last Ferry.mp4` or `2026-11-06 22-00 The Last Ferry.mp4` | 58:47 / 58:02 | The late-night talk show: Vincent's monologue, the guests, the house band. Watch both and keep the better one. |

Make the documentaries a playlist (*Port Wexley Stories*), and put the others in *Full programmes*.

## In reserve: one a week after launch

Every Sunday from 27 December, one long video. **Prefer the best of the latest week** (the nightly documentary
keeps coming, and every week's fixes make the new recordings better than these); these are the fallback:

| video | file | length | note |
|---|---|---|---|
| **Laced Down: Port Wexley Braces for the First Winter Gale** (1 Nov) | `2026-11-01 23-25 Port Wexley Stories.mp4` | 13:45 | |
| **Five Boats and a Six Per Cent: The Quay Auction's Rough Day** (2 Nov) | `2026-11-02 21-44 Port Wexley Stories.mp4` | 12:49 | |
| **The Wheel and the Stall: 136 Years of Harrow Street Market** (30 Oct) | `2026-10-30 23-32 Port Wexley Stories.mp4` | 13:43 | A history piece, so it doesn't date. Recorded before the guest voices were recast on 1 November: listen to the guests first. |
| **The Inquiry: "Who Pays When the Quay's Fenders Wait for the Auction?"** (6 Nov, with the harbourmaster, Ivy Marchetti) | `2026-11-06 19-58 The Inquiry.mp4` | 29:48 | |
| **The Panel** (6 Nov) | `2026-11-06 20-28 The Panel.mp4` | 30:49 | |
| **Coastwide** (5 Nov, the bonfire night edition) | `2026-11-05 19-44 Coastwide.mp4` | 58:36 | |
| the other *Last Ferry* of 5/6 November | | ~58 min | |

Later possibilities: the next council nights (19 Nov, 3 Dec, 17 Dec) once recorded, and a "story so far" of
one long-running story, cut from its coverage across several days with the promo's clip-finding tools
(`data/one_off/promo-2026/montage/tools/`).

## Not for the channel

- ***Rock Pool***: it's children's television, so YouTube would need it marked "made for kids", which turns off
  comments and personalised ads and can colour how the channel is treated. Keep it to the live stream.
- **The one-off specials** (Budget 2026, the F1 São Paulo preview and qualifying show): real events, and
  probably real people. That brings in YouTube's real-person disclosure rule, DramaBox's no-impersonation term
  and F1's trademarks. Keep the channel to the fictional town.
- ***Wexley Wits***: it belongs to the entertainment channel.
- **The five-minute specials** (the ~100 short *Port Wexley Stories* files): too many near-alike pieces, which is
  the "mass-produced" pattern the inauthentic-content policy looks for. Use them for Shorts, or a compilation.
- **SEVENTEXT, *Morning Tide*, the news hours**, the files with "first try" or "abandoned" in the name, and the
  untitled timestamp files.

## Preparing each file

1. **Watch it through.** Note anything that shouldn't go out: a mangled word, a long filler card, a guest who
   repeats, a factual slip about the town, anything that reads badly out of context. Trim the head or tail with
   `ffmpeg -ss <start> -to <end> -c copy` if needed.
2. **Upscale to 1440p**, if the promo's 1440p test (LAUNCH.md, week 1) shows YouTube then gives the full quality
   ladder. The recordings are 1920×1080, exactly 6x the 320×180 canvas, so 2560×1440 (8x) with nearest-neighbour
   keeps every pixel square:

   ```powershell
   ffmpeg -i "E:/recordings/2026-11-03 23-46 Port Wexley Stories.mp4" -vf "scale=2560:1440:flags=neighbor" `
     -c:v libx264 -crf 18 -preset slow -pix_fmt yuv420p -c:a aac -b:a 192k `
     "E:/recordings/uploads/2026-11-03 Six Minutes Slow 1440p.mp4"
   ```

   The recordings are quite low bitrate (about 0.4 Mbps), so this doesn't add detail; it only gets YouTube to
   serve a sharper version.
3. **The ticker and the clock are in the picture** (a NEWS ticker with that night's headlines, the time in the
   corner). That's fine: present each video as "as broadcast", with the date in the description.
4. **Thumbnail**: a frame upscaled with nearest-neighbour, with the title in Bahnschrift. Custom thumbnails need
   the channel verified (youtube.com/verify).

## Upload settings

- Audience: **No, it's not made for kids.**
- **Altered content: Yes** (see STREAMING.md).
- Visibility: **Scheduled**, so the shelf goes public together on 20 December, and the weekly ones on Sundays.
- Category: Entertainment. Language: English (United Kingdom).

```text
Title:
Six Minutes Slow: The Town Hall Clock | Port Wexley Stories

Description:
Port Wexley is a fictional town. Every programme is written and voiced by AI.

Port Wexley Stories is Channel 7's nightly documentary: fifteen minutes on one of the town's stories,
researched from everything the station has aired about it. As broadcast on 3 November 2026.

Channel 7 is live around the clock: TODO (live link)
Support the station: TODO (Ko-fi)

Voices: Pocket TTS by Kyutai (CC BY 4.0, https://huggingface.co/kyutai/pocket-tts) and Kokoro-82M (Apache 2.0).
Scripts: Claude and DeepSeek. Full credits: https://github.com/cubes321/mini-newsroom/blob/master/docs/CREDITS.md
```

For a full programme, swap the second paragraph for one line about the show, and add chapters (`00:00 Opening`,
`04:12 Motion 1: ...`) for *The Chamber* and *The Inquiry*.
