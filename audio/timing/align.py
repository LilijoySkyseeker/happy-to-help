import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # repo root
# Forced-align the real lyric text to the Demucs vocal stem (torchaudio MMS_FA).
# In: work/lines.json (from timeline.js), vocals.wav. Out: audio/aligned.json
import json, re, sys, torch, torchaudio, soundfile as sf
SCR = os.path.join(ROOT, 'work')
lines = json.load(open(f'{SCR}/lines.json'))
_x, sr = sf.read(f'{SCR}/sep/htdemucs/take1/vocals.wav', dtype='float32'); wav = torch.from_numpy(_x.T.copy())
wav = torchaudio.functional.resample(wav.mean(0, keepdim=True), sr, 16000); SR = 16000
B = torchaudio.pipelines.MMS_FA
model = B.get_model(with_star=True).eval(); tok = B.get_tokenizer(); aligner = B.get_aligner()
SUNG = {  # what is actually sung, where it differs from the on-screen text
  "…so who's holding the mouse?@56.9": "now now now now now now now now holding the mouse now now now now now now now so who's holding the mouse",
}
REPL = [('p(doom)', 'pee doom'), ('SQLite', 'sequel lite'), ('OpenSSL', 'open ess ess ell'), ('✓', 'check'),
        ('--dangerously-skip-permissions', 'dangerously skip permissions'), ('HAL', 'hal'), ('mil,', 'mill,')]
def norm(s):
    for a, b in REPL: s = s.replace(a, b)
    s = s.lower().replace('-', ' ')
    return [w for w in (re.sub(r"[^a-z']", '', x) for x in s.split()) if w and w != "'"]
out = []
idx = [i for i, L in enumerate(lines) if L[4] != 'word']
# blocks of nearby lines
blocks, cur = [], []
for i in idx:
    if cur and (lines[i][0] - lines[cur[-1]][1] > 2.5 or lines[i][1] - lines[cur[0]][0] > 22): blocks.append(cur); cur = []
    cur.append(i)
blocks.append(cur)
res = {}
for blk in blocks:
    a = max(0, lines[blk[0]][0] - 1.2); b = lines[blk[-1]][1] + 1.2
    seg = wav[:, int(a*SR):int(b*SR)]
    words, owner = [], []
    for i in blk:
        key = f"{lines[i][2]}@{lines[i][0]}"
        ws = norm(SUNG.get(key, lines[i][2])); words += ws; owner += [i]*len(ws)
    with torch.inference_mode(): em, _ = model(seg)
    spans = aligner(em[0], tok(words))
    ratio = seg.size(1) / em.size(1) / SR
    for w, sp, i in zip(words, spans, owner):
        s, e = a + sp[0].start*ratio, a + sp[-1].end*ratio
        sc = float(sum(x.score*len(x) for x in sp) / sum(len(x) for x in sp))
        res.setdefault(i, []).append(dict(w=w, s=round(s, 3), e=round(e, 3), score=round(sc, 3)))
for i, L in enumerate(lines):
    ws = res.get(i)
    out.append(dict(i=i, text=L[2], old=[L[0], L[1]], words=ws, t0=ws[0]['s'] if ws else L[0], t1=ws[-1]['e'] if ws else L[1]))
json.dump(out, open(os.path.join(ROOT, 'audio', 'timing', 'aligned.json'), 'w'), indent=0)
for o in out:
    if o['words']:
        lo = min(w['score'] for w in o['words'])
        print(f"{o['old'][0]:7.2f}->{o['t0']:7.2f}  {o['old'][1]:7.2f}->{o['t1']:7.2f}  min={lo:.2f}  {o['text'][:50]}")
