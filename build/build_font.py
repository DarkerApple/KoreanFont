import time, os
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib.removeOverlaps import removeOverlaps
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontcommon import *
import hangul

VERSION="2.002"

def make_comp(components):
    """Composite glyph; bakes the global SLANT in (shear about baseline y=0).
    Accepts (name,bx,by,dx,dy) anisotropic or legacy (name,scale,dx,dy)."""
    g=Glyph(); g.numberOfContours=-1; g.components=[]
    for comp in components:
        if len(comp)==5: name,bx,by,dx,dy=comp
        else: name,bx,dx,dy=comp; by=bx
        c=GlyphComponent(); c.glyphName=name
        c.x=int(round(dx+SLANT*dy)); c.y=int(round(dy))
        c.flags=0x0002                       # ARGS_ARE_XY_VALUES
        c.transform=[[float(bx),float(SLANT*by)],[0.0,float(by)]]
        g.components.append(c)
    return g

def shear(cs, s=SLANT):
    sh=lambda p:(p[0]+s*p[1], p[1])
    out=[]
    for c in cs:
        o=[(c[0][0], sh(c[0][1]))]
        for seg in c[1:]:
            o.append((seg[0], sh(seg[1]) if seg[0]=='line' else tuple(sh(p) for p in seg[1])))
        out.append(o)
    return out

def build(family, out, include_korean, style="Regular", weightclass=400):
    t0=time.time()
    glyphs={'.notdef':notdef_glyph()}; hmtx={'.notdef':(600,60)}; cmap={}
    order=['.notdef','space']; simple=set(['.notdef','space'])
    glyphs['space']=glyph_from_em([]); hmtx['space']=(330,0); cmap[0x20]='space'

    # ---- ASCII (flattened simple glyphs) ----
    for gid,m in meta.items():
        if m['role']!='uni' or m['empty']: continue
        cp=m['cp']; bl=baseline_for(gid,category_for_cp(cp))
        em,bw,bh=em_contours_raw(gid, bl)
        name="uni%04X"%cp; glyphs[name]=glyph_from_em(em)
        hmtx[name]=(int(round(bw*S+2*SB)), SB); cmap[cp]=name
        order.append(name); simple.add(name)


    # ---- tabular digits: uniform advance, each digit centred ----
    dws={}
    for cp in range(0x30,0x3A):
        gid="uni%04X"%cp
        if gid in glyphs:
            _,bw,_=em_contours_raw(gid, baseline_for(gid,'alpha'))
            dws[cp]=bw*S
    if dws:
        advd=int(round(max(dws.values())+2*SB))
        for cp,w in dws.items():
            gid="uni%04X"%cp
            pad=SB+(advd-2*SB-w)/2.0
            em,_,_=em_contours_raw(gid, baseline_for(gid,'alpha'), sb=pad)
            glyphs[gid]=glyph_from_em(em)
            hmtx[gid]=(advd, int(round(pad)))

    # ---- synthesize $ ^ | and en/em dashes ----
    def add_simple(cp, contours, adv, lsb=SB):
        if cp in cmap: return                    # a drawn glyph wins over synthetics
        nm="uni%04X"%cp; glyphs[nm]=glyph_from_em(contours); hmtx[nm]=(adv,lsb)
        cmap[cp]=nm; order.append(nm); simple.add(nm)
    def rect(x0,y0,x1,y1): return [('move',(x0,y0)),('line',(x1,y0)),('line',(x1,y1)),('line',(x0,y1))]
    add_simple(0x7C, shear([rect(0,-90,76,700)]), 76+2*SB)
    add_simple(0x5E, shear([[('move',(150,690)),('line',(280,470)),('line',(232,470)),
                       ('line',(150,610)),('line',(68,470)),('line',(20,470))]]), 300+2*SB)
    def barred(src, cp, bars):
        """currency synth: source letter + horizontal bar(s)"""
        if cp in cmap or src not in glyphs: return
        em,bw,_=em_contours_raw(src, baseline_for(src,"alpha"))
        ys=[q[1] for c in em for p in c for q in ([p[1]] if p[0]!='curve' else list(p[1]))]
        xs=[q[0] for c in em for p in c for q in ([p[1]] if p[0]!='curve' else list(p[1]))]
        x0,x1=min(xs)-40,max(xs)+40
        add_simple(cp, em+shear([rect(x0,y-27,x1,y+27) for y in bars]), int(round(bw*S+2*SB)))
    s_em,sbw,_=em_contours_raw("uni0053", baseline_for("uni0053","alpha"))   # already sheared
    xs=[q[0] for c in s_em for p in c for q in ([p[1]] if p[0]!='curve' else [p[1][2]])]
    scx=(min(xs)+max(xs))/2
    add_simple(0x24, s_em+shear([rect(scx-26,-70,scx+26,760)]), int(round(sbw*S+2*SB)))
    barred("uni0057",0x20A9,[300])                 # ₩ = W + bar
    barred("uni0043",0x20AC,[300,430])             # € = C + bars
    barred("uni0059",0x00A5,[240,370])             # ¥ = Y + bars
    hy_em,_,_=em_contours_raw("uni002D", baseline_for("uni002D","symbol"))
    hys=[q[1] for c in hy_em for p in c for q in ([p[1]] if p[0]!='curve' else [p[1][2]])]
    hymid=(min(hys)+max(hys))/2; hyth=max(56,(max(hys)-min(hys)))
    add_simple(0x2013, shear([rect(40,hymid-hyth/2,500,hymid+hyth/2)]), 540)
    add_simple(0x2014, shear([rect(20,hymid-hyth/2,840,hymid+hyth/2)]), 880)

    def add_comp(cp, comps, adv):
        if cp in cmap: return                    # drawn glyph wins
        nm="uni%04X"%cp; glyphs[nm]=make_comp(comps); hmtx[nm]=(adv,0)
        cmap[cp]=nm; order.append(nm)
    add_comp(0x2026,[("uni002E",1.0,0,0),("uni002E",1.0,300,0),("uni002E",1.0,600,0)],900+2*SB)  # …
    add_comp(0x00B7,[("uni002E",1.0,0,250)], hmtx["uni002E"][0])                                  # ·
    def alias(cp,src):
        if src in glyphs and cp not in cmap: cmap[cp]=src
    alias(0x00A0,"space"); alias(0x0060,"uni0027")
    alias(0x2018,"uni0027"); alias(0x2019,"uni0027")
    alias(0x201C,"uni0022"); alias(0x201D,"uni0022")
    alias(0x2010,"uni002D"); alias(0x2011,"uni002D"); alias(0x2212,"uni002D")

    nsyl=0; ncompat=0
    if include_korean:
        # base jamo (simple, cleaned); one weight variant per scale bucket
        import json as _json
        buckets=_json.load(open("buckets.json"))
        basegids=[f"{g}_{k}" for g,c in sorted(buckets.items()) for k in range(len(c))]
        basegids+=[f"jung{i:02d}" for i in (9,10,11,14,15,16,19)]   # whole compound vowels (compat jamo)
        for gid in basegids:
            nm=hangul.base_name(gid)
            glyphs[nm]=glyph_from_em(hangul.base_contours(gid)); hmtx[nm]=(1000,0)
            order.append(nm); simple.add(nm)
        # 11,172 syllables (composites)
        for ci in range(19):
            for ji in range(21):
                for ki in range(28):
                    cp=0xAC00+((ci*21)+ji)*28+ki
                    glyphs["uni%04X"%cp]=make_comp(hangul.compose_components(ci,ji,ki))
                    hmtx["uni%04X"%cp]=(hangul.ADV,0); cmap[cp]="uni%04X"%cp
                    order.append("uni%04X"%cp); nsyl+=1
        # compatibility jamo
        cons="ㄱㄲㄳㄴㄵㄶㄷㄸㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅃㅄㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
        vow ="ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
        comp={}
        for k,ch in enumerate(cons):
            if ch in hangul.CHO: comp[0x3131+k]="cho%02d"%hangul.CHO.index(ch)
            elif ch in hangul.JONG: comp[0x3131+k]="jong%02d"%hangul.JONG.index(ch)
        for k,ch in enumerate(vow): comp[0x314F+k]="jung%02d"%hangul.JUNG.index(ch)
        for cpc,gid in comp.items():
            glyphs["uni%04X"%cpc]=make_comp([hangul.standalone_component(gid)])
            hmtx["uni%04X"%cpc]=(hangul.ADV,0); cmap[cpc]="uni%04X"%cpc
            order.append("uni%04X"%cpc); ncompat+=1

    fb=FontBuilder(UPM, isTTF=True)
    fb.setupGlyphOrder(order); fb.setupCharacterMap(cmap)
    fb.setupGlyf(glyphs); fb.setupHorizontalMetrics(hmtx)
    fb.setupHorizontalHeader(ascent=ASC, descent=DESC, lineGap=120)
    ps=family.replace(" ","")+"-"+style
    fb.setupNameTable({"familyName":family,"styleName":style,
        "uniqueFontIdentifier":f"{family} {style} {VERSION}","fullName":f"{family} {style}",
        "version":f"Version {VERSION}","psName":ps,
        "manufacturer":"Built from handwriting"})
    fb.setupOS2(sTypoAscender=ASC, sTypoDescender=DESC, sTypoLineGap=120,
                usWinAscent=920, usWinDescent=300, sxHeight=X_H, sCapHeight=CAP_H,
                achVendID="HAND", fsType=0, usWeightClass=weightclass)
    fb.setupPost(keepGlyphNames=False)
    removeOverlaps(fb.font, glyphNames=simple)
    fb.font['head'].fontRevision=float(VERSION)
    if style=="Bold":
        fb.font['head'].macStyle|=0x0001
        fb.font['OS/2'].fsSelection=(fb.font['OS/2'].fsSelection & ~0x40)|0x20
    fb.font.save(out)
    print(f"{out}: {len(glyphs)} glyphs (syl {nsyl}, compat {ncompat}) "
          f"{os.path.getsize(out)/1e6:.2f}MB  {time.time()-t0:.1f}s")

if __name__=='__main__':
    import os as _os
    STYLE=_os.environ.get("LH_STYLE","Regular")
    WC={"Light":300,"Regular":400,"Bold":700}[STYLE]
    build("Lightheaded",       f"Lightheaded-{STYLE}.ttf",       True,  STYLE, WC)
    build("Lightheaded Latin", f"Lightheaded-Latin-{STYLE}.ttf", False, STYLE, WC)
