"""Finite manual comparison of fourteen existing drafts with local references.

No modern reference translation is copied into production by this script.
Edits below record the editor's source/body comparison, not machine approval.
"""
import copy
import json
from enrichment_pipeline import Pipeline, digest, read, write_once, normalize_definition, validate_patch

IDS=[f'tang-{i}' for i in (133,134,135,136,137,138,139,140,142,143,144,145,147,149)]
DEFS={
 '包':('包裹；容纳。','包羞忍耻指承受羞辱，包有容忍义。'),
 '婿':('女儿的丈夫；丈夫。','夫婿指丈夫。'),
 '替':('代替；为。','替人垂泪写蜡烛仿佛代离人流泪。'),
 '栽':('种植；栽种。','满院栽写院中遍植菊花。'),
 '矶':('水边突出的岩石或石滩。','石矶指水边的岩石。'),
 '蕊':('花蕊、花的中心部分。','蕊寒以花蕊受寒写菊花秋日开放。'),
 '陲':('边界；边缘。','南山陲指终南山一带、终南山边。'),
}

def main():
    pipe=Pipeline();_,drafts,_,_=pipe.inspect(); logs=[]
    for pid in IDS:
        if pid not in pipe.pending:continue
        poem=pipe.poems[pid]; record=drafts[pid]; old=record['patch']; patch=copy.deepcopy(old)
        refs=sorted((pipe.work/'references').glob(pid+'--*.json'))
        if not refs:raise ValueError('No matched reference: '+pid)
        reference=read(refs[0])
        assert reference['inputHash']==pipe.input_hash(poem)
        if pid=='tang-134':
            patch['translation']=patch['translation'].replace('忍受羞辱、包藏耻辱','承受失败带来的羞辱')
            patch['notes'][1]['meaning']='承受羞辱、忍耐耻辱，写遭遇失败后仍能坚忍。'
        if pid=='tang-137':
            patch['translation']=patch['translation'].replace('黄鹤楼中有人吹奏玉笛，五月的江城仿佛飘落了梅花。','黄鹤楼上传来玉笛吹奏的《梅花落》，使五月的江城仿佛也飘起了梅花。')
        if pid=='tang-138':patch['translation']=patch['translation'].replace('送走了南飞的大雁群','送来了一群群南飞的大雁')
        if pid=='tang-144':patch['translation']=patch['translation'].replace('荷花飘零，你还来不及知晓','花叶已凋零，你却还不知道')
        if pid=='tang-145':
            patch['translation']=patch['translation'].replace('我下马请你饮酒','请你下马来喝一杯酒')
            patch['notes'][-1]['meaning']='山间无尽的白云，烘托归隐生活的闲适自在。'
        validate_patch(patch,poem,pipe.tags[poem['category']])
        assert all(n['term'] in poem['content'] for n in patch['notes'])
        path=pipe.result_path(poem)
        if old!=patch:
            write_once(pipe.work/'history'/f'{pid}--{digest(old)}.json',old)
            path.write_text(json.dumps(patch,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
        else:write_once(path,patch)
        ih=pipe.input_hash(poem)
        write_once(pipe.work/'reviews'/f'{pid}--{ih}.json',dict(decision='approved',
            reviewer='Codex source-first editorial comparison 2026-11-04',inputHash=ih,resultHash=digest(patch),
            referencePacket=pipe.relative(refs[0]),scope='对照正文及本地参考核对全篇，修正语义；不构成专家审定或源文版本校勘。'))
        logs.append(dict(id=pid,reference=pipe.relative(refs[0]),edited=old!=patch))
    required={c for x in logs for c in pipe.poems[x['id']]['content'] if '\u4e00'<=c<='\u9fff'}-set(pipe.dictionary)
    for ch in sorted(required):
        a,b=DEFS[ch];entry=normalize_definition(dict(meanings=[a],ancient=[b]))
        write_once(pipe.work/'dictionary'/f'{ch}.json',entry)
        write_once(pipe.work/'reviews/dictionary'/f'{ch}.json',dict(decision='approved',
            reviewer='Codex contextual dictionary review 2026-11-04',definitionHash=digest(entry)))
    write_once(pipe.work/'reviews/reference-pilot-v1.0.0.json',dict(entries=logs,
        policy='既有草稿与原文、参考对照后编辑；不整批照搬来源现代译注。'))
    print('Reviewed:',len(logs),'dictionary:',len(required))

if __name__=='__main__':main()
