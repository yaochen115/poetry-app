"""名单 -> 诗泉 API -> 身份/全篇校验 -> 备份 -> App JSON 数据库；默认预览，--apply 入库。"""
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError
import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import threading
import time
from uuid import uuid4

from enrichment_pipeline import ROOT, read, write_once, digest
from data_scope import active_items, disabled_ids
from prepare_poetry_catalog_v1_0_2 import clean_body
from select_poetry_2000_v1_0_0 import BASE, norm

VERSION = '1.0.0'
WORK = ROOT / 'expansion/poetry-api-sync-v1.0.0'
CACHE = BASE / 'provider-api'
SLOTS = {'诗': '唐诗', '词': '宋词'}  # 旧版存储槽位；genre 才是实际体裁，不表示朝代。
PREFIX = {'诗': 'tang', '词': 'song'}


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def atomic_bytes(path, raw):
    path = Path(path)
    with tempfile.NamedTemporaryFile(dir=path.parent, prefix='.api-sync-', delete=False) as f:
        temporary = Path(f.name)
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


class Client:
    def __init__(self, workers=2, interval=1, budget=2000):
        self.interval = interval
        self.budget = budget
        self.lock = threading.Lock()
        self.next = 0
        self.requests = 0
        self.stop = threading.Event()
        self.reason = None

    def search(self, query):
        params = dict(q=query, page=1, pageSize=100, lang='zh-Hans')
        url = 'https://poetry.palemoky.com/api/search?' + urlencode(sorted(params.items()))
        key = hashlib.sha256(url.encode()).hexdigest()
        path = CACHE / 'cache' / (key + '.json')
        if path.exists():
            meta = read(CACHE / 'metadata' / (key + '.json'))
            if meta['url'] != url or sha(path) != meta['sha256']:
                raise ValueError('API cache changed: ' + key)
            return read(path)
        with self.lock:
            if self.stop.is_set():
                raise RuntimeError('Requests stopped: ' + str(self.reason))
            if self.requests >= self.budget:
                raise RuntimeError('Per-run request budget reached; resume with same command')
            time.sleep(max(0, self.next - time.monotonic()))
            self.next = time.monotonic() + self.interval
            self.requests += 1
        try:
            with urlopen(Request(url, headers={'User-Agent': 'HongzhuangCatalogSync/1.0 (bounded cached requests)'}), timeout=20) as response:
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise ValueError('Response exceeded 4MB')
                doc = json.loads(raw)
                if not isinstance(doc.get('data'), list):
                    raise ValueError('Unexpected public API schema')
            write_once(path, doc)
            write_once(CACHE / 'metadata' / (key + '.json'), dict(url=url, sha256=sha(path), acquiredAt=datetime.now(timezone.utc).isoformat()))
            return doc
        except HTTPError as exc:
            if exc.code in (401, 403, 429, 503):
                self.reason = 'HTTP ' + str(exc.code)
                self.stop.set()
            raise


def catalog_items(document):
    items = document['items']
    if Counter(p['genre'] for p in items) != document['target']:
        raise ValueError('Catalog genre counts differ from target')
    if len({p['id'] for p in items}) != len(items):
        raise ValueError('Duplicate catalog IDs')
    fingerprints = [p['canonicalFingerprint'] for p in items if p['canonicalFingerprint']]
    if len(fingerprints) != len(set(fingerprints)):
        raise ValueError('Same original counted as multiple selected works')
    for p in items:
        if not p.get('title') or not p.get('author') or p['genre'] not in SLOTS:
            raise ValueError('Invalid selected identity')
        if p['canonicalFingerprint'] and norm(clean_body(p['matchingText'])) != p['canonicalFingerprint']:
            raise ValueError('Catalog reference fingerprint changed: ' + p['id'])
    return items


def provider_index(root=ROOT, base=BASE):
    result = defaultdict(list)
    paths = list((base / 'provider-api/cache').glob('*.json'))
    for path in sorted(paths):
        if not path.resolve().is_relative_to((root / 'expansion').resolve()):
            raise ValueError('Cache path escaped project expansion directory')
        metadata = base / 'provider-api/metadata' / path.name
        if path.parent.name == 'cache':
            meta = read(metadata)
            if sha(path) != meta['sha256'] or not meta['url'].startswith('https://poetry.palemoky.com/api/'):
                raise ValueError('Changed/untrusted provider cache: ' + str(path))
        else:
            meta = dict(url='https://poetry.palemoky.com/api/search', sha256=sha(path))
        doc = read(path)
        for row in doc.get('data', []):
            if not isinstance(row, dict) or not isinstance(row.get('content'), list) or not isinstance(row.get('author'), dict):
                continue
            content = '\n'.join(row['content'])
            if any(s in content for s in ('记忆体', '海内存', '\ufffd')) or any(0xe000 <= ord(c) <= 0xf8ff for c in content):
                continue
            body = norm(content)
            if not body:
                continue
            result[(norm(row['author']['name']), body)].append(dict(row=row, content=content, source=dict(
                provider='https://poetry.palemoky.com', url=meta['url'], providerId=row['id'],
                cacheFile=path.relative_to(root).as_posix(), sha256=meta['sha256'])))
    return result


def resolve(items, index):
    accepted, held = [], []
    for p in items:
        if not p['canonicalFingerprint']:
            held.append(dict(id=p['id'], title=p['title'], author=p['author'], reason='reference_original_missing'))
            continue
        hits = index.get((norm(p['author']), p['canonicalFingerprint']), [])
        if not hits:
            held.append(dict(id=p['id'], title=p['title'], author=p['author'], reason='no_full_text_author_exact_match; variants/truncations_not_auto_imported'))
            continue
        hit = min(hits, key=lambda h: (h['row']['id'], h['source']['cacheFile']))
        accepted.append(dict(selected=p, **hit))
    return accepted, held


def plan(document, accepted):
    """Pure merge: old rows untouched, stable IDs reused, new source originals appended."""
    result = copy.deepcopy(document)
    rows = result['items']
    excluded = disabled_ids(result)
    active = active_items(result)
    # Stored order and activation order differ when an archived work is enabled.
    # Preserve the profile's order so the next run cannot bump versions by reordering IDs.
    chosen = list(result['selectionProfile']['ids']) if result.get('selectionProfile') else [p['id'] for p in active]
    selected_ids = set(chosen)
    bindings = result.setdefault('poetryApiBindings', {})
    existing = defaultdict(list)
    body_authors = defaultdict(set)
    for p in rows:
        if p['id'] not in excluded:
            body = norm(clean_body(p['content']))
            existing[(norm(p['author']), body)].append(p)
            body_authors[body].add(norm(p['author']))
    ids = {p['id'] for p in rows}
    added, activated, preserved, conflicts = [], [], [], []
    for entry in accepted:
        p = entry['selected']
        key = (norm(p['author']), p['canonicalFingerprint'])
        matches = existing.get(key, [])
        if matches:
            old = min(matches, key=lambda x: (x['id'] not in selected_ids, x['id']))
            app_id = old['id']
            preserved.append(app_id)
        else:
            if body_authors.get(key[1]):
                conflicts.append(dict(id=p['id'], reason='same_text_different_existing_author; attribution_review_needed'))
                continue
            prefix = PREFIX[p['genre']]
            number = max((int(i.split('-')[1]) for i in ids if re.fullmatch(prefix + r'-\d+', i)), default=0) + 1
            if number > 9999:
                raise ValueError('Legacy numeric ID space exhausted')
            app_id = f'{prefix}-{number:03d}'
            row = dict(id=app_id, category=SLOTS[p['genre']], genre=p['genre'], title=p['title'], subtitle='',
                       author=p['author'], dynasty=p['dynasty'], excerptOf=None, excerptNote='', content=entry['content'],
                       translation='', notes=[], tags=[], editorialStatus='original_only',
                       pending=['translation', 'notes', 'themeTags', 'dictionary'], originalSource=entry['source'],
                       selectionCatalogId=p['id'], review=dict(identity='full_text_author_normalized_exact', literaryApproved=False))
            rows.append(row)
            ids.add(app_id)
            existing[key].append(row)
            body_authors[key[1]].add(key[0])
            added.append(app_id)
        if app_id not in selected_ids:
            chosen.append(app_id)
            selected_ids.add(app_id)
            activated.append(app_id)
        # Preserve earlier provenance once a stable catalog binding is established.
        if p['id'] not in bindings:
            bindings[p['id']] = dict(appId=app_id, genre=p['genre'], source=entry['source'],
                                    referenceFingerprint=p['canonicalFingerprint'], preservedExistingEntry=app_id not in added)
    by_id = {p['id']: p for p in rows}
    if not bindings and 'poetryApiBindings' not in document:
        result.pop('poetryApiBindings')
    old_profile = result.get('selectionProfile', {})
    result['selectionProfile'] = dict(old_profile, ids=chosen, expectedCounts=dict(Counter(by_id[i]['category'] for i in chosen)))
    changed = result != document
    if changed:
        parts = result['dataVersion'].split('.')
        parts[-1] = str(int(parts[-1]) + 1)
        result['dataVersion'] = '.'.join(parts)
    return result, dict(changed=changed, newRows=added, newlyVisible=activated, preservedExistingIds=sorted(set(preserved)),
                        boundCatalogWorks=len(bindings), active=len(chosen), conflicts=conflicts)


def apply(document, proposed, summary, *, root=ROOT, validate=True):
    if not summary['changed']:
        return dict(applied=False, reason='idempotent_no_changes', **summary)
    data = root / 'data/poems.json'
    asset = root / 'app/assets/data/poems.json'
    if read(data) != document or data.read_bytes() != asset.read_bytes():
        raise ValueError('Database changed or assets differ; re-run to recompute merge')
    version = proposed['dataVersion']
    backup = root / 'expansion/checkpoints' / ('pre-poetry-api-data-v' + version + '--' + uuid4().hex[:8])
    before = {data: data.read_bytes(), asset: asset.read_bytes()}
    for path, raw in before.items():
        dest = backup / path.relative_to(root)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(raw)
    manifest = root / 'expansion/poetry-api-imports' / ('data-v' + version + '.json')
    write_once(manifest, dict(toolVersion=VERSION, dataVersion=version, status='prepared', summary=summary,
                              entries=[p for p in proposed['items'] if p['id'] in summary['newRows']],
                              bindings=proposed['poetryApiBindings'], backup=backup.relative_to(root).as_posix()))
    raw = (json.dumps(proposed, ensure_ascii=False, indent=2) + '\n').encode('utf-8')
    snapshot = root / 'data/versions' / ('poems-v' + version + '.json')
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    try:
        for path in before:
            atomic_bytes(path, raw)
        if validate:
            subprocess.run([sys.executable, '-B', str(root / 'scripts/validate_data.py'), '--original-only'], check=True, cwd=root)
        with snapshot.open('xb') as f:
            f.write(raw)
        write_once(manifest.with_name(manifest.stem + '-committed.json'), dict(status='committed', dataVersion=version, sha256=sha(data)))
    except Exception:
        for path, old in before.items():
            atomic_bytes(path, old)
        write_once(manifest.with_name(manifest.stem + '-rolled-back.json'), dict(status='rolled_back', dataVersion=version))
        raise
    return dict(applied=True, dataVersion=version, snapshot=str(snapshot), backup=str(backup), **summary)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--catalog', type=Path, default=BASE / 'catalog-v1.0.2.json')
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--offline', action='store_true', help='只复用现有诗泉缓存并入库，零网络请求')
    parser.add_argument('--workers', type=int, default=2)
    parser.add_argument('--interval', type=float, default=1)
    parser.add_argument('--max-requests', type=int, default=2000)
    args = parser.parse_args()
    if not 1 <= args.workers <= 4 or not .5 <= args.interval <= 30 or not 1 <= args.max_requests <= 4000:
        parser.error('workers 1..4; interval .5..30; max-requests 1..4000')
    catalog = args.catalog.resolve()
    if not catalog.is_relative_to((ROOT / 'expansion').resolve()):
        parser.error('名单必须位于本项目 expansion 目录内')
    WORK.mkdir(parents=True, exist_ok=True)
    lock = ROOT / 'expansion/poetry-api-sync.lock'
    fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    os.write(fd, str(os.getpid()).encode())
    stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S') + '--' + uuid4().hex[:6]
    try:
        items = catalog_items(read(catalog))
        index = provider_index()
        accepted, held = resolve(items, index)
        print(f'名单 {len(items)} 篇；缓存严格匹配 {len(accepted)} 篇；待补 {len(held)} 篇。', flush=True)
        errors = []
        client = Client(args.workers, args.interval, args.max_requests)
        if not args.offline:
            ids = {e['selected']['id'] for e in accepted}
            missing = [p for p in items if p['id'] not in ids and p['canonicalFingerprint']]
            queries = sorted({p['canonicalFingerprint'][:9] for p in missing})
            print(f'待检查查询 {len(queries)} 个（缓存命中不重复请求）；网络预算 {client.budget} 次。', flush=True)
            # Bounded in-flight work; a stopped source does not create thousands of fake failed queries.
            for start in range(0, len(queries), args.workers):
                if client.stop.is_set() or client.requests >= client.budget:
                    break
                with ThreadPoolExecutor(max_workers=args.workers) as pool:
                    jobs = {pool.submit(client.search, q): q for q in queries[start:start + args.workers]}
                    for job in as_completed(jobs):
                        try:
                            job.result()
                        except Exception as exc:
                            errors.append(dict(query=jobs[job], error=type(exc).__name__ + ': ' + str(exc)))
                if start % (args.workers * 25) == 0:
                    print(f'查询进度 {min(start + args.workers, len(queries))}/{len(queries)}；实际联网 {client.requests}；停止原因 {client.reason or "无"}', flush=True)
            accepted, held = resolve(items, provider_index())
        document = read(ROOT / 'data/poems.json')
        proposed, summary = plan(document, accepted)
        applied = apply(document, proposed, summary) if args.apply else dict(applied=False, reason='preview_only', **summary)
        handoff = None
        if applied.get('applied'):
            try:
                subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/export_pending_enrichment.py')], check=True, cwd=ROOT)
                handoff = 'pending queues and CURRENT_STATE refreshed'
            except Exception as exc:
                handoff = 'Database committed; handoff export needs retry: ' + str(exc)
        report = dict(toolVersion=VERSION, catalog=catalog.relative_to(ROOT).as_posix(), catalogSha256=sha(catalog),
                      target=len(items), matched=len(accepted), held=held, networkRequests=client.requests,
                      stopped=client.stop.is_set(), stopReason=client.reason, errors=errors, database=applied, handoff=handoff, apkBuilt=False)
        path = WORK / ('run-v1.0.0--' + stamp + '.json')
        write_once(path, report)
        print(json.dumps(dict(report=str(path), target=len(items), matched=len(accepted), held=len(held),
                             networkRequests=client.requests, stopped=client.stop.is_set(), stopReason=client.reason,
                             database={k:v for k,v in applied.items() if k not in ('newRows','newlyVisible','preservedExistingIds')}, apkBuilt=False), ensure_ascii=False, indent=2))
    finally:
        os.close(fd)
        lock.unlink()


if __name__ == '__main__':
    main()
