"""Bounded public-directory crawler and incremental enrichment importer.

Default is preview. --apply imports structurally eligible selected works only.
No model calls, ID creation, full-site traversal or APK builds.
"""
import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
from itertools import zip_longest
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.robotparser import RobotFileParser

from enrichment_pipeline import ROOT, Pipeline, digest, read, write_once, validate_patch
from convert_downloaded_materials_v1_0_0 import normal
from prepare_reference_review_v1_0_0 import extract_notes
from probe_gushiwenku_v1_0_0 import Document, parse

HOST = 'www.gushiwenku.cn'
BASE = 'https://'+HOST
WORK = ROOT/'expansion/gushiwenku-crawler-v1.0.0'
CATALOGS = [BASE+'/xuanji/'+s+'-sanbaishou/' for s in ('tangshi','songci','yuanqu')]
UA = 'HongzhuangCrawler/1.0 (limited public-page collection)'


def safe_url(url):
    p = urlparse(url)
    if p.scheme != 'https' or p.netloc != HOST or p.query or p.fragment:
        raise ValueError('Only clean HTTPS URLs on the configured host are accepted')
    if p.path != '/robots.txt' and not re.fullmatch(r'/(?:shiwen/[0-9a-f]+|xuanji/[a-z0-9-]+(?:/page/\d+)?)/',p.path):
        raise ValueError('Outside permitted article/catalog paths')
    return url


class StopCollection(Exception): pass


class Redirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        safe_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class Client:
    def __init__(self, work, offline=False, delay=2):
        self.work=work; self.offline=offline; self.delay=delay; self.last=0
        self.requests=0; self.hits=0; self.robot=None
        self.opener=build_opener(Redirects())

    def get(self, url):
        safe_url(url)
        if self.robot and not self.robot.can_fetch(UA,url): raise ValueError('robots disallows URL')
        key=hashlib.sha256(url.encode()).hexdigest(); meta=self.work/'cache'/(key+'.json')
        if meta.exists():
            record=read(meta)
            if not re.fullmatch(r'[0-9a-f]{64}\.html',record['blob']):raise ValueError('Invalid cache blob name')
            raw=(self.work/'cache'/record['blob']).read_bytes()
            if record['url']!=url or hashlib.sha256(raw).hexdigest()!=record['sha256']:
                raise ValueError('Cache integrity error')
            self.hits+=1; return raw.decode('utf-8'), record
        if self.offline: raise ValueError('Not cached: '+url)
        time.sleep(max(0,self.delay-(time.monotonic()-self.last)))
        try:
            self.requests+=1
            with self.opener.open(Request(url,headers={'User-Agent':UA}),timeout=25) as response:
                safe_url(response.url); raw=response.read(2_000_001)
                if len(raw)>2_000_000: raise ValueError('Page exceeds 2 MB')
                record=dict(url=url,finalUrl=response.url,status=response.status,
                    fetchedAt=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(raw).hexdigest())
        except HTTPError as exc:
            if exc.code in (401,403,429,503): raise StopCollection(f'HTTP {exc.code}; no retries or bypass') from exc
            raise
        finally: self.last=time.monotonic()
        html=raw.decode('utf-8'); visible=Document(html).root.text().lower()
        if any(s in visible[:2500] for s in ('access denied','verify you are human','人机验证','请输入验证码')):
            raise StopCollection('Access challenge; no bypass')
        record['blob']=record['sha256']+'.html'
        meta.parent.mkdir(parents=True,exist_ok=True)
        blob=meta.parent/record['blob']
        if not blob.exists():
            with blob.open('xb') as stream: stream.write(raw)
        write_once(meta,record)
        return html,record

    def robots(self):
        self.robot=RobotFileParser()
        try:
            # No configured rules until the robots response is acquired.
            self.robot=None; html, _=self.get(BASE+'/robots.txt')
            self.robot=RobotFileParser(); self.robot.parse(html.splitlines())
        except HTTPError as exc:
            if exc.code not in (404,410): raise
            self.robot=RobotFileParser(); self.robot.parse([])


def reuse_sample_cache(work):
    """Reuse original successful sample files; never refetch the same URL."""
    for folder in ('gushiwenku-samples-v1.0.0','gushiwenku-catalog-check-v1.0.0'):
        for path in (ROOT/'expansion'/folder).glob('*.metadata.json'):
            record=read(path); source=path.with_name(path.name.replace('.metadata.json','.html'))
            if not source.exists() or record.get('status')!=200: continue
            raw=source.read_bytes()
            if hashlib.sha256(raw).hexdigest()!=record.get('sha256'): raise ValueError('Changed sample cache')
            key=hashlib.sha256(record['url'].encode()).hexdigest(); dest=work/'cache'/(key+'.json')
            if dest.exists(): continue
            record=dict(record,blob=record['sha256']+'.html'); dest.parent.mkdir(parents=True,exist_ok=True)
            blob=dest.parent/record['blob']
            if not blob.exists():
                with blob.open('xb') as stream:stream.write(raw)
            write_once(dest,record)


def title_keys(poem):
    title=poem['title']; subtitle=poem.get('subtitle','')
    first=re.split(r'[，。！？\s]',poem.get('content','').strip())[0]
    return {normal(title),normal(title+subtitle),normal(title+first)}-{''}


def discover(html, catalog, pending):
    links=[]; seen=set()
    wanted={key for p in pending.values() for key in title_keys(p)}
    for node in Document(html).root.all():
        if node.tag!='a': continue
        url=urljoin(catalog,node.attrs.get('href',''))
        if not re.fullmatch(r'https://www\.gushiwenku\.cn/shiwen/[0-9a-f]+/',url): continue
        name=next((n.text() for n in node.all() if n.has('works-name')),node.text())
        # A title is a discovery hint only; import always requires body + author.
        author=next((n.text() for n in node.all() if n.has('works-author')),'')
        name_key=normal(name)
        title_hint=name_key in wanted or any(
            name_key.startswith(normal(p['title'])) and normal(author)==normal(p['author'])
            for p in pending.values() if author)
        if not title_hint or url in seen: continue
        seen.add(url); links.append(url)
    return links


def convert(html, pipe):
    try: row=parse(html)
    except StopIteration:
        nodes=list(Document(html).root.all())
        if any(n.attrs.get('aria-labelledby')=='poem-translation' for n in nodes):raise
        # Some real pages expose only original/pinyin. Retain an honest missing
        # translation record rather than harvesting a related work's content.
        poem=next(n for n in nodes if n.tag=='article' and n.has('poem-content'))
        row=dict(title=next(n.text() for n in nodes if n.attrs.get('id')=='poem-title'),
                 writer=next(n.text() for n in nodes if n.has('poem-author')),
                 content='\n'.join(n.text() for n in poem.all() if n.tag=='p' and n.has('original')),
                 translation='',remark='',type=[])
    matches=[p for p in pipe.pending.values() if normal(p['content'])==normal(row['content'])
             and normal(p['author'])==normal(row['writer'])]
    if len(matches)!=1: return row,None,{'identity': 'not_pending_or_not_exact_match'}
    poem=matches[0]; tags=list(poem.get('tags',[])); tag_sources=[]
    aliases={'山水田园':['山水','田园'],'田园':['田园','山水'],'离别':['离别','送别'],'送别':['送别','离别']}
    for n in Document(html).root.all():
        if n.tag=='a' and n.has('theme-link'):
            tag_sources.append(n.text()); tags.extend(aliases.get(n.text(),[n.text()]))
    tags=list(dict.fromkeys(t for t in tags if t in pipe.tags[poem['category']]))[:2]
    notes=extract_notes(row['remark'],poem['content'])[:18]
    patch=dict(id=poem['id'],tags=tags,translation=row['translation'],notes=notes)
    reasons=[]
    if normal(row['title']) not in title_keys(poem): reasons.append('title_variant')
    try:validate_patch(patch,poem,pipe.tags[poem['category']])
    except ValueError as exc: reasons.append(str(exc))
    if len(row['content'].splitlines())!=len(row['translation'].splitlines()):
        reasons.append('paragraph_coverage_requires_review')
    if re.match(r'^(注释|注解)',patch['translation']): reasons.append('annotation_only_translation')
    missing=sorted({c for c in poem['content'] if '\u4e00'<=c<='\u9fff'}-set(pipe.dictionary))
    # Reuse explicit one-character body annotations as contextual ancient senses.
    # Never split multi-character terms or manufacture general/modern meanings.
    additions={n['term']:dict(meanings=[],ancient=[n['meaning']]) for n in notes
               if len(n['term'])==1 and n['term'] in missing}
    missing=sorted(set(missing)-set(additions))
    if missing:reasons.append('missing_dictionary')
    return row,patch,dict(reasons=reasons,missingCharacters=missing,sourceTags=tag_sources,
                          dictionaryAdditions=additions,inputHash=pipe.input_hash(poem))


def import_batch(eligible, pipe, work):
    if not eligible:return None
    # Shared lock protects concurrent instances of this runner. Inputs are rechecked
    # against production immediately before applying a batch.
    current=Pipeline()
    for item in eligible:
        pid=item['patch']['id']
        if pid not in current.pending or current.input_hash(current.poems[pid])!=item['checks']['inputHash']:
            raise ValueError('Production changed since extraction: '+pid)
        raw=(work/'cache'/item['source']['blob']).read_bytes()
        if hashlib.sha256(raw).hexdigest()!=item['source']['sha256']: raise ValueError('Changed downloaded source')
    batches=[int(p.stem) for p in (ROOT/'expansion/enrichment').glob('*.json') if p.stem.isdigit()]
    number=f'{max(batches,default=0)+1:03}'
    def bump(v):
        a=v.split('.');a[-1]=str(int(a[-1])+1);return '.'.join(a)
    additions={}
    for item in eligible:
        for ch,entry in item['checks']['dictionaryAdditions'].items():
            if ch in current.dictionary:continue
            dst=additions.setdefault(ch,dict(meanings=[],ancient=[]))
            dst['ancient']=list(dict.fromkeys(dst['ancient']+entry['ancient']))
    batch=dict(dataVersion=bump(read(ROOT/'data/poems.json')['dataVersion']),
        dictionaryVersion=bump(read(ROOT/'data/dict.json')['dataVersion']),
        patches=[e['patch'] for e in eligible],dictionaryAdditions=additions,
        policy='负责人授权网站公开资料自动采集入库；身份及结构自动检查，未逐篇语义复核，不声称独立编写。',
        review=dict(literaryApproved=False,automaticSourceImport=True,dictionarySource='explicit single-character body notes',dictionaryReviewed=False),
        conversionProvenance=[dict(id=e['patch']['id'],source=e['source'],checks=e['checks']) for e in eligible])
    path=ROOT/'expansion/enrichment'/(number+'.json');write_once(path,batch,accept_identical=False)
    subprocess.run([sys.executable,'-B',str(ROOT/'scripts/apply_enrichment_batch.py'),str(path)],check=True)
    subprocess.run([sys.executable,'-B',str(ROOT/'scripts/export_pending_enrichment.py')],check=True)
    return dict(batch=number,count=len(eligible),dataVersion=batch['dataVersion'],dictionaryVersion=batch['dictionaryVersion'])


def run(args):
    work=args.work.resolve()
    if not work.is_relative_to((ROOT/'expansion').resolve()): raise ValueError('Work directory must be under project expansion/')
    if args.max_pages<1 or args.max_pages>500 or args.delay<2:raise ValueError('max-pages must be 1..500; delay >= 2')
    work.mkdir(parents=True,exist_ok=True)
    lock=ROOT/'expansion/gushiwenku-crawler.lock'
    fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode()); reuse_sample_cache(work)
        pipe=Pipeline();client=Client(work,args.offline,args.delay);client.robots()
        catalogs=args.catalog if args.catalog else ([] if args.url else CATALOGS)
        if len(catalogs)>10: raise ValueError('At most 10 explicit catalog pages')
        groups=[];errors=[];stop=None
        for catalog in catalogs:
            try:
                html,_=client.get(catalog);groups.append(discover(html,catalog,pipe.pending))
            except StopCollection as exc:stop=str(exc);break
            except Exception as exc:errors.append(dict(url=catalog,error=str(exc)))
        # Round robin allows different genres in a short run.
        queue=list(dict.fromkeys(args.url+[u for batch in zip_longest(*groups) for u in batch if u]))
        previously_held={read(p)['url'] for p in (work/'held').glob('*.json')}
        if not args.recheck:
            queue=[url for url in queue if url not in previously_held]
        eligible=[];records=[];seen=set()
        for url in queue[:args.max_pages] if not stop else []:
            try:
                html,source=client.get(url);row,patch,checks=convert(html,pipe)
                item=dict(url=url,row=row,source=source,checks=checks,patch=patch)
                records.append(item)
                if patch and not checks['reasons'] and patch['id'] not in seen:
                    eligible.append(item);seen.add(patch['id'])
                elif not patch or checks.get('reasons'):
                    held=dict(url=url,checks=checks)
                    write_once(work/'held'/('held-'+digest(held)+'.json'),held)
                print(json.dumps(dict(title=row['title'],id=patch['id'] if patch else None,checks=checks),ensure_ascii=False),flush=True)
            except StopCollection as exc:stop=str(exc);break
            except Exception as exc:
                error=dict(url=url,error=type(exc).__name__+': '+str(exc));errors.append(error)
                write_once(work/'held'/('error-'+digest(error)+'.json'),error)
        snapshot=dict(records=records,errors=errors,stop=stop)
        write_once(work/'snapshots'/('records-'+digest(snapshot)+'.json'),snapshot)
        # Stop conditions never trigger an automatic write to production.
        imported=import_batch(eligible,pipe,work) if args.apply and not stop else None
        report=dict(toolVersion='1.0.0',networkRequests=client.requests,cacheHits=client.hits,
            discovered=len(queue),attempted=min(len(queue),args.max_pages) if not stop else len(records)+len(errors),
            parsed=len(records),eligible=len(eligible),imported=imported,errors=errors,stop=stop,
            held=[dict(url=r['url'],id=r['patch']['id'] if r['patch'] else None,checks=r['checks'])
                  for r in records if not r['patch'] or r['checks'].get('reasons')],
            literaryApproved=False,apkBuilt=False,
            snapshot='snapshots/records-'+digest(snapshot)+'.json')
        dest=work/'reports'/('report-'+digest(report)+'.json');write_once(dest,report)
        print(json.dumps(dict(report=str(dest),**{k:v for k,v in report.items() if k not in ('held','errors')}),ensure_ascii=False,indent=2))
        if stop:raise SystemExit(2)
    finally:
        os.close(fd);lock.unlink()


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--url',action='append',default=[],help='Explicit poem URL; repeatable')
    p.add_argument('--catalog',action='append',default=[],help='Explicit catalog URL; repeatable')
    p.add_argument('--max-pages',type=int,default=20,help='Maximum poem attempts per run (plus up to 10 catalog pages and robots)')
    p.add_argument('--delay',type=float,default=2)
    p.add_argument('--work',type=Path,default=WORK)
    p.add_argument('--offline',action='store_true')
    p.add_argument('--recheck',action='store_true',help='Revisit previously held/error pages explicitly')
    p.add_argument('--apply',action='store_true',help='Import eligible matches through existing backup/audit pipeline')
    run(p.parse_args())


if __name__=='__main__':main()
