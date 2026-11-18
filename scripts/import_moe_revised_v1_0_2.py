"""Import pinned MOE dictionary JSON; retain source wording and full downloads.

Run offline after obtaining the pinned dict-revised.json.xz and README.md.
Lookup aliases change keys only, never definitions or quotations.
"""
import collections
import hashlib
import json
import lzma
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'expansion/python-packages'))
from opencc import OpenCC
from prune_dictionary_v1_0_0 import queryable, save_new

SOURCE = ROOT / 'expansion/sources/moe-revised-v1.0.0'
COMMIT = 'a6dc997417507eb510fc29822bc514de2c92728c'
GIT_BLOB = '4f457b60ff75dc8813ce87d68ee41fbc49f21b4a'
ATTRIBUTION = ('資料來源：教育部《重編國語辭典修訂本》（萌典 JSON 整理版）。'
               'CC BY-ND 3.0 TW；釋義與例證保留原文，僅轉換資料格式並建立查詢索引。'
               '\nhttps://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/index.html'
               '\nhttps://creativecommons.org/licenses/by-nd/3.0/tw/')


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode()


def sha(blob):
    return hashlib.sha256(blob).hexdigest()


def render(row):
    """Only add layout labels; every supplied field value remains verbatim."""
    blocks, readings = [], []
    for h in row.get('heteronyms', []):
        reading = h.get('pinyin') or h.get('bopomofo')
        if reading:
            readings.append(reading)
        lines = [f'【原詞頭】{row["title"]}']
        if h.get('pinyin'):
            lines.append('【漢語拼音】' + h['pinyin'])
        if h.get('bopomofo'):
            lines.append('【注音】' + h['bopomofo'])
        for i, definition in enumerate(h.get('definitions', []), 1):
            lines.append(f'〔{i}〕')
            for key, label in [('type', '詞性'), ('def', '釋義'), ('quote', '書證'),
                               ('example', '例句'), ('link', '參照'),
                               ('synonyms', '近義詞'), ('antonyms', '反義詞')]:
                value = definition.get(key)
                if value:
                    lines.append('【' + label + '】')
                    lines.extend(value if isinstance(value, list) else [value])
        if h.get('definitions'):
            blocks.append('\n'.join(lines))
    return list(dict.fromkeys(readings)), blocks


def main():
    blob = (SOURCE / 'dict-revised.json.xz').read_bytes()
    assert hashlib.sha1(b'blob ' + str(len(blob)).encode() + b'\0' + blob).hexdigest() == GIT_BLOB
    assert json.loads((SOURCE / 'commit.json').read_text(encoding='utf-8-sig'))['sha'] == COMMIT
    decompressed = lzma.decompress(blob)
    rows = json.loads(decompressed)
    assert len(rows) == 161194
    save_new(SOURCE / 'dict-revised-full-v20260711.json', decompressed)
    meta = dict(datasetId='moe-revised', name='教育部《重編國語辭典修訂本》',
                repository='https://github.com/g0v/moedict-data', commit=COMMIT,
                downloadedFrom=f'https://raw.githubusercontent.com/g0v/moedict-data/{COMMIT}/dict-revised.json.xz',
                officialDownload='https://language.moe.gov.tw/001/Upload/Files/site_content/M0001/respub/dict_reviseddict_download.html',
                downloadedAt='2026-11-09', sourceEdition='README：民國110年11月網路第六版；倉庫提交2026-07-11',
                note='官網域名在本機無法解析，使用固定萌典整理版；不宣稱等同官網20260929更新包。',
                sha256=sha(blob), gitBlobSha1=GIT_BLOB, jsonSha256=sha(decompressed),
                records=len(rows), license='CC BY-ND 3.0 TW', attribution=ATTRIBUTION,
                licenseUrl='https://creativecommons.org/licenses/by-nd/3.0/tw/',
                readmeSha256=sha((SOURCE / 'README.md').read_bytes()))
    save_new(SOURCE / 'source-v1.0.0.json', encode(meta))
    save_new(SOURCE / '来源及使用说明-v1.0.0.md',
             ('# 教育部辭典來源\n\n' + ATTRIBUTION + '\n\n' + meta['note'] +
              '\n\n完整原始JSON、壓縮包與來源README均保留；簡繁轉換只用於查詢鍵，釋義不轉換。'
              '本次未下載字圖，含缺字佔位碼的條目保留於原始庫，暫不自動作為正常詞頭匹配。\n').encode())
    cc = OpenCC('t2s')
    traditional = OpenCC('s2t')
    taiwan = OpenCC('s2tw')
    index = collections.defaultdict(list)
    excluded = []
    for i, row in enumerate(rows):
        title = row['title']
        if '{[' in title or not row.get('heteronyms'):
            excluded.append({'sourceIndex': i, 'title': title, 'reason': '字圖佔位詞頭或空音義'})
            continue
        for key in dict.fromkeys([title, cc.convert(title)]):
            index[key].append(i)
    poems_blob = (ROOT / 'data/poems.json').read_bytes()
    poems = json.loads(poems_blob)
    selected = set(poems['selectionProfile']['ids'])
    disabled = {p['id'] for p in poems.get('disabledEntries', [])}
    active = [p for p in poems['items'] if p['id'] in selected - disabled]
    streams = [[ch for ch in p['content'] if queryable(ch)] for p in active]
    used = {ch for stream in streams for ch in stream}
    pairs = {a+b for stream in streams for a,b in zip(stream, stream[1:])}
    chars, words, provenance, word_provenance = {}, {}, {}, {}
    for key in sorted(used | pairs):
        ids = index.get(key, [])
        if not ids:
            # Handle alternate simplified spellings such as 钜/馀/着.
            # Only add aliases when the literal query has no source entry.
            ids = list(dict.fromkeys(index.get(traditional.convert(key), []) + index.get(taiwan.convert(key), []) + index.get(cc.convert(key), [])))
        if not ids:
            continue
        # Literal heads come before simplified aliases. Preserve all distinct
        # readings/definitions and identify original head to expose collisions.
        ids = sorted(ids, key=lambda i: (rows[i]['title'] != key, i))
        readings, meanings = [], []
        for i in ids:
            py, defs = render(rows[i])
            readings.extend(py)
            meanings.extend(defs)
        readings = list(dict.fromkeys(readings))
        if not meanings:
            continue
        detail = {'sourceIndices': ids, 'originalHeads': [rows[i]['title'] for i in ids],
                  'missingSourceReading': not readings}
        if len(key) == 1:
            chars[key] = dict(pinyin=readings, meanings=meanings, ancient=[])
            provenance[key] = detail
        else:
            words[key] = '\n\n'.join(meanings)
            word_provenance[key] = detail
    dictionary = dict(dataVersion='1.1.32', chars=chars, words=words, source=meta,
                      attribution=ATTRIBUTION, charProvenance=provenance,
                      wordProvenance=word_provenance,
                      pruning=dict(scope='active_poem_queryable_cells', activePoems=len(active),
                                   poemsSha256=sha(poems_blob), fullSource=(SOURCE / 'dict-revised-full-v20260711.json').relative_to(ROOT).as_posix(),
                                   policy='Exact original heads and OpenCC t2s/s2t/s2tw lookup aliases (fallback only when literal head absent); full original wording preserved; no Xinhua fallback.'))
    # Verify every original source string survives the presentation conversion.
    checks = 0
    for table, prov in [(chars, provenance), (words, word_provenance)]:
        for key, info in prov.items():
            display = '\n'.join(table[key]['meanings']) if table is chars else table[key]
            for i in info['sourceIndices']:
                for h in rows[i]['heteronyms']:
                    for d in h.get('definitions', []):
                        for value in d.values():
                            for s in value if isinstance(value, list) else [value]:
                                if s:
                                    assert s in display, (key, i, s)
                                    checks += 1
    previous_blob = (ROOT / 'data/dict.json').read_bytes()
    assert json.loads(previous_blob)['dataVersion'] in ('1.1.29', '1.1.30', '1.1.31', '1.1.32')
    assert (ROOT / 'app/assets/data/dict.json').read_bytes() == previous_blob
    previous = json.loads((ROOT / 'data/versions/dict-v1.1.29.json').read_bytes())
    assert previous['dataVersion'] == '1.1.29', 'Use a new version for a later corpus/import.'
    han = {ch for p in active for ch in p['content'] if re.fullmatch(r'[\u3400-\u9fff〇]', ch)}
    missing = sorted(han - chars.keys())
    old_missing = han - previous['chars'].keys()
    per_poem = []
    for p in active:
        needed = {ch for ch in p['content'] if ch in han}
        per_poem.append({'id': p['id'], 'title': p['title'], 'missingCharacters': sorted(needed-chars.keys())})
    report = dict(version='1.0.2', dictionaryVersion='1.1.32', source=meta,
                  sourceRecords=len(rows), sourceSingleCharacterRows=sum(len(r['title'])==1 for r in rows),
                  excludedHeads=excluded, characterLookupKeys=len(chars), wordLookupKeys=len(words),
                  activePoems=len(active), uniqueHanCharacters=len(han), coveredHanCharacters=len(han & chars.keys()),
                  missingCharacters=missing, previousMissingCharacters=sorted(old_missing),
                  newlyCovered=sorted(old_missing & chars.keys()), lostCoverage=sorted((han & previous['chars'].keys())-chars.keys()),
                  fullyCoveredPoems=sum(not p['missingCharacters'] for p in per_poem),
                  sourceStringsVerified=checks, missingSourceReadings=[k for k,v in chars.items() if not v['pinyin']],
                  aliasCollisions={k:v['originalHeads'] for k,v in provenance.items() if len(v['sourceIndices'])>1},
                  perPoem=per_poem, poemsSha256=sha(poems_blob), dictionarySha256=sha(encode(dictionary)),
                  previousDictionarySha256=sha((ROOT / 'data/versions/dict-v1.1.29.json').read_bytes()), apkBuilt=False)
    output = encode(dictionary)
    save_new(ROOT / 'data/versions/dict-v1.1.32.json', output)
    save_new(ROOT / 'expansion/dictionary/moe-revised-match-v1.0.2.json', encode(report))
    assert (ROOT / 'data/poems.json').read_bytes() == poems_blob
    assert (ROOT / 'app/assets/data/poems.json').read_bytes() == poems_blob
    try:
        (ROOT / 'data/dict.json').write_bytes(output)
        (ROOT / 'app/assets/data/dict.json').write_bytes(output)
        assert (ROOT / 'data/dict.json').read_bytes() == (ROOT / 'app/assets/data/dict.json').read_bytes()
    except BaseException:
        for path in ['data/dict.json', 'app/assets/data/dict.json']:
            (ROOT / path).write_bytes(previous_blob)
        raise
    print(json.dumps({k:v for k,v in report.items() if k in
                     ['dictionaryVersion','sourceRecords','characterLookupKeys','wordLookupKeys','activePoems',
                      'uniqueHanCharacters','coveredHanCharacters','fullyCoveredPoems','sourceStringsVerified']}, ensure_ascii=True))
    print(json.dumps({'missing':len(missing),'previousMissing':len(old_missing),
                      'newlyCovered':len(report['newlyCovered']),'lostCoverage':len(report['lostCoverage']),
                      'missingReadings':len(report['missingSourceReadings']), 'bytes':len(output)},ensure_ascii=True))


if __name__ == '__main__':
    main()
