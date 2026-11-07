"""Reuse explicit body-note senses for missing chars; preserve old dictionary."""
from collections import defaultdict
import hashlib,json,subprocess,sys
from enrichment_pipeline import ROOT,read,write_once
from data_scope import active_items
from translation_overlay_v1_0_0 import overlay_for
sys.path.insert(0,str(ROOT/'expansion/python-packages'))
from pypinyin import pinyin,Style

EXCLUDED={'姚','钧','裾','幢'}  # mixed-term or sense ambiguities retained for review


def sense(value):
    value=value.split('。')[0].strip()+'。'
    if any(s in value for s in ('：',':','印“','待补','暂无')):return None
    if value.count('“')!=value.count('”') or len(value)>100:return None
    return value


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    pp=ROOT/'data/dict.json';asset=ROOT/'app/assets/data/dict.json'
    dictionary=read(pp);document=read(ROOT/'data/poems.json');candidates=defaultdict(list)
    for poem in active_items(document):
        extra=overlay_for(document,poem)
        for note in poem['notes'] or (extra.get('notes',[]) if extra else []):
            ch=note['term'];definition=sense(note['meaning'])
            if len(ch)!=1 or ch not in poem['content'] or ch in dictionary['chars'] or ch in EXCLUDED or not definition or not extra:continue
            source=extra['source'];path=ROOT/source['cacheFile']
            if hashlib.sha256(path.read_bytes()).hexdigest()!=source['sha256']:raise ValueError('Changed source')
            candidates[ch].append(dict(poemId=poem['id'],definition=definition,originalNote=note,source=source))
    if not candidates:print('No eligible new dictionary entries.');return
    previous=dictionary['dataVersion'];parts=previous.split('.');parts[-1]=str(int(parts[-1])+1);version='.'.join(parts)
    checkpoint=ROOT/'expansion/checkpoints'/('pre-release-dictionary-v'+version)
    checkpoint.mkdir(parents=True,exist_ok=False)
    backup={pp:pp.read_bytes(),asset:asset.read_bytes()}
    for path,raw in backup.items():(checkpoint/path.name.replace('.json','-'+('asset' if path==asset else 'data')+'.json')).write_bytes(raw)
    for ch,records in candidates.items():
        dictionary['chars'][ch]=dict(pinyin=sorted({v for group in pinyin(ch,heteronym=True,style=Style.TONE3) for v in group}),
                                    meanings=[],ancient=list(dict.fromkeys(r['definition'] for r in records)))
        dictionary.setdefault('charProvenance',{})[ch]=dict(method='existing_explicit_body_notes',literaryApproved=False,records=records)
    dictionary['dataVersion']=version
    write_once(ROOT/'expansion/dictionary'/('release-note-senses-v'+version+'.json'),dict(previous=previous,version=version,additions=dict(candidates),excluded=sorted(EXCLUDED)))
    raw=(json.dumps(dictionary,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    try:
        for path in backup:path.write_bytes(raw)
        for script,args in [('validate_data.py',['--original-only']),('audit_expansion.py',[]),('export_pending_enrichment.py',[])]:
            subprocess.run([sys.executable,'-B',str(ROOT/'scripts'/script),*args],check=True)
    except BaseException:
        for path,old in backup.items():path.write_bytes(old)
        raise
    print(json.dumps(dict(added=len(candidates),dictionaryVersion=version),ensure_ascii=False))


if __name__=='__main__':main()
