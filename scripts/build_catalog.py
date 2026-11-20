#!/usr/bin/env python3
"""Build a custom-only WoW addon release manifest and staged GitHub Release assets.

Standard library only. Does not publish, mutate source archives, or touch WTF.
A release is published by the separately permissioned GitHub Actions job.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import os
import json
import re
import shutil
import stat
import sys
import zipfile
from pathlib import Path
from urllib.parse import quote

SAFE_NAME = re.compile(r"^[A-Za-z0-9_+.-]{1,110}$")
SAFE_ARCHIVE = re.compile(r"^[A-Za-z0-9_.-]+\.zip$", re.I)
SAFE_REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
BLOCKED = {".exe", ".dll", ".com", ".scr", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe", ".js", ".jse", ".hta", ".lnk", ".url", ".reg", ".msi", ".msp", ".jar", ".cpl", ".wsf", ".wsh"}
VERSION = re.compile(r"^\s*[vV]?(\d+(?:\.\d+){0,3})(?:[-_.]([a-zA-Z][a-zA-Z0-9._-]*))?\s*$")
MAX_ZIP_ENTRIES = 30000
MAX_ARCHIVE_BYTES = 200_000_000
MAX_FILE_BYTES = 200 * 1024 * 1024
MAX_EXPANDED_BYTES = 1200 * 1024 * 1024


def fail(msg: str):
    raise ValueError(msg)


def h(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def version_compare(left: str, right: str) -> int:
    """Matches the manager's numeric+known qualifier ordering, fails closed."""
    a, b = VERSION.fullmatch(left), VERSION.fullmatch(right)
    if not a or not b:
        fail(f"Uncomparable versions: {left!r} vs {right!r}")
    nums_a = [int(p) for p in a.group(1).split(".")]
    nums_b = [int(p) for p in b.group(1).split(".")]
    nums_a += [0] * (4 - len(nums_a))
    nums_b += [0] * (4 - len(nums_b))
    if nums_a != nums_b:
        return (nums_a > nums_b) - (nums_a < nums_b)
    ta, tb = (a.group(2) or "").lower(), (b.group(2) or "").lower()
    if ta == tb:
        return 0
    ranks = {"alpha": 10, "a": 10, "beta": 20, "b": 20, "rc": 25, "": 30, "rebuilt": 40, "patch": 45, "hotfix": 45, "fix": 45}
    ka, kb = re.sub(r"[._-]\d+$", "", ta), re.sub(r"[._-]\d+$", "", tb)
    if ka not in ranks or kb not in ranks or ranks[ka] == ranks[kb]:
        fail(f"Ambiguous version suffix: {left!r} vs {right!r}")
    return (ranks[ka] > ranks[kb]) - (ranks[ka] < ranks[kb])


def safe_piece(name: str) -> bool:
    if not name or name in (".", "..") or name.rstrip(" .") != name:
        return False
    if any(ord(c) < 32 or c in '<>:"/\\|?*' for c in name):
        return False
    if re.match(r"^(CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(\..*)?$", name, re.I):
        return False
    return True


def header(text: str, name: str) -> str:
    m = re.search(r"^##\s*" + re.escape(name) + r"\s*:\s*(.*?)\s*$", text, flags=re.M | re.I)
    return m.group(1).strip() if m else ""


def inspect_addon(path: Path) -> dict:
    if not SAFE_ARCHIVE.fullmatch(path.name) or path.stat().st_size > MAX_ARCHIVE_BYTES:
        fail(f"Invalid archive file: {path.name}")
    archive_raw = path.read_bytes()
    records, total, paths_seen, folders = [], 0, set(), {}
    with zipfile.ZipFile(path) as z:
        if len(z.infolist()) > MAX_ZIP_ENTRIES:
            fail(f"ZIP has excessive entry count: {path.name}")
        for entry in z.infolist():
            name = entry.filename
            if '\\' in name or not name or name.startswith("/") or '//' in name or ':' in name:
                fail(f"Unsafe ZIP entry: {name!r}")
            pieces = name.rstrip('/').split('/')
            if (len(pieces) < 2 and not entry.is_dir()) or any(not safe_piece(p) for p in pieces):
                fail(f"Invalid ZIP hierarchy: {name!r}")
            root = pieces[0]
            if not SAFE_NAME.fullmatch(root) or root.lower().startswith('blizzard_'):
                fail(f"Cannot manage protected folder: {root}")
            if (entry.external_attr >> 16) & 0xF000 == stat.S_IFLNK:
                fail(f"Symlink inside ZIP: {name!r}")
            total += entry.file_size
            if entry.file_size > MAX_FILE_BYTES or total > MAX_EXPANDED_BYTES:
                fail(f"Oversized ZIP payload: {path.name}")
            if entry.is_dir():
                continue
            if Path(name).suffix.lower() in BLOCKED:
                fail(f"Executable content is forbidden: {name!r}")
            lower = name.lower()
            if lower in paths_seen:
                fail(f"Duplicate ZIP entry: {name!r}")
            paths_seen.add(lower)
            contents = z.read(entry)
            records.append(lower + '\t' + h(contents))
            if len(pieces) == 2 and pieces[1].lower() == (root + '.toc').lower():
                text = contents.decode('utf-8-sig', errors='strict')
                version = header(text, 'Version')
                if not version:
                    fail(f"No version in TOC: {name}")
                if root in folders:
                    fail(f"Repeated TOC: {name}")
                folders[root] = {
                    'version': version,
                    'title': header(text, 'Title-koKR') or header(text, 'Title') or root,
                    'dependencies': [v.strip() for v in header(text, 'Dependencies').split(',') if v.strip()],
                    'optionalDependencies': [v.strip() for v in header(text, 'OptionalDeps').split(',') if v.strip()],
                }
        if not folders:
            fail(f"No direct root TOC found in {path.name}")
        roots = {n.split('/')[0] for n in paths_seen}
        if roots != {folder.lower() for folder in folders}:
            fail(f"Every ZIP root must have matching TOC: {path.name}")
        versions = {f['version'] for f in folders.values()}
        if len(versions) != 1:
            fail(f"Different versions among root TOCs: {path.name}")
    records.sort()
    tree_hash = h(('\n'.join(records) + '\n').encode('utf-8'))
    return {'archive': path.name, 'sha256': h(archive_raw), 'size': len(archive_raw),
            'folders': sorted(folders), 'treeSha256': tree_hash, 'fileCount': len(records),
            'version': next(iter(versions)), 'metadata': folders}


def title_clean(text: str) -> str:
    text = re.sub(r'\|c[0-9a-fA-F]{8}|\|r', '', text)
    return re.sub(r'\s+', ' ', text).strip()[:120]


def slug(folder: str) -> str:
    text = re.sub(r'([a-z0-9])([A-Z])', r'\1-\2', folder).replace('_', '-').lower()
    if not SAFE_NAME.fullmatch(text):
        fail(f"Could not create a safe id for {folder}")
    return text



def approved_retirements(repo_root: Path, original: dict) -> list[dict]:
    """Only deliberately registered old IDs may leave the public active list.

    A retired entry is metadata, NOT an uninstall instruction. The owner keeps
    a recovery ZIP privately in Library /Addon/_SourceImports.
    """
    registry_path = repo_root / 'retired_addons.json'
    earlier = original.get('retired', [])
    if not registry_path.is_file():
        if earlier:
            fail('Retirement records were removed from the repository')
        return []
    data = json.loads(registry_path.read_text('utf-8'))
    if data.get('schema') != 1 or not isinstance(data.get('retired'), list):
        fail('Invalid retired_addons.json schema')
    active_before = {p['id']: p for p in original['apps']}
    retired_before = {p['id']: p for p in earlier}
    if len(retired_before) != len(earlier):
        fail('Duplicate historic retirement entries')
    approved, seen = [], set()
    for item in data['retired']:
        rid = item.get('id', '')
        if not isinstance(rid, str) or not SAFE_NAME.fullmatch(rid) or rid.lower() in seen:
            fail(f'Invalid or duplicate retirement ID: {rid!r}')
        seen.add(rid.lower())
        if item.get('policy') != 'preserve-installed':
            fail(f'Retirement must preserve every existing installation: {rid}')
        folders = item.get('folders')
        if not isinstance(folders, list) or not folders or any(
            not isinstance(p, str) or not SAFE_NAME.fullmatch(p) or p.lower().startswith('blizzard_') for p in folders
        ):
            fail(f'Unsafe retired folder identity: {rid}')
        if not isinstance(item.get('sha256'), str) or not re.fullmatch('[a-fA-F0-9]{64}', item['sha256']):
            fail(f'Invalid last published archive SHA-256: {rid}')
        if not isinstance(item.get('archive'), str) or not SAFE_ARCHIVE.fullmatch(item['archive']):
            fail(f'Invalid retired ZIP name: {rid}')
        if not isinstance(item.get('version'), str) or not VERSION.fullmatch(item['version']):
            fail(f'Invalid retired version: {rid}')
        if not isinstance(item.get('title'), str) or not item['title'].strip():
            fail(f'Missing retired addon title: {rid}')
        previous = active_before.get(rid) or retired_before.get(rid)
        if previous is None:
            fail(f'Cannot retire an addon that was never published: {rid}')
        for field in ('id', 'version', 'folders', 'archive', 'sha256'):
            if previous.get(field) != item.get(field):
                fail(f'Retirement fingerprint mismatch ({field}): {rid}')
        if rid in retired_before and retired_before[rid].get('policy') != 'preserve-installed':
            fail(f'Prior retirement policy changed: {rid}')
        approved.append(item)
    if set(retired_before) - {r['id'] for r in approved}:
        fail('Existing retired addon records cannot disappear')
    return sorted(approved, key=lambda r: r['id'])


def build(repo_root: Path, repo: str, out: Path, revision: int, tag: str, now: str) -> dict:
    if not SAFE_REPO.fullmatch(repo) or not repo or '..' in repo:
        fail('Expected public GitHub OWNER/REPO')
    if not re.fullmatch(r'[A-Za-z0-9_.-]{1,120}', tag):
        fail('Invalid GitHub release tag')
    if revision < 1:
        fail('Revision must be positive')
    original = json.loads((repo_root / 'catalog.json').read_text('utf-8-sig'))
    if original.get('schema') != 1 or not isinstance(original.get('apps'), list):
        fail('Unsupported source catalog')
    if revision <= int(original['revision']):
        fail('New revision must be higher than previous revision')
    if any(a['kind'] != 'custom' for a in original['apps']):
        fail('Only GPT-made custom addons may be published')
    previous = original['apps']
    retired = approved_retirements(repo_root, original)
    retired_ids = {r['id'] for r in retired}
    retired_folders = {f.lower() for r in retired for f in r['folders']}
    files = sorted((repo_root / 'addons').glob('*.zip'))
    if not files:
        fail('No addon ZIP files available')
    inspections = [inspect_addon(f) for f in files]
    ids, folder_set, archive_set = set(), set(), set()
    apps = []
    for item in inspections:
        if any(f.lower() in retired_folders for f in item['folders']):
            fail(f'Retired managed folder must not reappear in active addons: {item["archive"]}')
        overlap = [p for p in previous if set(p['folders']) & set(item['folders'])]
        if len(overlap) > 1:
            fail(f"Archive overlaps multiple managed addons: {item['archive']}")
        old = overlap[0] if overlap else None
        if old and set(old['folders']) != set(item['folders']):
            fail(f"Folder ownership changed for {old['id']}")
        if old:
            cmp = version_compare(item['version'], str(old['version']))
            if cmp < 0:
                fail(f"Refusing version downgrade: {old['id']} {old['version']} -> {item['version']}")
            if cmp == 0 and item['sha256'] != str(old['sha256']):
                fail(f"Content changed without version increase: {old['id']}; bump the TOC version")
            app_id = old['id']
        else:
            app_id = slug(item['folders'][0])
        if app_id.lower() in ids or item['archive'].lower() in archive_set:
            fail(f"Duplicate addon id/archive: {app_id}")
        ids.add(app_id.lower())
        archive_set.add(item['archive'].lower())
        for folder in item['folders']:
            if folder.lower() in folder_set:
                fail(f"Two archives claim the same folder: {folder}")
            folder_set.add(folder.lower())
        data = item['metadata'][item['folders'][0]]
        app = {
            'id': app_id,
            'title': old['title'] if old else title_clean(data['title']),
            'kind': 'custom',
            'version': item['version'],
            'folders': item['folders'],
            'archive': item['archive'],
            'sha256': item['sha256'],
            'size': item['size'],
            'url': 'https://github.com/' + repo + '/releases/download/' + quote(tag) + '/' + quote(item['archive']),
            'dependencies': old.get('dependencies', []) if old else data['dependencies'],
            'optionalDependencies': old.get('optionalDependencies', []) if old else data['optionalDependencies'],
            'installPolicy': 'managed',
            'treeSha256': item['treeSha256'],
            'fileCount': item['fileCount'],
            'versionFolders': old.get('versionFolders', item['folders']) if old else item['folders'],
        }
        apps.append(app)
    missing = sorted({p['id'] for p in previous} - {a['id'] for a in apps})
    unexpected = sorted(set(missing) - retired_ids)
    if unexpected:
        fail('Deletion is not an automatic update. Restore missing ZIPs or perform separately reviewed retirement: ' + ', '.join(unexpected))
    manifest = {'schema': 1, 'revision': revision, 'channel': 'stable-custom-online', 'publishedAt': now,
                'publisher': 'ForeverAddonManager', 'apps': sorted(apps, key=lambda a: a['id']),
                'retired': retired, 'profile': None}
    if out.exists():
        if any(out.iterdir()):
            fail(f"Refusing to replace a nonempty output folder: {out}")
    out.mkdir(parents=True, exist_ok=True)
    for p in files:
        shutil.copy2(p, out / p.name)
    (out / 'catalog.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (out / 'release_info.json').write_text(json.dumps({'repo': repo, 'tag': tag, 'revision': revision, 'count': len(apps)}, indent=2) + '\n', encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--repo', required=True)
    parser.add_argument('--revision', required=True, type=int)
    parser.add_argument('--tag', required=True)
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    prev = json.loads((args.root / 'catalog.json').read_text('utf-8-sig'))
    revision = max(int(prev['revision']) + 1, args.revision)
    if args.tag == 'auto':
        tag = f"addons-r{revision}-run{int(os.environ.get('GITHUB_RUN_ID', '0'))}-try{int(os.environ.get('GITHUB_RUN_ATTEMPT', '1'))}"
    else:
        tag = args.tag
    m = build(args.root, args.repo, args.out, revision, tag, datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ'))
    print(json.dumps({'ok': True, 'revision': m['revision'], 'totalCustomAddons': len(m['apps']), 'tag': tag, 'catalogUrl': f'https://github.com/{args.repo}/releases/latest/download/catalog.json'}, ensure_ascii=False))


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, zipfile.BadZipFile, UnicodeDecodeError) as exc:
        print('RELEASE BLOCKED: ' + str(exc), file=sys.stderr)
        sys.exit(1)