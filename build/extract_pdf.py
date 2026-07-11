"""Extract black-ink glyphs from the LightheadedRAW.pdf worksheet.
Cells are located via the PDF text layer's U+XXXX captions; only pixels
darker than INK_T are kept (drops gray reference letters, guides, borders)."""
import re, json, subprocess, os
import numpy as np
from PIL import Image

PDF="/root/.claude/uploads/6ef2b99b-98a1-5245-8965-0721a9254744/a5188fcf-LightheadedRAW.pdf"
DPI=300; SCALE=DPI/72.0
INK_T=100
EXCLUDE={0x20A9,0x20AC,0x00A3,0x00A5,0x00B7,0x00A9,0x00AE}   # scribbled/blacked-out cells

CHO =['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
JUNG=['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ','ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ']
JONG=['ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ','ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']

# ---- labels from the text layer ----
html=subprocess.run(["pdftotext","-bbox",PDF,"-"],capture_output=True,text=True).stdout
labels=[]; page=0
for line in html.splitlines():
    if "<page" in line: page+=1
    m=re.search(r'<word xMin="([\d.]+)" yMin="([\d.]+)" xMax="([\d.]+)" yMax="([\d.]+)">(U\+[0-9A-Fa-f]{4})</word>',line)
    if m:
        x0,y0,x1,y1=map(float,m.groups()[:4])
        labels.append(dict(page=page,cp=int(m.group(5)[2:],16),
                           xc=(x0+x1)/2*SCALE, ytop=y0*SCALE))
# sort into document order: page, row(cluster y), x
labels.sort(key=lambda L:(L['page'], round(L['ytop']/40), L['xc']))
print("labels found:",len(labels))

# column pitch from page-1 first row
row0=[L for L in labels if L['page']==1][:6]
pitch=np.median(np.diff(sorted(l['xc'] for l in row0)))
CW=int(pitch*0.905)               # cell square side (px)
print("pitch px=%.1f cell=%dpx"%(pitch,CW))

# ---- role assignment by document order ----
jamo=labels[:19+21+27]
seq=[l['cp'] for l in jamo]
exp=[ord(c) for c in CHO]+[ord(c) for c in JUNG]+[ord(c) for c in JONG]
assert seq==exp, f"jamo sequence mismatch: {[hex(a) for a,b in zip(seq,exp) if a!=b][:5]}"
assign=[]
for k,L in enumerate(labels):
    if   k<19:    assign.append(("cho%02d"%k,'cho',ord(CHO[k]),CHO[k],L))
    elif k<19+21: assign.append(("jung%02d"%(k-19),'jung',ord(JUNG[k-19]),JUNG[k-19],L))
    elif k<19+21+27: assign.append(("jong%02d"%(k-40),'jong',ord(JONG[k-40]),JONG[k-40],L))
    else:
        if L['cp'] in EXCLUDE: continue
        assign.append(("uni%04X"%L['cp'],'uni',L['cp'],chr(L['cp']),L))

os.makedirs("glyphs",exist_ok=True)
for f in os.listdir("glyphs"): os.remove(os.path.join("glyphs",f))
pages={p:np.asarray(Image.open(f"pdfpages/p-{p}.png").convert('L')) for p in range(1,7)}

meta={}; nink=0
for gid,role,cp,ch,L in assign:
    a=pages[L['page']]
    x0=int(L['xc']-CW/2); x1=int(L['xc']+CW/2)
    y1=int(L['ytop']-12); y0=y1-CW
    m=12                                        # margin to catch slight overflow
    win=a[max(0,y0-m):y1+m, max(0,x0-m):x1+m]
    ink=win<INK_T
    # drop dust
    from scipy import ndimage
    lab,n=ndimage.label(ink)
    if n:
        sizes=ndimage.sum(ink,lab,range(1,n+1))
        keep=np.isin(lab,[i+1 for i,s in enumerate(sizes) if s>=40])
    else: keep=ink
    rec=dict(page=f"p{L['page']}",role=role,cp=cp,char=ch,empty=True)
    if keep.sum()>=60:
        ys,xs=np.where(keep)
        iy0,iy1,ix0,ix1=ys.min(),ys.max(),xs.min(),xs.max()
        g=np.where(keep[iy0:iy1+1,ix0:ix1+1],0,255).astype(np.uint8)
        Image.fromarray(g).save(f"glyphs/{gid}.png")
        # box_rel relative to the nominal cell square
        offx=(x0-(max(0,x0-m))); offy=(y0-(max(0,y0-m)))
        nx0=(ix0-offx)/CW; nx1=(ix1+1-offx)/CW
        ny0=(iy0-offy)/CW; ny1=(iy1+1-offy)/CW
        rec.update(empty=False,box_rel=[float(nx0),float(ny0),float(nx1),float(ny1)],
                   ink_px=[int(ix1-ix0+1),int(iy1-iy0+1)])
        nink+=1
    meta[gid]=rec
json.dump(meta,open("meta.json","w"),ensure_ascii=False)
print(f"cells assigned={len(assign)} with-ink={nink} empty={sum(1 for r in meta.values() if r['empty'])}")
print("empty:",[k for k,r in meta.items() if r['empty']])

# ---- post-fix: close the internal gap in mix vowels (ㅘㅙㅚㅝㅞㅟㅢ) ----
# the drawn right bar sits far from the ㅗ/ㅜ/ㅡ base; pull it in so the bar
# doesn't float at the end of the syllable.
def _close_mix_gap(path, maxgap=0.11):
    im=np.asarray(Image.open(path).convert('L')); ink=im<128
    H,W=ink.shape
    cols=ink.any(axis=0)
    runs=[]; i=0
    while i<W:
        if cols[i]:
            j=i
            while j<W and cols[j]: j+=1
            runs.append((i,j)); i=j
        else: i+=1
    if len(runs)<2: return False
    gaps=[(runs[k+1][0]-runs[k][1],k) for k in range(len(runs)-1)]
    g,k=max(gaps)
    if g <= maxgap*W: return False
    newg=int(maxgap*W)
    shift=g-newg
    cut=runs[k][1]
    out=np.zeros((H,W-shift),bool)
    out[:, :cut]=ink[:, :cut]
    out[:, cut+newg- (runs[k+1][0]-cut-shift) if False else cut:]=False
    right=ink[:, runs[k+1][0]:]
    out[:, runs[k+1][0]-shift:runs[k+1][0]-shift+right.shape[1]]|=right
    Image.fromarray(np.where(out,0,255).astype(np.uint8)).save(path)
    return True

if __name__=='__main__' or True:
    for i in (9,10,11,14,15,16,19):     # ㅘㅙㅚㅝㅞㅟㅢ
        p=f"glyphs/jung{i:02d}.png"
        if os.path.exists(p):
            print("mix-gap fix", p, _close_mix_gap(p))
