import sys, glob, os, pickle, time, tempfile
import numpy as np
from PIL import Image
from vector import trace_png

from PIL import ImageFilter
MAXSIDE=420
def trace_capped(p):
    im=Image.open(p).convert('L')
    m=max(im.size)
    if m<=MAXSIDE and "glyphs_norm" not in p: return trace_png(p)
    if m>MAXSIDE:
        s=MAXSIDE/m
        im=im.resize((max(2,round(im.width*s)),max(2,round(im.height*s))), Image.LANCZOS)
    im=im.filter(ImageFilter.GaussianBlur(1.0))          # kill resample wobble
    arr=np.asarray(im)
    with tempfile.NamedTemporaryFile(suffix=".png",delete=False) as t:
        Image.fromarray(np.where(arr<128,0,255).astype(np.uint8)).save(t.name)
        r=trace_png(t.name, opttolerance=1.0, alphamax=1.3)
    os.unlink(t.name)
    return r
src = sys.argv[1] if len(sys.argv)>1 else "glyphs_norm"
t0=time.time(); traces={}
for p in sorted(glob.glob(f"{src}/*.png")):
    traces[os.path.splitext(os.path.basename(p))[0]]=trace_capped(p)
for p in sorted(glob.glob("glyphs/*.png")):     # raw geometry for variant selection
    traces["raw_"+os.path.splitext(os.path.basename(p))[0]]=trace_png(p)
pickle.dump(traces, open("traces.pkl","wb"))
print(f"traced {len(traces)} entries from {src}/ (+raw) in {time.time()-t0:.1f}s")
