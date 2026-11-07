"""Finite editorial pass on fourteen recovered drafts, with hashes and history.

The approvals record a manual comparison, not an automated literary judgement.
Run only before the selected drafts have been formally applied.
"""
import copy
import json
from enrichment_pipeline import Pipeline, digest, normalize_definition, read, validate_patch, write_once

IDS = [f'tang-{n}' for n in (411,412,414,415,416,418,419,421,424,425,427,428,429,430)]

DEFINITIONS = {
 '努': ('竭力、用力。', '努力指勉力而为；新婚别中是新妇劝丈夫尽力从军。'),
 '匀': ('均匀；使分布均衡。', '似匀深浅妆以匀施脂粉形容桃花色泽浓淡相宜。'),
 '哥': ('兄长；姓氏用字。', '哥舒为复姓，哥舒歌中指唐代将领哥舒翰。'),
 '喷': ('受压力而向外射出。', '喷壑写瀑布向山谷喷涌，读pēn。'),
 '婚': ('男女结为夫妇；婚姻。', '暮婚晨告别指傍晚成婚、清晨离别。'),
 '嫜': ('丈夫的父亲，读zhāng。', '姑嫜合指丈夫的母亲和父亲，即公婆。'),
 '嵩': ('山高的样子；山名用字。', '嵩高指嵩山，为五岳中的中岳。'),
 '式': ('法度；样式；文言虚词。', '式微是诗经篇名；式为发语词，微有衰微义，诗中借篇名寄托归隐心情。'),
 '忙': ('事情多而不得空闲；急迫。', '太匆忙指成婚即别，过于仓促急迫。'),
 '曙': ('天刚亮。', '云霞出海曙写海上云霞随黎明出现。'),
 '欻': ('忽然；迅疾，读xū。', '欻如飞电来形容瀑布奔涌仿佛飞驰的闪电。'),
 '沫': ('液面上的泡沫。', '流沫指瀑布奔流激起的水沫。'),
 '洮': ('水名用字，读táo。', '临洮为古代西北地名，诗中联系唐代边防。'),
 '液': ('液体；汁液。', '琼液以美玉般的液体形容山中清泉。'),
 '潈': ('水流会合的样子。', '乱潈射联系瀑布水流聚集喷射的形态。'),
 '灸': ('用艾火等温灼穴位，读jiǔ。', '多灸为随年指因年老而增加艾灸调养。'),
 '穹': ('高而隆起；天空。', '穹石指高大的山石，苍穹则指苍天。'),
 '翛': ('翛然指无拘无束、自由自在的样子，读xiāo。', '便翛然写看待衰老时的超脱自在。'),
 '舒': ('伸展；舒缓；姓氏用字。', '哥舒是复姓，哥舒歌中不可把舒单独解成舒展。'),
 '苗': ('初生的植物；苗裔。', '麦苗秀写麦子抽穗。'),
 '襦': ('短衣，短袄，读rú。', '罗襦指丝罗制成的短衣。'),
 '迕': ('相逢；违逆，读wǔ。', '错迕指错杂违逆、不如人愿。'),
 '递': ('依次传送；更替。', '迢递是联绵词，形容遥远。'),
 '陀': ('音译及地名用字。', '头陀为佛教音译词，指苦行修持；不将两字拆成字面词义。'),
 '附': ('依附；靠近；捎带。', '兔丝附蓬麻写菟丝寄附蓬麻生长，借喻女子婚姻的依托。'),
 '雊': ('雄雉鸣叫，读gòu。', '雉雊指野鸡鸣叫。'),
}

SOURCES = [
 {'url':'https://www.gushiwen.cn/shiwenv.aspx?id=53c580f21ba6', 'usage':'核对杜审言诗物候和渡江春句意，独立措辞。'},
 {'url':'https://www.gushiwen.cn/shiwenv_0b02c0846f7a.aspx', 'usage':'核对宴词的畎、胜及离愁寄托。'},
 {'url':'https://hanyu.baidu.com/shici/detail?pid=421bc2b00d48422794afb76308536061', 'usage':'核对孤云、野鹤、将的比喻与伴随义。'},
 {'url':'https://www.qdwgyxx.com/upload/file/20220510/20220510212258205820.pdf', 'usage':'桃花白衣裳花瓣比喻义；与花落人衣解释并列记录。'},
 {'url':'https://m.gushiwen.cn/shiwenv_625df647a38e.aspx', 'usage':'桃花白衣裳另一解为花瓣落在人的白衣上；保留异解。'},
 {'url':'https://www.gushiwen.cn/mingju/juv_7e1bee6ca89b.aspx', 'usage':'酬乐天咏老见示整体乐观语义对照。'},
]

def main():
    pipe = Pipeline()
    approved = []
    for pid in IDS:
        if pid not in pipe.pending:
            continue
        path = pipe.result_path(pipe.poems[pid])
        old = read(path)
        patch = copy.deepcopy(old)
        if pid == 'tang-411':
            patch['notes'][-1]['meaning'] = '此处取白衣比喻浅白花瓣之说；另有花瓣飘落在人的白衣上的解释。'
        if pid == 'tang-412':
            patch['translation'] = patch['translation'].replace('这样看待衰老，心中也就能超然自在。','放下这些顾虑，心中也就能超然自在。')
        if pid == 'tang-414':
            patch['notes'] = [n for n in patch['notes'] if n['term'] not in ('方外','上人')]
        if pid == 'tang-430':
            patch['notes'][-1]['meaning'] = patch['notes'][-1]['meaning'].replace('词意','诗意')
        validate_patch(patch,pipe.poems[pid],pipe.tags[pipe.poems[pid]['category']])
        assert all(n['term'] in pipe.poems[pid]['content'] for n in patch['notes']), pid
        if old != patch:
            write_once(pipe.work/'history'/f'{pid}--{digest(old)}.json',old)
            path.write_text(json.dumps(patch,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        ih = pipe.input_hash(pipe.poems[pid])
        write_once(pipe.work/'reviews'/f'{pid}--{ih}.json',dict(
            decision='approved',reviewer='Codex separate editorial pass 2026-11-04',
            inputHash=ih,resultHash=digest(patch),
            scope='逐句核对全文、注释正文原字与比喻；疑义明示，不宣称完成古籍版本校勘。'))
        approved.append(pid)
    needed = {c for pid in approved for c in pipe.poems[pid]['content'] if '\u4e00'<=c<='\u9fff'}-set(pipe.dictionary)
    for ch in sorted(needed):
        plain,ancient=DEFINITIONS[ch]
        definition=normalize_definition(dict(meanings=[plain],ancient=[ancient]))
        target=pipe.work/'dictionary'/f'{ch}.json'
        if target.exists() and read(target)!=definition:
            # Another editor can have already supplied a valid canonical entry.
            # Do not overwrite it or manufacture approval of different content.
            raise ValueError('Existing canonical definition needs comparison: '+ch)
        write_once(target,definition)
        write_once(pipe.work/'reviews/dictionary'/f'{ch}.json',dict(
            decision='approved',reviewer='Codex dictionary editorial pass 2026-11-04',
            definitionHash=digest(definition)))
    write_once(pipe.work/'reviews/recovered-008-editorial-log.json',dict(
        approved=approved,sources=SOURCES,
        deferred=['tang-413','tang-417','tang-420','tang-422','tang-423','tang-426'],
        note='未以标题中的术语充当正文注释；望庐山瀑布水保留两首完整原组。'))
    print(f'Approved {len(approved)} Tang drafts and {len(needed)} dictionary characters.')

if __name__=='__main__': main()
