import sys, glob, os, pickle, time
from vector import trace_png
src = sys.argv[1] if len(sys.argv)>1 else "glyphs_norm"
t0=time.time(); traces={}
for p in sorted(glob.glob(f"{src}/*.png")):
    gid=os.path.splitext(os.path.basename(p))[0]
    traces[gid]=trace_png(p)
pickle.dump(traces, open("traces.pkl","wb"))
print(f"traced {len(traces)} glyphs from {src}/ in {time.time()-t0:.1f}s")
