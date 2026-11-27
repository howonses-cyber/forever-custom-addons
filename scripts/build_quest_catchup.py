#!/usr/bin/env python3
"""Reproduce only Forever Quest Guide V2.8.0 from its reviewed V2.7.1 ZIP.

Source patch is SHA-pinned, Unicode UTF-8 and available beside this script;
reconstruction does not read official addons, user game files or WTF. Native
Lua5.1/LuaJIT mock compatibility is enforced by the separate Actions CI step.
"""
from __future__ import annotations
import base64,gzip,hashlib,subprocess,tempfile,zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parent.parent
ADDONS=ROOT/'addons'
BASE='ForeverQuestGuide_Forever_v2.7.1_EUI_Tracker_Bridge_Recovery.zip'
NEW='ForeverQuestGuide_Forever_v2.8.0_FullChain_FriendCatchup.zip'
PATCH='phase8_quest_v2.8.0.patch.gz.b64'
FOLDER='ForeverDungeonQuestGuide'
BASE_SHA='1836fe34effec56e6deee6cff7691836c95723374386a886cfcd4e059c0e7151'
PATCH_SHA='5c1cba05aaad2a84becb7f7579b3476fa613dcf5b60fe8ea4442efd4e15892f1'
NEW_SHA='a365f1a38ab9f4992fa9145c8ca48649499463a077bc3b2db661454ad378b824'
DATE=(2026,11,27,19,45,0)
FILE_COUNT=119

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def check(condition:bool,explanation:str):
 if not condition:raise ValueError(explanation)

def main()->None:
 base=ADDONS/BASE;out=ADDONS/NEW
 if out.is_file() and not base.is_file():
  check(sha(out.read_bytes())==NEW_SHA,'existing V2.8.0 ZIP changed')
  print('Verified existing QuestGuide V2.8.0 SHA-256',NEW_SHA)
  return
 check(base.is_file(),'reviewed V2.7.1 base ZIP missing')
 check(sha(base.read_bytes())==BASE_SHA,'V2.7.1 baseline SHA-256 changed')
 encoded=(ROOT/'scripts'/PATCH).read_text('ascii').strip()
 patch=gzip.decompress(base64.b64decode(encoded,validate=True))
 check(sha(patch)==PATCH_SHA,'patch SHA-256 mismatch')
 with tempfile.TemporaryDirectory(prefix='fdqg-catchup-') as tmp:
  tmp=Path(tmp);source=tmp/FOLDER
  with zipfile.ZipFile(base) as z:
   check(z.testzip() is None,'source ZIP CRC failure')
   check(len(z.infolist())==112,'source ZIP file count mismatch')
   for info in z.infolist():
    rel=info.filename
    check(rel.startswith(FOLDER+'/') and not rel.endswith('/') and '..' not in Path(rel).parts,'unsafe base path: '+rel)
    f=tmp/rel;f.parent.mkdir(parents=True,exist_ok=True);f.write_bytes(z.read(info))
  patch_path=tmp/'reviewed.patch';patch_path.write_bytes(patch)
  proc=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(patch_path)],cwd=source,text=True,capture_output=True)
  check(proc.returncode==0,'source patch failed: '+proc.stdout+proc.stderr)
  toc=(source/'ForeverDungeonQuestGuide.toc').read_text('utf-8')
  check('## Version: 2.8.0' in toc,'V2.8.0 TOC not found')
  check('G.version="2.8.0"' in (source/'Core.lua').read_text('utf-8'),'runtime version mismatch')
  for path in ('QuestChainGraph.lua','CatchupGuide.lua','CatchupSync.lua','CatchupUI.lua','tests/test_catchup_v280.lua'):
   check((source/path).is_file(),'missing new source: '+path)
  files=sorted(p for p in source.rglob('*') if p.is_file())
  check(len(files)==FILE_COUNT,'wrong ZIP file count')
  with zipfile.ZipFile(out,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as z:
   for path in files:
    arc=path.relative_to(tmp).as_posix()
    info=zipfile.ZipInfo(arc,date_time=DATE)
    info.compress_type=zipfile.ZIP_STORED;info.create_system=3
    info.external_attr=(0o100644<<16)
    z.writestr(info,path.read_bytes())
 with zipfile.ZipFile(out) as z:
  check(z.testzip() is None and len(z.infolist())==FILE_COUNT,'output CRC/file count failure')
 new_hash=sha(out.read_bytes())
 check(new_hash==NEW_SHA,'output ZIP SHA-256 differed: '+new_hash)
 base.unlink()  # only this addon V2.7.1 in GitHub's managed addons folder
 print('PASS reconstructed',out.name,'files',FILE_COUNT,'bytes',out.stat().st_size,'sha256',new_hash)

if __name__=='__main__':main()