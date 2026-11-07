"""Build source-first editorial packets. Never writes production or approvals.

Run again safely after enrichment: immutable packets retain hashes, while each
queue snapshot is content-addressed. Reference text remains editorial material.
"""
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
from enrichment_pipeline import Pipeline, digest, read, write_once


def extract_notes(text, content):
    """Conservative line parser; unparsed material is retained in the source packet."""
    candidates = []
    for line in text.splitlines():
        match = re.match(r'^\s*(?:[①-⑳]|\d+[.、．)])?\s*([^：:]{1,30})[：:]\s*(.+)$', line)
        if not match:
            continue
        term, meaning = match.groups()
        term = re.sub(r'[（(][^()（）]*[)）]', '', term).strip('《》“”「」 \t')
        # Exact source glyphs required; title-only terms are not body notes.
        if term and term in content and not any(n['term'] == term for n in candidates):
            candidates.append(dict(term=term, meaning=meaning.strip()))
    return candidates


def flags_for(ref, poem, notes):
    flags = list(ref.get('flags', []))
    text = ref.get('translationReference', '').strip()
    if re.match(r'^(?:译文\s*)?(?:注释|注解|词句注释)', text):
        flags.append('annotation_in_translation_field')
    if ref.get('sourceAuthor', '').strip() != poem['author'].strip():
        flags.append('author_requires_comparison')
    if len(notes) < 3:
        flags.append('fewer_than_three_parsed_body_notes')
    if not text or any(s in text for s in ('译文略', '暂无翻译', '待翻译')):
        flags.append('translation_missing_or_placeholder')
    return sorted(set(flags))


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    pipe = Pipeline()
    base = pipe.work/'reference-review-v1.0.0'
    source_hashes = {}
    choices = {}
    rejected = []
    for path in sorted((pipe.work/'references').glob('*.json')):
        packet = read(path)
        pid = packet['id']
        if pid not in pipe.pending:
            continue
        poem = pipe.poems[pid]
        if packet.get('inputHash') != pipe.input_hash(poem):
            rejected.append(dict(file=pipe.relative(path), reason='stale_input_hash'))
            continue
        for ref in packet['references']:
            source = (pipe.root/ref['file']).resolve()
            if not source.is_relative_to((pipe.root/'expansion/sources').resolve()):
                raise ValueError('Source outside project reference directory')
            if source not in source_hashes:
                source_hashes[source] = hashlib.sha256(source.read_bytes()).hexdigest()
            if source_hashes[source] != ref['sourceSha256']:
                rejected.append(dict(file=pipe.relative(path), reason='source_hash_changed'))
                continue
            notes = extract_notes(ref.get('notesReference', ''), poem['content'])
            flags = flags_for(ref, poem, notes)
            record = dict(id=pid, inputHash=packet['inputHash'], original=pipe.source(poem),
                tagEnum=pipe.tags[poem['category']], reference=ref,
                bodyNoteCandidates=notes, flags=flags,
                reuseStatus='permission_not_established_reference_only',
                editorialStatus='reference_ready_requires_semantic_review',
                instructions=['核对逐句覆盖、人物关系、时态、古义和注音。',
                    '来源现代译注未确认复用许可，不直接作为正式发布译注。',
                    '保留来源和原文；独立编辑后走现有结果哈希/审核/字典/批次入库流程。'])
            target = base/'packets'/f'{pid}--{digest(record)}.json'
            write_once(target, record)
            rank = (len(flags), -len(notes), pipe.relative(target))
            previous = choices.get(pid)
            if previous is None or rank < previous[0]:
                choices[pid] = (rank, dict(id=pid, category=poem['category'],
                    title=poem['title'], author=poem['author'],
                    packet=pipe.relative(target), flags=flags, parsedNotes=len(notes)))
    ordered = sorted((v[1] for v in choices.values()),
                     key=lambda r:(len(r['flags']), pipe.category_order[r['category']],
                                   int(r['id'].split('-')[1])))
    missing = [dict(id=pid,title=pipe.poems[pid]['title'],author=pipe.poems[pid]['author'],
                    category=pipe.poems[pid]['category'],
                    action='定向查找允许访问的来源；记录出处、版本及复用条件。')
               for pid in pipe.ordered(set(pipe.pending)-set(choices))]
    queue = dict(toolVersion='1.0.0', formalPending=len(pipe.pending),
                 matched=len(ordered), byCategory=dict(Counter(x['category'] for x in ordered)),
                 cleanStructuralCandidates=sum(not x['flags'] for x in ordered),
                 flaggedCandidates=sum(bool(x['flags']) for x in ordered),
                 sourceFilesVerified=len(source_hashes), rejected=rejected,
                 referenceReviewQueue=ordered, onlineLookupQueue=missing,
                 productionChanged=False, automaticApprovals=0,
                 scope='结构筛选通过不等于译注正确、可直接复制或可发布。')
    target = base/f'queue-v1.0.0--{digest(queue)}.json'
    write_once(target, queue)
    print(json.dumps({k:v for k,v in queue.items() if k not in
                     ('referenceReviewQueue','onlineLookupQueue')},ensure_ascii=False,indent=2))
    print('Queue: '+pipe.relative(target))


if __name__ == '__main__': main()
