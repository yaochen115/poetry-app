"""Index supplied local reference material, never import it as finished work.

Only exact normalized original-text matches are linked; annotations stored in a
field named translation are flagged rather than treated as completed translation.
"""
import hashlib
import json
from pathlib import Path
import re
import sys
from collections import Counter, defaultdict

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'expansion/python-packages'))
from opencc import OpenCC
from enrichment_pipeline import Pipeline,digest,write_once


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    cc=OpenCC('t2s')
    def normalize(text):
        return re.sub(r'[^\u3400-\u9fff〇]','',cc.convert(text))
    index=defaultdict(list)
    for path in sorted((ROOT/'expansion/sources/chinese-gushiwen').rglob('*.json')):
        text=path.read_text(encoding='utf-8')
        try:rows=json.loads(text)
        except json.JSONDecodeError:rows=[json.loads(line) for line in text.splitlines() if line.strip()]
        if not isinstance(rows,list):continue
        source_hash=hashlib.sha256(path.read_bytes()).hexdigest()
        for row_number,row in enumerate(rows):
            if not isinstance(row,dict) or not isinstance(row.get('content'),str):continue
            translation=row.get('translation','')
            if not isinstance(translation,str) or not translation.strip():continue
            flags=[]
            if re.match(r'^\s*(注释|注解|译注|词句注释)',translation):
                flags.append('translation_field_may_contain_annotations_only')
            index[normalize(row['content'])].append(dict(
                file=path.relative_to(ROOT).as_posix(),row=row_number,sourceSha256=source_hash,
                sourceTitle=row.get('title'),sourceAuthor=row.get('writer'),
                translationReference=translation,notesReference=row.get('remark',''),
                flags=flags,attribution='Supplied local source; editorial reference only, no automatic publication.'))
    pipe=Pipeline();counts=Counter();flagged=0;linked=0
    for pid in pipe.ordered(pipe.pending):
        poem=pipe.poems[pid];matches=index.get(normalize(poem['content']),[])
        if not matches:continue
        record=dict(id=pid,inputHash=pipe.input_hash(poem),normalizedTextMatch=True,
                    versionAndAuthorStillRequireReview=True,references=matches,
                    policy='参考包，不是正式译注、审核通过结果或授权声明；需核对作者、版本、译文覆盖并独立编写。')
        target=pipe.work/'references'/(pid+'--'+digest(record)+'.json')
        write_once(target,record)
        counts[poem['category']]+=1;linked+=1
        flagged+=any(m['flags'] for m in matches)
    print(json.dumps(dict(linkedPendingPoems=linked,byCategory=dict(counts),
                         packetsWithFlags=flagged,productionChanged=False),ensure_ascii=False,indent=2))


if __name__=='__main__':main()
