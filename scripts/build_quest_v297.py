from pathlib import Path
import argparse,base64,gzip,hashlib,json,zipfile
ROOT=Path(__file__).resolve().parent.parent
OLD='ForeverQuestGuide_Forever_v2.9.6_SmoothScroll_CompactConditions.zip'
NEW='ForeverQuestGuide_Forever_v2.9.7_CompactHUD_OriginalDetails.zip'
OLD_SHA='27113ab22b40ec03d34928784c9ef21067326b29dbc38e3d24434ae77f100455'
def digest(b):return hashlib.sha256(b).hexdigest()
def build(old,delta,out,expected=None):
    assert digest(old.read_bytes())==OLD_SHA,'incorrect base'
    d=json.loads(gzip.decompress(base64.b64decode(delta.read_bytes())))
    with zipfile.ZipFile(old) as z: files={i.filename:z.read(i) for i in z.infolist() if not i.is_dir()}
    for n,b in d.items():
        assert n.startswith('ForeverDungeonQuestGuide/') and '..' not in Path(n).parts and '\\' not in n,n
        if 'new' in b: files[n]=base64.b64decode(b['new'])
        else:
            lines=files[n].splitlines(keepends=True);parts=[];last=0
            for start,end,replacement in b['patch']:
                assert last<=start<=end<=len(lines),n
                parts.extend(lines[last:start]);parts.append(base64.b64decode(replacement));last=end
            parts.extend(lines[last:]);files[n]=b''.join(parts)
        assert digest(files[n])==b['sha'],n
    assert b'## Version: 2.9.7' in files['ForeverDungeonQuestGuide/ForeverDungeonQuestGuide.toc']
    out.parent.mkdir(parents=True,exist_ok=True)
    temp=out.with_suffix('.tmp')
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=9) as z:
        for n,b in sorted(files.items()):
            zi=zipfile.ZipInfo(n,(2026,1,1,0,0,0));zi.compress_type=zipfile.ZIP_DEFLATED;zi.create_system=3;zi.external_attr=0o100644<<16
            z.writestr(zi,b,compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    sha=digest(temp.read_bytes())
    if expected:assert sha==expected,(sha,expected)
    with zipfile.ZipFile(temp) as z:
        assert z.testzip() is None
        assert set(z.namelist())==set(files)
        assert all(z.read(n)==b for n,b in files.items())
    temp.replace(out)
    print('Quest Guide verified',out.name,'files',len(files),'bytes',out.stat().st_size,'sha256',sha)
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--base',type=Path,default=ROOT/'addons'/OLD);p.add_argument('--delta',type=Path,default=ROOT/'scripts'/'quest_v2.9.7_delta.gz.b64');p.add_argument('--out',type=Path,default=ROOT/'addons'/NEW);p.add_argument('--expected-sha');a=p.parse_args();build(a.base,a.delta,a.out,a.expected_sha)
