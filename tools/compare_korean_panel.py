"""Where Lightheaded sits among Korean fonts on everything that was tuned."""
import glob, os, statistics as st
from fontTools.ttLib import TTFont
from PIL import Image, ImageDraw, ImageFont

SAMPLE = [0xAC00+li*588+vi*28+ti for li in range(0,19,2) for vi in range(0,21,2) for ti in (0,4,8,21)]

def metrics(path):
    f=TTFont(path); glyf=f['glyf']; cm=f.getBestCmap(); hm=f['hmtx']
    k=1000/f['head'].unitsPerEm
    adv=[]; w=[]; h=[]; top=[]; bot=[]; left=[]; right=[]
    for cp in SAMPLE:
        n=cm.get(cp)
        if not n: continue
        g=glyf[n]
        if g.numberOfContours==0: continue
        g.recalcBounds(glyf)
        a=hm[n][0]*k
        adv.append(a); w.append((g.xMax-g.xMin)*k); h.append((g.yMax-g.yMin)*k)
        top.append(g.yMax*k); bot.append(g.yMin*k)
        left.append(g.xMin*k); right.append(a-g.xMax*k)
    if not adv: return None
    return dict(adv=st.median(adv), ink=st.median(w), fill=st.median(w)/st.median(adv),
                top=st.median(top), topsd=st.pstdev(top), bot=st.median(bot),
                left=st.median(left), right=st.median(right),
                edgesd=(st.pstdev(left)+st.pstdev(right))/2, n=len(adv))

def stroke(path):
    """Rendered stroke weight and its spread, measured on the raster."""
    PX=200; ft=ImageFont.truetype(path,PX)
    per=[]
    for ch in "가나다라마바사아자차카타파하고구그기간갈감강":
        im=Image.new("L",(PX*2,PX*2),0); ImageDraw.Draw(im).text((PX//3,PX//3),ch,font=ft,fill=0 if False else 255)
        px=im.load(); runs=[]
        for y in range(im.height):
            n=0
            for x in range(im.width):
                if px[x,y]>110: n+=1
                elif n: runs.append(n); n=0
            if n: runs.append(n)
        for x in range(im.width):
            n=0
            for y in range(im.height):
                if px[x,y]>110: n+=1
                elif n: runs.append(n); n=0
            if n: runs.append(n)
        runs=sorted(r for r in runs if r>1)
        if len(runs)<8: continue
        t=runs[len(runs)//5]; band=[r for r in runs if 0.5*t<=r<=2.5*t]
        per.append(st.median(band)/PX*1000)
    return st.median(per), st.pstdev(per)/st.median(per)

def final_ratio(path):
    PX=300; ft=ImageFont.truetype(path,PX); out=[]
    for ch in "랄갈알물간감강":
        im=Image.new("L",(PX*2,PX*2),0); ImageDraw.Draw(im).text((PX//2,PX//2),ch,font=ft,fill=255)
        px=im.load()
        rows=[y for y in range(im.height) if any(px[x,y]>110 for x in range(im.width))]
        if not rows: continue
        lo,hi=min(rows),max(rows); h=hi-lo
        empty=[y for y in range(lo,hi+1) if not any(px[x,y]>110 for x in range(im.width))]
        runs=[]; start=prev=None
        for y in empty:
            if prev is None or y!=prev+1:
                if start is not None: runs.append((start,prev))
                start=y
            prev=y
        if start is not None: runs.append((start,prev))
        low=[r for r in runs if (r[0]-lo)>h*0.5]
        if low:
            s=max(low,key=lambda t:t[1]-t[0])[1]
            out.append((hi-s)/(s-lo))
    return st.median(out) if out else None

FONTS=[("Lightheaded v2.400","v8.ttf"),("Lightheaded v2.300","cur.ttf")] + sorted(
    (os.path.basename(p)[:-4], p) for p in glob.glob("ref/*.ttf"))
print(f"{'font':20}{'adv':>6}{'ink':>6}{'fill':>6}{'top':>6}{'topσ':>6}{'bot':>6}"
      f"{'edgeσ':>7}{'pen':>6}{'penσ/m':>8}{'final':>7}")
for name,path in FONTS:
    try:
        m=metrics(path)
        if not m: print(f"{name:20} (no Hangul)"); continue
        pen,psd=stroke(path); fr=final_ratio(path)
        print(f"{name:20}{m['adv']:6.0f}{m['ink']:6.0f}{m['fill']:6.2f}{m['top']:6.0f}"
              f"{m['topsd']:6.1f}{m['bot']:6.0f}{m['edgesd']:7.1f}{pen:6.0f}{psd:8.3f}"
              f"{(fr if fr else 0):7.2f}")
    except Exception as e:
        print(f"{name:20} ERROR {e}")
