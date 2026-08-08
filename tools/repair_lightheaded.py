#!/usr/bin/env python3
"""Repair and regularise the Lightheaded Regular Hangul font.

Every syllable in this font is a composite assembled from a library of ~520
un-encoded hand-drawn strokes, each placed with its own 2x2 transform.  That
makes the font very cheap to fix — almost everything below is a change to a
component's transform or offset, not to an outline — but it also means small
inconsistencies in the assembly show up as visible defects.  Six passes:

1. ㅗ / ㅛ open syllables (25 glyphs) were assembled with the *tall* variant of
   the lead consonant stacked over a vowel pushed ~100 units below the baseline.
   The result was ~1030 units tall — taller than the em — and hung below the
   line.  ㅜ / ㅠ syllables have the same consonant-over-vowel structure and
   already used a *flat* lead variant at y=382 over a vowel at y=-23, so those
   components are reused verbatim.  No outline is scaled or distorted.

2. The ieung (ㅇ) was drawn from nine different masters whose aspect ratios ran
   from 0.86 to 1.95, then scaled non-uniformly on top of that, so the rendered
   ㅇ ranged from a 396x616 upright egg (아) to a 784x455 pancake (오) to a
   627x296 sliver (강) — its size and shape changed with whatever followed it.
   All 987 of them are rebuilt from one master at one aspect ratio (1.15) and a
   near-constant size, placed against the stroke below and centred properly.
   Gowun Dodum, the closest reference, holds its ㅇ between 419x338 and 448x432.

3. Standalone compatibility jamo were normalised to a fixed *width*, which left
   ㅗ ㅛ ㅜ ㅠ ㅡ at ~290 units tall with strokes 24% thinner than the same
   stroke inside a syllable — next to a 690-unit ㄱ they read as hairlines.
   Vowels are rescaled to the size they get inside a syllable.

4. Syllables were 960 units wide around 780 units of ink (81%), against Gowun
   Dodum's 87% and Jua's 91%, and their ink sat 9.5 units right of centre in
   every single glyph.  Advance drops to 900 and the ink is recentred.

5. The figures were tabular at 681 units while their ink ranged from 255 (one)
   to 581 (four).  They become proportional with side bearings matched to the
   Latin lowercase (~21% tighter), with a tabular set behind a new `tnum`
   feature.  The currency symbols ₩ € ¥ had advances *narrower* than their own
   ink — € by 130 units — so they collided with whatever came next.

6. Vertical metrics, the head bounding box and hhea side bearings are recomputed
   from the repaired outlines.

Usage:  python3 tools/repair_lightheaded.py <source.ttf> <output.ttf>
Requires: fonttools (plus brotli if you also want the .woff2)
"""

import copy
import math
import statistics
import sys

from fontTools.feaLib.builder import addOpenTypeFeaturesFromString
from fontTools.ttLib import TTFont
from fontTools.ttLib.tables._g_l_y_f import Glyph

# Hangul syllable index: cp = 0xAC00 + lead*588 + vowel*28 + tail
SYLLABLE_BASE = 0xAC00
SYLLABLE_END = 0xD7A4
LEAD_COUNT = 19
V_O, V_YO, V_U, V_YU = 8, 12, 13, 17  # ㅗ ㅛ ㅜ ㅠ
IEUNG_LEAD, IEUNG_TAIL = 11, 21

# a syllable whose ink starts below this is one of the broken ㅗ/ㅛ ones;
# healthy syllables bottom out around -20
BROKEN_BELOW = -60

# --- ieung -----------------------------------------------------------------
# glyph00277 is the roundest of the nine hand-drawn ieung masters (1120x1002,
# ar 1.12).  Its ring is thin for the size we now draw it at, so the inner
# contour is pulled in slightly: that thickens the stroke without touching the
# outline's hand-drawn character.
IEUNG_BASE = "glyph00277"
IEUNG_MASTER = "ieung.norm"
IEUNG_RING_TIGHTEN = 0.927
IEUNG_AR = 1.15          # Gowun Dodum's ieung sits between 1.04 and 1.29
IEUNG_H_LEAD = 400
IEUNG_H_TAIL = 350
IEUNG_GAP_LEAD = 38      # smallest gap left to the stroke underneath
IEUNG_GAP_TAIL = 26
IEUNG_TAIL_OVERSHOOT = -45   # a round shape needs to drop below the baseline
IEUNG_BAND_WIDTH = 600       # wider than this and the ㅇ spans the whole syllable

# --- standalone compatibility jamo -----------------------------------------
JAMO_MAX_WIDTH = 740     # what a horizontal vowel measures inside a syllable
JAMO_MAX_HEIGHT = 861    # what a vertical vowel measures inside a syllable
JAMO_VOWELS = range(0x314F, 0x3164)

# --- Hangul advance --------------------------------------------------------
HANGUL_ADVANCE = 900     # Gowun Dodum 900, Jua 821; was 960 around 780 of ink

# --- figures ---------------------------------------------------------------
DIGITS = "zero one two three four five six seven eight nine".split()

# Side bearings for the proportional figures, tuned against the Latin lowercase
# (o = 44/34, n = 55/47, H = 50/61).  Round-sided figures get a little less air
# than flat-sided ones; `one` keeps extra room so a lone stem is not swallowed
# by its neighbours.
FIGURE_SIDE_BEARINGS = {
    "zero": 40, "one": 78, "two": 46, "three": 42, "four": 38,
    "five": 46, "six": 40, "seven": 44, "eight": 38, "nine": 40,
}
TABULAR_SIDE_BEARING = 30   # air around the widest figure in the tabular set
CURRENCY_SIDE_BEARING = 45  # ₩ € ¥ — advances that actually contain the ink
CURRENCY = {0x20A9: "won", 0x20AC: "Euro", 0x00A5: "yen"}

# --- stroke weight ---------------------------------------------------------
# Every stroke master is drawn at its own size and then scaled to fit, so the
# pen that reaches the page ranges from 48 to 112 units depending on which
# stroke you are looking at.  Each master is offset along its own normals until
# it renders at one weight.  68 is the font's own median, so most masters barely
# move (median correction: 9% of the master's pen).
PEN_TARGET = 75          # the font's own usage-weighted median
PEN_FLATTEN_STEPS = 6      # curve subdivision when measuring
PEN_SCANLINES = 80
PEN_MIN_COUNTER = 26       # white left between two strokes of the same jamo
PEN_MAX_CHANGE = 0.28      # never move a stroke more than this much of its pen
PEN_PASSES = 2             # offsetting changes the measurement, so measure again

# --- gaps between the jamo of a syllable -----------------------------------
# The white between the lead consonant and a vertical vowel runs from 20 units
# (ㅔ) to 147 (ㅣ), because the vowel's own width varies while the syllable's
# edges do not.  Even it out, but gently: the syllable's outer margins are
# currently far more consistent than either reference font's and are worth
# keeping.
GAP_TARGET = 75
GAP_MAX_SHIFT = 30         # total change to any one syllable's interior gap

VERSION = "Version 2.100"
FONT_REVISION = 2.1


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

    def component_box(comp):
        """Where a component's ink actually lands in the composite."""
        sub = glyf[comp.glyphName]
        sub.recalcBounds(glyf)
        sx, sy = comp.transform[0][0], comp.transform[1][1]
        x0 = comp.x + sub.xMin * sx
        y0 = comp.y + sub.yMin * sy
        return (x0, y0, x0 + (sub.xMax - sub.xMin) * sx, y0 + (sub.yMax - sub.yMin) * sy)

    repair_vertical_vowel_syllables(font, glyf, bounds)
    normalise_ieung(font, glyf, hmtx, component_box)
    normalise_stroke_weight(font, glyf)
    even_out_jamo_gaps(font, glyf, component_box)
    rescale_compat_jamo(font, glyf, bounds, component_box)
    respace_hangul(font, glyf, hmtx, bounds)
    respace_figures(font, glyf, hmtx, bounds)
    recompute_metrics(font, glyf, hmtx, bounds)
    stamp_version(font)

    font.save(dst)
    print(f"\nwrote {dst}")


def syllable(lead, vowel, tail=0):
    return SYLLABLE_BASE + lead * 588 + vowel * 28 + tail


def decompose(cp):
    i = cp - SYLLABLE_BASE
    return i // 588, (i % 588) // 28, i % 28


# --------------------------------------------------- 1. ㅗ / ㅛ open syllables
def repair_vertical_vowel_syllables(font, glyf, bounds):
    cmap = font.getBestCmap()
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

    print(f"1. repaired {len(repaired)} ㅗ/ㅛ syllables")
    for ch, before, after in repaired:
        print(f"     {ch}  y {before[1]:5}..{before[3]:4}  ->  {after[1]:5}..{after[3]:4}")


# --------------------------------------------------------------- 2. the ieung
def build_ieung_master(font, glyf, hmtx):
    """One round ieung with a stroke heavy enough for the size we draw it at."""
    src = glyf[IEUNG_BASE]
    coords, end_points, flags = src.getCoordinates(glyf)
    contours, start = [], 0
    for end in end_points:
        contours.append(range(start, end + 1))
        start = end + 1
    area = [(max(coords[i][0] for i in c) - min(coords[i][0] for i in c)) *
            (max(coords[i][1] for i in c) - min(coords[i][1] for i in c)) for c in contours]
    inner = contours[area.index(min(area))]
    cx = sum(coords[i][0] for i in inner) / len(inner)
    cy = sum(coords[i][1] for i in inner) / len(inner)

    moved = list(coords)
    for i in inner:
        moved[i] = (round(cx + (coords[i][0] - cx) * IEUNG_RING_TIGHTEN),
                    round(cy + (coords[i][1] - cy) * IEUNG_RING_TIGHTEN))

    glyph = Glyph()
    glyph.numberOfContours = len(end_points)
    glyph.endPtsOfContours = list(end_points)
    glyph.coordinates = type(coords)(moved)
    glyph.flags = flags
    glyph.program = src.program
    glyf[IEUNG_MASTER] = glyph

    order = list(dict.fromkeys(list(font.getGlyphOrder()) + [IEUNG_MASTER]))
    font.setGlyphOrder(order)
    glyf.glyphOrder = order
    glyf.glyphs = {n: glyf.glyphs[n] for n in order}
    hmtx.metrics[IEUNG_MASTER] = hmtx[IEUNG_BASE]
    font["maxp"].numGlyphs = len(order)

    glyph.recalcBounds(glyf)
    return glyph.xMax - glyph.xMin, glyph.yMax - glyph.yMin, glyph.xMin, glyph.yMin


def normalise_ieung(font, glyf, hmtx, component_box):
    mw, mh, mx, my = build_ieung_master(font, glyf, hmtx)
    cmap = font.getBestCmap()

    def place(comp, w, h, left, bottom):
        sx, sy = w / mw, h / mh
        comp.glyphName = IEUNG_MASTER
        comp.transform = [[sx, 0.0], [0.0, sy]]
        comp.x = round(left - mx * sx)
        comp.y = round(bottom - my * sy)

    sizes = {"lead": [], "tail": []}
    for cp in range(SYLLABLE_BASE, SYLLABLE_END):
        lead, _, tail = decompose(cp)
        parts = glyf[cmap[cp]].components
        roles = ([("lead", 0)] if lead == IEUNG_LEAD else []) + \
                ([("tail", len(parts) - 1)] if tail == IEUNG_TAIL else [])
        for role, index in roles:
            me = parts[index]
            box = component_box(me)
            others = [component_box(c) for k, c in enumerate(parts) if k != index]
            # a ㅇ that spans the syllable belongs over the middle of everything
            # else in it, not over wherever its own old ellipse happened to sit
            centre = (min(o[0] for o in others) + max(o[2] for o in others)) / 2

            if role == "lead":
                # never grow down into the stroke below
                under = [o[3] for o in others if o[3] < box[3] - 50]
                height = IEUNG_H_LEAD
                if under:
                    height = min(height, box[3] - (max(under) + IEUNG_GAP_LEAD))
                width = height * IEUNG_AR
                # nor sideways into a vowel standing to its right.  Never reach
                # further right than the ㅇ already did, so no overlap that the
                # design already tolerates can get worse.
                beside = [o[0] for o in others
                          if o[0] > (box[0] + box[2]) / 2 and o[3] > box[1] and o[1] < box[3]]
                if beside:
                    anchor = box[0]          # a ㅇ in the left column keeps its margin
                    limit = max(box[2], min(beside) - IEUNG_GAP_LEAD)
                    width = min(width, limit - anchor)
                    height = min(height, width / IEUNG_AR)
                    width = height * IEUNG_AR
                    left = anchor
                else:
                    left = centre - width / 2
                place(me, width, height, left, box[3] - height)
            else:
                bottom = min(box[1], IEUNG_TAIL_OVERSHOOT)
                height = min(IEUNG_H_TAIL, min(o[1] for o in others) - IEUNG_GAP_TAIL - bottom)
                width = height * IEUNG_AR
                place(me, width, height, centre - width / 2, bottom)
            sizes[role].append((width, height))

    for role, values in sizes.items():
        widths = sorted(w for w, _ in values)
        heights = sorted(h for _, h in values)
        n = len(values)
        print(f"2. ieung {role:4} n={n:4}  {widths[n // 2]:.0f} x {heights[n // 2]:.0f}"
              f"   (height {heights[0]:.0f}..{heights[-1]:.0f})")



# ------------------------------------------------------- 2b. stroke weight
def _flatten(pen_value, steps):
    """Recorded pen output -> polygons, so we can take scanline measurements."""
    polys, cur, last = [], [], None
    for op, args in pen_value:
        if op == "moveTo":
            cur = [args[0]]; last = args[0]
        elif op == "lineTo":
            cur.append(args[0]); last = args[0]
        elif op == "qCurveTo":
            points = list(args); on, offs, prev = points[-1], points[:-1], last
            for i, c in enumerate(offs):
                nxt = ((c[0] + offs[i + 1][0]) / 2, (c[1] + offs[i + 1][1]) / 2) \
                    if i + 1 < len(offs) else on
                for step in range(1, steps + 1):
                    t = step / steps
                    cur.append(((1 - t) ** 2 * prev[0] + 2 * (1 - t) * t * c[0] + t * t * nxt[0],
                                (1 - t) ** 2 * prev[1] + 2 * (1 - t) * t * c[1] + t * t * nxt[1]))
                prev = nxt
            last = on
        elif op == "curveTo":
            p0, (p1, p2, p3) = last, args
            for step in range(1, steps + 1):
                t = step / steps
                cur.append(((1 - t) ** 3 * p0[0] + 3 * (1 - t) ** 2 * t * p1[0]
                            + 3 * (1 - t) * t * t * p2[0] + t ** 3 * p3[0],
                            (1 - t) ** 3 * p0[1] + 3 * (1 - t) ** 2 * t * p1[1]
                            + 3 * (1 - t) * t * t * p2[1] + t ** 3 * p3[1]))
            last = p3
        elif op in ("closePath", "endPath"):
            if len(cur) > 2:
                polys.append(cur)
            cur = []
    if len(cur) > 2:
        polys.append(cur)
    return polys


def _ink_runs(polys, axis, count, white=None):
    """Lengths of the ink crossings along `count` scanlines."""
    values = [p[axis ^ 1] for poly in polys for p in poly]
    lo, hi = min(values), max(values)
    if hi - lo < 2:
        return []
    out = []
    for i in range(1, count):
        line = lo + (hi - lo) * i / count
        crossings = []
        for poly in polys:
            n = len(poly)
            for j in range(n):
                a, b = poly[j], poly[(j + 1) % n]
                a_on, b_on = a[axis ^ 1], b[axis ^ 1]
                if (a_on <= line < b_on) or (b_on <= line < a_on):
                    t = (line - a_on) / (b_on - a_on)
                    crossings.append(a[axis] + t * (b[axis] - a[axis]))
        crossings.sort()
        out += [crossings[k + 1] - crossings[k] for k in range(0, len(crossings) - 1, 2)
                if crossings[k + 1] - crossings[k] > 1]
        if white is not None:
            white += [crossings[k + 2] - crossings[k + 1] for k in range(0, len(crossings) - 2, 2)
                      if crossings[k + 2] - crossings[k + 1] > 1]
    return out


def measure_pen(glyph_set, name):
    """The master's typical stroke thickness, and the narrowest white gap inside
    it — thicken a ㅌ past that and its three bars merge into a block."""
    from fontTools.pens.recordingPen import RecordingPen
    pen = RecordingPen()
    glyph_set[name].draw(pen)
    polys = _flatten(pen.value, PEN_FLATTEN_STEPS)
    if not polys:
        return None, None
    white = []
    runs = sorted(_ink_runs(polys, 0, PEN_SCANLINES, white)
                  + _ink_runs(polys, 1, PEN_SCANLINES, white))
    if len(runs) < 8:
        return None, None
    white.sort()
    gap = white[len(white) // 20] if len(white) >= 20 else (white[0] if white else None)
    # a low percentile finds the thinnest stroke; take the median of everything
    # near it so a ㅌ is judged by its bars, not by its one thin stem, and a long
    # stem still contributes its width rather than its length
    thin = runs[len(runs) // 5]
    band = [r for r in runs if 0.5 * thin <= r <= 2.5 * thin]
    return statistics.median(band), gap


def _signed_area(ring):
    total = 0.0
    for i in range(len(ring)):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % len(ring)]
        total += x0 * y1 - x1 * y0
    return total / 2


def offset_outline(glyph, delta):
    """Push every point away from the ink by `delta`, thickening the stroke.
    Winding decides which way is out, so counters close as the stroke grows."""
    coords, end_points, _ = glyph.getCoordinates(None)
    points = list(coords)
    start = 0
    for end in end_points:
        index = list(range(start, end + 1))
        start = end + 1
        ring = [points[i] for i in index]
        if len(ring) < 3:
            continue
        direction = 1.0 if _signed_area(ring) < 0 else -1.0
        n = len(ring)
        for k, i in enumerate(index):
            before, after = ring[(k - 1) % n], ring[(k + 1) % n]
            tx, ty = after[0] - before[0], after[1] - before[1]
            length = math.hypot(tx, ty)
            if length < 1e-6:
                continue
            points[i] = (points[i][0] - ty / length * direction * delta,
                         points[i][1] + tx / length * direction * delta)
    glyph.coordinates = type(coords)([(round(x), round(y)) for x, y in points])


def normalise_stroke_weight(font, glyf):
    glyph_set = font.getGlyphSet()

    # what scale does each master actually reach the page at?
    scales = {}
    for name in font.getGlyphOrder():
        glyph = glyf[name]
        if glyph.numberOfContours != -1:
            continue
        for comp in glyph.components:
            sx, sy = comp.transform[0][0], comp.transform[1][1]
            scales.setdefault(comp.glyphName, []).append((sx + sy) / 2)

    first, moved = None, set()
    for _ in range(PEN_PASSES):
        rendered = []
        for name, used in scales.items():
            glyph = glyf[name]
            if glyph.numberOfContours <= 0:
                continue
            pen, counter = measure_pen(glyph_set, name)
            if not pen:
                continue
            scale = statistics.median(used)
            rendered.append(pen * scale)
            delta = (PEN_TARGET / scale - pen) / 2
            limit = PEN_MAX_CHANGE * pen / 2
            if counter is not None:
                # leave enough white that neighbouring strokes stay apart
                limit = min(limit, max(0.0, (counter - PEN_MIN_COUNTER / scale) / 2))
            delta = max(-limit, min(limit, delta))
            if abs(delta) < 1:
                continue
            offset_outline(glyph, delta)
            glyph.recalcBounds(glyf)
            moved.add(name)
        if first is None:
            first = rendered
        last = rendered

    def spread(values):
        return statistics.pstdev(values) / statistics.median(values)
    print(f"2b. stroke weight: {len(moved)} masters offset to a {PEN_TARGET}-unit pen"
          f"   ({min(first):.0f}..{max(first):.0f} -> {min(last):.0f}..{max(last):.0f},"
          f" spread {spread(first):.3f} -> {spread(last):.3f})")


# ------------------------------------------------------ 2c. jamo gaps
def even_out_jamo_gaps(font, glyf, component_box):
    """Pull the white between a lead consonant and a vertical vowel toward one
    value by moving the two apart or together, half from each side so the
    syllable stays centred."""
    cmap = font.getBestCmap()
    vowels = "ㅏㅐㅑㅒㅓㅔㅕㅖㅗㅘㅙㅚㅛㅜㅝㅞㅟㅠㅡㅢㅣ"
    simple = set("ㅏㅐㅑㅒㅓㅔㅕㅖㅣ")
    before, after, touched = [], [], 0
    for cp in range(SYLLABLE_BASE, SYLLABLE_END):
        _, vowel_index, _ = decompose(cp)
        if vowels[vowel_index] not in simple:
            continue
        parts = glyf[cmap[cp]].components
        lead, vowel = parts[0], parts[1]
        gap = component_box(vowel)[0] - component_box(lead)[2]
        before.append(gap)
        shift = max(-GAP_MAX_SHIFT, min(GAP_MAX_SHIFT, GAP_TARGET - gap))
        if abs(shift) >= 2:
            lead.x -= round(shift / 2)
            vowel.x += shift - round(shift / 2)
            touched += 1
        after.append(gap + shift)
    print(f"2c. jamo gaps: {touched} syllables nudged   "
          f"median {statistics.median(before):.0f} -> {statistics.median(after):.0f}, "
          f"sigma {statistics.pstdev(before):.0f} -> {statistics.pstdev(after):.0f}")

# ------------------------------------------------- 3. standalone compat jamo
def rescale_compat_jamo(font, glyf, bounds, component_box):
    """The vowels were normalised to a fixed width, which left the horizontal
    ones tiny and thin.  Rescale them to the size they get inside a syllable."""
    cmap = font.getBestCmap()
    changed = []
    for cp in JAMO_VOWELS:
        name = cmap.get(cp)
        if not name:
            continue
        glyph = glyf[name]
        if glyph.numberOfContours != -1 or len(glyph.components) != 1:
            continue
        comp = glyph.components[0]
        x0, y0, x1, y1 = component_box(comp)
        factor = min(JAMO_MAX_WIDTH / (x1 - x0), JAMO_MAX_HEIGHT / (y1 - y0))
        if abs(factor - 1) < 0.01:
            continue
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        sub = glyf[comp.glyphName]
        sub.recalcBounds(glyf)
        sx = comp.transform[0][0] * factor
        sy = comp.transform[1][1] * factor
        comp.transform = [[sx, comp.transform[0][1] * factor],
                          [comp.transform[1][0] * factor, sy]]
        comp.x = round(cx - (x1 - x0) * factor / 2 - sub.xMin * sx)
        comp.y = round(cy - (y1 - y0) * factor / 2 - sub.yMin * sy)
        changed.append((chr(cp), round(x1 - x0), round(y1 - y0), factor))
    print(f"3. rescaled {len(changed)} standalone jamo vowels "
          f"(x{min(c[3] for c in changed):.2f}..{max(c[3] for c in changed):.2f})")


# ----------------------------------------------- 4. Hangul advance & centring
def respace_hangul(font, glyf, hmtx, bounds):
    cmap = font.getBestCmap()
    targets = [cp for cp in range(SYLLABLE_BASE, SYLLABLE_END) if cp in cmap]
    targets += [cp for cp in range(0x3131, 0x3164) if cp in cmap]
    names = list(dict.fromkeys(cmap[cp] for cp in targets))

    centres = sorted(sum(bounds(n)[0::2]) / 2 for n in names if bounds(n))
    old_advance = hmtx[names[0]][0]
    # one uniform shift keeps the font's very tight per-glyph consistency
    # (sigma 3.3 units) instead of recentring each glyph on its own ink
    shift = round(HANGUL_ADVANCE / 2 - centres[len(centres) // 2])

    for name in names:
        glyph = glyf[name]
        if glyph.numberOfContours == -1:
            for comp in glyph.components:
                comp.x += shift
        else:
            coords, _, _ = glyph.getCoordinates(glyf)
            for i in range(len(coords)):
                coords[i] = (coords[i][0] + shift, coords[i][1])
            glyph.coordinates = coords
        glyph.recalcBounds(glyf)
        bounds(name, fresh=True)
        hmtx[name] = (HANGUL_ADVANCE, glyph.xMin)

    edges = [(bounds(n)[0], HANGUL_ADVANCE - bounds(n)[2]) for n in names if bounds(n)]
    print(f"4. Hangul advance {old_advance} -> {HANGUL_ADVANCE}, ink shifted {shift:+}"
          f"   ({len(names)} glyphs, tightest side bearing {min(min(e) for e in edges)})")


# --------------------------------------------------------------- 5. figures
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

    was = hmtx["zero"][0]
    advances = {}
    for name in DIGITS:
        sb = FIGURE_SIDE_BEARINGS[name]
        advances[name] = set_side_bearings(name, sb, sb)
    mean = sum(advances.values()) / len(advances)
    print(f"5. figures {was} -> mean {mean:.0f}  ({100 - 100 * mean / was:.0f}% tighter)")

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
    order = list(dict.fromkeys(order))
    font.setGlyphOrder(order)
    glyf.glyphOrder = order
    glyf.glyphs = {name: glyf.glyphs[name] for name in order}
    font["maxp"].numGlyphs = len(order)
    print(f"   tabular set (tnum): width {tabular_width}")

    addOpenTypeFeaturesFromString(font, "feature tnum {\n%s\n} tnum;\n" % "\n".join(
        f"    sub {name} by {name}.tnum;" for name in DIGITS))

    cmap = font.getBestCmap()
    for cp, label in CURRENCY.items():
        name = cmap.get(cp)
        if not name:
            continue
        before = hmtx[name][0]
        after = set_side_bearings(name, CURRENCY_SIDE_BEARING, CURRENCY_SIDE_BEARING)
        print(f"   {chr(cp)} advance {before} -> {after}  "
              f"(ink was overflowing by {bounds(name)[2] - before + CURRENCY_SIDE_BEARING})")


# --------------------------------------------------------------- 6. metrics
def recompute_metrics(font, glyf, hmtx, bounds):
    head, hhea, os2 = font["head"], font["hhea"], font["OS/2"]

    all_bounds = {name: bounds(name, fresh=True) for name in font.getGlyphOrder()}
    xs = [v for b in all_bounds.values() if b for v in (b[0], b[2])]
    ys = [v for b in all_bounds.values() if b for v in (b[1], b[3])]
    head.xMin, head.yMin, head.xMax, head.yMax = min(xs), min(ys), max(xs), max(ys)

    # vertical metrics only need to clear the glyphs that are actually reachable
    # through cmap; the un-encoded stroke library is only ever drawn scaled down
    # inside composites
    reachable = [all_bounds[name] for name in set(font.getBestCmap().values())]
    reachable_ys = [v for b in reachable if b for v in (b[1], b[3])]

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
    print(f"6. reachable ink y {min(reachable_ys)}..{max(reachable_ys)}  "
          f"winAscent {os2.usWinAscent} winDescent {os2.usWinDescent}")


def stamp_version(font):
    name = font["name"]
    for name_id, value in ((3, "Lightheaded-Regular-2.000"), (5, VERSION)):
        name.setName(value, name_id, 3, 1, 0x409)
        name.setName(value, name_id, 1, 0, 0)
    font["head"].fontRevision = FONT_REVISION


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
