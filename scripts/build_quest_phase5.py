#!/usr/bin/env python3
"""Deterministically build one opt-in quest addon release on GitHub Actions.

Reproduces the reviewed local ZIP from its SHA-pinned previous release and
SHA-pinned unified source patch. Does not touch official addons, WTF, other
custom addons, or user characters. Native Lua regressions run separately.
"""
from __future__ import annotations
import base64
import gzip
import hashlib
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parent.parent
ADDONS=ROOT/'addons'
BASE='ForeverQuestGuide_Forever_v2.6.0_DataDiagnostics_PagedSearch_Eligibility.zip'
NEW='ForeverQuestGuide_Forever_v2.7.0_MapEUI_Performance_PartyConsent.zip'
PATCH='phase5_quest_v2.7.0.patch.gz.b64'
FOLDER='ForeverDungeonQuestGuide'
BASE_SHA='f8a736f4a284a8e0908acedeb087810a0bf964a0a4e187a0d80403f0d20a4720'
PATCH_SHA='629853657fa12207ad4cf3b265f13373c7536363f619e2d3c4d03297603e5ad9'
NEW_SHA='c2b70f5b2e8d852703a518371bf8a7f7fd723c971f60f7fb0f35e43081f54276'
ZIP_DATE=(2026,11,27,10,15,0)

def sha(data:bytes)->str:return hashlib.sha256(data).hexdigest()
def check(value:bool,msg:str)->None:
 if not value:raise ValueError(msg)

def main()->None:
 base=ADDONS/BASE;output=ADDONS/NEW
 if output.is_file() and not base.is_file():
  check(sha(output.read_bytes())==NEW_SHA,'already-published artifact integrity failed')
  print('Existing Phase5 release integrity verified',output.name)
  return
 check(base.is_file(),'source V2.6.0 missing')
 check(sha(base.read_bytes())==BASE_SHA,'unexpected V2.6.0 baseline hash')
 encoded=(ROOT/'scripts'/PATCH).read_text('ascii')
 patch=gzip.decompress(base64.b64decode(encoded.strip(),validate=True))
 check(sha(patch)==PATCH_SHA,'reviewed source patch hash mismatch')
 with tempfile.TemporaryDirectory(prefix='fdqg-phase5-') as temp:
  temp=Path(temp)
  with zipfile.ZipFile(base) as z:
   check(z.testzip() is None,'bad source ZIP CRC')
   for info in z.infolist():
    name=info.filename
    check(name.startswith(FOLDER+'/') and '..' not in Path(name).parts and not name.endswith('/'),'unsafe source path '+name)
    target=temp/name;target.parent.mkdir(parents=True,exist_ok=True)
    target.write_bytes(z.read(info))
  diff=temp/'phase5.patch';diff.write_bytes(patch)
  run=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(diff)],cwd=temp/FOLDER,capture_output=True,text=True)
  check(run.returncode==0,'patch failed: '+run.stdout+run.stderr)
  src=temp/FOLDER
  toc=(src/'ForeverDungeonQuestGuide.toc').read_text('utf-8')
  check('## Version: 2.7.0' in toc,'invalid TOC version')
  check('PartySync.lua' in toc and 'MapPins.lua' in toc and 'EUIQuestBridge.lua' in toc,'missing phase5 modules')
  check('G.version="2.7.0"' in (src/'Core.lua').read_text('utf-8'),'runtime mismatch')
  files=sorted(path for path in src.rglob('*') if path.is_file())
  check(len(files)==110,'unexpected total file count')
  with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as z:
   for path in files:
    rel=path.relative_to(temp).as_posix()
    info=zipfile.ZipInfo(rel,date_time=ZIP_DATE)
    info.compress_type=zipfile.ZIP_STORED
    info.create_system=3
    info.external_attr=(0o100644<<16)
    z.writestr(info,path.read_bytes())
 with zipfile.ZipFile(output) as z:
  check(z.testzip() is None and len(z.infolist())==110,'new archive CRC/count check failed')
 result=sha(output.read_bytes())
 check(result==NEW_SHA,'new ZIP hash mismatch '+result)
 base.unlink() # only archived predecessor of this managed custom addon
 print('PASS deterministic phase5 release',output.name,len(files),output.stat().st_size,result)

if __name__=='__main__':main()