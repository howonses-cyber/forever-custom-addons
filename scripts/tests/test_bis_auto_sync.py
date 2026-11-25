import json
import tempfile
import unittest
from pathlib import Path
import sys
import zipfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import bis_auto_sync as sync


def source_html(label='Enhancement Shaman', first='Black Dragonscale Helm', item_id=12345, status='Crafted: Leatherworking', host='foreverwow.gg'):
    slots=['Head','Neck','Shoulder','Back','Chest','Legs']
    rows=[]
    for i,slot in enumerate(slots):
        n=first if i==0 else 'Sample Item '+slot
        ident=item_id if i==0 else item_id + i
        if host=='foreverwow.gg':
            rows.append(f'<section id="{slot.lower()}"><ol><li><details><summary>BiS <a href="https://www.wowhead.com/forever/item={ident}">{n}</a> {status} 100%</summary></details></li></ol></section>')
        else:
            rows.append(f'<h3>{slot} - best {slot} for {label}</h3><table><tr><td>1.</td><td><a href="/en/items/#item-{ident}">{n}</a></td><td>{status}</td></tr></table>')
    return '<html><head><title>'+label+' Pre-raid BiS Gear</title></head><body><main><h1>'+label+' Pre-raid BiS</h1>\n'+''.join(rows)+'</main></body></html>'


class ParserTests(unittest.TestCase):
    def test_parses_exact_slot_item_and_id(self):
        data=sync.parse_ranking(source_html(),'https://foreverwow.gg/shaman/enhancement/pre-raid/','Enhancement Shaman')
        self.assertEqual(data['slotCount'],6)
        self.assertEqual(data['slots']['Head']['id'],12345)
        self.assertEqual(data['slots']['Head']['source'],'Crafted: Leatherworking')

    def test_requires_two_matching_sources(self):
        a=sync.parse_ranking(source_html(),'https://foreverwow.gg/shaman/enhancement/pre-raid/','Enhancement Shaman')
        b=sync.parse_ranking(source_html(host='theforeverera.com'),'https://theforeverera.com/en/bis/shaman/enhancement/pre-raid/','Enhancement Shaman')
        accepted,pending=sync.match_sources(a,b,5,'SHAMAN:enhancement')
        self.assertEqual(len(accepted),6)
        self.assertFalse(pending)
        b['slots']['Head']['id']=90999
        accepted,pending=sync.match_sources(a,b,5,'SHAMAN:enhancement')
        self.assertEqual(len(accepted),5)
        self.assertTrue(any(x['reason']=='top_rank_disagreement' for x in pending))

    def test_source_coverage_refuses_update(self):
        a=sync.parse_ranking(source_html(),'https://foreverwow.gg/shaman/enhancement/pre-raid/','Enhancement Shaman')
        b=sync.parse_ranking(source_html(host='theforeverera.com'),'https://theforeverera.com/en/bis/shaman/enhancement/pre-raid/','Enhancement Shaman')
        b['slots']={'Head':b['slots']['Head']};b['slotCount']=1
        accepted,pending=sync.match_sources(a,b,5,'SHAMAN:enhancement')
        self.assertEqual(accepted,[])
        self.assertEqual(pending[0]['reason'],'parser_low_coverage')

    def test_blocks_raid_unconfirmed_and_horde(self):
        for status in ['Drop: Molten Core raid', 'Drop: Example unconfirmed in Forever', 'Quest: Horde only', 'Vendor: Alterac Valley']:
            p=sync.parse_ranking(source_html(status=status),'https://foreverwow.gg/shaman/enhancement/pre-raid/','Enhancement Shaman')
            self.assertTrue(p['slots']['Head'].get('blocked'),status)

    def test_rejects_wrong_spec_and_host(self):
        with self.assertRaises(ValueError):
            sync.parse_ranking(source_html(),'https://foreverwow.gg/shaman/enhancement/pre-raid/','Frost Mage')
        self.assertFalse(sync.eligible_url('https://evil.example.com/shaman/enhancement/pre-raid/'))
        self.assertFalse(sync.eligible_url('http://foreverwow.gg/shaman/enhancement/pre-raid/'))

    def test_overlay_is_escaped_and_keeps_locked(self):
        row={'class':'SHAMAN','spec':'enhancement','slot':'Head','name':'Black Dragonscale Helm','itemId':12345,
             'source':'Crafted: Leatherworking','status':'unknown','checked':'2026-11-24',
             'urls':['https://foreverwow.gg/shaman/enhancement/pre-raid/','https://theforeverera.com/en/bis/shaman/enhancement/pre-raid/']}
        lua=sync.build_overlay('0.2.1',[row],'2026-11-24')
        self.assertIn("row.status=='locked'",lua)
        self.assertIn('12345',lua)
        self.assertIn('B.autoItemIds',lua)
        self.assertEqual(sync.bump_patch('0.2.3'),'0.2.4')

    def test_existing_zip_rebuilt_from_state(self):
        repository=Path(__file__).resolve().parents[2]
        candidates=list((repository/'addons').glob('ForeverBiSAudit_Forever_v*.zip'))
        self.assertEqual(len(candidates),1,'CI repository must contain the managed BiS addon ZIP')
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'addons').mkdir()
            archive=root/'addons'/candidates[0].name
            archive.write_bytes(candidates[0].read_bytes())
            current=sync.archive_version(archive)
            target=sync.bump_patch(current)
            before=archive.read_bytes()
            for stale in ('0.2.1', current):
                if sync.version_key(stale) <= sync.version_key(current):
                    with self.assertRaises(ValueError):
                        sync.update_addon_archive(root,{'packageVersion':stale,'approved':[]})
                    self.assertEqual(archive.read_bytes(),before)
            state={'packageVersion':target,'approved':[]}
            name=sync.update_addon_archive(root,state)
            self.assertEqual(name,'ForeverBiSAudit_Forever_v'+target+'_AutoData.zip')
            with zipfile.ZipFile(root/'addons'/name) as z:
                self.assertIn('## Version: '+target,z.read('ForeverBiSAudit/ForeverBiSAudit.toc').decode())
                self.assertIn("B.dataVersion = '"+target+"'",z.read('ForeverBiSAudit/Core.lua').decode())
                self.assertIn('B.autoMeta',z.read('ForeverBiSAudit/AutoData.lua').decode())

    def test_monitor_can_publish_consensus_as_provisional_only(self):
        repository=Path(__file__).resolve().parents[2]
        candidates=list((repository/'addons').glob('ForeverBiSAudit_Forever_v*.zip'))
        self.assertEqual(len(candidates),1)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'addons').mkdir();(root/'bis-sync').mkdir()
            (root/'addons'/candidates[0].name).write_bytes(candidates[0].read_bytes())
            src=json.loads((repository/'bis-sync/sources.json').read_text('utf-8'))
            src['profiles']=src['profiles'][:1]
            (root/'bis-sync/sources.json').write_text(json.dumps(src))
            state=json.loads((repository/'bis-sync/approved.json').read_text('utf-8'))
            archive=next((root/'addons').glob('ForeverBiSAudit*.zip'))
            current=sync.archive_version(archive)
            target=sync.bump_patch(current)
            state['approved']=[]
            state['packageVersion']='0.0.1'
            state_path=root/'bis-sync/approved.json'
            state_path.write_text(json.dumps(state))
            original=archive.read_bytes()
            original_state=state_path.read_bytes()
            urls=src['profiles'][0]['sources']
            fixture=source_html(item_id=60001)
            stale_report=sync.monitor(root,{urls[0]:fixture,urls[1]:source_html(item_id=60001,host='theforeverera.com')},True)
            self.assertEqual(stale_report['state'],'baseline-mismatch')
            self.assertEqual(stale_report['approvedChanges'],0)
            self.assertEqual(archive.read_bytes(),original)
            self.assertEqual(state_path.read_bytes(),original_state)
            self.assertEqual(len(list((root/'addons').glob('ForeverBiSAudit*.zip'))),1)
            state['packageVersion']=current
            state_path.write_text(json.dumps(state))
            report=sync.monitor(root,{urls[0]:fixture,urls[1]:source_html(item_id=60001,host='theforeverera.com')},True)
            self.assertEqual(report['state'],'published')
            self.assertEqual(report['approvedChanges'],6)
            self.assertEqual(len(list((root/'addons').glob('ForeverBiSAudit*.zip'))),1)
            stored=json.loads((root/'bis-sync/approved.json').read_text('utf-8'))
            self.assertEqual(stored['packageVersion'],target)
            self.assertTrue(all(row['status']=='unknown' for row in stored['approved']))
            archive=next((root/'addons').glob('ForeverBiSAudit*.zip'))
            with zipfile.ZipFile(archive) as z:
                contents=z.read('ForeverBiSAudit/AutoData.lua').decode('utf-8')
                self.assertIn('upsert("SHAMAN","enhancement","Head"',contents)
                self.assertIn('status="unknown"',contents)
            # A second unchanged daily observation must NOT produce another ZIP version.
            report2=sync.monitor(root,{urls[0]:fixture,urls[1]:source_html(item_id=60001,host='theforeverera.com')},True)
            self.assertEqual(report2['approvedChanges'],0)
            state2=json.loads((root/'bis-sync/approved.json').read_text('utf-8'))
            self.assertEqual(state2['packageVersion'],target)

    def test_owner_locked_item_never_auto_promotes(self):
        repository=Path(__file__).resolve().parents[2]
        candidates=list((repository/'addons').glob('ForeverBiSAudit_Forever_v*.zip'))
        self.assertEqual(len(candidates),1)
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'addons').mkdir()
            (root/'bis-sync').mkdir()
            (root/'addons'/candidates[0].name).write_bytes(candidates[0].read_bytes())
            src=json.loads((repository/'bis-sync/sources.json').read_text('utf-8'))
            src['profiles']=src['profiles'][:1]
            (root/'bis-sync/sources.json').write_text(json.dumps(src))
            state=json.loads((repository/'bis-sync/approved.json').read_text('utf-8'))
            (root/'bis-sync/approved.json').write_text(json.dumps(state))
            urls=src['profiles'][0]['sources']
            fixture=source_html(first='The Unstoppable Force',item_id=19323,status='Vendor: Gaelden').replace('<section id="head">', '<section id="two-hand">')
            report=sync.monitor(root,{urls[0]:fixture,urls[1]:source_html(first='The Unstoppable Force',item_id=19323,status='Vendor: Gaelden',host='theforeverera.com').replace('<h3>Head - best Head', '<h3>Two-Hand - best Two-Hand')},False)
            self.assertTrue(any(x['reason']=='owner_phase_lock' for x in report['pending']))
            self.assertEqual(report['approvedChanges'],0)
            self.assertTrue(any(x['slot']=='TwoHand' for x in report['pending']))



if __name__=='__main__':
    unittest.main()