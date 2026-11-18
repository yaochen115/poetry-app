"""Replace the approved guhanyu dictionary with the pinned Xinhua corpus."""
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


def encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2) + '\n').encode('utf-8')


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    folder = ROOT / 'expansion/sources/chinese-xinhua-v1.0.0'
    meta = json.loads((folder / 'source-v1.0.0.json').read_text(encoding='utf-8'))
    for name, record in meta['files'].items():
        assert hashlib.sha256((folder / name).read_bytes()).hexdigest() == record['sha256']
    rows = json.loads((folder / 'word.json').read_text(encoding='utf-8-sig'))
    terms = json.loads((folder / 'ci.json').read_text(encoding='utf-8-sig'))
    cc_simple, cc_traditional = OpenCC('t2s'), OpenCC('s2t')
    groups = defaultdict(list)
    corrections = []
    for index, row in enumerate(rows):
        head = row['word']
        if re.fullmatch(r'[\u3400-\u9fff][A-Za-z]+', head):
            corrections.append(dict(sourceIndex=index, originalHead=head, lookupHead=head[0]))
            head = head[0]
        assert len(head) == 1 and row['pinyin'].strip()
        keys = [head]
        old = row.get('oldword', '')
        if len(old) == 1:
            keys.append(old)
        for key in list(keys):
            keys.extend((cc_simple.convert(key), cc_traditional.convert(key)))
        for key in dict.fromkeys(keys):
            assert len(key) == 1
            groups[key].append(index)
    chars = {}
    for key, indices in groups.items():
        readings = list(dict.fromkeys(rows[i]['pinyin'].strip() for i in indices))
        definitions = []
        for i in indices:
            for field in ('explanation', 'more'):
                text = rows[i].get(field, '').strip()
                if text and text not in definitions:
                    definitions.append(text)
        assert definitions
        chars[key] = dict(pinyin=readings, meanings=definitions, ancient=[])
    word_groups = defaultdict(list)
    excluded = []
    for index, row in enumerate(terms):
        term, definition = row['ci'].strip(), row['explanation'].strip()
        if not term or not definition:
            excluded.append(dict(sourceIndex=index, term=term, reason='空词头或空释义'))
            continue
        if definition not in word_groups[term]:
            word_groups[term].append(definition)
    dictionary = dict(dataVersion='1.1.28', chars=chars,
                      words={key: '\n'.join(values) for key, values in word_groups.items()},
                      source=meta,
                      charProvenance={key: dict(sourceIndices=indices) for key, indices in groups.items()},
                      sourceRecordCoverage=dict(characters=len(rows), words=len(terms),
                                                excludedWords=excluded, correctedHeads=corrections))
    output = encode(dictionary)
    data = ROOT / 'data/dict.json'
    asset = ROOT / 'app/assets/data/dict.json'
    if data.read_bytes() == output:
        assert asset.read_bytes() == output
        print('Identical import already present.')
        return
    previous = json.loads(data.read_text(encoding='utf-8'))
    assert previous['dataVersion'] == '1.1.27'
    backup = ROOT / 'backups/替换古汉语字典前-v1.0.0-2026-11-09'
    backup.mkdir(parents=True, exist_ok=False)
    names = ['data/dict.json', 'app/assets/data/dict.json', 'app/test/guhanyu_test.dart',
             'app/lib/widgets/dict_sheet.dart', 'data/poems.json', 'app/assets/data/poems.json']
    originals = {name: (ROOT / name).read_bytes() for name in names}
    old_source = ROOT / 'expansion/sources/guhanyu-v1.0.0'
    for path in old_source.iterdir():
        assert path.is_file()
        originals[path.relative_to(ROOT).as_posix()] = path.read_bytes()
    archive = backup / '原字典及来源-v1.0.0.zip'
    with zipfile.ZipFile(archive, 'x', zipfile.ZIP_DEFLATED) as z:
        for name, raw in originals.items():
            z.writestr(name, raw)
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        for name, raw in originals.items():
            assert z.read(name) == raw
    poems = json.loads(originals['data/poems.json'])
    selected = set(poems['selectionProfile']['ids'])
    used = set()
    adjacent = set()
    for row in poems['items']:
        if row['id'] not in selected:
            continue
        for run in re.findall(r'[\u3400-\u9fff〇]+', row['content']):
            used.update(run)
            adjacent.update(run[i:i+2] for i in range(len(run)-1))
    report = dict(version='1.0.0', dictionaryVersion='1.1.28',
                  sourceCharacters=len(rows), sourceWords=len(terms),
                  uniqueOriginalCharacterHeads=len({r['word'] for r in rows}),
                  characterLookupKeys=len(chars), wordLookupKeys=len(word_groups),
                  excludedWords=excluded, correctedHeads=corrections,
                  selectedCharacters=len(used), coveredCharacters=len(used & chars.keys()),
                  missingCharacters=sorted(used-chars.keys()),
                  matchedAdjacentWords=sorted(adjacent & word_groups.keys()),
                  replacedRepository=previous['source']['repository'],
                  source=meta, backup=backup.relative_to(ROOT).as_posix(),
                  backupSha256=hashlib.sha256(archive.read_bytes()).hexdigest(),
                  apkBuilt=False, nextApkRequiresExplicitApproval=True)
    try:
        data.write_bytes(output)
        asset.write_bytes(output)
        assert data.read_bytes() == asset.read_bytes()
        with (ROOT / 'data/versions/dict-v1.1.28.json').open('xb') as f:
            f.write(output)
        with (ROOT / 'expansion/dictionary/xinhua-import-v1.0.0.json').open('xb') as f:
            f.write(encode(report))
    except BaseException:
        data.write_bytes(originals['data/dict.json'])
        asset.write_bytes(originals['app/assets/data/dict.json'])
        raise
    assert (ROOT / 'data/poems.json').read_bytes() == originals['data/poems.json']
    print(json.dumps({k: v for k, v in report.items() if k not in
                     ('source', 'matchedAdjacentWords', 'excludedWords', 'missingCharacters')}, ensure_ascii=False, indent=2))
    print('Missing characters:', len(report['missingCharacters']))
    print('Matched adjacent words:', len(report['matchedAdjacentWords']))


if __name__ == '__main__':
    main()
