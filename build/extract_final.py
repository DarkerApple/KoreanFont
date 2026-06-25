import numpy as np, os, json
from collections import deque
from PIL import Image
from spec import PAGES, CHO, JUNG, JONG
from geom_fixed import GEOM

OUT="glyphs"; os.makedirs(OUT, exist_ok=True)
UP=3                       # upscale factor for smooth tracing
MARGIN_FR=0.06             # write-box right portion fraction of a pair
PAIR_WRITE=(0.515,0.995)   # write box spans this fraction of a pair column

def gid(g):
    role,v=g
    if role=='uni':  return f"uni{v:04X}", role, v, chr(v)
    if role=='cho':  return f"cho{v:02d}", role, ord(CHO[v]), CHO[v]
    if role=='jung': return f"jung{v:02d}", role, ord(JUNG[v]), JUNG[v]
    if role=='jong': return f"jong{v:02d}", role, ord(JONG[v]), JONG[v]

def components(mask):
    H,W=mask.shape; lab=np.zeros((H,W),np.int32); comps=[]; cur=0
    for sy in range(H):
        for sx in range(W):
            if mask[sy,sx] and lab[sy,sx]==0:
                cur+=1; q=deque([(sy,sx)]); lab[sy,sx]=cur
                minx=maxx=sx; miny=maxy=sy; cnt=0; px=[]
                while q:
                    y,x=q.popleft(); cnt+=1; px.append((y,x))
                    minx=min(minx,x);maxx=max(maxx,x);miny=min(miny,y);maxy=max(maxy,y)
                    for dy,dx in((1,0),(-1,0),(0,1),(0,-1),(1,1),(1,-1),(-1,1),(-1,-1)):
                        ny,nx=y+dy,x+dx
                        if 0<=ny<H and 0<=nx<W and mask[ny,nx] and lab[ny,nx]==0:
                            lab[ny,nx]=cur; q.append((ny,nx))
                comps.append(dict(bbox=(minx,miny,maxx,maxy),cnt=cnt,px=px))
    return comps

meta={}
for name,pagerows in PAGES.items():
    g=GEOM[name]; cx0,cx1=g['cx']; rows=g['rows']
    full=Image.open(f"raw/{name}.jpg").convert('L')
    W,H=full.size; pw=(cx1-cx0)/3.0
    bw=(PAIR_WRITE[1]-PAIR_WRITE[0])*pw           # write box width
    box_side=bw
    for ri,cells in enumerate(pagerows):
        cy=rows[ri]
        for ci,gg in enumerate(cells):
            name_id,role,cp,ch=gid(gg)
            px0=cx0+ci*pw+PAIR_WRITE[0]*pw
            bx0=px0; bx1=px0+bw
            bcx=(bx0+bx1)/2.0
            # nominal box square
            box=(bcx-box_side/2, cy-box_side/2, bcx+box_side/2, cy+box_side/2)
            # detection region = box + margin (capture overflow like descenders)
            mxp=int(box_side*0.10); myp=int(box_side*0.14)
            rx0=int(box[0]-mxp); ry0=int(box[1]-myp); rx1=int(box[2]+mxp); ry1=int(box[3]+myp)
            crop=full.crop((rx0,ry0,rx1,ry1))
            a=np.asarray(crop).astype(np.float32)          # native res (fast)
            Hc,Wc=a.shape; area=Hc*Wc
            white=np.percentile(a,75)                       # box background level
            T=white-52.0                                    # pen is far below bg; guides/border are not
            ink=a<T
            rec=dict(page=name,role=role,cp=cp,char=ch,empty=True)
            comps=components(ink)
            # nominal box bounds within the detection region (native px)
            bL=box[0]-rx0; bT=box[1]-ry0; bR=box[2]-rx0; bB=box[3]-ry0
            keep=np.zeros_like(ink); kept=0
            for c in comps:
                mnx,mny,mxx,mxy=c['bbox']; w=mxx-mnx+1; h=mxy-mny+1
                if c['cnt'] < max(6, 0.0004*area):          # speckle
                    continue
                touches_all = (mnx<=2 and mny<=2 and mxx>=Wc-3 and mxy>=Hc-3)
                if touches_all and c['cnt']<0.45*w*h:       # hollow box-frame outline
                    continue
                # drop neighbour-cell leaks: component lying wholly outside the box
                if (mxx<=bL+3 or mnx>=bR-3 or mxy<=bT+3 or mny>=bB-3):
                    continue
                for (y,x) in c['px']: keep[y,x]=True
                kept+=c['cnt']
            if kept>=70:
                ys,xs=np.where(keep)
                iy0,iy1,ix0,ix1=int(ys.min()),int(ys.max()),int(xs.min()),int(xs.max())
                # smooth glyph: keep grayscale on ink pixels, upscale, re-threshold
                clean=np.where(keep, a, 255.0).astype(np.uint8)
                sub=clean[iy0:iy1+1, ix0:ix1+1]
                im=Image.fromarray(sub).resize(((ix1-ix0+1)*UP,(iy1-iy0+1)*UP), Image.BICUBIC)
                arr=np.asarray(im).astype(np.float32)
                g_img=np.where(arr<T, 0, 255).astype(np.uint8)
                Image.fromarray(g_img).save(f"{OUT}/{name_id}.png")
                off_x=(box[0]-rx0); off_y=(box[1]-ry0)
                nx0=(ix0-off_x)/box_side; nx1=(ix1+1-off_x)/box_side
                ny0=(iy0-off_y)/box_side; ny1=(iy1+1-off_y)/box_side
                rec.update(empty=False, box_rel=[nx0,ny0,nx1,ny1],
                           ink_px=[int(ix1-ix0+1),int(iy1-iy0+1)])
            meta[name_id]=rec
    print(name,"done")
json.dump(meta, open("meta.json","w"), ensure_ascii=False)
n_ok=sum(1 for v in meta.values() if not v['empty']); n_em=sum(1 for v in meta.values() if v['empty'])
print("TOTAL glyphs:",len(meta)," extracted:",n_ok," empty:",n_em)
print("empty ones:", [k for k,v in meta.items() if v['empty']])
