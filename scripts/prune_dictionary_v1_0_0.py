"""Offline, lossless corpus dictionary pruning. Full source stays in project."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def digest(blob):
    return hashlib.sha256(blob).hexdigest()


def queryable(ch):
    n = ord(ch)
    return not (ch.isspace() or 0x3001 <= n <= 0x303F or
                0xFF00 <= n <= 0xFF0F or 0xFF1A <= n <= 0xFF1F or
                n in (0x2018, 0x2019, 0x201C, 0x201D, 0x2026, 0x2014, 0x2013, 0x27))


def save_new(path, blob):
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        assert path.read_bytes() == blob, f'Refusing to overwrite {path}'
    else:
        with path.open('xb') as f:
            f.write(blob)


def lookup(d, ch, prev, nxt):
    # Mirror AppState.lookup, including its original UTF-16 Han predicate.
    if not (0x4E00 <= ord(ch) <= 0x9FA5 or ch == '〇') and ch not in d['chars']:
        return ('punctuation', ch)
    for word in (prev + ch, ch + nxt):
        if word in d['words']:
            return ('word', word, d['words'][word])
    return ('char', ch, d['chars'].get(ch))


def main():
    full_path = ROOT / 'data/full-dictionaries/新华字典完整库-v1.1.28.json'
    if not full_path.exists():
        blob = (ROOT / 'data/dict.json').read_bytes()
        assert digest(blob) == '91f8960df4c97dba24a8778002c35a5b2451796237bf555e05b394ee4540f5ca'
        save_new(full_path, blob)
    blob = full_path.read_bytes()
    full = json.loads(blob)
    poems_blob = (ROOT / 'data/poems.json').read_bytes()
    poems = json.loads(poems_blob)
    selected = set(poems['selectionProfile']['ids'])
    disabled = {p['id'] for p in poems.get('disabledEntries', [])}
    active = [p for p in poems['items'] if p['id'] in selected - disabled]
    # PoemText flattens queryable cells ACROSS punctuation and line breaks.
    streams = [[ch for ch in p['content'] if queryable(ch)] for p in active]
    used = {ch for stream in streams for ch in stream}
    pairs = {a + b for stream in streams for a, b in zip(stream, stream[1:])}
    # A singleton can be queried at stream boundaries too, if present in words.
    word_keys = pairs | used
    chars = {k: v for k, v in full['chars'].items() if k in used}
    words = {k: v for k, v in full['words'].items() if k in word_keys}
    provenance = {k: v for k, v in full['charProvenance'].items() if k in chars}
    covered = {i for v in provenance.values() for i in v['sourceIndices']}
    reduced = dict(dataVersion='1.1.29', chars=chars, words=words,
                   source=full['source'], charProvenance=provenance,
                   sourceRecordCoverage={'characters': len(covered), 'words': len(words)},
                   pruning={'version': '1.0.0', 'scope': 'active_poem_queryable_cells',
                            'fullDictionary': full_path.relative_to(ROOT).as_posix(),
                            'fullDictionarySha256': digest(blob),
                            'poemsSha256': digest(poems_blob),
                            'fullCharacters': len(full['chars']), 'fullWords': len(full['words']),
                            'activePoems': len(active),
                            'policy': 'Preserve definitions and all actual word-first lookup results; retain full source outside app assets.'})
    checks = 0
    for stream in streams:
        for i, ch in enumerate(stream):
            prev = stream[i - 1] if i else ''
            nxt = stream[i + 1] if i + 1 < len(stream) else ''
            assert lookup(full, ch, prev, nxt) == lookup(reduced, ch, prev, nxt)
            checks += 1
    output = (json.dumps(reduced, ensure_ascii=False, indent=2) + '\n').encode()
    save_new(ROOT / 'data/versions/dict-v1.1.29.json', output)
    for rel in ('data/dict.json', 'app/assets/data/dict.json'):
        (ROOT / rel).write_bytes(output)
    report = {'version': '1.0.0', 'originalBytes': len(blob), 'prunedBytes': len(output),
              'fullDictionary': str(full_path.relative_to(ROOT)), 'fullSha256': digest(blob),
              'prunedSha256': digest(output), 'characters': len(chars), 'words': len(words),
              'removedCharacters': len(full['chars']) - len(chars),
              'removedWords': len(full['words']) - len(words),
              'activePoems': len(active), 'lookupEquivalenceChecks': checks,
              'allLookupsIdentical': True, 'poemsUnchanged': digest(poems_blob) == digest((ROOT / 'data/poems.json').read_bytes())}
    save_new(ROOT / 'expansion/dictionary/pruning-v1.0.0.json',
             (json.dumps(report, ensure_ascii=False, indent=2) + '\n').encode())
    print(json.dumps(report, ensure_ascii=True))


if __name__ == '__main__':
    main()
