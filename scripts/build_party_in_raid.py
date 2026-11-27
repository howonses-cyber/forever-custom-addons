#!/usr/bin/env python3
"""Reproducibly build only ForeverPartyInRaid from separately reviewed source."""
import argparse
import hashlib
from pathlib import Path
import zipfile

NAME='ForeverPartyInRaid_v1.1.0_EUI_NativePartyFrames.zip'
FILES=('ForeverPartyInRaid.toc','ForeverPartyInRaid.lua','README_KO.md','LICENSE.txt')


def build(root, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_STORED, allowZip64=True) as z:
        for name in sorted(FILES):
            data=(root/name).read_bytes()
            info=zipfile.ZipInfo('ForeverPartyInRaid/'+name, date_time=(2026,11,28,0,0,0))
            info.compress_type=zipfile.ZIP_STORED
            info.create_system=3
            info.external_attr=(0o100644 << 16)
            z.writestr(info,data)
    raw=output.read_bytes()
    sha=hashlib.sha256(raw).hexdigest()
    with zipfile.ZipFile(output) as z:
        assert z.testzip() is None
        assert z.namelist()==['ForeverPartyInRaid/'+x for x in sorted(FILES)]
        assert b'## Version: 1.1.0' in z.read('ForeverPartyInRaid/ForeverPartyInRaid.toc')
        lua=z.read('ForeverPartyInRaid/ForeverPartyInRaid.lua')
        assert b'SecureGroupHeaderTemplate' not in lua
        assert b'StatusBar' not in lua
    print(f'Archive {output.name} {len(raw)} bytes sha256={sha} entries={len(FILES)}')
    return sha

if __name__=='__main__':
    parser=argparse.ArgumentParser()
    parser.add_argument('--source',default=str(Path(__file__).resolve().parent/'party_in_raid'/'ForeverPartyInRaid'))
    parser.add_argument('--output',default='addons/'+NAME)
    parser.add_argument('--expected-sha',default=None)
    a=parser.parse_args()
    sha=build(Path(a.source),Path(a.output))
    if a.expected_sha and sha!=a.expected_sha:
        raise SystemExit('SHA mismatch expected='+a.expected_sha+' actual='+sha)
