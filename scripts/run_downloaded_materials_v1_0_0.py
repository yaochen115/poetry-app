"""Batch local-only conversion/import; no downloads, models, or APK builds."""
import json
from pathlib import Path
import subprocess
import sys
from collections import Counter
from enrichment_pipeline import Pipeline, ROOT, digest, read, write_once, validate_patch


def bump(version):
    parts = version.split('.'); parts[-1] = str(int(parts[-1])+1)
    return '.'.join(parts)


def apply(path):
    subprocess.run([sys.executable, '-B', str(ROOT/'scripts/apply_enrichment_batch.py'), str(path)], check=True)


def versions():
    return bump(read(ROOT/'data/poems.json')['dataVersion']), bump(read(ROOT/'data/dict.json')['dataVersion'])


def next_batch():
    return f"{max(int(p.stem) for p in (ROOT/'expansion/enrichment').glob('*.json') if p.stem.isdigit())+1:03}"


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    target = ROOT/'expansion/working/download-import-run-v1.0.0.json'
    if target.exists():
        previous = read(target)
        print(json.dumps(dict(alreadyExecuted=True, applied=previous['applied']), ensure_ascii=False, indent=2))
        return
    output = ROOT/'expansion/working/download-conversion-v1.0.0'
    subprocess.run([sys.executable, '-B', str(ROOT/'scripts/convert_downloaded_materials_v1_0_0.py'),
        'prepare', '--source', str(ROOT/'expansion/sources/chinese-gushiwen/guwen'),
        '--source', str(ROOT/'expansion/sources/poetry-source/source'), '--output', str(output)], check=True)
    report = dict(toolVersion='1.0.0', downloads=0, modelCalls=0, apkBuilds=0, applied=[])
    delivery = read(ROOT/'expansion/working/v2/editorial/lunyu-23-delivery-20261104.json')
    pipe = Pipeline(); ready = [pid for pid in delivery['approvedIds'] if pid in pipe.pending]
    if ready:
        batch = next_batch(); pv, dv = versions()
        pipe.assemble(batch, pv, dv, ids=ready)
        apply(ROOT/'expansion/enrichment'/f'{batch}.json')
        report['applied'].append(dict(batch=batch, count=len(ready), method='existing_reviewed_results'))
    pipe = Pipeline(); packet = read(output/'candidates-v1.0.0.json')
    patches = []; provenance = []; held = []
    for candidate in packet['candidates']:
        pid = candidate['patch']['id']
        if pid not in pipe.pending: continue
        reasons = list(candidate['flags'])
        missing = sorted({ch for ch in pipe.poems[pid]['content'] if '\u4e00' <= ch <= '\u9fff'}-set(pipe.dictionary))
        if missing: reasons.append('missing_dictionary')
        if reasons:
            held.append(dict(id=pid, reasons=reasons, missingCharacters=missing)); continue
        if digest({k:v for k,v in candidate.items() if k != 'candidateHash'}) != candidate['candidateHash']:
            raise ValueError('Changed candidate: '+pid)
        import hashlib
        if hashlib.sha256(Path(candidate['source']['file']).read_bytes()).hexdigest() != candidate['source']['sha256']:
            raise ValueError('Changed reference source: '+pid)
        if pipe.input_hash(pipe.poems[pid]) != candidate['inputHash']:
            raise ValueError('Changed original: '+pid)
        validate_patch(candidate['patch'], pipe.poems[pid], pipe.tags[pipe.poems[pid]['category']])
        patches.append(candidate['patch'])
        provenance.append(dict(id=pid, source=candidate['source'], candidateHash=candidate['candidateHash']))
    if patches:
        batch = next_batch(); pv, dv = versions()
        path = ROOT/'expansion/enrichment'/f'{batch}.json'
        write_once(path, dict(dataVersion=pv, dictionaryVersion=dv, patches=patches,
            dictionaryAdditions={},
            policy='负责人授权脚本整理现有本地资料；自动结构与身份检查通过，未逐篇语义复核，不声称独立编写。',
            review=dict(literaryApproved=False, automaticSourceImport=True),
            conversionProvenance=provenance), accept_identical=False)
        apply(path)
        report['applied'].append(dict(batch=batch, count=len(patches), method='automatic_source_import', literaryApproved=False))
    subprocess.run([sys.executable, '-B', str(ROOT/'scripts/export_pending_enrichment.py')], check=True)
    report.update(held=held, heldReasons=dict(Counter(reason for row in held for reason in row['reasons'])))
    write_once(target, report)
    print(json.dumps({k:v for k,v in report.items() if k!='held'}, ensure_ascii=False, indent=2))


if __name__ == '__main__': main()
