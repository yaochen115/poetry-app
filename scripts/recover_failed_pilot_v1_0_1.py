"""One-time recovery: retain failed pilot snapshot, publish a new rollback version."""
import json
from sync_poetry_api_v1_0_0 import ROOT,read,atomic_bytes,write_once

def main():
 doc=read(ROOT/'data/poems.json')
 if doc['dataVersion']!='1.2.30':
  raise ValueError('Recovery only applies to failed pilot data1.2.30')
 checkpoints=list((ROOT/'expansion/checkpoints').glob('pre-poetry-api-data-v1.2.30--*'))
 if len(checkpoints)!=1:raise ValueError('Ambiguous rollback checkpoint')
 previous=read(checkpoints[0]/'data/poems.json')
 if previous['dataVersion']!='1.2.29':raise ValueError('Unexpected prior version')
 previous['dataVersion']='1.2.31'
 raw=(json.dumps(previous,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
 with (ROOT/'data/versions/poems-v1.2.31.json').open('xb') as f:f.write(raw)
 for p in [ROOT/'data/poems.json',ROOT/'app/assets/data/poems.json']:atomic_bytes(p,raw)
 write_once(ROOT/'expansion/poetry-api-sync-v1.0.1/failed-pilot-recovery-v1.0.1.json',dict(
  failedDataVersion='1.2.30',restoredDataFrom='1.2.29',publishedDataVersion='1.2.31',
  reason='Post-import source audit detected an unbound duplicate row; formal run not started. Failed snapshot retained.'))
 print('Recovered prior rows and bindings as data1.2.31; failed1.2.30 retained.')
if __name__=='__main__':main()
