import json, numpy as np, os
from PIL import Image
from scipy import ndimage
import hangul
from fontcommon import S, eff_f
meta=json.load(open("meta.json"))
OUT="glyphs_norm"; os.makedirs(OUT, exist_ok=True)
T_EM=85.0     # target final rendered stroke width (em)
JAMO_BOOST=1.07   # jamo render slightly under target (median-scale placements); compensate
MAX_DILATE=4.0

# Composition scales per jamo, split by context: L = no batchim (big zones),
# S = with batchim (small zones). jong only ever appears in S.
scales_L={}; scales_S={}
for ci in range(19):
  for ji in range(21):
    for ki in range(28):
      d = scales_L if ki==0 else scales_S
      for name,scale,dx,dy in hangul.compose_components(ci,ji,ki):
        d.setdefault(name.split('_L')[0].split('_S')[0].replace('jamo_',''),[]).append(scale)
ref_L={k:float(np.median(v)) for k,v in scales_L.items()}
ref_S={k:float(np.median(v)) for k,v in scales_S.items()}

def half_px(fg):
    dt=ndimage.distance_transform_edt(fg)
    if fg.sum()<8: return 0.0,dt
    return 2*np.median(dt[fg]), dt   # stroke≈4*median -> half≈2*median

def adjust(a, fg, th):
    """Erode/dilate ink to hit half-width th (px). Returns black/white array."""
    h,dt=half_px(fg)
    e=h-th
    if e>0.4:                                # too thick -> erode
        newfg=dt>e
        if newfg.sum() < 0.25*fg.sum(): newfg=dt>(h*0.5)
    elif e<-0.4:                             # too thin -> dilate (capped)
        g=int(np.ceil(min(-e,MAX_DILATE)))+1
        fg2=np.pad(fg,g)
        dtb=ndimage.distance_transform_edt(~fg2)
        newfg=dtb<=min(-e,MAX_DILATE)
    else:
        newfg=fg
    return np.where(newfg,0,255).astype(np.uint8)

def save(gid, out_name, sref):
    a=np.asarray(Image.open(f"glyphs/{gid}.png").convert('L')); fg=a<128
    W,H=fg.shape[1],fg.shape[0]
    m=meta[gid]
    if m['role']=='uni':
        nx0,ny0,nx1,ny1=m['box_rel']; boxperpx=(ny1-ny0)/H
        th=(T_EM/(boxperpx*S*eff_f(gid)))/2.0
    else:
        th=((T_EM*JAMO_BOOST/sref)*H/1000.0)/2.0
    Image.fromarray(adjust(a,fg,th)).save(f"{OUT}/{out_name}.png")

n=0
for gid,m in meta.items():
    if m['role']=='uni':
        save(gid, gid, None); n+=1
    elif m['role'] in ('cho','jung'):
        save(gid, gid+"_L", ref_L[gid]); save(gid, gid+"_S", ref_S[gid]); n+=2
    else:                                    # jong
        save(gid, gid, ref_S[gid]); n+=1
print(f"normalized -> {n} bitmaps (L/S variants for cho/jung)")
