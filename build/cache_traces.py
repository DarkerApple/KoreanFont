import sys, glob, os, pickle, time
from vector import trace_png
src = sys.argv[1] if len(sys.argv)>1 else "glyphs_norm"
t0=time.time(); traces={}
for p in sorted(glob.glob(f"{src}/*.png")):
    traces[os.path.splitext(os.path.basename(p))[0]]=trace_png(p)
for p in sorted(glob.glob("glyphs/*.png")):     # raw geometry for variant selection
    traces["raw_"+os.path.splitext(os.path.basename(p))[0]]=trace_png(p)
pickle.dump(traces, open("traces.pkl","wb"))
print(f"traced {len(traces)} entries from {src}/ (+raw) in {time.time()-t0:.1f}s")
