import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # repo root
# Builds prototype/timeline.js (v4) from:
#   beatmap.json (Beat This! beats, smoothed), aligned.json (MMS forced alignment per line),
#   words_vocals_medium.en.json (whisper medium on the vocal stem), words_small.en.json (whisper small, full mix),
#   aligned_fast.json (MMS on the 168-187 s block).
import json, re, difflib, numpy as np
A = os.path.join(ROOT, 'audio')
P = os.path.join(ROOT, 'render')
H = os.path.join(ROOT, 'audio', 'timing')
v3 = json.load(open(f'{H}/lines_v3.json'))
L3 = v3['LINES']
BM = json.load(open(f'{A}/beatmap.json'))
BEATS = np.array(BM['beats'])
BT = json.load(open(f'{A}/beatthis.json'))
MMS = {x['i']: x for x in json.load(open(f'{A}/aligned.json'))}
FAST = json.load(open(f'{A}/aligned_fast.json'))
def beat_t(b):  # fractional beat index -> time
    k = int(np.floor(b)); f = b - k
    return float(BEATS[k] + f * (BEATS[k + 1] - BEATS[k]))
def t_beat(t):
    k = int(np.searchsorted(BEATS, t)); k = min(max(k, 1), len(BEATS) - 1)
    return k - 1 + (t - BEATS[k - 1]) / (BEATS[k] - BEATS[k - 1])

# ---------- restructure lines ----------
lines = []  # dict(t0,t1,text,side,skin,opts,orig)
for i, l in enumerate(L3):
    d = dict(t0=l[0], t1=l[1], text=l[2], side=l[3], skin=l[4], opts=(l[5] if len(l) > 5 else {}) or {}, orig=i)
    if i == 16:   # chorus-1 tag: sung "so who's holding the mouse?", then a chant, then the question again
        lines.append(dict(d, text="…so who's holding the mouse?", opts={}, orig=None, fixed=[("…so", 54.87), ("who's", 55.17), ("holding", 55.59), ("the", 56.04), ("mouse?", 56.37)]))
        lines.append(dict(d, text="holding the mouse", skin='chant', opts={}, orig=None, fixed=[("holding", 59.50), ("the", 59.62), ("mouse", 59.84)]))
        lines.append(dict(d, text="…so who's holding the mouse?", opts={'sting': 1}, orig=None, fixed=[("…so", 62.20), ("who's", 62.22), ("holding", 62.66), ("the", 63.09), ("mouse?", 63.55)]))
        continue
    if 61 <= i <= 77:   # pass 6 + help strobe rebuilt below
        continue
    lines.append(d)
# pass 6: one word per beat (beats 413..420); the helps are a stuttered, accelerating chop (vocal onsets + whisper medium)
P6 = [("CURE", 'g'), ("CON", 'b'), ("FOLD", 'g'), ("FLIP", 'b'), ("PATCH", 'g'), ("PHISH", 'b'), ("SCAN", 'g'), ("SCAM", 'b')]
idx6 = next(k for k, d in enumerate(lines) if d['orig'] == 78)  # insert before the collapse
new = []
for j, (w, s) in enumerate(P6):
    t = beat_t(413 + j)
    new.append(dict(t0=t, t1=None, text=w, side=s, skin='word', opts={}, orig=None, fixed=[(w, t)]))
HELPS = [184.34, 184.80, 185.07, 185.50, 185.78, 185.94, 186.06, 186.32, 186.46]
for j, t in enumerate(HELPS):
    new.append(dict(t0=t, t1=None, text="HELP", side='gb'[j % 2], skin='word', opts={}, orig=None, fixed=[("HELP", t)]))
new.append(dict(t0=186.62, t1=None, text="HELP", side='n', skin='word', opts={'stop': 1}, orig=None, fixed=[("HELP", 186.62)]))
lines[idx6:idx6] = new

# ---------- word candidates ----------
REPL = [('p(doom)', 'pee doom'), ('SQLite', 'sequel lite'), ('OpenSSL', 'open ssl'), ('✓', 'check'),
        ('--dangerously-skip-permissions', 'dangerously skip permissions'), ('--yolo', 'dash dash yolo')]
def norm(w):
    w = w.lower().replace('’', "'")
    return re.sub(r"[^a-z0-9']+", ' ', w).split()
def disp_tokens(text):
    out = []
    for tok in text.split():
        tt = tok
        for a, b in REPL: tt = tt.replace(a, b)
        out.append((tok, norm(tt)))
    return out
def flat(segs):
    o = []
    for s in segs:
        for w in s['words']:
            for t in norm(w['w']): o.append((t, w['s'], w['e']))
    return o
MED = flat(json.load(open(f'{A}/words_vocals_medium.en.json')))
SML = flat(json.load(open(f'{A}/words_small.en.json')))
def sim(a, b): return 1.0 if a == b else difflib.SequenceMatcher(None, a, b).ratio()
def dp(L, M, gap=-0.45):
    n, m = len(L), len(M)
    D = np.zeros((n + 1, m + 1)); Pm = np.zeros((n + 1, m + 1), dtype=np.int8)
    D[1:, 0] = np.arange(1, n + 1) * gap; Pm[1:, 0] = 1
    D[0, 1:] = np.arange(1, m + 1) * gap; Pm[0, 1:] = 2
    for i in range(1, n + 1):
        for j in range(1, m + 1):
            s = sim(L[i - 1], M[j - 1]); s = 1.0 if s == 1 else (s * 1.2 - 0.5 if s > 0.55 else -0.8)
            c = (D[i - 1, j - 1] + s, D[i - 1, j] + gap, D[i, j - 1] + gap)
            k = int(np.argmax(c)); D[i, j] = c[k]; Pm[i, j] = k
    i, j, pairs = n, m, {}
    while i > 0 or j > 0:
        k = Pm[i, j]
        if i > 0 and j > 0 and k == 0:
            if sim(L[i - 1], M[j - 1]) >= 0.55: pairs[i - 1] = j - 1
            i -= 1; j -= 1
        elif i > 0 and (j == 0 or k == 1): i -= 1
        else: j -= 1
    return pairs
# global lyric token list (only for lines without fixed words)
G = []  # (line_idx, disp_idx, sub_idx, token)
for li, d in enumerate(lines):
    if 'fixed' in d: continue
    for di, (tok, subs) in enumerate(disp_tokens(d['text'])):
        for si, s in enumerate(subs): G.append((li, di, si, s))
gtok = [g[3] for g in G]
pm = dp(gtok, [m[0] for m in MED]); ps = dp(gtok, [m[0] for m in SML])
CHORUS = {12, 13, 14, 15, 33, 34, 35, 36, 37, 87, 88, 89, 90, 91, 92, 93}
cand = {}  # (li,di,si) -> dict(src->t)
for gi, (li, di, si, s) in enumerate(G):
    c = {}
    if gi in pm: c['med'] = MED[pm[gi]][1]
    if gi in ps: c['sml'] = SML[ps[gi]][1]
    cand[(li, di, si)] = c
# MMS per original line: align its word list to the line's tokens
for li, d in enumerate(lines):
    if 'fixed' in d or d['orig'] is None or d['orig'] not in MMS: continue
    mw = MMS[d['orig']]['words']
    if not mw: continue
    toks = [(di, si, s) for di, (tok, subs) in enumerate(disp_tokens(d['text'])) for si, s in enumerate(subs)]
    pr = dp([t[2] for t in toks], [w['w'].replace("'", "'") for w in mw])
    thr = 0.6 if d['orig'] in CHORUS else 0.4
    for k, j in pr.items():
        c = cand[(li, toks[k][0], toks[k][1])]
        c['chorus'] = d['orig'] in CHORUS
        if mw[j]['score'] >= thr: c['mms'] = mw[j]['s']
        else: c['weak'] = mw[j]['s']
# pass 5: use the fast-block alignment (all its phrase starts sit on beats)
FASTW = [(w, t, sc) for w, t, sc, ph in FAST]
for li, d in enumerate(lines):
    if d['orig'] is not None and 51 <= d['orig'] <= 60 or d['orig'] == 50:
        toks = [(di, si, s) for di, (tok, subs) in enumerate(disp_tokens(d['text'])) for si, s in enumerate(subs)]
        lo, hi = d['t0'] - 1.2, d['t1'] + 1.2
        fw = [f for f in FASTW if lo <= f[1] <= hi]
        pr = dp([t[2] for t in toks], [f[0] for f in fw])
        for k, j in pr.items():
            if fw[j][2] >= 0.2 or True: cand[(li, toks[k][0], toks[k][1])]['fast'] = fw[j][1]
def choose(c):
    if 'fast' in c: return c['fast'], 'fast'
    if c.get('chorus'):   # MMS is unreliable on the stuttered choruses; the vocal-stem transcription is best there
        for k in ('med', 'sml', 'mms'):
            if k in c: return c[k], 'chorus-' + k
    v = [(k, c[k]) for k in ('mms', 'med', 'sml') if k in c]
    if not v: return None, '-'
    if len(v) == 3:
        return float(np.median([x[1] for x in v])), 'median3'
    if len(v) == 2:
        a, b = v[0][1], v[1][1]
        if abs(a - b) < 0.3: return (a + b) / 2, 'mean2'
        if 'mms' in c: return c['mms'], 'pref-mms'
        if 'weak' in c:   # tie-break with the low-confidence forced alignment
            k = min(('med', 'sml'), key=lambda k: abs(c[k] - c['weak']))
            return c[k], 'tie-' + k
        return c['med'], 'pref-med'
    return v[0][1], 'only-' + v[0][0]
# manual line-start overrides (see notes in the reply / memory): value = first-word time
OVR = {   # orig v3 line index -> first-word time
    22: 80.66,    # MMS failed here; small "If you're sure" at 80.66
    23: 84.06,
    24: 87.42,    # an unclear ad-lib sits at 86.25-87.3 (shown as a typing indicator)
    25: 91.05,
    32: 115.50,   # "Ninety": small 115.32, medium 115.54, MMS 115.51
    46: 154.75,   # "15" at 154.66/154.80
    48: 162.02,   # both whispers: "968" at 162.00/162.10
    50: 169.15,
    59: 179.52,
    60: 180.18,
    15: 52.30,
    36: 129.20,
    34: 122.40,
}
LSTART = {12: 42.20, 14: 49.20, 33: 119.18, 35: 126.62, 87: 215.40, 89: 222.60, 93: 236.06}  # stutter pickups before "Happy"
report = []
out = []
for li, d in enumerate(lines):
    dt = disp_tokens(d['text'])
    if 'fixed' in d:
        words = [[w, round(t, 3)] for w, t in d['fixed']]
        out.append(dict(d, words=words)); report.append((li, d, words[0][1], 'fixed', words)); continue
    times = []
    srcs = []
    for di, (tok, subs) in enumerate(dt):
        tt, how = None, '-'
        for si in range(len(subs)):
            t, h = choose(cand[(li, di, si)])
            if t is not None: tt, how = t - (0 if si == 0 else 0.12 * si), h; break
        times.append(tt); srcs.append(how)
    # overrides
    if d['orig'] in OVR:
        times[0] = OVR[d['orig']]; srcs[0] = 'override'
    # fill gaps by interpolation weighted by token length
    n = len(times)
    known = [k for k in range(n) if times[k] is not None]
    if not known:
        times = [d['t0'] + (d['t1'] - d['t0']) * k / max(1, n) for k in range(n)]
    else:
        for k in range(n):
            if times[k] is None:
                p = max([q for q in known if q < k], default=None); q2 = min([q for q in known if q > k], default=None)
                if p is not None and q2 is not None:
                    times[k] = times[p] + (times[q2] - times[p]) * (k - p) / (q2 - p)
                elif p is not None: times[k] = times[p] + 0.22 * (k - p)
                else: times[k] = times[q2] - 0.22 * (q2 - k)
    # monotonic inside the line
    for k in range(1, n):
        if times[k] < times[k - 1] + 0.04: times[k] = times[k - 1] + 0.04
    words = [[tok, round(t, 3)] for (tok, subs), t in zip(dt, times)]
    out.append(dict(d, words=words)); report.append((li, d, times[0], srcs[0], words))
# line t0 = first word; enforce monotonic across lines
for k, d in enumerate(out):
    d['t0'] = LSTART.get(d['orig'], d['words'][0][1]) if d['orig'] is not None else d['words'][0][1]
for k in range(1, len(out)):
    if out[k]['t0'] <= out[k - 1]['t0'] + 0.05:
        print('!! non-monotonic line start', k, out[k]['text'], out[k]['t0'], 'prev', out[k - 1]['t0'])
# t1 = next line start (hero stays up until the next line), except before long silences
for k, d in enumerate(out):
    nxt = out[k + 1]['t0'] if k + 1 < len(out) else 257.56
    last = d['words'][-1][1]
    quiet = d['skin'] in ('same', 'outro') and nxt - last > 2.5
    d['t1'] = round(min(nxt, last + 1.2) if quiet else nxt, 3)
# special cases: the chant fills 56.9-62.2; the outro last line runs to the end
for d in out:
    if d['skin'] == 'chant': d['t0'] = 56.92; d['t1'] = 62.2
    if d['text'].startswith('Is there anything else'): d['t1'] = 257.56
for k, d in enumerate(out):
    if k + 1 < len(out) and out[k + 1]['skin'] == 'chant': d['t1'] = out[k + 1]['t0']
for li, d, t0, how, words in report:
    print(f"{li:3d} {out[li]['t0']:7.2f}-{out[li]['t1']:7.2f} [{how:9s}] {d['text'][:50]:50s} | " + ' '.join(f"{w}@{t:.2f}" for w, t in words[:5]))
# events
EV = {
    # chant: 8th notes from 56.92 to 62.1 (cursor multiplication); "holding the mouse" at 59.5
    'chant': [round(beat_t(b / 2), 3) for b in range(int(np.ceil(t_beat(56.9) * 2)), int(t_beat(62.1) * 2) + 1)],
    'adlib': [[86.25, 87.3]],             # unclear sung phrase: typing indicator only
    'stomp': [89.80, 90.32, 90.62, 90.88],  # "…walk" stutters after "let it walk"
}
json.dump(dict(lines=out, events=EV), open(f'{H}/timeline_v4.json', 'w'), indent=0)
# downbeats as beat indices
db = [int(round(t_beat(t))) for t in BT['downbeats']]
# write JS
def js(v): return json.dumps(v, ensure_ascii=False)
with open(f'{P}/timeline.js', 'w') as f:
    f.write("// Song timeline v4 for audio/take1.wav. Generated by audio/timing/build_timeline.py; edit there or by hand.\n")
    f.write("// BEATS: every beat time from Beat This! (the song drifts from ~136 to ~140 BPM, so no fixed grid).\n")
    f.write("// LINES: [t0, t1, text, side, skin, opts, words]; words = [[displayToken, time], ...] from forced alignment\n")
    f.write("// merged with two Whisper passes. side: n neutral, g good, b bad.\n")
    f.write(f"window.SONG = {{ dur: 257.56 }};\n")
    f.write("window.BEATS = " + js([round(x, 3) for x in BEATS.tolist()]) + ";\n")
    f.write("window.DOWNBEATS = " + js(sorted(set(db))) + ";\n")
    f.write("window.EVENTS = " + js(EV) + ";\n")
    f.write("window.LINES = [\n")
    for d in out:
        f.write("  " + js([round(d['t0'], 3), round(d['t1'], 3), d['text'], d['side'], d['skin'], d['opts'], d['words']]) + ",\n")
    f.write("];\n")
    SECT = [[0, 7.04, 'intro', 0], [7.04, 35.19, 'war', 7], [35.19, 42.2, 'pre', 3], [42.2, 63.64, 'chorus', 9],
            [63.64, 105.02, 'pass1', 2], [105.02, 119.18, 'pass2', 4], [119.18, 133.85, 'chorus', 9], [133.85, 144.78, 'jail', 5],
            [144.78, 158.25, 'pass3', 6], [158.25, 172.18, 'pass4', 8], [172.18, 180.9, 'pass5', 11], [180.9, 187.06, 'pass6', 14],
            [187.06, 195.43, 'collapse', 0], [195.43, 215.4, 'bridge', 1], [215.4, 245.3, 'dream', 12], [245.3, 257.56, 'outro', 0]]
    f.write("// section -> clutter density (background popups) and page colour\n")
    f.write("window.SECTIONS = " + js(SECT) + ";\n")
print('wrote', f'{P}/timeline.js', len(out), 'lines')
