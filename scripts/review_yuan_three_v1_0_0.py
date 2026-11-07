"""Source-assisted editorial additions for three selected short Yuan works."""
from enrichment_pipeline import Pipeline,read,write_once,digest,validate_patch,normalize_definition

ROWS=[
 ('yuan-136',['时令','山水'],
  '雪花洁白明亮，像梨花纷纷飞舞，烟霭中的几户村舍已被遮住。密密洒落的雪景足以入画，稀疏的树林里，晚归的乌鸦正在啼叫。清江边枯黄的芦苇掩映着一只斜斜系泊的钓鱼小船。',
  [('雪粉','如粉般洁白的雪。'),('华','光彩，写雪色明亮。'),('堪','可以、值得。'),('黄芦','枯黄的芦苇。'),('缆','用绳索系船。'),('艖','小船，读chā。')],
  'https://www.guwendao.net/shiwenv_d3ba5a3a4d29.aspx'),
 ('yuan-221',['闺怨','爱情'],
  '星光稀疏，月色淡淡，秋千院落十分冷清；美人的脸上布满了愁怨。想到系着红线的燕子，伤感不已；镜中的孤单身影和闲置的团扇，又惹起烦恼。兽形香炉升起沉香的轻烟，碧绿池塘漂着残花。这一切愁绪，都一并写进了相思的篇章。',
  [('芙蓉面','以荷花比喻美丽的面容。'),('燕足留红线','用给燕子系红线、盼它归来的故事寄托相思。'),('鸾影','联系镜中孤单的人影。'),('团扇','圆形的扇子，闲字写其闲置。'),('兽炉','兽形的香炉。'),('沉水','沉水香，即沉香。'),('翠沼','碧绿的池塘，沼读zhǎo。'),('传','记述相思的篇章，传读zhuàn。')],
  'https://www.guwendao.net/shiwenv_e44c347eeea5.aspx'),
 ('yuan-295',['羁旅','思乡'],
  '雨打梧桐，一声声都带着秋意；雨落芭蕉，一点点都添着愁绪。三更时梦回故乡，醒来已经过了三更。灯花落下，棋局还没收拾；叹自己如当年客居新丰旅舍的马周一样，久久滞留异乡。躺在枕上，十年来的往事、远在江南的年老双亲，全都涌上心头。',
  [('归梦','梦中回到故乡。'),('灯花','油灯灯芯燃烧后结成的花状余烬。'),('新丰','借马周困顿时客居新丰旅舍的故事寄寓羁旅，不据此断定作者当时实在新丰。'),('逆旅','旅舍。'),('淹留','长久停留。'),('二老','年老的父母。')],
  'https://www.gushiwen.cn/GuShiWen.aspx?id=5c309a08ac'),
]

def main():
    pipe=Pipeline();done=[]
    for pid,tags,translation,pairs,url in ROWS:
        if pid not in pipe.pending:continue
        poem=pipe.poems[pid]
        refs=sorted((pipe.work/'references').glob(pid+'--*.json'));assert refs
        reference=read(refs[0]);assert reference['inputHash']==pipe.input_hash(poem)
        patch=dict(id=pid,tags=tags,translation=translation,notes=[dict(term=a,meaning=b) for a,b in pairs])
        validate_patch(patch,poem,pipe.tags['元曲'])
        assert all(n['term'] in poem['content'] for n in patch['notes'])
        write_once(pipe.result_path(poem),patch)
        ih=pipe.input_hash(poem)
        write_once(pipe.work/'reviews'/f'{pid}--{ih}.json',dict(decision='approved',
            reviewer='Codex Yuan source/body editorial review 2026-11-04',inputHash=ih,resultHash=digest(patch),
            referencePacket=pipe.relative(refs[0]),referenceUrl=url,
            scope='对照正文及已有译注整理，保留原字；新丰按典故解释，不照搬参考中的枕中记作者归属。'))
        done.append(pid)
    defs={'沼':('池塘，读zhǎo。','翠沼指碧绿的池塘。'),
          '粉':('细末；白色或粉红色。','雪粉以细白的粉末形容雪。'),
          '艖':('小船，读chā。','钓鱼艖指供钓鱼使用的小船。')}
    chars={ch for pid in done for ch in pipe.poems[pid]['content'] if '\u4e00'<=ch<='\u9fff'}-set(pipe.dictionary)
    for ch in chars:
        a,b=defs[ch];entry=normalize_definition(dict(meanings=[a],ancient=[b]))
        write_once(pipe.work/'dictionary'/f'{ch}.json',entry)
        write_once(pipe.work/'reviews/dictionary'/f'{ch}.json',dict(decision='approved',
            reviewer='Codex Yuan dictionary contextual review 2026-11-04',definitionHash=digest(entry)))
    print('Reviewed',len(done),'Yuan works;',len(chars),'characters.')

if __name__=='__main__':main()
