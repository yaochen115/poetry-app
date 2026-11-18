"""Download pinned text volumes and stage translation matches. Never imports data."""
import argparse
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from difflib import SequenceMatcher
from functools import lru_cache
import hashlib
import json
from pathlib import Path
import re
import shutil
import threading
import time
import urllib.error
import urllib.parse
import urllib.request

from convert_downloaded_materials_v1_0_0 import normal, text
from prepare_poetry_catalog_v1_0_2 import clean_body
from data_scope import active_items

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'expansion/sources/chinesepoetrylibrary-v1.0.0'
OUTPUT = ROOT / 'expansion/chinesepoetrylibrary-matching-v1.0.0'
VOLUMES = ('guwen.json', 'tang.json', 'songci.json', 'yuan.json',
           'other.json', 'songshi.json', 'ming.json', 'qing.json')
PRODUCTION = ('data/poems.json', 'data/dict.json',
              'app/assets/data/poems.json', 'app/assets/data/dict.json')
NETWORK_SLOTS = threading.Semaphore(16)


def download_ranges(record, url, partial):
    """Resume the contiguous prefix, downloading missing segments concurrently."""
    start = partial.stat().st_size if partial.exists() else 0
    assert start <= record['size']
    folder = SOURCE / (record['path'] + '.segments')
    folder.mkdir(exist_ok=True)
    segments = [(offset, min(offset + 32 * 1024 * 1024, record['size']) - 1)
                for offset in range(start, record['size'], 32 * 1024 * 1024)]
    progress = {'bytes': start, 'last': time.monotonic()}
    lock = threading.Lock()

    def fetch(segment):
        begin, end = segment
        dest = folder / f'{begin}-{end}.bin'
        expected = end - begin + 1
        if not dest.exists() or dest.stat().st_size != expected:
            temp = folder / f'{begin}-{end}.tmp'
            for attempt in range(3):
                offset = temp.stat().st_size if temp.exists() else 0
                if offset == expected:
                    temp.rename(dest)
                    break
                headers = {'User-Agent': 'HongzhuangTranslationMatching/1.0',
                           'Range': f'bytes={begin+offset}-{end}'}
                try:
                    request = urllib.request.Request(url + f'&range_start={begin+offset}', headers=headers)
                    with NETWORK_SLOTS, urllib.request.urlopen(request, timeout=90) as response:
                        if response.status != 206 or response.headers.get('Content-Range') != f'bytes {begin+offset}-{end}/{record["size"]}':
                            raise ValueError('Unexpected segment response')
                        with temp.open('ab') as out:
                            while True:
                                block = response.read(1024 * 1024)
                                if not block:
                                    break
                                out.write(block)
                    if temp.stat().st_size != expected:
                        raise OSError('Truncated segment')
                    temp.rename(dest)
                    break
                except urllib.error.HTTPError as exc:
                    if exc.code in (401, 403, 429, 503) or attempt == 2:
                        raise
                    time.sleep(2 * (attempt + 1))
                except (OSError, TimeoutError):
                    if attempt == 2:
                        raise
                    time.sleep(2 * (attempt + 1))
        with lock:
            progress['bytes'] += expected
            if time.monotonic() - progress['last'] >= 40:
                print(f'Ranges {record["path"]}: {progress["bytes"]}/{record["size"]}', flush=True)
                progress['last'] = time.monotonic()
        return dest

    with ThreadPoolExecutor(max_workers=8) as pool:
        pieces = list(pool.map(fetch, segments))
    with partial.open('ab') as out:
        for piece in pieces:
            with piece.open('rb') as source:
                shutil.copyfileobj(source, out, 1024 * 1024)
    assert partial.stat().st_size == record['size']


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for block in iter(lambda: f.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def write_new(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8') as f:
        json.dump(value, f, ensure_ascii=False, indent=2)
        f.write('\n')


def iter_rows(path, chunk_size=1024 * 1024):
    """Stream a JSON array without loading a multi-GB volume into memory."""
    decoder = json.JSONDecoder()
    buffer = ''
    position = 0
    ended = False
    with path.open(encoding='utf-8-sig') as f:
        while not buffer.strip():
            block = f.read(chunk_size)
            if not block:
                raise ValueError('Empty JSON file')
            buffer += block
        position = len(buffer) - len(buffer.lstrip())
        if buffer[position] != '[':
            raise ValueError('Expected JSON array')
        position += 1
        while True:
            position = re.compile(r'[\s,]*').match(buffer, position).end()
            if position < len(buffer) and buffer[position] == ']':
                ended = True
                if (buffer[position + 1:] + f.read()).strip():
                    raise ValueError('Trailing JSON content')
                break
            try:
                row, end = decoder.raw_decode(buffer, position)
            except json.JSONDecodeError:
                block = f.read(chunk_size)
                if not block:
                    raise ValueError('Truncated or malformed JSON array')
                buffer = buffer[position:] + block
                position = 0
                if len(buffer) > 64 * 1024 * 1024:
                    raise ValueError('Unexpectedly large source row')
                continue
            if not isinstance(row, dict):
                raise ValueError('Expected object row')
            yield row
            position = end
            if position > chunk_size:
                buffer = buffer[position:]
                position = 0
    if not ended:
        raise ValueError('Unclosed JSON array')


def verify_source(path, record):
    if path.stat().st_size != record['size']:
        raise ValueError('Source size mismatch: ' + path.name)
    digest = sha256(path)
    lfs = record.get('lfs', {})
    expected = lfs.get('oid')
    if expected:
        if digest != expected:
            raise ValueError('Source SHA256 mismatch: ' + path.name)
    else:
        git = hashlib.sha1(f"blob {record['size']}\0".encode())
        with path.open('rb') as f:
            for block in iter(lambda: f.read(1024 * 1024), b''):
                git.update(block)
        if git.hexdigest() != record['oid']:
            raise ValueError('Source git blob mismatch: ' + path.name)
    return digest


def download(record, revision, offline):
    name = record['path']
    path = SOURCE / name
    url = (f'https://huggingface.co/datasets/byj233/ChinesePoetryLibrary/'
           f'resolve/{revision}/{urllib.parse.quote(name)}?download=true')
    if not path.exists():
        if offline:
            raise FileNotFoundError('Source not cached: ' + name)
        partial = SOURCE / (name + '.part')
        download_ranges(record, url, partial)
        verify_source(partial, record)
        partial.rename(path)
    digest = verify_source(path, record)
    verification = SOURCE / (name + '.verified-v1.0.0.json')
    if not verification.exists():
        write_new(verification, dict(url=url, revision=revision, bytes=record['size'], sha256=digest))
    print(f'Verified {name}: {record["size"]} bytes', flush=True)
    return path, digest


@lru_cache(maxsize=50000)
def author_key(value):
    return normal(value)


def quality_flags(translation, body):
    if not translation.strip():
        return ['missing_translation']
    flags = []
    if any(x in translation for x in ('暂无翻译', '暂无译文', '待翻译', '译文略', '（略）')):
        flags.append('placeholder_or_truncation')
    if len(translation.strip()) < 8:
        flags.append('short_translation')
    if normal(translation) == body:
        flags.append('translation_equals_original')
    if len(normal(translation)) < len(body) * 0.35:
        flags.append('possible_incomplete_translation')
    return flags


def match_volume(path, digest, poems, active_ids, revision):
    exact = defaultdict(list)
    titled = defaultdict(list)
    for p in poems:
        a, b = author_key(p['author']), normal(clean_body(p['content']))
        exact[(a, b)].append(p)
        titled[(a, normal(p['title']))].append(p)
    authors = {a for a, _ in exact}
    counts = Counter()
    matches = []
    for index, row in enumerate(iter_rows(path)):
        counts['scanned'] += 1
        author = row.get('author', '')
        if not isinstance(author, str) or author_key(author) not in authors:
            continue
        a = author_key(author)
        body = normal(clean_body(row.get('content', '')))
        targets = exact.get((a, body), [])
        match_type = 'exact_author_body'
        similarity = None
        if not targets:
            candidates = titled.get((a, normal(row.get('title', ''))), [])
            targets = []
            for p in candidates:
                expected = normal(clean_body(p['content']))
                if not expected or not body or not 0.8 <= len(body) / len(expected) <= 1.25:
                    continue
                score = SequenceMatcher(None, expected, body, autojunk=False).ratio()
                if score >= 0.9:
                    targets.append(p)
                    similarity = score
            match_type = 'variant_requires_review'
        if not targets:
            continue
        translation = text(row.get('translation', ''))
        flags = quality_flags(translation, body)
        for p in targets:
            matches.append(dict(id=p['id'], active=p['id'] in active_ids,
                title=p['title'], author=p['author'], baseContent=p['content'],
                matchType=match_type, similarity=similarity, flags=flags,
                translation=translation, notes1=row.get('explanation1', []),
                notes2=row.get('explanation2', []),
                source=dict(file=path.relative_to(ROOT).as_posix(), sha256=digest,
                    revision=revision, row=index, poetryId=row.get('poetry_id'),
                    title=row.get('title'), author=author, content=row.get('content'),
                    originalTranslation=row.get('translation')),
                literaryReviewed=False, approvalRequired=True))
            counts[match_type] += 1
    return dict(file=path.name, counts=dict(counts), matches=matches)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--phase', choices=('pilot', 'full'), required=True)
    ap.add_argument('--offline', action='store_true')
    ap.add_argument('--workers', type=int, choices=range(1, 5), default=3)
    args = ap.parse_args()
    before = {name: sha256(ROOT / name) for name in PRODUCTION}
    doc = json.loads((ROOT / 'data/poems.json').read_text(encoding='utf-8'))
    active_ids = {p['id'] for p in active_items(doc)}
    info = json.loads((SOURCE / 'dataset-info-v1.0.0.json').read_text(encoding='utf-8'))
    files = json.loads((SOURCE / 'file-list-v1.0.0.json').read_text(encoding='utf-8'))
    names = ('guwen.json',) if args.phase == 'pilot' else VOLUMES
    records = sorted((r for r in files if r['path'] in names), key=lambda r: names.index(r['path']))
    assert len(records) == len(names)
    if args.phase == 'full':
        gate = json.loads((OUTPUT / 'pilot-gate-v1.0.0.json').read_text(encoding='utf-8'))
        assert gate['productionSha256'] == before and gate['passed']
    results, errors = [], []
    started = time.monotonic()

    def task(record):
        path, digest = download(record, info['sha'], args.offline)
        result = match_volume(path, digest, doc['items'], active_ids, info['sha'])
        print(f'Matched {path.name}: {result["counts"]}', flush=True)
        return result

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(task, r): r for r in records}
        for future in as_completed(futures):
            try:
                results.append(future.result())
            except Exception as exc:
                errors.append(dict(file=futures[future]['path'], error=repr(exc)))
                print(f'Failed {futures[future]["path"]}: {exc}', flush=True)
    assert before == {name: sha256(ROOT / name) for name in PRODUCTION}, 'Production changed during matching'
    matches = [m for r in results for m in r['matches']]
    active = [m for m in matches if m['active']]
    good = [m for m in active if m['matchType'] == 'exact_author_body' and not m['flags']]
    good_ids = {m['id'] for m in good}
    variants = {m['id'] for m in active if m['matchType'] == 'variant_requires_review' and m['translation']}
    conflicts = {pid for pid in good_ids if len({m['translation'] for m in good if m['id'] == pid}) > 1}
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
    folder = OUTPUT / f'{args.phase}-{stamp}'
    summary = dict(version='1.0.0', phase=args.phase, sourceRevision=info['sha'],
        seconds=round(time.monotonic()-started, 2), volumesCompleted=len(results), errors=errors,
        stored=len(doc['items']), active=len(active_ids), sourceRowsScanned=sum(r['counts'].get('scanned',0) for r in results),
        activeExactReadableCandidates=len(good_ids), activeTranslationConflicts=len(conflicts),
        activeVariantCandidates=len(variants), activeWithoutExactReadableCandidate=len(active_ids-good_ids),
        productionSha256=before, productionChanged=False, databaseImported=False, apkBuilt=False,
        approvalRequired=True, literaryReviewed=False)
    write_new(folder / 'candidates-v1.0.0.json', dict(summary=summary, matches=matches))
    write_new(folder / 'report-v1.0.0.json', summary)
    write_new(folder / 'unmatched-active-v1.0.0.json',
              [dict(id=p['id'],title=p['title'],author=p['author'],category=p.get('genre',p['category']))
               for p in doc['items'] if p['id'] in active_ids-good_ids])
    if args.phase == 'pilot' and not errors and good_ids:
        gate_path = OUTPUT / 'pilot-gate-v1.0.0.json'
        if not gate_path.exists():
            write_new(gate_path, dict(passed=True, productionSha256=before, report=str(folder.relative_to(ROOT))))
    print(json.dumps(summary, ensure_ascii=False, indent=2), flush=True)
    print('Results:', folder, flush=True)


if __name__ == '__main__':
    main()
