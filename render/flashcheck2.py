#!/usr/bin/env python3
"""Approximate WCAG 2.3.1 / Ofcom flash check on area averages (general flash and red flash).

usage: flashcheck2.py VIDEO [START END]

Not a certified Harding/PEAT test. A flash only matters when a large enough area changes together,
so this tracks the average relative luminance of screen regions, not single pixels (single pixels
flicker whenever something moves, which is not a flash):
- Regions are quarter-width x quarter-height windows (480x270 at 1080p) on a stride of 1/16 of the
  screen. That is 25% of a 10 degree field on a phone held sideways, the WCAG area limit. The whole
  screen (the TV-viewing limit, 25% of the screen) is covered too, since a big flash moves every region.
- A transition is a swing of at least 0.1 in a region's average relative luminance between turning
  points, with the darker end below 0.8. Red: a swing above 20 in max(0,(R-G-B)*320) of a region
  whose average colour is saturated red (R/(R+G+B) >= 0.8).
- A region fails when it has more than 6 transitions (more than 3 flashes) in any 1 s.
"""
import subprocess, sys, numpy as np

FF = __import__('os').environ.get('FFMPEG', 'ffmpeg')   # an ffmpeg with libx264
path = sys.argv[1]
t0 = float(sys.argv[2]) if len(sys.argv) > 2 else 0.0
t1 = float(sys.argv[3]) if len(sys.argv) > 3 else None
FPS = 30
DW, DH = 384, 216
RW, RH = DW // 4, DH // 4        # region = quarter width x quarter height (in decoded px)
SX, SY = DW // 16, DH // 16      # stride

args = [FF, '-v', 'error']
if t0: args += ['-ss', str(t0)]
args += ['-i', path]
if t1 is not None: args += ['-t', str(t1 - t0)]
args += ['-vf', f'fps={FPS},scale={DW}:{DH}:flags=area', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-']
proc = subprocess.Popen(args, stdout=subprocess.PIPE)

lut = np.arange(256) / 255.0
lut = np.where(lut <= 0.04045, lut / 12.92, ((lut + 0.055) / 1.055) ** 2.4).astype(np.float64)
ys = np.arange(0, DH - RH + 1, SY); xs = np.arange(0, DW - RW + 1, SX)


def region_means(img):
    c = np.pad(img.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    y0, x0 = ys[:, None], xs[None, :]
    return (c[y0 + RH, x0 + RW] - c[y0, x0 + RW] - c[y0 + RH, x0] + c[y0, x0]) / (RW * RH)


class Zigzag:
    def __init__(self, th, dark_max=None):
        self.th, self.dm, self.dir = th, dark_max, None

    def ok(self, d):
        return d < self.dm if self.dm is not None else np.ones(d.shape, bool)

    def step(self, x):
        if self.dir is None:
            self.dir = np.zeros(x.shape, np.int8); self.ext = x.copy(); self.lo = x.copy(); self.hi = x.copy()
            return np.zeros(x.shape, bool)
        th = self.th
        u = self.dir == 0
        self.lo = np.where(u, np.minimum(self.lo, x), self.lo); self.hi = np.where(u, np.maximum(self.hi, x), self.hi)
        up0 = u & (x - self.lo >= th) & self.ok(self.lo)
        dn0 = u & ~up0 & (self.hi - x >= th) & self.ok(x)
        r = self.dir == 1
        self.ext = np.where(r & (x > self.ext), x, self.ext)
        dn1 = r & (self.ext - x >= th) & self.ok(x)
        f = self.dir == -1
        self.ext = np.where(f & (x < self.ext), x, self.ext)
        up1 = f & (x - self.ext >= th) & self.ok(self.ext)
        up, dn = up0 | up1, dn0 | dn1
        self.dir = np.where(up, 1, np.where(dn, -1, self.dir)).astype(np.int8)
        self.ext = np.where(up | dn, x, self.ext)
        return up | dn


zl, zr = Zigzag(0.1, 0.8), Zigzag(20.0)
shape = (len(ys), len(xs))
ring_l = np.zeros((FPS,) + shape, np.uint8); ring_r = np.zeros((FPS,) + shape, np.uint8)
fr = DW * DH * 3
i = 0
fails = []
peak = {'lum': (0, 0.0), 'red': (0, 0.0)}
per_sec = {}
while True:
    buf = proc.stdout.read(fr)
    if len(buf) < fr: break
    rgb = lut[np.frombuffer(buf, np.uint8).reshape(DH, DW, 3)]
    L = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    Lm = region_means(L)
    Rm, Gm, Bm = (region_means(rgb[..., k]) for k in range(3))
    sat = Rm / np.maximum(Rm + Gm + Bm, 1e-9) >= 0.8
    red = np.where(sat, np.maximum(0, (Rm - Gm - Bm) * 320), 0)
    ring_l[i % FPS] = zl.step(Lm); ring_r[i % FPS] = zr.step(red)
    t = t0 + i / FPS
    for kind, ring in (('lum', ring_l), ('red', ring_r)):
        n = int(ring.sum(0).max())
        if n > peak[kind][0]: peak[kind] = (n, t)
        s = int(t)
        per_sec[(kind, s)] = max(per_sec.get((kind, s), 0), n)
        if n > 6: fails.append((kind, t, n))
    i += 1
proc.wait()

print(f'frames {i} ({i / FPS:.1f} s from {t0:.2f}); {shape[0] * shape[1]} regions of 1/16 screen')
for k in ('lum', 'red'):
    print(f'{k}: most transitions in any region in any 1 s: {peak[k][0]} (at {peak[k][1]:.2f}s); limit 6')
if not fails:
    print('PASS: no region has more than 3 flashes in any second')
else:
    rng = []
    for k, t, n in sorted(fails):
        if rng and rng[-1][0] == k and t - rng[-1][2] <= 2 / FPS:
            rng[-1][2] = t; rng[-1][3] = max(rng[-1][3], n)
        else:
            rng.append([k, t, t, n])
    print(f'FAIL: {len(fails)} frames in {len(rng)} ranges')
    for k, a, b, n in rng[:60]:
        print(f'  {k} {a:.2f}-{b:.2f}s  up to {n} transitions/s')
busy = sorted((s, n) for (k, s), n in per_sec.items() if k == 'lum' and n >= 5)
print('seconds with 5+ transitions in some region:', ' '.join(f'{s}s:{n}' for s, n in busy))
