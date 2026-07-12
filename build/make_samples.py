"""Regenerate the README sample images from the built TTFs."""
from PIL import Image, ImageDraw, ImageFont
import os
OUT="../samples"; os.makedirs(OUT, exist_ok=True)
LH="Lightheaded-Regular.ttf"

def sheet(path, blocks, pad=28, bg=255):
    """blocks: list of (fontpath,size,color,text) — multiline supported."""
    imgs=[]
    for fp,size,col,text in blocks:
        f=ImageFont.truetype(fp,size)
        d=ImageDraw.Draw(Image.new('L',(10,10)))
        lines=text.split("\n")
        w=max(int(d.textlength(l,font=f)) for l in lines)+2*pad
        lh=int(size*1.42)
        im=Image.new('L',(w,lh*len(lines)+pad),bg)
        dr=ImageDraw.Draw(im)
        for i,l in enumerate(lines):
            dr.text((pad,pad//2+i*lh), l, font=f, fill=col)
        imgs.append(im)
    W=max(i.width for i in imgs)
    H=sum(i.height for i in imgs)
    out=Image.new('L',(W,H),bg); y=0
    for i in imgs:
        out.paste(i,(0,y)); y+=i.height
    out.save(path); print(path, out.size)

# 1) paragraph
sheet(f"{OUT}/paragraph.png", [
    (LH,64,0,"다람쥐 헌 쳇바퀴에 타고파. 동해 물과 백두산이\n"
             "마르고 닳도록, 하느님이 보우하사 우리나라 만세.\n"
             "The quick brown fox jumps over the lazy dog."),
    (LH,44,0,"손글씨 폰트 «Lightheaded» — 한글 11,172자 + Latin.\n"
             "웃는 얼굴로 쓴 손글씨, 가볍고 고른 굵기의 글꼴입니다.\n"
             "Handwriting with an even, lightheaded stroke. 0123456789"),
])

# 2) consistency — includes this round's pain points
sheet(f"{OUT}/consistency.png", [
    (LH,72,0,"쳐켜펴텨져쳬쥐귀위퀴의화왜웨줘"),
    (LH,72,0,"크트츠스므프흐고호손곰몸폰트"),
    (LH,72,0,"가나다라마바사아자차카타파하"),
    (LH,72,0,"강낭담랑망밥샀았잦찾캌탙팦핳"),
    (LH,44,0,"글자 크기와 굵기가 고르게 — 받침도 몸에 붙게.\n"
             "weight & block size consistent across all syllables"),
])

# 3) frequency sheet — most-used syllables for eyeballing awkward ones
freq=("가강같거게겠고과관그근글금기길김나난날남내너네년노는니다단달담대더데도동되된두드든들등디따때또"
      "라란러런레려로록론료루르른를리린마만말맘매머먼메면명몇모목무문물뭐미민바반받발밤방배버번벌법베변별"
      "보본볼부분불비빠사산살상새생서선설성세소속손수순술스습시식신실싶써아안않알았야약양어언얼업없었에여"
      "역연영예오온올와완왜외요용우운울워원월위유으은을음의이인일임입있자작잘잠장재저적전점정제조존좀종주"
      "준줄중즉지진질집짜쪽차찾책처천철첫청체쳐초최추출충치카크큰클키타태터테토통투트특티파판퍼페편평포표"
      "푸품프피하학한할함합항해했행혀현형호혹화확환활회효후훈흐히힘")
rows=[freq[i:i+28] for i in range(0,len(freq),28)]
words="쳐다보다 크게 웃다 폰트 만들기 귀여운 쥐 화요일 왜냐하면 의외로 괜찮아 뭘 봐 죽 먹자"
sheet(f"{OUT}/frequency-sheet.png",
      [(LH,54,0,"\n".join(rows)),(LH,54,0,words)])

# 4) commercial compare
NOTO="reffonts/NotoSansKR-Regular.otf"; NANUM="reffonts/NanumGothic-Regular.ttf"
line="쳐다본 크기의 손글씨 폰트 — 귀엽고 고르게 123 abc"
sheet(f"{OUT}/commercial-compare.png", [
    (LH,58,0,"Lightheaded   "+line),
    (NOTO,58,0,"Noto Sans KR  "+line),
    (NANUM,58,0,"NanumGothic   "+line),
])

# 5) gray-value heatmap: per-syllable ink coverage vs sheet mean
import numpy as np
def coverage(f,ch,px=160):
    im=Image.new('L',(px*2,px*2),255)
    ImageDraw.Draw(im).text((px//2,px//2),ch,font=f,fill=0)
    a=np.asarray(im)<128
    if not a.any(): return 0
    ys,xs=np.where(a)
    return a.sum()/((xs.max()-xs.min()+1)*(ys.max()-ys.min()+1))
def heatmap(path, chars, cols=28, cell=64):
    f=ImageFont.truetype(LH, int(cell*0.78))
    covs={ch:coverage(f,ch) for ch in chars}
    m=np.mean(list(covs.values()))
    rows=(len(chars)+cols-1)//cols
    im=Image.new('RGB',(cols*cell+20, rows*cell+70),(255,255,255))
    d=ImageDraw.Draw(im)
    for i,ch in enumerate(chars):
        x=10+(i%cols)*cell; y=10+(i//cols)*cell
        dev=(covs[ch]-m)/m
        if   dev> 0.25: bg=(255,150,150)     # notably darker
        elif dev> 0.15: bg=(255,215,160)
        elif dev<-0.25: bg=(165,190,255)     # notably lighter
        elif dev<-0.15: bg=(205,225,255)
        else: bg=(246,246,246)
        d.rectangle([x,y,x+cell-2,y+cell-2], fill=bg)
        d.text((x+cell*0.10,y+cell*0.02), ch, font=f, fill=(20,20,20))
    d.text((12, rows*cell+22),
           f"gray-value proof: mean ink {m*100:.0f}%  |  colored = >15% / >25% off mean "
           f"(structural density of dense/sparse jamo)", fill=(60,60,60))
    im.save(path); print(path, im.size)
freqs=freq+"까따빠싸짜뚫짧닭않옳읽값웩귀쥐뭘"
heatmap(f"{OUT}/gray-heatmap.png", freqs)

# 6) weight family showcase
import os as _os
if all(_os.path.exists(f"Lightheaded-{s}.ttf") for s in ("Light","Regular","Bold")):
    sheet(f"{OUT}/weights.png", [
        ("Lightheaded-Light.ttf",  58,0,"Light    — 가벼운 손글씨 폰트 Lightheaded 0123 Aa"),
        ("Lightheaded-Regular.ttf",58,0,"Regular — 가벼운 손글씨 폰트 Lightheaded 0123 Aa"),
        ("Lightheaded-Bold.ttf",   58,0,"Bold     — 가벼운 손글씨 폰트 Lightheaded 0123 Aa"),
    ])
