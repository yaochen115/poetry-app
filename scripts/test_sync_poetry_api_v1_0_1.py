import threading
import json
import tempfile
from pathlib import Path
from unittest.mock import patch
import unittest
from collections import defaultdict
import sync_poetry_api_v1_0_1 as new
from test_sync_poetry_api import document


class QueryTests(unittest.TestCase):
    def test_phrase_does_not_join_verse_across_punctuation(self):
        p=dict(matchingText='故人西辞黄鹤楼，烟花三月下扬州。')
        self.assertEqual(new.phrase_query(p),'故人西辞黄鹤楼')
        self.assertNotIn('楼烟',new.phrase_query(p))

    def test_short_ci_clause_and_five_character_clause(self):
        self.assertEqual(new.phrase_query(dict(matchingText='寻寻觅觅，冷冷清清。')),'寻寻觅觅')
        self.assertEqual(new.phrase_query(dict(matchingText='花间一壶酒，独酌无相亲。')),'花间一壶酒')

    def test_title_fallback_does_not_search_tune_and_incipit_as_one_string(self):
        self.assertEqual(new.title_query(dict(title='水调歌头·明月几时有')),'水调歌头')
        self.assertIsNone(new.title_query(dict(title='春晓')))

    def test_unusable_reference_does_not_invent_a_query(self):
        self.assertIsNone(new.phrase_query(dict(matchingText='')))

    def variant_fixture(self):
        body='月落乌啼霜满天，江枫渔火对愁眠。姑苏城外寒山寺，夜半钟声到客船。'
        source=body.replace('江枫','江村')
        p=dict(id='catalog-variant',title='枫桥夜泊',author='张继',genre='诗',dynasty='唐',canonicalFingerprint=new.old.norm(body),matchingText=body)
        hit=dict(row=dict(id=1,title='枫桥夜泊',author={'name':'张继'},content=[source]),content=source,source={'providerId':1})
        return p,hit

    def test_full_length_variant_passes_but_partial_and_different_title_do_not(self):
        p,hit=self.variant_fixture()
        self.assertIsNotNone(new.variant_confidence(p,hit))
        shorter=dict(hit,content=hit['content'][:14])
        self.assertIsNone(new.variant_confidence(p,shorter))
        wrong=dict(hit,row=dict(hit['row'],title='另外一首'))
        self.assertIsNone(new.variant_confidence(p,wrong))

    def test_variant_is_archived_without_overwriting_existing_poem_or_translation(self):
        p,hit=self.variant_fixture();doc=document()
        row=dict(doc['items'][0],author=p['author'],title=p['title'],content=p['matchingText'])
        doc['items']=[row]
        entry=dict(selected=p,**hit,variant=new.variant_confidence(p,hit))
        proposed,summary=new.variant_plan(doc,[entry])
        self.assertEqual(proposed['items'],doc['items'])
        b=proposed['poetryApiBindings'][p['id']]
        self.assertEqual(b['appId'],row['id'])
        self.assertEqual(b['sourceVariant']['content'],hit['content'])
        self.assertTrue(b['sourceVariant']['variantReviewPending'])
        again,r=new.variant_plan(proposed,[entry])
        self.assertFalse(r['changed']);self.assertEqual(again,proposed)

    def test_new_variant_poem_stores_actual_provider_original_and_reference_separately(self):
        p,hit=self.variant_fixture();entry=dict(selected=p,**hit,variant=new.variant_confidence(p,hit))
        proposed,summary=new.variant_plan(document(),[entry])
        self.assertEqual(proposed['items'][-1]['content'],hit['content'])
        self.assertEqual(proposed['poetryApiBindings'][p['id']]['catalogReferenceFingerprint'],p['canonicalFingerprint'])

    def test_already_bound_identity_never_creates_an_orphan_row_for_a_different_variant(self):
        p,hit=self.variant_fixture();entry=dict(selected=p,**hit,variant=new.variant_confidence(p,hit))
        first,_=new.variant_plan(document(),[entry])
        other=dict(entry,content=entry['content'].replace('江村','江枫'))
        again,summary=new.variant_plan(first,[other])
        self.assertEqual(again,first)
        self.assertFalse(summary['changed'])

    def test_failed_source_audit_rolls_back_before_commit_or_snapshot(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);data=root/'data/poems.json';asset=root/'app/assets/data/poems.json'
            data.parent.mkdir(parents=True);asset.parent.mkdir(parents=True)
            old=document();raw=json.dumps(old).encode();data.write_bytes(raw);asset.write_bytes(raw)
            p,hit=self.variant_fixture();entry=dict(selected=p,**hit,variant=new.variant_confidence(p,hit))
            proposed,summary=new.variant_plan(old,[entry])
            with patch.object(new.subprocess,'run',side_effect=[None,RuntimeError('source audit failed')]):
                with self.assertRaises(RuntimeError):new.commit_with_audit(old,proposed,summary,root)
            self.assertEqual(data.read_bytes(),raw);self.assertEqual(asset.read_bytes(),raw)
            self.assertFalse((root/'data/versions/poems-v1.2.26.json').exists())

    def test_response_rows_are_usable_by_strict_source_matcher(self):
        content='故人西辞黄鹤楼，烟花三月下扬州。'
        row=dict(id=20,title='黄鹤楼送孟浩然之广陵',author={'name':'李白'},content=[content])
        index=defaultdict(list);path=new.ROOT/'expansion/fake-api-cache.json'
        response=({'data':[row]},{'url':'https://poetry.palemoky.com/api/search','sha256':'test'},path,False)
        self.assertEqual(new.add_response(index,response),1)
        self.assertEqual(new.add_response(index,response),0)
        poem=dict(id='catalog-a',title=row['title'],author='李白',canonicalFingerprint=new.old.norm(content))
        self.assertEqual(len(new.old.resolve([poem],index)[0]),1)
        poem['author']='杜甫'
        self.assertEqual(new.old.resolve([poem],index)[0],[])

    def test_zero_yield_circuit_does_not_run_whole_queue(self):
        class Dummy:
            requests=0;budget=100;reason=None
            def __init__(self):self.stop=threading.Event()
            def search(self,q):
                self.requests+=1
                return {'data':[]},{'url':'https://poetry.palemoky.com/api/search','sha256':'x'},new.ROOT/'expansion/fake.json',False
        client=Dummy();items=[dict(id=str(i),title='题名',author='作者',canonicalFingerprint='正文'+str(i)) for i in range(50)]
        records=[]
        new.run_stage('test',items,lambda p:p['id'],client,defaultdict(list),items,2,records,3)
        self.assertTrue(client.stop.is_set())
        self.assertLessEqual(len(records),5)
        self.assertGreaterEqual(len(records),3)


if __name__=='__main__':unittest.main()
