import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

import crawl_gushiwenku_v1_0_1 as fast
from translation_overlay_v1_0_0 import apply,overlay_for


class FastImportTests(unittest.TestCase):
    def test_translation_does_not_require_tags_notes_or_dictionary(self):
        html=(fast.ROOT/'expansion/gushiwenku-samples-v1.0.0/064809f.html').read_text(encoding='utf-8')
        row=fast.old.parse(html)
        poem=dict(id='tang-577',title='不同题名',author=row['writer'],content=row['content'],category='唐诗',tags=[])
        pipe=SimpleNamespace(pending={'tang-577':poem},poems={'tang-577':poem},tags={'唐诗':[]},dictionary={},input_hash=lambda p:'x')
        meta=dict(url=fast.old.BASE+'/shiwen/064809f/',sha256='x',fetchedAt='x',blob='x.html')
        entry,held=fast.candidate(html,meta,pipe,fast.WORK)
        self.assertIsNone(held)
        self.assertIn('dictionary',entry['pending']);self.assertIn('themeTags',entry['pending'])
        self.assertTrue(entry['titleAlias']);self.assertFalse(entry['literaryApproved'])
        pipe.pending['tang-577']['author']='李白'
        self.assertIsNone(fast.candidate(html,meta,pipe,fast.WORK)[0])

    def fixture(self,root):
        poem=dict(id='tang-001',title='样例',author='作者',content='山川春',translation='',notes=[],tags=[],editorialStatus='original_only')
        document=dict(dataVersion='1.2.12',items=[poem])
        for folder in ('data','app/assets/data','expansion/cache'):(root/folder).mkdir(parents=True,exist_ok=True)
        for folder in ('data','app/assets/data'):(root/folder/'poems.json').write_text(json.dumps(document),encoding='utf-8')
        raw=b'sample';(root/'expansion/cache/source.html').write_bytes(raw)
        entry=dict(id='tang-001',baseContent='山川春',baseAuthor='作者',translation='这是春天的山川景色。',
            notes=[],tags=[],pending=['notes','themeTags','dictionary','semanticReview'],literaryApproved=False,
            source=dict(cacheFile='expansion/cache/source.html',sha256=hashlib.sha256(raw).hexdigest()))
        return poem,document,entry

    def test_partial_import_preserves_canonical_state_and_is_idempotent(self):
        with tempfile.TemporaryDirectory(dir=fast.ROOT/'expansion/working') as folder:
            root=Path(folder);poem,doc,entry=self.fixture(root)
            self.assertEqual(apply([entry],root)['added'],1)
            saved=json.loads((root/'data/poems.json').read_text(encoding='utf-8'))
            self.assertEqual(saved['items'][0],poem)
            self.assertEqual(overlay_for(saved,poem)['translation'],entry['translation'])
            self.assertEqual((root/'data/poems.json').read_bytes(),(root/'app/assets/data/poems.json').read_bytes())
            self.assertEqual(apply([entry],root)['added'],0)

    def test_source_tampering_prevents_write(self):
        with tempfile.TemporaryDirectory(dir=fast.ROOT/'expansion/working') as folder:
            root=Path(folder);poem,doc,entry=self.fixture(root)
            before=(root/'data/poems.json').read_bytes()
            (root/'expansion/cache/source.html').write_bytes(b'changed')
            with self.assertRaisesRegex(ValueError,'Source changed'):apply([entry],root)
            self.assertEqual((root/'data/poems.json').read_bytes(),before)

    def test_stale_overlay_cannot_change_reading(self):
        poem=dict(id='tang-001',content='原文',author='作者')
        doc=dict(translationImports={'tang-001':dict(baseContent='他文',baseAuthor='作者',translation='错误译文')})
        self.assertIsNone(overlay_for(doc,poem))


if __name__=='__main__':unittest.main()
