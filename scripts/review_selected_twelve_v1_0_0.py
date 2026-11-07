"""Finite editorial pass; original group texts are retained as single records."""
import copy,json
from enrichment_pipeline import Pipeline,read,write_once,digest,validate_patch,normalize_definition
IDS=[f'tang-{n}' for n in (185,186,195,201,205,213,220,222,223,225,227,228)]
DEFS={
 '亥':('地支第十二位；用于人名。','朱亥为战国时信陵君的门客。'),
 '侠':('仗义助人的人；侠义。','侠客行写侠士重诺守义的精神。'),
 '凰':('用于凤凰一词，传说中的神鸟。','凤凰叫以神鸟鸣声形容箜篌乐声。'),
 '吐':('从口中出来；说出。','吐然诺指说出承诺、作出许诺。'),
 '嗾':('唤狗的声音；唆使、挑动，读sǒu。','嗾人狂写春色撩拨人心。'),
 '娲':('用于女娲，神话人物名，读wā。','女娲炼石采用炼石补天的神话意象。'),
 '嬴':('姓氏，读yíng。','侯嬴是战国时信陵君门客，曾谋划救赵。'),
 '昆':('兄长；众；山名等用字。','昆山玉碎借美玉碎裂的声音形容乐声清脆。'),
 '栋':('房屋的大梁。','画栋指装饰华美的栋梁。'),
 '槌':('敲打所用的棒、锤。','金槌联系朱亥击杀晋鄙、帮助救赵的故事。'),
 '沓':('重复、众多；合在一起。','飒沓形容飞驰迅疾，沓在这里读tà。'),
 '炼':('用火冶制、加工；锤炼。','炼石联系女娲炼石补天的神话。'),
 '烜':('盛大、显著，读xuǎn。','烜赫指声名显赫、声势盛大。'),
 '禾':('谷类作物。','锄禾指给禾苗松土除草。'),
 '笳':('胡笳，古代管乐器，读jiā。','胡笳声在边塞诗中常联系征戍和思乡。'),
 '箜':('用于箜篌，古代拨弦乐器，读kōng。','与篌连用，联系乐工李凭的演奏。'),
 '篌':('用于箜篌，古代拨弦乐器，读hóu。','与箜连用，不拆解成另一件乐器。'),
 '缸':('盛物的器具；古通釭。','兰缸指灯具，不能按现代水缸理解。'),
 '蒿':('蒿草，草本植物的泛称，读hāo。','蓬蒿在诗中借指草野。'),
 '赫':('显著、显赫；红色。','烜赫写壮士名声显赫。'),
 '跨':('迈越；骑乘。','新跨白玉鞍写刚跨上配着白玉鞍的马，不把新误解为刚配鞍。'),
 '辈':('同一类的人；辈分。','我辈指我们这些人。'),
 '逗':('停留；引出。','逗秋雨指引落秋雨。'),
 '邯':('用于邯郸，地名。','侠客行中邯郸为赵国都城，联系信陵君救赵。'),
 '郸':('用于邯郸，地名。','与邯连用，古城在今河北邯郸一带。'),
 '鞭':('驱赶牲畜的工具；以鞭驱策。','著鞭跨马写扬鞭上马，踏上远行之路。'),
 '韭':('韭菜，多年生草本，叶可食。','剪春韭写主人雨夜剪取春韭招待友人。'),
 '骝':('黑鬃黑尾的红马，读liú。','骝马为骏马，诗中用其衬托将士英姿。'),
}
SOURCES={
 'tang-205':'https://www.gushiwen.cn/shiwenv_6e6d79655f69.aspx',
 'tang-228':'https://www.gushiwen.cn/mingju/juv_612367c0dadd.aspx',
 'tang-223':'https://www.gushiwen.cn/mingju/juv_300c41b8dbaa.aspx',
}

def main():
    p=Pipeline();_,drafts,_,_=p.inspect();done=[]
    for pid in IDS:
        if pid not in p.pending:continue
        r=drafts[pid];old=r['patch'];patch=copy.deepcopy(old);poem=p.poems[pid]
        if pid=='tang-185':
            patch['translation']=patch['translation'].replace('泥土融化松软','泥土湿润松软')
            patch['notes'][1]['meaning']='泥土湿润松软。'
            patch['notes'][2]['meaning']='更加。'
        if pid=='tang-186':patch['translation']=patch['translation'].replace('请朱亥吃肉','拿烤肉请朱亥食用')
        if pid=='tang-195':
            patch['translation']=patch['translation'].replace('碗中的饭食','盘中的饭食')
            patch['notes'][-1]['meaning']='盘中的饭食。'
        if pid=='tang-201':
            patch['translation']=patch['translation'].replace('乌鸦啼叫，喜鹊喧噪，黄昏时分栖满高大的树木','乌鸦啼叫，喜鹊喧噪，高大的树木一片昏暗')
            patch['translation']=patch['translation'].replace('九泉之下昏暗深沉，哭声再大也听不见','幽暗的黄泉之下，逝者再也听不见地上的哭声')
        if pid=='tang-205':
            patch['translation']=patch['translation'].replace('骑着新配上白玉鞍的赤红骏马','刚跨上配着白玉鞍的骝马')
            patch['notes'][0]['meaning']='借汉代名将赞叹良将。具体所指有李广、卫青及合用两者事迹等解释，译文不限定唯一人选。'
        if pid=='tang-220':patch['translation']=patch['translation'].replace('秦中的花鸟想来已经凋残','长安一带的花时鸟语想来已渐渐阑珊')
        if pid=='tang-223':
            patch['notes'].append(dict(term='千金笑',meaning='形容美丽女子的笑容。'))
            patch['notes'][-3]['meaning']='一干多枝的灯具，此处称九枝灯。'
        if pid=='tang-225':
            patch['notes'].append(dict(term='游说',meaning='以言辞劝说君王；说读shuì。'))
            patch['notes'].append(dict(term='白酒',meaning='此处是新酿的米酒，不按现代蒸馏白酒理解。'))
        if pid=='tang-227':patch['notes'][-1]['meaning']='栏杆，此处读jiàn。'
        if pid=='tang-228':
            patch['translation']=patch['translation'].replace('在深秋调好了弦','在深秋奏响')
            patch['translation']=patch['translation'].replace('乐声仿佛传入神山，教神妪弹奏','幻境中仿佛李凭进入神山，把弹奏技艺传授给神女')
            patch['notes'].append(dict(term='中国',meaning='此处指国都长安，不是现代国家名称的用法。'))
            patch['notes'][4]['meaning']='字面为天上的神帝，也有借指人间帝王的解释，诗的描写联系二者。'
        validate_patch(patch,poem,p.tags[poem['category']])
        assert all(n['term'] in poem['content'] for n in patch['notes']),pid
        path=p.result_path(poem)
        if old!=patch:
            write_once(p.work/'history'/f'{pid}--{digest(old)}.json',old)
            path.write_text(json.dumps(patch,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        else:write_once(path,patch)
        refs=[p.relative(f) for f in sorted((p.work/'references').glob(pid+'--*.json'))]
        write_once(p.work/'reviews'/f"{pid}--{r['inputHash']}.json",dict(decision='approved',
            reviewer='Codex selected-group editorial pass 2026-11-04',inputHash=r['inputHash'],resultHash=digest(patch),
            references=refs,additionalReferenceUrl=SOURCES.get(pid),
            scope='逐句通读原文和草稿、核对可用参考，修正词义主体和时序；组作完整保留，争议注释列出异解。'))
        done.append(pid)
    chars={ch for pid in done for ch in p.poems[pid]['content'] if '\u4e00'<=ch<='\u9fff'}-set(p.dictionary)
    for ch in chars:
        a,b=DEFS[ch];entry=normalize_definition(dict(meanings=[a],ancient=[b]))
        write_once(p.work/'dictionary'/f'{ch}.json',entry)
        write_once(p.work/'reviews/dictionary'/f'{ch}.json',dict(decision='approved',
            reviewer='Codex selected-context character review 2026-11-04',definitionHash=digest(entry)))
    write_once(p.work/'reviews/selected-twelve-v1.0.0.json',dict(approved=done,
        deferred=['tang-180','tang-191','tang-197','tang-207'],
        note='四篇分别因作者归属、未足句义、和亲主体、昨风文本疑点待核，不为凑满数量批准。'))
    print('Reviewed',len(done),'poems and',len(chars),'characters.')

if __name__=='__main__':main()
