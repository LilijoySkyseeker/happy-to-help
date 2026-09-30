#!/usr/bin/env python3
"""Diagnose a flash-check failure: print the worst region's luminance trace and save a sheet of the
frames at its transitions. usage: flashdiag.py VIDEO START END OUT.jpg"""
import subprocess, sys, numpy as np
from PIL import Image, ImageDraw
sys.argv, argv = sys.argv[:1], sys.argv
FF = __import__('os').environ.get('FFMPEG', 'ffmpeg')   # an ffmpeg with libx264
path, t0, t1, out = argv[1], float(argv[2]), float(argv[3]), argv[4]
FPS, DW, DH = 30, 384, 216
RW, RH, SX, SY = DW // 4, DH // 4, DW // 16, DH // 16
raw = subprocess.run([FF, '-v', 'error', '-ss', str(t0), '-i', path, '-t', str(t1 - t0), '-vf',
                      f'fps={FPS},scale={DW}:{DH}:flags=area', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'],
                     capture_output=True, check=True).stdout
frames = np.frombuffer(raw, np.uint8).reshape(-1, DH, DW, 3)
lut = np.arange(256) / 255.0
lut = np.where(lut <= 0.04045, lut / 12.92, ((lut + 0.055) / 1.055) ** 2.4)
ys = np.arange(0, DH - RH + 1, SY); xs = np.arange(0, DW - RW + 1, SX)
tr = []
for f in frames:
    rgb = lut[f]; L = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    c = np.pad(L.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    y0, x0 = ys[:, None], xs[None, :]
    tr.append((c[y0 + RH, x0 + RW] - c[y0, x0 + RW] - c[y0 + RH, x0] + c[y0, x0]) / (RW * RH))
tr = np.array(tr)                      # frames x regions_y x regions_x
def zig(x, th=0.1):
    ev, d, ext, lo, hi = [], 0, x[0], x[0], x[0]
    for i, v in enumerate(x):
        if d == 0:
            lo, hi = min(lo, v), max(hi, v)
            if v - lo >= th and lo < .8: d, ext = 1, v; ev.append((i, '+'))
            elif hi - v >= th and v < .8: d, ext = -1, v; ev.append((i, '-'))
        elif d == 1:
            if v > ext: ext = v
            elif ext - v >= th and v < .8: d, ext = -1, v; ev.append((i, '-'))
        else:
            if v < ext: ext = v
            elif v - ext >= th and ext < .8: d, ext = 1, v; ev.append((i, '+'))
    return ev
best = None
for ry in range(tr.shape[1]):
    for rx in range(tr.shape[2]):
        ev = zig(tr[:, ry, rx])
        w = max((sum(1 for j, _ in ev if a <= j < a + FPS) for a in range(len(tr))), default=0)
        if best is None or w > best[0]: best = (w, ry, rx, ev)
w, ry, rx, ev = best
print(f'worst region y{ry} x{rx} (1080p box x={xs[rx] * 5} y={ys[ry] * 5} w=480 h=270): {w} transitions in 1 s')
print('trace:', ' '.join(f'{t0 + i / FPS:.2f}:{v:.2f}' for i, v in enumerate(tr[:, ry, rx])))
print('transitions:', ' '.join(f'{t0 + j / FPS:.2f}{s}' for j, s in ev))
# sheet of frames at each transition and the frame before it
picks = []
for j, s in ev[:12]:
    picks += [max(j - 1, 0), j]
W, H = 320, 180
sheet = Image.new('RGB', (W * 4, (H + 16) * ((len(picks) + 3) // 4)), '#222'); d = ImageDraw.Draw(sheet)
for k, j in enumerate(picks):
    im = Image.fromarray(frames[j]).resize((W, H)); dd = ImageDraw.Draw(im)
    bx, by = xs[rx] * W / DW, ys[ry] * H / DH
    dd.rectangle([bx, by, bx + RW * W / DW, by + RH * H / DH], outline='#0f0', width=2)
    x, y = (k % 4) * W, (k // 4) * (H + 16)
    sheet.paste(im, (x, y + 16)); d.text((x + 4, y + 2), f'{t0 + j / FPS:.2f}s L={tr[j, ry, rx]:.2f}', fill='#fff')
sheet.save(out, quality=85)
