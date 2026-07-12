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

# ---- post-clean the drawn jamo --------------------------------------------
def _load_g(gid):
    a=np.asarray(Image.open(f"glyphs/{gid}.png").convert('L')); return a<128
def _save_g(gid, ink):
    ys,xs=np.where(ink)
    g=np.where(ink[ys.min():ys.max()+1, xs.min():xs.max()+1],0,255).astype(np.uint8)
    Image.fromarray(g).save(f"glyphs/{gid}.png")

def trim_stem(gid, side):
    """Drop narrow stem overshoot past the arm of ㅗ/ㅜ/ㅛ/ㅠ.
    side='u': arm on top (ㅜㅠ) — clear ink above it; side='o': arm at bottom."""
    import os as _os
    if not _os.path.exists(f"glyphs/{gid}.png"): return
    ink=_load_g(gid); H,W=ink.shape
    rw=ink.sum(axis=1)
    wide=np.where(rw>=0.55*W)[0]
    if len(wide)==0: return
    if side=='u':
        t0=wide.min()
        if t0>0 and ink[:t0].any(): ink[:t0]=False; _save_g(gid,ink)
    else:
        b0=wide.max()
        if b0<H-1 and ink[b0+1:].any(): ink[b0+1:]=False; _save_g(gid,ink)

def _resize_mask(ink, w, h):
    im=Image.fromarray(np.where(ink,0,255).astype(np.uint8)).resize((max(1,w),max(1,h)),Image.LANCZOS)
    return np.asarray(im)<128

def print_jieut():
    """Rebuild ㅈ with print topology from the user's own ink:
    their ㅡ as the top bar + their ㅅ beneath, apex meeting the bar."""
    s=_load_g('cho09'); bar=_load_g('jung18')
    sh,sw=s.shape; bh,bw=bar.shape
    W=int(round(sw*1.10))
    b=_resize_mask(bar, W, max(4,int(round(bh*W/bw))))
    bh2=b.shape[0]
    ov=max(2,int(bh2*0.45))
    H=bh2-ov+sh
    z=np.zeros((H,W),bool)
    z[:bh2,:]=b
    x0=(W-sw)//2
    z[bh2-ov:bh2-ov+sh, x0:x0+sw]|=s
    return z

def _tick():
    """The detached tick from the drawn ㅊ (topmost small component)."""
    from scipy import ndimage as _n
    ink=_load_g('cho14')
    lab,n=_n.label(ink)
    if n<2: return None
    parts=[]
    for c in range(1,n+1):
        ys,xs=np.where(lab==c)
        parts.append((ys.min(),c,ys,xs))
    parts.sort()
    y0,c,ys,xs=parts[0]
    if (lab==c).sum()>0.30*ink.sum(): return None
    return ink[ys.min():ys.max()+1, xs.min():xs.max()+1]

def print_chieut(z):
    t=_tick()
    if t is None:
        th=max(4,z.shape[0]//12); tw=z.shape[1]//3
        t=np.ones((th,tw),bool)
    gap=max(3,z.shape[0]//14)
    H=t.shape[0]+gap+z.shape[0]; W=max(z.shape[1],t.shape[1])
    out=np.zeros((H,W),bool)
    tx=(W-t.shape[1])//2
    out[:t.shape[0], tx:tx+t.shape[1]]=t
    out[t.shape[0]+gap:, (W-z.shape[1])//2:(W-z.shape[1])//2+z.shape[1]]=z
    return out

def _swap_right(gid, z):
    """Replace the right half of a two-part cluster (e.g. ㄵ) with new ink."""
    ink=_load_g(gid); H,W=ink.shape
    cols=ink.any(axis=0); runs=[]; x=0
    while x<W:
        if cols[x]:
            j=x
            while j<W and cols[j]: j+=1
            runs.append((x,j)); x=j
        else: x+=1
    if len(runs)<2: return
    inkw=sum(b-a for a,b in runs); best=None
    for k in range(len(runs)-1):
        gap=runs[k+1][0]-runs[k][1]
        if gap<0.03*W: continue
        left=sum(b-a for a,b in runs[:k+1])/inkw
        bal=min(left,1-left)
        if best is None or bal>best[0]: best=(bal,k)
    if not best: return
    k=best[1]
    left=ink[:, :runs[k][1]]
    rh=H
    rz=_resize_mask(z, int(round(z.shape[1]*rh/z.shape[0])), rh)
    gap=runs[k+1][0]-runs[k][1]
    out=np.zeros((H, runs[k][1]+gap+rz.shape[1]), bool)
    out[:, :runs[k][1]]=left
    out[:, runs[k][1]+gap:]=rz
    _save_g(gid, out)

def equalize_bars(gid):
    """ㅐㅒㅔㅖ (and split compound bars): make both vertical stems the
    same height by extending the shorter ends."""
    import os as _os
    if not _os.path.exists(f"glyphs/{gid}.png"): return
    ink=_load_g(gid); H,W=ink.shape
    ysi=np.arange(H)[:,None]
    cols=ink.any(axis=0)
    top=np.where(ink, ysi, H).min(axis=0); bot=np.where(ink, ysi, -1).max(axis=0)
    colh=np.where(cols, bot-top+1, 0)
    tallc=colh>=0.60*H
    runs=[]; x=0
    while x<W:
        if tallc[x]:
            j=x
            while j<W and tallc[j]: j+=1
            runs.append((x,j)); x=j
        else: x+=1
    if len(runs)<2: return
    runs=runs[-2:]                          # the two stems (rightmost tall runs)
    spans=[(min(top[a:b]), max(bot[a:b])) for a,b in runs]
    T=min(s[0] for s in spans); B=max(s[1] for s in spans)
    for (a,b),(t,bt) in zip(runs,spans):
        if t>T:  # extend upward, replicating a clean row of this stem
            row=ink[min(t+3,H-1), a:b]
            for y in range(T,t): ink[y, a:b]|=row
        if bt<B:
            row=ink[max(bt-3,0), a:b]
            for y in range(bt+1,B+1): ink[y, a:b]|=row
    _save_g(gid, ink)

def tieut_from_dieut(dgid):
    """ㅌ in the user's own hand: their drawn ㄷ plus a middle bar (their ㅡ)
    attached to the stem at mid-height — keeps the curled personality."""
    d=_load_g(dgid); H,W=d.shape
    bar=_load_g('jung18')
    row=d[int(H*0.44):int(H*0.56)]
    xs=np.where(row.any(axis=0))[0]
    x0=int(xs.min()) if len(xs) else 0
    bw=int(W*0.86)-x0
    bt=max(4,int(round(bar.shape[0]*bw/bar.shape[1])))
    y0=(H-bt)//2
    z=d.copy()
    z[y0:y0+bt, x0:x0+bw]|=_resize_mask(bar, bw, bt)
    return z

# plain ㅗㅜㅛㅠ: stems must not cross their arm
trim_stem('jung13','u'); trim_stem('jung17','u')
trim_stem('jung08','o'); trim_stem('jung12','o')
# ㅌ = the drawn ㄷ + a clean middle bar (same stroke set, same curl)
_save_g('cho16', tieut_from_dieut('cho03'))
_save_g('jong24', tieut_from_dieut('jong06'))
# print-topology ㅈ / ㅊ / ㅉ built from the user's own ㅡ + ㅅ (+ drawn tick)
_Z=print_jieut(); _C=print_chieut(_Z)
_save_g('cho12',_Z); _save_g('cho14',_C)
_zz_w=int(round(_Z.shape[1]*0.58))
_zz=np.zeros((_Z.shape[0], 2*_zz_w+max(3,_Z.shape[1]//12)), bool)
_zzp=_resize_mask(_Z,_zz_w,_Z.shape[0])
_zz[:, :_zz_w]|=_zzp; _zz[:, _zz.shape[1]-_zz_w:]|=_zzp
_save_g('cho13',_zz)
_save_g('jong22',_Z); _save_g('jong23',_C)
_swap_right('jong04', _Z)                   # ㄵ = ㄴ + new ㅈ
equalize_bars('jung01'); equalize_bars('jung03')
equalize_bars('jung05'); equalize_bars('jung07')

# ---- decompose mix vowels (ㅘㅙㅚㅝㅞㅟㅢ) into base (ㅗ/ㅜ/ㅡ) + right bar ----
# split at the most balanced wide column gap; each part becomes its own glyph
# so composition can place them independently (base under the initial, bar right).
def _split_mix(i):
    path=f"glyphs/jung{i:02d}.png"
    if not os.path.exists(path): return False
    im=np.asarray(Image.open(path).convert('L')); ink=im<128
    H,W=ink.shape
    def tight(a):
        ys,xs=np.where(a)
        return a[ys.min():ys.max()+1, xs.min():xs.max()+1]
    def bars_in(a):
        """tall columns in the right part of a mask (a base must have none)"""
        if not a.any(): return True
        aa=tight(a); h,w=aa.shape
        ysi=np.arange(h)[:,None]
        cols=aa.any(axis=0)
        top=np.where(aa, ysi, h).min(axis=0); bot=np.where(aa, ysi, -1).max(axis=0)
        colh=np.where(cols, bot-top+1, 0)
        return bool(((colh>=0.72*h)&(np.arange(w)>=0.55*w)).any())
    def save(base,bar):
        Image.fromarray(np.where(tight(base),0,255).astype(np.uint8)).save(f"glyphs/jung{i:02d}_base.png")
        Image.fromarray(np.where(tight(bar),0,255).astype(np.uint8)).save(f"glyphs/jung{i:02d}_bar.png")
        return True
    # 1) balanced column gap
    cols=ink.any(axis=0); runs=[]; x=0
    while x<W:
        if cols[x]:
            j=x
            while j<W and cols[j]: j+=1
            runs.append((x,j)); x=j
        else: x+=1
    if len(runs)>=2:
        inkw=sum(b-a for a,b in runs); best=None
        for k in range(len(runs)-1):
            gap=runs[k+1][0]-runs[k][1]
            if gap < 0.04*W: continue
            left=sum(b-a for a,b in runs[:k+1])/inkw
            bal=min(left,1-left)
            if best is None or bal>best[0]: best=(bal,k)
        if best:
            k=best[1]
            base,bar=ink[:, :runs[k][1]], ink[:, runs[k+1][0]:]
            if not bars_in(base): return save(base,bar)
    # 2) connected components: tall right components form the bar
    from scipy import ndimage as _ndi
    lab,n=_ndi.label(ink)
    if n>=2:
        barmask=np.zeros_like(ink)
        for c in range(1,n+1):
            ys,xs=np.where(lab==c)
            if (ys.max()-ys.min()+1)>=0.55*H and xs.mean()>=0.5*W:
                barmask|=(lab==c)
        if barmask.any() and barmask.sum()<ink.sum():
            base=ink&~barmask
            if not bars_in(base): return save(base,barmask)
    # 3) cut before the leftmost tall column right of centre (ㅘㅙㅚㅞ)
    ysi=np.arange(H)[:,None]
    top=np.where(ink, ysi, H).min(axis=0); bot=np.where(ink, ysi, -1).max(axis=0)
    colh=np.where(cols, bot-top+1, 0)
    tall=np.where((colh>=0.70*H)&(np.arange(W)>=0.40*W))[0]
    if len(tall)==0: return False
    cut=max(int(tall.min())-2, 1)
    return save(ink[:, :cut], ink[:, cut:])
if __name__=='__main__' or True:
    import json as _j
    meta2=_j.load(open("meta.json"))
    for i in (9,10,11,14,15,16,19):     # ㅘㅙㅚㅝㅞㅟㅢ
        ok=_split_mix(i)
        print("mix split", i, ok)
        if ok:
            src=meta2[f"jung{i:02d}"]
            for part in ("base","bar"):
                meta2[f"jung{i:02d}_{part}"]=dict(page=src["page"],role="jung",cp=src["cp"],
                                                  char=src["char"],empty=False,
                                                  box_rel=src["box_rel"],ink_px=src["ink_px"])
    _j.dump(meta2, open("meta.json","w"), ensure_ascii=False)
    # split bases inherit the arm rule; split double bars get equal stems
    for i in (9,10,11): trim_stem(f"jung{i:02d}_base",'o')
    for i in (14,15,16): trim_stem(f"jung{i:02d}_base",'u')
    equalize_bars('jung10_bar'); equalize_bars('jung15_bar')
