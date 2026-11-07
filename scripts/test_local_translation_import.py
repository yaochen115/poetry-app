from types import SimpleNamespace
import unittest
from import_local_translations_v1_0_0 import build_entry,usable_translation


class LocalImportTests(unittest.TestCase):
    def test_annotations_and_placeholders_are_not_translations(self):
        self.assertIsNone(usable_translation('注释：春是春天，山是山峰。'))
        self.assertIsNone(usable_translation('本篇暂无翻译，请等待。'))
        self.assertIsNone(usable_translation('很短'))

    def test_partial_translation_accepted_without_tags_or_notes(self):
        poem=dict(id='tang-001',author='李白',content='山川风雨',title='原题',category='唐诗',tags=[])
        pipe=SimpleNamespace(dictionary={},tags={'唐诗':['山水']})
        row=dict(writer='李白',title='别名',content='山川，風雨。',translation='山川之上风雨正在到来。')
        entry=build_entry(row,poem,pipe,{})
        self.assertTrue(entry['titleAlias']);self.assertFalse(entry['literaryApproved'])
        self.assertIn('notes',entry['pending']);self.assertIn('dictionary',entry['pending'])
        row['writer']='杜甫';self.assertIsNone(build_entry(row,poem,pipe,{}))

    def test_body_mismatch_is_not_relaxed(self):
        poem=dict(id='tang-001',author='李白',content='山川风雨',title='原题',category='唐诗',tags=[])
        row=dict(writer='李白',content='不同原文',translation='这里是一篇其他作品的译文。')
        self.assertIsNone(build_entry(row,poem,SimpleNamespace(),{}))


if __name__=='__main__':unittest.main()
