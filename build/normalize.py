import json, re, numpy as np, os
from PIL import Image
from scipy import ndimage
import hangul
from fontcommon import S, eff_f
meta=json.load(open("meta.json"))
OUT="glyphs_norm"; os.makedirs(OUT, exist_ok=True)
T_EM=80.0        # target final rendered stroke width (em)
GID_BOOST={}     # directional targeting handles ㅟ/ㅢ now
MAX_DILATE=9.0
PAD=12
SPAN=1.16        # scale bucket max span
RSPAN=1.10       # ratio bucket max span
MAXK=14

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
    for gc in split1d(geos, SPAN, 5):
        glo,ghi=gc.min(),gc.max()
        rs=[r for g,r in v if glo<=g<=ghi]
        for rc in split1d(rs, RSPAN, 4):
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
    """Per-pixel run length along axis (vectorised)."""
    f=fg.astype(np.int32)
    if axis==1: f=f.T
    H,W=f.shape
    idx=np.arange(H)[:,None]*np.ones((1,W),np.int32)
    # distance since last zero (top->down)
    last=np.where(f==0, idx, -1)
    last=np.maximum.accumulate(last,axis=0)
    down=idx-last
    lastr=np.where(f[::-1]==0, idx, -1)
    lastr=np.maximum.accumulate(lastr,axis=0)
    up=(idx-lastr)[::-1]
    rl=down+up-1
    rl[f==0]=0
    return rl if axis==0 else rl.T

def dir_widths(fg):
    """(vertical-stroke width, horizontal-stroke width) in px."""
    if fg.sum()<8: return 0.0,0.0
    h=runlen(fg,1)      # horizontal run length (width of vertical strokes)
    v=runlen(fg,0)
    vm=fg&(h<v); hm=fg&(v<=h)
    wv=float(np.median(h[vm])) if vm.sum()>20 else 0.0
    wh=float(np.median(v[hm])) if hm.sum()>20 else 0.0
    if not wv: wv=wh
    if not wh: wh=wv
    return wv,wh

def morph(fg, ex, ey, dilate=False):
    """Elliptical erode/dilate by (ex,ey) px (either may be 0)."""
    ex=max(ex,1e-6); ey=max(ey,1e-6)
    if dilate:
        dt=ndimage.distance_transform_edt(~fg, sampling=(1.0/ey,1.0/ex))
        return dt<=1.0
    dt=ndimage.distance_transform_edt(fg, sampling=(1.0/ey,1.0/ex))
    return dt>1.0

def adjust_dir(fg0, thx, thy):
    """Iteratively hit half-widths thx (vertical strokes) / thy (horizontal)."""
    fg0=np.pad(fg0,PAD)
    cx=cy=0.0; cur=fg0
    for _ in range(5):
        wv,wh=dir_widths(cur)
        ex=wv/2-thx; ey=wh/2-thy
        if abs(ex)<=0.3 and abs(ey)<=0.3: break
        cx+=ex; cy+=ey
        cx=max(min(cx, 60), -MAX_DILATE); cy=max(min(cy, 60), -MAX_DILATE)
        cur=fg0
        if cx>0.2 or cy>0.2:
            cur=morph(cur, max(cx,0.01), max(cy,0.01))
            if cur.sum()<0.18*fg0.sum():          # don't dissolve
                cx*=0.5; cy*=0.5
                cur=morph(fg0, max(cx,0.01), max(cy,0.01))
        if cx<-0.2 or cy<-0.2:
            cur=morph(cur, max(-cx,0.01), max(-cy,0.01), dilate=True) | cur
    return cur

def emit(out_name, fg, thx, thy):
    out=adjust_dir(fg, thx, thy)
    ys,xs=np.where(out)
    out=out[ys.min():ys.max()+1, xs.min():xs.max()+1]
    Image.fromarray(np.where(out,0,255).astype(np.uint8)).save(f"{OUT}/{out_name}.png")

n=0
for gid,m in meta.items():
    a=np.asarray(Image.open(f"glyphs/{gid}.png").convert('L')); fg=a<128
    H=fg.shape[0]
    if m['role']=='uni':
        nx0,ny0,nx1,ny1=m['box_rel']; boxperpx=(ny1-ny0)/H
        th=(T_EM/(boxperpx*S*eff_f(gid)))/2.0
        emit(gid, fg, th, th); n+=1
    else:
        B=T_EM*GID_BOOST.get(gid,1.0)
        for k,(g,r) in enumerate(buckets[gid]):
            bx=g*(r**0.5); by=g/(r**0.5)
            sx=bx*1000.0/H; sy=by*1000.0/H      # em per px in each direction
            emit(f"{gid}_{k}", fg, (B/sx)/2.0, (B/sy)/2.0); n+=1
print(f"normalized -> {n} bitmaps (2D scale+ratio buckets, directional weight)")
