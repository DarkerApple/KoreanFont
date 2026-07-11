"""Hangul syllable composition: place cho/jung/jong jamo into zones."""
import json as _json, os as _os, re as _re
from fontcommon import traces, meta
_B=_json.load(open("buckets.json")) if _os.path.exists("buckets.json") else {}
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
        if vt=='vert': return dict(cho=(.02,.04,.52,.71), jung=(.53,.02,.45,.96))
        if vt=='horz': return dict(cho=(.04,.02,.92,.54), jung=(.04,.56,.92,.42))
        return dict(cho=(.02,.02,.43,.46), jung=(.05,.03,.89,.95))   # mix
    else:
        # batchim band sits close under the body
        if vt=='vert': return dict(cho=(.02,.02,.50,.54), jung=(.53,.02,.45,.54), jong=(.06,.56,.88,.385))
        if vt=='horz': return dict(cho=(.05,.02,.90,.37), jung=(.04,.40,.92,.20), jong=(.06,.605,.88,.35))
        return dict(cho=(.02,.02,.42,.38), jung=(.27,.02,.68,.57), jong=(.06,.585,.88,.375))  # mix

# per-role fill factor and alignment (ax,ay in 0..1; .5=center)
ROLE_FIT={'cho':0.96,'jung':0.96,'jong':1.0}

def T(gid):
    """Trace lookup with fallbacks: variant -> plain -> raw."""
    if gid in traces: return traces[gid]
    base=_re.sub(r'_\d+$','',gid)
    if base in traces: return traces[base]
    return traces['raw_'+base]

def select_variant(gid, zone, fill, align):
    """Pick the weight variant whose calibration scale is nearest this placement
    (selection geometry always from the raw trace for determinism)."""
    B=_B.get(gid)
    if not B: return gid
    key='raw_'+gid if 'raw_'+gid in traces else gid
    (sx,sy),x0,yT,W,H=placement_raw(key, zone, fill, align, opt_gid=gid)
    s=H*((sx*sy)**0.5)/1000.0        # stroke responds to the mean scale
    k=min(range(len(B)), key=lambda i:abs(B[i]-s))
    vg=f"{gid}_{k}"
    return vg if vg in traces else gid

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
POLICY={'cho':((0.78,0.97),1.80,1.15), 'jong':((0.80,0.99),1.30,1.05)}

RING_A=1.35           # ㅇ stretches toward its zone's aspect (per vowel direction)

def _scales_for(gid, zone, fill):
    W,H,cs=T(gid)
    zx,zy,zw,zh=zone
    zwe=zw*SQW; zhe=zh*SQH
    if gid.startswith('cho11'): fill*=0.92        # ring slightly smaller overall
    sx0=fill*zwe/W; sy0=fill*zhe/H
    sc=min(sx0,sy0)
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

def placement_raw(gid, zone, fill, align, opt_gid=None):
    """placement() without variant selection (used for selection itself)."""
    fill=optical_fill(opt_gid or gid, fill)
    W,H,cs=T(gid)
    zx,zy,zw,zh=zone
    zL=SQ_L+zx*SQW; zR=SQ_L+(zx+zw)*SQW
    zTop=SQ_T-zy*SQH; zBot=SQ_T-(zy+zh)*SQH
    zwe, zhe = zR-zL, zTop-zBot
    sx,sy=_scales_for(gid, zone, fill)
    gw, gh = W*sx, H*sy
    ax,ay=align
    x0=zL+(zwe-gw)*ax
    yTop=zTop-(zhe-gh)*ay
    return (sx,sy), x0, yTop, W, H

def placement(gid, zone, fill, align):
    return placement_raw(gid, zone, fill, align)

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

def component(gid, zone, fill, align):
    """Return (base_name, bx, by, dx, dy): anisotropic scales relative to the
    height-1000 base glyph, plus offset."""
    gid=select_variant(gid, zone, fill, align)
    (sx,sy),x0,yTop,W,H=placement(gid,zone,fill,align)
    return base_name(gid), H*sx/1000.0, H*sy/1000.0, x0, yTop-H*sy

# alignment per role/type: pull jamo toward where they belong
def align_for(role, vt):
    if role=='cho':
        if vt=='vert': return (0.42,0.45)   # centered in left half
        if vt=='horz': return (0.5,0.35)     # center, upper
        return (0.35,0.30)
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

COUPLE=90             # gap between cho ink and a vertical vowel bar (em)

def _ink_span(comps):
    xs=[]
    for name,bx,by,dx,dy in comps:
        gid=name.replace('jamo_','')
        W,H,_=T(gid)
        xs.append(dx); xs.append(dx + W*(1000.0/H)*bx)
    return min(xs), max(xs)

def compose_components(cho_i, jung_i, jong_full):
    has=jong_full>0
    z=zones(jung_i, has); vt=vtype(jung_i)
    comps=[component("cho%02d"%cho_i, z['cho'], ROLE_FIT['cho'], align_for('cho',vt))]
    jc=component("jung%02d"%jung_i, z['jung'], ROLE_FIT['jung'], align_for('jung',vt))
    if vt=='vert':
        # couple the vowel bar to the initial, with a floor so narrow bodies
        # (이/비) keep a commercial-consistent syllable width
        _,cmaxx=_ink_span(comps)
        name,bx,by,dx,dy=jc
        gid=name.replace('jamo_',''); W,H,_=T(gid)
        jw=W*(1000.0/H)*bx
        BAR_MIN=SQ_L+0.72*SQW
        nx=min(max(cmaxx+COUPLE, BAR_MIN), SQ_R-jw)
        jc=(name,bx,by,nx,dy)
    comps.append(jc)
    if has:
        jz=jong_zone(jong_full-1, z['jong'])
        comps.append(component("jong%02d"%(jong_full-1), jz, ROLE_FIT['jong'], align_for('jong',vt)))
    # optical centring of the whole syllable in its fixed advance
    mn,mx=_ink_span(comps)
    shift=(ADV-(mx-mn))/2.0 - mn
    comps=[(n,bx,by,dx+shift,dy) for (n,bx,by,dx,dy) in comps]
    return comps

# standalone jamo (for compatibility-jamo codepoints): centred in the square
def standalone_component(gid):
    return component(gid, (.12,.06,.76,.88), 0.90, (0.5,0.5))

def syl_code(ci,ji,ki): return 0xAC00 + (ci*21+ji)*28 + ki
