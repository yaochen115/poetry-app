import json,sys,time
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError
from enrichment_pipeline import ROOT,write_once
OUT=ROOT/'expansion/poetry-2000-v1.0.0/provider-probe'
CASES=[('list-camel','/api/poems',dict(pageSize=100)),
 ('search-camel','/api/search',dict(q='李白',pageSize=100)),
 ('search-limit','/api/search',dict(q='李白',limit=100)),
 ('list-authorid','/api/poems',dict(author_id=5839,pageSize=100)),
 ('list-type','/api/poems',dict(type_id=20,pageSize=100))]
def main():
 sys.stdout.reconfigure(encoding='utf-8')
 for name,path,args in CASES:
  if (OUT/(name+'--data.json')).exists():continue
  url='https://poetry.palemoky.com'+path+'?'+urlencode(args)
  try:
   with urlopen(Request(url,headers={'User-Agent':'HongzhuangAnthology/1.0'}),timeout=20) as r:raw=r.read(3_000_001)
   if len(raw)>3_000_000:raise ValueError('Probe size limit')
   d=json.loads(raw);write_once(OUT/(name+'--data.json'),d)
   print(json.dumps(dict(name=name,count=len(d.get('data',[])),meta={k:v for k,v in d.items() if k!='data'},examples=[(p.get('title'),p.get('author'),p.get('type')) for p in d.get('data',[])[:2]]),ensure_ascii=False),flush=True)
  except HTTPError as exc:print(name,exc.code,exc.read(2000).decode('utf-8','replace'),flush=True)
  except Exception as exc:print(name,type(exc).__name__,str(exc),flush=True)
  time.sleep(.5)
if __name__=='__main__':main()
