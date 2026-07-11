"""Shared coordinate mapping + glyph construction for the handwriting font."""
import pickle, json
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen

UPM   = 1000
S     = 2000.0      # em units per box-unit (cap height ~700)
SB    = 50          # default side bearing (em) — compact spacing
B0    = 0.71        # global baseline in box coords (used for symbols)
DESC_DEPTH = 0.10   # descender depth in box units
DESCSET = set('gjpqy')
CAP_H, X_H, ASC, DESC = 700, 500, 880, -290
SLANT = 0.05        # consistent forward tilt (x += SLANT*y about baseline)
MAXW  = 0.82        # cap a glyph's ink width (em fraction) so wide letters (M) don't balloon

traces = pickle.load(open("traces.pkl","rb"))
meta   = json.load(open("meta.json"))

def category_for_cp(cp):
    ch=chr(cp)
    if ch in DESCSET: return 'desc'
    if ('A'<=ch<='Z') or ('a'<=ch<='z') or ('0'<=ch<='9'): return 'alpha'
    return 'symbol'

SIZE_BLEND = 0.78
def _ref_target(gid):
    """(reference height in box units, target em, (f_min,f_max)) per category."""
    m=meta[gid]
    if m['role']!='uni': return None
    ch=chr(m['cp']); nx0,ny0,nx1,ny1=m['box_rel']; bh=ny1-ny0
    if ('A'<=ch<='Z') or ('0'<=ch<='9'): return bh, CAP_H, (0.85,1.30)
    if ch in 'acemnorsuvwxz':            return bh, X_H,   (0.85,1.30)
    if ch in 'bdfhklt':                  return bh, 700,   (0.85,1.25)   # ascenders ≈ cap
    if ch in 'gpqy':  return (ny1-DESC_DEPTH)-ny0, X_H, (0.95,1.50)      # size bowl to x-height
    if ch=='j':       return (ny1-DESC_DEPTH)-ny0, X_H, (0.95,1.50)
    if ch=='i':       return bh, 680, (0.90,1.20)
    return None

def sizecorr(gid):
    rt=_ref_target(gid)
    if not rt: return 1.0
    ref,Ht,(lo,hi)=rt; cur=ref*S
    if cur<=1: return 1.0
    f=(1-SIZE_BLEND)+SIZE_BLEND*(Ht/cur)
    return max(lo, min(hi, f))

import math
def scales(gid):
    """(fx, fy): height-normalising scale fy, with width capped separately as fx
       so over-wide letters (M) keep their height instead of shrinking."""
    fy=sizecorr(gid); fx=fy
    nx0,ny0,nx1,ny1=meta[gid]['box_rel']; bw=nx1-nx0
    if bw*S*fx > MAXW*UPM: fx*=(MAXW*UPM)/(bw*S*fx)
    return fx, fy
def eff_f(gid):
    fx,fy=scales(gid); return math.sqrt(fx*fy)    # for stroke-weight normalisation

def em_contours_raw(gid, baseline_box, sb=SB):
    """Map traced contours into em space (baseline->0, left ink->sb) with
       per-category size normalisation, an ink-width cap, and a consistent slant."""
    W,H,cs = traces[gid]
    nx0,ny0,nx1,ny1 = meta[gid]['box_rel']
    bw,bh = nx1-nx0, ny1-ny0
    fx,fy = scales(gid)
    def conv(px,py):
        box_x = nx0 + (px/W)*bw
        box_y = ny0 + (py/H)*bh
        ex=(box_x-nx0)*S*fx + sb; ey=(baseline_box-box_y)*S*fy
        return (ex + SLANT*ey, ey)        # forward slant about baseline
    out=[]
    for c in cs:
        seg2=[('move',conv(*c[0][1]))]
        for seg in c[1:]:
            if seg[0]=='line': seg2.append(('line',conv(*seg[1])))
            else:
                p1,p2,p3=seg[1]; seg2.append(('curve',(conv(*p1),conv(*p2),conv(*p3))))
        out.append(seg2)
    return out, bw*fx, bh*fy

def baseline_for(gid, category):
    nx0,ny0,nx1,ny1 = meta[gid]['box_rel']
    if category=='desc':   return ny1-DESC_DEPTH
    if category=='symbol': return B0
    return ny1                       # alpha: sit on baseline

def draw_em(em_cs, pen, max_err=1.5):
    qpen=Cu2QuPen(pen, max_err)
    for c in em_cs:
        qpen.moveTo(c[0][1])
        for seg in c[1:]:
            if seg[0]=='line': qpen.lineTo(seg[1])
            else: qpen.curveTo(*seg[1])
        qpen.closePath()

def glyph_from_em(em_cs):
    pen=TTGlyphPen(None); draw_em(em_cs, pen); return pen.glyph()

def notdef_glyph(adv=600):
    pen=TTGlyphPen(None)
    for box in [[(60,0),(540,0),(540,700),(60,700)],
                [(120,60),(120,640),(480,640),(480,60)]]:
        pen.moveTo(box[0])
        for p in box[1:]: pen.lineTo(p)
        pen.closePath()
    return pen.glyph()
