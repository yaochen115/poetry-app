"""Audit actual imported data against baseline, batches, cached sources and assets."""
import hashlib
import html
import json
import re
import sys
import urllib.parse
from collections import Counter
from pathlib import Path
from data_scope import active_items, disabled_ids

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'expansion'


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def normalize(text):
    text = re.sub(r'[(（][^)）]*[)）]', '', text)
    return re.sub(r'[^\u3400-\u9fff〇]', '', text)


def main():
    document = read(ROOT / 'data/poems.json')
    poems = document['items']
    active = active_items(document)
    disabled = disabled_ids(document)
    baseline = read(WORK / 'baseline/poems.json')['items']
    by_id = {p['id']: p for p in poems}
    require(len(by_id) == len(poems), 'Duplicate production IDs')
    require(all(by_id.get(p['id']) == p for p in baseline), 'Original baseline changed')
    for name in ('poems.json', 'dict.json'):
        require((ROOT / 'data' / name).read_bytes() ==
                (ROOT / 'app/assets/data' / name).read_bytes(), f'Asset mismatch: {name}')
    tracked = {p['id'] for p in baseline}
    local_verified, external_verified = set(), set()
    batches = sorted((WORK / 'batches').glob('*.json'))
    for fp in batches:
        batch = read(fp)
        items = {p['id']: p for p in batch['items']}
        require(not tracked.intersection(items), f'ID reused in batch {fp.name}')
        require(all(by_id.get(iid) == p for iid, p in items.items()), f'Batch mismatch: {fp.name}')
        tracked.update(items)
        provenance = batch['provenance']
        sources = provenance.get('sources', [])
        if 'sourceRowsZeroBased' in provenance:
            sources = [dict(repository=provenance['originalRepository'],
                            file=provenance['originalFile'],
                            rowsZeroBased=provenance['sourceRowsZeroBased'])]
        covered = set()
        for src in sources:
            if 'file' not in src:
                require(src.get('url', '').startswith('https://'), 'External source URL missing')
                external_verified.update(src['ids'])
                covered.update(src['ids'])
                continue
            path = WORK / 'sources' / src['repository'].split('/')[-1] / src['file']
            if 'locations' in src:
                try:
                    data = read(path)
                except json.JSONDecodeError:
                    data = [json.loads(line) for line in path.read_text(encoding='utf-8').splitlines() if line.strip()]
                for iid, location in src['locations'].items():
                    if isinstance(location, dict):
                        if 'row' in location:
                            row=data[location['row']]
                            text=row.get('content',row.get('paragraphs'))
                            if isinstance(text,list):text='\n'.join(text)
                            if location.get('textTransform')=='opencc-t2s':
                                sys.path.insert(0,str(WORK/'python-packages'))
                                from opencc import OpenCC
                                text=OpenCC('t2s').convert(text)
                            else:
                                require(not location.get('textTransform'),'Unknown source transform')
                        elif 'book' in location:
                            book = next(b for books in data.values() for b in books if b['nameStr'] == location['book'])
                            text = book['book']['tb_bookviews']['bookviews'][location['view']]['content']['tb_bookview']['cont']
                            text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1],16)), text)
                            text = text.replace(r'\r\n', '\n')
                            text = html.unescape(re.sub(r'<[^>]*>', '', text))
                        else:
                            text = data[location['chapter']]['paragraphs'][location['paragraph']]
                    else:
                        row = data[location]
                        text = row.get('content', row.get('paragraphs'))
                        if isinstance(text, list):
                            text = '\n'.join(text)
                    require(normalize(items[iid]['content']) in normalize(text),
                            f'Original differs from source: {iid}')
                    local_verified.add(iid)
                    covered.add(iid)
                continue
            is_yuan = src['file'].endswith('yuanqu.json')
            data = read(path) if is_yuan else path.read_text(encoding='utf-8').splitlines()
            pairs = ({iid: src['rowZeroBased'] for iid in src['ids']}
                     if is_yuan else src['rowsZeroBased'])
            for iid, index in pairs.items():
                row = data[index] if is_yuan else json.loads(data[index])
                text = '\n'.join(row['paragraphs']) if is_yuan else row['content']
                require(normalize(items[iid]['content']) in normalize(text),
                        f'Original differs from source: {iid}')
                local_verified.add(iid)
                covered.add(iid)
        require(covered == set(items), f'Incomplete source tracking: {fp.name}')
    for entry in document.get('poetryApiBindings', {}).values():
        iid = entry['appId']
        require(iid in by_id, 'Unknown API import ID')
        source = entry['source']
        path = (ROOT/source['cacheFile']).resolve()
        require(path.is_relative_to((WORK/'poetry-2000-v1.0.0/provider-api/cache').resolve()), 'Invalid API cache path')
        require(hashlib.sha256(path.read_bytes()).hexdigest() == source['sha256'], 'API source hash changed')
        from convert_downloaded_materials_v1_0_0 import normal
        from prepare_poetry_catalog_v1_0_2 import clean_body
        rows = [r for r in read(path)['data'] if r.get('id') == source['providerId']]
        require(len(rows) == 1, 'API identity not unique in source response')
        row = rows[0]
        require(normal(row['author']['name']) == normal(by_id[iid]['author']), 'API author differs')
        require(normal('\n'.join(row['content'])) == normal(clean_body(by_id[iid]['content'])), 'API full text differs')
        tracked.add(iid)
        local_verified.add(iid)
    require(tracked == set(by_id), 'Untracked production additions')
    originals = [normalize(p['content']) for p in poems]
    require(len(set(originals)) == len(originals), 'Duplicate normalized original')
    dictionary = read(ROOT / 'data/dict.json')
    old_dict = read(WORK / 'baseline/dict.json')
    require(all(dictionary['chars'].get(ch) == entry for ch, entry in old_dict['chars'].items()),
            'Baseline character dictionary changed')
    require(all(dictionary['words'].get(word) == entry for word, entry in old_dict['words'].items()),
            'Baseline word dictionary changed')
    for ch in dictionary['chars'].keys() - old_dict['chars'].keys():
        entry = dictionary['chars'][ch]
        require(all(re.fullmatch(r'[a-züv]+[1-5]?', p) for p in entry['pinyin']), f'Invalid pinyin: {ch}')
        require(bool(entry['meanings'] or entry['ancient']), f'Empty meaning: {ch}')
    combined = read(WORK / 'sources/manifest.json') + read(WORK / 'sources/expansion-manifest.json')
    extra_manifest=WORK/'sources/additional-originals-manifest.json'
    if extra_manifest.exists():
        combined += read(extra_manifest)
    manifest = list({(item['repo'], item['path']): item for item in combined}.values())
    for item in manifest:
        path = WORK / 'sources' / item['repo'].split('/')[-1] / item['path']
        require(hashlib.sha256(path.read_bytes()).hexdigest() == item['sha256'],
                f'Source hash changed: {item["path"]}')
    prose_manifest = read(WORK/'sources/poems-db-originals-manifest.json')
    prose_path = urllib.parse.unquote(prose_manifest['url'].split('/master/')[1])
    require(hashlib.sha256((WORK/'sources/poems-db'/prose_path).read_bytes()).hexdigest() == prose_manifest['sha256'],
            'Prose source hash changed')
    original_only = [p for p in active if p.get('editorialStatus') == 'original_only']
    complete = [p for p in active if p.get('editorialStatus') != 'original_only']
    from translation_overlay_v1_0_0 import overlay_for
    supplements=document.get('translationImports',{})
    for pid, entry in supplements.items():
        require(pid in {p['id'] for p in active}, 'Unselected translation import')
        require(overlay_for(document,by_id[pid]) is not None,'Stale translation import')
        source=entry['source'];path=(ROOT/source['cacheFile']).resolve()
        require(path.is_relative_to((ROOT/'expansion').resolve()),'Invalid import source path')
        require(hashlib.sha256(path.read_bytes()).hexdigest()==source['sha256'],'Imported translation source changed')
    report = dict(
        productionTotal=len(active),storedTotal=len(poems),disabledCount=len(disabled),
        disabledIds=sorted(disabled),perCategory=dict(Counter(p['category'] for p in active)),
        baselinePreserved=len(baseline), addedOriginals=len(active)-len(baseline),
        completedAdditions=len(complete)-len(baseline),
        completeWithTranslation=len(complete), originalOnlyPendingEnrichment=len(original_only),
        partialImportedTranslations=sum(bool(overlay_for(document,p)) and not p.get('translation','').strip() for p in active),
        availableTranslations=sum(bool(p.get('translation','').strip()) or bool(overlay_for(document,p)) for p in active),
        targetTotal=sum(document.get('selectionProfile',{}).get('expectedCounts',dict.fromkeys(('唐诗','宋词','元曲','古文'),1050)).values()),
        remainingTo4200=None if document.get('selectionProfile') else 4200-len(active), dictionaryCharacters=len(dictionary['chars']),
        dictionaryWords=len(dictionary['words']), importedBatches=len(batches),
        cachedSourceTextMatches=len(local_verified),
        externalSourceReviewedSeparately=sorted(external_verified),
        assetCopiesIdentical=True, normalizedOriginalDuplicates=0,
        sourceFilesHashChecked=len(manifest)+1,
        sourceGlyphIssuesPending=sum(any(0xe000<=ord(c)<=0xf8ff for c in p['content']) for p in poems),
        activeSourceGlyphIssues=sum(any(0xe000<=ord(c)<=0xf8ff for c in p['content']) for p in active),
        scope='Structural and source-text audit of stored originals and current selected library; does not prove translation accuracy or final completion.',
    )
    (WORK / 'audit-report.json').write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
