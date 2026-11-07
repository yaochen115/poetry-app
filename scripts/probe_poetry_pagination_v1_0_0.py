import json,sys,time
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from enrichment_pipeline import ROOT,write_once

OUT=ROOT/'expansion/poetry-2000-v1.0.0/provider-probe'
URLS=[('list-poems','https://poetry.palemoky.com/api/poems?'+urlencode(dict(author='李白',page_size=100,page=1))),
 ('author-search','https://poetry.palemoky.com/api/search?'+urlencode(dict(q='李白',type='author',page_size=100,page=1))),
 ('author-page2','https://poetry.palemoky.com/api/search?'+urlencode(dict(q='李白',type='author',page_size=100,page=2)))]

def main():
 sys.stdout.reconfigure(encoding='utf-8')
 for name,url in URLS:
  if (OUT/(name+'--data.json')).exists():continue
  try:
   with urlopen(Request(url,headers={'User-Agent':'HongzhuangAnthology/1.0'}),timeout=20) as response:raw=response.read(3_000_001)
   if len(raw)>3_000_000:raise ValueError('Probe too large')
   r=json.loads(raw);write_once(OUT/(name+'--data.json'),r)
   print(json.dumps(dict(name=name,count=len(r.get('data',[])),metadata={k:v for k,v in r.items() if k!='data'},firstIds=[x.get('id') for x in r.get('data',[])[:3]]),ensure_ascii=False),flush=True)
  except Exception as exc:print(name,type(exc).__name__,str(exc),flush=True)
  time.sleep(.5)

if __name__=='__main__':main()
