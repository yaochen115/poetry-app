"""Import the complete pinned guhanyu source offline, with reversible checkpoints."""
from collections import defaultdict
from pathlib import Path
import hashlib
import json
import re
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'expansion/python-packages'))
from opencc import OpenCC

SOURCE = ROOT / 'expansion/sources/guhanyu-v1.0.0'
PINYIN = re.compile(r'^[㈠-㈩⑴-⑽\d（）()]*\s*([a-züāáǎàēéěèīíǐìōóǒòūúǔùǖǘǚǜńňǹḿê]+)', re.I)
COMPOUND = re.compile(r'[【〖]([^】〗]+)[】〗]([^【〖]*)')


def encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    raw = (SOURCE / 'guhanyu.json').read_bytes()
    meta = json.loads((SOURCE / 'source-v1.0.0.json').read_text(encoding='utf-8'))
    assert hashlib.sha256(raw).hexdigest() == meta['sha256']
    rows = json.loads(raw.decode('utf-8-sig'))
    assert len(rows) == meta['sourceEntries']
    cc = OpenCC('t2s')
    chars = defaultdict(list)
    words = defaultdict(list)
    unmapped = []
    for index, row in enumerate(rows):
        assert len(row) >= 2 and all(isinstance(s, str) and s.strip() for s in row)
        head = row[0]
        if len(head) != 1:
            unmapped.append(dict(sourceIndex=index, originalEntry=row,
                                 reason='组合字形字头，Unicode对应尚待确认'))
            continue
        for key in dict.fromkeys((head, cc.convert(head))):
            assert len(key) == 1
            chars[key].append(index)
        for term, meaning in COMPOUND.findall('\n'.join(row[1:])):
            if len(term) < 2 or not meaning.strip() or not all('\u3400' <= ch <= '\u9fff' for ch in term):
                continue
            for key in dict.fromkeys((term, cc.convert(term))):
                words[key].append(dict(sourceIndex=index, originalTerm=term,
                                       definition=meaning.strip()))
    entries = {}
    for ch, indices in chars.items():
        readings = []
        definitions = []
        distinguish = len({rows[i][0] for i in indices}) > 1
        for i in indices:
            row = rows[i]
            for definition in row[1:]:
                match = PINYIN.match(definition.strip())
                if match and match[1] not in readings:
                    readings.append(match[1])
                # Preserve full source text, including readings and examples.
                definitions.append(f'【原字「{row[0]}」】{definition}' if distinguish else definition)
        assert readings and definitions
        entries[ch] = dict(pinyin=readings, meanings=[], ancient=definitions)
    doc = dict(dataVersion='1.1.27', chars=entries,
               words={k: '\n'.join(dict.fromkeys(v['definition'] for v in records))
                      for k, records in words.items()},
               source=meta, sourceEntries=rows, unmappedEntries=unmapped,
               charProvenance={ch: dict(sourceIndices=indices,
                                       simplifiedAlias=any(rows[i][0] != ch for i in indices))
                               for ch, indices in chars.items()},
               wordProvenance=dict(words))
    covered = {i for indices in chars.values() for i in indices}
    covered.update(r['sourceIndex'] for r in unmapped)
    assert covered == set(range(len(rows)))
    for i, row in enumerate(rows):
        if len(row[0]) == 1:
            assert all(any(text == value or text.endswith('】' + value)
                           for text in doc['chars'][row[0]]['ancient']) for value in row[1:])
    data_path = ROOT / 'data/dict.json'
    asset_path = ROOT / 'app/assets/data/dict.json'
    output = encoded(doc)
    if data_path.read_bytes() == output:
        assert asset_path.read_bytes() == output
        print('Identical full import already present.')
        return
    previous = json.loads(data_path.read_text(encoding='utf-8'))
    assert ((previous['dataVersion'] == '1.1.25' and not previous['chars'] and not previous['words'])
            or (previous['dataVersion'] == '1.1.26' and previous.get('source', {}).get('sha256') == meta['sha256'])), 'Expected approved empty database or initial source-only import'
    checkpoint = ROOT / f"expansion/checkpoints/pre-guhanyu-dict-v{previous['dataVersion']}-v1.0.0.zip"
    names = ['data/dict.json', 'app/assets/data/dict.json', 'data/poems.json',
             'app/assets/data/poems.json', 'app/lib/state.dart', 'app/test/widget_test.dart']
    originals = {name: (ROOT / name).read_bytes() for name in names}
    with zipfile.ZipFile(checkpoint, 'x', zipfile.ZIP_DEFLATED) as z:
        for name, content in originals.items():
            z.writestr(name, content)
    with zipfile.ZipFile(checkpoint) as z:
        assert z.testzip() is None
        for name, content in originals.items():
            assert z.read(name) == content
    poems = json.loads(originals['data/poems.json'])
    selected = set(poems['selectionProfile']['ids'])
    used = {ch for p in poems['items'] if p['id'] in selected for ch in p['content']
            if '\u3400' <= ch <= '\u9fff' or ch == '〇'}
    report = dict(version='1.0.0', dictionaryVersion=doc['dataVersion'],
                  sourceEntries=len(rows), indexedSourceRecords=len(rows)-len(unmapped),
                  lookupCharacters=len(entries), lookupCompounds=len(words),
                  unmapped=unmapped, fullSourcePreserved=True,
                  sourceSha256=meta['sha256'], dictionarySha256=hashlib.sha256(output).hexdigest(),
                  selectedUsedCharacters=len(used), coveredSelectedCharacters=len(used & entries.keys()),
                  missingSelectedCharacters=sorted(used - entries.keys()),
                  apkBuilt=False, nextApkRequiresExplicitApproval=True,
                  editorialReview='机械转换，未逐义语义精校；上游转载授权待确认')
    try:
        data_path.write_bytes(output)
        asset_path.write_bytes(output)
        assert data_path.read_bytes() == asset_path.read_bytes()
        with (ROOT / 'data/versions/dict-v1.1.27.json').open('xb') as f:
            f.write(output)
        with (ROOT / 'expansion/dictionary/guhanyu-import-dict-v1.1.27-v1.0.0.json').open('xb') as f:
            f.write(encoded(report))
    except BaseException:
        data_path.write_bytes(originals['data/dict.json'])
        asset_path.write_bytes(originals['app/assets/data/dict.json'])
        raise
    assert originals['data/poems.json'] == (ROOT / 'data/poems.json').read_bytes()
    assert originals['app/assets/data/poems.json'] == (ROOT / 'app/assets/data/poems.json').read_bytes()
    print(json.dumps({k: v for k, v in report.items() if k not in ('unmapped', 'missingSelectedCharacters')}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
