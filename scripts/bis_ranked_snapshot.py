#!/usr/bin/env python3
"""Read public pre-raid ranking facts, not guide prose or third-party addon code."""
from __future__ import annotations
import argparse, concurrent.futures, datetime as dt, hashlib, json, re, time, urllib.request, urllib.parse
from pathlib import Path
from bs4 import BeautifulSoup

PROFILES = {
 "WARRIOR":["arms","fury","protection"], "PALADIN":["holy","protection","retribution"],
 "HUNTER":["beast-mastery","marksmanship","survival"], "ROGUE":["assassination","combat","subtlety"],
 "PRIEST":["discipline","holy","shadow"], "SHAMAN":["elemental","enhancement","restoration"],
 "MAGE":["arcane","fire","frost"], "WARLOCK":["affliction","demonology","destruction"],
 "DRUID":["balance","feral-cat","feral-bear","restoration"],
}
SLUG={"beast-mastery":"beastmastery","feral-cat":"feralcat","feral-bear":"feralbear"}
SLOTS={"head":"Head","neck":"Neck","shoulder":"Shoulder","shoulders":"Shoulder","back":"Back","cloak":"Back","chest":"Chest","wrist":"Wrist","wrists":"Wrist","hand":"Hands","hands":"Hands","waist":"Waist","legs":"Legs","feet":"Feet","finger":"Finger","fingers":"Finger","ring":"Finger","rings":"Finger","trinket":"Trinket","trinkets":"Trinket","main hand":"MainHand","mainhand":"MainHand","off hand":"OffHand","offhand":"OffHand","two hand":"TwoHand","two handed":"TwoHand","twohand":"TwoHand","ranged":"Ranged","relic":"Relic"}
ITEM_ID=re.compile(r"(?:[?&]item=|/items?[/=](?:#item-)?|\bitem:)([1-9]\d{2,8})(?!\d)",re.I)
SOURCE=re.compile(r"\b(Crafted|Crafting|Drop|Quest|Vendor|Reputation|Container|World Drop|PvP|Source)\s*(?::\s*|(?=·|$))",re.I)
BAD=re.compile(r"unconfirmed in forever|stats from classic|source unknown|unknown source|raid.gated|not yet available",re.I)
RAID=re.compile(r"\b(molten core|onyxia|blackwing lair|naxxramas|ahn.qiraj|zul.gurub|world boss)\b",re.I)
PVP=re.compile(r"alterac valley|stormpike|frostwolf|warsong|arathi basin|defilers|league of arathor|honor rank|battleground",re.I)
PROF={"blacksmithing":"대장기술","leatherworking":"가죽세공","tailoring":"재봉술","engineering":"기계공학","alchemy":"연금술","enchanting":"마법부여","jewelcrafting":"보석세공"}
ZONE={"Blackrock Depths":"검은바위 나락","Blackrock Spire":"검은바위 첨탑","Stratholme":"스트라솔름","Scholomance":"스칼로맨스","Dire Maul":"혈투의 전장","Maraudon":"마라우돈","Ironforge":"아이언포지","Orgrimmar":"오그리마","Stranglethorn Vale":"가시덤불 골짜기","Western Plaguelands":"서부 역병지대","Eastern Plaguelands":"동부 역병지대","Hinterlands":"동부 내륙지","Azshara":"아즈샤라","Alterac Valley":"알터랙 계곡"}
def clean(s,n=220):
    return re.sub(r"[\s\x00-\x1f|]+"," ",str(s)).strip()[:n]
def url_for(c,s): return "https://foreverwow.gg/"+c.lower()+"/"+SLUG.get(s,s)+"/pre-raid/"
def get(url):
    if urllib.parse.urlsplit(url).hostname not in {"foreverwow.gg","raw.githubusercontent.com"}:raise ValueError("invalid host")
    req=urllib.request.Request(url,headers={"User-Agent":"ForeverBiSAudit/0.8 public pre-raid facts; repository howonses-cyber/forever-custom-addons","Accept":"text/html,application/json"})
    with urllib.request.urlopen(req,timeout=35) as r:
        if urllib.parse.urlsplit(r.geturl()).hostname!=urllib.parse.urlsplit(url).hostname:raise ValueError("unexpected redirect")
        raw=r.read(12_000_001)
    if len(raw)>12_000_000 or not raw:raise ValueError("bad response size")
    return raw
def item_id(tag):
    for k in ("data-item-id","data-itemid","data-wowhead","href","data-item"):
        v=str(tag.get(k,""));m=ITEM_ID.search(v)
        if m:return int(m.group(1))
        if v.isdigit() and 100<=int(v)<=999999999:return int(v)
    return None
def slot_for(x):
    s=re.sub(r"[_-]+"," ",str(x).lower()).strip()
    if s.startswith("slot "):s=s[5:]
    return SLOTS.get(s)
def local_source(s):
    s=clean(s,240)
    m=SOURCE.search(s)
    if not m:return "획득처 세부 미확인" if not s else s
    label={"crafted":"제작","crafting":"제작","drop":"전리품","quest":"퀘스트","vendor":"상인","reputation":"평판","container":"상자","world drop":"월드 드롭","pvp":"PvP","source":"출처"}.get(m.group(1).lower(),"출처")
    tail=s[m.end():].strip(" ·:")
    for en,ko in PROF.items():tail=re.sub(r"\b"+re.escape(en)+r"\b",ko,tail,flags=re.I)
    for en,ko in ZONE.items():tail=tail.replace(en,ko)
    tail=tail.replace("Alliance only","얼라이언스 전용").replace("Horde only","호드 전용").replace("unconfirmed in Forever","포에버 획득 미확인").replace("reputation required","평판 필요")
    return label+(" · "+tail if tail else "")
def parse(html,c,s):
    soup=BeautifulSoup(html,"html.parser")
    title=clean(soup.title.get_text(" ",strip=True) if soup.title else "",200)
    main=soup.find("main") or soup.find("article") or soup.body or soup
    intro=(title+" "+main.get_text(" ",strip=True)[:2600]).lower()
    tokens=[c.lower()]+s.split("-")
    if not all(t in intro for t in tokens) or "pre-raid" not in intro or not ("bis" in intro or "best in slot" in intro):
        raise ValueError("wrong ranking page: "+title)
    rows=[];seen=set();coverage=set()
    for section in main.find_all("section"):
        slot=slot_for(section.get("id") or section.get("data-slot") or "")
        if not slot or slot in coverage:continue
        ol=section.find("ol")
        if not ol:continue
        local=[]
        for idx,li in enumerate(ol.find_all("li",recursive=False)[:10],1):
            summary=li.find("summary") or li
            summary_text=clean(summary.get_text(" ",strip=True),500)
            found=None
            for a in summary.find_all("a"):
                id=item_id(a);name=clean(a.get_text(" ",strip=True),120)
                if id and name and len(name)>2 and not re.fullmatch(r"[\d%]+",name):found=(id,name);break
            if not found:continue
            id,name=found
            if (slot,id) in seen:continue
            # Explicit list order, never fabricate an item's rank after filtering.
            prefix=re.match(r"^\s*(\d+)[.)]\s*",summary_text)
            rank=int(prefix.group(1)) if prefix else idx
            if not 1<=rank<=10:continue
            score=re.search(r"\b(\d{1,3}(?:\.\d+)?)%\b?",summary_text) if False else re.search(r"(\d{1,3}(?:\.\d+)?)\s*%",summary_text)
            # Retain only acquisition facts, not guide commentary or tooltip prose.
            match=SOURCE.search(summary_text)
            source=summary_text[match.start():] if match else ""
            source=re.split(r"\s+\d{1,3}(?:\.\d+)?\s*%",source,1)[0]
            source=clean(source,200)
            full=clean(li.get_text(" ",strip=True),1800)
            faction="Alliance" if "alliance only" in full.lower() else "Horde" if "horde only" in full.lower() else "Both"
            status="locked" if RAID.search(source) else "unknown" if BAD.search(full) or not source else "reference"
            if PVP.search(source): status="unknown" if status!="locked" else status
            if not source:source="획득처 확인 필요"
            row={"class":c,"spec":s,"slot":slot,"itemId":id,"name":name,"rank":rank,"source":source,"sourceKo":local_source(source),"status":status,"faction":faction,"url":url_for(c,s)}
            if score and 0<=float(score.group(1))<=100:row["rankScore"]=float(score.group(1))
            # Base item ID cannot identify a random-suffix roll: preserve limitation.
            if re.search(r" of the (Bear|Tiger|Monkey|Eagle|Owl|Wolf|Gorilla|Falcon|Boar|Whale|Fox)$",name,re.I):row["variant"]=True
            local.append(row);seen.add((slot,id))
        if local:rows.extend(local);coverage.add(slot)
    if len(coverage)<10 or len(rows)<25:
        raise ValueError(f"low ranking coverage: {len(coverage)} slots / {len(rows)} rows; title {title}; sections "+str([(x.get("id"),x.get("data-slot")) for x in main.find_all("section")[:15]]))
    return rows,{"spec":c+":"+s,"slots":len(coverage),"rows":len(rows),"title":title,"htmlSha256":hashlib.sha256(html.encode()).hexdigest()}
def field(d,*keys,default=None):
    for k in keys:
        if k in d:return d[k]
    return default
def enrich(rows,db):
    items={int(x["id"]):x for x in db.get("items",[]) if x.get("id")}
    zones={int(x["id"]):clean(x.get("name","")) for x in db.get("zones",[]) if x.get("id")}
    npcs={int(x["id"]):x for x in db.get("npcs",[]) if x.get("id")}
    factions={int(x["id"]):clean(x.get("name","")) for x in db.get("factions",[]) if x.get("id")}
    matched=0
    for row in rows:
        item=items.get(row["itemId"])
        if not item:continue
        matched+=1
        lv=field(item,"reqLvl","req_lvl",default=0)
        if isinstance(lv,int) and 0<lv<=60:row["requiredLevel"]=lv
        phase=field(item,"phase")
        if phase in (2,"ContentPhaseUnknown"):row["phaseUnknown"]=True
        side=field(item,"factionRestriction","faction_restriction")
        if side in (1,"FACTION_RESTRICTION_ALLIANCE_ONLY"):row["faction"]="Alliance"
        elif side in (2,"FACTION_RESTRICTION_HORDE_ONLY"):row["faction"]="Horde"
        st=field(item,"setName","set_name")
        if st:row["setName"]=clean(st,100)
        details=[]
        for src in item.get("sources",[])[:8]:
            for k,d in src.items():
                if not isinstance(d,dict):continue
                zone=zones.get(field(d,"zoneId","zone_id"),"");nid=field(d,"npcId","npc_id");npc=npcs.get(nid,{})
                if not zone:zone=zones.get(field(npc,"zoneId","zone_id"),"")
                zone=ZONE.get(zone,zone)
                name=clean(field(d,"npcName","npc_name","name","otherName","other_name",default="") or npc.get("name",""),120)
                if k=="drop":
                    if field(d,"difficulty") in (2,"DifficultyRaid"):continue
                    line="전리품 · "+" / ".join(x for x in [zone,name] if x)
                elif k=="quest":line="퀘스트 · "+" / ".join(x for x in [zone,name] if x)
                elif k in ("soldBy","sold_by"):line="상인 · "+" / ".join(x for x in [zone,name] if x)
                elif k=="rep":
                    rep=factions.get(field(d,"repFactionId","rep_faction_id"),"");level=field(d,"repLevel","rep_level")
                    lvl={5:"약간 우호",6:"우호",7:"매우 우호",8:"확고한 동맹","RepLevelHonored":"우호","RepLevelRevered":"매우 우호","RepLevelExalted":"확고한 동맹"}.get(level,"")
                    line="평판 · "+" / ".join(x for x in [rep,lvl] if x)
                elif k=="crafted":line="제작 · "+PROF.get(str(d.get("profession","")).lower().replace("profession",""),"제작법 상세 확인")
                else:continue
                if line.strip(" ·") not in ("전리품","퀘스트","상인","평판") and line not in details:details.append(line)
        if details:row["details"]="\n".join(details[:4])
    return matched
def main():
    p=argparse.ArgumentParser();p.add_argument("--out",default="bis-sync/ranked_snapshot.json");p.add_argument("--report",default="bis-sync/ranked_report.json");args=p.parse_args()
    jobs=[(c,s) for c,ss in PROFILES.items() for s in ss]
    def run(x):
        c,s=x;u=url_for(c,s)
        try:return parse(get(u).decode("utf-8","replace"),c,s)
        except Exception as e:return [],{"spec":c+":"+s,"error":str(e)[:500],"url":u}
    with concurrent.futures.ThreadPoolExecutor(max_workers=3) as ex:results=list(ex.map(run,jobs))
    rows=[r for rr,_ in results for r in rr];report=[d for _,d in results]
    # Use open MIT source data for zone/name enrichment; preserve website attribution.
    db_info={}
    try:
        u="https://raw.githubusercontent.com/wowsims/forever/master/assets/database/db.json"
        raw=get(u);db=json.loads(raw);db_info={"url":u,"sha256":hashlib.sha256(raw).hexdigest(),"matched":enrich(rows,db),"license":"MIT"}
    except Exception as e:db_info={"error":str(e)[:300]}
    now=dt.datetime.now(dt.timezone.utc).isoformat();coverage={"profiles":len([x for x in report if "rows" in x]),"expected":len(jobs),"rows":len(rows),"details":sum("details" in x for x in rows)}
    doc={"schema":2,"source":"ForeverWoW.gg pre-raid, slot order","checked":now[:10],"coverage":coverage,"database":db_info,"rows":rows}
    Path(args.report).parent.mkdir(parents=True,exist_ok=True)
    Path(args.report).write_text(json.dumps({"checked":now,"coverage":coverage,"profiles":report,"database":db_info},ensure_ascii=False,indent=2)+"\n","utf-8")
    print(json.dumps({"coverage":coverage,"errors":[x for x in report if "error" in x],"database":db_info},ensure_ascii=False))
    # Missing profiles never erase a previous good snapshot; partial acquisition is not a release.
    if coverage["profiles"]!=len(jobs):raise SystemExit("incomplete profile coverage; retain prior data")
    if not all(any(r["slot"]==slot and r["class"]==c and r["spec"]==s for r in rows) for c,s in jobs for slot in ("Head","Neck","Chest","Feet","Finger","Trinket")):raise SystemExit("missing mandatory gear sections")
    Path(args.out).write_text(json.dumps(doc,ensure_ascii=False,separators=(",",":"))+"\n","utf-8")
if __name__=="__main__":main()
