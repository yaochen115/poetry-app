"""Offline, append-only enrichment preparation. Python standard library only.

CLI (run from the project):
  python scripts/enrichment_pipeline.py prepare
  python scripts/enrichment_pipeline.py status
  python scripts/enrichment_pipeline.py assemble 011 --data-version 1.1.7 \
      --dictionary-version 1.1.5

Tasks name exact resultPath values. A poem result has ONLY id, tags, translation,
notes; its filename is results/{id}--{full inputHash}.json. Input hashes cover
source text/identity/excerpt metadata and the category's allowed tags. Editing a
source invalidates its old results; changing unrelated poems does not.

Manual poem reviews: reviews/{id}--{inputHash}.json containing
{decision: "approved"|"rejected", reviewer: "name", inputHash: "...",
 resultHash: digest(result)}. No command manufactures literary approval.

Dictionary results: dictionary/{character}.json with meanings/ancient lists.
Manual canonical selection: reviews/dictionary/{character}.json containing
{decision: "approved", reviewer: "name", definitionHash: digest(normalized entry)}.
Use status --details to inspect candidate hashes and sources. A selection must
match an extant candidate; edits invalidate the selection. Production entries
always win. Different non-production definitions require explicit selection even
with --allow-unreviewed. That flag permits unreviewed poems and unambiguous
dictionary drafts, and labels the resulting batch accordingly.

Legacy chunks are read only. Only wholly valid, source-matching legacy blocks
exclude IDs from the new queue. Individually valid patches in other blocks are
salvaged as v2 drafts, but their IDs remain in the task queue. All definitions,
including contextual ancient senses, remain in batch candidate records.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
import unicodedata


ROOT = Path(__file__).resolve().parents[1]
SOURCE_FIELDS = ("id", "category", "title", "subtitle", "author", "dynasty",
                 "content", "excerptOf", "excerptNote")
PATCH_FIELDS = {"id", "tags", "translation", "notes"}
PLACEHOLDERS = ("待补", "待译", "暂无", "译文略", "（略）", "同原文")
RESULT_RE = re.compile(r"^([a-z]+-\d+)--([0-9a-f]{64})\.json$")


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Duplicate JSON key: " + key)
        result[key] = value
    return result


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"),
                      object_pairs_hook=_unique_object)


def digest(value):
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
                                    separators=(",", ":")).encode("utf-8")).hexdigest()


def write_once(path, value, accept_identical=True):
    """Publish a complete file atomically without replacing any existing file."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                         dir=path.parent, prefix=".pipeline-", suffix=".tmp",
                                         delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(value, ensure_ascii=False, indent=2) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        # Same-filesystem hard-link creation is atomic and fails if path exists.
        os.link(temporary, path)
        return True
    except FileExistsError:
        if not accept_identical or read(path) != value:
            raise ValueError("Refusing to overwrite: " + str(path))
        return False
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def id_key(pid):
    prefix, number = pid.rsplit("-", 1)
    return prefix, int(number)


def characters(text):
    return {ch for ch in text if "\u4e00" <= ch <= "\u9fff" or ch == "〇"}


def normalized_text(value):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected nonempty text")
    return unicodedata.normalize("NFC", value.strip())


def normalize_definition(value):
    if not isinstance(value, dict) or set(value) - {"meanings", "ancient", "pinyin"}:
        raise ValueError("Definition requires meanings/ancient (optional pinyin)")
    result = {}
    for key in ("meanings", "ancient"):
        values = value.get(key, [])
        if isinstance(values, str):
            values = [values]
        if not isinstance(values, list):
            raise ValueError("Definition senses must be lists or strings")
        # Sort for semantic duplicate detection; never discard a distinct sense.
        result[key] = sorted({normalized_text(v) for v in values})
    if not (result["meanings"] or result["ancient"]):
        raise ValueError("Empty definition")
    return result


def validate_patch(patch, poem, tags):
    if not isinstance(patch, dict) or set(patch) != PATCH_FIELDS:
        raise ValueError("Patch requires exactly id/tags/translation/notes")
    if patch["id"] != poem["id"]:
        raise ValueError("Patch ID mismatch")
    translation = normalized_text(patch["translation"])
    if len(translation) < 8 or any(s in translation for s in PLACEHOLDERS):
        raise ValueError("Translation is too short or contains a placeholder")
    chosen = patch["tags"]
    if (not isinstance(chosen, list) or not chosen
            or any(not isinstance(t, str) or t not in tags for t in chosen)
            or len(chosen) != len(set(chosen))):
        raise ValueError("Invalid category tags")
    notes = patch["notes"]
    if not isinstance(notes, list) or not 3 <= len(notes) <= 18:
        raise ValueError("Expected 3..18 notes")
    for note in notes:
        if not isinstance(note, dict) or set(note) != {"term", "meaning"}:
            raise ValueError("Note requires term/meaning")
        normalized_text(note["term"])
        normalized_text(note["meaning"])


def estimate(poem):
    """Conservative output character budget, not a tokenizer or API cost."""
    length = len(poem["content"])
    return 600 + length * (3 if poem["category"] == "古文" else 2)


class Pipeline:
    def __init__(self, root=ROOT):
        self.root = Path(root).resolve()
        self.work = self.root / "expansion/working/v2"
        document = read(self.root / "data/poems.json")
        self.dictionary = read(self.root / "data/dict.json")["chars"]
        categories = read(self.root / "data/categories.json")["categories"]
        self.tags = {c["key"]: c["tags"] for c in categories}
        self.category_order = {c["key"]: n for n, c in enumerate(categories)}
        self.poems = {p["id"]: p for p in document["items"]}
        if len(self.poems) != len(document["items"]):
            raise ValueError("Duplicate production IDs")
        self.disabled = {p["id"] for p in document.get("disabledEntries", [])}
        from data_scope import active_items
        self.active = {p['id']: p for p in active_items(document)}
        self.pending = {pid: p for pid, p in self.active.items()
                        if p.get("editorialStatus") == "original_only"}

    def source(self, poem):
        return {k: poem.get(k, "" if k in ("subtitle", "excerptNote") else None)
                for k in SOURCE_FIELDS}

    def input_hash(self, poem):
        return digest({"poem": self.source(poem),
                       "tagEnum": sorted(self.tags[poem["category"]])})

    def result_path(self, poem):
        return self.work / "results" / (poem["id"] + "--" + self.input_hash(poem) + ".json")

    def relative(self, path):
        return Path(path).relative_to(self.root).as_posix()

    def ordered(self, ids):
        return sorted(ids, key=lambda pid: (self.category_order[self.poems[pid]["category"]],
                                            id_key(pid)))

    def legacy(self):
        recovered, excluded, definitions, issues = defaultdict(list), set(), [], []
        folder = self.root / "expansion/working/chunks"
        for output in sorted(folder.glob("out-*.json")):
            try:
                out = read(output)
                if not isinstance(out, dict):
                    raise ValueError("Legacy output must be an object")
            except (OSError, ValueError) as error:
                issues.append(dict(source=self.relative(output), error=str(error)))
                continue
            try:
                inp = read(output.with_name(output.name.replace("out-", "in-", 1)))
                if not isinstance(inp, dict):
                    raise ValueError("Legacy input must be an object")
            except (OSError, ValueError) as error:
                issues.append(dict(source=self.relative(output), error=str(error)))
                inp = {}
            try:
                raw_sources, raw_patches = inp.get("poems"), out.get("patches")
                valid = isinstance(raw_sources, list) and isinstance(raw_patches, list)
                sources = [p for p in (raw_sources if isinstance(raw_sources, list) else [])
                           if isinstance(p, dict) and isinstance(p.get("id"), str)]
                patches = [p for p in (raw_patches if isinstance(raw_patches, list) else [])
                           if isinstance(p, dict) and isinstance(p.get("id"), str)]
                valid &= (len(sources) == (len(raw_sources) if isinstance(raw_sources, list) else -1)
                          and len(patches) == (len(raw_patches) if isinstance(raw_patches, list) else -1))
                wanted = [p["id"] for p in sources]
                got = [p["id"] for p in patches]
                source_counts, counts = Counter(wanted), Counter(got)
                source_map = {p["id"]: p for p in sources}
                valid &= bool(wanted) and set(wanted) == set(got)
                valid &= all(n == 1 for n in list(source_counts.values()) + list(counts.values()))
                good = []
                for patch in patches:
                    pid = patch["id"]
                    try:
                        # Known, unselected archive records are outside this run's
                        # work scope. Preserve their files, rather than reporting
                        # the entire historical block as invalid.
                        if (pid in self.poems and pid not in self.active and
                                pid not in self.disabled and counts[pid] == 1 and source_counts[pid] == 1):
                            good.append(pid)
                            continue
                        if (pid not in self.active or counts[pid] != 1
                                or source_counts[pid] != 1):
                            raise ValueError("Unknown, disabled or duplicate legacy ID")
                        source = dict(source_map[pid], category=inp.get("category"))
                        if source_map[pid].get("category", source["category"]) != source["category"]:
                            raise ValueError("Legacy category mismatch")
                        old_hash = digest({"poem": self.source(source),
                                           "tagEnum": sorted(inp.get("tagEnum", []))})
                        expected = self.input_hash(self.poems[pid])
                        if old_hash != expected or source.get("inputHash", expected) != expected:
                            raise ValueError("Legacy source hash mismatch")
                        validate_patch(patch, self.poems[pid], self.tags[self.poems[pid]["category"]])
                        record = dict(patch=patch, inputHash=expected, source=self.relative(output))
                        good.append(pid)
                        if pid in self.pending:
                            recovered[pid].append(record)
                    except (ValueError, TypeError, KeyError) as error:
                        valid = False
                        issues.append(dict(source=self.relative(output), id=pid, error=str(error)))
                additions = out.get("dictionaryAdditions")
                if not isinstance(additions, dict):
                    valid = False
                    additions = {}
                required = set()
                for poem in sources:
                    missing = poem.get("missingChars")
                    if (not isinstance(missing, list)
                            or any(not isinstance(ch, str) or len(ch) != 1 for ch in missing)):
                        valid = False
                    else:
                        required.update(missing)
                if set(additions) != required:
                    valid = False
                    issues.append(dict(source=self.relative(output),
                                       error="Legacy dictionary coverage mismatch"))
                for ch, entry in additions.items():
                    try:
                        self.add_candidate(definitions, ch, entry, self.relative(output),
                                           [p["id"] for p in sources if ch in p.get("content", "")])
                    except (ValueError, TypeError) as error:
                        valid = False
                        issues.append(dict(source=self.relative(output), char=ch, error=str(error)))
                if valid and len(good) == len(wanted):
                    excluded.update(set(good) & self.pending.keys())
                elif not any(i["source"] == self.relative(output) for i in issues):
                    issues.append(dict(source=self.relative(output), error="Legacy block ID set mismatch"))
            except (OSError, ValueError, TypeError, KeyError) as error:
                issues.append(dict(source=self.relative(output), error=str(error)))
        return recovered, excluded, definitions, issues

    @staticmethod
    def add_candidate(records, ch, entry, source, ids):
        ch = normalized_text(ch)
        if len(ch) != 1 or not characters(ch):
            raise ValueError("Dictionary key must be one Chinese character")
        normalized = normalize_definition(entry)
        records.append(dict(char=ch, definition=normalized, definitionHash=digest(normalized),
                            source=source, contextIds=sorted(ids, key=id_key), original=entry))

    def dictionary_state(self, legacy_definitions):
        records = list(legacy_definitions)
        issues = []
        for path in sorted((self.work / "dictionary").glob("*.json")):
            try:
                self.add_candidate(records, path.stem, read(path), self.relative(path), [])
            except (OSError, ValueError, TypeError) as error:
                issues.append(dict(source=self.relative(path), error=str(error)))
        grouped = defaultdict(dict)
        for record in records:
            variants = grouped[record["char"]]
            candidate = variants.setdefault(record["definitionHash"], dict(
                definitionHash=record["definitionHash"], definition=record["definition"], sources=[]))
            candidate["sources"].append({k: record[k] for k in ("source", "contextIds", "original")})
        state = {}
        for ch in sorted(grouped):
            candidates = sorted(grouped[ch].values(), key=lambda c: c["definitionHash"])
            entry = dict(candidates=candidates, conflict=len(candidates) > 1,
                         selectedHash=None, approved=False, official=ch in self.dictionary)
            if entry["official"]:
                entry.update(selectedHash=digest(normalize_definition(self.dictionary[ch])),
                             approved=True, selected=normalize_definition(self.dictionary[ch]))
            else:
                review_path = self.work / "reviews/dictionary" / (ch + ".json")
                if review_path.exists():
                    try:
                        review = read(review_path)
                        selection = next((c for c in candidates
                                          if c["definitionHash"] == review.get("definitionHash")), None)
                        if (review.get("decision") != "approved" or not review.get("reviewer")
                                or selection is None):
                            raise ValueError("Invalid/stale dictionary canonical selection")
                        normalized_text(review["reviewer"])
                        entry.update(selectedHash=selection["definitionHash"], approved=True,
                                     selected=selection["definition"], review=review)
                    except (OSError, ValueError, TypeError, AttributeError) as error:
                        issues.append(dict(source=self.relative(review_path), error=str(error)))
                elif len(candidates) == 1:
                    entry.update(selectedHash=candidates[0]["definitionHash"],
                                 selected=candidates[0]["definition"])
            entry["needsReview"] = not entry["official"] and not entry["approved"]
            # Contextual alternatives to an official definition also remain pending.
            entry["alternativesNeedReview"] = entry["official"] and any(
                c["definitionHash"] != entry["selectedHash"] for c in candidates)
            state[ch] = entry
        return state, issues

    def drafts(self, recovered):
        drafts, bad, stale, issues = {}, set(), [], []
        # V2 is authoritative over a legacy draft for the same input.
        for pid, candidates in recovered.items():
            distinct = {digest(c["patch"]): c for c in candidates}
            if len(distinct) == 1:
                drafts[pid] = next(iter(distinct.values()))
            else:
                bad.add(pid)
                issues.append(dict(id=pid, error="Conflicting legacy poem drafts; choose a v2 result"))
        for path in sorted((self.work / "results").glob("*.json")):
            match = RESULT_RE.fullmatch(path.name)
            if not match:
                issues.append(dict(source=self.relative(path), error="Result filename requires full inputHash"))
                continue
            pid, input_hash = match.groups()
            if pid not in self.pending:
                # Already imported results are not pending drafts or broken drafts.
                if pid not in self.poems or pid in self.disabled:
                    issues.append(dict(source=self.relative(path), error="Unknown/disabled result ID"))
                continue
            if input_hash != self.input_hash(self.poems[pid]):
                stale.append(self.relative(path))
                continue
            try:
                patch = read(path)
                validate_patch(patch, self.poems[pid], self.tags[self.poems[pid]["category"]])
                drafts[pid] = dict(patch=patch, inputHash=input_hash, source=self.relative(path))
                bad.discard(pid)
            except (OSError, ValueError, TypeError, KeyError) as error:
                # A malformed v2 draft must not silently fall back to an older one.
                drafts.pop(pid, None)
                bad.add(pid)
                issues.append(dict(id=pid, source=self.relative(path), error=str(error)))
        for pid, record in drafts.items():
            record["approved"] = False
            review_path = self.work / "reviews" / (pid + "--" + record["inputHash"] + ".json")
            if not review_path.exists():
                continue
            try:
                review = read(review_path)
                if (review.get("inputHash") != record["inputHash"]
                        or review.get("resultHash") != digest(record["patch"])
                        or not review.get("reviewer")
                        or review.get("decision") not in ("approved", "rejected")):
                    raise ValueError("Invalid/stale literary review")
                normalized_text(review["reviewer"])
                record["approved"] = review["decision"] == "approved"
                record["rejected"] = review["decision"] == "rejected"
                record["review"] = review
                if record["rejected"]:
                    bad.add(pid)
            except (OSError, ValueError, TypeError, AttributeError) as error:
                issues.append(dict(id=pid, source=self.relative(review_path), error=str(error)))
        return drafts, bad, stale, issues

    def inspect(self):
        recovered, excluded, definitions, legacy_issues = self.legacy()
        drafts, bad, stale, result_issues = self.drafts(recovered)
        bad.update(i["id"] for i in legacy_issues
                   if i.get("id") in self.pending and i["id"] not in drafts)
        dictionary, dictionary_issues = self.dictionary_state(definitions)
        usable = {pid: r for pid, r in drafts.items() if not r.get("rejected")}
        approved = [pid for pid, r in usable.items() if r["approved"]]
        report = dict(
            formalComplete=len(self.active) - len(self.pending),
            formalPending=len(self.pending), disabled=len(self.disabled),
            usableDrafts=len(usable), approvedDrafts=len(approved),
            awaitingReview=len(usable) - len(approved), badDrafts=len(bad),
            missingDrafts=len(set(self.pending) - set(drafts) - bad),
            recoverableLegacyCount=len(excluded), recoverableLegacyIds=self.ordered(excluded),
            staleResults=stale,
            dictionaryConflicts=sum(e["conflict"] for e in dictionary.values()),
            dictionaryAwaitingReview=sum(e["needsReview"] or e["alternativesNeedReview"]
                                         for e in dictionary.values()),
            issues=legacy_issues + result_issues + dictionary_issues,
            meaning="Usable means structurally valid and source-matching; literary approval is separate.")
        return report, drafts, dictionary, recovered

    def prepare(self, max_items=12, max_chars=5000, max_output=16000):
        if min(max_items, max_chars, max_output) < 1:
            raise ValueError("Budgets must be positive")
        report, drafts, dictionary, recovered = self.inspect()
        for pid in self.ordered(recovered):
            record = drafts.get(pid)
            if record and record["source"].startswith("expansion/working/chunks/"):
                write_once(self.result_path(self.poems[pid]), record["patch"])
        queue = self.ordered(set(self.pending) - set(report["recoverableLegacyIds"]))
        # Existing immutable tasks reserve only their still-current assignments.
        assigned = set()
        for path in sorted((self.work / "tasks").glob("poems-*.json")):
            task = read(path)
            for item in task["poems"]:
                pid = item["id"]
                if pid in self.pending and item["inputHash"] == self.input_hash(self.poems[pid]):
                    assigned.add(pid)
        pending_tasks = [pid for pid in queue if pid not in assigned]
        chunks, chunk, chars, output = [], [], 0, 0
        for pid in pending_tasks:
            poem = self.poems[pid]
            length, budget = len(poem["content"]), estimate(poem)
            if chunk and (poem["category"] != self.poems[chunk[0]]["category"]
                          or len(chunk) >= max_items or chars + length > max_chars
                          or output + budget > max_output):
                chunks.append(chunk)
                chunk, chars, output = [], 0, 0
            chunk.append(pid)
            chars += length
            output += budget
        if chunk:
            chunks.append(chunk)
        created = []
        for ids in chunks:
            poems = [dict(self.source(self.poems[pid]), inputHash=self.input_hash(self.poems[pid]),
                          estimatedOutput=estimate(self.poems[pid]),
                          resultPath=self.relative(self.result_path(self.poems[pid]))) for pid in ids]
            total_chars = sum(len(p["content"]) for p in poems)
            total_output = sum(p["estimatedOutput"] for p in poems)
            task = dict(schemaVersion=2, category=poems[0]["category"],
                        tagEnum=self.tags[poems[0]["category"]], poems=poems,
                        contentChars=total_chars, estimatedOutput=total_output,
                        oversized=total_chars > max_chars or total_output > max_output,
                        budgets=dict(maxItems=max_items, maxChars=max_chars, maxOutput=max_output))
            path = self.work / "tasks" / ("poems-" + digest(task) + ".json")
            if write_once(path, task):
                created.append(self.relative(path))
        queue_document = dict(schemaVersion=2, sourceOfTruth="data/poems.json",
                              items=[dict(id=pid, inputHash=self.input_hash(self.poems[pid]),
                                          resultPath=self.relative(self.result_path(self.poems[pid])),
                                          hasDraft=pid in drafts) for pid in queue])
        queue_path = self.work / "queues" / ("poems--" + digest(queue_document) + ".json")
        write_once(queue_path, queue_document)
        contexts = defaultdict(list)
        for pid in self.ordered(self.pending):
            for ch in sorted(characters(self.poems[pid]["content"]) - self.dictionary.keys()):
                contexts[ch].append(pid)
        dictionary_items = []
        for ch in sorted(contexts):
            task = dict(schemaVersion=2, char=ch,
                        resultPath=self.relative(self.work / "dictionary" / (ch + ".json")))
            task_path = self.work / "tasks/dictionary" / ("U+%04X.json" % ord(ch))
            write_once(task_path, task)
            dictionary_items.append(dict(task, taskPath=self.relative(task_path), contextIds=contexts[ch],
                                         candidates=dictionary.get(ch, {}).get("candidates", [])))
        dictionary_queue = dict(schemaVersion=2, items=dictionary_items)
        dictionary_path = self.work / "queues" / ("dictionary--" + digest(dictionary_queue) + ".json")
        write_once(dictionary_path, dictionary_queue)
        (self.work / "results").mkdir(parents=True, exist_ok=True)
        (self.work / "dictionary").mkdir(parents=True, exist_ok=True)
        return dict(queue=self.relative(queue_path), dictionaryQueue=self.relative(dictionary_path),
                    queuedPoems=len(queue), createdTasks=created, missingCharacters=len(contexts),
                    recoveredLegacy=len(report["recoverableLegacyIds"]))

    def assemble(self, batch, data_version, dictionary_version, ids=None, allow_unreviewed=False):
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", batch) or batch.endswith(".json"):
            raise ValueError("Batch must be a filename stem without a directory or .json suffix")
        for version in (data_version, dictionary_version):
            if not re.fullmatch(r"\d+\.\d+\.\d+", version):
                raise ValueError("Versions must have the form 1.2.3")
        path = self.root / "expansion/enrichment" / (batch + ".json")
        if path.exists():
            raise ValueError("Refusing to overwrite existing batch: " + str(path))
        report, drafts, dictionary, _ = self.inspect()
        selected = list(ids) if ids is not None else [pid for pid, r in drafts.items()
                    if not r.get("rejected") and (allow_unreviewed or r["approved"])]
        if not selected or len(selected) != len(set(selected)):
            raise ValueError("No selected eligible drafts, or duplicate IDs")
        if any(pid not in self.pending for pid in selected):
            raise ValueError("Selected IDs must be active production pending entries")
        patches, poem_reviews = [], {}
        for pid in self.ordered(selected):
            record = drafts.get(pid)
            if (pid not in self.pending or record is None or record.get("rejected")
                    or (not allow_unreviewed and not record["approved"])):
                raise ValueError("Missing, bad, stale or unreviewed draft: " + pid)
            patches.append(record["patch"])
            poem_reviews[pid] = dict(inputHash=record["inputHash"], resultHash=digest(record["patch"]),
                                    source=record["source"], review=record.get("review"),
                                    literaryApproved=record["approved"])
        required = {ch for patch in patches for ch in characters(self.poems[patch["id"]]["content"])}
        additions = {}
        for ch in sorted(required - self.dictionary.keys()):
            entry = dictionary.get(ch)
            if not entry or not entry.get("selected"):
                raise ValueError("Missing definition or unresolved canonical conflict: " + ch)
            if not allow_unreviewed and not entry["approved"]:
                raise ValueError("Unreviewed dictionary definition: " + ch)
            additions[ch] = entry["selected"]
        result = dict(dataVersion=data_version, dictionaryVersion=dictionary_version,
                      policy="Offline assembled drafts; literary and dictionary review recorded separately.",
                      patches=patches, dictionaryAdditions=additions,
                      review=dict(literaryApproved=all(r["literaryApproved"] for r in poem_reviews.values()),
                                  allowUnreviewed=allow_unreviewed, poems=poem_reviews),
                      # Keep ALL observed variants, even alternatives to an official entry.
                      dictionaryCandidates=dictionary, pipelineIssues=report["issues"])
        write_once(path, result, accept_identical=False)
        return dict(batch=self.relative(path), patches=len(patches), dictionaryAdditions=len(additions))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Recover drafts and append budgeted tasks")
    prepare.add_argument("--max-items", type=int, default=12)
    prepare.add_argument("--max-chars", type=int, default=5000)
    prepare.add_argument("--max-output", type=int, default=16000, help="Estimated output characters")
    status = commands.add_parser("status", help="Read-only production/draft/review status")
    status.add_argument("--details", action="store_true")
    assemble = commands.add_parser("assemble", help="Create a new batch for apply_enrichment_batch.py")
    assemble.add_argument("batch")
    assemble.add_argument("--data-version", required=True)
    assemble.add_argument("--dictionary-version", required=True)
    assemble.add_argument("--ids", nargs="+")
    assemble.add_argument("--allow-unreviewed", action="store_true")
    args = parser.parse_args(argv)
    try:
        pipeline = Pipeline(args.root)
        if args.command == "prepare":
            result = pipeline.prepare(args.max_items, args.max_chars, args.max_output)
        elif args.command == "status":
            result, drafts, dictionary, _ = pipeline.inspect()
            if args.details:
                result.update(drafts=drafts, dictionary=dictionary)
            else:
                result.pop("recoverableLegacyIds")
        else:
            result = pipeline.assemble(args.batch, args.data_version, args.dictionary_version,
                                       args.ids, args.allow_unreviewed)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print("Pipeline error: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except AttributeError:
        pass
    sys.exit(main())
