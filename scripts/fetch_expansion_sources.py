"""Cache public-domain original-text candidates with file hashes and source URLs."""
import concurrent.futures
import hashlib
import json
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'expansion' / 'sources'


def fetch(job):
    repo, name, blob = job
    url = f'https://raw.githubusercontent.com/{repo}/master/{urllib.parse.quote(name)}'
    dest = OUT / repo.split('/')[-1] / name
    dest.parent.mkdir(parents=True, exist_ok=True)
    for attempt in range(3):
        try:
            data = urllib.request.urlopen(url, timeout=60).read()
            dest.write_bytes(data)
            return dict(repo=repo, path=name, url=url, gitBlob=blob,
                        bytes=len(data), sha256=hashlib.sha256(data).hexdigest())
        except Exception:
            if attempt == 2:
                raise
            time.sleep(1)


def main():
    jobs = []
    for repo, tree in [('snowtraces/poetry-source', 'poetry-source'),
                       ('chinese-poetry/chinese-poetry', 'chinese-poetry')]:
        entries = json.loads((OUT / (tree + '-tree.json')).read_text(encoding='utf-8'))['tree']
        for e in entries:
            n = e['path']
            take = n in ('README.md', 'LICENSE')
            if tree == 'poetry-source':
                take |= (n.startswith(('source/诗/唐/', 'source/词/宋/'))
                         and n.endswith(('.0000.json', '.0001.json', '.0002.json', '.0003.json')))
                take |= n == 'source/曲/元/qu.元.0000.json'
            else:
                take |= n in ('论语/lunyu.json', '四书五经/mengzi.json',
                              '四书五经/daxue.json', '四书五经/zhongyong.json')
                take |= n in ('全唐诗/poet.tang.0.json', '全唐诗/poet.tang.1000.json',
                              '全唐诗/poet.tang.2000.json', '宋词/ci.song.0.json',
                              '宋词/ci.song.1000.json', '宋词/ci.song.2000.json')
            if take and e['type'] == 'blob':
                jobs.append((repo, n, e['sha']))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        records = list(pool.map(fetch, jobs))
    (OUT / 'expansion-manifest.json').write_text(
        json.dumps(records, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    print(f'Cached {len(records)} source files with hashes.')


if __name__ == '__main__':
    main()
