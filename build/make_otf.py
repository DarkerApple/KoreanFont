"""Convert the built TTFs to CFF-flavoured OTFs (flatten composites, quad->cubic)."""
import time
from fontTools.ttLib import TTFont
from fontTools.fontBuilder import FontBuilder
from fontTools.pens.t2CharStringPen import T2CharStringPen

def to_otf(src, dst):
    t0=time.time()
    f=TTFont(src)
    gs=f.getGlyphSet()
    order=f.getGlyphOrder()
    upm=f['head'].unitsPerEm
    hmtx=f['hmtx']
    charstrings={}
    for name in order:
        pen=T2CharStringPen(hmtx[name][0], gs)
        gs[name].draw(pen)                      # composites flatten; quads -> cubics
        charstrings[name]=pen.getCharString()
    fam=f['name'].getDebugName(1); ps=f['name'].getDebugName(6)
    fb=FontBuilder(upm, isTTF=False)
    fb.setupGlyphOrder(order)
    fb.setupCharacterMap({cp:g for cp,g in f.getBestCmap().items()})
    fb.setupCFF(ps, {'FullName':f['name'].getDebugName(4),'FamilyName':fam,
                     'Weight':f['name'].getDebugName(2) or 'Regular'}, charstrings, {})
    fb.setupHorizontalMetrics({g:hmtx[g] for g in order})
    hh=f['hhea']
    fb.setupHorizontalHeader(ascent=hh.ascent, descent=hh.descent, lineGap=hh.lineGap)
    n=f['name']
    fb.setupNameTable({"familyName":fam,"styleName":f['name'].getDebugName(2) or "Regular",
        "uniqueFontIdentifier":n.getDebugName(3),"fullName":n.getDebugName(4),
        "version":n.getDebugName(5),"psName":ps,"manufacturer":"Built from handwriting"})
    o=f['OS/2']
    fb.setupOS2(sTypoAscender=o.sTypoAscender,sTypoDescender=o.sTypoDescender,
        sTypoLineGap=o.sTypoLineGap,usWinAscent=o.usWinAscent,usWinDescent=o.usWinDescent,
        sxHeight=o.sxHeight,sCapHeight=o.sCapHeight,achVendID=o.achVendID,fsType=o.fsType,
        usWeightClass=o.usWeightClass)
    fb.setupPost()
    fb.font['head'].fontRevision=f['head'].fontRevision
    import os
    if not os.environ.get("LH_NO_COMPRESS"):
        try:
            from compreffor import compress; compress(fb.font)   # CFF subroutinisation
        except Exception as e:
            print("  (compreffor skipped:",e,")")
    fb.font.save(dst)
    import os; print(f"{dst}: {len(order)} glyphs {os.path.getsize(dst)/1e6:.2f}MB {time.time()-t0:.1f}s")

import sys, os as _os
_targets=sys.argv[1:] or ["Lightheaded-Regular.ttf","Lightheaded-Latin-Regular.ttf"]
for _t in _targets:
    to_otf(_t, _t.replace(".ttf",".otf"))
