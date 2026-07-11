import json, re, numpy as np, os
from PIL import Image
from scipy import ndimage
import hangul
from fontcommon import S, eff_f
meta=json.load(open("meta.json"))
OUT="glyphs_norm"; os.makedirs(OUT, exist_ok=True)
T_EM=85.0        # target final rendered stroke width (em)
MAX_DILATE=6.0
PAD=10
SPAN=1.16        # a bucket may span at most ±8% in scale
MAXK=6

# ---- collect every placement scale per jamo across all 11,172 syllables ----
scales={}
for ci in range(19):
  for ji in range(21):
    for ki in range(28):
      for name,scale,dx,dy in hangul.compose_components(ci,ji,ki):
        gid=re.sub(r'_\d+$','',name.replace('jamo_',''))
        scales.setdefault(gid,[]).append(scale)

# ---- cluster each jamo's scales: split widest bucket at its largest gap ----
buckets={}
for gid,v in scales.items():
    clusters=[np.sort(np.array(v))]
    while len(clusters)<MAXK:
        spans=[(c.max()/c.min() if c.min()>0 else 1.0) for c in clusters]
        j=int(np.argmax(spans))
        if spans[j]<=SPAN: break
        c=clusters[j]
        gaps=c[1:]/c[:-1]
        cut=int(np.argmax(gaps))+1
        clusters[j:j+1]=[c[:cut], c[cut:]]
    buckets[gid]=sorted(float(np.median(c)) for c in clusters)
json.dump(buckets, open("buckets.json","w"))
print("buckets per jamo:", {k:len(v) for k,v in sorted(buckets.items())[:6]}, "...")
print("total base variants:", sum(len(v) for v in buckets.values()))

def half_px(fg):
    if fg.sum()<8: return 0.0
    dt=ndimage.distance_transform_edt(fg)
    return 2*np.median(dt[fg])

def adjust_iter(fg0, th):
    """Iteratively erode/dilate (from the original ink) until half-width hits th."""
    fg0=np.pad(fg0, PAD)
    dt_in =ndimage.distance_transform_edt(fg0)
    dt_out=ndimage.distance_transform_edt(~fg0)
    c=0.0; cur=fg0
    for _ in range(5):
        h=half_px(cur)
        e=h-th
        if abs(e)<=0.25: break
        c+=e
        if c>=0:
            nxt=dt_in>c
            if nxt.sum() < 0.22*fg0.sum():
                c-=e; break
            cur=nxt
        else:
            cur=dt_out<=min(-c, MAX_DILATE)
    return cur

def emit(gid, out_name, th, fg):
    out=adjust_iter(fg, th)
    ys,xs=np.where(out)
    out=out[ys.min():ys.max()+1, xs.min():xs.max()+1]
    Image.fromarray(np.where(out,0,255).astype(np.uint8)).save(f"{OUT}/{out_name}.png")

n=0
for gid,m in meta.items():
    a=np.asarray(Image.open(f"glyphs/{gid}.png").convert('L')); fg=a<128
    H=fg.shape[0]
    if m['role']=='uni':
        nx0,ny0,nx1,ny1=m['box_rel']; boxperpx=(ny1-ny0)/H
        emit(gid, gid, (T_EM/(boxperpx*S*eff_f(gid)))/2.0, fg); n+=1
    else:
        for k,s in enumerate(buckets[gid]):
            emit(gid, f"{gid}_{k}", ((T_EM/s)*H/1000.0)/2.0, fg); n+=1
print(f"normalized -> {n} bitmaps (scale-bucketed variants)")
