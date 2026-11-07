"""Partial source imports: usable translations, without claiming full enrichment."""
from pathlib import Path
import hashlib
import json
import subprocess
import sys
from uuid import uuid4
from enrichment_pipeline import ROOT, read, write_once
from data_scope import active_items


def overlay_for(document, poem):
    entry=document.get('translationImports',{}).get(poem['id'])
    if not entry or entry.get('baseContent')!=poem['content'] or entry.get('baseAuthor')!=poem['author']:
        return None
    return entry if isinstance(entry.get('translation'),str) and entry['translation'].strip() else None


def apply(entries, root=ROOT):
    pp=root/'data/poems.json'; asset=root/'app/assets/data/poems.json'
    doc=read(pp); by_id={p['id']:p for p in active_items(doc)}
    imports=doc.setdefault('translationImports',{}); added=[]
    for entry in entries:
        pid=entry['id']; poem=by_id[pid]
        if poem.get('translation','').strip() or overlay_for(doc,poem):continue
        if entry['baseContent']!=poem['content'] or entry['baseAuthor']!=poem['author']:
            raise ValueError('Stale source identity: '+pid)
        if len(entry['translation'].strip())<8:raise ValueError('Empty/short translation')
        source=entry['source']; path=root/source['cacheFile']
        if not path.resolve().is_relative_to((root/'expansion').resolve()):raise ValueError('Invalid source path')
        if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('Source changed')
        imports[pid]=entry;added.append(pid)
    if not added:return dict(added=0)
    parts=doc['dataVersion'].split('.');parts[-1]=str(int(parts[-1])+1);doc['dataVersion']='.'.join(parts)
    version=doc['dataVersion'];checkpoint=root/'expansion/checkpoints'/('pre-translation-import-'+version+'-'+uuid4().hex[:8])
    old={pp:pp.read_bytes(),asset:asset.read_bytes()}
    for path,raw in old.items():
        dest=checkpoint/path.relative_to(root);dest.parent.mkdir(parents=True,exist_ok=True);dest.write_bytes(raw)
    write_once(root/'expansion/translation-imports'/('data-v'+version+'.json'),
        dict(dataVersion=version,ids=added,entries=[imports[i] for i in added],
             policy='Source-imported partial data; no literary approval or completion claim.'))
    encoded=(json.dumps(doc,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    try:
        for path in old:path.write_bytes(encoded)
        if root==ROOT:
            for script,args in [('validate_data.py',['--original-only']),('audit_expansion.py',[]),('export_pending_enrichment.py',[])]:
                subprocess.run([sys.executable,'-B',str(root/'scripts'/script),*args],check=True)
    except BaseException:
        for path,raw in old.items():path.write_bytes(raw)
        raise
    return dict(added=len(added),dataVersion=version,ids=added,checkpoint=str(checkpoint))
