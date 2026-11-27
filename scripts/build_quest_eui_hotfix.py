#!/usr/bin/env python3
"""Reproducibly publish the EUI bridge-only hotfix from a pinned custom ZIP.

Extract only the reviewed quest addon folder, apply a SHA-pinned textual patch,
rebuild a byte-identical ZIP, then remove only its versioned predecessor from
this distribution repository. No EUI, other addons, user settings, or WTF.
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
BASE='ForeverQuestGuide_Forever_v2.7.0_MapEUI_Performance_PartyConsent.zip'
NEW='ForeverQuestGuide_Forever_v2.7.1_EUI_Tracker_Bridge_Recovery.zip'
PATCH='hotfix_quest_v2.7.1.patch.gz.b64'
FOLDER='ForeverDungeonQuestGuide'
BASE_SHA='c2b70f5b2e8d852703a518371bf8a7f7fd723c971f60f7fb0f35e43081f54276'
PATCH_SHA='2b616bf9427d11fdd17caeb35c4af67be58d047ef0cea46ccfa43ddef81135f7'
NEW_SHA='1836fe34effec56e6deee6cff7691836c95723374386a886cfcd4e059c0e7151'
ZIP_DATE=(2026,11,27,11,15,0)

def sha(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def check(yes:bool,msg:str)->None:
 if not yes:raise ValueError(msg)

def main()->None:
 base=ADDONS/BASE
 output=ADDONS/NEW
 if output.is_file() and not base.is_file():
  check(sha(output.read_bytes())==NEW_SHA,'existing EUI hotfix changed')
  print('PASS existing EUI hotfix',output.name)
  return
 check(base.is_file(),'pinned quest addon baseline missing')
 check(sha(base.read_bytes())==BASE_SHA,'baseline SHA-256 mismatch')
 encoded=(ROOT/'scripts'/PATCH).read_text('ascii')
 patch=gzip.decompress(base64.b64decode(encoded.strip(),validate=True))
 check(sha(patch)==PATCH_SHA,'reviewed patch mismatch')
 with tempfile.TemporaryDirectory(prefix='fdqg-eui-hotfix-') as temp_dir:
  temp=Path(temp_dir)
  with zipfile.ZipFile(base) as archive:
   check(archive.testzip() is None,'baseline ZIP CRC error')
   for item in archive.infolist():
    name=item.filename
    check(name.startswith(FOLDER+'/') and '..' not in Path(name).parts and not name.endswith('/'),'unsafe input path '+name)
    dest=temp/name
    dest.parent.mkdir(parents=True,exist_ok=True)
    dest.write_bytes(archive.read(item))
  diff=temp/'eui.patch';diff.write_bytes(patch)
  process=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(diff)],cwd=temp/FOLDER,capture_output=True,text=True)
  check(process.returncode==0,'source patch refused: '+process.stdout+process.stderr)
  src=temp/FOLDER
  check('## Version: 2.7.1' in (src/'ForeverDungeonQuestGuide.toc').read_text('utf-8'),'TOC version incorrect')
  check('G.version="2.7.1"' in (src/'Core.lua').read_text('utf-8'),'runtime version incorrect')
  check('function G.RefreshEUITrackerLauncher()' in (src/'EUIQuestBridge.lua').read_text('utf-8'),'EUI launcher missing')
  check('test_eui_recovery.lua' in (src/'tests/run_compatibility.py').read_text('utf-8'),'new EUI regression suite not required')
  files=sorted(p for p in src.rglob('*') if p.is_file())
  check(len(files)==112,'unexpected payload file count')
  with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as archive:
   for file in files:
    name=file.relative_to(temp).as_posix()
    entry=zipfile.ZipInfo(name,date_time=ZIP_DATE)
    entry.compress_type=zipfile.ZIP_STORED
    entry.create_system=3
    entry.external_attr=(0o100644<<16)
    archive.writestr(entry,file.read_bytes())
 with zipfile.ZipFile(output) as archive:
  check(archive.testzip() is None and len(archive.infolist())==112,'output ZIP invalid')
 check(sha(output.read_bytes())==NEW_SHA,'build mismatch: '+sha(output.read_bytes()))
 base.unlink() # only the replaced version of this specific custom quest addon
 print('PASS byte-identical EUI hotfix',output.name,'SHA-256',NEW_SHA)

if __name__=='__main__':main()