"""Acquire small anthology indices for selection evidence, not original substitution."""
import hashlib,json,sys,time
from urllib.parse import quote
from urllib.request import Request,urlopen
from enrichment_pipeline import ROOT,write_once

OUT=ROOT/'expansion/poetry-2000-v1.0.0/evidence'
FILES=['全唐诗/唐诗三百首.json','宋词/宋词三百首.json','蒙学/qianjiashi.json','蒙学/tangshisanbaishou.json']


def main():
 sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(parents=True,exist_ok=True)
 manifest=[]
 for name in FILES:
  path=OUT/name.replace('/','--');url='https://raw.githubusercontent.com/chinese-poetry/chinese-poetry/master/'+quote(name)
  if not path.exists():
   with urlopen(Request(url,headers={'User-Agent':'HongzhuangAnthology/1.0'}),timeout=25) as response:
    raw=response.read(2_000_001)
    if len(raw)>2_000_000:raise ValueError('Small anthology budget exceeded')
   json.loads(raw);path.write_bytes(raw);time.sleep(.5)
  raw=path.read_bytes();manifest.append(dict(file=path.relative_to(ROOT).as_posix(),url=url,sha256=hashlib.sha256(raw).hexdigest()))
 write_once(OUT/'manifest-v1.0.0.json',manifest);print(json.dumps(manifest,ensure_ascii=False))


if __name__=='__main__':main()
