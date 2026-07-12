"""Hangul syllable composition: place cho/jung/jong jamo into zones."""
import json as _json, os as _os, re as _re
from fontcommon import traces, meta
_B=_json.load(open("buckets.json")) if _os.path.exists("buckets.json") else {}
_PROF=_json.load(open("profiles.json")) if _os.path.exists("profiles.json") else {}
CHO =['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
JUNG=['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ','ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ']
JONG=['ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ','ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
VERT={0,1,2,3,4,5,6,7,20}; HORZ={8,12,13,17,18}; MIX={9,10,11,14,15,16,19}

# Syllable design square in em (baseline y=0) — sized to commercial Korean fonts
# (Noto Sans KR / Nanum Gothic ink ≈ 0.91 x 0.85 em)
SQ_L, SQ_R, SQ_B, SQ_T = 38, 908, -60, 874
SQW, SQH = SQ_R-SQ_L, SQ_T-SQ_B
ADV = 960

def vtype(j): return 'vert' if j in VERT else ('horz' if j in HORZ else 'mix')

# zones: (x,y,w,h) normalized within square, y measured DOWN from square top.
def zones(jung, has_jong):
    vt=vtype(jung)
    if not has_jong:
        if vt=='vert': return dict(cho=(.02,.09,.52,.80), jung=(.53,.02,.45,.96))
        if vt=='horz': return dict(cho=(.04,.02,.92,.54), jung=(.04,.56,.92,.42))
        return dict(cho=(.01,.01,.56,.61), jung=(.05,.03,.89,.95))   # mix
    else:
        # batchim band sits close under the body
        if vt=='vert': return dict(cho=(.02,.02,.50,.54), jung=(.53,.02,.45,.54), jong=(.06,.56,.88,.385))
        if vt=='horz': return dict(cho=(.05,.02,.90,.37), jung=(.04,.43,.92,.18), jong=(.06,.635,.88,.32))
        return dict(cho=(.01,.01,.53,.49), jung=(.27,.02,.68,.57), jong=(.06,.585,.88,.375))  # mix

# per-role fill factor and alignment (ax,ay in 0..1; .5=center)
ROLE_FIT={'cho':0.96,'jung':0.96,'jong':1.0}

def T(gid):
    """Trace lookup with fallbacks: variant -> plain -> raw."""
    if gid in traces: return traces[gid]
    base=_re.sub(r'_\d+$','',gid)
    if base in traces: return traces[base]
    return traces['raw_'+base]

def select_variant(gid, zone, fill, align, free=False):
    """Pick the weight variant nearest this placement in (scale, anisotropy)."""
    B=_B.get(gid)
    if not B: return gid
    key='raw_'+gid if 'raw_'+gid in traces else gid
    (sx,sy),x0,yT,W,H=placement_raw(key, zone, fill, align, opt_gid=gid, free=free)
    import math
    g=H*((sx*sy)**0.5)/1000.0; r=sx/sy
    def dist(b):
        gb,rb=(b if isinstance(b,(list,tuple)) else (b,1.0))
        return abs(math.log(g/gb))+0.7*abs(math.log(r/rb))
    k=min(range(len(B)), key=lambda i:dist(B[i]))
    vg=f"{gid}_{k}"
    return vg if vg in traces else gid

def select_by(gid, bx, by):
    """Variant selection from final base-relative scales."""
    B=_B.get(gid)
    if not B: return gid
    import math
    g=(bx*by)**0.5; r=bx/by
    def dist(b):
        gb,rb=(b if isinstance(b,(list,tuple)) else (b,1.0))
        return abs(math.log(g/gb))+0.7*abs(math.log(r/rb))
    k=min(range(len(B)), key=lambda i:dist(B[i]))
    vg=f"{gid}_{k}"
    return vg if vg in traces else gid

def raw_dims(gid):
    t=traces.get('raw_'+gid) or T(gid)
    return t[0], t[1]

def fit_box(gid, x0, y0, x1, y1, uniform=False, ax=0.5, ay=0.5):
    """Place gid into the em box; free anisotropic fill unless uniform.
    Returns a component tuple (name, bx, by, dx, dy)."""
    W,H=raw_dims(gid)
    wu=W*1000.0/H                      # base-glyph width units (height=1000)
    bw,bh=x1-x0, y1-y0
    if uniform:
        s=min(bw/wu, bh/1000.0); bx=by=s
    else:
        bx=bw/wu; by=bh/1000.0
        cap=1.85 if gid.startswith('cho11') else AFREE   # rings stay ring-like
        if bx/by>cap: bx=by*cap
        if by/bx>cap: by=bx*cap
    vg=select_by(gid,bx,by)
    Wv,Hv,_=T(vg)
    wuv=Wv*1000.0/Hv
    bx2=min(bx*wu/wuv, bw/wuv)         # variant dims correction, stay inside box
    embw=wuv*bx2; embh=1000.0*by
    dx=x0+(bw-embw)*ax; dy=y0+(bh-embh)*ay
    return base_name(vg), bx2, by, dx, dy

def comp_span(c):
    name,bx,by,dx,dy=c
    gid=name.replace('jamo_','')
    W,H,_=T(gid)
    return dx, dx+W*(1000.0/H)*bx, dy, dy+1000.0*by   # l,r,b,t

def optical_fill(gid, fill):
    """Adapt each jamo's size to its complexity: simple consonants (ㄱㄴㅅ…)
    slightly smaller, complex ones (ㅃㅄ…) use the full zone."""
    if gid.startswith('jung'): return fill
    n=len(T(gid)[2])               # traced contour count = stroke complexity
    if gid.startswith('jong'):     # batchim stays big even when simple
        return fill*(0.97 if n<=1 else 1.0)
    return fill*(0.90 if n<=1 else 0.96 if n==2 else 1.0)

# per-role stretch policy: (h_min,h_max) as zone fraction, max vertical
# anisotropy A, max width overstretch WCAP (x uniform fit)
POLICY={'cho':((0.82,0.99),1.80,1.15), 'jong':((0.80,0.99),1.30,1.05)}

RING_A=1.35           # ㅇ stretches toward its zone's aspect (per vowel direction)

AFREE=2.6            # loose anisotropy cap in free-fit mode

def _scales_for(gid, zone, fill, trace_key=None, free=False):
    W,H,cs=T(trace_key or gid)
    zx,zy,zw,zh=zone
    zwe=zw*SQW; zhe=zh*SQH
    if gid.startswith('cho11') and not free: fill*=0.92   # ring slightly smaller
    sx0=fill*zwe/W; sy0=fill*zhe/H
    sc=min(sx0,sy0)
    if free:                                   # ratio unlocked: fill the zone
        return min(sx0, sy0*AFREE), min(sy0, sx0*AFREE)
    role='cho' if gid.startswith('cho') else 'jong' if gid.startswith('jong') else 'jung'
    if gid.startswith('cho11'):                   # ㅇ: ellipse follows zone shape
        return min(sx0, sc*RING_A), min(sy0, sc*RING_A)
    if role=='jung':
        if zwe>1.8*zhe:                           # flat vowels (ㅗㅜㅡ…) span the width
            return min(sx0, sc*2.1), sc
        return sc,sc
    (fmin,fmax),A,WCAP=POLICY[role]
    tmin,tmax=fmin*zhe,fmax*zhe
    sy=sc
    if H*sy<tmin: sy=min(tmin/H, sc*A, sy0)      # stretch short/wide consonants taller
    if H*sy>tmax: sy=tmax/H                       # cap tall ones (e.g. the ㅇ ring)
    wcap=sc*WCAP
    if zwe>1.8*zhe: wcap=sc*1.9                   # wide-flat zone (horz-vowel context)
    sx=min(sx0, wcap, sy*A)                       # width follows the zone
    sx=max(sx, min(sy/A, sx0))
    return sx,sy

def placement_raw(gid, zone, fill, align, opt_gid=None, free=False):
    """placement() without variant selection (used for selection itself)."""
    logical=opt_gid or _re.sub(r'^raw_','',gid)
    if not free: fill=optical_fill(logical, fill)
    W,H,cs=T(gid)
    zx,zy,zw,zh=zone
    zL=SQ_L+zx*SQW; zR=SQ_L+(zx+zw)*SQW
    zTop=SQ_T-zy*SQH; zBot=SQ_T-(zy+zh)*SQH
    zwe, zhe = zR-zL, zTop-zBot
    sx,sy=_scales_for(logical, zone, fill, trace_key=gid, free=free)
    gw, gh = W*sx, H*sy
    ax,ay=align
    x0=zL+(zwe-gw)*ax
    yTop=zTop-(zhe-gh)*ay
    return (sx,sy), x0, yTop, W, H

def placement(gid, zone, fill, align, free=False):
    return placement_raw(gid, zone, fill, align, free=free)

def place(gid, zone, fill, align):
    gid=select_variant(gid, zone, fill, align)
    (sx,sy),x0,yTop,W,H=placement(gid,zone,fill,align)
    _,_,cs=T(gid)
    def conv(px,py): return (x0+px*sx, yTop-py*sy)
    out=[]
    for c in cs:
        seg2=[('move',conv(*c[0][1]))]
        for seg in c[1:]:
            if seg[0]=='line': seg2.append(('line',conv(*seg[1])))
            else:
                p1,p2,p3=seg[1]; seg2.append(('curve',(conv(*p1),conv(*p2),conv(*p3))))
        out.append(seg2)
    return out

# --- base jamo glyph (normalised: ink height=1000, bottom at 0, left at 0) ---
def base_contours(gid):
    W,H,cs=T(gid); K=1000.0/H
    def conv(px,py): return (px*K, (H-py)*K)
    out=[]
    for c in cs:
        seg2=[('move',conv(*c[0][1]))]
        for seg in c[1:]:
            if seg[0]=='line': seg2.append(('line',conv(*seg[1])))
            else:
                p1,p2,p3=seg[1]; seg2.append(('curve',(conv(*p1),conv(*p2),conv(*p3))))
        out.append(seg2)
    return out

def base_name(gid): return "jamo_"+gid     # e.g. jamo_cho00

def component(gid, zone, fill, align, free=False):
    """Return (base_name, bx, by, dx, dy): anisotropic scales relative to the
    height-1000 base glyph, plus offset."""
    gid=select_variant(gid, zone, fill, align, free=free)
    (sx,sy),x0,yTop,W,H=placement(gid,zone,fill,align,free=free)
    return base_name(gid), H*sx/1000.0, H*sy/1000.0, x0, yTop-H*sy

# alignment per role/type: pull jamo toward where they belong
def align_for(role, vt):
    if role=='cho':
        if vt=='vert': return (0.42,0.50)   # centred on the vowel bar
        if vt=='horz': return (0.5,0.80)     # sink toward the vowel below
        return (0.08,0.55)   # mix: hug the left edge
    if role=='jung':
        if vt=='vert': return (0.85,0.5)     # bar toward the right edge (commercial)
        if vt=='horz': return (0.5,0.6)
        return (0.72,0.55)
    return (0.5,0.28) # jong: hug the body above

# 0-based indices into JONG that are two-consonant clusters (wide finals)
COMPOUND_JONG={2,4,5,8,9,10,11,12,13,14,17}
def jong_zone(j0, base):
    """Wider/taller zone for compound finals so they don't get squished."""
    if j0 in COMPOUND_JONG:
        return (.01, base[1]-.01, .98, base[3]+.02)
    return (.11, base[1], .78, base[3])

def compose(cho_i, jung_i, jong_full):
    cs=[]
    for name,bx,by,dx,dy in compose_components(cho_i,jung_i,jong_full):
        gid=name.replace('jamo_','')
        for c in base_contours(gid):
            seg2=[]
            for seg in c:
                if seg[0]=='curve':
                    seg2.append(('curve',tuple((dx+p[0]*bx, dy+p[1]*by) for p in seg[1])))
                else:
                    seg2.append((seg[0],(dx+seg[1][0]*bx, dy+seg[1][1]*by)))
            cs.append(seg2)
    return cs

COUPLE=70             # 2-D ink clearance between body and a vertical vowel bar (em)

def _ink_span(comps):
    xs=[]
    for name,bx,by,dx,dy in comps:
        gid=name.replace('jamo_','')
        W,H,_=T(gid)
        xs.append(dx); xs.append(dx + W*(1000.0/H)*bx)
    return min(xs), max(xs)

def _prof(gid):
    """Edge profile with the same fallback chain as T()."""
    if gid in _PROF: return _PROF[gid]
    base=_re.sub(r'_\d+$','',gid)
    return _PROF.get(base) or _PROF.get('raw_'+base)

def _couple2d(comps, bar_gid, bar_w, bar_bot, bar_top, gap):
    """Leftmost bar x giving >=gap true 2-D clearance from every placed
    component — lets vowel arms (ㅕㅔ…) tuck into the notch of the initial
    (commercial behaviour) instead of clearing its whole bounding box."""
    pb=_prof(bar_gid)
    if pb is None or not comps:
        return _spans(comps)[1]+gap if comps else SQ_L
    NBp=len(pb['L']); lo=-1e9
    spans=[]
    for c in comps:
        name,bx,by,dx,dy=c
        gid=name.replace('jamo_','')
        W,H,_=T(gid)
        spans.append((_prof(gid), dx, dy, W*(1000.0/H)*bx, 1000.0*by))
    for s in range(64):
        y=bar_bot+(s+0.5)/64.0*(bar_top-bar_bot)
        bi=min(NBp-1, max(0, int((bar_top-y)/(bar_top-bar_bot)*NBp)))
        bl=pb['L'][bi]
        if bl is None: continue
        for pc,cx,cy,cw,chh in spans:
            if not (cy<=y<=cy+chh): continue
            if pc is not None:
                ci=min(len(pc['R'])-1, max(0, int((cy+chh-y)/chh*len(pc['R']))))
                cr=pc['R'][ci]
                if cr is None: continue
                cr=cx+cr*cw
            else:
                cr=cx+cw
            lo=max(lo, cr+gap-bl*bar_w)
    return lo if lo>-1e8 else _spans(comps)[1]+gap

def compose_components(cho_i, jung_i, jong_full):
    has=jong_full>0
    z=zones(jung_i, has); vt=vtype(jung_i)
    if vt=='mix':
        comps=_compose_mix(cho_i, jung_i, jong_full, has)
    elif vt=='vert':
        if jung_i==20:   # plain ㅣ: widen the initial so the block isn't narrow
            zx,zy,zw,zh=z['cho']; z['cho']=(zx,zy,zw+.06,zh)
        comps=[component("cho%02d"%cho_i, z['cho'], ROLE_FIT['cho'], align_for('cho',vt))]
        jc=component("jung%02d"%jung_i, z['jung'], ROLE_FIT['jung'], align_for('jung',vt))
        name,bx,by,dx,dy=jc
        gid=name.replace('jamo_',''); W,H,_=T(gid)
        jw=W*(1000.0/H)*bx
        lo=_couple2d(comps, gid, jw, dy, dy+1000.0*by, COUPLE)
        # floor: block stays wide enough for the width normaliser, but a
        # thin ㅣ bar never gets pushed out just to fill the square
        BAR_MIN=min(_spans(comps)[0]+(0.90*SQW)/1.08-jw,
                    SQ_L+(0.67 if jung_i==20 else 0.62)*SQW)
        nx=min(max(lo, BAR_MIN), SQ_R-jw)
        comps.append((name,bx,by,nx,dy))
        if has:
            comps.append(_guard_jong(comps, component("jong%02d"%(jong_full-1),
                         jong_zone(jong_full-1, z['jong']), ROLE_FIT['jong'], align_for('jong',vt))))
    else:   # horz: vowel anchored, the initial fills everything above it (rule 2)
        jc=component("jung%02d"%jung_i, z['jung'], ROLE_FIT['jung'], align_for('jung',vt))
        _,_,jb,jt=comp_span(jc)
        top=SQ_T-.02*SQH
        cho=fit_box("cho%02d"%cho_i, SQ_L+.05*SQW, jt+(70 if has else 95), SQ_L+.95*SQW, top, ax=0.5, ay=0.5)
        comps=[cho,jc]
        if has:
            comps.append(_guard_jong(comps, component("jong%02d"%(jong_full-1),
                         jong_zone(jong_full-1, z['jong']), ROLE_FIT['jong'], align_for('jong',vt)), mingap=30))
    # ---- uniform block: normalise ink width, then centre in the advance ----
    mn,mx,_,_=_spans(comps)
    w=mx-mn; W_T=0.90*SQW
    f=min(max(W_T/w, 0.94), 1.10)
    if abs(f-1.0)>0.02:
        comps=[(n,bx*f,by,mn+(dx-mn)*f,dy) for (n,bx,by,dx,dy) in comps]
        mn,mx,_,_=_spans(comps)
    shift=(ADV-(mx-mn))/2.0 - mn
    comps=[(n,bx,by,dx+shift,dy) for (n,bx,by,dx,dy) in comps]
    # ---- optical vertical centring: all blocks share one axis (no row wobble)
    _,_,bm,tm=_spans(comps)
    MID=(SQ_T+SQ_B)/2.0
    vs=max(-90.0, min(90.0, MID-(tm+bm)/2.0))
    vs=min(vs, SQ_T+8-tm)                    # never poke above the square
    return [(n,bx,by,dx,dy+vs) for (n,bx,by,dx,dy) in comps]

def _guard_jong(comps, jcomp, mingap=28):
    """Shift a final down (within the square) if it crowds the body above."""
    jl,jr,jb,jt2=comp_span(jcomp)
    need=0.0
    for c in comps:
        l,r,b,t=comp_span(c)
        if jr>l and r>jl and b<jt2+mingap:
            need=max(need, jt2-(b-mingap))
    if need>0:
        need=min(need, jb-(SQ_B-15))
        if need>0:
            jcomp=(jcomp[0],jcomp[1],jcomp[2],jcomp[3],jcomp[4]-need)
    return jcomp

def _spans(comps):
    ls,rs,bs,ts=[],[],[],[]
    for c in comps:
        l,r,b,t=comp_span(c)
        ls.append(l); rs.append(r); bs.append(b); ts.append(t)
    return min(ls),max(rs),min(bs),max(ts)

def _compose_mix(cho_i, jung_i, jong_full, has):
    """Decomposed compound vowel: base (ㅗ/ㅜ/ㅡ) under the initial, bar right."""
    gb=f"jung{jung_i:02d}_base"; gr=f"jung{jung_i:02d}_bar"
    if ('raw_'+gb) not in traces and gb not in traces:      # fallback: whole glyph
        z=zones(jung_i, has)
        comps=[component("cho%02d"%cho_i, z['cho'], ROLE_FIT['cho'], align_for('cho','mix'), free=True),
               component("jung%02d"%jung_i, z['jung'], ROLE_FIT['jung'], align_for('jung','mix'))]
        if has:
            comps.append(component("jong%02d"%(jong_full-1),
                         jong_zone(jong_full-1, z['jong']), ROLE_FIT['jong'], align_for('jong','mix')))
        return comps
    # vertical budget (fractions of SQH, from the top)
    if has: cho_h, base_h, jong_y, gap = .34, .17, .615, 60
    else:   cho_h, base_h, jong_y, gap = .42, .26, None, 85
    top=SQ_T-.02*SQH
    # initial: top-left, free fill
    cho=fit_box("cho%02d"%cho_i, SQ_L+.02*SQW, top-cho_h*SQH, SQ_L+.56*SQW, top, ax=0.35, ay=0.4)
    comps=[cho]
    cl,cr,cb,ct=comp_span(cho)
    # base: width follows the initial (stem tucked inside its footprint),
    # with commercial-scale air under the cho and a longer stem
    bw=(cr-cl)*1.12
    bx0=max(SQ_L+.01*SQW, cl-(bw-(cr-cl))/2.0)
    btop=cb-gap
    base=fit_box(gb, bx0, btop-base_h*SQH, bx0+bw, btop)
    comps.append(base)
    # bar: right, 2-D coupled with floor, spanning the body height
    bar_top=top
    bar_bot=(SQ_T-(jong_y-.02)*SQH) if has else (SQ_B+18)
    W,H=raw_dims(gr); wu=W*1000.0/H
    by=(bar_top-bar_bot)/1000.0
    bxs=by                                              # bars keep natural aspect
    vg=select_by(gr,bxs,by)
    Wv,Hv,_=T(vg); wuv=Wv*1000.0/Hv
    jw=wuv*bxs
    lo=_couple2d(comps, vg, jw, bar_bot, bar_top, COUPLE)
    BAR_MIN=min(_spans(comps)[0]+(0.90*SQW)/1.08-jw, SQ_L+0.62*SQW)
    nx=min(max(lo, BAR_MIN), SQ_R-jw)
    comps.append((base_name(vg), bxs, by, nx, bar_bot))
    if has:
        z=zones(jung_i, True)
        comps.append(_guard_jong([cho,base], component("jong%02d"%(jong_full-1),
                     jong_zone(jong_full-1, z['jong']), ROLE_FIT['jong'], align_for('jong','mix'))))
    return comps

# standalone jamo (for compatibility-jamo codepoints): centred in the square
def standalone_component(gid):
    return component(gid, (.12,.06,.76,.88), 0.90, (0.5,0.5))

def syl_code(ci,ji,ki): return 0xAC00 + (ci*21+ji)*28 + ki
