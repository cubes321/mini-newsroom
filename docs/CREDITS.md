# Credits and licences

This is the list of everything Port Wexley is made with, and what each licence means for **putting the
station on YouTube and Twitch and earning money from it** (ads, Twitch subs, Ko-fi). The licence texts were
read on **2026-11-08**. Links go to the text that was read. This is a careful reading by a developer, not
legal advice: before money depends on one of these, read the text yourself.

The project's own code is MIT ([LICENSE](../LICENSE)). Port Wexley and everyone in it are fictional.

## The short version

| | what | verdict for a monetised channel |
|---|---|---|
| **BLOCKER** | MiniMax H3 (the cartoons) | **Not licensed in the UK, EU, US or South Korea at all**, for any use, without MiniMax's approval. Not on air yet. |
| **Done** | Stable Audio 3 Medium (the old music bed) | **Off air since 2026-11-08**: the bed is now rendered in code. Only the unaired cartoon beds still use it. |
| **Condition** | DramaBox (guest, council and three presenter voices) | Free under US $10M revenue. The licence **requires** saying the content is machine-generated. |
| **Credit** | Pocket TTS (every voice on air) | CC-BY-4.0: needs an attribution line. Also no cloning of real people without consent. |
| **Fine** | Kokoro, misaki, Qwen-Image, Qwen-Image-Edit 2511, Z-Image Turbo, Qwen-Image-Lightning, Qwen3-TTS, Claude, DeepSeek, Windows fonts | Apache 2.0 / MIT / provider terms that give you the output. Details below. |
| **Note** | espeak-ng (inside Kokoro's dependencies) | GPL-3.0, but it covers the software, not the audio. Nothing to do for broadcast. |

The disclosure line used everywhere (stream title or description, Shorts, the making-of post) is:

> Port Wexley is a fictional town. Every programme is written and voiced by AI.

and the credit line for Pocket TTS is:

> Voices: Pocket TTS by Kyutai (CC BY 4.0), with Kokoro-82M (Apache 2.0).

`docs/STREAMING.md` has title and description templates with both.

---

## Blockers and limits

### MiniMax H3 Ref2VA: the cartoons (`entertainment/cartoons.py`), not on air

- **Licence:** MiniMax H3 Community License Agreement, 2 August 2026
  ([LICENSE](https://huggingface.co/MiniMaxAI/MiniMax-H3/blob/main/LICENSE),
  [model card](https://huggingface.co/MiniMaxAI/MiniMax-H3)).
- **The territory clause is the problem.** §I.5 names the European Union, the **United Kingdom**, the Republic
  of Korea and the United States as "Excluded Territories". The grant in §II applies "solely within the
  Applicable Territory", and §V.4 says you may not "use, reproduce, modify, distribute, or display" the
  works **or any of their Outputs** outside it. So from the UK, rendering the cartoons and airing them are
  both outside the licence. That is true for a hobby channel too, not just a monetised one.
- **The way in:** §II invites people in those countries to contact MiniMax for a licence. The model card
  links an application form for the USA, EU, UK and South Korea at
  [platform.minimax.io/h3-license](https://platform.minimax.io/h3-license).
- **If a licence is granted**, the terms for everyone else are: free below US $20M yearly revenue (§IV.1);
  a commercial product must "prominently display 'MiniMax H3'" in its user interface (§IV.2), so put it in
  the description and the end card; generated content put in public must be clearly disclosed as
  machine-generated (Exhibit A, item 12); outputs may not be used to train other models (§V.3). MiniMax
  claims no rights over outputs (§VI.4). Hong Kong law.
- **Wan2GP's FastH3** is the same model, so switching engine does not help.
- **What to do:** keep Cartoon Time and the Gully films off every public channel and out of the promo and
  Shorts until MiniMax says yes. Apply now if the cartoons matter for launch. The SA3 score and ambience
  beds used by the cartoons (`data/cartoons/gully/sound/`) have the Stable Audio question below as well.

### Stable Audio 3 Medium: the old music bed, replaced 2026-11-08

- **Replaced.** On 2026-11-08 the bed (`assets/music/bed.wav`, baked into `assets/music_bed.wav`) was
  replaced by one rendered in code: `jingle.bed("vibes")`, chosen by ear over two other code takes. **No
  Stable Audio output is on air now.** The notes below are kept for the cartoons' beds
  (`data/cartoons/gully/sound/`, not on air) and in case SA3 is used again.
- **What it made:** the 87-second vibraphone-and-Rhodes bed that looped under the news, the test card and
  SEVENTEXT (`newsroom/station_audio.py:1-15`, `TODO.md:749-753`). It was the only Stable Audio file on
  air: every ident, bumper, sting and the house band are code renders of the *Beacon* motif from
  `newsroom/jingle.py` (the SA3 takes for the news ident were turned down by ear).
- **Licence:** Stability AI Community License
  ([model card](https://huggingface.co/stabilityai/stable-audio-3-medium),
  [Community License Agreement](https://stability.ai/community-license-agreement), last updated 5 July 2024,
  [licence overview](https://stability.ai/license)).
- **Commercial use:** allowed for anyone with less than US $1,000,000 annual revenue. §III: "If You are using
  or distributing the Stability AI Materials for a Commercial Purpose, You must register with Stability AI."
- **Outputs:** §IV(c)(iii): "You own any outputs generated from the Models ... to the extent permitted by
  applicable law." The "Powered by Stability AI" attribution in §IV(a) applies when you distribute the model
  or a product built on it, not to audio you made with it.
- **Open questions:** the model's own `LICENSE.md` could not be read (Hugging Face returned 401 to an
  unauthenticated reader), and the gate on the model page links the *Stable Audio Open 1.0* licence
  instead. The licence is also revocable (§II).
- **Verdict:** not a hard block, but one 87-second loop carried a registration duty and two unknowns, and it
  was also the last 24 kHz mono stem in a 44.1 kHz stereo mixer. Hence the code bed. If SA3 output goes on
  air again (the cartoons), register for the Community License at stability.ai first.

### DramaBox (Resemble AI, on LTX-2.3 audio): the designed voices

- **What it made:** the 24 local guest reference clips (the `assets/voices/*.b.wav` entries with a `gender` and
  `age`), the
  mayor and six councillors, and three presenters, Tamsin Jago, Howard Lanyon and Meg Trethewey
  (`assets/voices/voices.toml:5` and `:238`), designed from a text prompt alone, seed 42, on 2026-11-01. Pocket
  TTS clones these clips live; DramaBox never runs during a broadcast.
- **Licence:** LTX-2 Community License Agreement, 5 January 2026
  ([DramaBox model card](https://huggingface.co/ResembleAI/Dramabox),
  [its LICENSE](https://huggingface.co/ResembleAI/Dramabox/blob/main/LICENSE),
  [repo](https://github.com/resemble-ai/dramabox)). DramaBox is a fine-tune of Lightricks' LTX-2.3, so it is
  a "Derivative of LTX-2" and carries that licence. Resemble retired it in August 2026; the archive stays
  under the same licence.
- **Commercial use:** free for entities with less than US $10,000,000 annual revenue (§2).
- **Outputs:** §5: "Licensor claims no rights in the Output you generate". You are accountable for the output
  and its uses.
- **The condition that matters:** the Acceptable Use Policy (Attachment A) applies to outputs. Item 5 forbids
  placing machine-generated content in any context "without expressly and intelligibly disclaiming that the
  information and/or content is machine generated". **So the "written and voiced by AI" line is a licence
  term, not just good manners: keep it on every stream, Short and post.** Item 7 forbids impersonating
  real people without consent; every Port Wexley voice is invented from a description.
- **Small questions, low risk:**
  - The clips are used as Pocket's cloning reference. That is conditioning at run time, not training, so
    item 18 (no training other models on outputs, for commercial use) shouldn't apply.
  - DramaBox adds an inaudible Resemble Perth watermark to its output. The clips were cloned by Pocket, so
    the broadcast audio isn't DramaBox output directly.
  - The repo's optional voice-reference denoiser (NVIDIA RE-USE) is non-commercial, but it only runs on a
    reference recording. These voices were designed from text, so it was never used.
- **Attribution:** none required for outputs. Credit it anyway (below).

### Pocket TTS (Kyutai): every voice on air

- **What it does:** speaks every line live on the CPU, cloning the reference clips in `assets/voices/`
  (`pocket-tts` 4.0.1, `[tts] backend = "pocket"`).
- **Licence:** weights **CC-BY-4.0**, code **MIT** ([model card](https://huggingface.co/kyutai/pocket-tts),
  [repo](https://github.com/kyutai-labs/pocket-tts)). The weights are gated: accept the terms on Hugging Face
  and `hf auth login` once.
- **Commercial use:** allowed with attribution. CC-BY-4.0 asks for the creator, the licence and a link.
- **Usage terms on the card:** no "voice impersonation or cloning without explicit and lawful consent", and
  no presenting generated content as genuine recordings of real people or events. Port Wexley clones only
  voices made by Kokoro and DramaBox for invented people, and the disclosure line covers the second point.
- **Kyutai's own voice packs** (`kyutai/tts-voices`) are not used. Some of them (the Expresso and EARS voices,
  "cosette" and "jean") are non-commercial only, so keep it that way.
- **Attribution text:**
  > Voices: Pocket TTS by Kyutai (https://huggingface.co/kyutai/pocket-tts), licensed CC BY 4.0.

---

## Fine for commercial use

### Kokoro-82M (hexgrad)

- Voices the continuity announcer, Gully, phone-in callers, visitors and anyone Pocket can't do, and made the
  presenters' reference clips (each presenter is a Pocket clone of their own Kokoro voice reading one
  sentence) and the visitors' `.a.wav` clips.
- **Licence:** Apache 2.0 ([model card](https://huggingface.co/hexgrad/Kokoro-82M)). Commercial use allowed.
  No attribution is required for audio. A few non-English voices have CC BY training data; none of them are
  used here.

### Kokoro's dependencies: misaki, phonemizer-fork, espeakng-loader, espeak-ng

- **misaki** (Kokoro's English G2P): Apache 2.0 ([LICENSE](https://github.com/hexgrad/misaki/blob/main/LICENSE)).
- **espeakng-loader** 0.2.4: its own code is MIT
  ([repo](https://github.com/thewh1teagle/espeakng-loader)), but the installed wheel bundles
  `espeak-ng.dll` and `espeak-ng-data/`, which is why its package metadata says GPL-3.0+.
- **phonemizer-fork** 3.3.2: GPL-3.0-or-later ([PyPI](https://pypi.org/project/phonemizer-fork/)).
- **espeak-ng**: GPL-3.0-or-later ([repo](https://github.com/espeak-ng/espeak-ng)). misaki falls back to it for
  words not in its dictionary. `newsroom/tts.py` also points it at a system install in
  `C:\Program Files\eSpeak NG` if one is there.
- **What the GPL means here:** the GPL governs copying and distributing the *software*. Audio made by running
  it is not a derivative work of it, so **broadcast output, recordings and Shorts are unaffected**. For the
  code: this repo contains no espeak-ng; `uv sync` downloads it from PyPI onto the user's own machine. So the
  repo stays MIT. It would only matter if someone shipped a bundled build (an installer or an exe with the DLL
  inside): that bundle would have to follow the GPL for those parts, which means including the licence and
  offering their source.

### Qwen3-TTS VoiceDesign (Alibaba Qwen): no longer used

- It designed the first set of guest clips on 2026-10-30. All thirteen of those files were replaced by
  DramaBox clips in commit `01bd4e3` on 2026-11-01 (checked with `git show --stat 01bd4e3`), and no Qwen3-TTS
  audio is left in `assets/voices/`. For the record it is Apache 2.0
  ([repo](https://github.com/QwenLM/Qwen3-TTS), [technical report](https://arxiv.org/abs/2601.15621)).

### The ComfyUI image models

| model | used for | licence | notes |
|---|---|---|---|
| Qwen-Image | the backdrops (`assets/backdrops/`); the live pictures' `qwen_image_cfg` setting | Apache 2.0 ([card](https://huggingface.co/Qwen/Qwen-Image)) | Base Qwen-Image only. The newer Qwen-Image 2.1 is under a non-commercial research licence: don't switch to it. |
| Qwen-Image-Edit 2511 | backdrop edits and night versions, cartoon plates | Apache 2.0 ([card](https://huggingface.co/Qwen/Qwen-Image-Edit-2511)) | |
| Qwen-Image-Lightning LoRA | the live pictures' fast `qwen_image` setting | Apache 2.0 ([card](https://huggingface.co/lightx2v/Qwen-Image-Lightning)) | |
| Z-Image Turbo (Tongyi-MAI) | live pictures (`newsroom/pictures.py`, shadow mode, not shown on air) | Apache 2.0 ([card](https://huggingface.co/Tongyi-MAI/Z-Image-Turbo)) | Confirmed from secondary sources only; check the card before the pictures go on air. |

Apache 2.0 puts no conditions on the images you make. The people on screen are drawn in code
(`newsroom/sprites.py`), not generated.

### The script writers: Claude (Anthropic) and DeepSeek

- **Claude** (Haiku 5.5 live, Sonnet 5.5 senior editor and fallback): Anthropic's
  [Commercial Terms of Service](https://www.anthropic.com/legal/commercial-terms) cover API use. The customer
  "owns its Outputs", and Anthropic assigns its rights in them to you, subject to the terms. You are
  responsible for checking outputs before you share them. (A UK customer contracts with Anthropic Ireland.)
- **DeepSeek** (Flash, the back office): the
  [Open Platform Terms of Service](https://cdn.deepseek.com/policies/en-US/deepseek-open-platform-terms-of-service.html),
  effective 29 April 2026. §4.2 assigns "any rights, title, and interests—if any—in the Outputs" to you, and
  commercial use is allowed. §8.1: "You shall clearly disclose to your end users that the Output content is
  generated by AI". The disclosure line does that. Don't use the DeepSeek name or logo in a way that implies
  a partnership (§5.2-5.3); a plain credit is fine.
- Kimi (Moonshot) wrote the scripts before 2026-10-26 and none of its output is needed for launch.

### Fonts: Bahnschrift and Consolas

- Captions, lower thirds and title cards use Bahnschrift (`newsroom/scenes.py:39`); SEVENTEXT, the sprite
  sheets and debug text use Consolas. Both ship with Windows and are loaded with `pygame.font.SysFont`; the
  repo contains no font files.
- Microsoft's [font FAQ](https://learn.microsoft.com/en-us/typography/fonts/font-faq) treats text in video
  "the same as graphic files, providing the captions or text is rendered as a bitmap image, and the font
  files themselves are not embedded within the video file", and it doesn't restrict selling what you make
  with them. Pygame renders the text into the picture, so streams, recordings and Shorts are fine.
- Don't add the `.ttf` files to the repo: Windows fonts may not be redistributed.

### Everything else

- Music: the station tune *Beacon*, all its arrangements and the music bed are original and rendered in
  code (`newsroom/jingle.py`). No library music, no samples, no generated audio.
- Backdrops, the logo, the people and the sets: made for this project (ComfyUI models above, or drawn in code).
- Pygame (LGPL-2.1, used as an unmodified library), PyTorch (BSD), pydantic, numpy, soundfile, obsws-python,
  the `anthropic` and `openai` SDKs: permissive licences for the software; none affects the broadcast.

---

## Credits block (for the README, descriptions and the end of the making-of post)

> **Port Wexley** is a fictional town. Every programme is written and voiced by AI.
>
> Scripts: Claude (Anthropic) and DeepSeek. Voices: Pocket TTS by Kyutai (CC BY 4.0) and Kokoro-82M by
> hexgrad (Apache 2.0); guest voices designed with DramaBox by Resemble AI (LTX-2 Community License).
> Pictures: Qwen-Image and Qwen-Image-Edit (Apache 2.0), made in ComfyUI. Music: original, rendered in code.
> Code: MIT, https://github.com/cubes321/mini-newsroom

Add "Animation: MiniMax H3" (and "Music: Stable Audio 3 by Stability AI", for their beds) if the cartoons are
ever licensed and aired.
