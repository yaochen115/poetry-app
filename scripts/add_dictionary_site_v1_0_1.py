"""Eight site-assisted factual definitions, reviewed against selected contexts.

Only adds missing characters. Does not copy examples, pronunciation errors,
unverified variant forms or unrelated senses from the supplied source pages.
"""
import json,sys,subprocess,hashlib
from pathlib import Path
from enrichment_pipeline import Pipeline,read,write_once
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'expansion/python-packages'))
from pypinyin import pinyin,Style
DEFS={
 '堕':('落下、坠落，通常读duò；另有通隳的huī音。','诗词中常写物体下落；通隳时与毁坏义有关，须随语境区别。'),
 '窝':('鸟兽的巢穴；比喻居住、安身之所。','安乐窝指安适的住处。'),
 '熏':('烟气熏染；温暖和煦。','熏炉联系焚香取暖的炉具；熏风指和暖的风，读xūn。'),
 '冉':('姓氏；冉冉表示缓慢或柔软下垂。','冉有是孔子弟子冉求的字；冉冉另表示渐进，不按姓氏解释。'),
 '严':('严格；严肃、庄严；严厉、程度深。','严寒指酷寒，庄严指严肃端正，须结合所修饰之词。'),
 '闷':('烦闷、不畅快，常读mèn；空气不流通、闭气，常读mēn。','解闷指排解愁闷，读mèn，不沿用来源页把所有义项都标为mèn的做法。'),
 '颍':('颍水，水名，流经河南、安徽，读yǐng。','箕颍联系箕山、颍水及许由隐居传说，借指隐逸。'),
 '配':('相称、匹配；婚配；分派、调配。','婚配指结为夫妇，分配指分派，不把现代词语的不同语境混为一义。'),
}

def main():
    sys.stdout.reconfigure(encoding='utf-8');pipe=Pipeline();path=ROOT/'data/dict.json'
    old=path.read_bytes();document=read(path);added={};proof={}
    for ch,(meaning,ancient) in DEFS.items():
        if ch in document['chars']:continue
        source=next((ROOT/'expansion/site-dictionary/priority-v1.0.0').glob(f'char-{ord(ch)}--*.json'))
        meta=read(source);assert meta.get('status')==200 and '/user/login' not in meta.get('finalUrl','')
        body=source.parent/f"char-{ord(ch)}--{meta['sha256']}.html"
        assert hashlib.sha256(body.read_bytes()).hexdigest()==meta['sha256']
        added[ch]=dict(pinyin=sorted({x for g in pinyin(ch,heteronym=True,style=Style.TONE3) for x in g}),
                       meanings=[meaning],ancient=[ancient])
        proof[ch]=dict(url=meta['url'],sha256=meta['sha256'],acquiredAt=meta['acquiredAt'],
            review='核对正文所需常用义，独立编写简明释义，不复制例句或未核定异体字。',
            contexts=[pid for pid,p in pipe.pending.items() if ch in p['content']])
    if not added:print('Already applied.');return
    checkpoint=ROOT/'expansion/checkpoints/pre-dictionary-site-v1.0.1'
    checkpoint.mkdir(parents=True,exist_ok=True)
    with (checkpoint/'dict.json').open('xb') as f:f.write(old)
    document['chars'].update(added);document.setdefault('charProvenance',{}).update(proof)
    version=list(map(int,document['dataVersion'].split('.')));version[-1]+=1
    document['dataVersion']='.'.join(map(str,version))
    write_once(ROOT/'expansion/dictionary/site-v1.0.1.json',dict(version='1.0.1',
        dictionaryVersion=document['dataVersion'],additions=added,provenance=proof,
        ignoredSourceClaims=['闷页不通气义也标mèn，未照搬。','颍页异体字泂未作版本核定，未收录。'],
        poemStatusChanged=False))
    encoded=(json.dumps(document,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    assets=ROOT/'app/assets/data/dict.json';old_assets=assets.read_bytes()
    try:
        path.write_bytes(encoded);assets.write_bytes(encoded)
        subprocess.run([sys.executable,str(ROOT/'scripts/audit_expansion.py')],check=True)
        subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py'),'--original-only'],check=True)
    except BaseException:
        path.write_bytes(old);assets.write_bytes(old_assets);raise
    print('Added',len(added),'site-assisted character definitions; poem completion unchanged.')

if __name__=='__main__':main()
