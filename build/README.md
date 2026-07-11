# Build pipeline

Reproduces the Lightheaded fonts from the source photos in `raw/`.

## Requirements

```bash
pip install fonttools pillow numpy scipy skia-pathops compreffor
# potrace binary:
apt-get install potrace      # Debian/Ubuntu
# brew install potrace       # macOS
```

## Run (from this directory)

```bash
python3 extract_final.py        # raw/*.jpg -> glyphs/*.png + meta.json  (cell crop + ink isolation)
python3 cache_traces.py glyphs  # glyphs/   -> traces.pkl                (needed by the normaliser)
python3 normalize.py            # glyphs/   -> glyphs_norm/              (even stroke weight)
python3 cache_traces.py         # glyphs_norm/ -> traces.pkl            (re-trace normalised)
python3 build_font.py           # -> Lightheaded-Regular.ttf (+ -Latin) (with & without Korean)
python3 make_otf.py             # -> .otf versions (CFF; then subroutinised with compreffor)
```

`build_font.py` emits **two** files: `Lightheaded-Regular.ttf` (with Korean) and
`Lightheaded-Latin-Regular.ttf` (Latin/symbols only).

## Files

| File | Role |
|---|---|
| `raw/img00…09.jpg` | the 10 filled-in template photos (jamo ×4, ASCII ×6) |
| `spec.py` | logical layout of every page → which glyph is in which cell |
| `geom_fixed.py` | frozen per-page grid geometry (row centres + column span) |
| `extract_final.py` | grid crop, ink isolation, neighbour-leak removal, per-glyph metadata |
| `vector.py` | potrace wrapper + SVG-path parser → Bézier contours |
| `normalize.py` | even out stroke weight (thin heavy strokes) to a consistent target |
| `cache_traces.py` | trace every glyph (arg = source dir) into `traces.pkl` |
| `fontcommon.py` | coordinate mapping (box → em), baseline rules, glyph pens |
| `hangul.py` | syllable composition: zones for the 6 layout types, jamo placement |
| `build_font.py` | assemble the TTF (ASCII + base jamo + 11,172 composites) |
| `meta.json` | extracted per-glyph bounding boxes / positions |

## Tuning

- **Syllable proportions** live in `hangul.py` (`zones`, `ROLE_FIT`, `jong_zone`,
  the design square `SQ_*`).
- **Latin metrics** (cap height, side bearings, baseline) live in `fontcommon.py`
  (`S`, `SB`, `CAP_H`, `X_H`, descender set).
- **Family name / vertical metrics** are in `build_font.py`.
