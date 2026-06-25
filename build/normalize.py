import json, numpy as np, os
from PIL import Image
from scipy import ndimage
import hangul
from fontcommon import S, sizecorr
meta=json.load(open("meta.json"))
OUT="glyphs_norm"; os.makedirs(OUT, exist_ok=True)
T_EM=85.0     # target final rendered stroke width (em)

# per-jamo reference scale = 70th pct of its composition scales (lean to thick cases)
scales={}
for ci in range(19):
  for ji in range(21):
    for ki in range(28):
      for name,scale,dx,dy in hangul.compose_components(ci,ji,ki):
        scales.setdefault(name,[]).append(scale)
sref={k:float(np.percentile(v,70)) for k,v in scales.items()}

def half_px(fg):
    dt=ndimage.distance_transform_edt(fg)
    if fg.sum()<8: return 0.0,dt
    return 2*np.median(dt[fg]), dt   # stroke≈4*median -> half≈2*median

def target_px(gid):
    m=meta[gid]; nx0,ny0,nx1,ny1=m['box_rel']
    W,H=Image.open(f"glyphs/{gid}.png").size
    if m['role']=='uni':
        boxperpx=(ny1-ny0)/H
        f=sizecorr(gid)                      # size-normalisation also scales the stroke
        return (T_EM/(boxperpx*S*f))/2.0     # half-width px
    base="jamo_"+gid; s=sref.get(base,0.5)
    return ((T_EM/s)*H/1000.0)/2.0           # half-width px

def normalize(gid):
    p=f"glyphs/{gid}.png"; a=np.asarray(Image.open(p).convert('L')); fg=a<128
    h,dt=half_px(fg)
    th=target_px(gid)
    e=h-th
    if e<=0.4:
        Image.fromarray(np.where(fg,0,255).astype(np.uint8)).save(f"{OUT}/{gid}.png"); return 0.0
    newfg=dt>e
    if newfg.sum() < 0.25*fg.sum():          # don't dissolve
        e=h*0.5; newfg=dt>e
    Image.fromarray(np.where(newfg,0,255).astype(np.uint8)).save(f"{OUT}/{gid}.png")
    return e

es=[]
for gid in meta: es.append(normalize(gid))
print("normalized", len(es), "glyphs; eroded(px) median %.1f max %.1f"%(np.median(es),max(es)))

# quick before/after compare for a few thick ones
from PIL import ImageDraw, ImageFont
tests=["jung20","jung18","cho11","uni0041","uni0061","cho06","jung00","jong20"]
cell=150; sh=Image.new('RGB',(cell*len(tests),cell*2),(255,255,255)); d=ImageDraw.Draw(sh)
for k,gid in enumerate(tests):
    for r,folder in enumerate(["glyphs","glyphs_norm"]):
        im=Image.open(f"{folder}/{gid}.png").convert('L'); s=min((cell-20)/im.width,(cell-20)/im.height)
        im=im.resize((int(im.width*s),int(im.height*s))); sh.paste(im,(k*cell+10,r*cell+10))
sh.save("norm_compare.png"); print("saved norm_compare.png (top=orig, bottom=normalized)")
