#!/usr/bin/env python3
"""Build a 128x128 Minecraft font resource pack from Lightheaded Regular.

Minecraft's built-in font lives in assets/minecraft/textures/font/ascii.png: a
128x128 sheet holding a 16x16 grid of 8x8 glyphs, in a Code Page 437-derived
order.  Replacing just that texture restyles the font on every version since
1.13 and needs no font JSON, so the accented, non-Latin and Unicode fallbacks
all keep working out of vanilla.

Lightheaded's stroke is 75/1000 of the em, which is 0.64 of a pixel in an 8px
cell, so downsampling its outlines breaks every time — at one threshold 'n'
loses its left stem, at the next 'e' fills in and reads as 'a'.  The Latin
glyphs are therefore drawn as pixel art after the font (see mc_glyphs.py)
rather than rasterised from it.  The box drawing and block rows are drawn
geometrically so they do not vanish from the sheet.

Usage: python3 tools/make_minecraft_pack.py <output-dir>
Requires: pillow
"""

import json
import os
import sys

from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import mc_glyphs

CELL = 8            # vanilla glyph cell, in pixels
GRID = 16           # 16 x 16 cells -> a 128 x 128 sheet
SHEET = CELL * GRID
BASELINE = 6        # 6 rows above the baseline, 2 below.  Vanilla's provider
                    # declares ascent 7, so the text floats one pixel high --
                    # worth it: at ascent 7 the descenders of g j p q y are cut
                    # to a single row and 'dog' reads as 'doo'.

# Minecraft's ascii.png layout.  Rows 2-7 are printable ASCII.
LAYOUT = [
    "ÀÁÂÈÊËÍÓÔÕÚßãõğİ",
    "ıŒœŞşŴŵžȇ\0\0\0\0\0\0\0",
    " !\"#$%&'()*+,-./",
    "0123456789:;<=>?",
    "@ABCDEFGHIJKLMNO",
    "PQRSTUVWXYZ[\\]^_",
    "`abcdefghijklmno",
    "pqrstuvwxyz{|}~\0",
    "ÇüéâäàåçêëèïîìÄÅ",
    "ÉæÆôöòûùÿÖÜø£Ø×ƒ",
    "áíóúñÑªº¿⌐¬½¼¡«»",
    "░▒▓│┤╡╢╖╕╣║╗╝╜╛┐",
    "└┴┬├─┼╞╟╚╔╩╦╠═╬╧",
    "╨╤╥╙╘╒╓╫╪┘┌█▄▌▐▀",
    "αβΓπΣσμτΦΘΩδ∞∅∈∩",
    "≡±≥≤⌠⌡÷≈°∙·√ⁿ²■\0",
]

def trim_left(cell):
    """Minecraft measures a glyph's advance from its ink, so start at column 0."""
    px = cell.load()
    cols = [x for x in range(CELL) if any(px[x, y] for y in range(CELL))]
    if not cols or cols[0] == 0:
        return cell
    shift = cols[0]
    moved = Image.new("L", (CELL, CELL), 0)
    moved.paste(cell.crop((shift, 0, CELL, CELL)), (0, 0))
    return moved


def geometry(char):
    """Box drawing and block characters, drawn rather than borrowed."""
    cell = Image.new("L", (CELL, CELL), 0)
    d = ImageDraw.Draw(cell)
    mid = 3
    light, heavy = "─│┼┤├┬┴┌┐└┘", "═║╬╣╠╦╩╔╗╚╝"
    if char == "█":
        d.rectangle([0, 0, CELL - 1, CELL - 1], fill=255)
    elif char == "▄":
        d.rectangle([0, CELL // 2, CELL - 1, CELL - 1], fill=255)
    elif char == "▀":
        d.rectangle([0, 0, CELL - 1, CELL // 2 - 1], fill=255)
    elif char == "▌":
        d.rectangle([0, 0, CELL // 2 - 1, CELL - 1], fill=255)
    elif char == "▐":
        d.rectangle([CELL // 2, 0, CELL - 1, CELL - 1], fill=255)
    elif char == "■":
        d.rectangle([1, 2, CELL - 3, CELL - 3], fill=255)
    elif char in "░▒▓":
        step = {"░": 3, "▒": 2, "▓": 1}[char]
        for y in range(CELL):
            for x in range(CELL):
                on = (x + y) % (step + 1) == 0 if step else True
                if char == "▓":
                    on = (x + y) % 2 == 0 or x % 2 == 0
                if on:
                    cell.putpixel((x, y), 255)
    elif char in light or char in heavy:
        double = char in heavy
        rows = [mid - 1, mid + 1] if double else [mid]
        up = char in "│┼┤├┘└║╬╣╠╝╚"
        down = char in "│┼┤├┐┌║╬╣╠╗╔"
        left = char in "─┼┤┴┐┘═╬╣╩╗╝"
        right = char in "─┼├┴┌└═╬╠╩╔╚"
        for r in rows:
            if left:
                d.line([(0, r), (mid, r)], fill=255)
            if right:
                d.line([(mid, r), (CELL - 1, r)], fill=255)
            if up:
                d.line([(r, 0), (r, mid)], fill=255)
            if down:
                d.line([(r, mid), (r, CELL - 1)], fill=255)
        if double and (left or right) and (up or down):
            d.point([(mid - 1, mid - 1), (mid + 1, mid + 1)], fill=255)
    else:
        return None
    return cell


def from_rows(rows):
    cell = Image.new("L", (CELL, CELL), 0)
    px = cell.load()
    for y, line in enumerate(rows):
        for x, c in enumerate(line[:CELL]):
            if c == "#":
                px[x, y] = 255
    return cell


def build_sheet(_font_path=None):
    sheet = Image.new("LA", (SHEET, SHEET), (255, 0))
    drawn = {"drawn": 0, "geometry": 0, "blank": 0}
    for row, line in enumerate(LAYOUT):
        for col, char in enumerate(line[:GRID]):
            if char in ("\0", " "):
                drawn["blank"] += 1
                continue
            rows = mc_glyphs.bitmap(char)
            cell = None
            if rows:
                cell = trim_left(from_rows(rows))
                if cell.getbbox():
                    drawn["drawn"] += 1
                else:
                    cell = None
            if cell is None:
                cell = geometry(char)
                if cell is not None:
                    drawn["geometry"] += 1
            if cell is None:
                drawn["blank"] += 1
                continue
            block = Image.new("LA", (CELL, CELL), (255, 0))
            block.putalpha(cell)
            sheet.paste(block, (col * CELL, row * CELL))
    return sheet.convert("RGBA"), drawn


def main(_unused, out_dir):
    sheet, drawn = build_sheet()
    tex = os.path.join(out_dir, "assets", "minecraft", "textures", "font")
    os.makedirs(tex, exist_ok=True)
    sheet.save(os.path.join(tex, "ascii.png"))

    with open(os.path.join(out_dir, "pack.mcmeta"), "w") as f:
        json.dump({
            "pack": {
                "pack_format": 34,
                "supported_formats": {"min_inclusive": 4, "max_inclusive": 99},
                "description": "Lightheaded — handwritten 128x128 font (English)",
            }
        }, f, indent=2)
        f.write("\n")

    # pack icon: the sheet's ASCII block, scaled up
    icon = Image.new("RGBA", (SHEET, SHEET), (24, 22, 20, 255))
    icon.alpha_composite(sheet.crop((0, 4 * CELL, SHEET, 8 * CELL)).resize(
        (SHEET, SHEET // 2), Image.NEAREST), (0, SHEET // 4))
    icon.save(os.path.join(out_dir, "pack.png"))

    print(f"sheet {sheet.size[0]}x{sheet.size[1]}   "
          f"{drawn['drawn']} letterforms, {drawn['geometry']} box-drawing, {drawn['blank']} blank")
    print(f"wrote {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    main(None, sys.argv[1])
