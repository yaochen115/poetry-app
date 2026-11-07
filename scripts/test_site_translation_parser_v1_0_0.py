"""python -B -m unittest discover -s scripts -p test_site_translation_parser_v1_0_0.py -v"""

from contextlib import redirect_stderr, redirect_stdout
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest

from site_translation_parser_v1_0_0 import (
    ROOT, ParseFailure, extract, main, normalize, parse_directory, parse_file, poem_index,
)


URL = "https://www.guwendao.net/shiwenv_abc123.aspx"
POEM = dict(id="test-001", title="示例", subtitle="", author="作者", content="甲乙，丙丁。\n戊己。")
HTML = '''<!doctype html><html><head><link rel="canonical" href="URL"></head><body>
<nav><h1>导航标题</h1><p class="source">导航作者</p>译文：导航不是译文</nav>
<main><article><h1><span>示例</span></h1>
<p class="source"><a href="/authorv_author.aspx"><img alt="作者头像">作者</a>
<a href="/shiwens/default.aspx">〔唐代〕</a></p>
<div class="contson extra" id="contsonabc123">甲乙，&#x4E19;丁。<br/>戊己。
<script>脚本不属于正文</script><span hidden>隐藏正文</span></div></article>
<div class="sons"><div class="contyishang"><h2><span>译文及注释</span></h2>
<p><strong>译文</strong><br/>这是第一句的译文。<br/>这是第二句的译文。</p>
<p><strong>注释</strong><br/>甲：甲的解释。<br/>乙：<a href="/book">乙</a>的解释。</p>
<div class="cankao">参考文献，不是注释正文</div></div></div>
<div class="contyishang"><h2>赏析</h2><p>赏析内容，绝不可混入译注。</p></div>
<div class="recommend"><h1>推荐标题</h1><p class="source">推荐作者</p>
<div class="contson" id="contsonother">别篇正文</div>
<div class="contyishang"><h2>译文</h2><p>推荐的译文</p></div></div></main>
<footer>译文 注释 赏析 下载APP</footer></body></html>'''.replace("URL", URL)


class SiteParserTests(unittest.TestCase):
    def setUp(self):
        # Keep temporary artifacts inside this project; cleanup removes only this fixture tree.
        self.temp = tempfile.TemporaryDirectory(prefix=".site-parser-test-", dir=ROOT)
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.index = poem_index([POEM])

    def fixture(self, html=HTML, metadata_changes=None):
        raw = html.encode("utf-8")
        sha = hashlib.sha256(raw).hexdigest()
        path = self.root / ("sample--" + sha + ".html")
        path.write_bytes(raw)
        metadata = dict(url=URL, finalUrl=URL, status=200, sha256=sha, bytes=len(raw),
                        acquiredAt="2026-11-04T00:00:00Z", reuseStatus="reference_only_test_marker")
        metadata.update(metadata_changes or {})
        sidecar = self.root / "sample--fetch-record.json"
        sidecar.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")
        return path, metadata

    def test_exact_dom_extraction_excludes_navigation_analysis_and_recommendations(self):
        path, metadata = self.fixture()
        result = parse_file(path, self.index, metadata)
        self.assertEqual(result["title"], "示例")
        self.assertEqual(result["author"], "作者")
        self.assertEqual(result["sourceText"], "作者\n〔唐代〕")
        self.assertEqual(result["content"], POEM["content"])
        self.assertEqual(result["translation"], "这是第一句的译文。\n这是第二句的译文。")
        self.assertEqual(result["notes"], ["甲：甲的解释。", "乙：乙的解释。"])
        self.assertFalse(result["literaryApproved"])
        self.assertEqual(result["stage"], "reference_candidate")
        self.assertEqual(result["provenance"]["htmlSha256"], metadata["sha256"])
        self.assertEqual(result["provenance"]["reuseStatus"], "reference_only_test_marker")
        self.assertEqual(result["url"], URL)

    def test_whole_body_identity_and_author_title_are_required(self):
        path, metadata = self.fixture()
        self.assertEqual(normalize("甲乙，丙丁。\n戊己。"), normalize("甲乙 丙丁 戊己"))
        self.assertNotEqual(normalize("甲乙（一作甲丙）"), normalize("甲乙"))
        for change in ({"content": "甲乙，丙丁。"}, {"content": "甲乙，丙丁。戊庚。"},
                       {"author": "另一作者"}, {"title": "另一个题目"}):
            with self.subTest(change=change), self.assertRaises(ParseFailure):
                parse_file(path, poem_index([dict(POEM, **change)]), metadata)
        duplicate = dict(POEM, id="test-002")
        with self.assertRaisesRegex(ParseFailure, "ambiguous"):
            parse_file(path, poem_index([POEM, duplicate]), metadata)

    def test_missing_truncated_malformed_and_borrowed_translation_are_failures(self):
        variants = {
            "missing": HTML.replace("<strong>译文</strong>", "<strong>译意</strong>"),
            "heading_only": HTML.replace("这是第一句的译文。<br/>这是第二句的译文。", ""),
            "notes_missing": HTML.replace("<strong>注释</strong>", "<strong>其他</strong>"),
            "truncated": HTML.replace("这是第二句的译文。", '这是第二句<a href="#">展开阅读全文</a>'),
            "unclosed_body": HTML.replace("<br/>戊己。", "<br/>戊己。").replace(
                '<span hidden>隐藏正文</span></div></article>', '<span hidden>隐藏正文</span></article>'),
        }
        for label, html in variants.items():
            with self.subTest(label=label), self.assertRaises(ParseFailure):
                extract(html.encode("utf-8"))
        # A second visible work must never supply the first work's absent translation.
        borrowed = HTML.replace('<div class="sons"><div class="contyishang">',
                                '<h1>另一作品</h1><div class="sons"><div class="contyishang">')
        with self.assertRaises(ParseFailure):
            extract(borrowed.encode("utf-8"))

    def test_cache_integrity_and_raw_html_url_handling(self):
        path, metadata = self.fixture()
        for change in ({"sha256": "0" * 64}, {"bytes": 1}, {"status": 403}, {"error": "fetch failed"},
                       {"finalUrl": URL.replace("abc123", "different")}):
            with self.subTest(change=change), self.assertRaises(ParseFailure):
                parse_file(path, self.index, dict(metadata, **change))
        self.assertEqual(parse_file(path, self.index)["id"], POEM["id"])
        raw = HTML.replace('<link rel="canonical" href="' + URL + '">', "")
        path.write_text(raw, encoding="utf-8")
        with self.assertRaisesRegex(ParseFailure, "URL"):
            parse_file(path, self.index)
        self.assertEqual(parse_file(path, self.index, url=URL)["id"], POEM["id"])
        path.write_bytes(b"\xff\xfe")
        with self.assertRaises(UnicodeError):
            parse_file(path, self.index, url=URL)

    def test_directory_cli_reports_failures_and_never_overwrites(self):
        self.fixture()
        poems_path = self.root / "poems.json"
        poems_path.write_text(json.dumps({"items": [POEM]}, ensure_ascii=False), encoding="utf-8")
        baseline = poems_path.read_bytes()
        output = self.root / "parsed.json"
        args = [str(self.root), "--poems", str(poems_path), "--output", str(output)]
        with redirect_stdout(io.StringIO()):
            self.assertEqual(main(args), 0)
        report = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(report["counts"], {"candidates": 1, "failures": 0, "skipped": 0})
        before = output.read_bytes()
        with redirect_stderr(io.StringIO()):
            self.assertEqual(main(args), 1)
        self.assertEqual(output.read_bytes(), before)
        self.assertEqual(poems_path.read_bytes(), baseline)
        # A bad cache record is a failure even when HTML itself would parse.
        sidecar = self.root / "sample--fetch-record.json"
        metadata = json.loads(sidecar.read_text(encoding="utf-8"))
        metadata["sha256"] = "0" * 64
        sidecar.write_text(json.dumps(metadata), encoding="utf-8")
        with redirect_stdout(io.StringIO()) as stream:
            self.assertEqual(main([str(self.root), "--poems", str(poems_path)]), 1)
        failed = json.loads(stream.getvalue())
        self.assertEqual(failed["candidates"], [])
        self.assertEqual(failed["counts"]["failures"], 1)

    def test_real_cached_pages_and_nonwork_skip(self):
        folder = ROOT / "expansion/site-samples/v1.0.0"
        if not folder.exists():
            self.skipTest("Project's real site cache is unavailable")
        poems = [dict(id="cache-1", title="行宫", author="元稹", content="寥落古行宫，宫花寂寞红。白头宫女在，闲坐说玄宗。"),
                 dict(id="cache-2", title="宴词", author="王之涣", content="长堤春水绿悠悠，畎入漳河一道流。莫听声声催去棹，桃溪浅处不胜舟。")]
        report = parse_directory(folder, poems)
        self.assertEqual(report["failures"], [])
        self.assertEqual(report["counts"], {"candidates": 2, "failures": 0, "skipped": 1})
        by_title = {c["title"]: c for c in report["candidates"]}
        self.assertEqual(len(by_title["行宫"]["notes"]), 6)
        self.assertEqual(len(by_title["宴词"]["notes"]), 7)
        for candidate in by_title.values():
            self.assertEqual(len(candidate["translation"].splitlines()), 2)
            self.assertNotIn("创作背景", candidate["translation"])
            self.assertNotIn("赏析", "\n".join(candidate["notes"]))
            self.assertIn("metadataSha256", candidate["provenance"])


if __name__ == "__main__":
    unittest.main()
