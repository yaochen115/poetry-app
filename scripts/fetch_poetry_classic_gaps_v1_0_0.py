"""Resolve explicit classic gaps via the provider's public search, not other originals."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json,sys
from enrichment_pipeline import ROOT,read,write_once
from collect_poetry_api_pool_v1_0_0 import API,OUT
from select_poetry_2000_v1_0_0 import BASE,norm

def main():
 sys.stdout.reconfigure(encoding='utf-8');api=API()
 latest=max((BASE/'selection-previews').glob('*.json'));missing=read(latest)['missingAnchors']
 def fetch(a):
  queries=list(dict.fromkeys([norm(a['incipit'])[:9],norm(a['title'].split('·')[0])]+[norm(x) for x in a.get('aliases',[])]))
  found=[];errors=[];used=[]
  for q in queries:
   if len(q)<3:continue
   used.append(q)
   try:
    rows=api.get('/api/search',dict(q=q,page=1,pageSize=100))['data']
    hits=[r for r in rows if norm(r.get('author',{}).get('name',''))==norm(a['author']) and norm(a['incipit']) in norm('\n'.join(r.get('content',[])))[:200]]
    if hits:found=[r['id'] for r in hits];break
   except Exception as exc:errors.append(type(exc).__name__+': '+str(exc))
  return dict(key=a['key'],author=a['author'],title=a['title'],queries=used,providerIds=found,errors=errors)
 report=[]
 with ThreadPoolExecutor(max_workers=2) as pool:
  futures=[pool.submit(fetch,a) for a in missing]
  for f in as_completed(futures):
   r=f.result();report.append(r);print(json.dumps(r,ensure_ascii=False),flush=True)
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
 write_once(OUT/('classic-gap-search-v1.0.0--'+stamp+'.json'),dict(missingAtStart=len(missing),found=sum(bool(r['providerIds']) for r in report),results=report,requests=api.requests))

if __name__=='__main__':main()
