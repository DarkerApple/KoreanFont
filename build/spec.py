# Logical layout of every page: ordered rows, each a list of glyph-ids.
# glyph-id: ('cho',i) ('jung',i) ('jong',i)  or ('uni', codepoint)
CHO=['ㄱ','ㄲ','ㄴ','ㄷ','ㄸ','ㄹ','ㅁ','ㅂ','ㅃ','ㅅ','ㅆ','ㅇ','ㅈ','ㅉ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']
JUNG=['ㅏ','ㅐ','ㅑ','ㅒ','ㅓ','ㅔ','ㅕ','ㅖ','ㅗ','ㅘ','ㅙ','ㅚ','ㅛ','ㅜ','ㅝ','ㅞ','ㅟ','ㅠ','ㅡ','ㅢ','ㅣ']
JONG=['ㄱ','ㄲ','ㄳ','ㄴ','ㄵ','ㄶ','ㄷ','ㄹ','ㄺ','ㄻ','ㄼ','ㄽ','ㄾ','ㄿ','ㅀ','ㅁ','ㅂ','ㅄ','ㅅ','ㅆ','ㅇ','ㅈ','ㅊ','ㅋ','ㅌ','ㅍ','ㅎ']

def chunk(lst,n=3):
    return [lst[i:i+n] for i in range(0,len(lst),n)]

def U(s): return ('uni', ord(s))

PAGES={}
PAGES['img00']=[[('cho',j) for j in row] for row in chunk(list(range(19)))]
PAGES['img01']=[[('jung',j) for j in row] for row in chunk(list(range(21)))]
PAGES['img02']=[[('jong',j) for j in row] for row in chunk(list(range(21)))]      # first 21
PAGES['img03']=[[('jong',j) for j in row] for row in chunk(list(range(21,27)))]   # last 6
PAGES['img04']=[[U(c) for c in row] for row in chunk(list("ABCDEFGHIJKLMNOPQRSTU"))]
PAGES['img05']=[[U(c) for c in row] for row in chunk(list("VWXYZ"))]
PAGES['img06']=[[U(c) for c in row] for row in chunk(list("abcdefghijklmnopqrstu"))]
PAGES['img07']=[[U(c) for c in row] for row in chunk(list("vwxyz"))] + \
               [[U(c) for c in row] for row in chunk(list("0123456789"))]
PAGES['img08']=[[U(c) for c in row] for row in
                [['.',',','!'],['?',':',';'],["'",'"','('],[')','[',']'],
                 ['{','}','-'],['_','/','\\'],['@','#','&']]]
PAGES['img09']=[[U(c) for c in row] for row in [['*','%','+'],['=','<','>'],['~']]]

def gid_name(gid):
    role,v=gid
    if role=='uni': return f"uni{v:04X}"
    if role=='cho': return f"cho{v:02d}_{CHO[v]}"
    if role=='jung': return f"jung{v:02d}_{JUNG[v]}"
    if role=='jong': return f"jong{v:02d}_{JONG[v]}"

if __name__=='__main__':
    tot=sum(len(r) for p in PAGES.values() for r in p)
    print("pages",len(PAGES),"total glyph cells", tot)
    for k,v in PAGES.items():
        print(k, "rows",len(v), "cells", sum(len(r) for r in v))
