#!/usr/bin/env python3
"""Read publicly accessible guide table facts. Do not bypass access controls."""
import json,re,datetime,urllib.request,urllib.parse,hashlib,concurrent.futures
from pathlib import Path
from bs4 import BeautifulSoup
P={"warrior":["arms","fury","protection"],"paladin":["holy","protection","retribution"],"hunter":["beast-mastery","marksmanship","survival"],"rogue":["assassination","combat","subtlety"],"priest":["discipline","holy","shadow"],"shaman":["elemental","enhancement","restoration"],"mage":["arcane","fire","frost"],"warlock":["affliction","demonology","destruction"],"druid":["balance","feral-cat","feral-bear","restoration"]}
def url(c,s):
    if s=="feral-cat": return "https://www.wowhead.com/forever/ko/guide/classes/druid/feral/bis-gear-dps"
    if s=="feral-bear": return "https://www.wowhead.com/forever/ko/guide/classes/druid/feral/bis-gear-tank"
    return "https://www.wowhead.com/forever/ko/guide/classes/"+c+"/"+s+"/bis-gear"
def item(a):
    href=a.get("href","")
    m=re.search(r"(?:item=|item%3D)(\d+)",href,re.I)
    if m:return int(m[1])
def clean(s,n=160):return re.sub(r"\s+"," ",s).strip()[:n]
def slot(t):
    for p,k in [(r"non.dagger.*main.hand|slow weapons","MainHand"),(r"dagger.*main.hand|1h dagger","MainHand"),(r"two.hand","TwoHand"),(r"off.hand","OffHand"),(r"main.hand|one.hand","MainHand"),(r"head|helm|머리","Head"),(r"shoulder|어깨","Shoulder"),(r"back|cloak|망토","Back"),(r"chest|가슴","Chest"),(r"wrist|손목","Wrist"),(r"hand armor|glove|손 장비","Hands"),(r"waist|belt|허리","Waist"),(r"legs|다리","Legs"),(r"feet|boots|발","Feet"),(r"neck|목걸이","Neck"),(r"ring|반지","Finger"),(r"trinket|장신구","Trinket"),(r"idol|totem|libram|relic|성물","Relic"),(r"wand|ranged|원거리","Ranged")]:
        if re.search(p,t,re.I):return k
def rank(s):
    x=s.casefold()
    if "bis" in x:return 1
    if "great" in x:return 2
    if "good" in x:return 3
    if "option" in x or "situational" in x:return 4
def parse(raw,u,c,s):
    soup=BeautifulSoup(raw,"html.parser")
    title=soup.title.get_text(" ",strip=True) if soup.title else ""
    if "forever" not in title.casefold() or not ("bis" in title.casefold() or "best in slot" in title.casefold()):raise ValueError("unexpected guide page")
    rows=[]
    for t in soup.find_all("table"):
        trs=t.find_all("tr")
        if not trs:continue
        hs=[clean(a.get_text(" ",strip=True)).casefold() for a in trs[0].find_all(["th","td"],recursive=False)]
        if len(hs)<3:continue
        mode="tier" if "rank" in hs[0] or "순위" in hs[0] else "set" if hs[0] in ("slot","부위") else None
        if not mode:continue
        heading=t.find_previous(["h2","h3","h4"])
        h=clean(heading.get_text(" ",strip=True) if heading else "")
        for tr in trs[1:]:
            td=tr.find_all(["th","td"],recursive=False)
            if len(td)<3:continue
            first=clean(td[0].get_text(" ",strip=True))
            k=slot(h if mode=="tier" else first)
            r=rank(first) if mode=="tier" else None
            if not k or (mode=="tier" and not r):continue
            for a in td[1].find_all("a"):
                i=item(a)
                if not i:continue
                n=clean(a.get_text(" ",strip=True),120)
                if not n:continue
                src=clean(td[2].get_text(" ",strip=True),180)
                rows.append(dict(id=i,slot=k,mode=mode,tier=r,name=n,acquisition=src,category=first if mode=="tier" else "",heading=h if mode=="tier" else first,url=u))
    if len(rows)<12:raise ValueError("no usable guide item table, "+str(len(rows)))
    return rows
def job(p):
    c,s=p;u=url(c,s)
    try:
        req=urllib.request.Request(u,headers={"User-Agent":"ForeverBiSAudit/0.9 (public guide item table facts)"})
        with urllib.request.urlopen(req,timeout=18) as r:
            if urllib.parse.urlsplit(r.geturl()).hostname!="www.wowhead.com":raise ValueError("unexpected redirect")
            raw=r.read(8_000_001)
        if len(raw)>8_000_000:raise ValueError("oversize response")
        rows=parse(raw,u,c,s)
        return c+":"+s,rows,{"rows":len(rows),"sha256":hashlib.sha256(raw).hexdigest(),"url":u}
    except Exception as e:return c+":"+s,[],{"error":str(e)[:240],"url":u}
def main():
    # Modest bounded parallelism, no bypass or repeat on access-denied responses.
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:res=list(ex.map(job,[(c,s) for c,ss in P.items() for s in ss]))
    path=Path("bis-sync/wowhead_evidence.json")
    old=json.loads(path.read_text()) if path.exists() else {"profiles":{}}
    for k,rows,diag in res:
        if rows:old["profiles"][k]=rows
    old["checked"]=datetime.date.today().isoformat()
    old["report"]={k:d for k,_,d in res}
    path.write_text(json.dumps(old,ensure_ascii=False,separators=(",",":"))+"\n",encoding="utf-8")
    print(json.dumps({"coverage":len(old["profiles"]),"report":old["report"]},ensure_ascii=False))
if __name__=="__main__":main()
