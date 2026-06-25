import sys, time
from fontTools.fontBuilder import FontBuilder
from fontTools.ttLib.removeOverlaps import removeOverlaps
from fontTools.ttLib.tables._g_l_y_f import Glyph, GlyphComponent
from fontcommon import *
import hangul

FAMILY="Songil Handwriting"
VERSION="1.000"
t0=time.time()

glyphs={'.notdef':notdef_glyph()}; hmtx={'.notdef':(600,60)}; cmap={}
order=['.notdef','space']
glyphs['space']=glyph_from_em([]); hmtx['space']=(330,0); cmap[0x20]='space'
simple=set(['.notdef','space'])

# ---- ASCII (flattened simple glyphs) ----
for gid,m in meta.items():
    if m['role']!='uni' or m['empty']: continue
    cp=m['cp']; cat=category_for_cp(cp); bl=baseline_for(gid,cat)
    em,bw,bh=em_contours_raw(gid, bl)
    name="uni%04X"%cp; glyphs[name]=glyph_from_em(em)
    hmtx[name]=(int(round(bw*S+2*SB)), SB); cmap[cp]=name
    order.append(name); simple.add(name)
# also map U+20A9 (won) to the backslash glyph drawn (₩)
if 0x5C in cmap: cmap[0x20A9]=cmap[0x5C]

# ---- synthesize the 4 ASCII glyphs not in the template ($ ^ ` |) + dashes ----
def add_simple(cp, contours, adv, lsb=SB):
    nm="uni%04X"%cp; glyphs[nm]=glyph_from_em(contours); hmtx[nm]=(adv,lsb)
    cmap[cp]=nm; order.append(nm); simple.add(nm)
def rect(x0,y0,x1,y1): return [('move',(x0,y0)),('line',(x1,y0)),('line',(x1,y1)),('line',(x0,y1))]
add_simple(0x7C, [rect(0,-90,88,700)], 88+2*SB)                       # | bar
add_simple(0x5E, [[('move',(150,690)),('line',(280,470)),('line',(232,470)),
                   ('line',(150,610)),('line',(68,470)),('line',(20,470))]], 300+2*SB)  # ^
s_em,sbw,_=em_contours_raw("uni0053", baseline_for("uni0053","alpha"))
xs=[q[0] for c in s_em for p in c for q in ([p[1]] if p[0]!='curve' else [p[1][2]])]
scx=(min(xs)+max(xs))/2
add_simple(0x24, s_em+[rect(scx-30,-70,scx+30,760)], int(round(sbw*S+2*SB)))   # $
# en/em dash: bold bar at hyphen height/thickness, just longer
hy_em,hbw,_=em_contours_raw("uni002D", baseline_for("uni002D","symbol"))
hys=[q[1] for c in hy_em for p in c for q in ([p[1]] if p[0]!='curve' else [p[1][2]])]
hymid=(min(hys)+max(hys))/2; hyth=max(60,(max(hys)-min(hys)))
add_simple(0x2013, [rect(40,hymid-hyth/2,500,hymid+hyth/2)], 540)     # – en dash
add_simple(0x2014, [rect(20,hymid-hyth/2,840,hymid+hyth/2)], 880)     # — em dash

# ---- base jamo glyphs (normalised, simple) ----
JCHO=range(19); JJUNG=range(21); JJONG=range(27)
for i in JCHO:
    gid="cho%02d"%i; nm=hangul.base_name(gid)
    glyphs[nm]=glyph_from_em(hangul.base_contours(gid)); hmtx[nm]=(1000,0)
    order.append(nm); simple.add(nm)
for i in JJUNG:
    gid="jung%02d"%i; nm=hangul.base_name(gid)
    glyphs[nm]=glyph_from_em(hangul.base_contours(gid)); hmtx[nm]=(1000,0)
    order.append(nm); simple.add(nm)
for i in JJONG:
    gid="jong%02d"%i; nm=hangul.base_name(gid)
    glyphs[nm]=glyph_from_em(hangul.base_contours(gid)); hmtx[nm]=(1000,0)
    order.append(nm); simple.add(nm)

def make_comp(components):
    g=Glyph(); g.numberOfContours=-1; g.components=[]
    for name,scale,dx,dy in components:
        c=GlyphComponent(); c.glyphName=name
        c.x=int(round(dx)); c.y=int(round(dy))
        c.flags=0x0002      # ARGS_ARE_XY_VALUES (scale flag added by compiler)
        c.transform=[[float(scale),0.0],[0.0,float(scale)]]
        g.components.append(c)
    return g

# ---- composite/aliased typographic punctuation ----
def add_comp(cp, comps, adv):
    nm="uni%04X"%cp; glyphs[nm]=make_comp(comps); hmtx[nm]=(adv,0)
    cmap[cp]=nm; order.append(nm)
add_comp(0x2026, [("uni002E",1.0,0,0),("uni002E",1.0,300,0),("uni002E",1.0,600,0)], 900+2*SB)  # …
add_comp(0x00B7, [("uni002E",1.0,0,250)], hmtx["uni002E"][0])                                   # ·
# cmap aliases to existing drawn glyphs (no new outlines)
def alias(cp, srcname):
    if srcname in glyphs: cmap[cp]=srcname
alias(0x00A0,"space")                       # nbsp
alias(0x0060,"uni0027")                      # ` -> apostrophe
alias(0x2018,"uni0027"); alias(0x2019,"uni0027")     # ' ' curly singles
alias(0x201C,"uni0022"); alias(0x201D,"uni0022")     # " " curly doubles
alias(0x2010,"uni002D"); alias(0x2011,"uni002D")     # hyphen variants
alias(0x2212,"uni002D")                      # minus sign

# ---- 11,172 syllable composites ----
nsyl=0
for ci in range(19):
    for ji in range(21):
        for ki in range(28):
            cp=0xAC00+((ci*21)+ji)*28+ki
            comps=hangul.compose_components(ci,ji,ki)
            name="uni%04X"%cp
            glyphs[name]=make_comp(comps); hmtx[name]=(hangul.ADV,0)
            cmap[cp]=name; order.append(name); nsyl+=1

# ---- compatibility jamo (standalone) U+3131..U+3163 ----
COMPAT={}  # codepoint -> source glyph id
cons="ㄱㄲㄳㄴㄵㄶㄷㄸㄹㄺㄻㄼㄽㄾㄿㅀㅁㅂㅃㅄㅅㅆㅇㅈㅉㅊㅋㅌㅍㅎ"
for k,ch in enumerate(cons):
    cpc=0x3131+k
    if ch in hangul.CHO: COMPAT[cpc]="cho%02d"%hangul.CHO.index(ch)
    elif ch in hangul.JONG: COMPAT[cpc]="jong%02d"%hangul.JONG.index(ch)
vow="ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
for k,ch in enumerate(vow):
    COMPAT[0x314F+k]="jung%02d"%hangul.JUNG.index(ch)
for cpc,gid in COMPAT.items():
    name="uni%04X"%cpc
    glyphs[name]=make_comp([hangul.standalone_component(gid)]); hmtx[name]=(hangul.ADV,0)
    cmap[cpc]=name; order.append(name)

print(f"glyphs: total={len(glyphs)} syllables={nsyl} compat={len(COMPAT)}  ({time.time()-t0:.1f}s)")

# ---- assemble ----
fb=FontBuilder(UPM, isTTF=True)
fb.setupGlyphOrder(order)
fb.setupCharacterMap(cmap)
fb.setupGlyf(glyphs)
fb.setupHorizontalMetrics(hmtx)
fb.setupHorizontalHeader(ascent=ASC, descent=DESC, lineGap=120)
fb.setupNameTable({
  "familyName":FAMILY, "styleName":"Regular",
  "uniqueFontIdentifier":f"{FAMILY} {VERSION}",
  "fullName":f"{FAMILY} Regular", "version":f"Version {VERSION}",
  "psName":FAMILY.replace(" ","")+"-Regular",
  "manufacturer":"Built from handwriting via FontForge Korean font project",
})
fb.setupOS2(sTypoAscender=ASC, sTypoDescender=DESC, sTypoLineGap=120,
            usWinAscent=920, usWinDescent=300, sxHeight=X_H, sCapHeight=CAP_H,
            achVendID="HAND", fsType=0)
fb.setupPost(keepGlyphNames=False)   # post 3.0 -> smaller file
print("removeOverlaps on", len(simple), "simple glyphs...")
removeOverlaps(fb.font, glyphNames=simple)
fb.font['head'].fontRevision=float(VERSION)
out="SongilHandwriting-Regular.ttf"
fb.font.save(out)
print(f"SAVED {out}  ({time.time()-t0:.1f}s)")
import os; print("file size: %.2f MB"%(os.path.getsize(out)/1e6))
