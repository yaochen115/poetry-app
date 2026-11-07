"""Post-run only: reconcile actual row/activation deltas and preserve old data evidence."""
from collections import Counter
import hashlib,json,sys
from enrichment_pipeline import ROOT,read,write_once
from data_scope import active_items
from translation_overlay_v1_0_0 import overlay_for

def compare(before,after):
 old={p['id']:p for p in before['items']};new={p['id']:p for p in after['items']}
 if not all(new.get(i)==p for i,p in old.items()):raise ValueError('Old original/translation row changed')
 before_active={p['id'] for p in active_items(before)};after_active={p['id'] for p in active_items(after)}
 added=set(new)-set(old);enabled=after_active-before_active
 if not before_active<=after_active:raise ValueError('Old selected work was removed')
 return dict(newRows=len(added),enabledOldArchived=len(enabled-added),activeIncrease=len(enabled),
             oldRowsPreserved=len(old),newRowIds=sorted(added),activatedArchivedIds=sorted(enabled-added))

def main():
 sys.stdout.reconfigure(encoding='utf-8')
 current=read(ROOT/'data/poems.json');baseline=read(ROOT/'data/versions/poems-v1.2.27.json');pre_full=read(ROOT/'data/versions/poems-v1.2.32.json')
 report_path=sorted((ROOT/'expansion/poetry-api-sync-v1.0.1').glob('full-v1.0.1--*.json'))[-1];run=read(report_path)
 if current['dataVersion']!=run['database']['dataVersion']:raise ValueError('Database changed after final report')
 if (ROOT/'data/poems.json').read_bytes()!=(ROOT/'app/assets/data/poems.json').read_bytes():raise ValueError('Assets differ')
 if baseline['translationImports']!=current['translationImports']:raise ValueError('Existing imported translations changed')
 active=active_items(current);bindings=current['poetryApiBindings']
 result=dict(toolVersion='1.0.1',dataVersion=current['dataVersion'],formalRun=report_path.relative_to(ROOT).as_posix(),
    formalRequests=run['networkRequests'],formalQueries=run['processedQueries'],formalSeconds=run['elapsedSeconds'],
    formal=compare(pre_full,current),includingPilots=compare(baseline,current),active=len(active),stored=len(current['items']),
    sourceBindings=len(bindings),variantBindings=sum('sourceVariant' in b for b in bindings.values()),remainingCatalog=2000-len(bindings),
    availableTranslations=sum(bool(p.get('translation','').strip()) or bool(overlay_for(current,p)) for p in active),
    perCategory=dict(Counter(p['category'] for p in active)),
    springRiverMoon=[dict(id=p['id'],title=p['title'],author=p['author'],characters=sum('\u3400'<=c<='\u9fff' for c in p['content'])) for p in active if '春江花月夜' in p['title'] and p['author']=='张若虚'],
    sourceLimit=run['stopReason'],assetsIdentical=True,oldRowsAndTranslationsPreserved=True,apkBuilt=False)
 write_once(ROOT/'expansion/poetry-api-sync-v1.0.1/post-check-v1.0.1.json',result)
 print(json.dumps({k:({kk:vv for kk,vv in v.items() if not kk.endswith('Ids')} if k in ['formal','includingPilots'] else v) for k,v in result.items()},ensure_ascii=False,indent=2))
if __name__=='__main__':main()
