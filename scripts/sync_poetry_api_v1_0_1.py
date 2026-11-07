"""Continuous bounded queue; real pilot gate; literal phrase search and automatic source-verified imports."""
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, wait, FIRST_COMPLETED
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import argparse
import copy
import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import time
from difflib import SequenceMatcher
from uuid import uuid4

import sync_poetry_api_v1_0_0 as old
from enrichment_pipeline import ROOT, read, write_once
from data_scope import active_items
from convert_downloaded_materials_v1_0_0 import CC
from prepare_poetry_catalog_v1_0_2 import clean_body

VERSION = '1.0.1'
WORK = ROOT / 'expansion/poetry-api-sync-v1.0.1'
CATALOG = old.BASE / 'catalog-v1.0.2.json'


def phrase_query(poem):
    """A literal contiguous phrase, never a fingerprint spanning punctuation."""
    runs = re.findall(r'[\u3400-\u9fff]{3,}', CC.convert(clean_body(poem.get('matchingText', ''))))
    return runs[0][:14] if runs else None


def title_query(poem):
    title = CC.convert(poem['title'].split('·')[0]).strip()
    title = re.sub(r'其[一二三四五六七八九十]+$', '', title).strip()
    return title if len(old.norm(title)) >= 3 else None


def variant_confidence(poem, hit):
    row=hit['row']
    if old.norm(row['author']['name'])!=old.norm(poem['author']):
        return None
    expected=poem['canonicalFingerprint']
    title=old.norm(poem['title'].split('·')[0]);source_title=old.norm(row['title'])
    if not expected or not (title in source_title or source_title in title):
        return None
    if hit.get('_matchBodyContent')!=hit['content']:
        hit['_matchBody']=old.norm(clean_body(hit['content']))
        hit['_matchBodyContent']=hit['content']
    actual=hit['_matchBody']
    if not actual:
        return None
    if not .97<=len(actual)/len(expected)<=1.03:
        return None  # Never accept a half poem / collection / title-only match.
    similarity=SequenceMatcher(None,expected,actual,autojunk=False).ratio()
    if similarity<.94:
        return None
    if SequenceMatcher(None,expected[:8],actual[:8]).ratio()<.75 or SequenceMatcher(None,expected[-8:],actual[-8:]).ratio()<.75:
        return None
    return dict(fullLengthRatio=round(len(actual)/len(expected),5),textSimilarity=round(similarity,5),
                authorExact=True,titleConfirmed=True,variantReviewPending=True)


def resolved(items,index,source_authors):
    exact,held=old.resolve(items,index);ids={e['selected']['id'] for e in exact}
    variants=[];memo=source_authors.setdefault(None,{})
    for p in items:
        if p['id'] in ids or not p['canonicalFingerprint']:
            continue
        candidates=source_authors.get(old.norm(p['author']),[])
        key=(p['id'],p['canonicalFingerprint'],old.norm(p['author']),len(candidates))
        if key in memo:
            best=memo[key]
        else:
            best=None
            for hit in candidates:
                confidence=variant_confidence(p,hit)
                if confidence and (best is None or confidence['textSimilarity']>best[0]['textSimilarity']):
                    best=confidence,hit
            memo[key]=best
        if best:
            variants.append(dict(selected=p,**best[1],variant=best[0]));ids.add(p['id'])
    return exact+variants,[p for p in held if p['id'] not in ids]


def variant_plan(document,entries):
    # A better/different provider variant must never allocate another app ID for
    # an already-bound catalog identity. Keep the committed source and old ID.
    entries=[e for e in entries if e['selected']['id'] not in document.get('poetryApiBindings',{})]
    existing=defaultdict(list)
    disabled=old.disabled_ids(document)
    for p in document['items']:
        if p['id'] not in disabled:
            existing[(old.norm(p['author']),old.norm(clean_body(p['content'])))].append(p)
    normal=[];preserve=[]
    for e in entries:
        if not e.get('variant'):
            normal.append(e);continue
        p=e['selected'];key=(old.norm(p['author']),p['canonicalFingerprint'])
        if existing.get(key):
            preserve.append((e,existing[key]));continue
        adjusted=copy.deepcopy(e);adjusted['selected']['canonicalFingerprint']=old.norm(e['content'])
        normal.append(adjusted)
    proposed,summary=old.plan(document,normal)
    profile=proposed['selectionProfile'];chosen=set(profile['ids']);by_id={p['id']:p for p in proposed['items']}
    for e,rows in preserve:
        p=e['selected'];pid=p['id'];row=min(rows,key=lambda r:(r['id'] not in chosen,r['id']));iid=row['id']
        if pid not in proposed.setdefault('poetryApiBindings',{}):
            proposed['poetryApiBindings'][pid]=dict(appId=iid,genre=p['genre'],source=e['source'],preservedExistingEntry=True,
                referenceFingerprint=p['canonicalFingerprint'],catalogReferenceFingerprint=p['canonicalFingerprint'],
                sourceVariant=dict(content=e['content'],referenceFingerprint=old.norm(clean_body(row['content'])),**e['variant']))
        if iid not in chosen:
            chosen.add(iid);profile['ids'].append(iid);summary['newlyVisible'].append(iid)
        summary['preservedExistingIds']=sorted(set(summary['preservedExistingIds']+[iid]))
    for e in entries:
        if not e.get('variant'):
            continue
        b=proposed.get('poetryApiBindings',{}).get(e['selected']['id'])
        if b:
            b.setdefault('catalogReferenceFingerprint',e['selected']['canonicalFingerprint'])
            b.setdefault('sourceVariant',dict(content=e['content'],referenceFingerprint=old.norm(clean_body(by_id[b['appId']]['content'])),**e['variant']))
    profile['expectedCounts']=dict(Counter(by_id[i]['category'] for i in profile['ids']))
    changed=proposed!=document
    if changed and proposed['dataVersion']==document['dataVersion']:
        parts=document['dataVersion'].split('.');parts[-1]=str(int(parts[-1])+1);proposed['dataVersion']='.'.join(parts)
    summary.update(changed=changed,active=len(profile['ids']),boundCatalogWorks=len(proposed.get('poetryApiBindings',{})))
    return proposed,summary


def commit_with_audit(document,proposed,summary,root=ROOT):
    if not summary['changed']:
        return dict(applied=False,reason='idempotent_no_changes',**summary)
    data=root/'data/poems.json';asset=root/'app/assets/data/poems.json'
    if read(data)!=document or data.read_bytes()!=asset.read_bytes():
        raise ValueError('Concurrent data change or inconsistent assets')
    version=proposed['dataVersion'];tx=uuid4().hex[:8]
    backup=root/'expansion/checkpoints'/('pre-poetry-api-data-v'+version+'--'+tx)
    before={data:data.read_bytes(),asset:asset.read_bytes()}
    for path,raw in before.items():
        dest=backup/path.relative_to(root);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    manifest=root/'expansion/poetry-api-imports'/('data-v'+version+'--'+tx+'.json')
    write_once(manifest,dict(toolVersion=VERSION,status='prepared',dataVersion=version,summary=summary,
                             backup=backup.relative_to(root).as_posix()))
    raw=(json.dumps(proposed,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    snapshot=root/'data/versions'/('poems-v'+version+'.json')
    if snapshot.exists():
        raise ValueError('Version already archived; refusing overwrite '+str(snapshot))
    try:
        for path in before:
            old.atomic_bytes(path,raw)
        subprocess.run([sys.executable,'-B',str(root/'scripts/validate_data.py'),'--original-only'],check=True,cwd=root)
        subprocess.run([sys.executable,'-B',str(root/'scripts/audit_expansion.py')],check=True,cwd=root,stdout=subprocess.DEVNULL)
        snapshot.parent.mkdir(parents=True,exist_ok=True)
        with snapshot.open('xb') as f:
            f.write(raw)
        write_once(manifest.with_name(manifest.stem+'-committed.json'),dict(status='committed',dataVersion=version,sha256=old.sha(data)))
    except Exception as exc:
        for path,previous in before.items():
            old.atomic_bytes(path,previous)
        write_once(manifest.with_name(manifest.stem+'-rolled-back.json'),dict(status='rolled_back',reason=str(exc),dataVersion=version))
        raise
    return dict(applied=True,dataVersion=version,snapshot=str(snapshot),backup=str(backup),**summary)


def ordered_pending(items, index, document):
    have, _ = old.resolve(items, index)
    ids = {x['selected']['id'] for x in have}
    return sorted((p for p in items if p['id'] not in ids and p['canonicalFingerprint']),
                  key=lambda p: (not any(e in p['dynasty'] for e in ('唐','宋','五代','先秦')),
                                 not bool(p['anchorKeys']), p['id']))


def pilot_targets(pending, document):
    existing = {(old.norm(p['author']), old.norm(clean_body(p['content']))) for p in document['items']}
    chosen = [p for p in pending if p['anchorKeys']][:4]
    for genre in ('诗', '词'):
        eligible = [p for p in pending if p['genre'] == genre and any(e in p['dynasty'] for e in ('唐','宋','五代'))
                    and (old.norm(p['author']), p['canonicalFingerprint']) not in existing and p not in chosen]
        chosen.extend(eligible[:8])
    for p in pending:
        if len(chosen) >= 20:
            break
        if p not in chosen:
            chosen.append(p)
    return chosen[:20]


class Client(old.Client):
    def search(self, query):
        params = dict(q=query, page=1, pageSize=100, lang='zh-Hans')
        url = 'https://poetry.palemoky.com/api/search?' + urlencode(sorted(params.items()))
        key = hashlib.sha256(url.encode()).hexdigest()
        path = old.CACHE / 'cache' / (key + '.json')
        if path.exists():
            meta = read(old.CACHE / 'metadata' / (key + '.json'))
            if meta['url'] != url or old.sha(path) != meta['sha256']:
                raise ValueError('Source cache integrity failed')
            return read(path), meta, path, True
        with self.lock:
            if self.stop.is_set():
                raise RuntimeError('Source stopped: ' + str(self.reason))
            if self.requests >= self.budget:
                raise RuntimeError('Request budget reached')
            time.sleep(max(0, self.next-time.monotonic()))
            self.next = time.monotonic()+self.interval
            self.requests += 1
        try:
            with urlopen(Request(url, headers={'User-Agent':'HongzhuangCatalogSync/1.0.1 (cached, bounded)'}), timeout=15) as response:
                raw = response.read(4_000_001)
                if len(raw) > 4_000_000:
                    raise ValueError('Page exceeded limit')
                doc = json.loads(raw)
                if not isinstance(doc.get('data'),list):
                    raise ValueError('Unexpected API schema')
            write_once(path, doc)
            meta = dict(url=url, sha256=old.sha(path), acquiredAt=datetime.now(timezone.utc).isoformat())
            write_once(old.CACHE/'metadata'/(key+'.json'),meta)
            return doc,meta,path,False
        except HTTPError as exc:
            if exc.code in (401,403,429,503):
                self.reason = 'HTTP '+str(exc.code)
                self.stop.set()
            raise


def add_response(index, response):
    doc,meta,path,cached = response
    added = 0
    for row in doc['data']:
        if not isinstance(row,dict) or not isinstance(row.get('content'),list) or not isinstance(row.get('author'),dict):
            continue
        content='\n'.join(row['content'])
        if any(x in content for x in ('记忆体','海内存','\ufffd')) or any(0xe000<=ord(c)<=0xf8ff for c in content):
            continue
        body=old.norm(content)
        key=(old.norm(row['author']['name']),body)
        if any(x['row']['id']==row['id'] for x in index.get(key,[])):
            continue
        index[key].append(dict(row=row,content=content,source=dict(provider='https://poetry.palemoky.com',url=meta['url'],providerId=row['id'],cacheFile=path.relative_to(ROOT).as_posix(),sha256=meta['sha256'])))
        added+=1
    return added


def check_bindings(document, bindings):
    by_id={p['id']:p for p in document['items']}
    loaded={}
    for b in bindings:
        source=b['source'];path=ROOT/source['cacheFile']
        if not path.resolve().is_relative_to((old.CACHE/'cache').resolve()) or old.sha(path)!=source['sha256']:
            raise ValueError('Invalid import source')
        if path not in loaded:
            loaded[path]=read(path)
        rows=[r for r in loaded[path]['data'] if r.get('id')==source['providerId']]
        if len(rows)!=1:
            raise ValueError('Ambiguous provider ID')
        p=by_id[b['appId']];row=rows[0]
        expected=b.get('sourceVariant',{}).get('content',p['content'])
        if old.norm(row['author']['name'])!=old.norm(p['author']) or old.norm('\n'.join(row['content']))!=old.norm(expected):
            raise ValueError('Imported full text/author does not replay from source')
        if b.get('sourceVariant') and b['sourceVariant']['referenceFingerprint']!=old.norm(clean_body(p['content'])):
            raise ValueError('Variant attached to another canonical work')


def run_stage(name, targets, query_function, client, index, items, workers, records, zero_limit, source_authors=None):
    groups=defaultdict(list)
    for p in targets:
        q=query_function(p)
        if q:
            groups[q].append(p)
    queue=iter(groups);inflight={};processed=0;zero=0
    source_authors=source_authors if source_authors is not None else defaultdict(list)
    matched={e['selected']['id'] for e in resolved(items,index,source_authors)[0]}
    def submit(pool):
        if client.stop.is_set() or client.requests>=client.budget:
            return False
        q=next(queue,None)
        if q is None:
            return False
        inflight[pool.submit(client.search,q)]=q
        return True
    print(json.dumps(dict(stage=name,uniqueQueries=len(groups),workers=workers),ensure_ascii=False),flush=True)
    with ThreadPoolExecutor(max_workers=workers) as pool:
        for _ in range(workers):
            submit(pool)
        while inflight:
            done,_=wait(inflight,return_when=FIRST_COMPLETED)
            for future in done:
                q=inflight.pop(future);before=len(matched);record=dict(stage=name,query=q)
                try:
                    response=future.result();record.update(results=len(response[0]['data']),cached=response[3]);add_response(index,response)
                    for row in response[0]['data']:
                        key=(old.norm(row.get('author',{}).get('name','')),old.norm('\n'.join(row.get('content',[]))))
                        for hit in index.get(key,[]):
                            if hit['row']['id']==row.get('id') and not any(h['row']['id']==row['id'] for h in source_authors[key[0]]):
                                source_authors[key[0]].append(hit)
                    # A single response can resolve several selected works; update every identity.
                    matched={e['selected']['id'] for e in resolved(items,index,source_authors)[0]}
                except Exception as exc:
                    record['error']=type(exc).__name__+': '+str(exc)
                record['newMatches']=len(matched)-before;records.append(record)
                zero=0 if record['newMatches'] else zero+1
                processed+=1
                if processed%25==0:
                    print(json.dumps(dict(stage=name,processed=processed,total=len(groups),networkRequests=client.requests,newMatches=sum(r['newMatches'] for r in records)),ensure_ascii=False),flush=True)
                if zero>=zero_limit and not client.stop.is_set():
                    client.reason=f'{zero_limit} consecutive queries without a new exact match';client.stop.set()
                if not client.stop.is_set():
                    submit(pool)
    return processed


def main():
    sys.stdout.reconfigure(encoding='utf-8');ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--phase',choices=['pilot','full'],default='full');ap.add_argument('--workers',type=int,default=4)
    ap.add_argument('--interval',type=float,default=.5);ap.add_argument('--max-requests',type=int,default=1800)
    ap.add_argument('--offline',action='store_true');ap.add_argument('--preview',action='store_true')
    args=ap.parse_args()
    if not 1<=args.workers<=4 or not .5<=args.interval<=10 or not 1<=args.max_requests<=2500:
        ap.error('workers 1..4; interval .5..10; max-requests 1..2500')
    WORK.mkdir(parents=True,exist_ok=True)
    pilot_reports=sorted(WORK.glob('pilot-v1.0.1--*.json'))
    if args.phase=='full' and not args.offline:
        pilot=read(pilot_reports[-1]) if pilot_reports else {}
        if not pilot.get('approvedForFull') or pilot.get('catalogSha256')!=old.sha(CATALOG) or pilot.get('scriptSha256')!=old.sha(Path(__file__)):
            ap.error('A successful real pilot import for this catalog is required before full acquisition')
    lock=ROOT/'expansion/poetry-api-sync.lock';fd=os.open(lock,os.O_CREAT|os.O_EXCL|os.O_WRONLY);os.write(fd,str(os.getpid()).encode())
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S')+'--'+uuid4().hex[:6];started=time.monotonic()
    try:
        old.VERSION=VERSION
        document=read(ROOT/'data/poems.json');dict_hash=old.sha(ROOT/'data/dict.json');items=old.catalog_items(read(CATALOG));index=old.provider_index()
        source_authors=defaultdict(list);seen_source_ids=set()
        for hits in index.values():
            for h in hits:
                if h['row']['id'] not in seen_source_ids:
                    source_authors[old.norm(h['row']['author']['name'])].append(h);seen_source_ids.add(h['row']['id'])
        initial,_=resolved(items,index,source_authors);initial_ids={e['selected']['id'] for e in initial}
        pending=[p for p in ordered_pending(items,index,document) if p['id'] not in initial_ids and p['id'] not in document.get('poetryApiBindings',{})]
        targets=pilot_targets(pending,document) if args.phase=='pilot' else pending
        client=Client(interval=args.interval,budget=min(args.max_requests,60) if args.phase=='pilot' else args.max_requests);records=[]
        print(json.dumps(dict(phase=args.phase,targetWorks=len(targets),alreadyMatched=len(initial),workers=args.workers,interval=args.interval),ensure_ascii=False),flush=True)
        if not args.offline:
            run_stage('literal_phrase',targets,phrase_query,client,index,items,args.workers,records,30,source_authors)
            found={e['selected']['id'] for e in resolved(items,index,source_authors)[0]}
            remaining=[p for p in targets if p['id'] not in found]
            # A low-yield phrase strategy switches once to title search. HTTP limits never reset.
            if client.reason and 'consecutive queries without a new exact match' in client.reason:
                client.stop.clear();client.reason=None
                print('Literal phrase strategy exhausted; switching once to title fallback.',flush=True)
            if not client.stop.is_set() and remaining:
                run_stage('title_fallback',remaining,title_query,client,index,items,args.workers,records,30,source_authors)
        accepted,held=resolved(items,index,source_authors)
        newly_fetched=[e for e in accepted if e['selected']['id'] not in initial_ids]
        # Resuming a pilot may reuse its successful downloads before they were committed.
        new_matches=[e for e in accepted if e['selected']['id'] not in document.get('poetryApiBindings',{})]
        if args.phase=='pilot':
            # Only the sample's actual matches are newly bound during the pilot.
            # A tune/title query can return another selected work: accept at most 20
            # newly source-verified catalog identities, rather than dropping valid results.
            allowed={e['selected']['id'] for e in new_matches[:20]}|set(document.get('poetryApiBindings',{}))
            accepted=[e for e in accepted if e['selected']['id'] in allowed]
        proposed,summary=variant_plan(document,accepted)
        new_bindings=[b for k,b in proposed.get('poetryApiBindings',{}).items() if k not in document.get('poetryApiBindings',{})]
        check_bindings(proposed,new_bindings)
        if any(p!=proposed['items'][i] for i,p in enumerate(document['items'])) or dict_hash!=old.sha(ROOT/'data/dict.json'):
            raise ValueError('Existing database/dictionary would change')
        gate=args.phase!='pilot' or (len(new_matches)>=3 and len(new_bindings)>=3 and bool(summary['newRows'] or summary['newlyVisible'] or any(e.get('variant') for e in new_matches)))
        imported=commit_with_audit(document,proposed,summary) if gate and not args.preview else dict(applied=False,reason='pilot_gate_failed' if not gate else 'preview',**summary)
        checks=dict(sourceReplay=True,oldRowsPreserved=True,dictionaryUnchanged=True)
        if imported.get('applied'):
            subprocess.run([sys.executable,'-B',str(ROOT/'scripts/export_pending_enrichment.py')],check=True,cwd=ROOT)
            if (ROOT/'data/poems.json').read_bytes()!=(ROOT/'app/assets/data/poems.json').read_bytes():
                raise ValueError('Assets out of sync')
            checks.update(databaseValidated=True,assetsIdentical=True,originalsAudit=True)
        report=dict(toolVersion=VERSION,scriptSha256=old.sha(Path(__file__)),phase=args.phase,catalogSha256=old.sha(CATALOG),sampleIds=[p['id'] for p in targets] if args.phase=='pilot' else None,
                    approvedForFull=args.phase=='pilot' and gate and bool(imported.get('applied')),networkRequests=client.requests,
                    processedQueries=len(records),newMatches=len(new_bindings),candidateUnboundMatches=len(new_matches),newlyFetchedMatches=len(newly_fetched),matched=len(accepted),held=len(items)-len(accepted),
                    variantBindings=sum(bool(b.get('sourceVariant')) for b in proposed.get('poetryApiBindings',{}).values()),
                    stopped=client.stop.is_set(),stopReason=client.reason,records=records,database=imported,checks=checks,
                    elapsedSeconds=round(time.monotonic()-started,2),apkBuilt=False)
        path=WORK/(args.phase+'-v1.0.1--'+stamp+'.json');write_once(path,report)
        print(json.dumps(dict(report=str(path),**{k:v for k,v in report.items() if k not in ['records','sampleIds','catalogSha256','database']},database={k:v for k,v in imported.items() if k not in ['newRows','newlyVisible','preservedExistingIds']}),ensure_ascii=False,indent=2),flush=True)
        if args.phase=='pilot' and not report['approvedForFull']:
            return 2
        return 0
    finally:
        os.close(fd);lock.unlink()


if __name__=='__main__':
    raise SystemExit(main())
