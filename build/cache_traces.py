import json, pickle, time
from vector import trace_png
meta=json.load(open("meta.json"))
t0=time.time(); traces={}
for gid in meta:
    W,H,cs=trace_png(f"glyphs/{gid}.png")
    traces[gid]=(W,H,cs)
pickle.dump(traces, open("traces.pkl","wb"))
print("traced", len(traces), "glyphs in %.1fs"%(time.time()-t0))
