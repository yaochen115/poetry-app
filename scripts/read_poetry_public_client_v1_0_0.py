import json,re,sys
from urllib.request import urlopen,Request
from urllib.parse import urljoin
from enrichment_pipeline import ROOT,write_once
OUT=ROOT/'expansion/poetry-2000-v1.0.0/provider-client-reference'
def fetch(url,name):
 path=OUT/name
 if path.exists():return path.read_text(encoding='utf-8')
 with urlopen(Request(url,headers={'User-Agent':'HongzhuangSourceReference/1.0'}),timeout=25) as r:raw=r.read(4_000_000)
 OUT.mkdir(parents=True,exist_ok=True);path.write_bytes(raw);return raw.decode('utf-8')
def main():
 sys.stdout.reconfigure(encoding='utf-8');h=fetch('https://poetry.palemoky.com/','homepage.html')
 links=re.findall(r'<script[^>]+src=["\']([^"\']+)',h)
 print('scripts',links,flush=True)
 for i,link in enumerate(links[:3]):
  raw=fetch(urljoin('https://poetry.palemoky.com/',link),'client-'+str(i)+'.js')
  hits=[]
  for token in ['/api/search','authorId','dynastyId','searchField','pageSize']:
   start=0
   for _ in range(4):
    at=raw.find(token,start)
    if at<0:break
    hits.append(dict(token=token,snippet=raw[max(0,at-180):at+300]));start=at+len(token)
  write_once(OUT/('snippets-'+str(i)+'.json'),hits);print(json.dumps(hits,ensure_ascii=False),flush=True)
if __name__=='__main__':main()
