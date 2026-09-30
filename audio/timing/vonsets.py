import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # repo root
import numpy as np, soundfile as sf, librosa, json
A=os.path.join(ROOT, 'audio')
x,sr=sf.read(f'{A}/vocals.wav',dtype='float32'); x=x.mean(1)
y=librosa.resample(x,orig_sr=sr,target_sr=22050); sr=22050; hop=128
env=librosa.onset.onset_strength(y=y,sr=sr,hop_length=hop)
rms=librosa.feature.rms(y=y,hop_length=hop)[0]
on=librosa.onset.onset_detect(onset_envelope=env,sr=sr,hop_length=hop,units='time',backtrack=False,delta=0.08,wait=3)
ft=librosa.frames_to_time(np.arange(len(env)),sr=sr,hop_length=hop)
json.dump({'onsets':on.tolist()},open(f'{A}/vocal_onsets.json','w'))
sm=np.array(json.load(open(f'{A}/beatmap.json'))['beats'])
def bp(t):
    k=np.searchsorted(sm,t); return k-1+(t-sm[k-1])/(sm[k]-sm[k-1])
for a,b in [(56.5,63.8),(85.9,91.2),(168.3,172.3),(178.2,181.0),(183.6,187.4)]:
    oo=on[(on>=a)&(on<=b)]
    print(f'--- {a}-{b}: '+' '.join(f'{t:.2f}[{bp(t):.2f}|{rms[np.searchsorted(ft,t)+3]*100:.0f}]' for t in oo))
