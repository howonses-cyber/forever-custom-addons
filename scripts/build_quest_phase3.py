#!/usr/bin/env python3
"""Rebuild exactly one reviewed custom quest-addon release from the pinned ZIP.

The fully versioned base archive is already part of the public GitHub repo.
The Unicode unified patch is bundled as gzip/base64 plain text. Offline and
GitHub builds use identical ZIP_STORED encoding, timestamps, filenames and
file metadata so their SHA-256 digests match irrespective of zlib versions.
No network, game files, users' WTF, or other addons are accessed.
"""
from __future__ import annotations
import base64
import gzip
import hashlib
from pathlib import Path
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parent.parent
ADDONS = ROOT / "addons"
BASE_NAME = "ForeverQuestGuide_Forever_v2.4.0_RouteSafety_Preflight.zip"
NEW_NAME = "ForeverQuestGuide_Forever_v2.5.0_Recommendations_ForeverEvidence_Korean.zip"
PATCH_NAME = "phase3_quest_v2.5.0.patch.gz.b64"
ROOT_FOLDER = "ForeverDungeonQuestGuide"
EXPECTED_BASE_SHA256 = "bcf4ea2e5de4d022db7b9bcf1dc0f93b89f9f6579db75af52e91b3bc0a1d1c22"
EXPECTED_PATCH_SHA256 = "6750a2dbe6252c1cefaec916eb42ec36d2442c09370a6b1da15751ca82921ffa"
EXPECTED_NEW_SHA256 = "b968da668f6288bc4cec73c0fa4eb9cd22234526fc27bc16e2b5892aa26295d9"
ZIP_DATE = (2026, 11, 27, 9, 30, 0)

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def check(yes: bool, message: str):
    if not yes:
        raise ValueError(message)

def main() -> None:
    base=ADDONS/BASE_NAME
    output=ADDONS/NEW_NAME
    if output.is_file() and not base.exists():
        check(sha(output.read_bytes())==EXPECTED_NEW_SHA256, "existing release changed")
        print("Verified existing V2.5.0:", output,EXPECTED_NEW_SHA256)
        return
    check(base.is_file(), "reviewed V2.4.0 baseline missing")
    check(sha(base.read_bytes())==EXPECTED_BASE_SHA256, "base archive integrity failed")
    compressed=(ROOT/'scripts'/PATCH_NAME).read_text(encoding='ascii')
    patch=gzip.decompress(base64.b64decode(compressed.strip(),validate=True))
    check(sha(patch)==EXPECTED_PATCH_SHA256,"patch source integrity failed")
    with tempfile.TemporaryDirectory(prefix='fdqg-phase3-') as temp:
        temp=Path(temp)
        with zipfile.ZipFile(base) as z:
            for info in z.infolist():
                n=info.filename
                check(n.startswith(ROOT_FOLDER+'/') and '..' not in Path(n).parts and not n.endswith('/'), 'unsafe source entry '+n)
                dest=temp/n
                dest.parent.mkdir(parents=True,exist_ok=True)
                dest.write_bytes(z.read(info))
        diff=temp/'phase3.patch';diff.write_bytes(patch)
        proc=subprocess.run(['patch','--batch','--fuzz=0','-p1','-i',str(diff)],
                            cwd=temp/ROOT_FOLDER,text=True,capture_output=True)
        check(proc.returncode==0,"patch conflict: "+proc.stdout+proc.stderr)
        source=temp/ROOT_FOLDER
        toc=(source/'ForeverDungeonQuestGuide.toc').read_text(encoding='utf-8')
        check('## Version: 2.5.0' in toc,'new TOC version missing')
        check('QuestRecommendation.lua' in toc and 'ForeverQuestEvidence.lua' in toc,'phase3 modules omitted')
        check('G.version="2.5.0"' in (source/'Core.lua').read_text(encoding='utf-8'),'runtime version missing')
        files=sorted(p for p in source.rglob('*') if p.is_file())
        check(len(files)>=100,'missing output files')
        # Uncompressed ZIP deliberately avoids local/runner zlib differences.
        with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED,allowZip64=False) as z:
            for file in files:
                rel=file.relative_to(temp).as_posix()
                info=zipfile.ZipInfo(rel,date_time=ZIP_DATE)
                info.compress_type=zipfile.ZIP_STORED
                info.create_system=3
                info.external_attr=(0o100644 << 16)
                z.writestr(info,file.read_bytes())
    with zipfile.ZipFile(output) as z:
        check(z.testzip() is None,'new zip CRC failure')
        count=len(z.infolist())
        check(all(n.startswith(ROOT_FOLDER+'/') and '..' not in Path(n).parts for n in z.namelist()),'unsafe output member')
    result=sha(output.read_bytes())
    check(result==EXPECTED_NEW_SHA256,'new ZIP integrity mismatch: '+result)
    base.unlink() # only the pinned predecessor of this managed custom addon
    print('Built verified',output.name,'files',count,'bytes',output.stat().st_size,'SHA256',result)

if __name__=='__main__':
    main()