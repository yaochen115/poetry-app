"""Match remaining works against a published compressed corpus, locally."""
import hashlib,json,os,re,sys
from collections import defaultdict,Counter
from datetime import datetime,timezone
from pathlib import Path
from urllib.request import Request,urlopen

from enrichment_pipeline import ROOT,Pipeline,read,write_once,digest
from translation_overlay_v1_0_0 import overlay_for,apply
from convert_downloaded_materials_v1_0_0 import normal,text
from import_local_translations_v1_0_0 import build_entry

OUT=ROOT/'expansion/sources/hf-gushiwen-translations-v1.0.0'
READER=ROOT.parents[1]/'.tools/duckdb-reader-1.4.1'
FILES=[('0000.parquet',261340857),('0001.parquet',334231)]
PREFIX='https://huggingface.co/datasets/Papersnake/gushiwen/resolve/refs%2Fconvert%2Fparquet/default/train/'


def split_translation(html,label=''):
    plain=text(html)
    headings=list(re.finditer(r'(?m)^\s*(译文[一二12]?|注释|注解|参考资料|赏析)[：:]?\s*$',plain))
    translations=[];notes=[]
    for index,match in enumerate(headings):
        section=plain[match.end():headings[index+1].start() if index+1<len(headings) else len(plain)].strip()
        if match[1].startswith('译文') and section:translations.append(section)
        elif match[1] in ('注释','注解'):notes.append(section)
    if translations:return translations[0],'\n'.join(notes)
    if headings or '注释' in label or re.match(r'^(注释|注解)',plain):return '',plain
    # An explicitly labelled standalone translation can omit section headings.
    if '译文' in label or '翻译' in label:return plain,''
    return '',''


def download(name,size):
    path=OUT/name;meta=path.with_suffix('.metadata.json')
    if path.exists():
        record=read(meta)
        if hashlib.sha256(path.read_bytes()).hexdigest()!=record['sha256']:raise ValueError('Changed corpus file')
        return path,record
    url=PREFIX+name;temporary=path.with_suffix('.partial');total=0;sha=hashlib.sha256()
    OUT.mkdir(parents=True,exist_ok=True)
    with urlopen(Request(url,headers={'User-Agent':'HongzhuangCorpusImport/1.0','Accept-Encoding':'identity'}),timeout=45) as response:
        if response.status!=200:raise ValueError('Unexpected corpus response')
        with temporary.open('wb') as stream:
            while True:
                block=response.read(1_048_576)
                if not block:break
                total+=len(block)
                if total>size+1024:raise ValueError('Unexpected corpus size')
                sha.update(block);stream.write(block)
                if total%26_214_400==0:print(f'{name}: {total//1_048_576} MiB',flush=True)
    if total!=size:raise ValueError('Incomplete corpus download')
    record=dict(url=url,size=total,sha256=sha.hexdigest(),acquiredAt=datetime.now(timezone.utc).isoformat())
    temporary.rename(path);write_once(meta,record)
    return path,record


def main():
    sys.stdout.reconfigure(encoding='utf-8');sys.path.insert(0,str(READER))
    import duckdb
    lock=ROOT/'expansion/gushiwenku-crawler.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode());pipe=Pipeline();document=read(ROOT/'data/poems.json')
        lookup=defaultdict(list)
        for pid,poem in pipe.pending.items():
            if not overlay_for(document,poem):lookup[(normal(poem['content']),normal(poem['author']))].append(pid)
        paths=[];sources=[]
        for name,size in FILES:
            path,meta=download(name,size);paths.append(str(path));sources.append(meta)
        from opencc import OpenCC
        traditional=OpenCC('s2t')
        authors=sorted({a for p in pipe.pending.values() for a in (p['author'],traditional.convert(p['author']))})
        connection=duckdb.connect(':memory:',config={'threads':2,'memory_limit':'1GB','temp_directory':str(OUT/'temp')})
        result=connection.execute('''SELECT tb_gushiwen,tb_fanyis FROM read_parquet(?)
            WHERE trim(tb_gushiwen.author) IN (SELECT unnest(?))
            AND (len(tb_fanyis.fanyis)>0 OR len(coalesce(tb_gushiwen.yizhu,''))>0)''',[paths,authors])
        choices={};scanned=0;matched=0;empty=0
        while True:
            rows=result.fetchmany(1000)
            if not rows:break
            for work,translations in rows:
                scanned+=1
                ids=lookup.get((normal(work.get('cont')),normal(work.get('author'))),[])
                if len(ids)!=1:continue
                matched+=1;pid=ids[0]
                options=[(f.get('cont',''),f.get('nameStr','')) for f in (translations or {}).get('fanyis',[]) or []]
                if work.get('yizhu'):options.append((work['yizhu'],'译文及注释'))
                for html,label in options:
                    tr,notes=split_translation(html,label)
                    if not tr:empty+=1;continue
                    raw=dict(tb_gushiwen=work,tb_fanyis=translations)
                    sourcepath=OUT/'matched-rows'/(digest(raw)+'.json');write_once(sourcepath,raw)
                    source=dict(url='https://huggingface.co/datasets/Papersnake/gushiwen',
                        cacheFile=sourcepath.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(sourcepath.read_bytes()).hexdigest(),
                        sourceTitle=work.get('nameStr'),corpusSha256=[s['sha256'] for s in sources])
                    row=dict(title=work.get('nameStr'),author=work.get('author'),content=work.get('cont'),translation=tr,remark=notes)
                    entry=build_entry(row,pipe.poems[pid],pipe,source)
                    if entry:
                        rank=(len(entry['notes']),len(entry['translation']))
                        if pid not in choices or rank>choices[pid][0]:choices[pid]=(rank,entry)
        entries=[choices[i][1] for i in pipe.ordered(choices)]
        applied=[apply(entries[n:n+50]) for n in range(0,len(entries),50)]
        report=dict(toolVersion='1.0.0',readerVersion=duckdb.__version__,sources=sources,
            filteredCorpusRows=scanned,bodyAuthorMatches=matched,unusableTranslationSections=empty,
            added=sum(r['added'] for r in applied),byCategory=dict(Counter(pipe.poems[e['id']]['category'] for e in entries)),
            applied=applied,modelCalls=0,apkBuilt=False)
        filename=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+os.urandom(3).hex()
        dest=ROOT/'expansion/hf-translation-reports-v1.0.0'/('run-'+filename+'.json');write_once(dest,report)
        print(json.dumps(dict(report=str(dest),**{k:v for k,v in report.items() if k not in ('sources','applied')}),ensure_ascii=False,indent=2))
    finally:os.close(fd);lock.unlink()


if __name__=='__main__':main()
