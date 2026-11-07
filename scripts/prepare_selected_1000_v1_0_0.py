"""Propose anthology-based 300/300/300/100 candidates; do not silently activate.

Popularity is not inferred from translation completeness. Selection evidence
and weak-evidence entries are exposed for editorial review.
"""
import sys,json,re,hashlib,shutil
from pathlib import Path
from collections import defaultdict,Counter
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'expansion/python-packages'))
from opencc import OpenCC
from enrichment_pipeline import read,write_once,digest

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cc=OpenCC('t2s')
    def norm(s):return re.sub(r'[^\u3400-\u9fff〇]','',cc.convert(s))
    poems=read(ROOT/'data/poems.json');disabled={x['id'] for x in poems['disabledEntries']}
    checkpoint=ROOT/'expansion/checkpoints/pre-selected-1000-v1.0.0'
    for name in ['poems.json','dict.json','categories.json']:
        write_once(checkpoint/name,read(ROOT/'data'/name))
    refs=defaultdict(list)
    for file in sorted((ROOT/'expansion/sources/chinese-gushiwen/guwen').glob('*.json')):
        text=file.read_text(encoding='utf-8')
        try:rows=json.loads(text)
        except json.JSONDecodeError:rows=[json.loads(x) for x in text.splitlines() if x.strip()]
        for n,r in enumerate(rows):
            if isinstance(r,dict) and isinstance(r.get('content'),str):
                refs[norm(r['content'])].append((r,file.relative_to(ROOT).as_posix(),n))
    target={'唐诗':300,'宋词':300,'元曲':300,'古文':100};chosen=[];summary={}
    for cat,count in target.items():
        candidates=[]
        for p in poems['items']:
            if p['id'] in disabled or p['category']!=cat:continue
            evidence=[];score=0;reference=[]
            # The initial 200 constitute the previously curated baseline.
            if int(p['id'].split('-')[1])<=50:score+=100;evidence.append('原始人工精选200篇基线')
            for r,file,row in refs.get(norm(p['content']),[]):
                if norm(r.get('writer',''))!=norm(p['author']):continue
                types=r.get('type',[])
                if isinstance(types,str):types=[types]
                tags=' '.join(types)
                found=[t for t in ['唐诗三百首','宋词三百首','元曲三百首','古文观止','小学古诗','初中古诗','高中古诗','初中文言文','高中文言文'] if t in tags]
                reference.append(dict(file=file,row=row,title=r.get('title'),tags=types,
                    hasTranslation=bool(r.get('translation','').strip()),hasNotes=bool(r.get('remark','').strip())))
                for t in found:
                    if t not in evidence:evidence.append(t);score+=80 if '三百' in t or t=='古文观止' else 60
            # Selection review flag is explicit; source availability alone is not fame.
            if reference:score+=10
            candidates.append(dict(id=p['id'],title=p['title'],author=p['author'],category=cat,
                score=score,evidence=evidence,referenceLocations=reference,
                complete=bool(p.get('translation','').strip()),
                requiresPopularityReview=not bool(evidence)))
        candidates.sort(key=lambda x:(-x['score'],int(x['id'].split('-')[1])))
        selection=candidates[:count];assert len(selection)==count
        chosen.extend(selection)
        summary[cat]=dict(selected=len(selection),complete=sum(x['complete'] for x in selection),
                         weakEvidence=sum(x['requiresPopularityReview'] for x in selection))
    packet=dict(schemaVersion='1.0.0',target=target,status='selection_draft_requires_editorial_review',
        policy='精选1000篇；暂保留古文完整译注目标，负责人此前仅询问取消古文翻译耗时，并未明确取消。',
        productionChanged=False,sourceDataSha256=hashlib.sha256((ROOT/'data/poems.json').read_bytes()).hexdigest(),
        summary=summary,items=chosen)
    dest=ROOT/'expansion/selected-1000'/f'selection-v1.0.0--{digest(packet)}.json'
    write_once(dest,packet)
    print(json.dumps(summary,ensure_ascii=False,indent=2));print(dest)

if __name__=='__main__':main()
