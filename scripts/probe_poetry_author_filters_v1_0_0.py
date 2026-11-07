import json,sys
from collect_poetry_api_pool_v1_0_0 import API,OUT
from enrichment_pipeline import write_once
def main():
 sys.stdout.reconfigure(encoding='utf-8');a=API()
 for tag,params in [('song',dict(dynastyId=8)),('qing',dict(dynastyId=11)),('named',dict(name='辛弃疾'))]:
  try:
   d=a.get('/api/authors',dict(params,page=1,pageSize=100));write_once(OUT/('author-filter-'+tag+'.json'),d)
   print(tag,d.get('pagination'),[x['name'] for x in d['data'][:4]],flush=True)
  except Exception as exc:print(tag,type(exc).__name__,str(exc),flush=True)
if __name__=='__main__':main()
