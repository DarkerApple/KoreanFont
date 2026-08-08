# Lightheaded 128×128 — Minecraft font pack (English)

A font-only resource pack: it restyles Minecraft's built-in text and touches
nothing else.

**Install:** drop [`Lightheaded-128x-Font.zip`](Lightheaded-128x-Font.zip) into
`.minecraft/resourcepacks/` and enable it in Options → Resource Packs.

```
pack.mcmeta
pack.png
assets/minecraft/textures/font/ascii.png     128 × 128
```

## How it works

Minecraft's built-in font lives in a single 128×128 sheet holding a 16×16 grid
of 8×8 glyphs, in a Code Page 437-derived order. Replacing **only that texture**
restyles the font on every version since 1.13 and needs no font JSON — so
vanilla's accented, non-Latin and Unicode fallbacks all keep working. There is
nothing in the pack that can conflict with another pack's fonts.

## Why the glyphs are drawn, not rendered from the TTF

Lightheaded's stroke is 75/1000 of the em. In an 8-pixel cell that is **0.64 of
a pixel**, so no threshold survives contact with the whole alphabet:

| threshold | what breaks |
|---|---|
| 0.30 | `e` fills in — "The" reads as "Tha" |
| 0.33 | best available, but `n` loses its left stem and `k`, `s`, `z` blob |
| 0.40 | thin diagonals break apart entirely |

So the Latin glyphs in [`../tools/mc_glyphs.py`](../tools/mc_glyphs.py) are drawn
as pixel art *after* the font, keeping its proportions — six rows of capital,
four of x-height, two of descender, and its rounded, loose fit. The box-drawing
and block rows are generated geometrically so they don't vanish from the sheet.

**128×128 forces 8×8 cells.** Printable ASCII is 95 characters, which needs at
least a 10×10 grid; the only grid that divides 128 evenly and holds that many is
16×16, giving 8×8 per glyph. A larger cell means a larger sheet.

## What's in the sheet

- **171 letterforms** — printable ASCII, plus accented Latin where an accent
  fits above the x-height (`á à â ä ã å é è ê ë í ì î ï ó ò ô ö õ ú ù û ü ñ ÿ`)
  and a handful of symbols (`£ ° · ± × ÷ ² ¡ ¿ « » ¬ ª º ß ø Ø æ Æ ƒ ½ ¼`)
- **31 box-drawing and block characters** — drawn geometrically
- **54 blank** — accented *capitals* keep their base letter (`À` renders as `A`)
  because a six-row capital leaves no room for a mark above it, and the Greek and
  maths row is not covered

## One deliberate difference from vanilla

The glyphs sit with their baseline on row 6 rather than row 7, which is what
vanilla's provider declares. Text therefore floats one pixel higher than
vanilla's. That is the price of a two-pixel descender: at row 7 the descenders of
`g j p q y` are cut to a single row and "dog" reads as "doo". For English text the
one-pixel shift is invisible; it is only noticeable if you mix in accented
capitals, which come from vanilla's own sheet.

## Rebuilding

```sh
pip install pillow
python3 tools/make_minecraft_pack.py minecraft/src
```

Edit [`tools/mc_glyphs.py`](../tools/mc_glyphs.py) to change a letterform — each
glyph is eight rows of `#` and `.`.
