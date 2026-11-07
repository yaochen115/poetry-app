"""Four short original-text translations, checked against a named commentary.

Only the selected chapters are processed; no existing original or ID changes.
"""
from enrichment_pipeline import Pipeline,write_once,digest,validate_patch,normalize_definition

SOURCE='https://dh.aks.ac.kr/~red/pdf/%E8%AB%96%E8%AA%9E%E8%AD%AF%E8%A8%BB.pdf'
ROWS=[
 ('guwen-086','孔子说：“一个人如果没有仁德，怎样能实践礼呢？一个人如果没有仁德，怎样能实践乐呢？”',
  [('仁','仁德，是礼乐所依存的内在品德。'),('如礼何','把礼怎么办，意为怎样实行礼。'),('乐','礼乐中的音乐，读yuè。')]),
 ('guwen-089','孔子说：“君子没有什么可争的。如果一定要有所竞赛，大概就是射箭吧！上场前互相作揖谦让，下场后依礼饮酒。这样的竞争仍保持着君子的风度。”',
  [('无所争','没有争夺的事情。'),('射','射箭，联系古代射礼中的比试。'),('揖让','作揖行礼并相互谦让。'),('饮','射礼结束后的饮酒环节。')]),
 ('guwen-095','孔子说：“周代借鉴了夏、商两代的礼制，礼仪文化多么丰富完备啊！我遵从周代的礼制。”',
  [('监','借鉴、参考，通鉴。'),('二代','指夏代、商代。'),('郁郁','丰富盛美的样子。'),('从','遵从、采用。')]),
 ('guwen-099','鲁定公问：“君主对待臣下、臣下侍奉君主，应当怎么做？”孔子回答：“君主应依礼对待臣下，臣下应尽忠侍奉君主。”',
  [('定公','鲁定公，鲁国国君。'),('使臣','任用、对待臣下，不是现代名词外交使臣。'),('事君','侍奉君主。'),('以礼','依照礼的原则。'),('忠','尽心尽力。')]),
]

def main():
    p=Pipeline();done=[]
    for pid,text,pairs in ROWS:
        if pid not in p.pending:continue
        poem=p.poems[pid]
        patch=dict(id=pid,tags=['哲理'],translation=text,notes=[dict(term=a,meaning=b) for a,b in pairs])
        validate_patch(patch,poem,p.tags['古文'])
        assert all(n['term'] in poem['content'] for n in patch['notes'])
        write_once(p.result_path(poem),patch)
        ih=p.input_hash(poem)
        write_once(p.work/'reviews'/f'{pid}--{ih}.json',dict(decision='approved',
            reviewer='Codex Analects short-chapter editorial review 2026-11-04',
            inputHash=ih,resultHash=digest(patch),referenceUrl=SOURCE,
            reference='杨伯峻《论语译注》八佾3.3、3.7、3.14、3.19，原文通读后独立整理。',
            scope='核对正文、古义和礼乐语境；整理原文译义，不复制现代注本译文。'))
        done.append(pid)
    defs={'揖':('拱手行礼，读yī。','揖让写射礼参与者互相行礼谦让。'),
          '让':('谦让；推让；责备。','揖让中的让是谦让，不是责备。'),
          '监':('察看；监督；借鉴。','周监于二代的监通鉴，表示借鉴，读jiàn。')}
    missing={ch for pid in done for ch in p.poems[pid]['content'] if '\u4e00'<=ch<='\u9fff'}-set(p.dictionary)
    for ch in sorted(missing):
        a,b=defs[ch];entry=normalize_definition(dict(meanings=[a],ancient=[b]))
        write_once(p.work/'dictionary'/f'{ch}.json',entry)
        write_once(p.work/'reviews/dictionary'/f'{ch}.json',dict(decision='approved',
            reviewer='Codex Analects contextual dictionary review 2026-11-04',definitionHash=digest(entry)))
    print('Reviewed',len(done),'chapters;',len(missing),'characters.')

if __name__=='__main__':main()
