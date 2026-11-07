"""Import a completed balanced batch, validate, then sync app assets. Roll back on error."""
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'expansion/python-packages'))
from pypinyin import pinyin, Style


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def dump(p, data):
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    batch = read(Path(sys.argv[1]))
    pp, dp = ROOT/'data/poems.json', ROOT/'data/dict.json'
    oldp, oldd = pp.read_bytes(), dp.read_bytes()
    poems, dictionary = read(pp), read(dp)
    ids = {p['id'] for p in poems['items']}
    incoming = batch['items']
    if all(p['id'] in ids for p in incoming):
        assert all(next(x for x in poems['items'] if x['id']==p['id'])==p for p in incoming)
        print('Identical batch already imported.')
        return
    assert not any(p['id'] in ids for p in incoming), 'ID collision'
    assert len({p['id'] for p in incoming}) == len(incoming), 'Duplicate batch ID'
    assert batch.get('provenance'), 'Source record required'
    chars = {c for p in incoming for c in p['content'] if '\u4e00' <= c <= '\u9fff'}
    definitions = batch.get('dictionaryAdditions', {})
    for ch in chars - dictionary['chars'].keys():
        assert ch in definitions, f'Missing edited dictionary definition: {ch}'
        dictionary['chars'][ch] = {
            'pinyin': sorted({p for group in pinyin(ch, heteronym=True, style=Style.TONE3) for p in group}),
            **definitions[ch],
        }
    for poem in incoming:
        for note in poem['notes']:
            term = note['term']
            if len(term)==2 and term in poem['content'] and term not in dictionary['words']:
                dictionary['words'][term] = note['meaning']
    poems['items'].extend(incoming)
    counts = Counter(p['category'] for p in poems['items'])
    assert len(counts)==4 and len(set(counts.values()))==1, 'Batch must keep category counts balanced'
    normalized = [re.sub(r'[^\u3400-\u9fff〇]', '', p['content']) for p in poems['items']]
    assert len(set(normalized)) == len(normalized), 'Duplicate original text'
    poems['dataVersion'] = batch['dataVersion']
    dictionary['dataVersion'] = batch.get('dictionaryVersion', dictionary['dataVersion'])
    try:
        dump(pp, poems)
        dump(dp, dictionary)
        subprocess.run([sys.executable, str(ROOT/'scripts/validate_data.py'),
                        '--expected-per-category', str(next(iter(counts.values())))], check=True)
    except BaseException:
        pp.write_bytes(oldp)
        dp.write_bytes(oldd)
        raise
    for name in ('poems.json', 'dict.json'):
        (ROOT/'app/assets/data'/name).write_bytes((ROOT/'data'/name).read_bytes())
    print(f'Imported {len(incoming)} edited entries; production now {len(poems["items"])}.')


if __name__ == '__main__':
    main()
