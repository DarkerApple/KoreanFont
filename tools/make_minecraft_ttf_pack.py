#!/usr/bin/env python3
"""Build a Minecraft resource pack that puts the real Lightheaded outlines into
the game, via a `ttf` font provider — no bitmap sheet, no redrawing.

Minecraft rasterises the font itself at whatever GUI scale you play at, so the
text is as sharp as the screen allows instead of being locked to an 8x8 cell.

Sizing.  stb_truetype (what the game uses) scales a font so that `size` pixels
spans hhea ascent..descent.  Lightheaded's span is 1170/1000 em, so
    em px  = size * 1000/1170
    cap px = 0.70 * em px
Vanilla's built-in font has a 7px capital sitting on a baseline 7px down, so
size 12 (cap 7.18px) with the baseline pulled up 2px matches it closely.

Usage: python3 tools/make_minecraft_ttf_pack.py <font.ttf> <output-dir>
Requires: fonttools, brotli
"""

import json
import os
import shutil
import sys

from fontTools import subset
from fontTools.ttLib import TTFont

NAMESPACE = "lightheaded"
FONT_NAME = "Lightheaded-Regular.ttf"

SIZE = 12.0        # cap height 7.18px, matching vanilla's 7px
OVERSAMPLE = 8.0   # atlas resolution multiplier: sharp up to GUI scale 8
SHIFT = [0.0, -2.0]

# "English only": Basic Latin, Latin-1, the punctuation and currency Minecraft
# actually shows, and the Latin Extended-A letters vanilla's own sheet carries.
UNICODES = [
    "U+0020-007E", "U+00A0-00FF", "U+0131", "U+0152-0153", "U+015E-015F",
    "U+0174-0175", "U+017E", "U+0207", "U+2010-2027", "U+2030", "U+2039-203A",
    "U+2044", "U+20A0-20BF", "U+2122", "U+2190-2193", "U+2212", "U+2260",
    "U+25A0", "U+2500-257F", "U+2580-259F",
]


def build_font(src, dest):
    """A Latin-only cut of the font — the whole family is 1.3 MB, this is ~40 KB."""
    options = subset.Options()
    options.layout_features = ["*"]      # keep tnum
    options.name_IDs = ["*"]
    options.notdef_outline = True
    options.recalc_bounds = True
    font = subset.load_font(src, options)
    subsetter = subset.Subsetter(options=options)
    subsetter.populate(unicodes=[c for r in UNICODES for c in _expand(r)])
    subsetter.subset(font)
    subset.save_font(font, dest, options)
    return TTFont(dest)


def _expand(spec):
    body = spec[2:]
    if "-" in body:
        lo, hi = (int(p, 16) for p in body.split("-"))
        return range(lo, hi + 1)
    return [int(body, 16)]


def main(src, out_dir):
    font_dir = os.path.join(out_dir, "assets", NAMESPACE, "font")
    json_dir = os.path.join(out_dir, "assets", "minecraft", "font")
    os.makedirs(font_dir, exist_ok=True)
    os.makedirs(json_dir, exist_ok=True)

    cut = build_font(src, os.path.join(font_dir, FONT_NAME))
    covered = len(cut.getBestCmap())

    provider = {
        "type": "ttf",
        "file": f"{NAMESPACE}:font/{FONT_NAME}",
        "size": SIZE,
        "oversample": OVERSAMPLE,
        "shift": SHIFT,
    }
    # order matters: Minecraft takes the FIRST provider that has a glyph, which
    # is why vanilla's own unifont fallback sits after its ascii sheet rather
    # than swallowing it.  Ours goes above the vanilla references.
    default = {"providers": [
        {"type": "reference", "id": "minecraft:include/space"},
        provider,
        {"type": "reference", "id": "minecraft:include/default", "filter": {"uniform": False}},
        {"type": "reference", "id": "minecraft:include/unifont"},
    ]}
    with open(os.path.join(json_dir, "default.json"), "w") as f:
        json.dump(default, f, indent=2)
        f.write("\n")

    with open(os.path.join(out_dir, "pack.mcmeta"), "w") as f:
        json.dump({"pack": {
            "pack_format": 34,
            "supported_formats": {"min_inclusive": 18, "max_inclusive": 99},
            "description": "Lightheaded — the real outlines, rendered by the game",
        }}, f, indent=2)
        f.write("\n")

    icon = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "..", "minecraft", "bitmap-8px", "pack.png")
    if os.path.exists(icon):
        shutil.copy(icon, os.path.join(out_dir, "pack.png"))

    size_kb = os.path.getsize(os.path.join(font_dir, FONT_NAME)) / 1024
    em = SIZE * 1000 / (cut["hhea"].ascent - cut["hhea"].descent)
    print(f"{covered} characters, {size_kb:.0f} KB")
    print(f"size {SIZE} -> em {em:.2f}px, cap {0.70 * em:.2f}px, "
          f"x-height {0.50 * em:.2f}px (vanilla: cap 7px)")
    print(f"wrote {out_dir}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    main(sys.argv[1], sys.argv[2])
