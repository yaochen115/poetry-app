"""Probe the requested original-text provider and its official release metadata."""
from datetime import datetime,timezone
import hashlib,json,time
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from enrichment_pipeline import ROOT,write_once

OUT=ROOT/'expansion/poetry-2000-v1.0.0/provider-probe'
URLS=[('health','https://poetry.palemoky.com/api/v1/health'),
 ('stats','https://poetry.palemoky.com/api/v1/stats'),
 ('spring-v1','https://poetry.palemoky.com/api/v1/poems/search?'+urlencode(dict(q='春江花月夜',type='title',page_size=20))),
 ('spring-legacy','https://poetry.palemoky.com/api/search?'+urlencode(dict(q='春江花月夜'))),
 ('release','https://api.github.com/repos/palemoky/chinese-poetry-api/releases/latest')]


def main():
 OUT.mkdir(parents=True,exist_ok=True)
 for name,url in URLS:
  if list(OUT.glob(name+'--*.json')):continue
  report=dict(url=url,requestedAt=datetime.now(timezone.utc).isoformat())
  try:
   with urlopen(Request(url,headers={'User-Agent':'HongzhuangAnthology/1.0','Accept':'application/json'}),timeout=25) as response:
    raw=response.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('Probe size limit')
    report.update(status=response.status,sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
   write_once(OUT/(name+'--data.json'),json.loads(raw))
   data=json.loads(raw)
   report['keys']=list(data) if isinstance(data,dict) else 'list'
   if name=='release':report['assets']=[dict(name=a['name'],size=a['size'],url=a['browser_download_url']) for a in data.get('assets',[])]
  except HTTPError as exc:report.update(status=exc.code,error=exc.read(1000).decode('utf-8','replace'))
  except Exception as exc:report['error']=type(exc).__name__+': '+str(exc)
  write_once(OUT/(name+'--metadata.json'),report)
  print(json.dumps(report,ensure_ascii=True),flush=True);time.sleep(.5)


if __name__=='__main__':main()
