import copy
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
import sync_poetry_api_v1_0_0 as sync


def poem(i='tang-001', author='李白', content='床前明月光，疑是地上霜。'):
    return dict(id=i, category='唐诗', title='静夜思', author=author, dynasty='唐', content=content,
                translation='原有译文不能覆盖', tags=['思乡'], notes=[])


def selected(content='春江潮水连海平，海上明月共潮生。', author='张若虚'):
    return dict(id='poem-catalog-test', genre='诗', title='春江花月夜', author=author, dynasty='唐',
                canonicalFingerprint=sync.norm(content), matchingText=content)


def accepted(p=None):
    p=p or selected()
    return dict(selected=p, content=p['matchingText'], source=dict(providerId=10, cacheFile='expansion/cache.json', sha256='test'), row=dict(id=10))


def document():
    return dict(dataVersion='1.2.25', items=[poem()], selectionProfile=dict(ids=['tang-001'], expectedCounts={'唐诗':1}), translationImports={'tang-001':{'untouched':'value'}})


class SyncTests(unittest.TestCase):
    def test_wrong_author_partial_and_similar_text_never_import(self):
        p=selected()
        good={k:v for k,v in accepted(p).items() if k!='selected'}
        wrong={(sync.norm('李白'),p['canonicalFingerprint']):[good]}
        short={(sync.norm(p['author']),p['canonicalFingerprint'][:6]):[good]}
        self.assertEqual(sync.resolve([p],wrong)[0],[])
        self.assertEqual(sync.resolve([p],short)[0],[])
        self.assertEqual(len(sync.resolve([p],{(sync.norm(p['author']),p['canonicalFingerprint']):[good]})[0]),1)

    def test_existing_id_translation_and_overlay_preserved_and_rerun_idempotent(self):
        old=document();p=selected(old['items'][0]['content'],'李白')
        new,report=sync.plan(old,[accepted(p)])
        self.assertEqual(new['items'],old['items'])
        self.assertEqual(new['translationImports'],old['translationImports'])
        self.assertEqual(new['poetryApiBindings'][p['id']]['appId'],'tang-001')
        again,r=sync.plan(new,[accepted(p)])
        self.assertFalse(r['changed'])
        self.assertEqual(again,new)

    def test_new_rows_original_only_not_fake_translation_or_wrong_era(self):
        old=document();p=selected(author='苏轼');p['dynasty']='宋'
        new,r=sync.plan(old,[accepted(p)])
        row=new['items'][-1]
        self.assertEqual(new['items'][0],old['items'][0])
        self.assertEqual((row['genre'],row['dynasty'],row['translation']),('诗','宋',''))
        self.assertEqual(row['editorialStatus'],'original_only')
        self.assertEqual(new['selectionProfile']['expectedCounts'],{'唐诗':2})
        self.assertIn(row['id'],new['selectionProfile']['ids'])

    def test_activating_earlier_archived_row_does_not_reorder_profile_on_next_run(self):
        old=document()
        archived=poem('tang-002','张若虚',selected()['matchingText'])
        old['items'].insert(0,archived)
        first,r=sync.plan(old,[accepted()])
        self.assertEqual(first['selectionProfile']['ids'],['tang-001','tang-002'])
        second,r=sync.plan(first,[accepted()])
        self.assertFalse(r['changed'])
        self.assertEqual(second,first)

    def test_cross_author_duplicate_is_held_not_attribution_silently_changed(self):
        old=document();p=selected(old['items'][0]['content'],'朱斌')
        new,r=sync.plan(old,[accepted(p)])
        self.assertEqual(new,old)
        self.assertFalse(r['changed'])
        self.assertEqual(len(r['conflicts']),1)

    def test_apply_failure_rolls_back_database_and_assets(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'data/poems.json';asset=root/'app/assets/data/poems.json'
            data.parent.mkdir(parents=True);asset.parent.mkdir(parents=True)
            old=document();raw=json.dumps(old).encode();data.write_bytes(raw);asset.write_bytes(raw)
            new,r=sync.plan(old,[accepted()])
            with patch.object(sync.subprocess,'run',side_effect=RuntimeError('verification failed')):
                with self.assertRaises(RuntimeError):sync.apply(old,new,r,root=root)
            self.assertEqual(data.read_bytes(),raw);self.assertEqual(asset.read_bytes(),raw)
            self.assertTrue(list((root/'expansion/checkpoints').glob('*/data/poems.json')))
            self.assertFalse((root/'data/versions/poems-v1.2.26.json').exists())

    def test_rate_limit_stops_further_network_requests(self):
        with tempfile.TemporaryDirectory() as tmp:
            client=sync.Client(interval=.5)
            error=HTTPError('https://poetry.palemoky.com/api/search',429,'limited',None,None)
            with patch.object(sync,'CACHE',Path(tmp)),patch.object(sync,'urlopen',side_effect=error) as request:
                with self.assertRaises(HTTPError):client.search('春江花月夜')
                with self.assertRaises(RuntimeError):client.search('静夜思')
                self.assertEqual(request.call_count,1)

    def test_tampered_cache_is_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);base=root/'expansion/provider'
            cache=base/'provider-api/cache/a.json';meta=base/'provider-api/metadata/a.json'
            cache.parent.mkdir(parents=True);meta.parent.mkdir(parents=True)
            cache.write_text('{"data":[]}',encoding='utf-8')
            meta.write_text(json.dumps({'url':'https://poetry.palemoky.com/api/poems','sha256':'wrong'}),encoding='utf-8')
            with self.assertRaises(ValueError):sync.provider_index(root,base)


if __name__=='__main__':unittest.main()
