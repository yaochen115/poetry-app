"""Reuse both site parsers for the new 2000-work catalog; reference imports only, no invented translations."""
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import argparse,hashlib,json,re,sys
from urllib.robotparser import RobotFileParser
from urllib.error import HTTPError
from enrichment_pipeline import ROOT,read,write_once
from select_poetry_2000_v1_0_0 import BASE,norm
from prepare_poetry_catalog_v1_0_2 import clean_body
from prepare_reference_review_v1_0_0 import extract_notes
import crawl_gushiwenku_v1_0_0 as ku
from crawl_gushiwenku_v1_0_1 import FastClient,seed_cache
import site_translation_parser_v1_0_2 as guwen
from retry_two_translation_sites_v1_0_0 import Client,SourceStopped

WORK=BASE/'two-sites-v1.0.0'

def main():
 sys.stdout.reconfigure(encoding='utf-8');ap=argparse.ArgumentParser();ap.add_argument('--max-new-pages',type=int,default=900);ap.add_argument('--offline',action='store_true');args=ap.parse_args()
 if not 0<=args.max_new_pages<=1500:ap.error('max-new-pages 0..1500')
 doc=read(BASE/'catalog-v1.0.2.json');wanted=defaultdict(list)
 for p in doc['items']:
  if p['canonicalFingerprint']:wanted[(norm(p['author']),p['canonicalFingerprint'])].append(p)
 accepted={};results=[];known=set();definitions=defaultdict(list);dictionary=read(ROOT/'data/dict.json')['chars']
 def process(raw,meta,cachefile,site):
  source=dict(url=meta['url'],sha256=hashlib.sha256(raw).hexdigest(),cacheFile=cachefile.relative_to(ROOT).as_posix(),site=site,
              fetchedAt=meta.get('fetchedAt',meta.get('acquiredAt')),permissionReviewed=False)
  try:
   if site=='gushiwenku':
    row=ku.parse(raw.decode('utf-8'));page=dict(title=row['title'],author=row['writer'],content=row['content'],translation=row['translation'],notes=row['remark'])
   else:page=guwen.extract(raw,url=meta.get('finalUrl',meta['url']))
  except Exception as exc:return dict(url=meta['url'],site=site,usable=False,reason='parse: '+type(exc).__name__+': '+str(exc))
  body=norm(clean_body(page['content']));author=norm(page['author']);matches=wanted.get((author,body),[])
  if len(matches)!=1:return dict(url=meta['url'],site=site,usable=False,reason='body_author_not_unique_exact_catalog_match',title=page['title'])
  p=matches[0];translation=page.get('translation','').strip()
  rawnotes=page.get('notes','');rawnotes='\n'.join(rawnotes) if isinstance(rawnotes,list) else rawnotes
  notes=extract_notes(rawnotes,p['matchingText'])
  if len(translation)<8 or any(x in translation for x in ['暂无翻译','待翻译','译文略','（略）']):return dict(url=meta['url'],site=site,id=p['id'],usable=False,reason='translation_missing_or_placeholder')
  entry=dict(id=p['id'],title=p['title'],author=p['author'],translation=translation,notes=notes,sourceNotes=rawnotes,source=source,
             baseReferenceFingerprint=body,editorialStatus='source_acquired_pending_review',literaryApproved=False,
             pending=['semanticReview','translationCoverage','sourcePermissionReview']+(['providerOriginal'] if not p['content'] else []))
  if p['id'] not in accepted or len(entry['notes'])>len(accepted[p['id']]['notes']):accepted[p['id']]=entry
  write_once(WORK/'entries'/(p['id']+'--'+source['sha256']+'.json'),entry)
  for note in notes:
   if len(note['term'])<=12:definitions[note['term']].append(dict(id=p['id'],meaning=note['meaning'],source=source,kind='contextual_source_note',reviewed=False))
  return dict(url=meta['url'],site=site,id=p['id'],usable=True,notes=len(notes))
 cache_roots=[ROOT/'expansion/gushiwenku-crawler-v1.0.1/cache',ROOT/'expansion/gushiwenku-crawler-v1.0.0/cache',WORK/'ku/cache',WORK/'guwen/cache']
 cache_roots+=list((ROOT/'expansion/two-site-retry-v1.0.0').glob('*/cache'))
 for folder in cache_roots:
  for path in sorted(folder.glob('*.json')):
   meta=read(path);url=meta.get('url','');blob=folder/meta.get('blob','MISSING')
   site='gushiwenku' if 'gushiwenku.cn/shiwen/' in url else 'guwendao' if re.search('shiwenv_[0-9a-f]+.aspx',url) else None
   if not site or url in known or not blob.is_file():continue
   raw=blob.read_bytes()
   if hashlib.sha256(raw).hexdigest()!=meta['sha256']:raise ValueError('Changed cached website data')
   known.add(url);results.append(process(raw,meta,blob,site))
 print('Cache parsed',len(known),'translations',len(accepted),flush=True)
 queues=[];errors=[];client_guwen=Client(WORK/'guwen');client_ku=FastClient(WORK/'ku',args.offline,.5)
 if not args.offline:
  try:
   client_ku.robots()
   pending={p['id']:dict(p,content=p['matchingText']) for p in doc['items'] if p['id'] not in accepted}
   catalogs=[ku.BASE+'/xuanji/'+s+'/' for s in ('tangshi-sanbaishou','songci-sanbaishou','xiaoxue-gushi','chuzhong-gushi','gaozhong-gushi')]
   for url in catalogs:
    try:
     html,_=client_ku.get(url)
     queues.extend(dict(site='gushiwenku',url=u) for u in ku.discover(html,url,pending) if u not in known)
    except Exception as exc:errors.append(dict(url=url,error=str(exc)))
  except Exception as exc:errors.append(dict(site='gushiwenku',stage='robots',error=str(exc)));client_ku.stop.set()
  robot=RobotFileParser()
  try:
   raw,_=client_guwen.get('https://www.guwendao.net/robots.txt','guwendao');robot.parse(raw.decode('utf-8').splitlines())
  except HTTPError as exc:
   if exc.code in (404,410):robot.parse([])
   else:client_guwen.stopped['guwendao']=str(exc)
  except Exception as exc:client_guwen.stopped['guwendao']=str(exc)
  client_guwen.robot['guwendao']=robot
  delay=robot.crawl_delay('HongzhuangRetry/1.0') or robot.crawl_delay('*')
  if delay:client_guwen.interval=max(client_guwen.interval,delay)
  source=ROOT/'expansion/sources/poems-db-translations-v1.0.0/poems1.jsonl'
  for line in source.open(encoding='utf-8-sig'):
   r=json.loads(line);matches=wanted.get((norm(r.get('author','')),norm(clean_body(r.get('content',[])))),[])
   m=re.search(r'shiwenv_([0-9a-f]{12})\.aspx',r.get('sourceLink',''))
   if len(matches)==1 and m and matches[0]['id'] not in accepted:
    url='https://www.guwendao.net/shiwenv_'+m[1]+'.aspx'
    if url not in known:queues.append(dict(site='guwendao',url=url))
  unique={q['url']:q for q in queues};queues=list(unique.values())[:args.max_new_pages]
  print('New detail targets',len(queues),flush=True)
  def fetch(q):
   if q['site']=='gushiwenku':
    html,meta=client_ku.get(q['url']);raw=html.encode('utf-8');folder=WORK/'ku/cache'
   else:raw,meta=client_guwen.get(q['url'],q['site']);folder=WORK/'guwen/cache'
   return raw,meta,folder/meta['blob'],q['site']
  with ThreadPoolExecutor(max_workers=2) as pool:
   futures={pool.submit(fetch,q):q for q in queues}
   for f in as_completed(futures):
    q=futures[f]
    try:results.append(process(*f.result()))
    except Exception as exc:errors.append(dict(**q,error=type(exc).__name__+': '+str(exc)))
    if (len(results)+len(errors))%25==0:print('translations',len(accepted),'results',len(results),'errors',len(errors),flush=True)
 stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')
 report=dict(schemaVersion='1.0.0',catalog='catalog-v1.0.2.json',cachedPages=len(known),newTargets=len(queues),
  requests={'gushiwenku':client_ku.network,'guwendao':dict(client_guwen.requests)},translations=len(accepted),
  byGenre=dict(Counter(next(p['genre'] for p in doc['items'] if p['id']==e['id']) for e in accepted.values())),
  noteCount=sum(len(e['notes']) for e in accepted.values()),definitionTerms=len(definitions),singleCharacters=sum(len(k)==1 for k in definitions),
  stopped=dict(guwendao=client_guwen.stopped,gushiwenku=client_ku.stop.is_set()),results=results,errors=errors,
  productionChanged=False,apkBuilt=False,policy='仅采集公开现成译文；逐字正文和作者匹配。字典为原注中词条的上下文释义候选，不冒充通用字典，也不覆盖现有释义；未逐篇语义/授权复核。')
 write_once(WORK/('translations-v1.0.0--'+stamp+'.json'),dict(entries=list(accepted.values())))
 write_once(WORK/('dictionary-candidates-v1.0.0--'+stamp+'.json'),dict(entries=dict(definitions),existingCharacters=len(dictionary),reviewed=False))
 write_once(WORK/('report-v1.0.0--'+stamp+'.json'),report)
 print(json.dumps({k:v for k,v in report.items() if k not in ['results','errors']},ensure_ascii=False,indent=2),flush=True)

if __name__=='__main__':main()
