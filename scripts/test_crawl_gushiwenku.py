import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest

import crawl_gushiwenku_v1_0_0 as crawler


class CrawlerTests(unittest.TestCase):
    def test_url_boundaries(self):
        self.assertEqual(crawler.safe_url(crawler.BASE+'/shiwen/064809f/'),crawler.BASE+'/shiwen/064809f/')
        for url in ('http://www.gushiwenku.cn/shiwen/aaa/',
                    'https://evil.test/shiwen/aaa/',crawler.BASE+'/template/api/',
                    crawler.BASE+'/shiwen/aaa/?login=true',crawler.BASE+'/shiwen/aaa/#x'):
            with self.assertRaises(ValueError):crawler.safe_url(url)

    def test_discovery_is_only_title_hint(self):
        html='<a href="/shiwen/abc/"><h3 class="works-name">《春晓》</h3><span>李白</span></a><a href="https://evil.test/shiwen/def/">春晓</a>'
        self.assertEqual(crawler.discover(html,crawler.BASE+'/xuanji/test/',{'x':{'title':'春晓','author':'李白'}}),
                         [crawler.BASE+'/shiwen/abc/'])

    def test_ci_title_and_subtitle_discovery(self):
        html='<a href="/shiwen/abc/"><h3 class="works-name">《浣溪沙·绣面芙蓉一笑开》</h3><span class="works-author">李清照</span></a>'
        poem=dict(title='浣溪沙',subtitle='闺情',content='绣面芙蓉一笑开，斜飞宝鸭衬香腮。',author='李清照')
        self.assertIn(crawler.normal('浣溪沙·绣面芙蓉一笑开'),crawler.title_keys(poem))
        self.assertEqual(crawler.discover(html,crawler.BASE+'/xuanji/test/',{'x':poem}),[crawler.BASE+'/shiwen/abc/'])

    def fixture(self):
        return (crawler.ROOT/'expansion/gushiwenku-samples-v1.0.0/064809f.html').read_text(encoding='utf-8')

    def fake_pipe(self):
        row=crawler.parse(self.fixture())
        poem=dict(id='tang-577',content=row['content'],author=row['writer'],title=row['title'],category='唐诗',tags=[])
        return SimpleNamespace(pending={poem['id']:poem},tags={'唐诗':['山水']},
            dictionary={c:{} for c in row['content']},input_hash=lambda p:'hash')

    def test_conversion_uses_source_tags_and_filters_title_notes(self):
        row,patch,checks=crawler.convert(self.fixture(),self.fake_pipe())
        self.assertEqual(checks['reasons'],[])
        self.assertEqual(patch['tags'],['山水'])
        self.assertTrue(all(n['term'] in row['content'] for n in patch['notes']))
        self.assertNotIn('业师',[n['term'] for n in patch['notes']])

    def test_wrong_author_and_missing_dictionary_hold(self):
        pipe=self.fake_pipe();pipe.pending['tang-577']['author']='李白'
        self.assertIsNone(crawler.convert(self.fixture(),pipe)[1])
        pipe=self.fake_pipe();pipe.dictionary={}
        self.assertIn('missing_dictionary',crawler.convert(self.fixture(),pipe)[2]['reasons'])

    def test_explicit_character_annotation_can_fill_one_missing_character(self):
        pipe=self.fake_pipe();del pipe.dictionary['倏']
        checks=crawler.convert(self.fixture(),pipe)[2]
        self.assertEqual(checks['reasons'],[])
        self.assertEqual(checks['dictionaryAdditions']['倏'],dict(meanings=[],ancient=['一下子。']))

    def test_cache_tamper_rejected_offline(self):
        with tempfile.TemporaryDirectory(dir=crawler.ROOT/'expansion/working') as folder:
            work=Path(folder);(work/'cache').mkdir()
            url=crawler.BASE+'/shiwen/abc/';key=crawler.hashlib.sha256(url.encode()).hexdigest()
            name='0'*64+'.html'
            (work/'cache'/name).write_text('changed',encoding='utf-8')
            (work/'cache'/(key+'.json')).write_text(json.dumps(dict(url=url,blob=name,sha256='wrong')),encoding='utf-8')
            with self.assertRaisesRegex(ValueError,'Cache integrity'):
                crawler.Client(work,offline=True).get(url)

    def test_page_without_translation_is_held(self):
        html=crawler.re.sub(r'<section class="card" aria-labelledby="poem-translation">.*?</section>',
                            '',self.fixture(),count=1,flags=crawler.re.S)
        row,patch,checks=crawler.convert(html,self.fake_pipe())
        self.assertEqual(row['translation'],'')
        self.assertTrue(checks['reasons'])
        self.assertEqual(patch['notes'],[])


if __name__=='__main__':unittest.main()
