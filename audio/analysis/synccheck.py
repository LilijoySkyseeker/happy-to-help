#!/usr/bin/env python3
"""Sync check for a rendered draft: cross-correlate on-screen motion with the kick and snare onsets,
and the muxed audio with take1.wav. usage: synccheck.py VIDEO DRUMS_JS TAKE1_WAV"""
import subprocess, sys, json, re, numpy as np

FF = __import__('os').environ.get('FFMPEG', 'ffmpeg')   # an ffmpeg with libx264
video, drums_js, wav = sys.argv[1:4]
FPS, W, H = 30, 160, 90

raw = subprocess.run([FF, '-v', 'error', '-i', video, '-vf', f'scale={W}:{H}:flags=area', '-f', 'rawvideo',
                      '-pix_fmt', 'gray', '-'], capture_output=True, check=True).stdout
fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
n = len(fr)
motion = np.r_[0, np.abs(np.diff(fr, axis=0)).mean((1, 2))]
print(f'video frames {n} ({n / FPS:.3f} s)')

src = open(drums_js).read()
D = json.loads(src[src.index('{', src.index('window.DRUMS')):src.rindex('}') + 1])
def train(ev):
    k = np.zeros(n)
    for t, s in ev:
        i = int(round(t * FPS))
        if 0 <= i < n: k[i] += s
    return k

def hp(x, w=15):
    return x - np.convolve(x, np.ones(w) / w, 'same')

m = hp(motion)
for name in ('kick', 'snare'):
    k = hp(train(D[name]))
    lags = range(-8, 9)
    c = [np.dot(m[8:-8], np.roll(k, L)[8:-8]) for L in lags]
    best = list(lags)[int(np.argmax(c))]
    print(f'{name}: best lag {best:+d} frames ({best * 1000 / FPS:+.0f} ms); corr by lag',
          ' '.join(f'{L:+d}:{v / max(c):.2f}' for L, v in zip(lags, c) if abs(L) <= 3))

# audio: muxed track vs the master
def pcm(path, extra=()):
    b = subprocess.run([FF, '-v', 'error', *extra, '-i', path, '-map', '0:a:0', '-ac', '1', '-ar', '8000',
                        '-f', 's16le', '-'], capture_output=True, check=True).stdout
    return np.frombuffer(b, np.int16).astype(np.float32)
a, b = pcm(video), pcm(wav)
seg = slice(8000 * 60, 8000 * 90)
x, y = a[seg], b[seg]
lags = range(-400, 401)
c = [np.dot(x[400:-400], np.roll(y, L)[400:-400]) for L in lags]
best = list(lags)[int(np.argmax(c))]
print(f'audio: muxed vs take1.wav best lag {best / 8:+.1f} ms; durations {len(a) / 8000:.3f} s vs {len(b) / 8000:.3f} s')
