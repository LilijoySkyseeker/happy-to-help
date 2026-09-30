import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # repo root
import json, re, difflib
A=os.path.join(ROOT, 'audio')
SCR=os.path.join(ROOT, 'work')
lines=json.load(open(f'{SCR}/lines.json'))
med=json.load(open(f'{A}/words_vocals_medium.en.json'))
sm=json.load(open(f'{A}/words_small.en.json'))
al={x['i']:x for x in json.load(open(f'{A}/aligned.json'))}
def norm(w):
    w=w.lower().replace('’',"'")
    w=re.sub(r"[^a-z0-9']+",' ',w)
    return w.split()
REPL=[('p(doom)','pee doom'),('SQLite','sequel lite'),('OpenSSL','open ssl'),('✓','check'),('--dangerously-skip-permissions','dangerously skip permissions'),('--yolo','dash dash yolo')]
def flat(segs):
    out=[]
    for s in segs:
        for w in s['words']:
            for t in norm(w['w']):
                out.append((t,w['s'],w['e']))
    return out
M=flat(med); S=flat(sm) if isinstance(sm,list) and 'words' in sm[0] else None
# lyric words
L=[]
for i,l in enumerate(lines):
    txt=l[2]
    for a,b in REPL: txt=txt.replace(a,b)
    for t in norm(txt): L.append((t,i))
def sim(a,b):
    if a==b: return 1.0
    r=difflib.SequenceMatcher(None,a,b).ratio()
    return r
def align(L,M):
    n,m=len(L),len(M)
    import numpy as np
    D=np.zeros((n+1,m+1)); P=np.zeros((n+1,m+1),dtype=np.int8)
    gap=-0.45
    for i in range(1,n+1): D[i,0]=i*gap; P[i,0]=1
    for j in range(1,m+1): D[0,j]=j*gap; P[0,j]=2
    for i in range(1,n+1):
        for j in range(1,m+1):
            s=sim(L[i-1][0],M[j-1][0]); s = 1.0 if s==1 else (s*1.2-0.5 if s>0.55 else -0.8)
            c=[D[i-1,j-1]+s, D[i-1,j]+gap, D[i,j-1]+gap]
            k=int(np.argmax(c)); D[i,j]=c[k]; P[i,j]=k
    i,j=n,m; pairs=[]
    while i>0 or j>0:
        k=P[i,j]
        if i>0 and j>0 and k==0:
            pairs.append((i-1,j-1)); i-=1; j-=1
        elif i>0 and (j==0 or k==1): i-=1
        else: j-=1
    return pairs[::-1]
def per_line(L,M):
    pairs=align(L,M)
    res={}
    for li,mj in pairs:
        w,line=L[li]
        mw=M[mj]
        if sim(w,mw[0])<0.55: continue
        res.setdefault(line,[]).append((li,w,mw[0],mw[1],mw[2]))
    return res
RM=per_line(L,M)
json.dump({k:v for k,v in RM.items()},open('med_matches.json','w'))
# first lyric word index per line
first={}; last={}
for idx,(w,i) in enumerate(L):
    first.setdefault(i,idx); last[i]=idx
rows=[]
for i,l in enumerate(lines):
    t0o,t1o,txt=l[0],l[1],l[2]
    a=al.get(i)
    mm=RM.get(i,[])
    nwords=last[i]-first[i]+1 if i in first else 0
    m0=m1=None; cov=len(mm)/max(1,nwords)
    if mm:
        # start: if first matched word is lyric word 0 use its start, else mark
        m0=mm[0][3] if mm[0][0]==first[i] else None
        m1=mm[-1][4] if mm[-1][0]==last[i] else None
        m0a=mm[0][3]; m1a=mm[-1][4]
    else: m0a=m1a=None
    amin=min([w['score'] for w in a['words']]) if a and a['words'] else None
    rows.append(dict(i=i,txt=txt[:44],old=[t0o,t1o],mms=[a['t0'],a['t1']] if a else None,amin=amin,
                     med=[m0,m1],meda=[m0a,m1a],cov=round(cov,2)))
    f=lambda x: '  -   ' if x is None else f'{x:6.2f}'
    print(f"{i:3d} {txt[:40]:40s} old {f(t0o)}-{f(t1o)} | mms {f(a['t0'] if a else None)}-{f(a['t1'] if a else None)} min{(amin if amin is not None else -1):.2f} | med {f(m0)}-{f(m1)} (any {f(m0a)}-{f(m1a)}) cov{cov:.2f}")
json.dump(rows,open('rows.json','w'),indent=0)
