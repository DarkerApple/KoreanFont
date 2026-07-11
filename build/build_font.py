import time, os
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib.removeOverlaps import removeOverlaps
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontcommon import *
import hangul

VERSION="1.000"

def make_comp(components):
    """Composite glyph; bakes the global SLANT in (shear about baseline y=0)."""
    g=Glyph(); g.numberOfContours=-1; g.components=[]
    for name,scale,dx,dy in components:
        c=GlyphComponent(); c.glyphName=name
        c.x=int(round(dx+SLANT*dy)); c.y=int(round(dy))
        c.flags=0x0002                       # ARGS_ARE_XY_VALUES
        c.transform=[[float(scale),float(SLANT*scale)],[0.0,float(scale)]]
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

def build(family, out, include_korean):
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
    if 0x5C in cmap: cmap[0x20A9]=cmap[0x5C]     # ₩ won == drawn backslash glyph

    # ---- synthesize $ ^ | and en/em dashes ----
    def add_simple(cp, contours, adv, lsb=SB):
        nm="uni%04X"%cp; glyphs[nm]=glyph_from_em(contours); hmtx[nm]=(adv,lsb)
        cmap[cp]=nm; order.append(nm); simple.add(nm)
    def rect(x0,y0,x1,y1): return [('move',(x0,y0)),('line',(x1,y0)),('line',(x1,y1)),('line',(x0,y1))]
    add_simple(0x7C, shear([rect(0,-90,76,700)]), 76+2*SB)
    add_simple(0x5E, shear([[('move',(150,690)),('line',(280,470)),('line',(232,470)),
                       ('line',(150,610)),('line',(68,470)),('line',(20,470))]]), 300+2*SB)
    s_em,sbw,_=em_contours_raw("uni0053", baseline_for("uni0053","alpha"))   # already sheared
    xs=[q[0] for c in s_em for p in c for q in ([p[1]] if p[0]!='curve' else [p[1][2]])]
    scx=(min(xs)+max(xs))/2
    add_simple(0x24, s_em+shear([rect(scx-26,-70,scx+26,760)]), int(round(sbw*S+2*SB)))
    hy_em,_,_=em_contours_raw("uni002D", baseline_for("uni002D","symbol"))
    hys=[q[1] for c in hy_em for p in c for q in ([p[1]] if p[0]!='curve' else [p[1][2]])]
    hymid=(min(hys)+max(hys))/2; hyth=max(56,(max(hys)-min(hys)))
    add_simple(0x2013, shear([rect(40,hymid-hyth/2,500,hymid+hyth/2)]), 540)
    add_simple(0x2014, shear([rect(20,hymid-hyth/2,840,hymid+hyth/2)]), 880)

    def add_comp(cp, comps, adv):
        nm="uni%04X"%cp; glyphs[nm]=make_comp(comps); hmtx[nm]=(adv,0)
        cmap[cp]=nm; order.append(nm)
    add_comp(0x2026,[("uni002E",1.0,0,0),("uni002E",1.0,300,0),("uni002E",1.0,600,0)],900+2*SB)  # …
    add_comp(0x00B7,[("uni002E",1.0,0,250)], hmtx["uni002E"][0])                                  # ·
    def alias(cp,src):
        if src in glyphs: cmap[cp]=src
    alias(0x00A0,"space"); alias(0x0060,"uni0027")
    alias(0x2018,"uni0027"); alias(0x2019,"uni0027")
    alias(0x201C,"uni0022"); alias(0x201D,"uni0022")
    alias(0x2010,"uni002D"); alias(0x2011,"uni002D"); alias(0x2212,"uni002D")

    nsyl=0; ncompat=0
    if include_korean:
        # base jamo (simple, cleaned)
        for role,n in (("cho",19),("jung",21),("jong",27)):
            for i in range(n):
                gid="%s%02d"%(role,i); nm=hangul.base_name(gid)
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
    ps=family.replace(" ","")+"-Regular"
    fb.setupNameTable({"familyName":family,"styleName":"Regular",
        "uniqueFontIdentifier":f"{family} {VERSION}","fullName":f"{family} Regular",
        "version":f"Version {VERSION}","psName":ps,
        "manufacturer":"Built from handwriting"})
    fb.setupOS2(sTypoAscender=ASC, sTypoDescender=DESC, sTypoLineGap=120,
                usWinAscent=920, usWinDescent=300, sxHeight=X_H, sCapHeight=CAP_H,
                achVendID="HAND", fsType=0)
    fb.setupPost(keepGlyphNames=False)
    removeOverlaps(fb.font, glyphNames=simple)
    fb.font['head'].fontRevision=float(VERSION)
    fb.font.save(out)
    print(f"{out}: {len(glyphs)} glyphs (syl {nsyl}, compat {ncompat}) "
          f"{os.path.getsize(out)/1e6:.2f}MB  {time.time()-t0:.1f}s")

if __name__=='__main__':
    build("Lightheaded",       "Lightheaded-Regular.ttf",       include_korean=True)
    build("Lightheaded Latin", "Lightheaded-Latin-Regular.ttf", include_korean=False)
