"""Download bounded published JSONL parts, match pending translations locally."""
import argparse
from collections import Counter,defaultdict
from datetime import datetime,timezone
import hashlib,json,os,sys,time
from urllib.request import Request,urlopen

from enrichment_pipeline import ROOT,Pipeline,read,write_once,digest
from translation_overlay_v1_0_0 import overlay_for,apply
from convert_downloaded_materials_v1_0_0 import normal,first
from import_local_translations_v1_0_0 import build_entry

OUT=ROOT/'expansion/sources/poems-db-translations-v1.0.0'


def download(part):
    path=OUT/f'poems{part}.jsonl';meta=path.with_suffix('.metadata.json')
    if path.exists():
        record=read(meta)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Cached source changed')
        return path,record
    url=f'https://raw.githubusercontent.com/yxcs/poems-db/master/poems{part}.json'
    temporary=path.with_suffix('.partial');total=0;sha=hashlib.sha256()
    OUT.mkdir(parents=True,exist_ok=True)
    with urlopen(Request(url,headers={'User-Agent':'HongzhuangTranslationImport/1.0','Accept-Encoding':'identity'}),timeout=40) as response:
        if response.status!=200:raise ValueError(f'Expected full public file, got {response.status}')
        expected=int(response.headers.get('Content-Length','0'))
        if expected>60_000_000:raise ValueError('Source part exceeds 60 MB budget')
        with temporary.open('wb') as stream:
            while True:
                block=response.read(1_048_576)
                if not block:break
                total+=len(block)
                if total>60_000_000:raise ValueError('Source exceeds budget')
                sha.update(block);stream.write(block)
                if total%5_242_880==0:print(f'part {part}: {total//1_048_576} MiB',flush=True)
        if expected and expected!=total:raise ValueError('Incomplete source download')
        record=dict(url=url,finalUrl=response.url,status=response.status,bytes=total,sha256=sha.hexdigest(),
                    acquiredAt=datetime.now(timezone.utc).isoformat())
    temporary.rename(path);write_once(meta,record)
    return path,record


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--part',type=int,action='append',choices=[1,2,3,4],required=True)
    args=parser.parse_args()
    lock=ROOT/'expansion/gushiwenku-crawler.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    report=dict(toolVersion='1.0.0',sources=[],scanned=0,eligible=0,imports=[],errors=[],apkBuilt=False)
    try:
        os.write(fd,str(os.getpid()).encode());pipe=Pipeline();document=read(ROOT/'data/poems.json')
        lookup=defaultdict(list)
        for pid,poem in pipe.pending.items():
            if not overlay_for(document,poem):lookup[(normal(poem['content']),normal(poem['author']))].append(pid)
        choices={}
        for part in dict.fromkeys(args.part):
            path,meta=download(part);report['sources'].append(meta)
            with path.open(encoding='utf-8-sig') as stream:
                for number,line in enumerate(stream):
                    if not line.strip():continue
                    try:row=json.loads(line)
                    except ValueError as exc:raise ValueError(f'Invalid source row {number}') from exc
                    report['scanned']+=1
                    ids=lookup.get((normal(row.get('content')),normal(row.get('author'))),[])
                    if len(ids)!=1:continue
                    row=dict(row,title=row.get('name',''))
                    source=dict(url=meta['url'],cacheFile=path.relative_to(ROOT).as_posix(),sha256=meta['sha256'],
                                sourceUrl=row.get('sourceLink'),row=number,sourceTitle=row['title'])
                    entry=build_entry(row,pipe.poems[ids[0]],pipe,source)
                    if not entry:continue
                    rank=(len(entry['notes']),len(entry['translation']))
                    if ids[0] not in choices or rank>choices[ids[0]][0]:choices[ids[0]]=(rank,entry)
        entries=[choices[i][1] for i in pipe.ordered(choices)];report['eligible']=len(entries)
        report['byCategory']=dict(Counter(pipe.poems[e['id']]['category'] for e in entries))
        for offset in range(0,len(entries),50):report['imports'].append(apply(entries[offset:offset+50]))
        report['added']=sum(x['added'] for x in report['imports'])
        name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+os.urandom(3).hex()
        dest=ROOT/'expansion/poems-db-translation-reports-v1.0.0'/('run-'+name+'.json')
        write_once(dest,report)
        print(json.dumps(dict(report=str(dest),**{k:v for k,v in report.items() if k not in ('imports','sources')}),ensure_ascii=False,indent=2))
    finally:os.close(fd);lock.unlink()


if __name__=='__main__':main()
