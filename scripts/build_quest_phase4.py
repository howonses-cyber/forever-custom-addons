#!/usr/bin/env python3
"""Reconstruct exactly one reviewed Phase4 quest-guide ZIP from pinned V2.5.0.

Read-only to external addons, user profiles and WTF. Only the superseded
quest-guide ZIP in this public repository is deleted, after full validation.
Archive bytes are deterministic (ZIP_STORED + fixed metadata).
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
BASE_NAME='ForeverQuestGuide_Forever_v2.5.0_Recommendations_ForeverEvidence_Korean.zip'
NEW_NAME='ForeverQuestGuide_Forever_v2.6.0_DataDiagnostics_PagedSearch_Eligibility.zip'
PATCH_NAME='phase4_quest_v2.6.0.patch.gz.b64'
FOLDER='ForeverDungeonQuestGuide'
EXPECTED_BASE_SHA256='b968da668f6288bc4cec73c0fa4eb9cd22234526fc27bc16e2b5892aa26295d9'
EXPECTED_PATCH_SHA256='ad3d695255f634b258c9e68d693a8bdb1fa8c51810e5a83ef25f28a91c2503b0'
EXPECTED_NEW_SHA256='f8a736f4a284a8e0908acedeb087810a0bf964a0a4e187a0d80403f0d20a4720'
STAMP=(2026,11,27,18,30,0)
def digest(raw:bytes)->str:return hashlib.sha256(raw).hexdigest()
def check(ok:bool,msg:str)->None:
 if not ok:raise ValueError(msg)
def main()->None:
 base=ADDONS/BASE_NAME
 output=ADDONS/NEW_NAME
 if output.is_file() and not base.exists():
  check(digest(output.read_bytes())==EXPECTED_NEW_SHA256,'Previously published ZIP changed unexpectedly')
  print('Verified prior V2.6.0 build',output.name,EXPECTED_NEW_SHA256)
  return
 check(base.is_file(),'Pinned V2.5.0 baseline not found')
 check(digest(base.read_bytes())==EXPECTED_BASE_SHA256,'Pinned base ZIP SHA-256 mismatch')
 encoded=(ROOT/'scripts'/PATCH_NAME).read_text(encoding='ascii').strip()
 patch=gzip.decompress(base64.b64decode(encoded,validate=True))
 check(digest(patch)==EXPECTED_PATCH_SHA256,'Reviewed patch SHA-256 mismatch')
 with tempfile.TemporaryDirectory(prefix='fqd-phase4-') as work:
  work=Path(work)
  with zipfile.ZipFile(base) as archive:
   check(archive.testzip() is None,'Base ZIP CRC failed')
   for item in archive.infolist():
    name=item.filename
    check(name.startswith(FOLDER+'/') and '..' not in Path(name).parts and not item.is_dir(),'Unsafe source entry: '+name)
    dest=work/name;dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(archive.read(item))
  diff=work/'reviewed.patch';diff.write_bytes(patch)
  proc=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(diff)],cwd=work/FOLDER,capture_output=True,text=True)
  check(proc.returncode==0,'Patch failed: '+proc.stdout+proc.stderr)
  source=work/FOLDER
  toc=(source/'ForeverDungeonQuestGuide.toc').read_text(encoding='utf-8')
  check('## Version: 2.6.0' in toc and 'QuestDiagnostics.lua' in toc,'Version or diagnostics missing from TOC')
  check('G.version="2.6.0"' in (source/'Core.lua').read_text(encoding='utf-8'),'Runtime version missing')
  check('test_phase4.lua' in (source/'tests'/'run_compatibility.py').read_text(encoding='utf-8'),'Regression suite not registered')
  files=sorted(p for p in source.rglob('*') if p.is_file())
  check(len(files)==106,'Unexpected file count')
  with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as archive:
   for file in files:
    name=file.relative_to(work).as_posix()
    entry=zipfile.ZipInfo(name,date_time=STAMP)
    entry.compress_type=zipfile.ZIP_STORED
    entry.create_system=3
    entry.external_attr=(0o100644 << 16)
    archive.writestr(entry,file.read_bytes())
 with zipfile.ZipFile(output) as archive:
  check(archive.testzip() is None,'ZIP CRC failure')
  check(len(archive.namelist())==106,'ZIP content count mismatch')
 computed=digest(output.read_bytes())
 check(computed==EXPECTED_NEW_SHA256,'Generated ZIP integrity mismatch: '+computed)
 base.unlink()
 print('Built verified custom Quest Guide',output.name,output.stat().st_size,'bytes, sha256',computed)
if __name__=='__main__':main()