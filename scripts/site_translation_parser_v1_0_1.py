"""Parse cached work pages offline using only the Python standard library.

python scripts/site_translation_parser_v1_0_1.py expansion/site-selected/known-v1.0.0 \
    --output expansion/site-selected/parsed-known-v1.0.1.json

No fetching, semantic approval, or production writes. --output creates a NEW
report and refuses any existing filename. Without --output, JSON goes to stdout.
Exit 1 means a failure or zero candidates; non-work pages are separately skipped.
Fetch sidecars are paired by filename prefix, then their recorded SHA is checked.
Raw HTML without a sidecar needs a canonical/og:url link (or --url for one file).

Normalization removes Unicode punctuation and whitespace ONLY, with NFC; it
does not change characters, simplify Chinese, drop prefaces, or accept substrings.
Candidate notes are exact source lines, NOT invented term/meaning apply patches.
All source text remains reference material requiring editorial review.

1.0.1 recognizes plain paragraph labels as well as strong-tag labels. A folded
fanyiquan block is eligible ONLY when already present in the received HTML,
paired with a visible fanyi preview and fanyiShow link for this same work. No
JavaScript, endpoint requests, login, or access-control bypass is performed.
"""

import argparse
from collections import defaultdict
from dataclasses import dataclass, field
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import unicodedata
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
VERSION = "1.0.1"
VOID = set("area base br col embed hr img input link meta param source track wbr".split())
BLOCKS = set("div p br li h1 h2 h3 h4 section article ul ol".split())
NOISE = {"nav", "header", "footer", "aside", "script", "style", "noscript", "textarea", "button"}
NOISE_CLASSES = {"tool", "tag", "cankao", "recommend", "recommendations", "tuijian", "navigation", "jiucuo"}
HEADINGS = {"译文": "translation", "白话译文": "translation", "注释": "notes", "注解": "notes",
            "译文及注释": None, "译文及注解": None, "参考资料": None,
            "赏析": None, "鉴赏": None, "简析": None, "创作背景": None}
WORK_URL = re.compile(r"/shiwenv_([a-zA-Z0-9]+)\.aspx$")
FANYI_SHOW = re.compile(r"\bfanyiShow\(\s*(\d+)\s*,\s*['\"][^'\"]*['\"]\s*,\s*['\"]([a-zA-Z0-9]+)['\"]\s*\)")
ACCESS_MESSAGES = ("登录后", "登录查看", "登录阅读", "请先登录", "会员专享", "开通会员", "付费阅读")
# Explicit title alias in the cached four-page corpus. Body AND author still
# have to match in full; this is not a general fuzzy-title exception.
TITLE_ALIASES = {("白居易", "草"): {"赋得古原草送别"}}


class ParseFailure(ValueError):
    pass


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def normalize(text):
    return "".join(ch for ch in unicodedata.normalize("NFC", text)
                   if not ch.isspace() and not unicodedata.category(ch).startswith("P"))


@dataclass
class Node:
    tag: str
    attrs: dict
    parent: object = None
    children: list = field(default_factory=list)
    closed: bool = False
    order: int = 0

    @property
    def classes(self):
        return set(self.attrs.get("class", "").split())

    def walk(self):
        yield self
        for child in self.children:
            if isinstance(child, Node):
                yield from child.walk()


def hidden(node, allowed_fold=None):
    style = re.sub(r"\s+", "", node.attrs.get("style", "").lower())
    return (node.tag in NOISE or bool(node.classes & NOISE_CLASSES)
            or "hidden" in node.attrs or node.attrs.get("aria-hidden") == "true"
            or ("display:none" in style and node is not allowed_fold) or "visibility:hidden" in style
            or node.attrs.get("id", "").lower().startswith(("tuijian", "recommend")))


def visible(node, allowed_fold=None):
    while node is not None:
        if hidden(node, allowed_fold):
            return False
        node = node.parent
    return True


def content_text(node, allowed_fold=None):
    parts = []

    def visit(current):
        if hidden(current, allowed_fold):
            return
        if current.tag in BLOCKS:
            parts.append("\n")
        for child in current.children:
            if isinstance(child, Node):
                visit(child)
            else:
                parts.append(child)
        if current.tag in BLOCKS:
            parts.append("\n")

    visit(node)
    return "\n".join(line.strip() for line in "".join(parts).splitlines() if line.strip())


class WorkHTML(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.root = Node("root", {}, closed=True)
        self.stack = [self.root]
        self.serial = 0

    def handle_starttag(self, tag, attrs):
        self.serial += 1
        node = Node(tag, dict(attrs), self.stack[-1], closed=tag in VOID, order=self.serial)
        self.stack[-1].children.append(node)
        if tag not in VOID:
            self.stack.append(node)

    def handle_startendtag(self, tag, attrs):
        self.handle_starttag(tag, attrs)
        if tag not in VOID:
            self.handle_endtag(tag)

    def handle_endtag(self, tag):
        for index in range(len(self.stack) - 1, 0, -1):
            if self.stack[index].tag == tag:
                self.stack[index].closed = True
                del self.stack[index:]
                return

    def handle_data(self, data):
        self.stack[-1].children.append(data)


def work_key(url):
    match = WORK_URL.fullmatch(urlsplit(url).path)
    return match.group(1) if match else None


def page_url(tree):
    urls = set()
    for node in tree.walk():
        if node.tag == "link" and "canonical" in node.attrs.get("rel", "").split():
            urls.add(node.attrs.get("href", ""))
        if node.tag == "meta" and node.attrs.get("property", "").lower() == "og:url":
            urls.add(node.attrs.get("content", ""))
    keys = {work_key(url) for url in urls if work_key(url)}
    if len(keys) > 1:
        raise ParseFailure("Conflicting canonical work URLs")
    return next((url for url in sorted(urls) if work_key(url)), None)


def extract_sections(block, allowed_fold=None, allow_truncated=False):
    headings = [n for n in block.walk() if n.tag in {"h2", "h3"} and visible(n, allowed_fold)]
    if not headings or content_text(headings[0], allowed_fold) not in {
            "译文及注释", "译文及注解", "译文", "白话译文", "注释", "注解"}:
        return None
    if not block.closed:
        raise ParseFailure("Unclosed translation container")
    state, parts, truncated = None, {"translation": [], "notes": []}, False
    lines = []

    def visit(node):
        nonlocal truncated
        if hidden(node, allowed_fold):
            return
        heading = content_text(node, allowed_fold)
        action = node.attrs.get("href", "") + " " + node.attrs.get("onclick", "")
        if FANYI_SHOW.search(action) or (node.tag in {"a", "button"} and any(
                x in heading for x in ("展开阅读全文", "展开全部", "展开阅读"))):
            truncated = True
            return
        if node.tag in {"a", "button"} and (heading in {"收起", "展开"} or "fanyiClose(" in action):
            return
        if node.tag in {"h2", "h3", "h4", "strong", "b"} and heading in HEADINGS:
            lines.extend(["\n", heading, "\n"])
            return
        if node.tag in BLOCKS:
            lines.append("\n")
        for child in node.children:
            if isinstance(child, Node):
                visit(child)
            else:
                lines.append(child)
        if node.tag in BLOCKS:
            lines.append("\n")

    visit(block)
    for line in "".join(lines).splitlines():
        line = line.strip()
        if any(message in line for message in ACCESS_MESSAGES):
            raise ParseFailure("requires_login: cached translation contains an access notice")
        if line in HEADINGS:
            state = HEADINGS[line]
        elif line and state:
            parts[state].append(line)
    # Keep exact paragraph/BR boundaries rather than merging note lines.
    result = {key: "\n".join(value) for key, value in parts.items()}
    result["truncated"] = truncated
    if truncated and not allow_truncated:
        raise ParseFailure("requires_expansion: truncated translation/notes has no complete cached replacement")
    return result


def translation_sections(blocks, tree, key, boundary):
    """Resolve only explicit same-work preview/full pairs already in the cache."""
    by_id = defaultdict(list)
    for node in tree.walk():
        if node.attrs.get("id"):
            by_id[node.attrs["id"]].append(node)
    sections, details = [], []
    for block in blocks:
        section = extract_sections(block, allow_truncated=True)
        if section is None:
            continue
        if not section["truncated"]:
            sections.append(section)
            details.append(dict(mode="visible_dom", requiresNetwork=False))
            continue
        wrapper = block.parent
        while wrapper is not None and not re.fullmatch(r"fanyi\d+", wrapper.attrs.get("id", "")):
            wrapper = wrapper.parent
        if wrapper is None:
            raise ParseFailure("requires_expansion: truncated block has no identified fanyi preview")
        number = wrapper.attrs["id"][5:]
        links = [match.groups() for node in block.walk()
                 for match in FANYI_SHOW.finditer(node.attrs.get("href", "") + " " + node.attrs.get("onclick", ""))]
        if not links or any(n != number or work != key for n, work in links):
            raise ParseFailure("cached_pair_mismatch: expand control does not identify this preview/work")
        full_id = "fanyiquan" + number
        full_nodes = by_id.get(full_id, [])
        if len(full_nodes) != 1:
            raise ParseFailure("requires_expansion: complete paired block is absent or ambiguous in cached HTML")
        full = full_nodes[0]
        if not full.closed or not wrapper.order < full.order < boundary or not visible(full, full):
            raise ParseFailure("requires_expansion: paired full block is unclosed, inaccessible or outside this work")
        full_blocks = [n for n in full.walk() if "contyishang" in n.classes and visible(n, full)]
        if len(full_blocks) != 1:
            raise ParseFailure("cached_pair_mismatch: ambiguous full translation container")
        close_pattern = re.compile(r"\bfanyiClose\(\s*" + re.escape(number) + r"\s*\)")
        if not any(close_pattern.search(n.attrs.get("href", "") + " " + n.attrs.get("onclick", ""))
                   for n in full.walk()):
            raise ParseFailure("cached_pair_mismatch: full block lacks its paired close control")
        complete = extract_sections(full_blocks[0], allowed_fold=full)
        if not complete or not complete["translation"] or not complete["notes"]:
            raise ParseFailure("requires_expansion: cached full block has incomplete translation/notes")
        for name in ("translation", "notes"):
            if section[name] and not normalize(complete[name]).startswith(normalize(section[name])):
                raise ParseFailure("cached_pair_mismatch: full " + name + " does not extend its visible preview")
        sections.append(complete)
        details.append(dict(mode="complete_fold_already_in_received_html", previewId=wrapper.attrs["id"],
                            fullId=full_id, prefixVerified=True, requiresNetwork=False,
                            discardedPreview=dict(reason="truncated_same_source_preview",
                                translationCharacters=len(section["translation"]),
                                notesCharacters=len(section["notes"]),
                                translationSha256=hashlib.sha256(section["translation"].encode("utf-8")).hexdigest(),
                                notesSha256=hashlib.sha256(section["notes"].encode("utf-8")).hexdigest())))
    return sections, details


def title_match(page_title, poem):
    title = normalize(page_title)
    if title in {normalize(poem["title"]), normalize(poem["title"] + poem.get("subtitle", ""))}:
        return "exact_or_subtitle"
    aliases = TITLE_ALIASES.get((poem["author"], poem["title"]), set())
    return "registered_alias" if title in {normalize(alias) for alias in aliases} else None


def extract(raw, url=None):
    parser = WorkHTML()
    parser.feed(raw.decode("utf-8-sig", errors="strict"))
    parser.close()
    tree = parser.root
    canonical = page_url(tree)
    url = url or canonical
    if not url or not work_key(url):
        raise ParseFailure("Missing work-page URL; provide fetch metadata, canonical URL or --url")
    if canonical and work_key(canonical) != work_key(url):
        raise ParseFailure("Canonical URL does not match source metadata")
    originals = [n for n in tree.walk() if "contson" in n.classes and visible(n)]
    exact = [n for n in originals if n.attrs.get("id") == "contson" + work_key(url)]
    if len(exact) == 1:
        original = exact[0]
    elif not exact and len(originals) == 1:
        original = originals[0]
        if original.attrs.get("id") and original.attrs["id"] != "contson" + work_key(url):
            raise ParseFailure("contson identity differs from work URL")
    else:
        raise ParseFailure("Missing or ambiguous primary contson")
    if not original.closed or not content_text(original):
        raise ParseFailure("Empty or unclosed contson")
    scope = original.parent
    while scope is not None:
        titles = [n for n in scope.walk() if n.tag == "h1" and visible(n)]
        sources = [n for n in scope.walk() if "source" in n.classes and visible(n)]
        if len(titles) == len(sources) == 1:
            break
        scope = scope.parent
    if scope is None or not titles[0].closed or not sources[0].closed:
        raise ParseFailure("Missing or ambiguous h1/source in primary work")
    links = [n for n in sources[0].walk() if n.tag == "a" and visible(n)
             and "/author" in n.attrs.get("href", "")]
    author = content_text(links[0]) if len(links) == 1 else ""
    if not links:
        author = re.sub(r"〔[^〕]*〕|\[[^]]*\]", "", content_text(sources[0])).strip()
    if not author:
        raise ParseFailure("Missing or ambiguous source author")
    # A subsequent work is a hard boundary: never borrow its translation.
    boundary = min((n.order for n in tree.walk() if visible(n) and n.order > original.order
                    and (n.tag == "h1" or "contson" in n.classes)), default=float("inf"))
    container = scope
    blocks = []
    while container is not None:
        blocks = [n for n in container.walk() if "contyishang" in n.classes and visible(n)
                  and original.order < n.order < boundary]
        if blocks:
            break
        container = container.parent
    sections, extraction_details = translation_sections(blocks, tree, work_key(url), boundary)
    translations = {s["translation"] for s in sections if s["translation"]}
    notes = {s["notes"] for s in sections if s["notes"]}
    if len(translations) != 1:
        raise ParseFailure("Missing or conflicting translation in contyishang")
    if len(notes) != 1:
        raise ParseFailure("Missing or conflicting annotations in contyishang")
    return dict(title=content_text(titles[0]), author=author, sourceText=content_text(sources[0]),
                content=content_text(original), translation=next(iter(translations)),
                notes=next(iter(notes)).splitlines(), url=url, canonicalUrl=canonical,
                extractionDetails=extraction_details)


def poem_index(poems):
    index = defaultdict(list)
    for poem in poems:
        if not all(isinstance(poem.get(k), str) and poem[k].strip()
                   for k in ("id", "content", "title", "author")):
            raise ParseFailure("Expected poem items with id/content/title/author")
        index[normalize(poem["content"])].append(poem)
    return index


def parse_file(path, index, metadata=None, url=None):
    path = Path(path)
    raw = path.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    metadata = metadata or {}
    if metadata.get("error") or metadata.get("status", 200) != 200:
        raise ParseFailure("Fetch metadata reports failure")
    if metadata.get("sha256") and metadata["sha256"] != sha:
        raise ParseFailure("HTML SHA-256 differs from fetch metadata")
    if metadata.get("bytes", len(raw)) != len(raw):
        raise ParseFailure("HTML byte length differs from fetch metadata")
    source_url = url or metadata.get("finalUrl") or metadata.get("url")
    page = extract(raw, source_url)
    matches = index.get(normalize(page["content"]), [])
    if not matches:
        raise ParseFailure("Full normalized body does not match expected poems")
    matches = [poem for poem in matches if normalize(poem["author"]) == normalize(page["author"])
               and title_match(page["title"], poem)]
    if len(matches) != 1:
        raise ParseFailure("Title/author mismatch or ambiguous matching poem IDs")
    poem = matches[0]
    return dict(id=poem["id"], **page, parserVersion=VERSION, stage="reference_candidate",
                matchedTitle=poem["title"], titleMatch=title_match(page["title"], poem),
                normalizedTextMatch=True, literaryApproved=False,
                matchedPoemSha256=hashlib.sha256(json.dumps({k: poem.get(k) for k in
                    ("id", "title", "subtitle", "author", "content")}, ensure_ascii=False,
                    sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest(),
                provenance=dict(htmlFile=str(path.resolve()), htmlSha256=sha,
                    requestedUrl=metadata.get("url"), acquiredAt=metadata.get("acquiredAt"),
                    reuseStatus=metadata.get("reuseStatus", "reference_only_permission_not_established"),
                    source="古诗文网/古文岛 cached HTML", parserVersion=VERSION))


def parse_directory(directory, poems, url=None):
    directory = Path(directory)
    html_files = [directory] if directory.is_file() else sorted(directory.rglob("*.html"))
    if url and len(html_files) != 1:
        raise ParseFailure("--url requires exactly one HTML file")
    index = poem_index(poems)
    report = dict(parserVersion=VERSION, candidates=[], failures=[], skipped=[])
    sidecars = defaultdict(list)
    folders = {path.parent for path in html_files}
    for folder in folders:
        for path in sorted(folder.glob("*.json")):
            if "--" not in path.stem:
                continue
            try:
                record = read_json(path)
                if not isinstance(record, dict) or not record.get("url"):
                    continue
                sidecars[(folder, path.stem.rsplit("--", 1)[0])].append((path, record))
            except (OSError, ValueError) as error:
                report["failures"].append(dict(file=str(path), error="Invalid sidecar: " + str(error)))
    if not html_files:
        report["failures"].append(dict(file=str(directory), error="No cached HTML files"))
    processed = set()
    for path in html_files:
        prefix = path.stem.rsplit("--", 1)[0]
        records = sidecars.get((path.parent, prefix), [])
        # Multiple acquisition attempts are allowed, but choose only the exact SHA.
        actual_sha = hashlib.sha256(path.read_bytes()).hexdigest()
        exact = [(meta_path, record) for meta_path, record in records if record.get("sha256") == actual_sha]
        choices = exact or records
        try:
            if len({r.get("finalUrl", r["url"]) for _, r in choices}) > 1:
                raise ParseFailure("Ambiguous fetch sidecars")
            meta_path, metadata = choices[0] if choices else (None, {})
            if metadata and not work_key(metadata.get("finalUrl") or metadata["url"]):
                report["skipped"].append(dict(file=str(path), reason="Not a work page"))
                continue
            candidate = parse_file(path, index, metadata, url)
            if meta_path:
                candidate["provenance"].update(metadataFile=str(meta_path.resolve()),
                    metadataSha256=hashlib.sha256(meta_path.read_bytes()).hexdigest())
                processed.add(meta_path)
            report["candidates"].append(candidate)
        except (OSError, ValueError, TypeError, KeyError, RecursionError) as error:
            report["failures"].append(dict(file=str(path), error=str(error)))
    for records in sidecars.values():
        for path, record in records:
            if path not in processed and record.get("error") and work_key(record["url"]):
                report["failures"].append(dict(file=str(path), error="Failed acquisition: " + str(record["error"])))
    report["counts"] = {name: len(report[name]) for name in ("candidates", "failures", "skipped")}
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("directory", nargs="?", type=Path, default=ROOT / "expansion/site-samples")
    parser.add_argument("--poems", type=Path, default=ROOT / "data/poems.json")
    parser.add_argument("--url", help="Source URL for exactly one raw HTML file")
    parser.add_argument("--output", type=Path, help="New JSON report; never overwrite")
    args = parser.parse_args(argv)
    try:
        poems = read_json(args.poems)
        report = parse_directory(args.directory, poems["items"] if isinstance(poems, dict) else poems, args.url)
        encoded = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            with args.output.open("x", encoding="utf-8") as stream:
                stream.write(encoded)
            print(json.dumps(report["counts"], ensure_ascii=False))
        else:
            print(encoded, end="")
        return 1 if report["failures"] or not report["candidates"] else 0
    except (OSError, ValueError, TypeError, KeyError) as error:
        print("Parser error: " + str(error), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")
    sys.exit(main())
