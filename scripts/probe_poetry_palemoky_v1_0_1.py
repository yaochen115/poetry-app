"""Check documented legacy routes and official bulk-data availability."""
import json,sys,time
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from urllib.parse import urlencode,urlparse
from enrichment_pipeline import ROOT,write_once

OUT=ROOT/'expansion/poetry-2000-v1.0.0/provider-probe'
URLS=[('legacy-health','https://poetry.palemoky.com/health','GET'),
 ('legacy-stats','https://poetry.palemoky.com/api/stats','GET'),
 ('legacy-types','https://poetry.palemoky.com/api/types','GET'),
 ('spring-confirm','https://poetry.palemoky.com/api/search?'+urlencode(dict(q='春江花月夜',lang='zh-Hans',page_size=20)),'GET'),
 ('checksums','https://github.com/palemoky/chinese-poetry-api/releases/download/v0.8.0/checksums.txt','GET'),
 ('bulk-head','https://github.com/palemoky/chinese-poetry-api/releases/download/v0.8.0/poetry.db.gz','HEAD')]


def main():
 sys.stdout.reconfigure(encoding='utf-8')
 for name,url,method in URLS:
  meta=OUT/(name+'--metadata.json')
  if meta.exists():continue
  report=dict(url=url,method=method)
  try:
   with urlopen(Request(url,method=method,headers={'User-Agent':'HongzhuangAnthology/1.0'}),timeout=20) as response:
    report.update(status=response.status,contentLength=response.headers.get('Content-Length'),host=urlparse(response.url).netloc)
    body=response.read(1_000_001) if method!='HEAD' else b''
    if len(body)>1_000_000:raise ValueError('Size limit')
   (OUT/(name+'--data.raw')).write_bytes(body)
   try:
    data=json.loads(body);report['data']=data
   except ValueError:report['preview']=body[:100].decode('utf-8','replace')
  except HTTPError as exc:report.update(status=exc.code,error=exc.read(500).decode('utf-8','replace'))
  except Exception as exc:report['error']=type(exc).__name__+': '+str(exc)
  write_once(meta,report);print(json.dumps({k:v for k,v in report.items() if k!='data'},ensure_ascii=False),flush=True);time.sleep(1)


if __name__=='__main__':main()
