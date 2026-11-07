import argparse
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import convert_downloaded_materials_v1_0_0 as converter


class ConversionTests(unittest.TestCase):
    def test_clean_html_without_script(self):
        self.assertEqual(converter.text('<p>第一句</p><script>坏内容</script><p>第二句<br>第三句</p>'),
                         '第一句\n第二句\n第三句')

    def test_notes_are_not_translation(self):
        self.assertIn('annotations_in_translation', converter.flags_for(
            dict(translation='注释：春天', notes=[{}]*3, tags=['山水'])))

    def test_identity_normalization(self):
        self.assertEqual(converter.normal(['風雨，', '山川。']), converter.normal('风雨山川'))
        self.assertNotEqual(converter.normal('李白'), converter.normal('李贺'))

    def test_explicit_review_required_and_tamper_rejected(self):
        with tempfile.TemporaryDirectory(dir=converter.ROOT/'expansion/working') as folder:
            base = Path(folder); source = base/'source.json'; source.write_text('[]', encoding='utf-8')
            item = dict(patch=dict(id='tang-001', tags=['山水'], translation='这是春天美丽的山川。',
                notes=[dict(term=c, meaning='解释') for c in '山川春']), inputHash='original',
                source=dict(file=str(source), sha256=converter.hashlib.sha256(source.read_bytes()).hexdigest()), flags=[])
            item['candidateHash'] = converter.digest(item)
            candidate = base/'candidates.json'; review_file = base/'reviews.json'; target = base/'batch.json'
            candidate.write_text(json.dumps(dict(candidates=[item])), encoding='utf-8')
            reviews = dict(poems=[dict(id='tang-001', decision='pending')])
            review_file.write_text(json.dumps(reviews), encoding='utf-8')
            args = argparse.Namespace(candidates=candidate, reviews=review_file, dictionary=None,
                                      output=target, data_version='1.2.9', dictionary_version='1.1.20')
            class FakePipeline:
                pending = {'tang-001'}
                poems = {'tang-001': {'id':'tang-001', 'category':'唐诗', 'content': '山川春'}}
                tags = {'唐诗': ['山水']}
                dictionary = {c:{} for c in '山川春'}
                def input_hash(self, poem): return 'original'
            with patch.object(converter, 'Pipeline', FakePipeline):
                with self.assertRaisesRegex(ValueError, 'No reviewed'): converter.assemble(args)
                self.assertFalse(target.exists())
                reviews['poems'][0].update(decision='approved', sourceUse='approved', reviewer='test',
                                          explanation='fixture review', candidateHash=item['candidateHash'])
                review_file.write_text(json.dumps(reviews), encoding='utf-8')
                converter.assemble(args)
                self.assertEqual(json.loads(target.read_text(encoding='utf-8'))['patches'], [item['patch']])
                with self.assertRaises(ValueError): converter.assemble(args)  # no overwriting
                item['patch']['translation'] = '篡改'
                candidate.write_text(json.dumps(dict(candidates=[item])), encoding='utf-8')
                with self.assertRaisesRegex(ValueError, 'Changed candidate'): converter.assemble(args)

    def test_prepare_matches_author_and_handles_flat_dictionary(self):
        with tempfile.TemporaryDirectory(dir=converter.ROOT/'expansion/working') as folder:
            base = Path(folder); source = base/'source.json'
            source.write_text(json.dumps([
                dict(title='春',writer='李白',content='山川春',translation='山川迎来了美好的春天。',
                     remark='山：高山。\n川：河川。\n春：春天。',type=['山水']),
                dict(title='春',writer='李贺',content='山川春',translation='这是同文异作者。')]),encoding='utf-8')
            class FakePipeline:
                pending = {'tang-001'}
                poems = {'tang-001':dict(id='tang-001',title='春',author='李白',content='山川春',category='唐诗')}
                dictionary = {'山':{}}
                tags = {'唐诗':['山水']}
                def input_hash(self, poem): return 'original'
                def ordered(self, ids): return sorted(ids)
            with patch.object(converter, 'Pipeline', FakePipeline):
                converter.prepare(argparse.Namespace(source=[source],output=base/'out'))
            result=json.loads((base/'out/candidates-v1.0.0.json').read_text(encoding='utf-8'))
            self.assertEqual(result['matched'],1)
            self.assertEqual(result['missingCharacters'],['川','春'])
            self.assertEqual(result['candidates'][0]['alternativeCount'],0)


if __name__ == '__main__': unittest.main()
