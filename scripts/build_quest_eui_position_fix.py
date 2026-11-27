#!/usr/bin/env python3
"""Reproduce the approved v2.8.1 EUI button-position hotfix without touching WTF.

The source ZIP and unified patch are SHA-256 pinned. Only this managed custom
quest addon is repacked. This is run before Lua 5.1/LuaJIT regressions in CI.
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
BASE='ForeverQuestGuide_Forever_v2.8.0_FullChain_FriendCatchup.zip'
NEW='ForeverQuestGuide_Forever_v2.8.1_EUI_Detail_Button_PositionFix.zip'
PATCH='eui_position_fix_v2.8.1.patch.gz.b64'
FOLDER='ForeverDungeonQuestGuide'
BASE_SHA='a365f1a38ab9f4992fa9145c8ca48649499463a077bc3b2db661454ad378b824'
PATCH_SHA='d3f07de7fd9258f2e051724b8be91493d83f8a938587831b0bad0240b1c8934c'
NEW_SHA='83a6fd847e9d85a7aec358e511868c260bf284a99cfdff26a752574b1c977583'
ZIP_DATE=(2026,11,27,20,0,0)

def sha(raw:bytes)->str:
 return hashlib.sha256(raw).hexdigest()
def check(ok,msg):
 if not ok: raise ValueError(msg)

def main():
 original=ADDONS/BASE
 target=ADDONS/NEW
 if target.exists() and not original.exists():
  check(sha(target.read_bytes())==NEW_SHA,'already published ZIP mismatch')
  print('Existing v2.8.1 artifact verified')
  return
 check(original.is_file(),'missing pinned v2.8.0 baseline')
 check(sha(original.read_bytes())==BASE_SHA,'unexpected v2.8.0 baseline')
 encoded=(ROOT/'scripts'/PATCH).read_text(encoding='ascii').strip()
 patch=gzip.decompress(base64.b64decode(encoded,validate=True))
 check(sha(patch)==PATCH_SHA,'v2.8.1 patch integrity mismatch')
 with tempfile.TemporaryDirectory(prefix='fqg-v281-') as tmp:
  temp=Path(tmp)
  with zipfile.ZipFile(original) as source:
   check(source.testzip() is None,'baseline ZIP CRC failure')
   for member in source.infolist():
    name=member.filename
    check(name.startswith(FOLDER+'/') and not name.endswith('/') and '..' not in Path(name).parts,'unsafe ZIP entry')
    dst=temp/name;dst.parent.mkdir(parents=True,exist_ok=True);dst.write_bytes(source.read(member))
  diff=temp/'fix.patch';diff.write_bytes(patch)
  proc=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(diff)],cwd=temp/FOLDER,capture_output=True,text=True)
  check(proc.returncode==0,'hotfix patch conflict: '+proc.stdout+proc.stderr)
  root=temp/FOLDER
  check('## Version: 2.8.1' in (root/'ForeverDungeonQuestGuide.toc').read_text('utf-8'),'TOC version mismatch')
  check('G.version="2.8.1"' in (root/'Core.lua').read_text('utf-8'),'runtime version mismatch')
  bridge=(root/'EUIQuestBridge.lua').read_text('utf-8')
  check('placeInside(button,win)' in bridge and 'placeOutside' not in bridge,'external detail-button fallback remained')
  files=sorted(p for p in root.rglob('*') if p.is_file())
  check(len(files)==120,'unexpected file count')
  target.parent.mkdir(parents=True,exist_ok=True)
  with zipfile.ZipFile(target,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as archive:
   for path in files:
    name=path.relative_to(temp).as_posix()
    entry=zipfile.ZipInfo(name,date_time=ZIP_DATE)
    entry.compress_type=zipfile.ZIP_STORED;entry.create_system=3;entry.external_attr=(0o100644<<16)
    archive.writestr(entry,path.read_bytes())
 with zipfile.ZipFile(target) as result:
  check(result.testzip() is None and len(result.namelist())==120,'new ZIP verification failed')
 check(sha(target.read_bytes())==NEW_SHA,'non-reproducible v2.8.1 ZIP: '+sha(target.read_bytes()))
 original.unlink()  # only the one managed predecessor, leave other addons untouched
 print('PASS deterministic v2.8.1 EUI detail-button fix',NEW_SHA,len(files),target.stat().st_size)

if __name__=='__main__':main()