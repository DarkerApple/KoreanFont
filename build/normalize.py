import json, re, numpy as np, os
from PIL import Image
from scipy import ndimage
import hangul
hangul._B={}          # collect placements from raw geometry only (deterministic buckets)
from fontcommon import S, eff_f
meta=json.load(open("meta.json"))
OUT="glyphs_norm"; os.makedirs(OUT, exist_ok=True)
for _f in os.listdir(OUT): os.remove(os.path.join(OUT,_f))   # no stale variants
T_EM=float(os.environ.get("LH_TEM","80"))   # target stroke width (em) — weight axis
# optical-color compensation: compressed multi-part jamo run slightly
# lighter — mild, so strokes still read as one thickness family
GID_BOOST={'cho01':0.93,'cho03':0.93,'cho08':0.92,'cho10':0.94,'cho13':0.93,
           'cho18':0.90,
           'jong01':0.93,'jong19':0.94,'jong07':0.94,
           'jong15':0.94,'jong16':0.93,'jong24':0.93,'jong25':0.93,'jong26':0.95,
           **{f"jong{j:02d}":0.92 for j in (2,4,5,8,9,10,11,12,13,14,17)}}
MAX_DILATE=9.0
PAD=40           # must exceed the worst dilation, or thin bars clip flat
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
    """Smallest typical internal background gap (px) — fusion guard.
    Tiny concave pockets at stroke joints are ignored: only gap
    populations big enough to be real counters/deck spacing count."""
    bg=~fg
    vals=[]
    need=max(60, int(0.025*fg.sum()))
    for axis in (0,1):
        f=fg if axis==0 else fg.T
        cum_d=np.maximum.accumulate(f,axis=0)            # ink somewhere above
        cum_u=np.maximum.accumulate(f[::-1],axis=0)[::-1] # ink somewhere below
        bounded=(~f)&cum_d&cum_u
        if axis==1: bounded=bounded.T
        rl=runlen(bg,axis)
        g=rl[bounded]
        g=g[g>0]
        if len(g)>need: vals.append(float(np.percentile(g,25)))
    return min(vals) if vals else 1e9

def bounded_gap_axes(fg):
    """Per-axis bounded gaps: (gx, gy) — gx guards x-dilation (side-by-side
    strokes), gy guards y-dilation (stacked strokes/decks)."""
    bg=~fg
    need=max(60, int(0.025*fg.sum()))
    out=[]
    for axis in (1,0):
        f=fg if axis==0 else fg.T
        cum_d=np.maximum.accumulate(f,axis=0)
        cum_u=np.maximum.accumulate(f[::-1],axis=0)[::-1]
        bounded=(~f)&cum_d&cum_u
        if axis==1: bounded=bounded.T
        rl=runlen(bg,axis)
        g=rl[bounded]; g=g[g>0]
        out.append(float(np.percentile(g,25)) if len(g)>need else 1e9)
    return out[0], out[1]

def _small_mask(fg, frac=0.10):
    """Mask of small detached components (ticks) that erosion must spare."""
    lab,n=ndimage.label(fg)
    if n<2: return None
    tot=fg.sum(); m=np.zeros_like(fg)
    for c in range(1,n+1):
        cc=(lab==c)
        if cc.sum()<frac*tot: m|=cc
    return m if m.any() else None

def _erode_guarded(fg, st):
    """Erode, but small components (ticks) keep their ink."""
    sm=_small_mask(fg)
    out=ndimage.binary_erosion(fg, structure=st)
    if sm is not None: out|=(fg&sm)
    return out

def adjust_dir(fg0, th, kk=None):
    """Directional stroke equalisation: vertical and horizontal stroke
    widths are corrected independently (stretch-proof weight), then the
    result is touched up isotropically. th = half-width target."""
    k=kk if kk else min(0.68, max(0.38, 0.45*(T_EM/80.0)**1.3))
    fg=np.pad(fg0,PAD)
    T=2.0*th
    for _ in range(3):
        ry=runlen(fg,0); rx=runlen(fg,1)
        vpx=fg&(rx<ry); hpx=fg&(ry<rx)
        if vpx.sum()<80 or hpx.sum()<80: break
        mv=float(np.median(rx[vpx])); mh=float(np.median(ry[hpx]))
        if abs(mv-T)<1.5 and abs(mh-T)<1.5: break
        gx,gy=bounded_gap_axes(fg)
        ex=int(round(np.clip((T-mv)/2.0, -6, min(6, k*gx/2.0))))
        ey=int(round(np.clip((T-mh)/2.0, -6, min(6, k*gy/2.0))))
        if ex==0 and ey==0: break
        for e,horiz in ((ex,True),(ey,False)):
            if e==0: continue
            st=np.ones((1,2*abs(e)+1),bool) if horiz else np.ones((2*abs(e)+1,1),bool)
            if e>0: fg=ndimage.binary_dilation(fg, structure=st)
            else:
                nxt=_erode_guarded(fg, st)
                if nxt.sum()>0.25*fg.sum(): fg=nxt
    return fg

def adjust_iso(fg0, th, kk=None, prepad=True):
    """Erode/dilate isotropically to stroke half-width th (px), guarding fusion."""
    fg0=np.pad(fg0,PAD) if prepad else fg0
    k=kk if kk else min(0.68, max(0.38, 0.45*(T_EM/80.0)**1.3))  # bold closes counters more
    cap=max(9.0, k*bounded_gap(fg0))
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
            sm=_small_mask(fg0)
            if sm is not None: nxt=nxt|(fg0&sm)   # ticks never erode away
            cur=nxt
        else:
            cur=(dt_out<=-c)
    return cur

def emit(out_name, fg, th, kk=None, directional=False):
    if directional:
        out=adjust_dir(fg, th, kk)             # stretch-proof per-axis weight
        out=adjust_iso(out, th, kk, prepad=False)
    else:
        out=adjust_iso(fg, th, kk)
    if not out.any():
        out=np.pad(fg,PAD)                     # never dissolve: keep the source
    ys,xs=np.where(out)
    out=out[ys.min():ys.max()+1, xs.min():xs.max()+1]
    Image.fromarray(np.where(out,0,255).astype(np.uint8)).save(f"{OUT}/{out_name}.png")

Q=1.0     # final-space raster: 1 px per em
# multi-deck glyphs (detached tick / stacked bars): stroke is capped to a
# fraction of the rendered height so the decks stay separable at small
# scales; the fraction breathes with the weight so Bold stays bold
_WS=(T_EM/80.0)**0.7
STRUCT_CAP={g:f*_WS for g,f in
            {'cho14':0.18,'cho18':0.16,'cho12':0.22,'cho13':0.20,
             'cho16':0.20,'jong24':0.20,'cho17':0.21,'jong25':0.21,
             'jong22':0.22,'jong23':0.18,'jong26':0.17,'jong04':0.20}.items()}
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
            sboost=min(1.04, max(0.82, (g/0.55)**0.30))   # smaller => lighter
            th_em=max(0.72*T_EM, T_EM*GID_BOOST.get(gid,1.0)*sboost)
            kk=None
            if gid in STRUCT_CAP:
                th_em=min(th_em, STRUCT_CAP[gid]*Hp); kk=0.30   # decks never fuse
            emit(f"{gid}_{k}", fgs, (th_em*Q)/2.0, kk, directional=True); n+=1
print(f"normalized -> {n} bitmaps (final-space pre-stretch, isotropic weight)")
