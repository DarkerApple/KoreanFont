import json, re, numpy as np, os
from PIL import Image
from scipy import ndimage
import hangul
hangul._B={}          # collect placements from raw geometry only (deterministic buckets)
from fontcommon import S, eff_f
meta=json.load(open("meta.json"))
OUT="glyphs_norm"; os.makedirs(OUT, exist_ok=True)
for _f in os.listdir(OUT): os.remove(os.path.join(OUT,_f))   # no stale variants
T_EM=80.0        # target final rendered stroke width (em)
GID_BOOST={}     # directional targeting handles ㅟ/ㅢ now
MAX_DILATE=9.0
PAD=12
SPAN=1.10        # scale bucket max span
RSPAN=1.07       # ratio bucket max span
MAXK=40

# ---- collect every placement (scale, anisotropy) per jamo ----
pl={}
for ci in range(19):
  for ji in range(21):
    for ki in range(28):
      for name,bx,by,dx,dy in hangul.compose_components(ci,ji,ki):
        gid=re.sub(r'_\d+$','',name.replace('jamo_',''))
        pl.setdefault(gid,[]).append(((bx*by)**0.5, bx/by))

def split1d(vals, span, maxk):
    cl=[np.sort(np.array(vals))]
    while len(cl)<maxk:
        spans=[(c.max()/c.min() if c.min()>0 else 1.0) for c in cl]
        j=int(np.argmax(spans))
        if spans[j]<=span: break
        c=cl[j]; cut=int(np.argmax(c[1:]/c[:-1]))+1
        cl[j:j+1]=[c[:cut],c[cut:]]
    return cl

buckets={}
for gid,v in pl.items():
    geos=[g for g,r in v]
    out=[]
    for gc in split1d(geos, SPAN, 6):
        glo,ghi=gc.min(),gc.max()
        rs=[r for g,r in v if glo<=g<=ghi]
        for rc in split1d(rs, RSPAN, 6):
            out.append([float(np.median(gc)), float(np.median(rc))])
    # dedupe near-identical
    ded=[]
    for g,r in out:
        if not any(abs(np.log(g/g2))<.04 and abs(np.log(r/r2))<.06 for g2,r2 in ded):
            ded.append([g,r])
    buckets[gid]=ded
json.dump(buckets, open("buckets.json","w"))
print("total variants:", sum(len(v) for v in buckets.values()))

def runlen(fg, axis):
    f=fg.astype(np.int32)
    if axis==1: f=f.T
    H,W=f.shape
    idx=np.arange(H)[:,None]*np.ones((1,W),np.int32)
    last=np.where(f==0, idx, -1); last=np.maximum.accumulate(last,axis=0); down=idx-last
    lastr=np.where(f[::-1]==0, idx, -1); lastr=np.maximum.accumulate(lastr,axis=0); up=(idx-lastr)[::-1]
    rl=down+up-1; rl[f==0]=0
    return rl if axis==0 else rl.T

def stroke_w(fg):
    if fg.sum()<8: return 0.0
    dt=ndimage.distance_transform_edt(fg)
    return 4*float(np.median(dt[fg]))

def bounded_gap(fg):
    """Smallest typical internal background gap (px) — fusion guard."""
    bg=~fg
    vals=[]
    for axis in (0,1):
        f=fg if axis==0 else fg.T
        cum_d=np.maximum.accumulate(f,axis=0)            # ink somewhere above
        cum_u=np.maximum.accumulate(f[::-1],axis=0)[::-1] # ink somewhere below
        bounded=(~f)&cum_d&cum_u
        if axis==1: bounded=bounded.T
        rl=runlen(bg,axis)
        g=rl[bounded]
        g=g[g>0]
        if len(g)>50: vals.append(float(np.percentile(g,25)))
    return min(vals) if vals else 1e9

def adjust_iso(fg0, th):
    """Erode/dilate isotropically to stroke half-width th (px), guarding fusion."""
    fg0=np.pad(fg0,PAD)
    cap=max(9.0, 0.45*bounded_gap(fg0))
    dt_in=ndimage.distance_transform_edt(fg0)
    dt_out=ndimage.distance_transform_edt(~fg0)
    c=0.0; cur=fg0
    for _ in range(5):
        h=stroke_w(cur)/2.0
        e=h-th
        if abs(e)<=0.35: break
        c+=e
        c=max(min(c,60.0), -cap)
        if c>=0:
            nxt=dt_in>c
            if nxt.sum()<0.2*fg0.sum(): c*=0.5; nxt=dt_in>c
            cur=nxt
        else:
            cur=(dt_out<=-c)
    return cur

def emit(out_name, fg, th):
    out=adjust_iso(fg, th)
    if not out.any():
        out=np.pad(fg,PAD)                     # never dissolve: keep the source
    ys,xs=np.where(out)
    out=out[ys.min():ys.max()+1, xs.min():xs.max()+1]
    Image.fromarray(np.where(out,0,255).astype(np.uint8)).save(f"{OUT}/{out_name}.png")

Q=1.0     # final-space raster: 1 px per em
n=0
for gid,m in meta.items():
    a=np.asarray(Image.open(f"glyphs/{gid}.png").convert('L')); fg=a<128
    H,W=fg.shape
    if m['role']=='uni':
        nx0,ny0,nx1,ny1=m['box_rel']; boxperpx=(ny1-ny0)/H
        emit(gid, fg, (T_EM/(boxperpx*S*eff_f(gid)))/2.0); n+=1
    else:
        for k,(g,r) in enumerate(buckets.get(gid,[])):
            bx=g*(r**0.5); by=g/(r**0.5)
            sx=bx*1000.0/H; sy=by*1000.0/H      # em per px per direction
            Wp=max(3,round(W*sx*Q)); Hp=max(3,round(H*sy*Q))
            im=Image.fromarray(np.where(fg,0,255).astype(np.uint8)).resize((Wp,Hp), Image.LANCZOS)
            fgs=np.asarray(im)<128
            emit(f"{gid}_{k}", fgs, (T_EM*Q)/2.0); n+=1
print(f"normalized -> {n} bitmaps (final-space pre-stretch, isotropic weight)")
