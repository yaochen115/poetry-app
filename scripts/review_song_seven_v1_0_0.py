"""Seven Song drafts independently edited against originals and local references.

Reference errors are retained as review issues, not silently copied into data.
"""
from enrichment_pipeline import Pipeline,read,write_once,digest,validate_patch,normalize_definition
ROWS=[
 ('song-082',['爱情','感遇'],
  '微微的汗浸透了碧色薄绢，明天便是端午，要用芳香的兰草沐浴。带着香气与脂粉的浴水，仿佛流满了晴日的河川。五彩丝线轻轻缠住如玉的手臂，小小的符箓斜挂在浓密乌发的发髻上。愿与佳人相会相守，直到千年。',
  [('碧纨','碧色的细绢，纨读wán。'),('明朝','明天，朝读zhāo。'),('浴芳兰','用芳香兰草沐浴，联系端午浴兰习俗。'),('流香涨腻','以香气和脂粉随浴水流出写女子沐浴，带有夸张意味。'),('彩线','端午缠臂的五彩丝线。'),('小符','端午佩戴以祈平安的小符箓。'),('绿云鬟','以绿云比喻浓密乌发，鬟指发髻。')]),
 ('song-084',['闺怨','感遇'],
  '黄莺啄弄着红艳的花，燕尾点过水面，荡起绿波。手指发冷，玉笙也透着寒意；一曲《小梅》吹尽，春意渐浓。依旧啊，依旧，人和绿杨还是那样消瘦。',
  [('红溜','形容花色红润、鲜明。'),('绿皱','碧绿水面荡起的细纹。'),('玉笙','精美的笙，笙为管乐器。'),('小梅','乐曲名，通常联系《小梅花》。'),('彻','尽、完，吹彻指吹完一曲。'),('俱','都、一同。')]),
 ('song-086',['离别','爱情'],
  '想留的人终究留不住，他带着醉意解开船缆离去了。一船划过碧波春水，经过那清晨黄莺啼鸣的地方。渡口杨柳青青，枝枝叶叶都寄着离情。从此不要再寄来情书了，画楼中旧日的亲密欢会，原来这样靠不住。',
  [('解','解开船缆。'),('兰舟','船的美称。'),('一棹','一船，棹本指船桨。'),('锦书','书信的美称，此处联系情书。'),('云雨','借指男女之间的欢会。'),('无凭','没有凭据、不可靠。')]),
 ('song-087',['哲理','感遇'],
  '水与污垢何曾彼此相容？细细看来，水和垢又都不是实有。告诉那位替我搓背的人：整天劳烦你挥动胳膊了。轻一点，再轻一点，居士本来就没有垢呀。',
  [('相受','彼此容受、相容。'),('两俱无有','水与垢都无实有，联系佛教空观的语意。'),('揩背','擦洗背部，揩读kāi。'),('挥肘','挥动手臂，肘读zhǒu。'),('居士','在家修佛之人的称呼，词中作者自称。'),('无垢','既指洗浴的污垢，又含心地清净的禅意。')]),
 ('song-090',['爱情'],
  '花色鲜明，月光暗淡，薄雾轻轻笼罩着，今夜正好到情郎身边去。我只穿着袜子走过台阶，手里提着金线装饰的鞋。在画堂南边相见，依偎着他，身体还在微微发颤。我出来一趟实在不容易，就请你好好疼爱我吧。',
  [('刬袜','只穿袜子、不着鞋地行走，刬读chǎn。'),('香阶','台阶的美称。'),('金缕鞋','用金线装饰的鞋。'),('一向','此处联系一晌、片刻的解释，另有一直之解；译文不强定持续时长。'),('奴','古代女子自称。'),('恣意','尽情、任意。'),('怜','爱怜、疼爱。')]),
 ('song-092',['感遇'],
  '天上的银河转动，人间的帘幕低垂，枕席渐凉，泪痕也不断增多。起身解开罗衣，姑且问一声：夜已经到什么时候了？衣上有贴翠工艺制成的小莲蓬纹，还有疏疏的销金荷叶纹。同样的时节，同样的衣裳，只有此刻的心情，再不像从前。',
  [('星河','银河。'),('枕簟','枕头与竹席，簟读diàn。'),('滋','增多。'),('夜何其','夜到什么时候了；其为语助成分，句意承《诗经·庭燎》。'),('翠贴','即贴翠，服饰装饰工艺，不直接等同于翠线绣花。'),('金销','即销金，以金装饰织物的工艺。'),('旧家时','从前的时候，家为语助成分。')]),
 ('song-093',['感遇'],
  '带着醉意驾一叶轻舟荡漾，任流水把我引到繁花深处。尘世的牵累误了我，使我无法长住花间。烟霭与水色迷茫，千里斜阳渐入暮色。山峦无数，落花如雨，竟已不记得来时的路。',
  [('漾','在水上飘荡。'),('信流','听任流水引导。'),('尘缘','尘世的牵系和因缘。'),('无计','没有办法。'),('乱红','纷乱飘落的花。')]),
]
DEFS={
 '偎':('亲近地靠着。','偎人写女子紧靠所爱的人。'),
 '垢':('污秽、污垢。','无垢在浴词中兼含洗浴与禅理双关。'),
 '揩':('擦拭、摩擦，读kāi。','揩背指替人擦洗背部。'),
 '漾':('水波动荡；浮动。','漾轻舟写小舟在水上荡漾。'),
 '纨':('细致的白绢、细绢，读wán。','碧纨指碧色细绢，不从旧参考误读为wàn。'),
 '肘':('上臂和前臂相接的部位，读zhǒu。','挥肘以肘部动作写手臂反复擦洗。'),
 '颤':('身体或物体发抖；颤动，读chàn时常表震动。','偎人颤写相见时紧张或激动而发抖，此处读chàn。'),
}

def main():
    p=Pipeline();done=[]
    for pid,tags,text,pairs in ROWS:
        if pid not in p.pending:continue
        poem=p.poems[pid];refs=sorted((p.work/'references').glob(pid+'--*.json'));assert refs
        assert read(refs[0])['inputHash']==p.input_hash(poem)
        patch=dict(id=pid,tags=tags,translation=text,notes=[dict(term=a,meaning=b) for a,b in pairs])
        validate_patch(patch,poem,p.tags['宋词'])
        assert all(n['term'] in poem['content'] for n in patch['notes']),pid
        write_once(p.result_path(poem),patch);ih=p.input_hash(poem)
        write_once(p.work/'reviews'/f'{pid}--{ih}.json',dict(decision='approved',
            reviewer='Codex original/reference semantic comparison 2026-11-04',
            inputHash=ih,resultHash=digest(patch),referencePacket=p.relative(refs[0]),
            scope='逐句对照原文和参考，纠正添译及词义，保留双关和不同解释；独立整理措辞，不逐篇复制参考译文。'))
        done.append(pid)
    chars={ch for pid in done for ch in p.poems[pid]['content'] if '\u4e00'<=ch<='\u9fff'}-set(p.dictionary)
    for ch in chars:
        a,b=DEFS[ch];entry=normalize_definition(dict(meanings=[a],ancient=[b]))
        write_once(p.work/'dictionary'/f'{ch}.json',entry)
        write_once(p.work/'reviews/dictionary'/f'{ch}.json',dict(decision='approved',
            reviewer='Codex Song contextual dictionary review 2026-11-04',definitionHash=digest(entry)))
    write_once(p.work/'reviews/song-seven-v1.0.0.json',dict(approved=done,
        sourceProblems=['旧参考纨注为wàn，按常用字读音改wán。','秦观如梦令旧参考添入亢奋、宏亮、潇洒清秀等原文无据内容。',
            '浴词旧参考以今日代尽日；李煜词注将夜雾写成晨雾。','南歌子旧译把贴翠销金硬解为丝绣并推定旧衣缩小，改保留工艺和纹样的原文描述。'],
        deferred=['song-083','song-085','song-089','song-091']))
    print('Reviewed',len(done),'Song poems;',len(chars),'characters.')

if __name__=='__main__':main()
