"""Build Minecraft (Java Edition 1.20.3+) resource packs for Lightheaded.
Two packs: English-only (Latin font) and Korean (full font).
The TTF provider renders the real outlines; a reference provider keeps
vanilla glyphs as fallback for anything the font doesn't cover."""
import json, os, zipfile
from PIL import Image, ImageDraw, ImageFont

MCDIR="../mc"; os.makedirs(MCDIR, exist_ok=True)

def pack(zip_path, ttf_src, desc, icon_text, icon_font):
    mcmeta={"pack":{
        "pack_format": 22,
        "supported_formats": {"min_inclusive": 15, "max_inclusive": 99},
        "description": desc}}
    fontjson={"providers":[
        {"type":"ttf","file":"minecraft:lightheaded.ttf",
         "shift":[0.0,0.6],"size":10.5,"oversample":4.0},
        {"type":"reference","id":"minecraft:include/default"},
        {"type":"reference","id":"minecraft:include/unifont"}]}
    # pack icon: the font on a warm card
    im=Image.new('RGB',(128,128),(247,243,234))
    d=ImageDraw.Draw(im)
    f=ImageFont.truetype(icon_font, 84)
    w=d.textlength(icon_text,font=f)
    d.text(((128-w)/2,14), icon_text, font=f, fill=(30,28,26))
    d.rectangle([0,0,127,127], outline=(30,28,26), width=3)
    icon_tmp=f"{MCDIR}/_icon.png"; im.save(icon_tmp)
    with zipfile.ZipFile(zip_path,'w',zipfile.ZIP_DEFLATED) as z:
        z.writestr("pack.mcmeta", json.dumps(mcmeta, ensure_ascii=False, indent=2))
        z.write(icon_tmp, "pack.png")
        z.writestr("assets/minecraft/font/default.json",
                   json.dumps(fontjson, indent=2))
        z.write(ttf_src, "assets/minecraft/font/lightheaded.ttf")
        z.writestr("README.txt",
            "Lightheaded Minecraft resource pack\n"
            "Drop this zip into .minecraft/resourcepacks and enable it in\n"
            "Options > Resource Packs. Requires Java Edition 1.20.3+\n"
            "(TTF + reference font providers).\n")
    os.remove(icon_tmp)
    print(zip_path, f"{os.path.getsize(zip_path)/1e6:.2f}MB")

pack(f"{MCDIR}/Lightheaded-English-MC.zip", "Lightheaded-Latin-Regular.ttf",
     "Lightheaded handwriting font (English)", "Aa", "Lightheaded-Latin-Regular.ttf")
pack(f"{MCDIR}/Lightheaded-Korean-MC.zip", "Lightheaded-Regular.ttf",
     "Lightheaded 손글씨 폰트 (한글+English)", "한", "Lightheaded-Regular.ttf")
