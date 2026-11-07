import json,sys
from enrichment_pipeline import write_once
from collect_poetry_api_pool_v1_0_0 import API,OUT
from collect_poetry_api_pool_v1_0_1 import batch
def main():
 sys.stdout.reconfigure(encoding='utf-8');a=API()
 for t in (10,40,21):
  try:
   d=batch(a,dict(typeId=t),10);write_once(OUT/'special-pools-v1.0.0'/('type-'+str(t)+'.json'),d)
   print(t,len(d['items']),d['truncated'],[(r['title'],r['author']['name']) for r in d['items'][:3]],flush=True)
  except Exception as exc:print(t,type(exc).__name__,str(exc),flush=True)
if __name__=='__main__':main()
