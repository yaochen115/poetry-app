"""Save and report only exact pending corpus matches for parser diagnostics."""
import sys,json
from collections import defaultdict
from import_hf_translations_v1_0_0 import READER,OUT,FILES,split_translation
from enrichment_pipeline import ROOT,Pipeline,read,write_once,digest
from translation_overlay_v1_0_0 import overlay_for
from convert_downloaded_materials_v1_0_0 import normal,text


def main():
    sys.stdout.reconfigure(encoding='utf-8');sys.path.insert(0,str(READER));import duckdb
    pipe=Pipeline();doc=read(ROOT/'data/poems.json');lookup=defaultdict(list)
    for pid,p in pipe.pending.items():
        if not overlay_for(doc,p):lookup[(normal(p['content']),normal(p['author']))].append(pid)
    connection=duckdb.connect(':memory:',config={'threads':2,'temp_directory':str(OUT/'temp')})
    rows=connection.execute('SELECT tb_gushiwen,tb_fanyis FROM read_parquet(?) WHERE len(tb_fanyis.fanyis)>0 OR len(coalesce(tb_gushiwen.yizhu,\'\'))>0',[[str(OUT/name) for name,_ in FILES]]).fetchall()
    report=[]
    for work,translations in rows:
        ids=lookup.get((normal(work.get('cont')),normal(work.get('author'))),[])
        if len(ids)!=1:continue
        raw=dict(tb_gushiwen=work,tb_fanyis=translations);path=OUT/'pending-rows'/(ids[0]+'--'+digest(raw)+'.json');write_once(path,raw)
        options=[(r.get('cont',''),r.get('nameStr','')) for r in (translations or {}).get('fanyis',[]) or []]
        if work.get('yizhu'):options.append((work['yizhu'],'译文及注释'))
        report.append(dict(id=ids[0],file=path.relative_to(ROOT).as_posix(),sections=[dict(label=label,characters=len(text(html)),prefix=text(html)[:70],parsed=bool(split_translation(html,label)[0])) for html,label in options]))
    write_once(ROOT/'expansion/hf-pending-format-report-v1.0.0.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
