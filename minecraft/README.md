# Lightheaded — Minecraft font pack (English)

Font-only resource packs: they restyle Minecraft's text and touch nothing else.

| | | |
|---|---|---|
| **[`Lightheaded-Font.zip`](Lightheaded-Font.zip)** | 17 KB | **the real outlines**, rendered by the game — 1.20.2+ |
| [`Lightheaded-Font-8px-legacy.zip`](Lightheaded-Font-8px-legacy.zip) | 4 KB | 8×8 bitmap sheet, for 1.13 – 1.20.1 |

Drop the zip into `.minecraft/resourcepacks/` and enable it in
Options → Resource Packs.

---

## The real font (`ttf/`)

Minecraft can rasterise a TrueType font itself, so the pack ships the outlines
and the game draws them at whatever GUI scale you play at. No bitmap sheet, no
redrawing, nothing locked to an 8-pixel cell — the curves, the loose fit and the
hand-drawn wobble all survive, and the text gets sharper as you raise the GUI
scale rather than blockier.

```
pack.mcmeta
assets/lightheaded/font/Lightheaded-Regular.ttf     Latin subset, 22 KB
assets/minecraft/font/default.json
```

### Sizing

`stb_truetype`, which the game uses, scales a font so that `size` pixels spans
hhea ascent → descent. Lightheaded's span is 1170/1000 em, so:

```
em px  = size × 1000/1170
cap px = 0.70 × em px
```

| size | em | cap height | x-height |
|---|---|---|---|
| 10 | 8.55px | 5.98px | 4.27px |
| 11 | 9.40px | 6.58px | 4.70px |
| **12** | **10.26px** | **7.18px** | **5.13px** |
| 13 | 11.11px | 7.78px | 5.56px |

Vanilla's built-in font has a 7px capital on a baseline 7px down, so the pack
ships **size 12** with `shift: [0, -2]` to pull that 9.03px ascent back onto
vanilla's 7px baseline. `oversample: 8` means the glyph atlas is built at eight
times the size, so it stays sharp up to GUI scale 8.

Those three numbers are the only knobs, all in `default.json`:

```json
{ "type": "ttf", "file": "lightheaded:font/Lightheaded-Regular.ttf",
  "size": 12.0, "oversample": 8.0, "shift": [0.0, -2.0] }
```

I could not launch the game from here, so **if the text sits a pixel high or
low, `shift[1]` is the number to nudge** — positive moves it down. Everything
else is arithmetic that checks out against the table above.

### Provider order

```json
"providers": [
  { "type": "reference", "id": "minecraft:include/space" },
  { "type": "ttf", ... },
  { "type": "reference", "id": "minecraft:include/default", "filter": {"uniform": false} },
  { "type": "reference", "id": "minecraft:include/unifont" }
]
```

Minecraft takes the **first** provider that has a glyph — which is why vanilla's
own unifont fallback sits *after* its ASCII sheet instead of swallowing it. So
Lightheaded goes above the vanilla references: it wins for everything it covers,
and vanilla still supplies Cyrillic, Greek, CJK, box drawing and the rest. The
`reference` provider needs 1.20.2; that is where the version floor comes from.

### English only

The bundled font is subset to Basic Latin, Latin-1, Latin Extended-A, and the
punctuation, arrows and currency Minecraft actually shows — 119 characters,
22 KB instead of 1.3 MB. To get Hangul as well, copy the full
[`fonts/Lightheaded-Regular.ttf`](../fonts/) over the bundled one; the JSON needs
no change.

### Rebuilding

```sh
pip install fonttools brotli
python3 tools/make_minecraft_ttf_pack.py fonts/Lightheaded-Regular.ttf minecraft/ttf
```

---

## The 8-pixel fallback (`bitmap-8px/`)

For 1.13 – 1.20.1, where the `reference` provider does not exist. It replaces
`assets/minecraft/textures/font/ascii.png` — a 128×128 sheet of 8×8 glyphs — and
nothing else, so vanilla's fallbacks keep working there too.

Its glyphs are **drawn**, not rasterised from the font. Lightheaded's stroke is
75/1000 of the em, which is 0.64 of a pixel in an 8-pixel cell, and no threshold
survives the whole alphabet: at 0.30 `e` fills in and "The" reads as "Tha", at
0.33 `n` loses its left stem, at 0.40 the diagonals break apart. So
[`../tools/mc_glyphs.py`](../tools/mc_glyphs.py) holds an 8×8 alphabet drawn after
the font's proportions — six rows of capital, four of x-height, two of descender.

Its baseline sits on row 6 rather than the row 7 vanilla declares, so text floats
a pixel high; at row 7 the descenders of `g j p q y` are cut to one row and "dog"
reads as "doo".

```sh
python3 tools/make_minecraft_pack.py minecraft/bitmap-8px
```
