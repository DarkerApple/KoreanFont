# Lightheaded — 손글씨 폰트

A light, even-weight **handwriting font built from hand-drawn worksheets** —
Korean (한글), Latin, digits and symbols — generated automatically from a
tablet-drawn glyph worksheet (`build/raw/LightheadedRAW.pdf`).

| Download | Coverage | Format |
|---|---|---|
| **[`Lightheaded-Regular.ttf`](Lightheaded-Regular.ttf)** | Korean + Latin + symbols | TrueType (recommended, ≈1.1 MB) |
| **[`Lightheaded-Regular.otf`](Lightheaded-Regular.otf)** | Korean + Latin + symbols | OpenType/CFF (≈29 MB — CFF can't share composed syllables; prefer the TTF) |
| **[`Lightheaded-Latin-Regular.ttf`](Lightheaded-Latin-Regular.ttf)** | Latin + symbols only | TrueType (≈0.02 MB) |
| **[`Lightheaded-Latin-Regular.otf`](Lightheaded-Latin-Regular.otf)** | Latin + symbols only | OpenType/CFF |

![paragraph sample](samples/paragraph.png)

## What's in the full font

| Coverage | Count | Notes |
|---|---|---|
| Hangul syllables | **11,172** | every modern syllable U+AC00–U+D7A3, composed from your jamo |
| Compatibility jamo | 51 | standalone ㄱ–ㅎ, ㅏ–ㅣ (U+3131–U+3163) |
| Latin | A–Z, a–z | consistent cap-height / x-height, even spacing |
| Digits & symbols | 0–9 + full ASCII | `! @ # $ % ^ & * ( ) … ~` (`$ ^ \` |` synthesised to match) |
| Typography | — | en/em dash, ellipsis, middle dot, curly quotes, ₩ won |
| **Total glyphs** | **11,812** | UPM 1000, `fsType` 0 (embeddable) |

Only **67 jamo + 88 ASCII glyphs were hand-drawn**; the 11,172 syllables are
assembled from the jamo by an automatic composition engine (6 layout types,
position-aware finals), so Korean is fully typeable.

The **Latin version** has the same 117 outlines but no Hangul — use it when
you only need English/symbols, or want a tiny file.

## Consistency & weight

The font is tuned for an even, *lightheaded* look:

- **Stroke weight** matched at ~80 em across Korean and Latin. Every jamo is
  calibrated per placement-scale bucket (weight variants selected at compose
  time) so all contexts render at the same optical weight.
- **Letter sizes** pulled toward consistent cap-height / x-height per category
  (with descender bowls sized to x-height and over-wide letters width-capped).
- **Consistent forward tilt** matching the natural lean of the handwriting.
- **Compact spacing** — tight side bearings; Korean uses a compact
  fixed-width syllable block with complexity-adaptive jamo sizing.

![consistency](samples/consistency.png)

## How it was made

1. **Extract** the ink from each worksheet cell, located via the PDF's own
   U+XXXX captions (the gray reference letters and guides drop out).
2. **Normalise** stroke weight & letter size.
3. **Vectorise** with `potrace`.
4. **Compose** all 11,172 syllables from the jamo as TrueType composites.
5. **Assemble** with `fontTools`; clean winding with `skia-pathops`.

Full reproducible source in [`build/`](build/).

## Using it

Double-click a `.ttf` to install, or on the web:

```css
@font-face{ font-family:"Lightheaded";
            src:url("Lightheaded-Regular.ttf"); }
body{ font-family:"Lightheaded", sans-serif; }
```

> The Latin-only file is family **“Lightheaded Latin”** so it can be installed
> alongside the full font without clashing.
