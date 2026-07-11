"""Hangul syllable composition: place cho/jung/jong jamo into zones."""
from fontcommon import traces, meta
CHO =['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
JUNG=['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ','ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ']
JONG=['ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ','ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
VERT={0,1,2,3,4,5,6,7,20}; HORZ={8,12,13,17,18}; MIX={9,10,11,14,15,16,19}

# Syllable design square in em (baseline y=0) — compact
SQ_L, SQ_R, SQ_B, SQ_T = 55, 865, -48, 858
SQW, SQH = SQ_R-SQ_L, SQ_T-SQ_B
ADV = 915

def vtype(j): return 'vert' if j in VERT else ('horz' if j in HORZ else 'mix')

# zones: (x,y,w,h) normalized within square, y measured DOWN from square top.
def zones(jung, has_jong):
    vt=vtype(jung)
    if not has_jong:
        if vt=='vert': return dict(cho=(.02,.02,.50,.95), jung=(.53,.02,.45,.95))
        if vt=='horz': return dict(cho=(.04,.02,.92,.52), jung=(.04,.55,.92,.43))
        return dict(cho=(.02,.02,.43,.45), jung=(.05,.03,.93,.95))   # mix
    else:
        if vt=='vert': return dict(cho=(.02,.02,.50,.64), jung=(.53,.02,.45,.64), jong=(.12,.69,.76,.29))
        if vt=='horz': return dict(cho=(.05,.02,.90,.34), jung=(.04,.37,.92,.30), jong=(.12,.69,.76,.29))
        return dict(cho=(.02,.02,.40,.42), jung=(.27,.02,.71,.63), jong=(.12,.69,.76,.29))  # mix

# per-role fill factor and alignment (ax,ay in 0..1; .5=center)
ROLE_FIT={'cho':0.95,'jung':0.95,'jong':0.95}

def optical_fill(gid, fill):
    """Adapt each jamo's size to its complexity: simple consonants (ㄱㄴㅅ…)
    slightly smaller, complex ones (ㅃㅄ…) use the full zone."""
    if gid.startswith('jung'): return fill
    n=len(traces[gid][2])          # traced contour count = stroke complexity
    return fill*(0.90 if n<=1 else 0.96 if n==2 else 1.0)

def placement(gid, zone, fill, align):
    """Return (sc, x0, yTop, W, H): scale (px->em) and top-left anchor in em."""
    fill=optical_fill(gid, fill)
    W,H,cs=traces[gid]
    zx,zy,zw,zh=zone
    zL=SQ_L+zx*SQW; zR=SQ_L+(zx+zw)*SQW
    zTop=SQ_T-zy*SQH; zBot=SQ_T-(zy+zh)*SQH
    zwe, zhe = zR-zL, zTop-zBot
    sc=min(fill*zwe/W, fill*zhe/H)
    gw, gh = W*sc, H*sc
    ax,ay=align
    x0=zL+(zwe-gw)*ax
    yTop=zTop-(zhe-gh)*ay
    return sc, x0, yTop, W, H

def place(gid, zone, fill, align):
    sc,x0,yTop,W,H=placement(gid,zone,fill,align)
    _,_,cs=traces[gid]
    def conv(px,py): return (x0+px*sc, yTop-py*sc)
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
    W,H,cs=traces[gid]; K=1000.0/H
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
    """Return (base_glyph_name, scale, dx, dy) referencing the normalised jamo."""
    sc,x0,yTop,W,H=placement(gid,zone,fill,align)
    scale=H*sc/1000.0
    return base_name(gid), scale, x0, yTop-H*sc

# alignment per role/type: pull jamo toward where they belong
def align_for(role, vt):
    if role=='cho':
        if vt=='vert': return (0.30,0.45)   # left, mid
        if vt=='horz': return (0.5,0.35)     # center, upper
        return (0.30,0.30)
    if role=='jung':
        if vt=='vert': return (0.62,0.5)
        if vt=='horz': return (0.5,0.6)
        return (0.6,0.55)
    return (0.5,0.7)  # jong: center, lower

# 0-based indices into JONG that are two-consonant clusters (wide finals)
COMPOUND_JONG={2,4,5,8,9,10,11,12,13,14,17}
def jong_zone(j0, base):
    """Wider/taller zone for compound finals so they don't get squished."""
    if j0 in COMPOUND_JONG:
        return (.03, base[1]-.01, .94, base[3]+.02)
    return (.15, base[1], .70, base[3])

def compose(cho_i, jung_i, jong_full):
    has=jong_full>0
    z=zones(jung_i, has); vt=vtype(jung_i)
    cs=[]
    cs+=place("cho%02d"%cho_i, z['cho'], ROLE_FIT['cho'], align_for('cho',vt))
    cs+=place("jung%02d"%jung_i, z['jung'], ROLE_FIT['jung'], align_for('jung',vt))
    if has:
        jz=jong_zone(jong_full-1, z['jong'])
        cs+=place("jong%02d"%(jong_full-1), jz, ROLE_FIT['jong'], align_for('jong',vt))
    return cs

def compose_components(cho_i, jung_i, jong_full):
    has=jong_full>0
    z=zones(jung_i, has); vt=vtype(jung_i)
    comps=[component("cho%02d"%cho_i, z['cho'], ROLE_FIT['cho'], align_for('cho',vt)),
           component("jung%02d"%jung_i, z['jung'], ROLE_FIT['jung'], align_for('jung',vt))]
    if has:
        jz=jong_zone(jong_full-1, z['jong'])
        comps.append(component("jong%02d"%(jong_full-1), jz, ROLE_FIT['jong'], align_for('jong',vt)))
    return comps

# standalone jamo (for compatibility-jamo codepoints): centred in the square
def standalone_component(gid):
    return component(gid, (.12,.06,.76,.88), 0.90, (0.5,0.5))

def syl_code(ci,ji,ki): return 0xAC00 + (ci*21+ji)*28 + ki
