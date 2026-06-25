import subprocess, re, os, tempfile
from PIL import Image

# ---- minimal SVG path parser (handles M/L/C/Z, abs+rel) ----
_num=re.compile(r'[-+]?[0-9]*\.?[0-9]+(?:[eE][-+]?[0-9]+)?')
def _tokpath(d):
    toks=re.findall(r'[MmLlHhVvCcSsZz]|'+_num.pattern, d)
    return toks

def parse_path(d):
    """Return list of contours; each contour = list of segments:
       ('move',(x,y)) ('line',(x,y)) ('curve',(c1,c2,(x,y)))."""
    toks=_tokpath(d); i=0; contours=[]; cur=None; cx=cy=0.0; sx=sy=0.0; cmd=None
    def num():
        nonlocal i; v=float(toks[i]); i+=1; return v
    while i<len(toks):
        t=toks[i]
        if t.isalpha():
            cmd=t; i+=1
        if cmd in('M','m'):
            x=num(); y=num()
            if cmd=='m': x+=cx; y+=cy
            cx,cy=x,y; sx,sy=x,y
            cur=[('move',(x,y))]; contours.append(cur)
            cmd='L' if cmd=='M' else 'l'
        elif cmd in('L','l'):
            x=num(); y=num()
            if cmd=='l': x+=cx; y+=cy
            cur.append(('line',(x,y))); cx,cy=x,y
        elif cmd in('H','h'):
            x=num();
            if cmd=='h': x+=cx
            cur.append(('line',(x,cy))); cx=x
        elif cmd in('V','v'):
            y=num()
            if cmd=='v': y+=cy
            cur.append(('line',(cx,y))); cy=y
        elif cmd in('C','c'):
            x1=num();y1=num();x2=num();y2=num();x=num();y=num()
            if cmd=='c':
                x1+=cx;y1+=cy;x2+=cx;y2+=cy;x+=cx;y+=cy
            cur.append(('curve',((x1,y1),(x2,y2),(x,y)))); cx,cy=x,y
        elif cmd in('Z','z'):
            cx,cy=sx,sy
        else:
            i+=1
    return contours

def trace_png(png_path, turdsize=4, alphamax=1.0, opttolerance=0.2):
    """potrace a black-on-white PNG -> (W,H, contours in image space y-down)."""
    im=Image.open(png_path).convert('1')
    W,H=im.size
    with tempfile.TemporaryDirectory() as td:
        bmp=os.path.join(td,'g.bmp'); svg=os.path.join(td,'g.svg')
        im.save(bmp)
        subprocess.run(['potrace',bmp,'-b','svg','-t',str(turdsize),
                        '-a',str(alphamax),'-O',str(opttolerance),
                        '--flat','-o',svg],check=True)
        s=open(svg).read()
    m=re.search(r'transform="translate\(([-0-9.]+),([-0-9.]+)\)\s*scale\(([-0-9.]+),([-0-9.]+)\)"', s)
    tx,ty,scx,scy=(0,0,0.1,-0.1)
    if m: tx,ty,scx,scy=map(float,m.groups())
    contours=[]
    for d in re.findall(r'<path[^>]*\bd="([^"]+)"', s):
        for c in parse_path(d):
            out=[]
            for seg in c:
                if seg[0]=='move': out.append(('move',_tf(seg[1],tx,ty,scx,scy)))
                elif seg[0]=='line': out.append(('line',_tf(seg[1],tx,ty,scx,scy)))
                else:
                    p1,p2,p3=seg[1]
                    out.append(('curve',(_tf(p1,tx,ty,scx,scy),_tf(p2,tx,ty,scx,scy),_tf(p3,tx,ty,scx,scy))))
            contours.append(out)
    return W,H,contours

def _tf(p,tx,ty,scx,scy):
    return (tx+p[0]*scx, ty+p[1]*scy)

# ---- signed area (shoelace, sampling curves coarsely) for winding checks ----
def contour_area(c):
    pts=[]
    for seg in c:
        if seg[0]=='move': pts.append(seg[1])
        elif seg[0]=='line': pts.append(seg[1])
        else: pts.append(seg[1][2])
    a=0.0; n=len(pts)
    for i in range(n):
        x0,y0=pts[i]; x1,y1=pts[(i+1)%n]; a+=x0*y1-x1*y0
    return a/2.0

if __name__=='__main__':
    import sys
    from PIL import ImageDraw
    tests=['cho00','jung00','jong20','uni0041','uni0061','uni0026','uni0040','uni0038','uni005C','uni0025']
    cell=200; sheet=Image.new('RGB',(cell*len(tests),cell*2),(255,255,255)); dd=ImageDraw.Draw(sheet)
    for k,gid in enumerate(tests):
        W,H,cs=trace_png(f'glyphs/{gid}.png')
        # original
        o=Image.open(f'glyphs/{gid}.png').convert('L'); s=min((cell-20)/o.width,(cell-20)/o.height)
        o=o.resize((int(o.width*s),int(o.height*s))); sheet.paste(o,(k*cell+10,10))
        # traced render (fill, y-down image space)
        img=Image.new('L',(W,H),255); d=ImageDraw.Draw(img)
        polys=[]
        for c in cs:
            pts=[]
            for seg in c:
                if seg[0] in('move','line'): pts.append(seg[1])
                else:
                    # sample cubic
                    x0,y0=pts[-1]; (x1,y1),(x2,y2),(x3,y3)=seg[1]
                    for t in [i/8 for i in range(1,9)]:
                        mt=1-t
                        x=mt**3*x0+3*mt*mt*t*x1+3*mt*t*t*x2+t**3*x3
                        y=mt**3*y0+3*mt*mt*t*y1+3*mt*t*t*y2+t**3*y3
                        pts.append((x,y))
            polys.append((contour_area(c),pts))
        polys.sort(key=lambda p:-abs(p[0]))
        for ar,pts in polys:
            fill=0 if ar==polys[0][0] else 255
            d.polygon(pts, fill=fill)
        s2=min((cell-20)/W,(cell-20)/H); img=img.resize((int(W*s2),int(H*s2)))
        sheet.paste(img,(k*cell+10,cell+10))
        dd.text((k*cell+10,cell-14),gid,fill=(200,0,0))
    sheet.save('trace_check.png'); print('saved trace_check.png  (top=source, bottom=traced)')
