"""Complete existing entries without changing their original text, IDs or provenance."""
import argparse
import copy
import json
import subprocess
import sys
from pathlib import Path
from data_scope import disabled_ids

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'expansion/python-packages'))
from pypinyin import pinyin,Style


def read(p):return json.loads(p.read_text(encoding='utf-8'))
def encode(d):return (json.dumps(d,ensure_ascii=False,indent=2)+'\n').encode('utf-8')


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('batch',type=Path)
    args=parser.parse_args()
    batch_path=args.batch.resolve()
    if batch_path.parent != (ROOT/'expansion/enrichment').resolve():
        raise ValueError('Enrichment batch must be in expansion/enrichment')
    batch=read(batch_path)
    pp,dp=ROOT/'data/poems.json',ROOT/'data/dict.json'
    poems,dictionary=read(pp),read(dp)
    ids=[p['id'] for p in batch['patches']]
    if not ids or len(ids)!=len(set(ids)):raise ValueError('Empty or duplicate patch IDs')
    if set(ids)&disabled_ids(poems):raise ValueError('Disabled originals must remain archived')
    by_id={p['id']:p for p in poems['items']}
    if all(by_id[i].get('editorialStatus')=='complete' for i in ids):
        for patch in batch['patches']:
            if any(by_id[patch['id']].get(k)!=v for k,v in patch.items()):raise ValueError('Different existing enrichment')
        print('Identical enrichment already applied.')
        return
    updates={}
    for patch in batch['patches']:
        if set(patch)!={'id','translation','notes','tags'}:raise ValueError('Only enrichment fields may change')
        p=by_id[patch['id']]
        if p.get('editorialStatus')!='original_only':raise ValueError('Entry is not pending')
        if not patch['translation'].strip() or not 3<=len(patch['notes'])<=18 or not patch['tags']:
            raise ValueError('Incomplete translation/notes/tags')
        p.update(patch,editorialStatus='complete',pending=[])
        updates[p['id']]=copy.deepcopy(p)
    chars={c for p in updates.values() for c in p['content'] if '\u4e00'<=c<='\u9fff'}
    for ch in chars-set(dictionary['chars']):
        if ch not in batch['dictionaryAdditions']:raise ValueError(f'No edited definition: {ch}')
        dictionary['chars'][ch]=dict(pinyin=sorted({x for g in pinyin(ch,heteronym=True,style=Style.TONE3) for x in g}),
                                     **batch['dictionaryAdditions'][ch])
    for p in updates.values():
        for n in p['notes']:
            term=n['term']
            if len(term)==2 and term in p['content'] and term not in dictionary['words']:
                dictionary['words'][term]=n['meaning']
    source_changes={}
    found=set()
    for path in (ROOT/'expansion/batches').glob('*.json'):
        original=read(path)
        changed=False
        for i,p in enumerate(original['items']):
            if p['id'] in updates:
                original['items'][i]=updates[p['id']]
                found.add(p['id']);changed=True
        if changed:
            original.setdefault('enrichmentHistory',[]).append(dict(batch=batch_path.name,ids=sorted(updates),
                note=batch.get('policy', '后续译注入库')+'；原文、ID和原始来源保持不变。原provenance描述原文入库当时的策略。'))
            source_changes[path]=encode(original)
    if found!=set(ids):raise ValueError('Original provenance batch missing')
    poems['dataVersion']=batch['dataVersion'];dictionary['dataVersion']=batch['dictionaryVersion']
    writes={pp:encode(poems),dp:encode(dictionary),ROOT/'app/assets/data/poems.json':encode(poems),
            ROOT/'app/assets/data/dict.json':encode(dictionary),**source_changes}
    backups={p:p.read_bytes() for p in writes}
    checkpoint=ROOT/'expansion/checkpoints'/('pre-enrichment-'+batch_path.stem)
    for path,old in backups.items():
        dest=checkpoint/path.relative_to(ROOT)
        dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and dest.read_bytes()!=old:raise ValueError('Checkpoint conflict')
        dest.write_bytes(old)
    try:
        for path,data in writes.items():path.write_bytes(data)
        subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py'),'--original-only'],check=True)
        subprocess.run([sys.executable,str(ROOT/'scripts/audit_expansion.py')],check=True)
    except BaseException:
        for path,old in backups.items():path.write_bytes(old)
        raise
    print(f'Completed {len(updates)} existing entries; no original text or ID changed.')


if __name__=='__main__':main()
