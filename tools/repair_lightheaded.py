#!/usr/bin/env python3
"""Repair the Lightheaded Regular Hangul font.

Two defects in the source font, both fixed here:

1. 25 open syllables (no jongseong) built on the ㅗ / ㅛ vowel were assembled
   with the *tall* variant of the lead consonant stacked on top of a vowel that
   had been pushed roughly 100 units below the baseline.  The result was a glyph
   ~1030 units tall — taller than the em — that sat too low, collided with the
   line below and got clipped by any tight line box.  ㅜ / ㅠ syllables (the same
   consonant-over-vowel structure) already used a *flat* lead variant sitting at
   y=382 over a vowel at y=-23, so those components are reused verbatim.  Pure
   component substitution + translation: no outline is scaled or distorted.

2. The figures were tabular at 681 units while their ink ranged from 255 (one)
   to 581 (four), so numbers read as a scatter of loose, unevenly spaced digits.
   They become proportional with side bearings matched to the Latin lowercase
   (~21% tighter on average), and a tabular set is kept behind the `tnum`
   OpenType feature for anyone who needs figures to line up in columns.

Usage:  python3 tools/repair_lightheaded.py <source.ttf> <output.ttf>
Requires: fonttools (plus brotli if you also want the .woff2)
"""

import copy
import sys

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont

# Hangul syllable index: cp = 0xAC00 + lead*588 + vowel*28 + tail
SYLLABLE_BASE = 0xAC00
V_O, V_YO, V_U, V_YU = 8, 12, 13, 17  # ㅗ ㅛ ㅜ ㅠ
LEAD_COUNT = 19

# a syllable whose ink starts below this is one of the broken ones; healthy
# syllables bottom out around -20
BROKEN_BELOW = -60

DIGITS = "zero one two three four five six seven eight nine".split()

# Side bearings for the proportional figures, tuned against the Latin lowercase
# (o = 44/34, n = 55/47, H = 50/61).  Round-sided figures get a little less air
# than flat-sided ones; `one` keeps extra room so a lone stem is not swallowed
# by its neighbours.
FIGURE_SIDE_BEARINGS = {
    "zero": 40, "one": 78, "two": 46, "three": 42, "four": 38,
    "five": 46, "six": 40, "seven": 44, "eight": 38, "nine": 40,
}

TABULAR_SIDE_BEARING = 30  # air around the widest figure in the tabular set

VERSION = "Version 1.100"
FONT_REVISION = 1.1


def main(src, dst):
    font = TTFont(src, recalcTimestamp=False)  # keep the build reproducible
    glyf, hmtx = font["glyf"], font["hmtx"]

    cache = {}

    def bounds(name, fresh=False):
        """Ink bbox of a glyph, or None if it is blank.  Memoised: resolving a
        composite's bounds walks its components, and this font has 11k of them."""
        if fresh:
            cache.pop(name, None)
        if name not in cache:
            glyph = glyf[name]
            if glyph.numberOfContours == 0:
                cache[name] = None
            else:
                glyph.recalcBounds(glyf)
                cache[name] = (glyph.xMin, glyph.yMin, glyph.xMax, glyph.yMax)
        return cache[name]

    repair_hangul(font, glyf, bounds)
    respace_figures(font, glyf, hmtx, bounds)
    recompute_metrics(font, glyf, hmtx, bounds)
    stamp_version(font)

    font.save(dst)
    print(f"\nwrote {dst}")


# ---------------------------------------------------------------- 1. Hangul
def repair_hangul(font, glyf, bounds):
    cmap = font.getBestCmap()

    def syllable(lead, vowel, tail=0):
        return SYLLABLE_BASE + lead * 588 + vowel * 28 + tail

    repaired = []
    for vowel, reference_vowel in ((V_O, V_U), (V_YO, V_YU)):
        for lead in range(LEAD_COUNT):
            cp = syllable(lead, vowel)
            name = cmap[cp]
            if bounds(name)[1] >= BROKEN_BELOW:
                continue  # already sits on the baseline, leave it alone
            before = bounds(name)

            glyph = glyf[name]
            reference = glyf[cmap[syllable(lead, reference_vowel)]]

            # take the lead consonant from the ㅜ / ㅠ sibling: same lead, same
            # x-extent, but the flat variant that leaves room for a vowel below
            source, target = reference.components[0], glyph.components[0]
            target.glyphName = source.glyphName
            target.transform = copy.deepcopy(source.transform)
            target.x, target.y = source.x, source.y

            # and lift ㅗ / ㅛ back onto the baseline, where ㅜ / ㅠ already sits
            glyph.components[1].y = reference.components[1].y

            repaired.append((chr(cp), before, bounds(name, fresh=True)))

    print(f"repaired {len(repaired)} Hangul syllables")
    for ch, before, after in repaired:
        print(f"  {ch}  y {before[1]:5}..{before[3]:4}  ->  {after[1]:5}..{after[3]:4}")


# ---------------------------------------------------------------- 2. figures
def respace_figures(font, glyf, hmtx, bounds):
    def set_side_bearings(name, left, right):
        """Shift the outline until its lsb is `left`, then set the advance."""
        shift = left - bounds(name, fresh=True)[0]
        glyph = glyf[name]
        if shift:
            coords, _, _ = glyph.getCoordinates(glyf)
            for i in range(len(coords)):
                coords[i] = (coords[i][0] + shift, coords[i][1])
            glyph.coordinates = coords
            glyph.recalcBounds(glyf)
            bounds(name, fresh=True)
        ink = glyph.xMax - glyph.xMin
        hmtx[name] = (left + ink + right, left)
        return hmtx[name][0]

    print("\nfigures")
    was = hmtx["zero"][0]
    advances = {}
    for name in DIGITS:
        sb = FIGURE_SIDE_BEARINGS[name]
        advances[name] = set_side_bearings(name, sb, sb)
        print(f"  {name:6} {was} -> {advances[name]}   (side bearings {sb}/{sb})")
    mean = sum(advances.values()) / len(advances)
    print(f"  mean advance {was} -> {mean:.0f}  ({100 - 100 * mean / was:.0f}% tighter)")

    # tabular alternates for `tnum`: one shared width, every figure centred in it
    tabular_width = max(bounds(n)[2] - bounds(n)[0] for n in DIGITS) + 2 * TABULAR_SIDE_BEARING
    order = list(font.getGlyphOrder())
    for name in DIGITS:
        alt = name + ".tnum"
        glyf[alt] = copy.deepcopy(glyf[name])
        order.append(alt)
        hmtx.metrics[alt] = (tabular_width, 0)
        ink = bounds(name)[2] - bounds(name)[0]
        lsb = round((tabular_width - ink) / 2)
        set_side_bearings(alt, lsb, tabular_width - ink - lsb)
    font.setGlyphOrder(order)
    glyf.glyphOrder = order
    glyf.glyphs = {name: glyf.glyphs[name] for name in order}
    font["maxp"].numGlyphs = len(order)
    print(f"  tabular set (tnum): width {tabular_width}")

    addOpenTypeFeaturesFromString(font, "feature tnum {\n%s\n} tnum;\n" % "\n".join(
        f"    sub {name} by {name}.tnum;" for name in DIGITS))


# ---------------------------------------------------------------- 3. metrics
def recompute_metrics(font, glyf, hmtx, bounds):
    head, hhea, os2 = font["head"], font["hhea"], font["OS/2"]

    all_bounds = {name: bounds(name) for name in font.getGlyphOrder()}
    xs = [v for b in all_bounds.values() if b for v in (b[0], b[2])]
    ys = [v for b in all_bounds.values() if b for v in (b[1], b[3])]
    head.xMin, head.yMin, head.xMax, head.yMax = min(xs), min(ys), max(xs), max(ys)

    # vertical metrics only need to clear the glyphs that are actually reachable
    # through cmap; the un-encoded stroke library is only ever drawn scaled down
    # inside composites
    reachable = [all_bounds[name] for name in set(font.getBestCmap().values())]
    reachable_ys = [v for b in reachable if b for v in (b[1], b[3])]
    print(f"\nreachable ink: y {min(reachable_ys)}..{max(reachable_ys)}")

    os2.usWinAscent = max(max(reachable_ys), os2.sTypoAscender)
    os2.usWinDescent = -min(min(reachable_ys), os2.sTypoDescender)
    hhea.ascent, hhea.descent = os2.sTypoAscender, os2.sTypoDescender
    hhea.lineGap = os2.sTypoLineGap
    hhea.advanceWidthMax = max(hmtx[name][0] for name in font.getGlyphOrder())
    hhea.minLeftSideBearing = min(b[0] for b in all_bounds.values() if b)
    hhea.minRightSideBearing = min(hmtx[n][0] - b[2] for n, b in all_bounds.items() if b)
    hhea.xMaxExtent = max(b[2] for b in all_bounds.values() if b)

    codepoints = font.getBestCmap()
    os2.usFirstCharIndex = min(codepoints)
    os2.usLastCharIndex = min(0xFFFF, max(codepoints))


# ---------------------------------------------------------------- 4. version
def stamp_version(font):
    name = font["name"]
    for name_id, value in ((3, "Lightheaded-Regular-1.100"), (5, VERSION)):
        name.setName(value, name_id, 3, 1, 0x409)
        name.setName(value, name_id, 1, 0, 0)
    font["head"].fontRevision = FONT_REVISION


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
