#!/usr/bin/env python3
"""Flash guard: the last step of the render. Holds every region of the screen to at most 6 luminance
transitions (3 flashes) in any second, and muxes the song back in.

usage: flashguard.py IN_VIDEO OUT.mp4 AUDIO.wav [DURATION [AUDIO_START]]   (AUDIO_START: where IN_VIDEO starts in the song)

Regions, thresholds and counting match flashcheck2.py: quarter-width x quarter-height regions on a 1/16
stride, a transition is a swing of at least 0.1 in a region's average relative luminance between turning
points (darker end below 0.8). When a frame would give a region its 7th transition inside one second, that
region's exposure is adjusted just enough to keep the swing under the threshold: dimmed when it would get too
bright, lifted toward white when it would get too dark. The picture itself stays current (no ghosting), and the
adjustment fades out over about 80 px around the region, so it shows no hard edge. If that can't get a region
under the limit, the region is blended toward the previous frame instead. Once a region has 5 transitions, near
misses (0.085 to 0.1, which encoding could tip over) are held back too. Only the few frames and regions that
would otherwise flash too often are touched; everything else passes through bit for bit. Not a certified
Harding/PEAT test; flashcheck2.py re-checks the encoded result.
"""
import subprocess, sys, numpy as np

FF = __import__('os').environ.get('FFMPEG', 'ffmpeg')   # an ffmpeg with libx264
src, dst, audio = sys.argv[1:4]
dur = sys.argv[4] if len(sys.argv) > 4 else None
astart = sys.argv[5] if len(sys.argv) > 5 else None
W, H, FPS = 1920, 1080, 30
F = 5                                  # analysis at 384x216, like flashcheck2
DW, DH = W // F, H // F
RW, RH, SX, SY = DW // 4, DH // 4, DW // 16, DH // 16
ys = np.arange(0, DH - RH + 1, SY); xs = np.arange(0, DW - RW + 1, SX)
TH, DARK = 0.1, 0.8          # counting exactly as flashcheck2 does
NEAR, ALLOW = 0.085, 0.07   # a swing that could count once encoded (NEAR) is held to ALLOW:
SOFT, HARD = 5, 6            # near misses from 5 transitions in the last second on, everything from 6 on
FR = 8                       # feather radius in analysis pixels (40 px at 1080p)

dec = subprocess.Popen([FF, '-v', 'error', '-i', src, '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], stdout=subprocess.PIPE)
enc_args = [FF, '-v', 'error', '-y', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-s', f'{W}x{H}', '-r', str(FPS), '-i', '-']
if dur: enc_args += ['-t', dur]
if astart: enc_args += ['-ss', astart]
enc_args += ['-i', audio]
if dur: enc_args += ['-t', dur]
enc_args += ['-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'medium', '-crf', '21', '-pix_fmt', 'yuv420p',
             '-c:a', 'aac', '-b:a', '256k', '-shortest', '-movflags', '+faststart', dst]
enc = subprocess.Popen(enc_args, stdin=subprocess.PIPE)


def lin(v):                             # sRGB 0..255 (float) -> linear 0..1
    v = v / 255.0
    return np.where(v <= 0.04045, v / 12.92, ((v + 0.055) / 1.055) ** 2.4)


def region_means(frame):
    low = frame.reshape(DH, F, DW, F, 3).mean((1, 3))
    rgb = lin(low)
    L = 0.2126 * rgb[..., 0] + 0.7152 * rgb[..., 1] + 0.0722 * rgb[..., 2]
    c = np.pad(L.cumsum(0).cumsum(1), ((1, 0), (1, 0)))
    y0, x0 = ys[:, None], xs[None, :]
    return (c[y0 + RH, x0 + RW] - c[y0, x0 + RW] - c[y0 + RH, x0] + c[y0, x0]) / (RW * RH)


class Zig:                              # same state machine as flashcheck2.Zigzag
    def __init__(self): self.dir = None

    def step(self, x, commit=True):
        if self.dir is None:
            if commit:
                self.dir = np.zeros(x.shape, np.int8); self.ext = x.copy(); self.lo = x.copy(); self.hi = x.copy()
            return np.zeros(x.shape, bool), np.zeros(x.shape, np.int8), x.copy()
        d, ext = self.dir, self.ext
        u = d == 0
        lo = np.where(u, np.minimum(self.lo, x), self.lo); hi = np.where(u, np.maximum(self.hi, x), self.hi)
        up0 = u & (x - lo >= TH) & (lo < DARK)
        dn0 = u & ~up0 & (hi - x >= TH) & (x < DARK)
        r = d == 1
        ext = np.where(r & (x > ext), x, ext)
        dn1 = r & (ext - x >= TH) & (x < DARK)
        f = d == -1
        ext = np.where(f & (x < ext), x, ext)
        up1 = f & (x - ext >= TH) & (ext < DARK)
        up, dn = up0 | up1, dn0 | dn1
        # the reference a new swing is measured from, for the limiter
        ref = np.where(u, np.where(up0, lo, hi), ext)
        if commit:
            self.lo, self.hi = lo, hi
            self.dir = np.where(up, 1, np.where(dn, -1, d)).astype(np.int8)
            self.ext = np.where(up | dn, x, ext)
        return up | dn, np.where(up, 1, np.where(dn, -1, 0)).astype(np.int8), ref


def box(a, r, axis):
    c = np.cumsum(np.pad(a, [(r + 1, r) if k == axis else (0, 0) for k in range(2)], mode='edge'), axis=axis)
    n = a.shape[axis]
    return (np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis) - np.take(c, np.arange(0, n), axis)) / (2 * r + 1)


def feather(A):
    """Spread each held region's alpha outward by FR (a min filter), then blur by FR, so that inside the region
    the alpha is unchanged (or lower) and outside it fades to 1 without an edge."""
    E = np.pad(A, FR, constant_values=1.0)
    for ax in (0, 1):
        m = E.copy()
        for d in range(1, FR + 1):
            m = np.minimum(m, np.roll(E, d, ax)); m = np.minimum(m, np.roll(E, -d, ax))
        E = m
    E = E[FR:-FR, FR:-FR]
    for _ in range(2):
        E = box(box(E, FR // 2, 0), FR // 2, 1)
    return np.minimum(E, 1.0)


def region_map(fac):
    """Per-pixel factor map (full resolution, 1 = untouched) from per-region factors: the lowest factor of the
    regions covering a pixel, feathered."""
    A = np.ones((DH, DW), np.float32)
    for ry, rx in zip(*np.nonzero(fac < 1)):
        y0, x0 = ys[ry], xs[rx]
        A[y0:y0 + RH, x0:x0 + RW] = np.minimum(A[y0:y0 + RH, x0:x0 + RW], fac[ry, rx])
    return np.repeat(np.repeat(feather(A), F, 0), F, 1)[..., None]


def expose(cand, dfac, bfac):
    """Dim (dfac) and lift toward white (bfac) the given regions of the current frame."""
    c = cand.astype(np.float32)
    o = 255 - (255 - c * region_map(dfac)) * region_map(bfac)
    return np.clip(o.round(), 0, 255).astype(np.uint8)


def blocked(m, recent):
    return ((m >= NEAR) & (m < TH) & (recent >= SOFT)) | ((m >= NEAR) & (recent >= HARD))


def swing(z, x):
    """How far x reverses from the running extreme, and in which direction (+1 up, -1 down), before any threshold."""
    if z.dir is None: return np.zeros(x.shape), np.zeros(x.shape, np.int8), x.copy()
    u = z.dir == 0
    lo = np.where(u, np.minimum(z.lo, x), z.lo); hi = np.where(u, np.maximum(z.hi, x), z.hi)
    ext = np.where(z.dir == 1, np.maximum(z.ext, x), np.where(z.dir == -1, np.minimum(z.ext, x), z.ext))
    up_m = np.where(u, x - lo, np.where(z.dir == -1, x - ext, 0.0))
    dn_m = np.where(u, hi - x, np.where(z.dir == 1, ext - x, 0.0))
    up_ok = up_m > 0; dn_ok = dn_m > 0
    darker_up = np.where(u, lo, ext); darker_dn = x
    up_m = np.where(up_ok & (darker_up < DARK), up_m, 0.0); dn_m = np.where(dn_ok & (darker_dn < DARK), dn_m, 0.0)
    d = np.where(up_m >= dn_m, 1, -1).astype(np.int8)
    m = np.maximum(up_m, dn_m)
    ref = np.where(d > 0, np.where(u, lo, ext), np.where(u, hi, ext))
    return m, d, ref


zig = Zig()
ring = np.zeros((FPS - 1, len(ys), len(xs)), np.uint8)   # transitions in the previous 29 frames
prev = None; prevL = None
fr = W * H * 3
i = touched = 0
log = []
while True:
    buf = dec.stdout.read(fr)
    if len(buf) < fr: break
    cand = np.frombuffer(buf, np.uint8).reshape(H, W, 3)
    Lc = region_means(cand)
    recent = ring.sum(0)
    mag, dirn, ref = swing(zig, Lc)
    need = blocked(mag, recent)
    out = cand
    if need.any() and prev is not None:
        # target: a swing of at most ALLOW from the reference, in the direction the frame wanted to go
        tgt = np.where(dirn > 0, np.minimum(ref + ALLOW, Lc), np.maximum(ref - ALLOW, Lc))
        # first try exposure: dim a region that would swing up too far, lift one that would swing down too far
        dfac = np.where(need & (dirn > 0), (np.maximum(tgt, 1e-4) / np.maximum(Lc, 1e-4)) ** (1 / 2.2), 1.0)
        bfac = np.where(need & (dirn < 0), np.clip((1 - tgt) / np.maximum(1 - Lc, 1e-4), 0, 1), 1.0)
        ok = False
        for it in range(8):
            out = expose(cand, dfac, bfac)
            Lo = region_means(out)
            m2, d2, r2 = swing(zig, Lo)
            bad = blocked(m2, recent)
            if not bad.any(): ok = True; break
            t2 = np.where(d2 > 0, r2 + ALLOW, r2 - ALLOW)
            dfac = np.where(bad & (d2 > 0), dfac * np.clip(np.maximum(t2, 1e-4) / np.maximum(Lo, 1e-4), 0, 1) ** (1 / 2.2) * .97, dfac)
            bfac = np.where(bad & (d2 < 0), bfac * np.clip((1 - t2) / np.maximum(1 - Lo, 1e-4), 0, 1) * .97, bfac)
        how = 'exposure'
        if not ok:   # fall back: blend those regions toward the previous frame
            how = 'blend'
            den = Lc - prevL
            a = np.where(np.abs(den) > 1e-6, (tgt - prevL) / np.where(np.abs(den) > 1e-6, den, 1), 0.0)
            alpha = np.where(need, np.clip(a, 0, 1), 1.0)
            for it in range(6):
                if it == 5: alpha = np.where(alpha < 1, 0.0, alpha)   # last resort: hold those regions still
                Af = region_map(alpha)
                out = (prev.astype(np.float32) + Af * (cand.astype(np.float32) - prev)).round().astype(np.uint8)
                Lo = region_means(out)
                m2, _, _ = swing(zig, Lo)
                bad = blocked(m2, recent)
                if not bad.any(): break
                alpha = np.where(bad, np.minimum(alpha, 1.0) * 0.5, alpha)
            dfac = alpha
        touched += 1
        log.append((i / FPS, int(need.sum()), how, float(min(dfac.min(), bfac.min()))))
    Lo = region_means(out) if out is not cand else Lc
    ev, _, _ = zig.step(Lo, commit=True)
    ring[i % (FPS - 1)] = ev
    prev, prevL = out, Lo
    enc.stdin.write(out.tobytes())
    i += 1
dec.wait(); enc.stdin.close(); enc.wait()
print(f'{i} frames; guard touched {touched} frames')
for t, n, how, a in log[:120]:
    print(f'  {t:.2f}s regions {n} {how} min factor {a:.2f}')
