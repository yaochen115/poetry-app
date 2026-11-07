"""Build a source-traceable original-only batch from cached public-domain texts."""
import argparse
import difflib
import html
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from data_scope import active_items

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / 'expansion'
sys.path.insert(0, str(WORK/'python-packages'))
from opencc import OpenCC
CC = OpenCC('t2s')
CATS = {'唐诗': 'tang', '宋词': 'song', '元曲': 'yuan', '古文': 'guwen'}


def read(path):
    return json.loads(path.read_text(encoding='utf-8'))


def clean(text, preserve_brackets=False):
    text = re.sub(r'\\u([0-9a-fA-F]{4})', lambda m: chr(int(m[1], 16)), text)
    text = text.replace(r'\r\n', '\n').replace('</p>', '\n')
    text = html.unescape(re.sub(r'</?(?:p|br|span|div|sup|a|strong|em|b|i|font)(?:\s[^>]*)?/?>', '', text, flags=re.I))
    if not preserve_brackets:
        text = re.sub(r'[(（][^)）]*[)）]', '', text)
    text = re.sub('[①②③④⑤⑥⑦⑧⑨⑩]', '', text)
    return '\n'.join(line.strip() for line in text.splitlines() if line.strip())


def key(text):
    return ''.join(c for c in CC.convert(text) if c.isalnum())


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--target-total', type=int, required=True)
    parser.add_argument('--batch', required=True)
    args = parser.parse_args()
    if args.target_total % 4 or not 0 < args.target_total <= 4200 or not re.fullmatch(r'\d{3}', args.batch):
        parser.error('Target must be divisible by 4 and at most 4200; batch must be 3 digits')
    output = WORK/'batches'/f'{args.batch}-originals.json'
    if output.exists():
        raise ValueError('Saved batch exists; do not overwrite')
    production = read(ROOT/'data/poems.json')
    counts = Counter(p['category'] for p in active_items(production))
    needed = {c: args.target_total//4-counts[c] for c in CATS}
    if len(set(needed.values())) != 1 or min(needed.values()) <= 0:
        raise ValueError('Current data must be balanced and below target')
    selected = {c: [] for c in CATS}
    seen = {key(p['content']) for p in production['items']}
    prefix_index = defaultdict(list)
    for text in seen:
        prefix_index[text[:8]].append(text)
    exclusions = Counter()

    def add(cat, title, author, dynasty, text, repo, file, location, excerpt=None, note='', preserve_brackets=False):
        if len(selected[cat]) >= needed[cat]:
            return False
        text = clean(text,preserve_brackets=preserve_brackets)
        k = key(text)
        if (len(k) < 12 or not author or not title or any(c in text for c in ['□','�','…','山雨亡泪','血华啼','凤酥不将肋'])
                or re.search(r'<[\u3400-\u9fff]|[{}]', text)
                or re.search(r'[\u3100-\u312f\u3040-\u30ff]', text)
                or any(0xe000 <= ord(c) <= 0xf8ff for c in text)
                or any(ord(c)>0xffff for c in text)):
            exclusions['broken_or_unsupported_text'] += 1
            return False
        if k in seen or any(difflib.SequenceMatcher(None,k,old,autojunk=False).ratio()>.94
                            for old in prefix_index[k[:8]]):
            exclusions['exact_or_near_duplicate'] += 1
            return False
        if cat == '古文' and any(k in old for old in seen if len(old)>len(k)):
            exclusions['prose_already_contained_in_existing_entry'] += 1
            return False
        seen.add(k)
        prefix_index[k[:8]].append(k)
        selected[cat].append(dict(title=title.split(' / ')[0],author=author,dynasty=dynasty,
                                 content=text,repo=repo,file=file,location=location,
                                 excerptOf=excerpt,excerptNote=note))
        return True

    tang_authors = set(('李白 杜甫 王维 孟浩然 王昌龄 王之涣 王勃 骆宾王 杨炯 卢照邻 陈子昂 '
        '贺知章 高适 岑参 王翰 王湾 李峤 刘长卿 韦应物 柳宗元 韩愈 白居易 刘禹锡 元稹 '
        '张籍 贾岛 姚合 李贺 李商隐 杜牧 温庭筠 张祜 许浑 赵嘏 皮日休 陆龟蒙 罗隐 '
        '郑谷 齐己 贯休 司空图 司空曙 钱起 卢纶 韩翃 皇甫冉 戴叔伦 李端 李益 王建 '
        '张九龄 宋之问 沈佺期 杜审言 王绩 崔颢 崔护 张旭 刘方平 常建 祖咏 綦毋潜 '
        '丘为 李颀 张志和 顾况 孟郊 李绅 张仲素 李涉 朱庆馀 雍陶 陈陶 曹松 黄巢 '
        '胡令能 林杰 高骈 薛涛 鱼玄机 李冶 金昌绪 西鄙人 佚名').split())
    ci = set(('忆江南 忆王孙 如梦令 捣练子 相见欢 乌夜啼 长相思 生查子 昭君怨 点绛唇 '
        '浣溪沙 浣溪纱 菩萨蛮 卜算子 采桑子 减字木兰花 清平乐 阮郎归 画堂春 眼儿媚 '
        '南歌子 醉花阴 武陵春 好事近 更漏子 谒金门 望江南 诉衷情 西江月 忆秦娥 '
        '鹊桥仙 天仙子 浪淘沙令 浪淘沙 桃源忆故人 钗头凤 鹧鸪天 蝶恋花 临江仙 '
        '青玉案 渔家傲 南乡子 破阵子 江城子 苏幕遮 定风波 玉楼春 木兰花 虞美人 '
        '一剪梅 踏莎行 少年游 望海潮 水调歌头 水龙吟 念奴娇 永遇乐 满江红 声声慢 '
        '八声甘州 扬州慢 齐天乐 摸鱼儿 贺新郎 沁园春 满庭芳 凤凰台上忆吹箫 醉落魄 '
        '祝英台近 碧牡丹 桂枝香 唐多令 一丛花 洞仙歌 暗香 疏影 浣溪沙慢').split())
    # Mixed corpus used only where dynasty and an explicit lyric tune/poet agree.
    for f in sorted((WORK/'sources/chinese-gushiwen/guwen').glob('*.json')):
        for index, line in enumerate(f.read_text(encoding='utf-8').splitlines()):
            p = json.loads(line)
            title = p['title'].split(' / ')[0]
            tune = title.split('·')[0]
            text = clean(p['content'])
            if p.get('dynasty') == '唐代' and p['writer'] in tang_authors and tune not in ci and 18<=len(key(text))<=1000:
                add('唐诗', title,p['writer'],'唐',text,'aopao/chinese-gushiwen','guwen/'+f.name,index)
            if (p.get('dynasty') == '宋代' or p['writer']=='李煜') and tune in ci and 30<=len(key(text))<=250:
                add('宋词',title,p['writer'],'五代·南唐' if p['writer']=='李煜' else '宋',text,
                    'aopao/chinese-gushiwen','guwen/'+f.name,index)

    # Dedicated Tang source: retain source coordinates and declare the exact
    # simplified-character conversion so the audit can replay it.
    emperor_names={'太宗皇帝':'李世民','明皇帝':'李隆基','則天皇后':'武则天',
                   '高宗皇帝':'李治','中宗皇帝':'李显','上官昭容':'上官婉儿'}
    for f in sorted((WORK/'sources/chinese-poetry/全唐诗').glob('poet.tang.*.json')):
        for index,p in enumerate(read(f)):
            source_author=p['author']
            author=emperor_names.get(source_author,CC.convert(source_author).removeprefix('僧'))
            text=CC.convert('\n'.join(p['paragraphs']))
            if (author in tang_authors or source_author in emperor_names) and 18<=len(key(text))<=1500:
                add('唐诗',CC.convert(p['title']),author,'唐',text,'chinese-poetry/chinese-poetry',
                    '全唐诗/'+f.name,dict(row=index,textTransform='opencc-t2s',sourceAuthor=source_author))

    # A dedicated lyric collection is a fallback; exclude untitled fragments.
    for f in sorted((WORK/'sources/chinese-poetry/宋词').glob('*.json')):
        for index,p in enumerate(read(f)):
            text='\n'.join(p['paragraphs'])
            if p['rhythmic'] in ci and 40<=len(key(text))<=250:
                add('宋词',p['rhythmic']+'·'+key(text)[:7],p['author'],'宋',text,
                    'chinese-poetry/chinese-poetry','宋词/'+f.name,index)

    yuan_authors = set(('白朴 马致远 张可久 张养浩 贯云石 乔吉 徐再思 周文质 卢挚 姚燧 '
        '刘时中 薛昂夫 徐琰 邓玉宾 刘庭信 郑光祖 张鸣善 王和卿 张弘范 曾瑞 赵善庆 '
        '卫立中 顾德润 李致远 任昱 盍西村 关汉卿 阿鲁威 赵显宏 吴西逸').split())
    tunes = ('庆宣和 凭栏人 得胜乐 落梅风 寿阳曲 天净沙 迎仙客 清江引 四块玉 阳春曲 '
        '喜春来 乔木查 寨儿令 金字经 拨不断 节节高 醉扶归 一半儿 春闺怨 红绣鞋 '
        '得胜令 庆东原 上小楼 卖花声 大德歌 醉中天 小桃红 绿么遍 朱履曲 山坡羊 '
        '水仙子 沉醉东风 折桂令 蟾宫曲 殿前欢 塞鸿秋 普天乐 山丹花 朝天子 人月圆 '
        '满庭芳 雁儿落 刮地风 梧叶儿 叨叨令 端正好 寄生草 小梁州 驻马听').split()
    yuan_file='source/曲/元/qu.元.0000.json'
    for index,p in enumerate(read(WORK/'sources/poetry-source'/yuan_file)):
        title = p.get('title','')
        text = '\n'.join(p.get('content',[]))
        if (p.get('authorName') in yuan_authors and any(t in title for t in tunes)
            and not any(s in title for s in ['幺篇','咏雪大石调','套数']) and 20<=len(key(text))<=350):
            add('元曲', title,p['authorName'],'元',text,'snowtraces/poetry-source',yuan_file,index)

    # Dedicated Quanyuan collection fallback. Keep complete source tune entries,
    # explicitly distinguish single movements from the entire suite, and do not
    # import the southern plays of Ming writers that coexist in this collection.
    yuan_authors.update(('王恽 胡祗遹 商挺 冯子振 刘敏中 珠帘秀 鲜于枢 鲜于必仁 周德清 '
        '张雨 曹德 孙周卿 李泂 杨朝英 范康 刘致 钱霖 虞集 王伯成 王举之 黄公望 '
        '王元鼎 苏彦文 吕止庵 陈草庵 赵禹圭 刘秉忠 庾天锡 庾吉甫 贾固 吴弘道').split())
    yuan_authors.update(('兰楚芳 朱庭玉 吴仁卿 钟嗣成 白贲 查德卿 丘士元 王仲元 孙叔顺 '
        '马谦斋 景元启 奥敦周卿 赵天锡 高秀文 赵彦晖 王德信 孙季昌 侯正卿 '
        '童童学士 王大学士 李唐宾 严忠济 王爱山 胡用和 唐毅夫 王修甫 吕济民 '
        '荆干臣 王仲诚 沙正卿 赵明道 夏庭芝 顾鉴中 亢文苑 阿里西瑛 阚志学 '
        '高克礼 孔文升 沈禧 陈克明 云龛子 张子坚 孔文卿 睢景臣 不忽木').split())
    yuan_whole='元曲/yuanqu.json'
    for index,p in enumerate(read(WORK/'sources/chinese-poetry'/yuan_whole)):
        if len(selected['元曲']) >= needed['元曲']:
            break
        title=p['title']
        text='\n'.join(p['paragraphs'])
        if (p['author'] not in yuan_authors or not re.match(r'^(正宫|中吕|双调|仙吕|南吕|越调|黄钟|商调|大石调)',title)
            or not 20<=len(key(text))<=1500 or any(x in title for x in ['幺','又'])
            or any(x in text for x in ['套数','(云)','(唱)','(下)','(上)','（云）','（唱）'])):
            continue
        k=key(text)
        if any(k in old or old in k for old in seen if len(old)>20):
            exclusions['qu_tune_overlaps_existing_text'] += 1
            continue
        add('元曲',title,p['author'],'元',text,'chinese-poetry/chinese-poetry',yuan_whole,index,
            title,'完整保留所据元曲数据集的整个曲牌条目；带组题或并序者保留整条，按一个原文条目计数，不拆句凑数。单支曲牌不代表整套全文，来源未提供的套曲连接信息后续另行校勘。')

    plays={
        '关汉卿':{'诈妮子调风月','温太真玉镜台','包待制三勘蝴蝶梦','赵盼儿风月救风尘',
                 '山神庙裴度还带','闺怨佳人拜月亭','感天动地窦娥冤','钱大尹智宠谢天香',
                 '关大王独赴单刀会','包待制智斩鲁斋郎','杜蕊娘智赏金线池','关张双赴西蜀梦'},
        '白朴':{'董秀英花月东墙记','唐明皇秋夜梧桐雨','裴少俊墙头马上'},
        '马致远':{'半夜雷轰荐福碑','江州司马青衫泪','西华山陈抟高卧','破幽梦孤雁汉宫秋',
                  '邯郸道省悟黄粱梦','吕洞宾三醉岳阳楼','马丹阳三度任风子'},
        '郑光祖':{'迷青琐倩女离魂','辅成王周公摄政','醉思乡王粲登楼','程咬金斧劈老君堂',
                  '立成汤伊尹耕莘','钟离春智勇定齐','虎牢关三战吕布'},
        '王实甫':{'草桥店梦莺莺(第四本)','崔莺莺夜听琴(第二本)','张君瑞闹道场(第一本)',
                  '张君瑞害相思(第三本)','四丞相高会丽春堂','吕蒙正风雪破窑记'},
    }
    for index,p in enumerate(read(WORK/'sources/chinese-poetry'/yuan_whole)):
        if len(selected['元曲'])>=needed['元曲']:
            break
        parts=p['title'].split('・',1)
        if len(parts)!=2 or parts[0] not in plays.get(p['author'],set()) or parts[1] in ['同上','幺篇','幺','尾']:
            continue
        text='\n'.join(p['paragraphs'])
        if not 40<=len(key(text))<=1500:
            continue
        k=key(text)
        if any(k in old or old in k for old in seen if len(old)>20):
            exclusions['dramatic_tune_overlaps_existing_text']+=1
            continue
        add('元曲',p['title'],p['author'],'元',text,'chinese-poetry/chinese-poetry',yuan_whole,index,
            parts[0],f'节选《{parts[0]}》中的【{parts[1]}】所据完整数据条目；保留附带宾白和舞台括注，不是全剧，也不虚拟折次。',
            preserve_brackets=True)

    # Whole numbered maxims and whole named chapters, not arbitrary sentence splits.
    prose_file='子部/儒家类.json'
    books=read(WORK/'sources/poems-db'/prose_file)['儒家类']
    for name,quota in [('围炉夜话',75),('国语',35)]:
        book=next(b for b in books if b['nameStr']==name)
        before=len(selected['古文'])
        for index,view in enumerate(book['book']['tb_bookviews']['bookviews']):
            original=view['content']['tb_bookview']
            text=clean(original.get('cont') or '')
            if len(key(text))>2000:
                continue
            add('古文',name+'·'+original['nameStr'], '王永彬' if name=='围炉夜话' else '左丘明（旧题）',
                '清' if name=='围炉夜话' else '先秦',text,'yxcs/poems-db',prose_file,
                dict(book=name,view=index),name,f'完整选录《{name}》中“{original["nameStr"]}”一则或一章；非全书。')
            if len(selected['古文'])-before>=quota:
                break
    for chapter,ch in enumerate(read(WORK/'sources/chinese-poetry/论语/lunyu.json')):
        for paragraph,text in enumerate(ch['paragraphs']):
            if 25<=len(key(text))<=160:
                add('古文',f'论语·{ch["chapter"]}·{paragraph+1}','孔子及其弟子','先秦·春秋',text,
                    'chinese-poetry/chinese-poetry','论语/lunyu.json',dict(chapter=chapter,paragraph=paragraph),
                    '论语·'+ch['chapter'],f'完整选录所据数据本篇第{paragraph+1}段，段号为数据排列位置；非全篇。')

    # When a larger batch exhausts eligible Analects paragraphs, use more whole
    # named Guoyu chapters rather than splitting a dialogue into fragments.
    if len(selected['古文']) < needed['古文']:
        book=next(b for b in books if b['nameStr']=='国语')
        for index,view in enumerate(book['book']['tb_bookviews']['bookviews']):
            original=view['content']['tb_bookview']
            text=clean(original.get('cont') or '')
            if len(key(text))>2000:
                continue
            add('古文','国语·'+original['nameStr'],'左丘明（旧题）','先秦',text,'yxcs/poems-db',
                prose_file,dict(book='国语',view=index),'国语',
                f'完整选录《国语》“{original["nameStr"]}”一章；非全书。')
            if len(selected['古文']) >= needed['古文']:
                break

    history_file='史部/杂史类.json'
    if len(selected['古文'])<needed['古文'] and (WORK/'sources/poems-db'/history_file).exists():
        history=read(WORK/'sources/poems-db'/history_file)
        book=next(b for bs in history.values() for b in bs if b['nameStr']=='战国策')
        for index,view in enumerate(book['book']['tb_bookviews']['bookviews']):
            if len(selected['古文'])>=needed['古文']:
                break
            original=view['content']['tb_bookview']
            text=clean(original.get('cont') or '')
            if not 40<=len(key(text))<=2500:
                continue
            add('古文','战国策·'+original['nameStr'],'刘向（编）','西汉',text,'yxcs/poems-db',
                history_file,dict(book='战国策',view=index),'战国策',
                f'完整选录所据《战国策》“{original["nameStr"]}”条目；非全书，编者署刘向，不据此虚拟原篇作者。')

    for c in CATS:
        if len(selected[c]) != needed[c]:
            raise ValueError(f'{c}: selected {len(selected[c])}, need {needed[c]}')
    rows=[]
    locations=defaultdict(dict)
    for cat,prefix in CATS.items():
        next_id=1+max(int(p['id'].split('-')[-1]) for p in production['items'] if p['category']==cat)
        for index,p in enumerate(selected[cat],next_id):
            iid=f'{prefix}-{index:03}'
            title=p['title']
            subtitle=''
            if cat=='元曲':
                # Keep source tune/title as supplied; preserve a readable full title.
                title=re.sub(r'[【】]', '', title)
                if not any(c in title for c in ['·','・']):
                    subtitle=re.split('[，。！？；]',p['content'])[0]
            elif cat!='古文' and '·' in title:
                title,subtitle=title.split('·',1)
            text=p['content']
            if cat=='唐诗':
                text=re.sub(r'\s+','',text)
                text=re.sub(r'([。！？])',r'\1\n',text).strip()
            rows.append(dict(id=iid,category=cat,tags=[],title=title,subtitle=subtitle,author=p['author'],
                dynasty=p['dynasty'],excerptOf=p['excerptOf'],excerptNote=p['excerptNote'],content=text,
                translation='',notes=[],editorialStatus='original_only',
                pending=['translation','notes','themeTags','dictionary']))
            locations[p['repo'],p['file']][iid]=p['location']
    version=production['dataVersion'].split('.')
    version[-1]=str(int(version[-1])+1)
    batch=dict(dataVersion='.'.join(version),stage='original_only',baseTotal=len(production['items']),
        targetTotal=len(production['items'])+len(rows),targetActiveTotal=args.target_total,items=rows,provenance=dict(
            policy='负责人批准 D 原文优先。本批不生成、不复用现代译注。',
            sources=[dict(repository='https://github.com/'+repo,file=file,locations=loc)
                     for (repo,file),loc in locations.items()],
            editorialChanges='仅移除来源括注、脚注、HTML及版式空白；保留古字。古文按完整则、章或数据段标注范围。',
            selectionExclusions=dict(exclusions),
            proseSelection=dict(Counter(p['excerptOf'].split('·')[0] for p in selected['古文'])),
            reviewScope='保留完整来源条目或有明确范围的古文章则/数据段，来源与近似重复已筛查；未作逐字版本校勘。'))
    output.write_text(json.dumps(batch,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(dict(batch=output.name,added=len(rows),categories={c:len(v) for c,v in selected.items()},
                          exclusions=dict(exclusions)),ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
