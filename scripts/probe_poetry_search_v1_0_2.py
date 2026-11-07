"""Three bounded queries to verify title versus body search before another batch."""
import json,sys
from sync_poetry_api_v1_0_0 import Client,WORK
from enrichment_pipeline import write_once
def main():
 sys.stdout.reconfigure(encoding='utf-8');c=Client(interval=.5,budget=3);out=[]
 for q in ['故人西辞黄鹤楼','黄鹤楼送孟浩然之广陵','君不见黄河之水天上来']:
  try:
   d=c.search(q);r=dict(query=q,count=len(d['data']),examples=[dict(title=x['title'],author=x['author']['name']) for x in d['data'][:4]])
  except Exception as exc:r=dict(query=q,error=repr(exc))
  print(json.dumps(r,ensure_ascii=False),flush=True);out.append(r)
 write_once(WORK/'search-field-probe-v1.0.2.json',out)
if __name__=='__main__':main()
