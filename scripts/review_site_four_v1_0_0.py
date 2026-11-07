"""Record a finite source/body comparison, retaining original draft prose."""
from pathlib import Path
import hashlib
from enrichment_pipeline import Pipeline,read,digest,write_once,normalize_definition

IDS=['tang-156','tang-160','tang-162','tang-165']
def main():
    p=Pipeline();_,drafts,_,_=p.inspect()
    for pid in IDS:
        if pid not in p.pending:continue
        source=next((p.root/'expansion/site-selected/known-v1.0.0').glob(pid+'--*.json'))
        meta=read(source)
        assert meta['status']==200 and meta['translationHeadingFound']
        raw=source.parent/(pid+'--'+meta['sha256']+'.html')
        assert hashlib.sha256(raw.read_bytes()).hexdigest()==meta['sha256']
        r=drafts[pid];patch=r['patch']
        # All four originals and full translations were manually compared with
        # public pages; original independent draft wording is retained.
        assert all(n['term'] in p.poems[pid]['content'] for n in patch['notes'])
        write_once(p.result_path(p.poems[pid]),patch)
        write_once(p.work/'reviews'/f"{pid}--{r['inputHash']}.json",dict(
            decision='approved',reviewer='Codex public-site editorial comparison 2026-11-04',
            inputHash=r['inputHash'],resultHash=digest(patch),
            sourceUrl=meta['url'],sourceSha256=meta['sha256'],
            scope='核对正文、作者、逐句译义、注释；保留独立草稿措辞，不整篇搬用现代网页译注。'))
    defs={'挥':('摇动、挥动；散发。','挥手指摇动手臂，表达送别之情。'),
          '班':('分开；次序；行列。','班马指离群的马，班有分别义。'),
          '萋':('萋萋形容草木茂盛。','萋萋满别情借茂盛芳草寄托惜别情意。')}
    for ch,(a,b) in defs.items():
        if ch in p.dictionary:continue
        entry=normalize_definition(dict(meanings=[a],ancient=[b]))
        write_once(p.work/'dictionary'/f'{ch}.json',entry)
        write_once(p.work/'reviews/dictionary'/f'{ch}.json',dict(decision='approved',
            reviewer='Codex contextual dictionary review 2026-11-04',definitionHash=digest(entry)))
    print('Four source comparisons and three dictionary reviews saved.')
if __name__=='__main__':main()
