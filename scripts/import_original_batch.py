"""Import an approved original-only batch; preserve prior entries and roll back on failure."""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path
from data_scope import active_items

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('batch',type=Path)
    args=parser.parse_args()
    batch_path=args.batch.resolve()
    if batch_path.parent != (ROOT/'expansion/batches').resolve():
        raise ValueError('Batch must be saved in expansion/batches')
    batch=json.loads(batch_path.read_text(encoding='utf-8'))
    target=batch['targetTotal']
    active_target=batch.get('targetActiveTotal',target)
    if batch.get('stage')!='original_only' or active_target%4 or not 0<active_target<=4200:
        raise ValueError('Invalid original-only target')
    path=ROOT/'data/poems.json'
    assets=ROOT/'app/assets/data/poems.json'
    old_bytes,old_assets=path.read_bytes(),assets.read_bytes()
    if old_bytes!=old_assets:
        raise ValueError('Existing source/asset mismatch')
    data=json.loads(old_bytes)
    by_id={p['id']:p for p in data['items']}
    incoming=batch['items']
    if not incoming or len({p['id'] for p in incoming})!=len(incoming):
        raise ValueError('Empty batch or duplicate incoming IDs')
    if all(p['id'] in by_id for p in incoming):
        if not all(by_id[p['id']]==p for p in incoming):
            raise ValueError('Imported batch has different contents')
        print('Identical batch already imported; no entries appended.')
        return
    if len(data['items'])!=batch['baseTotal'] or any(p['id'] in by_id for p in incoming):
        raise ValueError('Base count mismatch or ID collision')
    if any(p.get('editorialStatus')!='original_only' or p['translation']!='' or p['notes']!=[] for p in incoming):
        raise ValueError('Incoming originals lack explicit pending markers')
    if any(any(0xe000<=ord(c)<=0xf8ff for c in p['content']) for p in incoming):
        raise ValueError('New originals contain unsupported private-use glyphs; replace the source before import')
    if any(re.search(r'<[\u3400-\u9fff]|[{}]',p['content']) for p in incoming):
        raise ValueError('New originals contain unresolved composite-glyph placeholders')
    checkpoint=ROOT/'expansion/checkpoints'/f'pre-{batch_path.stem}'
    checkpoint.mkdir(parents=True,exist_ok=True)
    for name,content in [('poems.json',old_bytes),('dict.json',(ROOT/'data/dict.json').read_bytes())]:
        dest=checkpoint/name
        if dest.exists() and dest.read_bytes()!=content:
            raise ValueError('Checkpoint conflict; do not overwrite')
        dest.write_bytes(content)
    data['items'].extend(incoming)
    if 'disabledEntries' in batch:
        data['disabledEntries']=batch['disabledEntries']
    if len(data['items'])!=target or Counter(p['category'] for p in active_items(data))!=Counter({c:active_target//4 for c in ['唐诗','宋词','元曲','古文']}):
        raise ValueError('Unexpected total or category counts')
    data['dataVersion']=batch['dataVersion']
    encoded=(json.dumps(data,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    try:
        path.write_bytes(encoded)
        assets.write_bytes(encoded)
        subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py'),
                        '--original-only','--expected-per-category',str(active_target//4)],check=True)
        subprocess.run([sys.executable,str(ROOT/'scripts/audit_expansion.py')],check=True)
        require={p['id']:p for p in data['items']}
        if not all(require[p['id']]==p for p in by_id.values()):
            raise ValueError('Previously imported entry changed')
    except BaseException:
        path.write_bytes(old_bytes)
        assets.write_bytes(old_assets)
        raise
    print(f'Imported {len(incoming)} originals; stored {target}, active {active_target}. All prior entries preserved.')


if __name__=='__main__':
    main()
