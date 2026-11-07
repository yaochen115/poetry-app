"""Offline regression tests, including all four previously failed real pages."""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

import site_translation_parser_v1_0_0 as old
import site_translation_parser_v1_0_1 as new


URL = "https://www.guwendao.net/shiwenv_abc123.aspx"
POEM = dict(id="fixture-001", title="示例", author="作者", content="甲乙，丙丁。")
PREVIEW = '''<div id="fanyi7" class="sons"><div class="contyishang">
<h2>译文及注释</h2><p>译文<br>完整译文。</p><p>注释<br>甲：第一条。<br>乙：第二
<a href="javascript:fanyiShow(7,'token','abc123')">展开阅读全文</a></div></div>'''
FULL = '''<div id="fanyiquan7" class="sons" style="display:none"><div class="contyishang">
<h2>译文及注释</h2><p><strong>译文</strong><br>完整译文。</p>
<p><strong>注释</strong><br>甲：第一条。<br>乙：第二条完整内容。</p>
<a href="javascript:fanyiClose(7)">收起</a></div></div>'''
HEADER = '''<html><head><link rel="canonical" href="URL"></head><body><main>
<article><h1>示例</h1><p class="source"><a href="/authorv_1.aspx">作者</a>〔唐代〕</p>
<div class="contson" id="contsonabc123">甲乙，丙丁。</div></article>'''.replace("URL", URL)
ANALYSIS = '''<div id="shangxiquan7" style="display:none"><div class="contyishang">
<h2>赏析</h2><strong>译文</strong><p>这是赏析里的引用，不能当译文。</p></div></div>'''
PAGE = HEADER + PREVIEW + FULL + ANALYSIS + "</main><footer>登录 译文</footer></body></html>"


class SiteParser101Tests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".site-parser-101-test-", dir=new.ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_four_real_pages_recover_complete_notes_without_changing_old_artifacts(self):
        folder = new.ROOT / "expansion/site-selected/known-v1.0.0"
        if not folder.exists():
            self.skipTest("Four-page project cache unavailable")
        frozen = [new.ROOT / "scripts/site_translation_parser_v1_0_0.py",
                  new.ROOT / "expansion/site-selected/parsed-known-v1.0.0.json"]
        before = {path: path.read_bytes() for path in frozen if path.exists()}
        poems = new.read_json(new.ROOT / "data/poems.json")["items"]
        legacy = old.parse_directory(folder, poems)
        self.assertEqual(legacy["counts"], dict(candidates=0, failures=4, skipped=0))
        report = new.parse_directory(folder, poems)
        self.assertEqual(report["counts"], dict(candidates=4, failures=0, skipped=0))
        expected = {"tang-156": (10, "班马："), "tang-160": (8, "萋萋："),
                    "tang-162": (17, "乡关："), "tang-165": (12, "万里：")}
        for candidate in report["candidates"]:
            with self.subTest(id=candidate["id"]):
                count, tail = expected[candidate["id"]]
                self.assertEqual(len(candidate["translation"].splitlines()), 4)
                self.assertEqual(len(candidate["notes"]), count)
                self.assertTrue(candidate["notes"][-1].startswith(tail))
                self.assertNotIn("收起", "\n".join(candidate["notes"]))
                self.assertNotIn("展开阅读全文", "\n".join(candidate["notes"]))
                detail = candidate["extractionDetails"][0]
                self.assertEqual(detail["mode"], "complete_fold_already_in_received_html")
                self.assertTrue(detail["prefixVerified"])
                self.assertIn("notesSha256", detail["discardedPreview"])
                self.assertFalse(detail["requiresNetwork"])
                self.assertFalse(candidate["literaryApproved"])
                self.assertEqual(candidate["parserVersion"], "1.0.1")
        self.assertEqual(before, {path: path.read_bytes() for path in before})

    def test_plain_labels_and_paired_full_preserve_lines_and_ignore_hidden_analysis(self):
        result = new.extract(PAGE.encode())
        self.assertEqual(result["translation"], "完整译文。")
        self.assertEqual(result["notes"], ["甲：第一条。", "乙：第二条完整内容。"])
        self.assertEqual(result["extractionDetails"][0]["fullId"], "fanyiquan7")
        plain_complete = HEADER + '''<div class="contyishang"><h2>译文及注释</h2>
<p>译文<br>纯文本标题译文。</p><p>注释<br>甲：注释。</p></div></main></body></html>'''
        self.assertEqual(new.extract(plain_complete.encode())["translation"], "纯文本标题译文。")

    def test_missing_full_and_access_gates_remain_failures(self):
        cases = [(PAGE.replace(FULL, ""), "requires_expansion"),
                 (PAGE.replace("第二条完整内容。", "请先登录后查看全部注释。"), "requires_login"),
                 (PAGE.replace('style="display:none"', 'style="display:none" aria-hidden="true"', 1), "requires_expansion"),
                 (PAGE.replace('href="javascript:fanyiClose(7)"', 'href="#"'), "cached_pair_mismatch")]
        for html, error in cases:
            with self.subTest(error=error), self.assertRaisesRegex(new.ParseFailure, error):
                new.extract(html.encode())

    def test_full_pair_identity_and_preview_prefix_must_agree(self):
        for html in (PAGE.replace("fanyiShow(7,'token','abc123')", "fanyiShow(7,'token','other')"),
                     PAGE.replace('id="fanyiquan7"', 'id="fanyiquan8"'),
                     PAGE.replace("第二条完整内容。", "完全不同的解释。"),
                     PAGE.replace('href="javascript:fanyiClose(7)"', 'href="javascript:fanyiClose(8)"')):
            with self.subTest(html=html[-120:]), self.assertRaises(new.ParseFailure):
                new.extract(html.encode())

    def test_genuinely_different_translations_and_missing_fields_do_not_pass(self):
        second = '''<div class="contyishang"><h2>译文</h2><p>真正不同的第二种译文。</p></div>'''
        conflict = PAGE.replace(ANALYSIS, second + ANALYSIS)
        with self.assertRaisesRegex(new.ParseFailure, "conflicting translation"):
            new.extract(conflict.encode())
        for html in (HEADER + ANALYSIS + "</main></body></html>",
                     PAGE.replace("完整译文。", ""),
                     PAGE.replace("<strong>注释</strong>", "<strong>其他</strong>")):
            with self.assertRaises(new.ParseFailure):
                new.extract(html.encode())

    def test_cli_cache_integrity_strict_identity_alias_and_no_overwrite(self):
        html_path = self.root / "work--sample.html"
        html_path.write_bytes(PAGE.encode())
        metadata = dict(url=URL, status=200, sha256=hashlib.sha256(PAGE.encode()).hexdigest())
        meta_path = self.root / "work--fetch.json"
        meta_path.write_text(json.dumps(metadata), encoding="utf-8")
        poems_path = self.root / "poems.json"
        poems_path.write_text(json.dumps({"items": [POEM]}, ensure_ascii=False), encoding="utf-8")
        output = self.root / "parsed-v1.0.1.json"
        args = [str(self.root), "--poems", str(poems_path), "--output", str(output)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(new.main(args), 0)
        before = output.read_bytes()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(new.main(args), 1)
        self.assertEqual(output.read_bytes(), before)
        metadata["sha256"] = "0" * 64
        meta_path.write_text(json.dumps(metadata), encoding="utf-8")
        report = new.parse_directory(self.root, [POEM])
        self.assertEqual(report["counts"]["candidates"], 0)
        self.assertEqual(report["counts"]["failures"], 1)
        self.assertEqual(new.title_match("赋得古原草送别", dict(POEM, title="草", author="白居易")), "registered_alias")
        self.assertIsNone(new.title_match("赋得古原草送别", dict(POEM, title="草", author="另一作者")))
        for change in ({"content": "另一个正文"}, {"title": "另一个题目"}, {"author": "另一个作者"}):
            with self.subTest(change=change), self.assertRaises(new.ParseFailure):
                new.parse_file(html_path, new.poem_index([dict(POEM, **change)]))


if __name__ == "__main__":
    unittest.main()
