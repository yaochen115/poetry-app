"""Fresh bounded detail-page retry for the two existing website adapters."""
from collections import Counter,defaultdict
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib,json,os,re,sys,threading,time
from urllib.parse import urlparse
from urllib.request import Request,build_opener,HTTPRedirectHandler
from urllib.error import HTTPError
from urllib.robotparser import RobotFileParser

from enrichment_pipeline import ROOT,Pipeline,read,write_once,digest
from translation_overlay_v1_0_0 import overlay_for,apply
from convert_downloaded_materials_v1_0_0 import normal
from import_local_translations_v1_0_0 import build_entry
import crawl_gushiwenku_v1_0_0 as ku
import site_translation_parser_v1_0_2 as guwen

OUT=ROOT/'expansion/two-site-retry-v1.0.0'
HOSTS={'www.gushiwenku.cn','www.guwendao.net','www.gushiwen.cn','so.gushiwen.org','so.gushiwen.cn'}


class SourceStopped(Exception):pass


def validate_url(url):
    p=urlparse(url)
    if p.scheme!='https' or p.netloc not in HOSTS or p.query or p.fragment:raise SourceStopped('Outside allowed sources')
    if p.path!='/robots.txt' and not re.fullmatch(r'(?:/shiwen/[0-9a-f]+/|/shiwenv_[0-9a-f]{12}\.aspx)',p.path):
        raise SourceStopped('Redirected away from a public detail page')


class Redirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        validate_url(newurl)
        return super().redirect_request(req,fp,code,msg,headers,newurl)


class Client:
    def __init__(self,folder):
        self.folder=folder;self.robot={};self.lock=threading.Lock();self.next_start=0;self.interval=.5;self.requests=Counter();self.stopped={}

    def get(self,url,site):
        validate_url(url)
        if site in self.stopped:raise SourceStopped(self.stopped[site])
        if site in self.robot and not self.robot[site].can_fetch('HongzhuangRetry/1.0',url):raise SourceStopped('robots disallows detail path')
        key=hashlib.sha256(url.encode()).hexdigest();metadata=self.folder/'cache'/(key+'.json')
        if metadata.exists():
            record=read(metadata);raw=(self.folder/'cache'/record['blob']).read_bytes()
            if hashlib.sha256(raw).hexdigest()!=record['sha256']:raise ValueError('Changed retry cache')
            return raw,record
        with self.lock:
            time.sleep(max(0,self.next_start-time.monotonic()))
            if site in self.stopped:raise SourceStopped(self.stopped[site])
            self.next_start=time.monotonic()+self.interval;self.requests[site]+=1
        try:
            with build_opener(Redirects()).open(Request(url,headers={'User-Agent':'HongzhuangRetry/1.0 (bounded public detail check)'}),timeout=20) as response:
                raw=response.read(2_000_001)
                if len(raw)>2_000_000:raise ValueError('Page too large')
                record=dict(url=url,finalUrl=response.url,status=response.status,sha256=hashlib.sha256(raw).hexdigest(),
                    acquiredAt=datetime.now(timezone.utc).isoformat())
        except HTTPError as exc:
            if exc.code in (401,403,429,503):self.stopped[site]=f'HTTP {exc.code}; no bypass or automatic retry';raise SourceStopped(self.stopped[site]) from exc
            raise
        visible=ku.Document(raw.decode('utf-8','replace')).root.text().lower()
        if any(t in visible[:2500] for t in ('verify you are human','access denied','人机验证','请输入验证码')):
            self.stopped[site]='Access challenge; stopped';raise SourceStopped(self.stopped[site])
        record['blob']=record['sha256']+'.html';cache=self.folder/'cache';cache.mkdir(parents=True,exist_ok=True)
        blob=cache/record['blob']
        if not blob.exists():blob.write_bytes(raw)
        write_once(metadata,record);return raw,record


def candidate(page,source,pipe,folder):
    row=dict(title=page['title'],author=page['author'],content=page['content'],translation=page['translation'],remark=page.get('notes',[]))
    matches=[pid for pid,p in pipe.pending.items() if normal(p['content'])==normal(row['content']) and normal(p['author'])==normal(row['author'])]
    if len(matches)!=1:return None,'body_author_not_unique_pending_match'
    source=dict(source,cacheFile=(folder/'cache'/source['blob']).relative_to(ROOT).as_posix(),sourceTitle=row['title'])
    entry=build_entry(row,pipe.poems[matches[0]],pipe,source)
    return entry, None if entry else 'no_usable_translation'


def targets(pipe):
    results={};wanted=defaultdict(list)
    for pid,p in pipe.pending.items():wanted[(normal(p['content']),normal(p['author']))].append(pid)
    for path in (ROOT/'expansion/gushiwenku-crawler-v1.0.1/cache').glob('*.json'):
        meta=read(path)
        if '/shiwen/' not in meta['url']:continue
        try:row,patch,_=ku.convert((path.parent/meta['blob']).read_text(encoding='utf-8'),pipe)
        except Exception:continue
        if patch:results[('gushiwenku',patch['id'])]=dict(site='gushiwenku',id=patch['id'],url=meta['url'])
    path=ROOT/'expansion/sources/poems-db-translations-v1.0.0/poems1.jsonl'
    for line in path.open(encoding='utf-8-sig'):
        row=json.loads(line);ids=wanted.get((normal(row.get('content')),normal(row.get('author'))),[])
        match=re.search(r'shiwenv_([0-9a-f]{12})\.aspx',row.get('sourceLink',''))
        if len(ids)==1 and match:results[('guwendao',ids[0])]=dict(site='guwendao',id=ids[0],url='https://www.guwendao.net/shiwenv_'+match[1]+'.aspx')
    return list(results.values())


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    lock=ROOT/'expansion/gushiwenku-crawler.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode());pipe=Pipeline();doc=read(ROOT/'data/poems.json')
        pipe.pending={i:p for i,p in pipe.pending.items() if not overlay_for(doc,p)}
        run_id=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+os.urandom(3).hex();folder=OUT/run_id
        client=Client(folder);queue=targets(pipe);results=[];entries={};robot_results={}
        for site,host in [('gushiwenku','www.gushiwenku.cn'),('guwendao','www.guwendao.net')]:
            robot=RobotFileParser()
            try:
                raw,_=client.get('https://'+host+'/robots.txt',site);robot.parse(raw.decode('utf-8').splitlines());robot_results[site]='read'
            except HTTPError as exc:
                if exc.code in (404,410):robot.parse([]);robot_results[site]=f'not_published_http_{exc.code}'
                else:client.stopped[site]=str(exc)
            except Exception as exc:client.stopped[site]=str(exc)
            client.robot[site]=robot
            delay=robot.crawl_delay('HongzhuangRetry/1.0') or robot.crawl_delay('*')
            if delay:client.interval=max(client.interval,delay)
        def process(item):
            raw,meta=client.get(item['url'],item['site'])
            if item['site']=='gushiwenku':
                row,_,_=ku.convert(raw.decode('utf-8'),pipe)
                page=dict(title=row['title'],author=row['writer'],content=row['content'],translation=row['translation'],notes=row['remark'])
            else:page=guwen.extract(raw,url=meta['finalUrl'])
            entry,reason=candidate(page,meta,pipe,folder)
            return entry,dict(**item,status=meta['status'],usable=bool(entry),reason=reason,matchedId=entry['id'] if entry else None)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures={pool.submit(process,item):item for item in queue}
            for future in as_completed(futures):
                item=futures[future]
                try:
                    entry,result=future.result();results.append(result)
                    if entry:entries.setdefault(entry['id'],entry)
                    print(json.dumps(result,ensure_ascii=False),flush=True)
                except Exception as exc:results.append(dict(**item,usable=False,error=type(exc).__name__+': '+str(exc)))
        applied=apply(list(entries.values())) if entries else dict(added=0)
        report=dict(toolVersion='1.0.0',runId=run_id,targets=len(queue),bySite={site:dict(
            targets=sum(x['site']==site for x in queue),requests=client.requests[site],
            usable=sum(x['site']==site and x.get('usable',False) for x in results),
            stopped=client.stopped.get(site)) for site in ('gushiwenku','guwendao')},
            robots=robot_results,results=results,imported=applied,apkBuilt=False)
        write_once(folder/'report.json',report)
        print(json.dumps({k:v for k,v in report.items() if k!='results'},ensure_ascii=False,indent=2))
    finally:os.close(fd);lock.unlink()


if __name__=='__main__':main()
