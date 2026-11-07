"""Resume official API cache; complete ci pools, bounded poet pools, no production edits."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import json,math,os,sys
from enrichment_pipeline import ROOT,read,write_once
from collect_poetry_api_pool_v1_0_0 import API,OUT,MAJOR_POETS

def batch(api,params,limit):
 rows=[];has_more=True
 for page in range(1,limit+1):
  doc=api.get('/api/poems',dict(params,page=page,pageSize=100))
  rows.extend(doc['data']);has_more=doc.get('pagination',{}).get('hasMore',False)
  if not has_more:break
 return dict(provider='https://poetry.palemoky.com/',query=params,items=rows,pages=page,
             truncated=has_more,policy='Candidate pool only; API text preserved, not literary approval')

def main():
 sys.stdout.reconfigure(encoding='utf-8');api=API();authors=[];errors=[]
 lock=OUT/'collector.lock';lock.parent.mkdir(parents=True,exist_ok=True)
 fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode())
 try:
  with ThreadPoolExecutor(max_workers=2) as pool:
   jobs={pool.submit(api.get,'/api/authors',dict(page=p,pageSize=100)):p for p in range(1,137)}
   for job in as_completed(jobs):
    try:authors.extend(job.result()['data'])
    except Exception as exc:errors.append(dict(stage='authors',page=jobs[job],error=str(exc)))
  write_once(OUT/'authors-v1.0.1.json',sorted(authors,key=lambda a:a['id']))
  anchor=read(ROOT/'expansion/poetry-2000-v1.0.0/classic-anchor-review-v1.0.0.json')
  wanted=(set(MAJOR_POETS)|{x['author'] for x in anchor['poems']})-{'佚名'}
  book=read(ROOT/'expansion/poetry-2000-v1.0.0/evidence/全唐诗--唐诗三百首.json')
  wanted.update(x['author'] for x in book)
  work=[('type-'+str(t),dict(typeId=t),350) for t in (20,21,50,70)]
  work.extend(('author-'+str(a['id']),dict(authorId=a['id']),8) for a in authors if a['name'] in wanted)
  saved=[];print('Indexed authors',len(authors),'pools',len(work),flush=True)
  with ThreadPoolExecutor(max_workers=2) as pool:
   jobs={pool.submit(batch,api,params,limit):(name,params) for name,params,limit in work}
   for job in as_completed(jobs):
    name,params=jobs[job]
    try:
     data=job.result();path=OUT/'pools-v1.0.1'/(name+'.json');write_once(path,data)
     saved.append(dict(pool=name,count=len(data['items']),truncated=data['truncated']))
     print(name,len(data['items']),'truncated='+str(data['truncated']),flush=True)
    except Exception as exc:errors.append(dict(stage='pool',pool=name,error=type(exc).__name__+': '+str(exc)))
  report=dict(requests=api.requests,authors=len(authors),pools=saved,errors=errors,stopped=api.stopped,
              absentMajorAuthors=sorted(wanted-{a['name'] for a in authors}),productionChanged=False)
  stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
  write_once(OUT/('collection-v1.0.1--'+stamp+'.json'),report)
  print('Finished',len(saved),'pools',len(errors),'errors',flush=True)
 finally:os.close(fd);lock.unlink()

if __name__=='__main__':main()
