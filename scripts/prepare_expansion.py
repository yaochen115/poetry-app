"""Prepare source-traceable editorial candidates. Never edits production data."""
import hashlib
import html
import json
import re
import sys
from collections import Counter
from pathlib import Path
from data_scope import active_items,disabled_ids

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'expansion'
sys.path.insert(0, str(WORK / 'python-packages'))
from opencc import OpenCC

CC = OpenCC('t2s')
CATS = {'唐诗': 'tang', '宋词': 'song', '元曲': 'yuan', '古文': 'guwen'}


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def key(s):
    return re.sub(r'[^\u3400-\u9fff〇a-zA-Z0-9]', '', CC.convert(s))


def main():
    production = read(ROOT / 'data/poems.json')
    active = active_items(production)
    snapshot = WORK / 'baseline'
    snapshot.mkdir(parents=True, exist_ok=True)
    for name in ('poems.json', 'dict.json', 'categories.json'):
        src = ROOT / 'data' / name
        dst = snapshot / name
        if not dst.exists():
            dst.write_bytes(src.read_bytes())
    baseline = read(snapshot / 'poems.json')
    seen = {key(p['content']) for p in production['items']}
    rows = {c: [] for c in CATS}
    targets = {c: max(0, 1050-sum(p['category'] == c for p in active)) for c in CATS}
    duplicates = Counter()

    def add(cat, title, author, dynasty, content, source, location, excerpt=None):
        content = CC.convert(content).strip()
        k = key(content)
        if not k or k in seen:
            duplicates[cat] += 1
            return
        if len(rows[cat]) >= targets[cat]:
            return
        # Reject visibly broken or missing texts, retain doubtful editions for review.
        if any(x in content for x in ('□', '�', '暂无', '原文缺')):
            return
        seen.add(k)
        rows[cat].append({
            'candidateId': f'{CATS[cat]}-candidate-{len(rows[cat])+1:04}',
            'category': cat, 'title': CC.convert(title), 'author': CC.convert(author),
            'dynasty': dynasty, 'content': content,
            'excerptOf': excerpt, 'source': source, 'sourceLocation': location,
            'contentSha256': hashlib.sha256(content.encode()).hexdigest(),
            'status': 'needs_editorial_review',
            'required': ['verify_original_and_category', 'translation', 'notes', 'tags', 'dictionary'],
            'reviewFlags': (['excerpt_boundary'] if excerpt else [])
                + (['dramatic_excerpt_or_suite'] if cat == '元曲' and any(s in title for s in ('/', '诈妮子', '闺怨佳人')) else [])
                + (['non_bmp_character'] if any(ord(c)>0xffff for c in content) else [])
                + (['long_text'] if len(content)>2000 else []),
        })

    sources = WORK / 'sources' / 'chinese-poetry'
    # Dedicated collections avoid relying on mixed-corpus dynasty/category labels.
    for cat, folder, glob, dynasty in [
        ('唐诗', '全唐诗', 'poet.tang.*.json', '唐'),
        ('宋词', '宋词', 'ci.song.*.json', '宋'),
        ('元曲', '元曲', 'yuanqu.json', '元'),
    ]:
        for f in sorted((sources / folder).glob(glob)):
            for i, p in enumerate(read(f)):
                add(cat, p.get('title', p.get('rhythmic', '')),
                    p.get('author', ''), dynasty, '\n'.join(p['paragraphs']),
                    'chinese-poetry/chinese-poetry', f.relative_to(sources).as_posix() + f'#{i}')

    prose_path = WORK / 'sources/poems-db/子部/儒家类.json'
    books = read(prose_path)['儒家类']
    for book in books:
        if book['nameStr'] not in ('荀子', '国语', '围炉夜话'):
            continue
        for i, view in enumerate(book['book']['tb_bookviews']['bookviews']):
            original = view['content']['tb_bookview']
            text = original.get('cont') or ''
            text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), text)
            text = text.replace(r'\r\n', '\n').replace('</p>', '\n')
            text = html.unescape(re.sub(r'<[^>]*>', '', text)).strip()
            bookname = book['nameStr']
            add('古文', f'{bookname}·{original["nameStr"]}', book['author'],
                '清' if bookname == '围炉夜话' else '先秦·战国', text,
                'yxcs/poems-db', f'子部/儒家类.json#book={bookname}&view={i+1}')

    # Prose passages retain chapter and paragraph locator. They are candidates,
    # not assertions that an isolated paragraph is a complete independent work.
    for name, author, dynasty in [
        ('论语/lunyu.json', '孔子及其弟子', '先秦·春秋'),
        ('四书五经/mengzi.json', '孟子及其弟子', '先秦·战国'),
        ('四书五经/daxue.json', '《礼记》', '先秦'),
        ('四书五经/zhongyong.json', '《礼记》', '先秦'),
    ]:
        a = read(sources / name)
        if isinstance(a, dict):
            a = [a]
        book = '论语' if 'lunyu' in name else '孟子' if 'mengzi' in name else '大学' if 'daxue' in name else '中庸'
        for ci, ch in enumerate(a):
            for pi, text in enumerate(ch['paragraphs']):
                # Short fragments need context; do not select them to inflate counts.
                if len(key(text)) < 35:
                    continue
                add('古文', f'{book}·{CC.convert(ch["chapter"])}（段落候选 {pi+1}）',
                    author, dynasty, text, 'chinese-poetry/chinese-poetry',
                    f'{name}#chapter={ci+1}&paragraph={pi+1}', book)

    for cat, values in rows.items():
        write(WORK / 'candidates' / (CATS[cat] + '.json'), {'items': values})
    all_chars = {c for vs in rows.values() for p in vs for c in p['content'] if '\u4e00' <= c <= '\u9fff'}
    dictionary = read(ROOT / 'data/dict.json')
    report = {
        'targetTotal': 4200, 'targetPerCategory': 1050,
        'productionTotal': len(active),'storedTotal':len(production['items']),'disabledCount':len(disabled_ids(production)),
        'addedOriginals': len(active)-len(baseline['items']),
        'completedAdditions': sum(p.get('editorialStatus') != 'original_only' for p in active)-len(baseline['items']),
        'completeWithTranslation': sum(p.get('editorialStatus') != 'original_only' for p in active),
        'originalOnlyPendingEnrichment': sum(p.get('editorialStatus') == 'original_only' for p in active),
        'remainingAdditions': 4200-len(active),
        'candidateCounts': {c: len(v) for c, v in rows.items()},
        'remainingCandidatesToFind': {c: targets[c]-len(v) for c,v in rows.items()},
        'deduplicatedAgainstProduction': True,
        'duplicatesSkipped': dict(duplicates),
        'missingCharactersInCandidates': ''.join(sorted(all_chars-set(dictionary['chars']))),
        'note': 'All candidates require editorial review. No candidate counts as a completed addition. Prose excerpt boundaries must be checked; no arbitrary split to meet quotas.',
        'excludedSource': 'snowtraces directory labels are not used as category authority: observed dynasty and genre mismatches.',
    }
    write(WORK / 'progress.json', report)
    print(json.dumps({k:v for k,v in report.items() if k!='missingCharactersInCandidates'}, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
