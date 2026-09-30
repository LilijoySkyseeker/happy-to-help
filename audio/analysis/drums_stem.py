import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # repo root
# Kick / snare / hi-hat hits from the Demucs drum stem, and the bass envelope from the bass stem, for 3.1.
import numpy as np, librosa, json
SR=22050; HOP=128
d,_=librosa.load('sep4/htdemucs/drums.wav',sr=SR,mono=True)
b,_=librosa.load('sep4/htdemucs/bass.wav',sr=SR,mono=True)
S=np.abs(librosa.stft(d,n_fft=1024,hop_length=HOP)); f=librosa.fft_frequencies(sr=SR,n_fft=1024); ft=HOP/SR
def flux(lo,hi):
    e=np.log1p(S[(f>=lo)&(f<hi)].sum(0)*10); x=np.maximum(0,np.diff(e,prepend=e[0])); return x/(np.percentile(x,99.5)+1e-9)
def peaks(x,delta,wait):
    pk=librosa.util.peak_pick(x,pre_max=3,post_max=3,pre_avg=10,post_avg=10,delta=delta,wait=wait)
    return [(round(float(i*ft),3),round(float(min(1,x[i])),2)) for i in pk]
lo,mid,hi=flux(30,140),flux(1200,5000),flux(7000,11000)
kick=peaks(lo,.12,int(.09/ft))
kt=np.array([k for k,_ in kick])
sn=[p for p in peaks(mid,.14,int(.09/ft)) if not len(kt) or np.min(np.abs(kt-p[0]))>.035 or lo[int(p[0]/ft)]<.35]
hat=[p for p in peaks(hi,.10,int(.05/ft))]
# bass envelope at 30 fps, normalised to its 98th percentile
rb=librosa.feature.rms(y=b,frame_length=2048,hop_length=SR//30)[0]; rb=np.clip(rb/np.percentile(rb,98),0,1)
beats=json.load(open(os.path.join(ROOT, 'audio', 'timing', 'beatmap.json')))
BT=np.array(beats['beats'] if isinstance(beats,dict) else beats)
def phase(t):
    k=np.searchsorted(BT,t)-1
    if k<0 or k>=len(BT)-1: return None
    return (t-BT[k])/(BT[k+1]-BT[k]), k
def hist(name,hits):
    ph=[phase(t) for t,_ in hits]; ph=[p for p in ph if p]
    q=np.histogram([p[0] for p in ph],bins=8,range=(0,1))[0]
    print(f'{name}: {len(hits)} hits; beat-phase histogram (8ths of a beat): {list(q)}')
hist('kick',kick); hist('snare',sn); hist('hat',hat)
json.dump(dict(kick=kick,snare=sn,hat=hat,bass=dict(fps=30,v=[round(float(v),3) for v in rb])),open('drums.json','w'))
for a in range(0,258,30): print(a,'kicks',sum(1 for k,_ in kick if a<=k<a+30),'snares',sum(1 for k,_ in sn if a<=k<a+30),'hats',sum(1 for k,_ in hat if a<=k<a+30),'bass',round(float(rb[a*30:(a+30)*30].mean()),2))
