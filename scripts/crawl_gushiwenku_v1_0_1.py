"""Faster bounded acquisition and field-level partial translation imports."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime,timezone
import hashlib
from itertools import zip_longest
import json
from pathlib import Path
import shutil
import os
import threading
import time

import crawl_gushiwenku_v1_0_0 as old
from enrichment_pipeline import ROOT, Pipeline, read, write_once, digest
from translation_overlay_v1_0_0 import apply, overlay_for

WORK=ROOT/'expansion/gushiwenku-crawler-v1.0.1'


class FastClient:
    def __init__(self,work,offline,interval):
        self.work=work;self.offline=offline;self.interval=interval
        self.lock=threading.Lock();self.next_start=0;self.stop=threading.Event()
        self.network=0;self.hits=0;self.robot=None

    def get(self,url):
        old.safe_url(url)
        key=hashlib.sha256(url.encode()).hexdigest()
        cached=(self.work/'cache'/(key+'.json')).exists()
        if self.stop.is_set():raise old.StopCollection('Collection halted after access/rate-limit response')
        if not cached and not self.offline:
            with self.lock:
                time.sleep(max(0,self.next_start-time.monotonic()))
                if self.stop.is_set():raise old.StopCollection('Collection halted')
                self.next_start=time.monotonic()+self.interval
        client=old.Client(self.work,self.offline,delay=0);client.robot=self.robot
        try:return client.get(url)
        except old.StopCollection:
            self.stop.set()
            # Stop rather than retry through a 403/challenge/429 response.
            with self.lock:self.interval=max(2,self.interval*2)
            raise
        finally:
            with self.lock:self.network+=client.requests;self.hits+=client.hits

    def robots(self):
        parser=old.RobotFileParser()
        try:html,_=self.get(old.BASE+'/robots.txt');parser.parse(html.splitlines())
        except old.HTTPError as exc:
            if exc.code not in (404,410):raise
            parser.parse([])
        self.robot=parser
        specified=parser.crawl_delay(old.UA) or parser.crawl_delay('*')
        if specified:self.interval=max(self.interval,specified)


def seed_cache(work):
    old.reuse_sample_cache(work)
    previous=old.WORK/'cache';dest=work/'cache';dest.mkdir(parents=True,exist_ok=True)
    for meta in previous.glob('*.json'):
        record=read(meta);old.safe_url(record['url'])
        if not old.re.fullmatch(r'[0-9a-f]{64}\.html',record['blob']):raise ValueError('Invalid cached blob')
        raw=(previous/record['blob']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Changed old cache')
        if not (dest/record['blob']).exists():shutil.copyfile(previous/record['blob'],dest/record['blob'])
        if not (dest/meta.name).exists():write_once(dest/meta.name,record)


def candidate(html,source,pipe,work):
    row,patch,checks=old.convert(html,pipe)
    if patch is None:return None,dict(title=row['title'],reason='identity_not_unique_pending_match')
    translation=patch['translation'].strip()
    if len(translation)<8 or any(w in translation for w in ('待翻译','暂无翻译','译文略','（略）')):
        return None,dict(id=patch['id'],title=row['title'],reason='no_usable_translation')
    if old.re.match(r'^(?:译文\s*)?(?:注释|注解|词句注释)',translation):
        return None,dict(id=patch['id'],reason='annotations_not_translation')
    poem=pipe.poems[patch['id']]
    unresolved=[]
    if not patch['tags']:unresolved.append('themeTags')
    if len(patch['notes'])<3:unresolved.append('notes')
    missing=sorted({c for c in poem['content'] if '\u4e00'<=c<='\u9fff'}-set(pipe.dictionary))
    if missing:unresolved.append('dictionary')
    if 'paragraph_coverage_requires_review' in checks['reasons']:unresolved.append('translationCoverage')
    return dict(id=patch['id'],baseContent=poem['content'],baseAuthor=poem['author'],
        translation=translation,notes=patch['notes'],tags=patch['tags'],
        source=dict(url=source['url'],sha256=source['sha256'],fetchedAt=source['fetchedAt'],
                    cacheFile=(work/'cache'/source['blob']).relative_to(ROOT).as_posix(),sourceTitle=row['title']),
        editorialStatus='source_imported_pending_review',literaryApproved=False,
        pending=unresolved+['semanticReview'],missingCharacters=missing,
        titleAlias=old.normal(row['title']) not in old.title_keys(poem)),None


def main():
    old.sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--max-pages',type=int,default=300)
    p.add_argument('--workers',type=int,default=2)
    p.add_argument('--interval',type=float,default=.5,help='Global minimum request start spacing')
    p.add_argument('--offline',action='store_true');p.add_argument('--apply',action='store_true')
    args=p.parse_args()
    if not 1<=args.workers<=4 or not .25<=args.interval<=10 or not 1<=args.max_pages<=500:
        p.error('workers 1..4, interval .25..10 seconds, max-pages 1..500')
    WORK.mkdir(parents=True,exist_ok=True)
    lock=ROOT/'expansion/gushiwenku-crawler.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+os.urandom(3).hex()
    report=dict(toolVersion='1.0.1',runId=run_id,records=[],errors=[],imports=[],stopped=False)
    start=time.monotonic()
    try:
        os.write(fd,str(os.getpid()).encode());seed_cache(WORK)
        pipe=Pipeline();document=read(ROOT/'data/poems.json')
        pipe.pending={pid:poem for pid,poem in pipe.pending.items() if not overlay_for(document,poem)}
        client=FastClient(WORK,args.offline,args.interval);client.robots()
        groups=[old.discover(client.get(url)[0],url,pipe.pending) for url in old.CATALOGS]
        # Reprocess all historical downloaded pages as well as new directory links.
        cached=[read(path)['url'] for path in (WORK/'cache').glob('*.json')
                if '/shiwen/' in read(path)['url']]
        queue=list(dict.fromkeys(cached+[u for batch in zip_longest(*groups) for u in batch if u]))[:args.max_pages]
        report['queued']=len(queue);chunk=[];seen=set()
        def fetch_convert(url):
            html,meta=client.get(url)
            return candidate(html,meta,pipe,WORK)
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            futures={pool.submit(fetch_convert,url):url for url in queue}
            for future in as_completed(futures):
                url=futures[future]
                try:
                    entry,held=future.result()
                    if entry and entry['id'] not in seen:
                        seen.add(entry['id']);chunk.append(entry)
                        write_once(WORK/'entries'/(entry['id']+'--'+digest(entry)+'.json'),entry)
                        report['records'].append(dict(id=entry['id'],url=url,pending=entry['pending']))
                        print(json.dumps(dict(saved=entry['id'],pending=entry['pending']),ensure_ascii=False),flush=True)
                    elif held:report['records'].append(dict(url=url,held=held))
                    if len(chunk)>=20:
                        if args.apply:report['imports'].append(apply(chunk))
                        chunk=[]
                except old.StopCollection as exc:
                    report['stopped']=True;report['errors'].append(dict(url=url,error=str(exc)))
                    for f in futures:f.cancel()
                    break
                except Exception as exc:report['errors'].append(dict(url=url,error=type(exc).__name__+': '+str(exc)))
        if chunk and args.apply:report['imports'].append(apply(chunk))
        report.update(networkRequests=client.network,cacheHits=client.hits,seconds=round(time.monotonic()-start,2),
                      saved=len(seen),added=sum(r.get('added',0) for r in report['imports']),
                      workers=args.workers,requestInterval=client.interval,apkBuilt=False)
        path=WORK/'reports'/('run-'+run_id+'.json');write_once(path,report)
        print(json.dumps(dict(report=str(path),**{k:v for k,v in report.items() if k not in ('records','errors')}),ensure_ascii=False,indent=2))
    finally:os.close(fd);lock.unlink()


if __name__=='__main__':main()
