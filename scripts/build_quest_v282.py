#!/usr/bin/env python3
"""Pin and rebuild the Forever Quest Guide V2.8.2 custom-addon artifact.

Source ZIP, Unicode diff, and output digest are fixed. No external addons,
WTF, characters, or user settings are read or modified. GitHub Actions runs
native Lua 5.1 / LuaJIT tests before public release and catalog promotion.
"""
from __future__ import annotations
import base64,gzip,hashlib,subprocess,tempfile,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parent.parent
ADDONS=ROOT/'addons'
BASE='ForeverQuestGuide_Forever_v2.8.1_EUI_Detail_Button_PositionFix.zip'
NEW='ForeverQuestGuide_Forever_v2.8.2_CompactList_ItemSources.zip'
PATCH='quest_v2.8.2.patch.gz.b64'
FOLDER='ForeverDungeonQuestGuide'
BASE_SHA='83a6fd847e9d85a7aec358e511868c260bf284a99cfdff26a752574b1c977583'
PATCH_SHA='df5ab689939c4a0d05f59e650d40fa291b2458584f74a290875e513348077790'
NEW_SHA='eb15ae3a42f7d5ae10c64bac4a44089a198436bae454d62584b1f0468f49ea42'
DATE=(2026,11,27,22,20,0)

def digest(b:bytes)->str:return hashlib.sha256(b).hexdigest()
def require(value:bool,what:str):
 if not value:raise RuntimeError(what)

def main()->None:
 base=ADDONS/BASE
 dest=ADDONS/NEW
 if dest.is_file() and not base.is_file():
  require(digest(dest.read_bytes())==NEW_SHA,'existing v2.8.2 changed')
  print('Verified existing V2.8.2 distribution',dest.name)
  return
 require(base.is_file(),'pinned V2.8.1 ZIP missing')
 require(digest(base.read_bytes())==BASE_SHA,'unexpected baseline ZIP digest')
 encoded=(ROOT/'scripts'/PATCH).read_text('ascii')
 patch=gzip.decompress(base64.b64decode(encoded.strip(),validate=True))
 require(digest(patch)==PATCH_SHA,'source patch integrity failed')
 with tempfile.TemporaryDirectory(prefix='fqg-v282-') as td:
  td=Path(td)
  with zipfile.ZipFile(base) as z:
   require(z.testzip() is None,'baseline CRC failure')
   for info in z.infolist():
    n=info.filename
    require(n.startswith(FOLDER+'/') and '..' not in Path(n).parts and not n.endswith('/'),'unsafe source path '+n)
    output=td/n
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(z.read(info))
  diff=td/'v282.patch';diff.write_bytes(patch)
  run=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(diff)],cwd=td/FOLDER,text=True,capture_output=True)
  require(run.returncode==0,'patch apply failed: '+run.stdout+run.stderr)
  src=td/FOLDER
  toc=(src/'ForeverDungeonQuestGuide.toc').read_text('utf-8')
  require('## Version: 2.8.2' in toc and 'QuestStartItems.lua' in toc,'TOC version/module mismatch')
  for mod,tag in [('Core.lua','G.version="2.8.2"'),('UI.lua','G.uiVersion="2.8.2"'),('QuestJourney.lua','G.journeyVersion="2.8.2"')]:
   require(tag in (src/mod).read_text('utf-8'),'runtime module version mismatch '+mod)
  files=sorted(p for p in src.rglob('*') if p.is_file())
  require(len(files)==123,'unexpected package file count')
  with zipfile.ZipFile(dest,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as z:
   for file in files:
    rel=file.relative_to(td).as_posix()
    info=zipfile.ZipInfo(rel,date_time=DATE)
    info.compress_type=zipfile.ZIP_STORED
    info.create_system=3
    info.external_attr=(0o100644<<16)
    z.writestr(info,file.read_bytes())
 with zipfile.ZipFile(dest) as z:
  require(z.testzip() is None and len(z.infolist())==123,'output archive corruption')
  require(all(n.startswith(FOLDER+'/') and '..' not in Path(n).parts for n in z.namelist()),'bad output path')
 result=digest(dest.read_bytes())
 require(result==NEW_SHA,'unexpected built archive digest: '+result)
 base.unlink() # Only this managed custom addon's pinned immediate predecessor
 print('PASS built',dest.name,'bytes',dest.stat().st_size,'files',len(files),'SHA256',result)
if __name__=='__main__':main()