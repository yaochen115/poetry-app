"""Offline JSON/JSONL references -> review packets -> compatible enrichment batch.

prepare never modifies production. assemble requires explicit content/use reviews,
current source hashes and reviewed definitions for every missing character.
"""
import argparse
from collections import defaultdict
from html import unescape
from html.parser import HTMLParser
import hashlib
import json
from pathlib import Path
import re
import sys

from enrichment_pipeline import Pipeline, digest, read, write_once, validate_patch, ROOT
from prepare_reference_review_v1_0_0 import extract_notes

sys.path.insert(0, str(ROOT/'expansion/python-packages'))
from opencc import OpenCC

CC = OpenCC('t2s')


class PlainText(HTMLParser):
    def __init__(self):
        super().__init__(); self.parts = []; self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style'): self.hidden += 1
        if tag in ('br', 'p', 'div', 'li'): self.parts.append('\n')

    def handle_endtag(self, tag):
        if tag in ('script', 'style'): self.hidden = max(0, self.hidden-1)
        if tag in ('p', 'div', 'li'): self.parts.append('\n')

    def handle_data(self, data):
        if not self.hidden: self.parts.append(data)


def text(value):
    if isinstance(value, list): return '\n'.join(text(v) for v in value)
    if not isinstance(value, str): return ''
    parser = PlainText(); parser.feed(value)
    return '\n'.join(line.strip() for line in unescape(''.join(parser.parts)).splitlines()
                     if line.strip())


def normal(value):
    return re.sub(r'[^\u3400-\u9fff〇]', '', CC.convert(text(value)))


def first(row, *keys):
    return next((row[k] for k in keys if row.get(k)), '')


def records(path):
    raw = path.read_text(encoding='utf-8-sig')
    try: data = json.loads(raw)
    except json.JSONDecodeError:
        data = [json.loads(line) for line in raw.splitlines() if line.strip()]
    if isinstance(data, dict): data = data.get('items', [data])
    if not isinstance(data, list): raise ValueError(f'Expected records: {path}')
    return data


def flags_for(patch):
    flags = []
    translation = patch['translation']
    if not translation: flags.append('missing_translation')
    elif len(translation.strip()) < 8: flags.append('translation_too_short')
    if re.match(r'^(?:译文\s*)?(?:注释|注解|词句注释)', translation):
        flags.append('annotations_in_translation')
    if any(s in translation for s in ('待译', '暂无', '译文略', '（略）')):
        flags.append('placeholder_or_truncation')
    if not 3 <= len(patch['notes']) <= 18: flags.append('notes_count')
    if not patch['tags']: flags.append('missing_tags')
    if '\ufffd' in translation: flags.append('encoding_error')
    return flags


def prepare(args):
    pipe = Pipeline(); lookup = defaultdict(list)
    for pid in pipe.pending:
        poem = pipe.poems[pid]
        lookup[(normal(poem['content']), normal(poem['author']))].append(pid)
    paths = set()
    for source in args.source:
        if source.is_dir():
            paths.update(source.rglob('*.json')); paths.update(source.rglob('*.jsonl'))
        else: paths.add(source)
    candidates = defaultdict(list); errors = []; scanned = 0
    for path in sorted(paths):
        path = path.resolve()
        try: rows = records(path)
        except (ValueError, OSError) as exc:
            errors.append({'file': str(path), 'error': str(exc)}); continue
        source_hash = hashlib.sha256(path.read_bytes()).hexdigest()
        for index, row in enumerate(rows):
            if not isinstance(row, dict): continue
            scanned += 1
            body = first(row, 'content', 'paragraph', 'paragraphs')
            author = first(row, 'authorName', 'writer', 'author')
            # Authorless corpora require a separate verified identity mapping.
            for pid in lookup.get((normal(body), normal(author)), []):
                poem = pipe.poems[pid]
                translation = text(first(row, 'translation', 'translate'))
                if not translation: continue
                raw_notes = first(row, 'annotation', 'remark', 'notes')
                if isinstance(raw_notes, list) and all(isinstance(n, dict) for n in raw_notes):
                    notes = [{'term': text(n.get('term')), 'meaning': text(n.get('meaning'))}
                             for n in raw_notes]
                    notes = [n for n in notes if n['term'] and n['term'] in poem['content'] and n['meaning']]
                else: notes = extract_notes(text(raw_notes), poem['content'])
                notes = list({n['term']: n for n in notes}.values())[:18]
                source_tags = first(row, 'tags', 'type')
                if not isinstance(source_tags, list): source_tags = []
                tags = list(dict.fromkeys(t for t in [*poem.get('tags', []), *source_tags]
                                         if isinstance(t, str) and t in pipe.tags[poem['category']]))[:2]
                patch = dict(id=pid, tags=tags, translation=translation, notes=notes)
                candidate = dict(patch=patch, inputHash=pipe.input_hash(poem),
                    source=dict(file=str(path), row=index, sha256=source_hash,
                                title=text(row.get('title')), author=text(author)),
                    flags=flags_for(patch),
                    reviewStatus='unreviewed', reuseStatus='unconfirmed')
                if normal(row.get('title')) != normal(poem['title']):
                    candidate['flags'].append('title_variant_requires_review')
                candidates[pid].append(candidate)
    output = []; approvals = []
    for pid in pipe.ordered(candidates):
        options = sorted(candidates[pid], key=lambda c:(len(c['flags']), -len(c['patch']['notes'])))
        candidate = options[0]
        candidate['alternativeCount'] = len(options)-1
        candidate['candidateHash'] = digest(candidate)
        output.append(candidate)
        approvals.append(dict(id=pid, candidateHash=candidate['candidateHash'],
                              decision='pending', sourceUse='unconfirmed', reviewer='', explanation=''))
    missing_chars = sorted({c for x in output for c in pipe.poems[x['patch']['id']]['content']
                            if '\u4e00' <= c <= '\u9fff'} - set(pipe.dictionary))
    report = dict(toolVersion='1.0.0', productionChanged=False, scannedRecords=scanned,
        formalPending=len(pipe.pending), matched=len(output),
        structurallyClean=sum(not c['flags'] for c in output),
        unmatched=pipe.ordered(set(pipe.pending)-set(candidates)),
        missingCharacters=missing_chars, errors=errors, candidates=output)
    args.output.mkdir(parents=True, exist_ok=True)
    write_once(args.output/'candidates-v1.0.0.json', report)
    write_once(args.output/'reviews-template-v1.0.0.json', dict(poems=approvals, dictionary={}))
    print(json.dumps({k:v for k,v in report.items() if k not in ('candidates','unmatched','missingCharacters')},
                     ensure_ascii=False, indent=2))


def assemble(args):
    pipe = Pipeline(); packet = read(args.candidates); reviews = read(args.reviews)
    candidates = {c['patch']['id']: c for c in packet['candidates']}
    patches = []; provenance = []; seen = set()
    for review in reviews['poems']:
        if review.get('decision') != 'approved': continue
        pid = review['id']
        if pid in seen: raise ValueError('Duplicate approval: '+pid)
        seen.add(pid); c = candidates[pid]
        payload = {k:v for k,v in c.items() if k != 'candidateHash'}
        if digest(payload) != c['candidateHash'] or review.get('candidateHash') != c['candidateHash']:
            raise ValueError('Changed candidate: '+pid)
        if review.get('sourceUse') != 'approved' or not review.get('reviewer') or not review.get('explanation'):
            raise ValueError('Content/use review required: '+pid)
        if pid not in pipe.pending or pipe.input_hash(pipe.poems[pid]) != c['inputHash']:
            raise ValueError('Stale original: '+pid)
        if hashlib.sha256(Path(c['source']['file']).read_bytes()).hexdigest() != c['source']['sha256']:
            raise ValueError('Source changed: '+pid)
        selected_patch = dict(c['patch'])
        if 'tags' in review: selected_patch['tags'] = review['tags']
        if flags_for(selected_patch): raise ValueError('Unresolved structural errors: '+pid)
        validate_patch(selected_patch, pipe.poems[pid], pipe.tags[pipe.poems[pid]['category']])
        if any(n['term'] not in pipe.poems[pid]['content'] or not n['meaning'].strip()
               for n in selected_patch['notes']): raise ValueError('Invalid body note: '+pid)
        patches.append(selected_patch); provenance.append(dict(id=pid, source=c['source'], review=review))
    if not patches: raise ValueError('No reviewed candidates selected')
    needed = {c for p in patches for c in pipe.poems[p['id']]['content']
              if '\u4e00' <= c <= '\u9fff'} - set(pipe.dictionary)
    definitions = read(args.dictionary) if args.dictionary else {}
    additions = {}
    for ch in sorted(needed):
        entry = definitions.get(ch)
        if not isinstance(entry, dict) or set(entry) != {'meanings', 'ancient'}:
            raise ValueError('Missing definition: '+ch)
        if any(not isinstance(entry[k], list) for k in entry) or not entry['meanings'] or any(
                not isinstance(v, str) or not v.strip() for values in entry.values() for v in values):
            raise ValueError('Invalid definition: '+ch)
        approval = reviews.get('dictionary', {}).get(ch, {})
        if approval.get('decision') != 'approved' or not approval.get('reviewer') or approval.get('definitionHash') != digest(entry):
            raise ValueError('Dictionary review required: '+ch)
        additions[ch] = entry
    for name, value in [('dataVersion', args.data_version), ('dictionaryVersion', args.dictionary_version)]:
        if not re.fullmatch(r'\d+\.\d+\.\d+', value): raise ValueError('Invalid '+name)
    batch = dict(dataVersion=args.data_version, dictionaryVersion=args.dictionary_version,
        policy='Source-backed conversion; explicit content/use/dictionary reviews attached.',
        patches=patches, dictionaryAdditions=additions, conversionProvenance=provenance)
    write_once(args.output, batch, accept_identical=False)
    print(f'Prepared compatible batch: {len(patches)} poems; {len(additions)} characters. Production unchanged.')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    p = sub.add_parser('prepare')
    p.add_argument('--source', type=Path, action='append', required=True)
    p.add_argument('--output', type=Path, required=True); p.set_defaults(run=prepare)
    a = sub.add_parser('assemble')
    for key in ('candidates', 'reviews', 'output'): a.add_argument('--'+key, type=Path, required=True)
    a.add_argument('--dictionary', type=Path)
    a.add_argument('--data-version', required=True); a.add_argument('--dictionary-version', required=True)
    a.set_defaults(run=assemble)
    args = parser.parse_args(); args.run(args)


if __name__ == '__main__': main()
