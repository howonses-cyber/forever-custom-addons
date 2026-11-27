#!/usr/bin/env python3
"""Rebuild *only* reviewed V2.9.1 Quest Guide from an integrity-pinned V2.9.0 ZIP."""
import argparse
import base64
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

OLD='ForeverQuestGuide_Forever_v2.9.0_ChainSections_FocusLayout.zip'
NEW='ForeverQuestGuide_Forever_v2.9.1_NestedFlame_Rewards.zip'
OLD_SHA='3c134073372fccfc3aa2b2a3ec3a16d82de50b3b67534fd7ce09fb8d7332e81d'
DELTA='quest_v2.9.1_delta.gz.b64'
ROOT='ForeverDungeonQuestGuide/'

def sha(data):return hashlib.sha256(data).hexdigest()

def build(base:Path,delta:Path,output:Path):
    data=base.read_bytes()
    if sha(data)!=OLD_SHA:raise ValueError('Pinned V2.9.0 ZIP mismatch')
    with zipfile.ZipFile(base) as z:
        if z.testzip() is not None:raise ValueError('base CRC error')
        records={x.filename:z.read(x) for x in z.infolist() if not x.is_dir()}
    changes=json.loads(gzip.decompress(base64.b64decode(delta.read_text(encoding='ascii').strip())))
    if changes.get('base_sha256')!=OLD_SHA or changes.get('format')!=1:raise ValueError('wrong base or diff format')
    edited=set()
    for item in changes['edits']:
        path=item['path']
        if not path.startswith(ROOT) or not path.endswith(('.toc','.lua','.txt','.md','.py')):
            raise ValueError('unreviewed path '+path)
        if path in edited:raise ValueError('duplicate edit '+path)
        edited.add(path)
        previous=records.get(path)
        if (sha(previous) if previous is not None else None)!=item['prior_sha256']:
            raise ValueError('file preimage mismatch '+path)
        content=base64.b64decode(item['data'])
        if sha(content)!=item['sha256']:raise ValueError('file content mismatch '+path)
        records[path]=content
    toc=records[ROOT+'ForeverDungeonQuestGuide.toc']
    if b'## Version: 2.9.1' not in toc:raise ValueError('incorrect TOC version')
    required={
      ROOT+'QuestTitleGroups.lua',ROOT+'QuestRewards.lua',
      ROOT+'tests/test_subchapters_v291.lua',ROOT+'tests/test_rewards_v291.lua',
      ROOT+'Docs/CHANGELOG_v2.9.1.txt'
    }
    if not required.issubset(records):raise ValueError('required source/tests missing')
    if b'G.version="2.9.1"' not in records[ROOT+'Core.lua']:raise ValueError('runtime version mismatch')
    if b'G.uiVersion="2.9.1"' not in records[ROOT+'UI.lua']:raise ValueError('UI version mismatch')
    modules=[s.strip() for s in toc.decode('utf-8-sig').splitlines() if s.strip().endswith('.lua') and not s.lstrip().startswith('#')]
    if len(modules)!=len(set(modules)) or any(ROOT+m not in records for m in modules):raise ValueError('missing/duplicate TOC module')
    output.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(output,'w',compression=zipfile.ZIP_STORED,allowZip64=True) as z:
        for path in sorted(records):
            info=zipfile.ZipInfo(path,(2026,11,28,0,0,0))
            info.compress_type=zipfile.ZIP_STORED
            info.create_system=3
            info.external_attr=(0o100644<<16)
            z.writestr(info,records[path])
    with zipfile.ZipFile(output) as z:
        if z.testzip() is not None or set(z.namelist())!=set(records):raise ValueError('output archive integrity mismatch')
    target=output.read_bytes()
    print(json.dumps({'file':output.name,'size':len(target),'sha256':sha(target),'entries':len(records),'luaModules':len(modules),'edited':sorted(edited)},ensure_ascii=False,indent=2))
    return sha(target)

if __name__=='__main__':
    ap=argparse.ArgumentParser()
    ap.add_argument('--root',type=Path,default=Path('.'))
    ap.add_argument('--base',type=Path)
    ap.add_argument('--delta',type=Path)
    ap.add_argument('--output',type=Path)
    ap.add_argument('--expected-sha')
    args=ap.parse_args()
    hash_now=build(args.base or args.root/'addons'/OLD,args.delta or args.root/'scripts'/DELTA,args.output or args.root/'addons'/NEW)
    if args.expected_sha and hash_now!=args.expected_sha:raise SystemExit('Target SHA mismatch')
