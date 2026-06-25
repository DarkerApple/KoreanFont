import sys, json, pickle, time
from vector import trace_png
src = sys.argv[1] if len(sys.argv)>1 else "glyphs_norm"
meta=json.load(open("meta.json")); t0=time.time()
traces={g:trace_png(f"{src}/{g}.png") for g in meta}
pickle.dump(traces, open("traces.pkl","wb"))
print(f"traced {len(traces)} glyphs from {src}/ in {time.time()-t0:.1f}s")
