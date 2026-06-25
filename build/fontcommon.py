"""Shared coordinate mapping + glyph construction for the handwriting font."""
import pickle, json
from fontTools.pens.ttGlyphPen import TTGlyphPen
from fontTools.pens.cu2quPen import Cu2QuPen

UPM   = 1000
S     = 2000.0      # em units per box-unit (cap height ~700)
SB    = 72          # default side bearing (em)
B0    = 0.71        # global baseline in box coords (used for symbols)
DESC_DEPTH = 0.13   # descender depth in box units
DESCSET = set('gjpqy')
CAP_H, X_H, ASC, DESC = 700, 500, 860, -250

traces = pickle.load(open("traces.pkl","rb"))
meta   = json.load(open("meta.json"))

def category_for_cp(cp):
    ch=chr(cp)
    if ch in DESCSET: return 'desc'
    if ('A'<=ch<='Z') or ('a'<=ch<='z') or ('0'<=ch<='9'): return 'alpha'
    return 'symbol'

SIZE_BLEND = 0.6     # how strongly to normalise letter sizes toward category targets
def target_h(gid):
    m=meta[gid]
    if m['role']!='uni': return None
    ch=chr(m['cp'])
    if ('A'<=ch<='Z') or ('0'<=ch<='9'): return CAP_H
    if ch in 'acemnorsuvwxz': return X_H
    if ch in 'bdfhklt': return 720
    if ch in 'gpqy':    return 720
    if ch in 'ij':      return 720
    return None          # symbols: keep natural size

def sizecorr(gid):
    """Uniform scale that pulls a Latin glyph's height toward its category target."""
    Ht=target_h(gid)
    if not Ht: return 1.0
    nx0,ny0,nx1,ny1=meta[gid]['box_rel']; cur=(ny1-ny0)*S
    if cur<=1: return 1.0
    return (1-SIZE_BLEND) + SIZE_BLEND*(Ht/cur)

def em_contours_raw(gid, baseline_box, sb=SB):
    """Map traced contours into em space (baseline->0, left ink->sb),
       applying per-category size normalisation (scaled about baseline/left)."""
    W,H,cs = traces[gid]
    nx0,ny0,nx1,ny1 = meta[gid]['box_rel']
    bw,bh = nx1-nx0, ny1-ny0
    f = sizecorr(gid)
    def conv(px,py):
        box_x = nx0 + (px/W)*bw
        box_y = ny0 + (py/H)*bh
        return ((box_x-nx0)*S*f + sb, (baseline_box-box_y)*S*f)
    out=[]
    for c in cs:
        seg2=[('move',conv(*c[0][1]))]
        for seg in c[1:]:
            if seg[0]=='line': seg2.append(('line',conv(*seg[1])))
            else:
                p1,p2,p3=seg[1]; seg2.append(('curve',(conv(*p1),conv(*p2),conv(*p3))))
        out.append(seg2)
    return out, bw*f, bh*f

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
