# Port Wexley Content Licence

Copyright (c) 2026 Mark Killingback. All rights reserved, except as set out below.

This repository is under two licences:

- **The code** is under the MIT licence in [LICENSE](LICENSE). Use it for anything you like.
- **Port Wexley**, the fictional town and everything made about it, is under this licence. You can run it and
  enjoy it at home, but you can't publish it, build on it or use it commercially without permission.

In short, you can take the engine and build your own town with it, but Port Wexley stays with its author.

## 1. What "Port Wexley Content" means

"Port Wexley Content" means the fictional world of Port Wexley and the programmes made about it, in any form and
wherever it appears in this repository, including:

1. **The town:** its name, places, streets, buildings, businesses, institutions, history, events, customs and
   local lore.
2. **The people:** every named or described character, including presenters, reporters, the mayor and
   councillors, guests, callers, visitors, and the characters of the entertainment channel and the cartoons,
   with their names, personalities, relationships, catchphrases and appearance.
3. **The station:** Channel 7 as the station of Port Wexley, its programme titles and formats, schedules,
   SEVENTEXT pages, continuity, and the adverts for the town's fictional businesses.
4. **The music:** the station tune *Beacon* and all its arrangements, idents, bumpers, stings, beds and house
   band pieces, whether stored as audio files or written as notes in source code.
5. **The pictures:** backdrops, sets, logos, sprites, character drawings, cartoon kits and plates, and title
   cards, including everything under `assets/backdrops/`.
6. **The voices:** the voice reference clips under `assets/voices/` and the casting of voices to characters.
7. **The words:** scripts, stories, bulletins, descriptions of the world given to language models as prompts,
   and the world's state and archive (kept under `data/` when the station runs, wherever it is published).
8. **The output:** recordings, streams, broadcasts, clips, Shorts, promos, thumbnails and stills of any of the
   above, whoever makes them.

Port Wexley Content stays Port Wexley Content when it appears as text, data or string literals inside source
files, tests or documentation. The MIT licence covers the code around it, not the content itself.

## 2. What is not Port Wexley Content

Everything that would still work if every Port Wexley name, place, character, picture, voice and tune were
replaced with someone else's is **code**, and stays under MIT. That includes the playout engine, rendering,
sprite drawing and animation code, audio synthesis and mixing code (but not the *Beacon* tune it plays), the
scheduling, the language model and text-to-speech plumbing, the tools, the tests as code, the safety blocklist
in `assets/safety/`, and the technical documentation.

If you aren't sure which side something falls on, treat it as Port Wexley Content or ask (see section 8).

## 3. What you may do

You may, free of charge:

1. Download Port Wexley Content and run the program with it on your own equipment, and watch and listen to it,
   for your own personal, non-commercial use.
2. Read and study it, and change it on your own equipment for that personal use.
3. Fork this repository on GitHub and send changes back, as GitHub's Terms of Service allow.
4. Share links to, and use the platform's own embed feature for, the author's official streams and videos.
5. Quote short extracts for criticism, review, commentary or news reporting, with credit to Port Wexley and a
   link to this repository. (This is fair dealing under UK law anyway; it's listed here so you don't have to
   wonder.)

## 4. What you may not do without written permission

1. Publish, broadcast, stream, upload or distribute Port Wexley Content, or anything you make by running the
   program with it. This includes running your own public Port Wexley station, channel or account.
2. Use Port Wexley Content commercially in any way, including on monetised channels and in paid products.
3. Make and publish new works set in Port Wexley or using its characters, such as new programmes, stories,
   episodes or spin-offs.
4. Use the names, logos or characters in a way that suggests your work is official or endorsed.
5. Use Port Wexley Content, including the voices, to train or fine-tune machine learning models, or clone
   any of the voices for use elsewhere.

## 5. Using the code with your own world

The engine is MIT, and building your own town, station and characters with it is welcome. Before you publish
anything made with it, replace all Port Wexley Content with your own. Much of the town is currently written
into the source files themselves, so a fork that publishes output has to replace it there too, not only in
`assets/` and `data/`.

## 6. Earlier versions

Before the commit that added this file, the whole repository, Port Wexley included, was published under the
MIT licence alone. Copies obtained before that commit stay under the licence they came with. This licence
applies to Port Wexley Content in the commit that adds this file and in every later commit.

## 7. Third-party terms

Some Port Wexley Content was made with third-party models and tools whose own terms still apply, such as the
requirement to say that content is machine-generated. These are listed in [docs/CREDITS.md](docs/CREDITS.md).
This licence grants no rights the author doesn't hold.

## 8. Asking for permission

To ask for anything section 4 rules out, open an issue at
<https://github.com/cubes321/mini-newsroom/issues>. Permission counts only if the author gives it in writing.

## 9. No warranty

Port Wexley Content is provided "as is", without warranty of any kind. The author is not liable for any claim,
damages or other liability arising from it or its use.

## 10. Law

This licence is governed by the law of England and Wales.
