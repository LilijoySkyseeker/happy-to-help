from faster_whisper import WhisperModel
import json,sys
m=WhisperModel(sys.argv[1],device='cpu',compute_type='int8',cpu_threads=4)
segs,info=m.transcribe('vocals.wav',word_timestamps=True,vad_filter=False,language='en',
  initial_prompt="Happy to help! p-doom, nothing went foom, shoggoth, basilisk, AlphaFold, halicin, SQLite, OpenSSL, Wexton, Meliorator, pig-butchering.")
out=[]
for s in segs:
    out.append({'start':s.start,'end':s.end,'text':s.text,'words':[{'w':w.word,'s':w.start,'e':w.end} for w in (s.words or [])]})
    print(f"{s.start:7.2f}-{s.end:7.2f} {s.text}",flush=True)
json.dump(out,open(f'words_vocals_{sys.argv[1]}.json','w'),indent=0)
