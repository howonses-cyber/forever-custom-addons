#!/usr/bin/env python3
"""Reproducible V2.9.0 packaging. Rebuild only Quest Guide from pinned V2.8.2."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

OLD='ForeverQuestGuide_Forever_v2.8.2_CompactList_ItemSources.zip'
NEW='ForeverQuestGuide_Forever_v2.9.0_ChainSections_FocusLayout.zip'
OLD_SHA='685b0972af03f4bd5f0b3ab8fd55283cccecd8a467bfb4c513ac0fbbe3ee8317'
DELTA='quest_v2.9.0_delta.gz.b64'
ROOT='ForeverDungeonQuestGuide/'

def sha(data):return hashlib.sha256(data).hexdigest()

def build(base:Path,delta:Path,output:Path):
    source=base.read_bytes()
    if sha(source)!=OLD_SHA:raise ValueError('V2.8.2 source integrity mismatch')
    with zipfile.ZipFile(base) as z:
        if z.testzip() is not None:raise ValueError('source CRC failed')
        records={x.filename:z.read(x) for x in z.infolist() if not x.is_dir()}
    raw=delta.read_text(encoding='ascii').strip()
    changes=json.loads(gzip.decompress(base64.b64decode(raw)))
    if changes.get('base_sha256')!=OLD_SHA:raise ValueError('delta applies to different base')
    edited=set()
    for item in changes['edits']:
        path=item['path']
        if not path.startswith(ROOT) or not path.endswith(('.toc','.lua','.txt','.md','.py')):
            raise ValueError('unsafe change path '+path)
        if path in edited:raise ValueError('duplicate edit '+path)
        edited.add(path)
        previous=records.get(path)
        if (sha(previous) if previous is not None else None)!=item['prior_sha256']:
            raise ValueError('file changed since review: '+path)
        edited_bytes=base64.b64decode(item['data'])
        if sha(edited_bytes)!=item['sha256']:raise ValueError('delta edit checksum mismatch: '+path)
        records[path]=edited_bytes
    if not edited or ROOT+'ForeverDungeonQuestGuide.toc' not in edited:raise ValueError('release missing TOC bump')
    if b'## Version: 2.9.0' not in records[ROOT+'ForeverDungeonQuestGuide.toc']:raise ValueError('incorrect TOC version')
    if b'G.uiVersion="2.9.0"' not in records[ROOT+'UI.lua']:raise ValueError('UI version drift')
    modules=[s.strip() for s in records[ROOT+'ForeverDungeonQuestGuide.toc'].decode('utf-8-sig').splitlines() if s.strip().endswith('.lua') and not s.lstrip().startswith('#')]
    if len(modules)!=len(set(modules)) or any(ROOT+s not in records for s in modules):raise ValueError('TOC module missing/duplicate')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for path in sorted(records):
            info=zipfile.ZipInfo(path,(2026,11,28,0,0,0))
            info.compress_type=zipfile.ZIP_STORED
            info.create_system=3
            info.external_attr=(0o100644<<16)
            z.writestr(info,records[path])
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None:raise ValueError('target CRC failed')
        if set(z.namelist())!=set(records):raise ValueError('output entries differ from reviewed tree')
    target=output.read_bytes()
    print(json.dumps({'file':output.name,'size':len(target),'sha256':sha(target),'entries':len(records),'luaModules':len(modules),'changed':sorted(edited)},ensure_ascii=False,indent=2))
    return sha(target)

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--root',type=Path,default=Path('.'))
    parser.add_argument('--delta',type=Path)
    parser.add_argument('--base',type=Path)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--expected-sha')
    a=parser.parse_args()
    root=a.root
    hash_now=build(a.base or root/'addons'/OLD,a.delta or root/'scripts'/DELTA,a.output or root/'addons'/NEW)
    if a.expected_sha and hash_now!=a.expected_sha:raise SystemExit('Target SHA mismatch')
