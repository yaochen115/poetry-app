"""Release-stage structural, provenance and coverage audit; no semantic claims."""
from collections import Counter,defaultdict
from pathlib import Path
import hashlib,json,re,sys,unicodedata
from enrichment_pipeline import ROOT,read,write_once
from data_scope import active_items
from translation_overlay_v1_0_0 import overlay_for
from convert_downloaded_materials_v1_0_0 import normal,text,records,first
from import_hf_translations_v1_0_0 import split_translation
import probe_gushiwenku_v1_0_0 as ku
import site_translation_parser_v1_0_2 as guwen


def compact(value):return re.sub(r'\s+','',unicodedata.normalize('NFC',value))


def hanzi(value):return {c for c in value if '\u3400'<=c<='\u9fff' or c=='〇'}


def valid_pinyin(value):
    if not isinstance(value,str) or not value:return False
    letters=''.join(c for c in unicodedata.normalize('NFD',value) if unicodedata.category(c)!='Mn')
    return bool(re.fullmatch(r'[a-z]+[1-5]?',letters))


def replay(entry,loaded):
    source=entry['source'];path=ROOT/source['cacheFile']
    if path.suffix=='.html':
        if 'gushiwenku.cn' in source['url']:
            row=ku.parse(path.read_text(encoding='utf-8'))
            return row['content'],row['writer'],[text(row['translation'])]
        row=guwen.extract(path.read_bytes(),url=source['url'])
        return row['content'],row['author'],[text(row['translation'])]
    if 'matched-rows' in str(path):
        raw=read(path);work=raw['tb_gushiwen'];options=[]
        for f in (raw.get('tb_fanyis') or {}).get('fanyis',[]) or []:
            tr,_=split_translation(f.get('cont',''),f.get('nameStr',''))
            if tr:options.append(text(tr))
        if work.get('yizhu'):
            tr,_=split_translation(work['yizhu'],'译文及注释')
            if tr:options.append(text(tr))
        return work['cont'],work['author'],options
    if path not in loaded:loaded[path]=records(path)
    row=loaded[path][source['row']]
    return first(row,'content','paragraph','paragraphs'),first(row,'authorName','writer','author'),[text(first(row,'translation','translate'))]


def audit():
    doc=read(ROOT/'data/poems.json');dictionary=read(ROOT/'data/dict.json');items=active_items(doc)
    errors=[];flags=[];seen=defaultdict(list);loaded={};hashes={};available=[];notes_checked=0
    for poem in items:
        extra=overlay_for(doc,poem)
        translation=poem.get('translation','').strip() or (extra['translation'].strip() if extra else '')
        if not translation:continue
        available.append(poem);seen[compact(translation)].append(poem['id'])
        def error(reason):errors.append(dict(id=poem['id'],reason=reason))
        if any(s in translation for s in ('暂无翻译','待翻译','译文略','展开阅读全文','请先登录')):error('placeholder_or_access_notice')
        if re.match(r'^\s*(注释|注解|词句注释)',translation):error('annotations_in_translation')
        if '\ufffd' in translation:error('replacement_character_in_translation')
        if re.search(r'<\s*(p|div|br|span|strong)\b',translation,re.I):error('html_in_translation')
        if normal(translation)==normal(poem['content']):flags.append(dict(id=poem['id'],reason='translation_equals_original'))
        if translation.endswith(('…','...')):flags.append(dict(id=poem['id'],reason='translation_ends_with_ellipsis'))
        notes=poem.get('notes',[]) or (extra.get('notes',[]) if extra else [])
        for note in notes:
            notes_checked+=1
            if not isinstance(note,dict) or not isinstance(note.get('term'),str) or not isinstance(note.get('meaning'),str) or not note['term'].strip() or not note['meaning'].strip():error('invalid_note');continue
            if note['term'] not in poem['content']:flags.append(dict(id=poem['id'],reason='note_term_outside_body',term=note['term']))
        if extra and not poem.get('translation','').strip():
            try:
                source=extra['source'];path=(ROOT/source['cacheFile']).resolve()
                if not path.is_relative_to((ROOT/'expansion').resolve()):raise ValueError('source_path_outside_project')
                if path not in hashes:hashes[path]=hashlib.sha256(path.read_bytes()).hexdigest()
                if hashes[path]!=source['sha256']:raise ValueError('source_hash_changed')
                original,author,candidates=replay(extra,loaded)
                if normal(original)!=normal(poem['content']) or normal(author)!=normal(poem['author']):raise ValueError('source_identity_mismatch')
                if compact(translation) not in {compact(x) for x in candidates}:raise ValueError('source_translation_mismatch')
            except Exception as exc:error(type(exc).__name__+': '+str(exc))
    for value,ids in seen.items():
        if len(ids)>1:flags.append(dict(ids=ids,reason='duplicate_translation_across_works'))
    for ch,entry in dictionary['chars'].items():
        reasons=[]
        if len(ch)!=1:reasons.append('invalid_character_key')
        for field in ('pinyin','meanings','ancient'):
            if not isinstance(entry.get(field),list) or any(not isinstance(x,str) or not x.strip() for x in entry.get(field,[])):reasons.append('invalid_'+field)
        if not entry.get('pinyin') or any(not valid_pinyin(p) for p in entry.get('pinyin',[])):reasons.append('invalid_pinyin')
        if not (entry.get('meanings') or entry.get('ancient')):reasons.append('missing_definition')
        if any(s in ' '.join(entry.get('meanings',[])+entry.get('ancient',[])) for s in ('待补释义','暂无释义','待完善释义')):reasons.append('placeholder_definition')
        errors.extend(dict(character=ch,reason=r) for r in reasons)
    for word,meaning in dictionary['words'].items():
        if len(word)!=2 or not isinstance(meaning,str) or not meaning.strip():errors.append(dict(word=word,reason='invalid_word_definition'))
    all_chars=set().union(*(hanzi(p['content']) for p in items))
    translated_chars=set().union(*(hanzi(p['content']) for p in available))
    report=dict(auditVersion='1.0.0',dataVersion=doc['dataVersion'],dictionaryVersion=dictionary['dataVersion'],
        selected=len(items),availableTranslations=len(available),missingTranslations=len(items)-len(available),
        sourceImportsReplayed=len(doc.get('translationImports',{})),sourceFilesHashed=len(hashes),notesChecked=notes_checked,
        dictionaryCharacters=len(dictionary['chars']),dictionaryWords=len(dictionary['words']),
        pinyinFormats='Tone marks and numbered tones both accepted; no context/pronunciation correctness claim.',
        missingDictionarySelected=sorted(all_chars-set(dictionary['chars'])),
        missingDictionaryTranslated=sorted(translated_chars-set(dictionary['chars'])),
        errors=errors,reviewFlags=flags,
        scope='All available text/definitions checked structurally; imported source identity, hashes and translation replayed. Not a full literary/lexicographic review.')
    return report


if __name__=='__main__':
    sys.stdout.reconfigure(encoding='utf-8');r=audit()
    path=ROOT/'expansion/release-audits'/('content-data-v'+r['dataVersion']+'-dict-v'+r['dictionaryVersion']+'-v1.0.0.json');write_once(path,r)
    print(json.dumps(dict(report=str(path),**{k:v for k,v in r.items() if k not in ('errors','reviewFlags','missingDictionarySelected','missingDictionaryTranslated')},
        errorCount=len(r['errors']),reviewFlagCount=len(r['reviewFlags']),
        missingDictionarySelectedCount=len(r['missingDictionarySelected']),missingDictionaryTranslatedCount=len(r['missingDictionaryTranslated'])),ensure_ascii=False,indent=2))
    print(json.dumps(dict(errors=r['errors'][:15],flags=r['reviewFlags'][:15]),ensure_ascii=False))
    if r['errors']:raise SystemExit(1)
