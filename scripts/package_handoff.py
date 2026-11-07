"""Create and verify a portable source/data handoff ZIP, explicitly labeling old APKs."""
import argparse
import hashlib
import json
import sys
import zipfile
from pathlib import Path
from data_scope import active_items,disabled_ids

ROOT=Path(__file__).resolve().parents[1]
PREFIX='hongzhuang-project'


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument('--output',required=True,type=Path)
    parser.add_argument('--original-archive',type=Path)
    args=parser.parse_args()
    output=args.output.resolve()
    output.parent.mkdir(parents=True,exist_ok=True)
    temp=output.with_suffix('.building.zip')
    excluded={'.git','.dart_tool','.gradle','.idea','build','__pycache__'}
    excluded_names={'local.properties','.flutter-plugins-dependencies'}
    allowed={'app','data','docs','expansion','scripts','prototype','release'}
    entries=[]
    data=json.loads((ROOT/'data/poems.json').read_text(encoding='utf-8'))
    active=active_items(data)
    complete=sum(p.get('editorialStatus')!='original_only' for p in active)
    files=[]
    for path in sorted(ROOT.rglob('*')):
        if not path.is_file():continue
        rel=path.relative_to(ROOT)
        if rel.parts[0] not in allowed and str(rel) not in {'START_HERE.md','CLAUDE.md','AGENTS.md'}:continue
        if any(part in excluded for part in rel.parts) or path.name in excluded_names or path.suffix in {'.pyc','.pyo','.log'}:continue
        files.append((rel.as_posix(),path))
    with zipfile.ZipFile(temp,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        def add(name,content):
            archive_name=PREFIX+'/'+name
            z.writestr(archive_name,content)
            entries.append(dict(path=name,bytes=len(content),sha256=hashlib.sha256(content).hexdigest()))
        for name,path in files:add(name,path.read_bytes())
        # Restore human-readable names lost in the source archive's doc filenames.
        aliases={'doc-182.md':'交接文档.md','doc-183.md':'技术方案.md','doc-184.md':'数据规范.md',
                 'doc-185.md':'进度日志.md','doc-186.md':'需求文档.md'}
        for old,new in aliases.items():
            if (ROOT/'docs'/old).exists():add('docs/'+new,(ROOT/'docs'/old).read_bytes())
        history=[]
        if args.original_archive:
            with zipfile.ZipFile(args.original_archive) as original:
                for version in ['1.0.0','1.0.1']:
                    matches=[p for p in original.infolist() if p.filename.startswith('release/') and p.filename.endswith('-v'+version+'.apk')]
                    if len(matches)!=1:raise ValueError('Historical APK not uniquely identified')
                    name='release/历史安装包/红妆-v'+version+'.apk'
                    add(name,original.read(matches[0]));history.append(name)
        note=('这些APK来自原始项目交接压缩包，仅保留作历史参考。\n'
              '它们不是当前4200原文及新增译注的构建产物。\n'
              '本交接包交付当前源码、数据及接续说明；新APK尚未构建。\n')
        add('release/历史安装包/请先阅读.txt',note.encode('utf-8'))
        manifest=dict(packageDate='2026-11-03',packageKind='source_data_handoff',
            activeEntries=len(active),storedEntries=len(data['items']),disabledEntries=len(disabled_ids(data)),
            completeWithTranslation=complete,pendingEnrichment=len(active)-complete,
            poemDataVersion=data['dataVersion'],historicalApks=history,newApkBuilt=False,
            flutterTestsRun=False,notes='START_HERE.md是接手入口；manifest列出自身以外的文件散列。',files=entries)
        z.writestr(PREFIX+'/PACKAGE_MANIFEST.json',json.dumps(manifest,ensure_ascii=False,indent=2)+'\n')
    with zipfile.ZipFile(temp) as z:
        if z.testzip() is not None:raise ValueError('ZIP CRC verification failed')
        manifest=json.loads(z.read(PREFIX+'/PACKAGE_MANIFEST.json'))
        for item in manifest['files']:
            content=z.read(PREFIX+'/'+item['path'])
            if hashlib.sha256(content).hexdigest()!=item['sha256']:raise ValueError('File hash mismatch')
        if z.read(PREFIX+'/data/poems.json')!=z.read(PREFIX+'/app/assets/data/poems.json'):raise ValueError('Poem asset mismatch')
        if z.read(PREFIX+'/data/dict.json')!=z.read(PREFIX+'/app/assets/data/dict.json'):raise ValueError('Dictionary asset mismatch')
        for required in ['START_HERE.md','expansion/CURRENT_STATE.md','expansion/AI_HANDOFF.md',
                         'expansion/pending-enrichment.json','app/lib/models.dart','scripts/apply_enrichment_batch.py']:
            z.getinfo(PREFIX+'/'+required)
    temp.replace(output)
    digest=hashlib.sha256(output.read_bytes()).hexdigest()
    output.with_suffix('.zip.sha256.txt').write_text(digest+'  '+output.name+'\n',encoding='utf-8')
    print(json.dumps(dict(output=str(output),bytes=output.stat().st_size,files=len(entries)+1,
                         activeEntries=len(active),completeWithTranslation=complete,pending=len(active)-complete,
                         sha256=digest,crcAndFileHashesVerified=True),ensure_ascii=False))


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8')
    main()
