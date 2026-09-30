# REPLICATE.md — for AI coding agents

You are an agent helping a person make a lyric music video like *Happy to Help!* from their own song. This file gives you the pipeline, the data contracts, the commands and the traps. For the reasons behind the choices, read [README.md](README.md). The code in this repo is MIT and a working reference; the song, lyrics and video are not licensed for reuse, so replace them.

## 0. Principles (do not skip)

1. **Deterministic renderer.** Every frame is a pure function of song time `t`. No `Date.now()`, no `Math.random()`, no animation state carried between frames. Use `hash(n)`/`hstr(s)` seeded by time, line index or item index. Determinism is what makes parallel chunked renders, one-second re-renders and exhaustive crash sweeps possible.
2. **Timing first.** Build beats and word times before any visuals. AI-generated songs drift in tempo, so never assume a fixed BPM grid.
3. **Flash-safe by design.** Where the picture alternates faster than once a second, change hue, not brightness. Check every render (§6).
4. **Facts are checked like an article.** If the lyrics name real events, each claim needs a source, and any lyric that overstates its source gets an on-screen correction or a rewrite. Ask the human before rewriting sung lines; the audio can't change without a new take.
5. **The human decides.** Offer numbered options with a recommendation for taste decisions (stance, genre, look, lyrics). Build reversible things without asking.

## 1. Pipeline

```
song idea ─► lyrics (+ phonetic spellings) ─► Suno take (human, by hand) ─► take.wav
take.wav ─► Demucs stems ─► drums/bass/vocal envelopes ─► render/drums.js, render/voice.js
take.wav ─► Beat This! ─► beatmap.json ─► BEATS
lyrics + vocal stem ─► MMS forced alignment ─┐
vocal stem ─► Whisper medium ───────────────┼─► merge + manual overrides ─► render/timeline.js
mix ─► Whisper small ───────────────────────┘
render/index.html?render + Playwright ─► JPEG frames ─► ffmpeg (x264), 4 chunks in parallel
concat ─► flashguard.py (adds audio, holds flashes) ─► flashcheck2.py (PASS/FAIL ranges)
```

Suno has no official API. Unofficial wrappers need the user's session cookie and break Suno's terms, so have the human generate takes by hand and hand you the WAV.

## 2. Renderer contract (`render/index.html`)

Load `index.html?render` (no audio, no live clock). The page must expose:

| Global | Type | Meaning |
|---|---|---|
| `window.READY` | Promise | Resolves when fonts are loaded and every sprite image is decoded. Await it before frame 0, or the first frames render with fallback fonts. |
| `window.DURATION` | number (s) | Song length. Here 257.56. |
| `window.renderAt(t)` | function | Draws song time `t` synchronously into the DOM. Must be idempotent and order-independent: `renderAt(100); renderAt(3)` gives the same frame 3 as a fresh page. |

Viewport is 1920×1080. Without `?render`, the page plays the audio and calls `renderAt(audio.currentTime)` every animation frame, which is the live preview.

`render.mjs` is the driver: `START=0 END=64 AUDIO=... FFMPEG=ffmpeg PRESET=veryfast node render.mjs out.mp4 30`. It screenshots JPEG q92 per frame into `ffmpeg -f image2pipe`. Frames cost 100–270 ms each here, so expect roughly 4–10 fps per chunk.

## 3. Data files and schemas

All are plain scripts that set globals, loaded before the renderer.

**`timeline.js`**
- `window.SONG = {dur}`.
- `window.BEATS = [t, ...]`: every beat in seconds (591 here). The helpers `beatPos(t)` (fractional beat index) and `beatTime(b)` interpolate between entries. Use them for all beat-synced motion.
- `window.DOWNBEATS`: beat indices of bar starts.
- `window.EVENTS = {name: [t, ...] | [[t0, t1], ...]}`: one-off hits (chants, stomps, ad-libs).
- `window.LINES = [[t0, t1, text, side, skin, opts, words], ...]`:
  - `side`: `'g'` good, `'b'` bad, `'n'` neutral. It decides layout side, palette and glitch.
  - `skin`: the scene type for that line (`word`, `notepad`, `terminal`, `chat`, `tweet`, `chorus`, `dream`, `outro`, `happy`, `same`, `chant`, `call`, `user`, `skype`, ...). The renderer dispatches on it.
  - `opts`: per-line object (source pill text, etc.).
  - `words`: `[[displayToken, tStart], ...]` from alignment. Tokens carry their punctuation.
- `window.SECTIONS = [[t0, t1, name, clutterDensity], ...]`: contiguous, covering 0 to `dur`.

**`drums.js`**: `window.DRUMS = {kick: [[t, strength]], snare: [...], hat: [...], bass: {fps: 30, v: [0..1, ...]}}`.

**`voice.js`**: `window.VOICE = {fps: 60, v: '<string of level chars>'}`: vocal envelope normalised to a local peak, used for mouth open levels.

**`sprites.js`**: `window.SPRITES[name] = {rows: [...], palette...}` and `window.spriteSVG(name, px, {flip, tint})`. Pixel art as row strings, turned into SVG data URLs. Draw sprites as original art; do not copy logos or characters.

**`names.js`**: `window.MINI_NAMES`: unique filenames for decorative windows.

## 4. Inside `index.html`

The file is large (~1,850 lines). Main tables and functions to find by name:

- **Timing helpers:** `beatPos`, `beatTime`, `sinceBeat`, `lineAt(t)` (binary search over `SHOW_T`), `sectionAt(t)`, `wordTime(li, match)`, `curWord(li, t)`.
- **Energy and drums:** the `ENERGY` map per section scales motion; `squash`, `hop`, `bassAt`, snare camera kicks in `camAt(t)`.
- **Lyric window ("hero"):** `hero(li, t, E, sec)` dispatches on `skin`; `fitSize` auto-sizes text to fill its box; `karaoke` and `typedText` reveal words on their times (typing on 16th notes); `NOTES` rows `[lineRegex, triggerWord|seconds, 'tag'|'fact', text]` hang detail and FACT CHECK notes under the window.
- **Pictures for sung words:** `SC` maps each line to sprites and effects. `ITEMS` is built from it once at load, with appear/exit times, slots (`SLOT`) or a stage position (`stageXY`), which `renderItem`/`stageItem` draw.
- **Windows:** `pop()` makes one browser-style popup; `winPop`, `sprWin`, `gridWin`, `counterWin`, `barWin`, `morphWin`, `swarm`, `stream`, `clash`, `sticker` are the variants.
- **Clutter:** `CLUTTER` plus `clutterItems(t, density, ...)` fill the screen by section density; the edge strips of small windows use `MINI_NAMES`.
- **Impact frames:** `HITS`, `IMPACT_T` (kept ≥0.45 s apart), `impactFrame(t)`.
- **Face:** `FACE_LINES`, `faceEyes`, `mouthLv` (from `VOICE`), `BLINKS`.
- **Jokes:** `JOKE` and `pageJokes()`, one hidden gag per section.

Pattern to copy: every visual element is computed from `(t, line index, seed)`, and everything expensive (item lists, text measurements) is precomputed once at load or cached by key.

## 5. Commands

```bash
# render (from render/): one chunk per core; boundaries on whole seconds
npm install && npx playwright install chromium
FFMPEG=ffmpeg bash render-chunks.sh full "0 64" "64 129" "129 193" "193 257.56"

# a short check render of one moment
START=184 END=186 FFMPEG=ffmpeg node render.mjs /tmp/check.mp4 30

# flash check on any video (optional window)
python3 flashcheck2.py renders/full.mp4 [START END]
```

Crash sweep, before any long render: open `index.html?render` in Playwright, await `READY`, call `renderAt(t)` for `t = 0, 0.1, ..., DURATION` and collect page errors. All 2,576 steps must be clean.

Sync check: `audio/analysis/synccheck.py` compares on-screen events with audio onsets; the final render measured 0 ms lag.

## 6. Flash safety

`flashcheck2.py` approximates WCAG 2.3.1 (it is not a certified Harding/PEAT test):
- average relative luminance of 480×270 regions (at 1080p) on a stride of 1/16 screen;
- a transition is a swing ≥ 0.1 with the darker end below 0.8;
- a region fails at more than 6 transitions (3 flashes) within any 1 s;
- saturated-red flashes are checked separately.

`flashguard.py IN OUT AUDIO [DUR [AUDIO_START]]` is the last step. Once a region has had 6 transitions in the last second, it corrects that region's exposure (dims it, or lifts it toward white, feathered over ~80 px) just enough to keep the next swing under 0.1; from 5 it also holds back near misses. Blending toward the previous frame is a fallback only, since it ghosts. Treat the guard as a safety net. If it touches more than a few dozen frames, fix the design.

Design rules that got the fast sections to pass:
- alternate good/bad by **hue at matched luminance**, never pastel-vs-dark;
- use `hue-rotate` glitches, not `invert`;
- impact frames rotate hue 90° then 40°; 180° turns green into magenta, which is itself a flash;
- in fast sections, pop-ins have no overshoot and big bright windows stay nearly still;
- clutter re-randomises only on the side flip, not every beat.

## 7. Gotchas

- **Tempo drift.** The take here drifts from ~136 to ~140 BPM. A fixed grid was 200 ms off by the end. Use a beat tracker ([Beat This!](https://github.com/CPJKU/beat_this)) and smooth the result.
- **Alignment.** MMS forced alignment is best on the Demucs vocal stem. Merge it with Whisper word times and keep a manual override table; phonetic spellings in the Suno lyrics must be mapped back to display words.
- **Chunk boundaries** must be multiples of 1/30 s. Use whole seconds: `64.4*30` is not exactly 1932 in floating point, which drops or duplicates a frame at the seam.
- **Fonts.** Bundle webfonts and `await READY`. The page also uses system fonts (DejaVu Sans, Liberation Sans, Noto Color Emoji); a different machine renders different text without them.
- **ffmpeg.** You need libx264. Playwright's bundled ffmpeg lacks it, and some Python packages ship an ffmpeg that might not match what you expect; pass the one you verified via `FFMPEG=`.
- **Killing renders.** `pkill -f PATTERN` also matches your own shell when the pattern is in the command line. Kill by PID.
- **Safety classifiers.** If the song covers misuse of dangerous capabilities, keep those lines at headline level in your prompts and on-screen text. Detailed wording can trip the model's safety filter and stall your work.

## 8. Adapting this repo to a new song

1. Get the human's take as WAV. Convert it to FLAC for the repo.
2. Run Demucs (4 stems), then `audio/timing/beatmap.py`, `align.py` (with the lyric sheet), the two Whisper passes, and `build_timeline.py` to produce `timeline.js`. Fix the paths at the top of each script; they are "as used".
3. Hand-write `LINES` side and skin per line (`lines_v3.json` is the sheet `build_timeline.py` reads) and `SECTIONS` with densities.
4. Run `drums_stem.py` and `voice_env.py` for `drums.js` and `voice.js`.
5. In `index.html`, rewrite the content tables (`SC`, `NOTES`, `JOKE`, `FACE_LINES`, `ENTER_AT`, `TW_STATS`, `WHO`, `CLUTTER`, `ENERGY` keys) for the new lyrics. Keep the engine functions. Draw new sprites as needed.
6. Crash sweep, a few 2-second check renders at the busiest moments, then the full chunked render, then the flash check.
7. Show the human drafts early. A first full draft plus a written list of options per change worked better than polishing one section.
