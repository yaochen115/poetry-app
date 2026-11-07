"""Rank only provider-fetched originals, independently of translation availability."""
import argparse,csv,hashlib,json,re,sys
from collections import Counter,defaultdict
from datetime import datetime,timezone
from functools import lru_cache
from difflib import SequenceMatcher
from enrichment_pipeline import ROOT,read,write_once,digest
from convert_downloaded_materials_v1_0_0 import normal,records,text
from collect_poetry_api_pool_v1_0_0 import MAJOR_POETS

BASE=ROOT/'expansion/poetry-2000-v1.0.0'
norm=lru_cache(maxsize=200000)(normal)
SCHOOL=('小学古诗','初中古诗','高中古诗')
ANTHO=('唐诗三百首','宋词三百首','古诗三百首','宋词精选','诗经','楚辞','乐府')
POETIC={10,11,12,13,14,15,16,17,50,70}
CI={20,21}

def build_evidence():
 refs=[]
 for path in sorted((ROOT/'expansion/sources/chinese-gushiwen/guwen').glob('*.json')):
  for i,r in enumerate(records(path)):
   tags=r.get('type',[]);tags=[tags] if isinstance(tags,str) else tags
   refs.append(dict(author=r.get('writer',''),title=r.get('title',''),content=text(r.get('content','')),dynasty=r.get('dynasty',''),
                    labels=tags,path=path.relative_to(ROOT).as_posix(),row=i))
 for name,label in [('全唐诗--唐诗三百首.json','唐诗三百首'),('宋词--宋词三百首.json','宋词三百首')]:
  path=BASE/'evidence'/name
  for i,r in enumerate(read(path)):
   refs.append(dict(author=r['author'],title=r.get('title',r.get('rhythmic','')),content='\n'.join(r['paragraphs']),
                    labels=[label],path=path.relative_to(ROOT).as_posix(),row=i))
 path=BASE/'evidence/蒙学--qianjiashi.json'
 for section in read(path)['content']:
  for i,r in enumerate(section['content']):
   groups=[r['paragraphs']] if all(isinstance(x,str) for x in r['paragraphs']) else [x['paragraphs'] for x in r['paragraphs']]
   for lines in groups:
    refs.append(dict(author=re.sub(r'^[（(].*?[）)]','',r['author']),title=r.get('chapter',''),content='\n'.join(lines),
                     labels=['千家诗'],path=path.relative_to(ROOT).as_posix(),section=section['type'],row=i))
 index=defaultdict(list)
 for r in refs:
  a=norm(r['author']);body=norm(r['content'])
  if a and body:
   r['bodyKey']=body;index[(a,body[:6])].append(r)
 return index

def provider_rows():
 index={}
 # Page caches are usable even if an unrelated author pool has not finished.
 for path in sorted((BASE/'provider-api/cache').glob('*.json')):
  for r in read(path).get('data',[]):
   if not isinstance(r,dict) or 'content' not in r or not isinstance(r.get('author'),dict):continue
   index.setdefault(r['id'],(r,path))
 probe=BASE/'provider-probe'
 for path in sorted(list(probe.glob('*--data.json'))+list(probe.glob('*--data.raw'))):
  try:rows=read(path).get('data',[])
  except Exception:continue
  for r in rows:
   if isinstance(r,dict) and 'content' in r and isinstance(r.get('author'),dict):index.setdefault(r['id'],(r,path))
 return index.values()

def author_eras():
 counts=defaultdict(Counter);locations={}
 for path in sorted((ROOT/'expansion/sources/chinese-gushiwen/guwen').glob('*.json')):
  for i,r in enumerate(records(path)):
   a=norm(r.get('writer',''));d=r.get('dynasty','').replace('代','')
   if a and d and a!='佚名':counts[a][d]+=1;locations[(a,d)]=dict(path=path.relative_to(ROOT).as_posix(),row=i,field='dynasty')
 result={}
 for a,c in counts.items():
  d,n=c.most_common(1)[0]
  if n/sum(c.values())>=.9:result[a]=(d,locations[(a,d)])
 return result

def match_reference(index,author,body):
 found=[]
 for r in index.get((author,body[:6]),[]):
  b=r['bodyKey']
  if b==body:found.append((r,'normalized_body_exact'))
  elif len(body)>10 and min(len(b),len(body))/max(len(b),len(body))>.88 and SequenceMatcher(None,b,body,autojunk=False).ratio()>.91:
   found.append((r,'near_text_variant_requires_review'))
 return found

def main():
 sys.stdout.reconfigure(encoding='utf-8');ap=argparse.ArgumentParser();ap.add_argument('--final',action='store_true');args=ap.parse_args()
 anchor=read(BASE/'classic-anchor-review-v1.0.0.json');refs=build_evidence();eras=author_eras();major={norm(n) for n in MAJOR_POETS}
 ci_authors={norm(x['author']) for x in anchor['ci']}
 anchors=anchor['poems']+anchor['ci'];by_author=defaultdict(list)
 for a in anchors:by_author[norm(a['author'])].append(a)
 candidates=[];seen=defaultdict(list);dropped=Counter()
 for row,path in provider_rows():
  content=text(row['content']);body=norm(content);author=row['author']['name'];ak=norm(author)
  title=row['title'];ty=row.get('type') or {};tid=ty.get('id');dyn=(row.get('dynasty') or {}).get('name','')
  if len(body)<10 or any(x in dyn for x in ['现代','近代','当代']):continue
  evidence=match_reference(refs,ak,body);labels={t for r,_ in evidence for t in r['labels']}
  potential=[a for a in by_author[ak] if norm(a['incipit']) in body[:160]]
  anchor_genres={'诗' if a in anchor['poems'] else '词' for a in potential}
  if len(anchor_genres)==1:genre=next(iter(anchor_genres))
  elif tid in CI:genre='词'
  elif tid in POETIC:genre='诗'
  else:
   # Unknown forms only enter through explicit anthology evidence, never meter guessing.
   if labels & {'宋词三百首','宋词精选'}:genre='词'
   elif labels & {'唐诗三百首','古诗三百首','千家诗','小学古诗','初中古诗','高中古诗','诗经','乐府'}:genre='诗'
   else:dropped['unclassified_form']+=1;continue
  matched=[]
  for a in by_author[ak]:
   if a not in anchor['poems'] and genre!='词':continue
   if a in anchor['poems'] and genre!='诗':continue
   inc=norm(a['incipit']);hit=body.startswith(inc) or (len(inc)>=4 and inc in body[:160])
   if hit:matched.append(a['key'])
  # Independent duplicates/variants are not counted twice. Common ci tune alone is not identity.
  duplicate=None
  for old in seen[(ak,genre,body[:6])]:
   ob=norm(old['content'])
   if body==ob or (min(len(body),len(ob))/max(len(body),len(ob))>.88 and SequenceMatcher(None,body,ob,autojunk=False).ratio()>.93):
    duplicate=old;break
  if duplicate:
   duplicate['providerAlternativeIds'].append(row['id']);duplicate['anchorKeys']=sorted(set(duplicate['anchorKeys']+matched))
   dropped['duplicate_or_near_variant']+=1;continue
  score=10000*bool(matched)
  score+=900*bool(labels&{'唐诗三百首','宋词三百首'})+650*bool(labels&set(SCHOOL))
  score+=450*bool(labels&{'古诗三百首','宋词精选','千家诗'})
  score+=200*bool(evidence)+min(3,len({r['path'].split('/')[2] for r,_ in evidence}))*40
  score+=min(12,len(evidence))*3
  score+=60*(ak in major or (genre=='词' and ak in ci_authors))
  if labels&{'诗经','楚辞','乐府'}:score+=200
  classic=bool(matched or labels&(set(SCHOOL)|set(ANTHO)|{'千家诗'}))
  era_correction=None
  original_dyn=dyn
  if ak in eras and eras[ak][0]!=dyn:
   dyn,location=eras[ak];era_correction=dict(field='dynasty',providerValue=original_dyn,value=dyn,reason='consistent author-era reference; provider value retained',reference=location)
  p=dict(id=('poem' if genre=='诗' else 'ci')+'-pq-'+str(row['id']),genre=genre,title=title,author=author,dynasty=dyn,providerDynasty=original_dyn,metadataCorrection=era_correction,
         content=content,paragraphs=row['content'],providerId=row['id'],providerType=ty,providerAlternativeIds=[],anchorKeys=matched,
         rankScore=score,selectionLabels=sorted(labels),requiresPopularityReview=not classic,
         selectionEvidence=[dict(path=r['path'],row=r['row'],title=r['title'],labels=r['labels'],match=method,dynasty=r.get('dynasty','')) for r,method in evidence],
         originalSource=dict(provider='https://poetry.palemoky.com',cacheFile=path.relative_to(ROOT).as_posix(),
                             cacheSha256=hashlib.sha256(path.read_bytes()).hexdigest()),
         translation='',notes=[],editorialStatus='provider_original_selection_not_translation_or_literary_approval')
  candidates.append(p);seen[(ak,genre,body[:6])].append(p)
 selected=[];summary={}
 for genre in ['诗','词']:
  ranked=sorted((p for p in candidates if p['genre']==genre),key=lambda p:(-p['rankScore'],norm(p['author']),norm(p['title']),p['providerId']))
  counts=Counter();items=[];deferred=[]
  for p in ranked:
   if len(items)>=1000:break
   if counts[p['author']]>=65 and not p['anchorKeys'] and not (set(p['selectionLabels'])&{'唐诗三百首','宋词三百首'}):deferred.append(p);continue
   items.append(p);counts[p['author']]+=1
  for p in deferred:
   if len(items)>=1000:break
   items.append(p)
  selected+=items
  summary[genre]=dict(count=len(items),candidates=len(ranked),authors=len({p['author'] for p in items}),
                    eras=dict(Counter(p['dynasty'] for p in items)),weakEvidence=sum(p['requiresPopularityReview'] for p in items),
                    topAuthors=Counter(p['author'] for p in items).most_common(15))
 covered={key for p in selected for key in p['anchorKeys']};missing=[a for a in anchors if a['key'] not in covered]
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
 report=dict(schemaVersion='1.0.0',createdAt=stamp,target={'诗':1000,'词':1000},summary=summary,
             policy='历代诗词；锚点、选本、教材来源标签交叉筛选。标签非官方教材逐册审核；无依据补位项显式标识。译文可得性不参与评分。近似异文只选一个，原文保留诗泉版本；未改正式库/学习ID，未构建APK。',
             productionChanged=False,apkBuilt=False,anchorsTotal=len(anchors),anchorsCovered=len(covered),
             missingAnchors=missing,dropped=dict(dropped),items=selected)
 path=BASE/'selection-v1.0.0.json' if args.final else BASE/'selection-previews'/('selection-'+stamp+'.json')
 if args.final and (len(selected)!=2000 or missing):raise ValueError('Final selection requires 2000 works and all classic anchors; run preview for gaps')
 write_once(path,report)
 print(json.dumps(dict(path=str(path),summary=summary,anchorsCovered=len(covered),missingAnchors=[dict(key=a['key'],title=a['title'],author=a['author'],incipit=a['incipit']) for a in missing]),ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
