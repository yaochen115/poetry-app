"""Run: python -m unittest discover -s scripts -p test_enrichment_pipeline.py -v"""

from contextlib import redirect_stderr, redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from enrichment_pipeline import Pipeline, digest, main, normalize_definition, read, write_once


class PipelineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.poems = [self.poem("tang-002"), self.poem("tang-010"), self.poem("tang-1000")]
        self.dictionary = {"月": {"meanings": ["月亮。"], "ancient": []}}
        self.save_data()

    @staticmethod
    def poem(pid, content="月月月月月", category="唐诗"):
        return dict(id=pid, category=category, title="测试作品", subtitle="", author="作者",
                    dynasty="唐", content=content, excerptOf=None, excerptNote="",
                    editorialStatus="original_only", pending=["translation", "notes", "themeTags", "dictionary"],
                    translation="", notes=[], tags=[])

    @staticmethod
    def patch(pid, translation="月光照着寂静的庭院，诗人思念远方的亲人。"):
        return dict(id=pid, tags=["思乡"], translation=translation,
                    notes=[dict(term=str(n), meaning="用于测试的具体释义。") for n in range(3)])

    def save(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
        return path

    def save_data(self, disabled=()):
        self.save("data/poems.json", dict(dataVersion="1.0.0", items=self.poems,
                                         disabledEntries=[dict(id=pid, reason='Test quarantine',
                                            replacementId=next(p['id'] for p in self.poems if p['id'] not in disabled))
                                            for pid in disabled]))
        self.save("data/dict.json", dict(dataVersion="1.0.0", chars=self.dictionary, words={}))
        self.save("data/categories.json", dict(categories=[dict(key=cat, tags=["思乡", "山水"])
                  for cat in ("唐诗", "宋词", "元曲", "古文")]))

    def legacy(self, number=1, poems=None, additions=None, patches=None):
        poems = poems if poems is not None else self.poems
        sources = []
        for poem in poems:
            source = {k: poem[k] for k in ("id", "title", "subtitle", "author", "dynasty",
                                           "content", "excerptOf", "excerptNote")}
            source["missingChars"] = sorted(set(poem["content"]) - self.dictionary.keys())
            sources.append(source)
        self.save("expansion/working/chunks/in-%03d.json" % number,
                  dict(category=poems[0]["category"], tagEnum=["思乡", "山水"], poems=sources))
        return self.save("expansion/working/chunks/out-%03d.json" % number,
                         dict(patches=patches if patches is not None else [self.patch(p["id"]) for p in poems],
                              dictionaryAdditions=additions if additions is not None else {}))

    def result(self, pid=None, approved=False):
        pipeline = Pipeline(self.root)
        pid = pid or self.poems[0]["id"]
        path = pipeline.result_path(pipeline.poems[pid])
        patch = self.patch(pid)
        self.save(path.relative_to(self.root), patch)
        if approved:
            self.review(pid, patch)
        return path

    def review(self, pid, patch, decision="approved"):
        pipeline = Pipeline(self.root)
        input_hash = pipeline.input_hash(pipeline.poems[pid])
        return self.save("expansion/working/v2/reviews/" + pid + "--" + input_hash + ".json",
                         dict(decision=decision, reviewer="文学审核员", inputHash=input_hash,
                              resultHash=digest(patch)))

    def canonical(self, ch, definition):
        return self.save("expansion/working/v2/reviews/dictionary/" + ch + ".json",
                         dict(decision="approved", reviewer="字典审核员",
                              definitionHash=digest(normalize_definition(definition))))

    def assemble(self, **kwargs):
        return Pipeline(self.root).assemble("011", "1.1.7", "1.1.5", **kwargs)

    def tasks(self):
        return [read(p) for p in sorted((self.root / "expansion/working/v2/tasks").glob("poems-*.json"))]

    def test_prepare_resume_preserves_all_80_old_inputs_and_outputs(self):
        for number in range(1, 81):
            self.save("expansion/working/chunks/in-%03d.json" % number, {"untouched": number})
        self.legacy(1, poems=self.poems[:1])
        chunks = self.root / "expansion/working/chunks"
        before = {p.name: p.read_bytes() for p in chunks.iterdir()}
        pipeline = Pipeline(self.root)
        first = pipeline.prepare(max_items=1)
        self.assertEqual(first["queuedPoems"], 2)
        self.assertEqual(first["recoveredLegacy"], 1)
        self.assertTrue(pipeline.result_path(self.poems[0]).exists())
        tasks_before = {p.name: p.read_bytes() for p in (pipeline.work / "tasks").glob("*.json")}
        self.result("tang-010")  # agent finishes one task before prepare is resumed
        second = Pipeline(self.root).prepare(max_items=1)
        self.assertEqual(second["createdTasks"], [])
        self.assertEqual(tasks_before, {p.name: p.read_bytes() for p in (pipeline.work / "tasks").glob("*.json")})
        self.assertEqual(before, {p.name: p.read_bytes() for p in chunks.iterdir()})

    def test_broken_block_salvages_good_poems_without_excluding_them(self):
        self.poems[0]["content"] = "月魑月"
        self.save_data()
        self.legacy(additions={})  # dictionary is incomplete, poem patches are sound
        pipeline = Pipeline(self.root)
        result = pipeline.prepare()
        self.assertEqual(result["queuedPoems"], 3)
        self.assertEqual(result["recoveredLegacy"], 0)
        self.assertTrue(all(pipeline.result_path(p).exists() for p in self.poems))
        report = Pipeline(self.root).inspect()[0]
        self.assertEqual(report["usableDrafts"], 3)
        self.assertEqual(report["approvedDrafts"], 0)
        self.assertEqual(report["awaitingReview"], 3)

    def test_broken_patch_does_not_discard_other_good_poems(self):
        patches = [self.patch(p["id"]) for p in self.poems]
        patches[1]["notes"] = []
        self.legacy(patches=patches)
        result = Pipeline(self.root).prepare()
        self.assertEqual(result["queuedPoems"], 3)
        self.assertEqual(len(list((Pipeline(self.root).work / "results").glob("*.json"))), 2)
        self.assertEqual(Pipeline(self.root).inspect()[0]["badDrafts"], 1)

    def test_budget_and_category_boundaries_and_numeric_order(self):
        self.poems = [self.poem("tang-1000"), self.poem("tang-010"), self.poem("tang-999"),
                      self.poem("song-001", category="宋词"), self.poem("guwen-001", "月" * 60, "古文")]
        self.save_data()
        Pipeline(self.root).prepare(max_items=20, max_chars=20, max_output=1250)
        tasks = self.tasks()
        tang = [t for t in tasks if t["category"] == "唐诗"]
        ordered = sorted(tang, key=lambda t: int(t["poems"][0]["id"].split("-")[1]))
        self.assertEqual([[p["id"] for p in t["poems"]] for t in ordered],
                         [["tang-010", "tang-999"], ["tang-1000"]])
        self.assertTrue(all(len({p["category"] for p in t["poems"]}) == 1 for t in tasks))
        self.assertTrue(next(t for t in tasks if t["category"] == "古文")["oversized"])
        self.assertTrue(all(t["estimatedOutput"] <= 1250 for t in tasks if not t["oversized"]))

    def test_content_length_and_item_limits_are_independent(self):
        Pipeline(self.root).prepare(max_items=20, max_chars=8, max_output=99999)
        self.assertEqual(len(self.tasks()), 3)
        self.assertTrue(all(len(t["poems"]) == 1 for t in self.tasks()))

    def test_changed_source_invalidates_result_review_and_legacy(self):
        self.legacy(poems=self.poems[:1])
        path = self.result(approved=True)
        old_bytes = path.read_bytes()
        self.poems[0]["content"] += "月"
        self.save_data()
        pipeline = Pipeline(self.root)
        report = pipeline.inspect()[0]
        self.assertEqual(report["usableDrafts"], 0)
        self.assertEqual(len(report["staleResults"]), 1)
        self.assertEqual(report["recoverableLegacyIds"], [])
        pipeline.prepare()
        self.assertEqual(path.read_bytes(), old_bytes)
        self.assertNotEqual(path, pipeline.result_path(self.poems[0]))

    def test_unrelated_poem_change_does_not_invalidate_result(self):
        self.result(approved=True)
        self.poems[1]["content"] += "月"
        self.save_data()
        self.assertEqual(Pipeline(self.root).inspect()[0]["approvedDrafts"], 1)

    def test_category_tag_change_invalidates_hash(self):
        self.result()
        path = self.root / "data/categories.json"
        data = read(path)
        data["categories"][0]["tags"].append("咏物")
        self.save("data/categories.json", data)
        self.assertEqual(len(Pipeline(self.root).inspect()[0]["staleResults"]), 1)

    def test_existing_results_never_overwritten_even_by_legacy_recovery(self):
        self.legacy(poems=self.poems[:1])
        path = self.result()
        alternative = self.patch(self.poems[0]["id"], "这份不同的译文已经由生成者写入，恢复程序必须保留。")
        self.save(path.relative_to(self.root), alternative)
        before = path.read_bytes()
        Pipeline(self.root).prepare()
        self.assertEqual(path.read_bytes(), before)

    def test_same_json_write_noop_different_json_is_refused(self):
        path = self.root / "one.json"
        self.assertTrue(write_once(path, {"x": 1}))
        self.assertFalse(write_once(path, {"x": 1}))
        with self.assertRaisesRegex(ValueError, "overwrite"):
            write_once(path, {"x": 2})
        self.assertEqual(read(path), {"x": 1})

    def test_failed_atomic_publish_leaves_no_partial_task(self):
        path = self.root / "task.json"
        with patch("enrichment_pipeline.os.link", side_effect=OSError("simulated interruption")):
            with self.assertRaises(OSError):
                write_once(path, {"poems": [self.poems[0]]})
        self.assertFalse(path.exists())
        self.assertEqual(list(self.root.glob(".pipeline-*.tmp")), [])
        self.assertTrue(write_once(path, {"poems": [self.poems[0]]}))

    def test_malformed_legacy_list_element_does_not_discard_good_drafts_or_definitions(self):
        self.poems[0]["content"] = "魑魑"
        self.save_data()
        definition = dict(meanings=["山鬼。"], ancient=[])
        path = self.legacy(additions={"魑": definition},
                           patches=[self.patch("tang-002"), None, self.patch("tang-1000")])
        result = Pipeline(self.root).prepare()
        self.assertEqual(result["recoveredLegacy"], 0)
        self.assertEqual(result["queuedPoems"], 3)
        report, drafts, dictionary, _ = Pipeline(self.root).inspect()
        self.assertEqual(set(drafts), {"tang-002", "tang-1000"})
        self.assertEqual(dictionary["魑"]["candidates"][0]["definition"], definition)
        self.assertTrue(any(i["source"].endswith(path.name) for i in report["issues"]))

    def test_duplicate_legacy_ids_block_whole_recovery_but_preserve_unrelated_poem(self):
        self.legacy(patches=[self.patch("tang-002"), self.patch("tang-002"), self.patch("tang-010")])
        report, drafts, _, _ = Pipeline(self.root).inspect()
        self.assertEqual(report["recoverableLegacyCount"], 0)
        self.assertEqual(set(drafts), {"tang-010"})
        self.assertEqual(report["badDrafts"], 1)

    def test_new_source_creates_new_assignment_without_overwriting_old_task(self):
        pipeline = Pipeline(self.root)
        pipeline.prepare(max_items=1)
        old = {p.name: p.read_bytes() for p in (pipeline.work / "tasks").glob("poems-*.json")}
        self.poems[0]["content"] += "月"
        self.save_data()
        result = Pipeline(self.root).prepare(max_items=1)
        self.assertEqual(len(result["createdTasks"]), 1)
        self.assertTrue(all((pipeline.work / "tasks" / name).read_bytes() == data for name, data in old.items()))
        self.assertEqual(len(self.tasks()), 4)

    def test_cli_prepare_status_assemble_and_error_paths(self):
        prefix = ["--root", str(self.root)]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(prefix + ["prepare", "--max-items", "1"]), 0)
        self.assertEqual(json.loads(output.getvalue())["queuedPoems"], 3)
        before = {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()}
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(prefix + ["status"]), 0)
        self.assertEqual(json.loads(output.getvalue())["formalPending"], 3)
        self.assertEqual(before, {str(p.relative_to(self.root)): p.read_bytes() for p in self.root.rglob("*") if p.is_file()})
        self.result(approved=True)
        args = prefix + ["assemble", "011", "--data-version", "1.1.7", "--dictionary-version", "1.1.5"]
        with redirect_stdout(io.StringIO()) as output:
            self.assertEqual(main(args), 0)
        self.assertEqual(json.loads(output.getvalue())["patches"], 1)
        with redirect_stderr(io.StringIO()) as error:
            self.assertEqual(main(args), 1)
        self.assertIn("overwrite", error.getvalue())

    def test_assemble_requires_literary_review_and_never_modifies_production(self):
        pid = self.poems[0]["id"]
        self.result()
        before = {p.name: p.read_bytes() for p in (self.root / "data").glob("*.json")}
        with self.assertRaises(ValueError):
            self.assemble(ids=[pid])
        self.review(pid, self.patch(pid))
        result = self.assemble(ids=[pid])
        batch = read(self.root / result["batch"])
        self.assertEqual(set(batch["patches"][0]), {"id", "tags", "translation", "notes"})
        self.assertTrue(batch["review"]["literaryApproved"])
        self.assertEqual(before, {p.name: p.read_bytes() for p in (self.root / "data").glob("*.json")})
        with self.assertRaisesRegex(ValueError, "overwrite"):
            self.assemble(ids=[pid])

    def test_changed_result_invalidates_approval(self):
        path = self.result(approved=True)
        patch = read(path)
        patch["translation"] += "这是一处新增的译文。"
        self.save(path.relative_to(self.root), patch)
        report = Pipeline(self.root).inspect()[0]
        self.assertEqual(report["approvedDrafts"], 0)
        self.assertEqual(report["awaitingReview"], 1)
        with self.assertRaises(ValueError):
            self.assemble(ids=[patch["id"]])

    def test_status_partitions_formal_approved_pending_rejected_and_bad(self):
        self.poems += [self.poem("tang-003"), self.poem("tang-004"), self.poem("tang-005")]
        self.poems[-1].update(self.patch("tang-005"), editorialStatus="complete")
        self.save_data(disabled=["tang-004"])
        self.result("tang-002", approved=True)
        self.result("tang-010")
        path = self.result("tang-1000")
        self.save(path.relative_to(self.root), {"id": "tang-1000"})
        self.result("tang-003")
        self.review("tang-003", self.patch("tang-003"), decision="rejected")
        report = Pipeline(self.root).inspect()[0]
        self.assertEqual([report[k] for k in ("formalComplete", "formalPending", "usableDrafts",
                         "approvedDrafts", "awaitingReview", "badDrafts", "missingDrafts", "disabled")],
                         [1, 4, 2, 1, 1, 2, 0, 1])

    def test_dictionary_global_queue_has_one_task_per_missing_character(self):
        self.poems[0]["content"] = "月魑魑"
        self.poems[1]["content"] = "魑魅"
        self.save_data()
        result = Pipeline(self.root).prepare()
        queue = read(self.root / result["dictionaryQueue"])
        self.assertEqual([x["char"] for x in queue["items"]], ["魅", "魑"])
        task_dir = Pipeline(self.root).work / "tasks/dictionary"
        self.assertEqual(len(list(task_dir.glob("*.json"))), 2)
        Pipeline(self.root).prepare()
        self.assertEqual(len(list(task_dir.glob("*.json"))), 2)
        self.assertEqual(len(next(x for x in queue["items"] if x["char"] == "魑")["contextIds"]), 2)

    def test_selection_profile_excludes_archived_originals_from_pending(self):
        document=read(self.root/'data/poems.json')
        document['selectionProfile']={'ids':['tang-002']}
        self.save('data/poems.json',document)
        pipeline=Pipeline(self.root)
        self.assertEqual(set(pipeline.pending),{'tang-002'})
        self.assertEqual(len(pipeline.poems),3)
        self.assertEqual(pipeline.inspect()[0]['formalPending'],1)

    def test_unselected_archives_do_not_invalidate_selected_legacy_or_results(self):
        self.legacy()
        self.result('tang-010')
        document=read(self.root/'data/poems.json')
        document['selectionProfile']={'ids':['tang-002']}
        self.save('data/poems.json',document)
        report=Pipeline(self.root).inspect()[0]
        self.assertEqual(report['recoverableLegacyCount'],1)
        self.assertEqual(report['usableDrafts'],1)
        self.assertEqual(report['badDrafts'],0)
        self.assertEqual(report['issues'],[])
        self.assertTrue(any((self.root/'expansion/working/v2/results').glob('tang-010--*.json')))

    def test_dictionary_normalizes_duplicates_and_preserves_context_senses(self):
        self.poems[0]["content"] = "魑魑"
        self.save_data()
        definition = dict(meanings=[" 山鬼。 ", "山鬼。"], ancient="本文特指山中精怪。")
        self.legacy(1, poems=self.poems[:1], additions={"魑": definition})
        self.legacy(2, poems=self.poems[:1], additions={"魑": dict(meanings="山鬼。", ancient=["本文特指山中精怪。"] )})
        state = Pipeline(self.root).inspect()[2]["魑"]
        self.assertFalse(state["conflict"])
        self.assertEqual(len(state["candidates"]), 1)
        self.assertEqual(len(state["candidates"][0]["sources"]), 2)
        self.assertEqual(state["selected"]["ancient"], ["本文特指山中精怪。"])
        self.assertFalse(state["approved"])

    def test_conflicting_dictionary_requires_explicit_canonical_even_with_override(self):
        self.poems[0]["content"] = "魑魑"
        self.save_data()
        first = dict(meanings=["山鬼。"], ancient=["此篇指山中精怪。"])
        second = dict(meanings=["妖魅。"], ancient=["另一篇借指恶人。"])
        self.legacy(1, poems=self.poems[:1], additions={"魑": first})
        self.save("expansion/working/v2/dictionary/魑.json", second)
        self.result(approved=True)
        with self.assertRaisesRegex(ValueError, "canonical conflict"):
            self.assemble(ids=["tang-002"], allow_unreviewed=True)
        self.canonical("魑", second)
        result = self.assemble(ids=["tang-002"])
        batch = read(self.root / result["batch"])
        self.assertEqual(batch["dictionaryAdditions"]["魑"], second)
        candidates = batch["dictionaryCandidates"]["魑"]["candidates"]
        self.assertEqual(len(candidates), 2)
        self.assertTrue(any(first == c["definition"] for c in candidates))

    def test_official_dictionary_wins_and_contextual_alternatives_are_preserved(self):
        special = dict(meanings=["月亮。"], ancient=["原文借指一个月的期限。"])
        self.legacy(1, poems=self.poems[:1], additions={"月": special})
        self.result(approved=True)
        result = self.assemble(ids=["tang-002"])
        batch = read(self.root / result["batch"])
        self.assertEqual(batch["dictionaryAdditions"], {})
        entry = batch["dictionaryCandidates"]["月"]
        self.assertEqual(entry["selected"], self.dictionary["月"])
        self.assertTrue(entry["alternativesNeedReview"])
        self.assertEqual(entry["candidates"][0]["definition"], special)

    def test_unambiguous_dictionary_needs_review_by_default(self):
        self.poems[0]["content"] = "魑魑"
        self.save_data()
        self.result(approved=True)
        definition = dict(meanings=["山鬼。"], ancient=[])
        self.save("expansion/working/v2/dictionary/魑.json", definition)
        with self.assertRaisesRegex(ValueError, "Unreviewed dictionary"):
            self.assemble(ids=["tang-002"])
        self.canonical("魑", definition)
        self.assemble(ids=["tang-002"])

    def test_stale_canonical_selection_is_not_used(self):
        self.poems[0]["content"] = "魑魑"
        self.save_data()
        self.result(approved=True)
        definition = dict(meanings=["山鬼。"], ancient=[])
        self.canonical("魑", definition)
        self.save("expansion/working/v2/dictionary/魑.json", dict(meanings=["修改后的释义。"], ancient=[]))
        with self.assertRaises(ValueError):
            self.assemble(ids=["tang-002"], allow_unreviewed=True)

    def test_json_duplicate_keys_are_not_silently_lost(self):
        path = self.root / "duplicates.json"
        path.write_text('{"魑": 1, "魑": 2}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "Duplicate JSON key"):
            read(path)

    def test_assemble_rejects_unsafe_batch_names_and_invalid_versions(self):
        pipeline = Pipeline(self.root)
        for name in ("../011", "a/b", "011.json", ".."):
            with self.subTest(name=name), self.assertRaises(ValueError):
                pipeline.assemble(name, "1.1.7", "1.1.5")
        with self.assertRaises(ValueError):
            pipeline.assemble("011", "latest", "1.1.5")


if __name__ == "__main__":
    unittest.main()
