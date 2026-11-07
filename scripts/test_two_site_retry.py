from pathlib import Path
from types import SimpleNamespace
import unittest
import retry_two_translation_sites_v1_0_0 as retry

class TwoSiteTests(unittest.TestCase):
    def test_reject_login_and_foreign_redirects(self):
        for url in ('https://www.guwendao.net/user/login.aspx','https://other.test/shiwenv_123456789abc.aspx'):
            with self.assertRaises(retry.SourceStopped):retry.validate_url(url)
        retry.validate_url('https://www.guwendao.net/shiwenv_123456789abc.aspx')
        retry.validate_url('https://www.gushiwenku.cn/shiwen/123abc/')

    def test_translation_only_can_be_staged_but_wrong_body_cannot(self):
        poem=dict(id='song-001',title='原题',author='作者',content='山川风雨',category='宋词',tags=[])
        pipe=SimpleNamespace(pending={'song-001':poem},poems={'song-001':poem},dictionary={},tags={'宋词':[]})
        page=dict(title='别名',author='作者',content='山川，风雨。',translation='山川之中正在落着风雨。',notes=[])
        source=dict(url='https://www.guwendao.net/shiwenv_123456789abc.aspx',blob='sample.html',sha256='x')
        entry,reason=retry.candidate(page,source,pipe,retry.OUT/'test')
        self.assertIsNotNone(entry);self.assertIsNone(reason);self.assertIn('notes',entry['pending'])
        page['content']='其他作品';self.assertIsNone(retry.candidate(page,source,pipe,retry.OUT/'test')[0])

if __name__=='__main__':unittest.main()
