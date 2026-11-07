"""Small public metadata/schema probes, capped at 2 MB per response."""
from datetime import datetime,timezone
import hashlib,json,time
from urllib.parse import urlencode
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from enrichment_pipeline import ROOT,write_once

OUT=ROOT/'expansion/source-probes-v1.0.0'
QUERY=dict(dataset='Papersnake/gushiwen',config='default',split='train')
URLS=[('hf-parquet','https://datasets-server.huggingface.co/parquet?'+urlencode(dict(dataset=QUERY['dataset']))),
      ('hf-rows','https://datasets-server.huggingface.co/rows?'+urlencode(dict(QUERY,offset=0,length=1))),
      ('hf-search-yuan','https://datasets-server.huggingface.co/search?'+urlencode(dict(QUERY,query='张可久',offset=0,length=5))),
      ('poems-db-sample','https://raw.githubusercontent.com/yxcs/poems-db/master/poems1.json')]


def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for name,url in URLS:
        if list(OUT.glob(name+'-*.json')):continue
        report=dict(url=url,time=datetime.now(timezone.utc).isoformat())
        try:
            headers={'User-Agent':'HongzhuangSources/1.0'}
            if name=='poems-db-sample':headers['Range']='bytes=0-16383'
            with urlopen(Request(url,headers=headers),timeout=20) as response:
                body=response.read(2_000_001);report.update(status=response.status,bytes=len(body),truncated=len(body)>2_000_000)
            key=hashlib.sha256(body).hexdigest();(OUT/(name+'-'+key+'.raw')).write_bytes(body)
            report['sha256']=key
            if not report['truncated']:
                try:
                    data=json.loads(body)
                    if name=='hf-parquet':report['data']=data
                    elif isinstance(data,dict):
                        report['keys']=list(data);report['features']=data.get('features');report['total']=data.get('num_rows_total');report['rowsCount']=len(data.get('rows',[]))
                except ValueError:pass
        except HTTPError as exc:report.update(status=exc.code,error=exc.read(2000).decode('utf-8','replace'))
        except Exception as exc:report['error']=type(exc).__name__+': '+str(exc)
        write_once(OUT/(name+'-'+hashlib.sha256(json.dumps(report,sort_keys=True).encode()).hexdigest()+'.json'),report)
        print(json.dumps(report,ensure_ascii=True),flush=True);time.sleep(.5)


if __name__=='__main__':main()
