# Happy to Help!

An electropop music video about the AI discourse, sung by a very eager assistant. Every event in it is real and sourced.

The same tool finds cures and cons. The difference is the hand on the mouse.

- **Watch:** <https://youtu.be/lxwUIi_IHbg>
- **Sources** for every event are in the video description.
- **Want to make one like it with an AI coding agent?** Point it at [REPLICATE.md](REPLICATE.md). That file is written for the agent, not for you.

This README is the human version: how the video was made, what worked and what didn't. The whole video is code, so you can also [render it yourself](#render-it-yourself).

## How it was made

I made this in about two days (29 and 30 September 2026) with Claude as my collaborator. I wrote and chose; Claude researched, drafted, wrote all the code and ran the renders. The song came from Suno.

### 1. Studying the genre

There's a small genre of "made with Claude" music videos. Before starting, Claude broke down four of them: mexicat's *i'm upping my p(doom)*, Patryk Perduta's *Upping My P(doom)*, Bright Mirror's *Nothing Went Foom!* and leo's *AI is a normal technology?*. All four share one recipe:

1. an AI-generated song (Suno or Udio);
2. the audio analysed for beats and word timings;
3. visuals written as **code**, not generated video, where every frame is a function of song time;
4. a headless browser screenshots each frame and ffmpeg joins them.

The look people associate with these videos is kinetic typography: each word appears exactly when it's sung and is part of the picture, not a subtitle.

I kept the recipe and changed everything else.

### 2. What the video says

My take is the middle ground. AI is a very capable tool that does what it's pointed at. The real risk is people pointing it at harm: hacking, scams, deepfakes, influence campaigns. That matters more to me than paperclip doom, and I'm annoyed that both camps argue past the nuance.

So the narrator is a cheerful assistant who is "happy to help" whoever asks. The villain is never named. It's just a cursor with a typing indicator. The chorus sting asks the real question: "so who's holding the mouse?"

Some decisions that shaped everything after:

- **Real events only.** A separate research pass built a sourced list of real incidents, each with dates, links and a confidence rating. That included the good side too: the same capability used to help. The video is meant to work as a source you can check.
- **Ping-pong structure.** Good and bad uses get equal airtime, in alternating slices that halve in length: verse, couplet, line, word, strobe. The halving builds until it collapses into the final "dream" chorus.
- **A triumphant but honest ending.** The dream is an AI that helps the good and declines the bad, then it pulls back: "that's the dream, at least, let's make that dream real."
- **One line of self-awareness.** The narrator admits it can misfire too ("keep an eye on me too"). A whole verse about it felt preachy, so it's one line in the bridge.

### 3. The lyrics

The lyrics went through four versions. v1 ("Aim Assist") found the tone. v2 locked the title and the chorus. v3 added the ping-pong pairs. v4 was a cold rewrite with three options per section for me to pick from. Every event line is tagged with its source entry, and lines were cut when a source didn't support them.

Suno mispronounces jargon, so the pasted lyrics use phonetic spellings: "pee-doom", "Shog-goth", "Ill-yuh", "dash-dash yo-low". That's why `song/lyrics.txt` reads oddly.

Even after all that checking, three sung lines still round their source up for the rhyme. The video shows a red **FACT CHECK** note on screen at each one, with the real figure.

### 4. The song

The genre is electropop in the spirit of Vylet Pony's *ANTONYMPH*. I generated takes by hand on Suno Pro (v6, Custom mode) from the style prompt and lyrics in `song/`, and picked the best one. I tried adding glitch effects to the audio in the "bad" sections, then dropped it. It hurt intelligibility, and the point is that the assistant sounds exactly the same helping either side. All the glitching is visual.

### 5. Timing

Everything on screen is driven by the audio, so the timing data had to be right.

- **Beats.** The Suno take isn't a steady tempo. It drifts from about 136 to 140 BPM. A fixed grid was off by up to 200 ms by the end, so every beat comes from a beat-tracking model ([Beat This!](https://github.com/CPJKU/beat_this)) instead.
- **Words.** Each word's time comes from forced alignment of the known lyrics against the vocal (torchaudio's MMS aligner), cross-checked against two Whisper transcriptions, with manual fixes where they disagreed.
- **Drums and voice.** [Demucs](https://github.com/facebookresearch/demucs) split the song into stems. The drum stem gives kick, snare and hi-hat hits. Kicks squash the windows, snares kick the camera, and hats throw sparkles. The vocal stem's loudness drives the assistant's mouth.

The scripts are in `audio/`, kept as they were used ([audio/README.md](audio/README.md)).

### 6. The look

The visual style is remixed from Lyra Rebane's website for *ANTONYMPH* ([lyra.horse/antonymph](https://lyra.horse/antonymph/)): a real-looking browser with popup windows that jump on the beat. All the code here is new; the look is theirs.

On top of that:

- Good lines sit on the left in pastel, and bad lines on the right in dark, glitched windows. What's sung slams in as pixel art on the other side. There are 80 original sprites.
- The layout is built to read on a phone held sideways.
- Every small window has its own filename, each section hides one joke, a clock runs from midnight to dawn, and a counter in the browser bar ticks at the real rate of ChatGPT messages.
- All the logos and interfaces are parodies. No real company's branding appears.

### 7. Drafts

- **Draft 1** found the style: maximalist 2010s internet around one readable "hero" window.
- **Draft 2** made it "MUCH more maximalist" and tied every motion to a sung word.
- **Draft 3** added drum-driven motion, lip-sync, detail notes and fact checks.
- **Draft 3.1** made it safe for people with photosensitive epilepsy (next section). That's the final version.

### 8. Flash safety

The ping-pong ending swaps good and bad several times a second, and draft 3 flashed more than three times a second in places. That's the threshold in the accessibility guideline for photosensitive epilepsy (WCAG 2.3.1).

The fix was mostly design: in the fast sections, **flip the hue, not the brightness**. A pastel window and a dark one alternating is a flash; the same window turning from green to purple at equal brightness is not. Impact frames rotate colour by 90° instead of inverting.

A last render step, `flashguard.py`, watches every region of the frame. When a region is at its limit, it adjusts that region's exposure just enough to hold it under. On the final version it touched about 50 of 7,727 frames by roughly 10%.

`flashcheck2.py` then checks the result. It's an approximation of the guideline, not a certified test like Harding FPA, so the description still carries a short warning.

### What I'd tell someone trying this

- Get the timing right before you design anything. Beat-tracking and forced alignment are the foundation, and AI songs drift.
- Keep the renderer deterministic: the same time must draw the same frame. Then you can render in parallel, re-render one second to check a fix, and test every tenth of a second for crashes.
- Design for flash safety from the start. It's much easier than fixing it afterwards.
- Fact-check the lyrics like an article. Rhymes pull numbers upward.

## Render it yourself

**With Nix** (flakes enabled), one command renders the whole video:

```bash
nix run github:LilijoySkyseeker/happy-to-help
```

It copies the project into `./happy-to-help`, renders four chunks in parallel, adds the song through the flash guard, runs the flash check, and leaves the video at `happy-to-help/renders/full.mp4`. It took about 20 minutes on a 4-core machine. The browser, ffmpeg and fonts are pinned by nixpkgs, so your render matches mine. To render just one moment, pass chunks: `nix run github:LilijoySkyseeker/happy-to-help -- "184 186"`. Inside a checkout, `nix run .` renders there, and `nix develop` gives you a shell with everything for editing.

**Without Nix** you need Node 18+, Python 3 with numpy, and an ffmpeg with libx264:

```bash
cd render
npm install                      # Playwright
npx playwright install chromium  # the headless browser
FFMPEG=ffmpeg bash render-chunks.sh full "0 64" "64 129" "129 193" "193 257.56"
```

The page also uses system fonts (DejaVu Sans, Liberation Sans, Noto Color Emoji). A machine without them renders slightly different text.

To watch it live, open `render/index.html` in a browser. It plays the song and draws the page at the current position.

## What's here

| Path | What it is |
|---|---|
| `render/index.html` | The whole video: layout, animation, every scene. |
| `render/timeline.js` | The song as data: beat times, sections, and every lyric line with per-word times. |
| `render/sprites.js` | 80 original pixel-art sprites, as SVG. |
| `render/drums.js`, `voice.js` | Drum hits, bass and vocal loudness from the stems. |
| `render/names.js` | Filenames for the small edge windows. |
| `render/render.mjs`, `render-chunks.sh` | The offline renderer and the parallel render script. |
| `render/flashcheck2.py`, `flashguard.py` | The flash check, and the last render step that holds flashing under the limit. |
| `audio/` | The song, plus the scripts that turned it into timing data. |
| `song/` | The Suno style prompt and lyrics as pasted. |
| `flake.nix` | One-command render with Nix. |
| `REPLICATE.md` | Instructions for an AI coding agent that wants to make a video like this. |

## Credits and licences

This project is copyleft: use it, remix it, share it, and keep it free for the next person. Details are in [LICENSE](LICENSE).

- **Code:** GNU GPL v3 or later ([COPYING](COPYING)).
- **Song, lyrics, sprites, timing data and the video** (including your own renders): [CC BY-SA 4.0](LICENSE-MEDIA). Credit it as: "Happy to Help!" by Lilijoy Skyseeker, CC BY-SA 4.0, with a link to this repo.
- **Visual style** is remixed from Lyra Rebane's website for Vylet Pony's *ANTONYMPH*: <https://lyra.horse/antonymph/>. ♥
- **Fonts:** Press Start 2P, VT323, Bangers, Silkscreen and Pixelify Sans, under the SIL Open Font License 1.1. The licences are in [render/fonts/licenses](render/fonts/licenses).
- Made with Claude (Anthropic), which wrote the code with me, and Suno, which made the audio from my lyrics and style prompt.
