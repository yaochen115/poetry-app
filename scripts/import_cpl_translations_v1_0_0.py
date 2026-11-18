"""Import explicitly approved, unambiguous full-text CPL translation matches."""
from collections import Counter, defaultdict
from pathlib import Path
import hashlib
import json
import sys

from data_scope import active_items
from enrichment_pipeline import digest, write_once
from match_chinesepoetrylibrary_v1_0_0 import normal, clean_body, quality_flags, sha256
from translation_overlay_v1_0_0 import apply, overlay_for

ROOT = Path(__file__).resolve().parents[1]
CANDIDATES = ROOT / 'expansion/chinesepoetrylibrary-matching-v1.0.0/full-20261109T055401/candidates-v1.0.0.json'


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    paths = [ROOT / 'data/poems.json', ROOT / 'app/assets/data/poems.json']
    old = {p: p.read_bytes() for p in paths}
    assert old[paths[0]] == old[paths[1]]
    before = json.loads(old[paths[0]])
    by_id = {p['id']: p for p in active_items(before)}
    groups = defaultdict(list)
    source_data = json.loads(CANDIDATES.read_text(encoding='utf-8'))
    for match in source_data['matches']:
        if match['id'] in by_id and match['matchType'] == 'exact_author_body' and not match['flags']:
            groups[match['id']].append(match)
    conflicts = {pid for pid, matches in groups.items()
                 if len({m['translation'] for m in matches}) != 1}
    expected_ids = set(groups) - conflicts
    assert len(expected_ids) == 1770 and len(conflicts) == 3
    entries = []
    for pid in sorted(expected_ids):
        match = sorted(groups[pid], key=lambda m: (m['source']['file'], m['source']['row']))[0]
        poem = by_id[pid]
        source = dict(match['source'])
        assert match['baseContent'] == poem['content']
        assert normal(source['author']) == normal(poem['author'])
        body = normal(clean_body(source['content']))
        assert body == normal(clean_body(poem['content']))
        assert not quality_flags(match['translation'], body)
        source['cacheFile'] = source.pop('file')
        source.update(provider='byj233/ChinesePoetryLibrary', importedAt='2026-11-09',
                      matchingMethod='normalized_full_author_and_body',
                      reuseStatus='unconfirmed_source_reference')
        # The user approved translations. Notes remain staged for separate review.
        entries.append(dict(id=pid, baseAuthor=poem['author'], baseContent=poem['content'],
                            translation=match['translation'], notes=[], tags=[], source=source,
                            literaryApproved=False, userApprovedImport=True,
                            pending=['literaryReview', 'sourcePermissionReview', 'notesReview']))
    present = {pid for pid in expected_ids if overlay_for(before, by_id[pid])}
    if present == expected_ids:
        assert all(overlay_for(before, by_id[e['id']])['translation'] == e['translation'] for e in entries)
        print('All approved translations already present; no change.')
        return
    assert before['dataVersion'] == '1.2.35' and not before.get('translationImports')
    dictionary_hash = sha256(ROOT / 'data/dict.json')
    try:
        # The historical expansion auditor assumes the old, now-replaced baseline.
        # Validate the current approved scope here and run the current data validator.
        result = apply(entries, validation_scripts=[('validate_data.py', ['--original-only'])])
        after = json.loads(paths[0].read_text(encoding='utf-8'))
        assert after['dataVersion'] == '1.2.36'
        assert before['items'] == after['items']
        assert {k: v for k, v in before.items() if k not in ('dataVersion', 'translationImports')} == {
            k: v for k, v in after.items() if k not in ('dataVersion', 'translationImports')}
        assert set(after['translationImports']) == expected_ids
        for e in entries:
            actual = overlay_for(after, by_id[e['id']])
            assert actual == e and actual['translation'].strip()
        assert paths[0].read_bytes() == paths[1].read_bytes()
        assert sha256(ROOT / 'data/dict.json') == dictionary_hash
        assert sha256(ROOT / 'app/assets/data/dict.json') == dictionary_hash
        report = dict(version='1.0.0', dataVersion=after['dataVersion'], added=result['added'],
                      active=len(by_id), readableTranslations=len(expected_ids),
                      missingTranslations=len(by_id)-len(expected_ids), conflictsExcluded=sorted(conflicts),
                      candidateFile=CANDIDATES.relative_to(ROOT).as_posix(),
                      candidateSha256=sha256(CANDIDATES), dictionarySha256=dictionary_hash,
                      originalsSha256=digest(before['items']), sourceFilesChecked=len({e['source']['cacheFile'] for e in entries}),
                      byCategory=dict(Counter(by_id[e['id']]['category'] for e in entries)),
                      checkpoint=result['checkpoint'], userApprovedImport=True, literaryReviewed=False,
                      notesImported=False, apkBuilt=False, nextApkRequiresExplicitApproval=True)
        write_once(ROOT / 'data/versions/poems-v1.2.36.json', after, accept_identical=False)
        write_once(ROOT / 'expansion/translation-imports/cpl-approved-import-v1.0.0.json', report,
                   accept_identical=False)
    except BaseException:
        for p, content in old.items():
            p.write_bytes(content)
        raise
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
