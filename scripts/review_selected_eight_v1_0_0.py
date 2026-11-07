"""Finite manual editorial pass over eight selected poems and twenty characters.

Preserves original text and prior drafts. Reviews describe the actual scope;
they do not assert that competing historical interpretations are settled.
"""
import copy,hashlib,json
from enrichment_pipeline import Pipeline,read,write_once,digest,normalize_definition,validate_patch

IDS=['tang-155','tang-157','tang-158','tang-161','tang-164','tang-166','tang-168','tang-169']
DEFS={
 '充':('填满；充当。','充饥指填饱肚子，充炭直指抵作木炭的价钱。'),
 '惘':('失意；迷惘。','惘然写怅惘迷茫、若有所失的心情。'),
 '愧':('惭愧。','私自愧写诗人因自己不事农桑却领取俸禄而感到惭愧。'),
 '捉':('捕捉；捉拿。','夜捉人写官吏夜间抓人征役。'),
 '敕':('帝王的诏令；告诫，读chì。','口称敕指口口声声宣称奉有皇帝命令。'),
 '浣':('洗涤，读huàn。','浣女指洗衣服的女子。'),
 '灼':('烧；烤，读zhuó。','背灼炎天光写背部受烈日烤晒。'),
 '炊':('烧火做饭。','备晨炊指准备早饭。'),
 '禄':('官吏的俸给。','吏禄指为官领取的俸禄。'),
 '秉':('持；拿着，读bǐng。','秉遗穗指手中拿着拾来的麦穗。'),
 '税':('征收的赋税；缴纳赋税。','输税指缴纳赋税。'),
 '穗':('谷类作物聚生花实的部分。','遗穗指收割后遗落田间的麦穗。'),
 '筐':('用竹篾或柳条等编成的盛物器。','敝筐指破旧的筐。'),
 '粮':('粮食。','余粮指剩余粮食，与贫妇充饥的困境形成对照。'),
 '绫':('有花纹的丝织品。','一丈绫与半匹红绡是宫使强充炭价的丝织物。'),
 '翩':('轻快飞动的样子。','翩翩写宫使骑马轻快而来的姿态，带有讽刺意味。'),
 '蝴':('用于蝴蝶一词，昆虫名。','晓梦迷蝴蝶用庄周梦蝶的典故。'),
 '辗':('滚动、碾轧；辗转又指翻转。','辗冰辙的辗通碾，写车轮碾过冰冻车辙。'),
 '陇':('山名、地名用字；同垄时指田埂或田地。','覆陇黄写田垄上遍布成熟发黄的小麦。'),
 '饷':('送饭；以食物款待；军粮或薪给。','饷田指往田间给劳作者送饭，读xiǎng。'),
}

def main():
    pipe=Pipeline();_,drafts,_,_=pipe.inspect();log=[]
    for pid in IDS:
        if pid not in pipe.pending:continue
        poem=pipe.poems[pid];r=drafts[pid];old=r['patch'];patch=copy.deepcopy(old)
        source=next((pipe.root/'expansion/site-selected/known-v1.0.1').glob(pid+'--*.json'))
        meta=read(source);assert meta.get('status')==200 and meta.get('translationHeadingFound'),pid
        raw=source.parent/(pid+'--'+meta['sha256']+'.html')
        assert hashlib.sha256(raw.read_bytes()).hexdigest()==meta['sha256']
        if pid=='tang-155':
            patch['translation']=patch['translation'].replace('王孙自可留下','我自然可以留下长住')
            patch['notes'][2]['meaning']='洗衣服的女子，浣读huàn。'
        if pid=='tang-157':
            patch['notes'][2]['meaning']='向秀经过嵇康旧居闻笛而作《思旧赋》的典故，诗中借以怀念故友。'
            patch['notes'][-1]['meaning']='振作精神，长读zhǎng。'
        if pid=='tang-158':
            patch['tags']=['咏怀']
            patch['notes'].append(dict(term='情人',meaning='有情之人、多情的人，不能只按现代恋人一义理解。'))
        if pid=='tang-161':
            patch['translation']=patch['translation'].replace('他母亲还没有改嫁离去','他的母亲还留在家里')
            patch['notes'].append(dict(term='去',meaning='离开；母未去写孩子的母亲仍留在家里。'))
        if pid=='tang-164':
            patch['notes'].append(dict(term='红绡',meaning='红色丝织物；网站及部分版本作红纱并注明红绡异文，此处保留项目原文字形。'))
        if pid=='tang-166':
            patch['translation']=patch['translation'].replace('筋疲力尽也不觉得热','筋疲力尽也顾不上炎热')
            patch['notes'].append(dict(term='石',meaning='古代容量单位，计算粮食、俸禄时读dàn。'))
            patch['notes'][1]['meaning']='用竹制食器盛的饭食；箪读dān，食在这个名词组合中读shí。'
        if pid=='tang-168':
            patch['notes'].append(dict(term='珠有泪',meaning='用鲛人泣珠的传说；此诗寄意有悼亡、自伤生平等多种解释，不据此断定唯一主旨。'))
        if pid=='tang-169':
            patch['translation']=patch['translation'].replace('历经艰难苦恨，两鬓如霜','国事和身世艰难，深憾鬓发愈加斑白')
            patch['notes'].append(dict(term='苦恨',meaning='极其遗憾、深深怅恨；苦有极、甚的意思。'))
            patch['notes'].append(dict(term='新停',meaning='刚刚停止，通行注释联系诗人晚年因病戒酒。'))
        validate_patch(patch,poem,pipe.tags[poem['category']])
        assert all(n['term'] in poem['content'] for n in patch['notes']),pid
        path=pipe.result_path(poem)
        if old!=patch:
            write_once(pipe.work/'history'/f'{pid}--{digest(old)}.json',old)
            path.write_text(json.dumps(patch,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        else:write_once(path,patch)
        write_once(pipe.work/'reviews'/f"{pid}--{r['inputHash']}.json",dict(
            decision='approved',reviewer='Codex selected-poem source comparison 2026-11-04',
            inputHash=r['inputHash'],resultHash=digest(patch),sourceUrl=meta['url'],sourceSha256=meta['sha256'],
            scope='逐句核对正文与网站资料，保留独立措辞，补注语义/读音并明示已知异解；未宣称逐字版本校勘。'))
        log.append(dict(id=pid,source=meta['url'],edited=old!=patch))
    chars={ch for item in log for ch in pipe.poems[item['id']]['content'] if '\u4e00'<=ch<='\u9fff'}-set(pipe.dictionary)
    for ch in sorted(chars):
        a,b=DEFS[ch];definition=normalize_definition(dict(meanings=[a],ancient=[b]))
        write_once(pipe.work/'dictionary'/f'{ch}.json',definition)
        write_once(pipe.work/'reviews/dictionary'/f'{ch}.json',dict(decision='approved',
            reviewer='Codex contextual dictionary review 2026-11-04',definitionHash=digest(definition)))
    write_once(pipe.work/'reviews/selected-eight-v1.0.0.json',dict(items=log,
        deferred=[dict(id='tang-163',reason='后半部分传本及归属须另核'),dict(id='tang-175',reason='移石动云根句义须另核，不照旧稿机械挪石解释')]))
    print('Reviewed',len(log),'poems;',len(chars),'dictionary characters.')

if __name__=='__main__':main()
