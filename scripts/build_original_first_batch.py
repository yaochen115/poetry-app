"""Build the authorized 600-original milestone; no placeholder translations."""
import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'expansion'


def read(p):
    return json.loads(p.read_text(encoding='utf-8'))


def write(p, value):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(value, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')


def main():
    poems = read(ROOT / 'data/poems.json')
    if len(poems['items']) != 244:
        raise ValueError('Build from the 244-entry checkpoint only; use the saved batch for repeats.')
    checkpoint = WORK / 'checkpoints/pre-original-600'
    checkpoint.mkdir(parents=True, exist_ok=True)
    for name in ('poems.json', 'dict.json'):
        target = checkpoint / name
        data = (ROOT / 'data' / name).read_bytes()
        if target.exists() and target.read_bytes() != data:
            raise ValueError('Checkpoint differs; do not overwrite')
        target.write_bytes(data)
    rows, sources = [], defaultdict(dict)
    curves = ('庆宣和 凭栏人 得胜乐 落梅风 寿阳曲 天净沙 迎仙客 清江引 四块玉 '
              '阳春曲 喜春来 乔木查 寨儿令 金字经 拨不断 节节高 醉扶归 一半儿 '
              '春闺怨 红绣鞋 得胜令 庆东原 上小楼 卖花声 大德歌 醉中天 小桃红 '
              '绿么遍 朱履曲 山坡羊 水仙子 沉醉东风').split()
    repairs = {}
    for prefix, category in [('tang', '唐诗'), ('song', '宋词'), ('yuan', '元曲'), ('guwen', '古文')]:
        selection = read(WORK / f'final-{prefix}-selection.json')
        if prefix == 'yuan':
            # A doubtful character in this source is avoided, not silently corrected.
            raw = read(WORK / 'sources/poetry-source/source/曲/元/qu.元.0000.json')
            selection[41] = dict(title=raw[226]['title'], writer=raw[226]['authorName'],
                                 dynasty='元', content='\n'.join(raw[226]['content']),
                                 _repo='poetry-source', _file='source/曲/元/qu.元.0000.json', _row=226)
        if len(selection) != 89:
            raise ValueError(f'{prefix}: expected 89 originals')
        for i, candidate in enumerate(selection, 62):
            iid = f'{prefix}-{i:03}'
            text = candidate['content'].strip()
            text = re.sub(r'[①②③④⑤⑥⑦⑧⑨⑩]', '', text)
            title = candidate['title'].split(' / ')[0]
            subtitle = ''
            excerpt = None
            excerpt_note = ''
            if prefix == 'yuan':
                original_title = title
                title = title.replace('阅金经', '金字经').replace('水坡羊', '山坡羊')
                if title != original_title:
                    repairs[iid] = dict(sourceTitle=original_title, normalizedTitle=title,
                                        reason='曲牌名按金字经、山坡羊规范写法整理；正文未改')
                if '稍宵宴坐' in title:
                    repairs[iid] = dict(sourceTitle=original_title,
                                        normalizedTitle=title.replace('稍宵宴坐', '秋宵宴坐'),
                                        reason='题名参照 chinese-poetry 元曲/yuanqu.json 第2128条的秋宵宴坐')
                    title = title.replace('稍宵宴坐', '秋宵宴坐')
                found = next((c for c in curves if c in title), None)
                if not found:
                    raise ValueError(f'Unrecognized tune: {title}')
                pos = title.index(found) + len(found)
                subtitle = title[pos:].strip('·・·【】 ')
                title = found
                if not subtitle:
                    subtitle = re.split('[，。！？；]', text)[0]
            elif prefix == 'guwen':
                chapter = candidate['_chapter']
                para = candidate['_paragraph']
                book = read(WORK / 'sources/chinese-poetry/论语/lunyu.json')[chapter]['chapter']
                title = f'论语·{book}·{para+1}'
                excerpt = f'论语·{book}'
                excerpt_note = f'完整选录所据数据本篇第{para+1}段，段号为该数据排列位置；非全篇。'
            elif '·' in title:
                title, subtitle = title.split('·', 1)
            dynasty = candidate['dynasty']
            if prefix == 'tang':
                dynasty = '唐'
                # Pair the lines as required by the existing poem renderer.
                text = re.sub(r'\s+', '', text)
                text = re.sub(r'([。！？])', r'\1\n', text).strip()
            elif prefix == 'song':
                dynasty = '五代·南唐' if candidate['writer'] == '李煜' else '宋'
            row = dict(id=iid, category=category, tags=[], title=title, subtitle=subtitle,
                       author=candidate['writer'], dynasty=dynasty, excerptOf=excerpt,
                       excerptNote=excerpt_note, content=text, translation='', notes=[],
                       editorialStatus='original_only',
                       pending=['translation', 'notes', 'themeTags', 'dictionary'])
            rows.append(row)
            repo = candidate.get('_repo', 'chinese-gushiwen')
            file = candidate['_file']
            if repo == 'chinese-gushiwen':
                file = 'guwen/' + file
            if prefix == 'guwen':
                location = dict(chapter=candidate['_chapter'], paragraph=candidate['_paragraph'])
            else:
                location = candidate['_row']
            sources[(repo, file)][iid] = location
    write(WORK / 'batches/004-originals.json', dict(
        dataVersion='1.1.0', stage='original_only', items=rows,
        provenance=dict(
            policy='负责人选择 D：原文优先。没有生成或复用现代译注。',
            sources=[dict(repository='https://github.com/' + {
                'chinese-gushiwen': 'aopao/chinese-gushiwen',
                'chinese-poetry': 'chinese-poetry/chinese-poetry',
                'poetry-source': 'snowtraces/poetry-source',
            }[repo], file=file, locations=locations) for (repo, file), locations in sources.items()],
            titleCorrections=repairs,
            editorialChanges='移除脚注标记、保留正文；唐诗按完整句组换行。副题缺失的小令以首句标识。',
        )))
    print(f'Built {len(rows)} original-only entries.')


if __name__ == '__main__':
    main()
