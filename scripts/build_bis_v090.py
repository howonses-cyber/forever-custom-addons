#!/usr/bin/env python3
"""Reproduce V0.9.0 from reviewed package plus its pinned source scores; validate with Lua 5.1/LuaJIT."""
from pathlib import Path
import hashlib,json,math,zipfile
from lupa import lua51,luajit21

BASE=Path("scripts/bis090/reviewed_base.zip")
SOURCE=Path("scripts/bis090/source_snapshot.json")
DEST=Path("addons/ForeverBiSAudit_Forever_v0.9.0_GuideRanks_KoreanAcquisition.zip")
OLD=Path("addons/ForeverBiSAudit_Forever_v0.8.0_RankedDropdown_ItemTooltips.zip")
PREFIX="ForeverBiSAudit/"
def sha(b):return hashlib.sha256(b).hexdigest()
def blob(b):return hashlib.sha1(b"blob "+str(len(b)).encode()+b"\0"+b).hexdigest()
base=BASE.read_bytes();raw=SOURCE.read_bytes()
assert sha(base)=="18845844e5ce40c124bf32cbce7430ee9eb4cc60e004b96b141bc369e3c2815b","staged ZIP hash"
assert blob(raw)=="86b0aeae119eab193ea436fb3f5ed7e56fd0ab10","pinned source hash"
doc=json.loads(raw)
def records(x):
    if isinstance(x,list):
        for v in x:yield from records(v)
    elif isinstance(x,dict):
        if all(k in x for k in ("class","spec","slot","itemId","rank","name")):yield x
        else:
            for v in x.values():yield from records(v)
def key(r):return ":".join(str(r[k]) for k in ("class","spec","slot","itemId","rank"))
mapping={}
for r in records(doc):
    k=key(r)
    val=r.get("rankScore")
    assert k not in mapping,("duplicate source key",k)
    assert val is None or (isinstance(val,(int,float)) and not isinstance(val,bool) and math.isfinite(val)),("score",k)
    mapping[k]=(r["name"],val)
assert len(mapping)==4283,("source rows",len(mapping))
with zipfile.ZipFile(BASE) as z:
    assert z.testzip() is None
    assert all(n.startswith(PREFIX) and ".." not in n.split("/") for n in z.namelist())
    data={n:z.read(n) for n in z.namelist()}
lua=lua51.LuaRuntime(unpack_returned_tuples=True)
b=lua.table()
lua.eval("function(s,b) return assert(loadstring(s))('ForeverBiSAudit',b) end")(data[PREFIX+"RankedData.lua"].decode(),b)
refkeys=set()
for i in range(1,len(b.catalog)+1):
    r=b.catalog[i]
    if r.mode=="reference":
        k=":".join(str(r[x]) for x in ("class","spec","slot","itemId","rank"))
        assert k in mapping and mapping[k][0]==r.name,("row source identity",k,r.name)
        assert k not in refkeys,("duplicate package key",k)
        refkeys.add(k)
assert refkeys==set(mapping)
scores={k:v[1] for k,v in mapping.items() if v[1] is not None}
assert len(scores)>0
code=["-- Source display scores from pinned 2026-11-27 snapshot. Not measured DPS or BiS.", "local _,B=...","local scores={"]
for k,v in sorted(scores.items()):code.append("["+json.dumps(k)+"]="+json.dumps(v)+",")
code+=["}","local n=0","for _,r in ipairs(B.catalog) do if r.mode=='reference' then local k=table.concat({r.class,r.spec,r.slot,r.itemId,r.rank},':');r.rankScore=scores[k];if r.rankScore~=nil then n=n+1 end end end","B.rankedMeta.sourceScores=n"]
data[PREFIX+"RankScores.lua"]=("\n".join(code)+"\n").encode()
toc=data[PREFIX+"ForeverBiSAudit.toc"].decode()
assert "## Version: 0.9.0" in toc
data[PREFIX+"ForeverBiSAudit.toc"]=toc.replace("RankedData.lua\n","RankedData.lua\nRankScores.lua\n",1).encode()
ui=data[PREFIX+"UI.lua"].decode()
data[PREFIX+"UI.lua"]=ui.replace("원본 스탯 점수","원본 사이트 표시 점수").encode()
data[PREFIX+"Docs/RankScoreProvenance.json"]=json.dumps({"source_blob":blob(raw),"rows":len(mapping),"display_scores":len(scores),"kind":"original website display score, not verified DPS or BiS"},ensure_ascii=False,indent=2).encode()+b"\n"
tmp=DEST.with_suffix(".tmp")
with zipfile.ZipFile(tmp,"w",zipfile.ZIP_DEFLATED,compresslevel=9) as z:
    for name,content in sorted(data.items()):
        info=zipfile.ZipInfo(name,date_time=(2026,1,1,0,0,0));info.compress_type=zipfile.ZIP_DEFLATED
        z.writestr(info,content,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
with zipfile.ZipFile(tmp) as z:
    assert z.testzip() is None
    assert all(z.read(n)==v for n,v in data.items())
    root=Path("verify_bis090");root.mkdir(exist_ok=True);z.extractall(root)
addon=(root/PREFIX).resolve().as_posix()+"/"
for module in (lua51,luajit21):
    L=module.LuaRuntime(unpack_returned_tuples=True)
    loader=L.eval("function(s) return assert(loadstring(s)) end")
    for name in toc.splitlines():
        if name.strip().endswith(".lua"):loader(data[PREFIX+name.strip()].decode())
    L.globals().ADDON_ROOT=addon
    L.execute("dofile(ADDON_ROOT..'tests/test_ranked.lua')")
    L.execute("dofile(ADDON_ROOT..'tests/test_v090.lua')")
    n=L.execute("local B={};assert(loadfile(ADDON_ROOT..'RankedData.lua'))('ForeverBiSAudit',B);assert(loadfile(ADDON_ROOT..'RankScores.lua'))('ForeverBiSAudit',B);return B.rankedMeta.sourceScores")
    assert n==len(scores)
    print("PASS",module.__name__,"TOC syntax, regression, source scores",n)
tmp.replace(DEST)
if OLD.exists():OLD.unlink()
print("VERIFIED V0.9.0",DEST,DEST.stat().st_size,sha(DEST.read_bytes()),"source scores",len(scores))
