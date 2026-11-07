"""Small, serial public-page acquisition probe; no login, bypass or bulk crawl."""
from datetime import datetime,timezone
import hashlib,json,time,urllib.request
from pathlib import Path
from html.parser import HTMLParser

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'expansion/site-samples/v1.0.0'
URLS=[('xinggong','https://www.guwendao.net/shiwenv_45c396367f59.aspx'),
      ('yanci','https://www.guwendao.net/shiwenv_0b02c0846f7a.aspx'),
      ('dictionary-index','https://www.guwendao.net/zici/')]

class Text(HTMLParser):
    def __init__(self):super().__init__();self.parts=[];self.skip=0
    def handle_starttag(self,tag,attrs):
        if tag in ('script','style'):self.skip+=1
        if tag in ('p','br','div','h1','h2','h3'):self.parts.append('\n')
    def handle_endtag(self,tag):
        if tag in ('script','style'):self.skip=max(0,self.skip-1)
        if tag in ('p','div','h1','h2','h3'):self.parts.append('\n')
    def handle_data(self,data):
        if not self.skip:self.parts.append(data)

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for name,url in URLS:
        # Reuse the previous attempt; never hammer a failed endpoint.
        if list(OUT.glob(name+'--*.json')):continue
        record=dict(url=url,acquiredAt=datetime.now(timezone.utc).isoformat(),
                    reuseStatus='reference_only_permission_not_established')
        try:
            req=urllib.request.Request(url,headers={'User-Agent':'Hongzhuang-Research/1.0 (limited public-page check)'})
            with urllib.request.urlopen(req,timeout=25) as response:
                raw=response.read(2_000_001)
                if len(raw)>2_000_000:raise ValueError('Page exceeds probe limit')
                record.update(finalUrl=response.url,status=response.status)
            sha=hashlib.sha256(raw).hexdigest();html=raw.decode('utf-8','replace')
            parser=Text();parser.feed(html)
            lines=[x.strip() for x in ''.join(parser.parts).splitlines() if x.strip()]
            record.update(sha256=sha,bytes=len(raw),lines=lines,
                translationHeadingFound=any(x in ('译文','译文及注释') for x in lines),
                dictionaryComplete=False)
            (OUT/f'{name}--{sha}.html').write_bytes(raw)
        except Exception as exc:record.update(error=type(exc).__name__+': '+str(exc))
        key=hashlib.sha256(json.dumps(record,sort_keys=True).encode()).hexdigest()
        with (OUT/f'{name}--{key}.json').open('x',encoding='utf-8') as f:json.dump(record,f,ensure_ascii=False,indent=2)
        print(name,json.dumps({k:v for k,v in record.items() if k!='lines'},ensure_ascii=True))
        time.sleep(2)

if __name__=='__main__':main()
