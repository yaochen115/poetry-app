import unittest
from import_hf_translations_v1_0_0 import split_translation

class SectionTests(unittest.TestCase):
    def test_separate_translation_notes_and_references(self):
        tr,notes=split_translation('<p>译文<br>这是现成的译文。</p><p>注释<br>春：春天。</p><p>参考资料<br>某书</p>','译文及注释')
        self.assertEqual(tr,'这是现成的译文。');self.assertEqual(notes,'春：春天。')

    def test_annotations_alone_are_not_imported(self):
        self.assertEqual(split_translation('注释\n春：春天。','译文及注释')[0],'')
        self.assertEqual(split_translation('春：春天。','注释')[0],'')

    def test_standalone_explicit_translation(self):
        self.assertEqual(split_translation('这是现成的作品译文。','译文')[0],'这是现成的作品译文。')
        self.assertEqual(split_translation('这是一段赏析。','赏析')[0],'')

if __name__=='__main__':unittest.main()
