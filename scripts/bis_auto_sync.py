#!/usr/bin/env python3
"""Fail-closed WoW Forever BiS source monitor and addon ZIP publisher.

This is NOT a simulator, a drop verifier or a game-client downloader.
A candidate is machine-promoted only when two independent pre-raid websites
present the same unambiguous top item within the same spec/slot.
Every claim of server availability remains unverified and is shown as such.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import time
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path

from bs4 import BeautifulSoup

SLOT_MAP = {
    'head': 'Head', 'neck': 'Neck', 'shoulder': 'Shoulder', 'shoulders': 'Shoulder', 'wrists': 'Wrist',
    'back': 'Back', 'cloak': 'Back', 'chest': 'Chest', 'wrist': 'Wrist',
    'hands': 'Hands', 'hand': 'Hands', 'waist': 'Waist', 'legs': 'Legs',
    'feet': 'Feet', 'finger': 'Finger', 'ring': 'Finger', 'trinket': 'Trinket',
    'main hand': 'MainHand', 'main-hand': 'MainHand', 'off hand': 'OffHand',
    'off-hand': 'OffHand', 'two-hand': 'TwoHand', 'two hand': 'TwoHand',
    'two-handed': 'TwoHand', 'ranged': 'Ranged', 'relic': 'Relic',
}
HEAD_PATTERN = re.compile(r'^\s*(main.hand|off.hand|two.hand|two.handed|head|neck|shoulders?|back|cloak|chest|wrists?|hands?|waist|legs|feet|finger|ring|trinket|ranged|relic)\b', re.I)
ITEM_PATH = re.compile(r'(?:[?&]item=|/item[=/]|/items/(?:\#item-|)|\bitem:)([1-9]\d{2,8})(?!\d)', re.I)
BAD_CONTEXT = re.compile(r'raid[- ]?gated|from (?:a |the )?raid|molten core|onyxia|blackwing lair|naxxramas|alterac valley|battleground|honor rank|horde only|unconfirmed in forever|world boss', re.I)
GOOD_SOURCE = re.compile(r'crafted:|drop:|quest:|vendor:|reputation:|container:', re.I)
NAME_RE = re.compile(r"^[\w][\w\s'.,:\-()]{3,99}$", re.UNICODE)
ALLOWED_HOSTS = {'foreverwow.gg', 'theforeverera.com'}
ARCHIVE_PREFIX = 'ForeverBiSAudit_Forever_v'


def now_utc() -> str:
    return dt.datetime.now(dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def normalize_name(s: str) -> str:
    return re.sub(r'\s+', ' ', re.sub(r'[^a-zA-Z0-9]+', ' ', s).lower()).strip()


def eligible_url(url: str) -> bool:
    u = urllib.parse.urlsplit(url)
    return u.scheme == 'https' and u.hostname in ALLOWED_HOSTS and '/pre-raid/' in u.path and not u.username and not u.password and not u.port


def fetch_html(url: str) -> str:
    if not eligible_url(url):
        raise ValueError('unapproved source URL')
    req = urllib.request.Request(url, headers={
        'User-Agent': 'ForeverBiSAuditSync/0.2 (+https://github.com/howonses-cyber/forever-custom-addons; periodic public ranking cross-check)',
        'Accept': 'text/html',
    })
    with urllib.request.urlopen(req, timeout=18) as resp:
        if resp.status != 200 or 'html' not in (resp.headers.get('Content-Type') or '').lower():
            raise ValueError('source did not serve expected HTML')
        if not eligible_url(resp.geturl()):
            raise ValueError('source redirected outside allowlist')
        data = resp.read(3_000_001)
    if not data or len(data) > 3_000_000:
        raise ValueError('source content empty or oversized')
    return data.decode('utf-8', errors='replace')


def get_slot(heading: str) -> str | None:
    clean = re.sub(r'\s+', ' ', heading).strip().lower()
    m = HEAD_PATTERN.match(clean)
    if not m:
        return None
    return SLOT_MAP.get(m.group(1).lower().replace('  ', ' '))


def id_for_link(tag) -> int | None:
    attrs = [tag.get('href', ''), tag.get('data-wowhead', ''), tag.get('data-item-id', ''), tag.get('data-itemid', '')]
    for value in attrs:
        raw = str(value)
        m = ITEM_PATH.search(raw)
        if m:
            return int(m.group(1))
        if raw.isdigit() and 100 <= int(raw) <= 999999999:
            return int(raw)
    return None


def parse_ranking(html: str, url: str, expected_label: str) -> dict:
    """Extract top-per-slot from both sites' public HTML, fail closed on ambiguous markup."""
    soup = BeautifulSoup(html, 'html.parser')
    for tag in soup(['script','style','nav','footer','header','noscript']):
        tag.decompose()
    title = (soup.title.get_text(' ', strip=True) if soup.title else '')[:180]
    main = soup.find('main') or soup.find('article') or soup.body or soup
    intro = main.get_text(' ', strip=True)[:3000].lower()
    tokens=expected_label.lower().split(' ')
    if not all(token in (title+' '+intro).lower() for token in tokens):
        raise ValueError('wrong class/spec page: '+title[:60])
    if not ('bis' in (title+' '+intro).lower() or 'best in slot' in (title+' '+intro).lower()):
        raise ValueError('page does not identify as a BiS ranking')
    if 'pre-raid' not in url:
        raise ValueError('page is not a pre-raid ranking')

    host=urllib.parse.urlsplit(url).hostname
    if host=='foreverwow.gg':
        result=_parse_foreverwow(main,url)
    elif host=='theforeverera.com':
        result=_parse_foreverera(main,url)
    else:
        raise ValueError('unsupported HTML adapter')
    diagnostics={}
    if not result:
        candidates=[a for a in main.find_all('a') if id_for_link(a)]
        anchor=candidates[0] if candidates else main.find('a')
        parents=[]
        p=anchor
        for _ in range(6):
            if not p:break
            parents.append({'tag':p.name, 'class':p.get('class', [])[:9],
                            'text':p.get_text(' ', strip=True)[:145]})
            p=p.parent
        diagnostics={'headings':[h.get_text(' ',strip=True)[:110] for h in main.find_all(['h2','h3','h4'])[:12]],
                     'itemLikeLinks':len(candidates),'ancestors':parents,'htmlSha256':hashlib.sha256(html.encode('utf-8')).hexdigest()}
    return {'url':url,'title':title,'slots':result,'slotCount':len(result),
            'diagnostics':diagnostics,'bodySha256':hashlib.sha256(html.encode('utf-8')).hexdigest()}


def _parse_foreverwow(main, url):
    """Extract explicit top cards inside named slot <section> elements only.

    ForeverWoW's visual slot headers are not h3s. Its ranking cards are
    ordered lists under sections with stable fragment IDs. Never infer slot
    from navigation link order or a global first item.
    """
    result={}
    for section in main.find_all('section'):
        raw=(section.get('id') or section.get('data-slot') or '').strip().lower().replace('-', ' ')
        slot=SLOT_MAP.get(raw)
        if not slot or slot in result:
            continue
        ranked_list=section.find('ol')
        if not ranked_list:
            continue
        first=ranked_list.find('li',recursive=False)
        if not first:
            continue
        summary=first.find('summary') or first
        txt=summary.get_text(' ',strip=True)
        if not (re.search(r'\bBiS\b',txt) or re.search(r'^1\.',txt)):
            continue
        item=None
        for a in summary.find_all('a'):
            ident=id_for_link(a)
            name=a.get_text(' ',strip=True).strip()
            if ident and NAME_RE.match(name):
                item=(ident,name)
                break
        if not item:
            continue
        if BAD_CONTEXT.search(txt):
            result[slot]={'blocked':True,'id':item[0],'name':item[1],'slot':slot,
                          'reason':'source-flagged locked/unconfirmed/faction/raid'}
            continue
        source_match=GOOD_SOURCE.search(txt)
        if not source_match:
            continue
        source=txt[source_match.start():source_match.start()+130]
        source=re.split(r'\s+\d{1,3}%',source,maxsplit=1)[0].strip()
        result[slot]={'id':item[0],'name':item[1],'slot':slot,'source':source,'url':url}
    return result


def _parse_foreverera(main,url):
    """Forever Era pre-raid uses h3 sections and /en/items/#item-ID links."""
    result={}
    for heading in main.find_all(['h2','h3','h4']):
        slot=get_slot(heading.get_text(' ',strip=True))
        if not slot or slot in result:continue
        for node in heading.next_elements:
            if getattr(node,'name',None) in ('h2','h3','h4'):break
            if getattr(node,'name',None)!='a':continue
            ident=id_for_link(node)
            if not ident:continue
            name=node.get_text(' ',strip=True).strip()
            if not NAME_RE.match(name):continue
            parent=node.find_parent(['li','tr','article']) or node.parent
            vicinity=parent.get_text(' ',strip=True)[:400] if parent else ''
            if BAD_CONTEXT.search(vicinity):
                result[slot]={'blocked':True,'id':ident,'name':name,'slot':slot,'reason':'source-flagged locked/unconfirmed/faction/raid'}
                break
            source_match=GOOD_SOURCE.search(vicinity)
            source=(vicinity[source_match.start():source_match.start()+140] if source_match else 'Source unverified by this site')
            result[slot]={'id':ident,'name':name,'slot':slot,'source':source,'url':url}
            break
    return result


def match_sources(a: dict, b: dict, minimum_slots: int, spec_key: str) -> tuple[list, list]:
    """Candidate source agreement is not an actual server-drop verification."""
    good, pending = [], []
    if a['slotCount'] < minimum_slots or b['slotCount'] < minimum_slots:
        pending.append({'spec': spec_key, 'reason': 'parser_low_coverage', 'counts': [a['slotCount'], b['slotCount']]})
        return good, pending
    for slot in sorted(set(a['slots']) | set(b['slots'])):
        first, second = a['slots'].get(slot), b['slots'].get(slot)
        if not first or not second:
            pending.append({'spec': spec_key, 'slot': slot, 'reason': 'not_in_both_sources'})
            continue
        if first.get('blocked') or second.get('blocked'):
            pending.append({'spec': spec_key, 'slot': slot, 'reason': 'restricted_or_unconfirmed_source'})
            continue
        if first['id'] != second['id'] or normalize_name(first['name']) != normalize_name(second['name']):
            pending.append({'spec': spec_key, 'slot': slot, 'reason': 'top_rank_disagreement',
                            'sourceNames': [first['name'], second['name']]})
            continue
        if not GOOD_SOURCE.search(first['source']):
            pending.append({'spec': spec_key, 'slot': slot, 'reason': 'missing_acquisition_evidence'})
            continue
        good.append({'slot': slot, 'name': first['name'], 'itemId': first['id'],
                     'source': first['source'], 'urls': [a['url'], b['url']], 'spec': spec_key,
                     'status': 'unknown'})
    return good, pending


def validate_approval(row: dict) -> None:
    assert set(row) >= {'class', 'spec', 'slot', 'name', 'itemId', 'source', 'urls', 'status', 'checked'}
    assert row['class'].isupper() and re.fullmatch(r'[A-Z]{4,12}', row['class'])
    assert re.fullmatch(r'[a-z-]{3,30}', row['spec'])
    assert row['slot'] in set(SLOT_MAP.values())
    assert 100 <= row['itemId'] <= 999999999
    assert NAME_RE.fullmatch(row['name'])
    assert row['status'] == 'unknown'  # two sites are NOT server drop confirmation
    assert len(row['source']) <= 140 and GOOD_SOURCE.search(row['source'])
    assert len(row['urls']) == 2 and len({urllib.parse.urlsplit(x).hostname for x in row['urls']}) == 2
    assert all(eligible_url(x) for x in row['urls'])
    assert re.fullmatch(r'\d{4}-\d{2}-\d{2}', row['checked'])


def lua_quote(value: str) -> str:
    # Escape Lua source text, including site-provided input. Never emit code from HTML.
    return '"' + value.replace('\\', '\\\\').replace('"', '\\"').replace('\n', ' ').replace('\r', ' ').replace('|', ' / ') + '"'


def build_overlay(version: str, approved: list, date: str) -> str:
    lines = [
        'local _,B=...',
        '-- Automatically generated from two independent public pre-raid rankings.',
        '-- Availability, drop and DPS superiority remain UNVERIFIED.',
        "B.autoMeta={version="+lua_quote(version)+",count="+str(len(approved))+",reviewedAt="+lua_quote(date)+",policy='two-source provisional; no client HTTP'}",
        'B.autoItemIds={}',
        'local function upsert(class,spec,slot,name,id,source,checked,url1,url2)',
        ' local current=nil',
        ' for _,row in ipairs(B.catalog or {}) do',
        "  if row.class==class and row.spec==spec and row.slot==slot then",
        "   if row.name==name and row.status=='locked' then return end",
        '   if row.name==name then current=row end',
        '  end',
        ' end',
        ' for _,row in ipairs(B.catalog or {}) do',
        '  if row.class==class and row.spec==spec and row.slot==slot and row.status~="locked" and row.priority==1 then row.priority=2 end',
        ' end',
        ' if not current then',
        '  current={class=class,spec=spec,slot=slot,name=name,status="unknown",kind="cross-source"}',
        '  B.catalog[#B.catalog+1]=current',
        ' end',
        ' current.priority=1; current.status="unknown"; current.source=source; current.checked=checked',
        ' current.url=url1; current.confirmingURL=url2; current.itemId=id; current.autoEvidence=true',
        ' current.note="Two independent public rankings agree; actual WoW Forever drops, faction and phase still need confirmation."',
        ' B.autoItemIds[string.lower(name)]=id',
        'end',
    ]
    for row in sorted(approved, key=lambda x: (x['class'], x['spec'], x['slot'], x['itemId'])):
        validate_approval(row)
        lines.append('upsert('+','.join([
            lua_quote(row['class']), lua_quote(row['spec']), lua_quote(row['slot']),
            lua_quote(row['name']), str(row['itemId']), lua_quote(row['source']),
            lua_quote(row['checked']),lua_quote(row['urls'][0]),lua_quote(row['urls'][1])
        ])+')')
    return '\n'.join(lines)+'\n'


def bump_patch(version: str) -> str:
    m = re.fullmatch(r'(\d+)\.(\d+)\.(\d+)', version)
    if not m:
        raise ValueError('unsupported version')
    return f'{m.group(1)}.{m.group(2)}.{int(m.group(3))+1}'


def update_addon_archive(repo: Path, state: dict) -> str:
    candidates = list((repo/'addons').glob(ARCHIVE_PREFIX+'*.zip'))
    if len(candidates) != 1:
        raise ValueError('expected exactly one current ForeverBiSAudit archive')
    previous = candidates[0]
    version = state['packageVersion']
    output_name = f'{ARCHIVE_PREFIX}{version}_AutoData.zip'
    output = repo/'addons'/output_name
    rows = state['approved']
    with zipfile.ZipFile(previous, 'r') as z:
        entries = {info.filename: z.read(info) for info in z.infolist() if not info.is_dir()}
    toc_name='ForeverBiSAudit/ForeverBiSAudit.toc'
    core_name='ForeverBiSAudit/Core.lua'
    overlay_name='ForeverBiSAudit/AutoData.lua'
    toc = entries[toc_name].decode('utf-8')
    core = entries[core_name].decode('utf-8')
    toc = re.sub(r'(?m)^## Version: .+$', '## Version: '+version, toc)
    core = re.sub(r"B.version = '[^']+'", "B.version = '"+version+"'", core)
    core = re.sub(r"B.dataVersion = '[^']+'", "B.dataVersion = '"+version+"'", core)
    entries[toc_name]=toc.encode('utf-8')
    entries[core_name]=core.encode('utf-8')
    entries[overlay_name]=build_overlay(version, rows, now_utc()[:10]).encode('utf-8')
    # Reproducible byte order and no packaged executables or unsafe paths.
    with zipfile.ZipFile(output, 'w', compression=zipfile.ZIP_DEFLATED, compresslevel=9) as z:
        for name in sorted(entries):
            if not name.startswith('ForeverBiSAudit/') or '..' in name or name.endswith(('.exe','.ps1','.dll','.bat')):
                raise ValueError('unsafe addon ZIP path')
            info=zipfile.ZipInfo(name, (2026,1,1,0,0,0))
            info.compress_type=zipfile.ZIP_DEFLATED
            z.writestr(info,entries[name],compress_type=zipfile.ZIP_DEFLATED,compresslevel=9)
    with zipfile.ZipFile(output) as z:
        assert z.read(toc_name).decode('utf-8').find('## Version: '+version)>=0
        assert b'B.autoMeta' in z.read(overlay_name)
        assert len(z.namelist())==len(entries)
    if previous != output:
        previous.unlink()
    return output_name


def monitor(repo: Path, snapshots: dict | None, allow_publish: bool) -> dict:
    profile_conf=json.loads((repo/'bis-sync/sources.json').read_text('utf-8'))
    state_path=repo/'bis-sync/approved.json'
    state=json.loads(state_path.read_text('utf-8'))
    if profile_conf.get('schema')!=1 or state.get('schema')!=1:
        raise ValueError('bad synchronization schema')
    before=json.loads(json.dumps(state))
    pending=[];results=[];proposals={}
    t=now_utc()
    for profile in profile_conf['profiles']:
        spec_key=profile['class']+':'+profile['spec']
        sources=profile['sources']
        if len(sources)!=2 or len({urllib.parse.urlsplit(u).hostname for u in sources})!=2:
            raise ValueError('invalid independent source configuration')
        try:
            parsed=[]
            for url in sources:
                html=snapshots[url] if snapshots is not None else fetch_html(url)
                doc=parse_ranking(html,url,profile['label'])
                parsed.append(doc)
                if snapshots is None: time.sleep(0.5)
            accepted,review=match_sources(parsed[0],parsed[1],profile_conf['minimumSlotsPerSource'],spec_key)
            pending.extend(review)
            results.append({'spec':spec_key,'state':'parsed',
                            'slots':[p['slotCount'] for p in parsed],
                            'agreed':len(accepted),'needsReview':len(review),
                            'sourceDigests':[p['bodySha256'] for p in parsed]})
            for item in accepted:
                key=(spec_key,item['slot'])
                if key in proposals:
                    pending.append({'spec':spec_key,'slot':item['slot'],'reason':'duplicate_proposal'})
                    continue
                proposals[key]=dict(item, class_=profile['class'], spec_=profile['spec'])
        except (KeyError, ValueError, OSError, TimeoutError, UnicodeError) as e:
            # Network/DOM failures never revoke prior approved gear or publish guesses.
            results.append({'spec':spec_key,'state':'unavailable','reason':str(e)[:160]})
    # Honor explicit manual unavailable/locked records, even if external guides rank them.
    old_archives=list((repo/'addons').glob(ARCHIVE_PREFIX+'*.zip'))
    if len(old_archives)!=1:
        raise ValueError('expected one current BiS archive for protection checks')
    locked=set()
    with zipfile.ZipFile(old_archives[0]) as z:
        base=z.read('ForeverBiSAudit/Data.lua').decode('utf-8')
    for line in base.splitlines():
        if 'status="locked"' not in line:
            continue
        fields=dict(re.findall(r'(class|spec|slot|name)="([^"]+)"',line))
        if len(fields)==4:
            locked.add((fields['class']+':'+fields['spec'],fields['slot'],normalize_name(fields['name'])))
    updated={ (r['class']+':'+r['spec'],r['slot']):r for r in state['approved'] }
    changes=[]
    for key,row in sorted(proposals.items()):
        if (key[0],key[1],normalize_name(row['name'])) in locked:
            pending.append({'spec':key[0],'slot':key[1],'reason':'owner_phase_lock'})
            continue
        proposed={'class':row['class_'],'spec':row['spec_'],'slot':row['slot'],
                  'name':row['name'],'itemId':row['itemId'],'source':row['source'],
                  'urls':row['urls'],'status':'unknown','checked':t[:10]}
        validate_approval(proposed)
        old=updated.get(key)
        if old and old['itemId']==proposed['itemId'] and normalize_name(old['name'])==normalize_name(proposed['name']):
            continue
        # Never publish if an existing manual lock names the same piece.
        changes.append({'spec':key[0],'slot':key[1], 'old':old['name'] if old else None,'new':row['name']})
        updated[key]=proposed
    changed=bool(changes)
    if changed and allow_publish:
        state['revision']=int(state['revision'])+1
        state['packageVersion']=bump_patch(state['packageVersion'])
        state['approved']=list(updated.values())
        output_name=update_addon_archive(repo,state)
        state_path.write_text(json.dumps(state,ensure_ascii=False,indent=2,sort_keys=True)+'\n','utf-8')
    else:
        output_name=None
    any_unavailable=any(z['state']=='unavailable' for z in results)
    report={'schema':1,'state':'published' if output_name else ('review-needed' if pending else ('unavailable' if any_unavailable else 'unchanged')),
            'lastCheckedUtc':t,'approvedChanges':len(changes) if output_name else 0,
            'potentialChanges':len(changes),'pendingChanges':len(pending),
            'results':results,'pending':pending[:120],
            'package':output_name,
            'note':'Automated cross-source ranking consensus is provisional, not confirmed server availability; client installs remain button-only.'}
    if allow_publish:
        (repo/'bis-sync/report.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n','utf-8')
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--root',type=Path,default=Path('.'))
    p.add_argument('--apply',action='store_true')
    p.add_argument('--fixture',type=Path,help='JSON map from source URL to fixture HTML')
    args=p.parse_args()
    snapshots=json.loads(args.fixture.read_text('utf-8')) if args.fixture else None
    report=monitor(args.root,snapshots,args.apply)
    print(json.dumps({'state':report['state'],'checked':report['lastCheckedUtc'],
                      'approvedChanges':report['approvedChanges'],'potential':report['potentialChanges'],
                      'needsReview':report['pendingChanges'],'profiles':report['results']},indent=2))


if __name__=='__main__':
    main()