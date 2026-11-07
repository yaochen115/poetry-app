import unittest
from audit_release_content_v1_0_0 import valid_pinyin,compact,audit
from supplement_release_dictionary_v1_0_0 import sense


class ReleaseAuditTests(unittest.TestCase):
    def test_tone_marks_and_numbers_are_both_valid(self):
        for value in ('yī','nǚ','lü4','lv4','zhong1','ń'):
            self.assertTrue(valid_pinyin(value),value)
        for value in ('','拼音','abc!','bo9',None):self.assertFalse(valid_pinyin(value),value)

    def test_sense_extraction_rejects_mixed_or_broken_entries(self):
        self.assertEqual(sense('筷子。另有典故。'),'筷子。')
        self.assertIsNone(sense('单位；发：头发。'))
        self.assertIsNone(sense('印“崦嵫”，传说中的山。'))
        self.assertIsNone(sense('“未闭合的引号。'))

    def test_compact_preserves_meaningful_characters(self):
        self.assertEqual(compact('第一句。\n 第二句！'),'第一句。第二句！')
        self.assertNotEqual(compact('一百'),compact('二百'))

    def test_current_release_sources_replay_without_errors(self):
        report=audit()
        self.assertEqual(report['errors'],[])
        self.assertEqual(report['availableTranslations']+report['missingTranslations'],report['selected'])
        self.assertGreater(report['sourceImportsReplayed'],0)


if __name__=='__main__':unittest.main()
