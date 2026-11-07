import json,sys,time
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from enrichment_pipeline import ROOT,write_once
OUT=ROOT/'expansion/poetry-2000-v1.0.0/provider-probe'
CASES=[('camel-author','/api/poems',dict(authorId=5839,pageSize=100)),
 ('camel-type','/api/poems',dict(typeId=20,pageSize=100)),
 ('authors-list','/api/authors',dict(pageSize=1000)),
 ('search-three','/api/search',dict(q='春江花',pageSize=100))]
def main():
 sys.stdout.reconfigure(encoding='utf-8')
 for name,path,args in CASES:
  if (OUT/(name+'--data.json')).exists():continue
  url='https://poetry.palemoky.com'+path+'?'+urlencode(args)
  try:
   with urlopen(Request(url,headers={'User-Agent':'HongzhuangAnthology/1.0'}),timeout=20) as r:raw=r.read(4_000_001)
   if len(raw)>4_000_000:raise ValueError('Probe size limit')
   d=json.loads(raw);write_once(OUT/(name+'--data.json'),d)
   print(json.dumps(dict(name=name,count=len(d.get('data',[])),meta={k:v for k,v in d.items() if k!='data'},examples=d.get('data',[])[:1]),ensure_ascii=False)[:900],flush=True)
  except HTTPError as exc:print(name,exc.code,exc.read(2000).decode('utf-8','replace'),flush=True)
  except Exception as exc:print(name,type(exc).__name__,str(exc),flush=True)
  time.sleep(.5)
if __name__=='__main__':main()
