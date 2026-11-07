import unittest
from prepare_reference_review_v1_0_0 import extract_notes, flags_for


class ReferenceChecks(unittest.TestCase):
    def test_notes_use_original_body_glyphs(self):
        notes=extract_notes('①阑干（lán）：纵横。\n词牌：标题术语。\n阑干：重复。','泪阑干')
        self.assertEqual(notes,[dict(term='阑干',meaning='纵横。')])

    def test_annotation_is_not_translation(self):
        flags=flags_for(dict(translationReference='注释：甲',sourceAuthor='李白'),
                        dict(author='李白'),[{}, {}, {}])
        self.assertIn('annotation_in_translation_field',flags)

    def test_author_mismatch_and_short_notes(self):
        flags=flags_for(dict(translationReference='正文译文',sourceAuthor='佚名'),
                        dict(author='王维'),[])
        self.assertIn('author_requires_comparison',flags)
        self.assertIn('fewer_than_three_parsed_body_notes',flags)

    def test_no_fabricated_notes(self):
        self.assertEqual(extract_notes('这是一段没有分词的赏析。','春眠不觉晓'),[])


if __name__=='__main__':unittest.main()
