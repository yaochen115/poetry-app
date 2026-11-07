"""One public provider query per missing selected work; resumable URL cache and immutable output."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from collections import defaultdict,Counter
from datetime import datetime,timezone
from difflib import SequenceMatcher
import hashlib,json,sys
from enrichment_pipeline import ROOT,read,write_once
from collect_poetry_api_pool_v1_0_0 import API,OUT
from select_poetry_2000_v1_0_0 import BASE,provider_rows,norm
from convert_downloaded_materials_v1_0_0 import text

def bind(document):
 exact=defaultdict(list);authors=defaultdict(list)
 for row,path in provider_rows():
  content=text(row['content']);body=norm(content)
  if any(x in content for x in ['记忆体','海内存','�']):continue
  r=(row,path,content,body);exact[body].append(r);authors[norm(row['author']['name'])].append(r)
 for p in document['items']:
  if p['content'] or not p['canonicalFingerprint']:continue
  b=p['canonicalFingerprint'];author=norm(p['author'])
  matches=[r for r in exact[b] if norm(r[0]['author']['name'])==author]
  if not matches:
   title=norm(p['title'].split('·')[0])
   for r in authors[author]:
    rt=norm(r[0]['title'])
    if .93<=len(r[3])/len(b)<=1.08 and (title in rt or rt in title) and SequenceMatcher(None,r[3],b,autojunk=False).ratio()>=.90:matches.append(r)
  if not matches:continue
  matches.sort(key=lambda r:(r[3]!=b,-SequenceMatcher(None,r[3],b,autojunk=False).ratio(),r[0]['id']))
  row,path,content,body=matches[0];p['content']=content;p['originalStatus']='provider_exact_normalized' if body==b else 'provider_full_length_variant_pending_review'
  p['originalSource']=dict(provider='https://poetry.palemoky.com',providerId=row['id'],providerTitle=row['title'],providerAuthor=row['author'],providerDynasty=row.get('dynasty'),providerType=row.get('type'),cacheFile=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
 return document

def main():
 sys.stdout.reconfigure(encoding='utf-8');api=API();doc=read(BASE/'catalog-v1.0.2.json')
 wanted=[p for p in doc['items'] if not p['content'] and p['canonicalFingerprint']];results=[]
 def fetch(p):
  q=p['canonicalFingerprint'][:9]
  response=api.get('/api/search',dict(q=q,page=1,pageSize=100))
  return dict(id=p['id'],query=q,results=len(response['data']))
 print('Missing originals',len(wanted),flush=True)
 with ThreadPoolExecutor(max_workers=6) as pool:
  futures={pool.submit(fetch,p):p for p in wanted}
  for f in as_completed(futures):
   p=futures[f]
   try:r=f.result()
   except Exception as exc:r=dict(id=p['id'],error=type(exc).__name__+': '+str(exc))
   results.append(r);write_once(OUT/'selected-query-checkpoints-v1.0.0'/(p['id']+'.json'),r)
   if len(results)%25==0:print('Processed',len(results),'/',len(wanted),flush=True)
 doc=bind(doc);stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
 for genre,s in doc['summary'].items():s['originals']=sum(bool(p['content']) for p in doc['items'] if p['genre']==genre)
 doc.update(schemaVersion='1.0.3',status='selected_2000_provider_queries_attempted',acquisition=dict(requests=api.requests,queried=len(results),errors=sum('error' in r for r in results),stopped=api.stopped,completedAt=stamp))
 write_once(BASE/'catalog-v1.0.3.json',doc)
 write_once(BASE/'provider-query-report-v1.0.1.json',dict(summary=doc['summary'],results=results,acquisition=doc['acquisition'],workers=6,globalMinimumRequestInterval=.5))
 print(json.dumps(dict(summary=doc['summary'],acquisition=doc['acquisition']),ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
