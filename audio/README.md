# audio/

`take1.flac` is the song: the take I picked from Suno, losslessly compressed from the 48 kHz WAV Suno gave me.

Everything else here turned that file into the numbers the renderer reads. The scripts are kept **as they were used**, not as a polished tool. They expect intermediate files (Demucs stems, Whisper output) in `work/` or `sep4/`, which are not in the repo because they are large and can be regenerated.

## timing/ (what `render/timeline.js` is built from)

| File | What it does |
|---|---|
| `beatmap.py` | Beat times from [Beat This!](https://github.com/CPJKU/beat_this), smoothed. The song drifts from about 136 to 140 BPM, so there is no fixed grid. Writes `beatmap.json`. |
| `align.py` | Forced alignment of the lyrics to the vocal stem (torchaudio MMS). Writes `aligned.json`. |
| `vonsets.py` | Vocal onsets, used to nudge word starts. Writes `vocal_onsets.json`. |
| `merge.py`, `build_timeline.py` | Merge the forced alignment with two Whisper transcriptions (`words_*.json`) plus manual fixes, and write `render/timeline.js`. `lines_v3.json` is the lyric sheet with per-line side and scene type. |
| `regions.json` | Good and bad sections of the song. |

## analysis/ (the other data files, plus checks)

| File | What it does |
|---|---|
| `drums_stem.py` | Kick, snare, hi-hat onsets and a bass envelope from the Demucs stems. Writes `render/drums.js`. |
| `voice_env.py` | Vocal loudness at 60 fps for the lip-sync. Writes `render/voice.js`. |
| `build_names.py` | Filenames for the small edge windows. Writes `render/names.js`. |
| `transcribe.py`, `transcribe_voc.py` | The Whisper passes (small on the mix, medium on the vocal stem). |
| `synccheck.py` | Checks a render against the audio for lag. |
| `flashdiag.py` | Finds which part of the frame is flashing, for fixing the design. |
