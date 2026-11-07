"""Reuse downloaded corpora as partial translations; no network or model calls."""
from collections import Counter, defaultdict
from datetime import datetime,timezone
import hashlib
import json
import os
import re

from enrichment_pipeline import ROOT,Pipeline,read,write_once,digest
from convert_downloaded_materials_v1_0_0 import records,normal,first,text
from prepare_reference_review_v1_0_0 import extract_notes
from translation_overlay_v1_0_0 import apply,overlay_for

WORK=ROOT/'expansion/local-translation-import-v1.0.0'


def usable_translation(value):
    value=text(value)
    if len(value)<8:return None
    if re.match(r'^(?:译文\s*)?(?:注释|注解|词句注释)',value):return None
    if any(w in value for w in ('待翻译','暂无翻译','译文略','（略）')):return None
    return value


def build_entry(row,poem,pipe,source):
    if normal(first(row,'content','paragraph','paragraphs'))!=normal(poem['content']):return None
    if normal(first(row,'authorName','writer','author'))!=normal(poem['author']):return None
    translation=usable_translation(first(row,'translation','translate'))
    if not translation:return None
    raw=first(row,'annotation','remark','notes')
    if isinstance(raw,list) and all(isinstance(n,dict) for n in raw):
        notes=[dict(term=text(n.get('term')),meaning=text(n.get('meaning'))) for n in raw]
        notes=[n for n in notes if n['term'] and n['term'] in poem['content'] and n['meaning']]
        notes=list({n['term']:n for n in notes}.values())[:18]
    else:notes=extract_notes(text(raw),poem['content'])[:18]
    rawtags=first(row,'tags','type')
    if not isinstance(rawtags,list):rawtags=[]
    tags=list(dict.fromkeys(t for t in poem.get('tags',[])+rawtags
                            if isinstance(t,str) and t in pipe.tags[poem['category']]))[:2]
    missing=sorted({c for c in poem['content'] if '\u4e00'<=c<='\u9fff'}-set(pipe.dictionary))
    pending=['semanticReview','sourcePermissionReview']
    if not tags:pending.append('themeTags')
    if len(notes)<3:pending.append('notes')
    if missing:pending.append('dictionary')
    return dict(id=poem['id'],baseContent=poem['content'],baseAuthor=poem['author'],
        translation=translation,notes=notes,tags=tags,source=source,
        editorialStatus='source_imported_pending_review',literaryApproved=False,pending=pending,
        missingCharacters=missing,titleAlias=normal(row.get('title'))!=normal(poem['title']))


def main():
    import sys
    sys.stdout.reconfigure(encoding='utf-8')
    WORK.mkdir(parents=True,exist_ok=True)
    lock=ROOT/'expansion/gushiwenku-crawler.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY)
    try:
        os.write(fd,str(os.getpid()).encode());pipe=Pipeline();document=read(ROOT/'data/poems.json')
        lookup=defaultdict(list)
        for pid,poem in pipe.pending.items():
            if not overlay_for(document,poem):lookup[(normal(poem['content']),normal(poem['author']))].append(pid)
        choices={};errors=[];scanned=0;rejected=0;matched=set()
        for folder in ('chinese-gushiwen/guwen','poetry-source/source'):
            for path in sorted((ROOT/'expansion/sources'/folder).rglob('*.json')):
                try:rows=records(path)
                except Exception as exc:errors.append(dict(file=str(path),error=str(exc)));continue
                sha=hashlib.sha256(path.read_bytes()).hexdigest()
                for index,row in enumerate(rows):
                    if not isinstance(row,dict):continue
                    scanned+=1
                    ids=lookup.get((normal(first(row,'content','paragraph','paragraphs')),
                                    normal(first(row,'authorName','writer','author'))),[])
                    if len(ids)!=1:continue
                    pid=ids[0];matched.add(pid)
                    source=dict(cacheFile=path.relative_to(ROOT).as_posix(),sha256=sha,row=index,
                        sourceTitle=text(row.get('title')),url='local:'+path.relative_to(ROOT).as_posix(),
                        importedAt=datetime.now(timezone.utc).isoformat(),reuseStatus='unconfirmed_source_reference')
                    entry=build_entry(row,pipe.poems[pid],pipe,source)
                    if not entry:rejected+=1;continue
                    rank=(len(entry['notes']),len(entry['tags']),len(entry['translation']))
                    if pid not in choices or rank>choices[pid][0]:choices[pid]=(rank,entry)
        entries=[choices[pid][1] for pid in pipe.ordered(choices)]
        for entry in entries:write_once(WORK/'entries'/(entry['id']+'--'+digest(entry)+'.json'),entry)
        applied=[]
        for offset in range(0,len(entries),50):applied.append(apply(entries[offset:offset+50]))
        report=dict(toolVersion='1.0.0',scanned=scanned,candidates=len(entries),
            sourceMatchedButNoUsableTranslation=sorted(matched-set(choices)),
            rejectedReferenceRows=rejected,errors=errors,
            byCategory=dict(Counter(pipe.poems[e['id']]['category'] for e in entries)),
            applied=applied,added=sum(r['added'] for r in applied),networkRequests=0,modelCalls=0,apkBuilt=False)
        name=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'-'+os.urandom(3).hex()
        path=WORK/'reports'/('run-'+name+'.json');write_once(path,report)
        print(json.dumps(dict(report=str(path),**{k:v for k,v in report.items() if k not in ('applied','sourceMatchedButNoUsableTranslation')}),ensure_ascii=False,indent=2))
    finally:os.close(fd);lock.unlink()


if __name__=='__main__':main()
