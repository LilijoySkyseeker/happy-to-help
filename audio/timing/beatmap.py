import os
ROOT = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..'))   # repo root
import json, numpy as np
A=os.path.join(ROOT, 'audio')
d=json.load(open(f'{A}/beatthis.json'))
b=np.array(d['beats']); db=np.array(d['downbeats'])
idx=[0]
for i in range(1,len(b)):
    idx.append(idx[-1]+max(1,int(round((b[i]-b[i-1])/0.435))))
idx=np.array(idx); N=idx[-1]+1
# smooth: local weighted linear regression over beat index (gaussian, sigma 6 beats)
ks=np.arange(N); sm=np.zeros(N)
for k in ks:
    w=np.exp(-0.5*((idx-k)/6.0)**2); m=w>1e-3
    A_=np.vstack([np.ones(m.sum()),idx[m]-k]).T*np.sqrt(w[m])[:,None]
    co=np.linalg.lstsq(A_,b[m]*np.sqrt(w[m]),rcond=None)[0]; sm[k]=co[0]
r=b-sm[idx]
print('N beats',N,'resid rms %.1f ms, max %.1f ms'%(np.sqrt((r**2).mean())*1000,np.abs(r).max()*1000))
big=np.where(np.abs(r)>0.03)[0]; print('beats with |resid|>30ms:',[(round(b[i],2),round(r[i]*1000)) for i in big][:30])
# downbeat phase
dbk=[int(ks[np.argmin(np.abs(sm-t))]) for t in db]
ph=np.array(dbk)%4; vals,cnt=np.unique(ph,return_counts=True); print('downbeat phase counts',dict(zip(vals.tolist(),cnt.tolist())))
P=int(vals[np.argmax(cnt)])
bad=[(round(db[i],2),dbk[i]%4) for i in range(len(db)) if dbk[i]%4!=P]; print('off-phase downbeats',bad)
# extend before first/after last beat
json.dump({'beats':[round(x,4) for x in sm.tolist()],'downPhase':P,'src':'Beat This! (CPJKU) on take1.wav, gaussian-smoothed, half-time gaps filled'},open(f'{A}/beatmap.json','w'))
print('first beats',np.round(sm[:6],3),'last',np.round(sm[-4:],3))
# compare vocal onsets in pass 5/6 with the map
V=[('fold',172.184),('flip',173.085),('read',173.966),('fake',174.807),('find',175.688),('dash',176.569),('patch',177.47),('paraphrase',178.331),('give',179.552),('mom',180.233),('cure',180.894),('con',181.314),('fold',181.734),('flip',182.135),('patch',182.595),('phish',183.016),('scan',183.416),('scam',183.837)]
for w,t in V:
    k=np.searchsorted(sm,t); f=(t-sm[k-1])/(sm[k]-sm[k-1]); print(f'  {w:10s} {t:8.3f}  beat {k-1}+{f:.2f}  (bar pos {(k-1-P)%4})')
