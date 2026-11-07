"""Finite reviewed additions for frequent missing characters; no poem completion.

Prioritization uses selected-text occurrence counts. Existing dictionary entries
are immutable, and the complete previous dictionary is checkpointed.
"""
import json,sys,subprocess
from pathlib import Path
from collections import Counter
from enrichment_pipeline import Pipeline,read,write_once,digest,normalize_definition
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'expansion/python-packages'))
from pypinyin import pinyin,Style

DEFS={
 '井':('为取地下水而凿的深洞；井宿。','贾傅井联系贾谊旧宅的水井；露井指没有覆盖物的井。'),
 '旋':('回转，读xuán；随即、不久；转动也有xuàn音。','酒旋沽写酒刚刚买来；回旋写旋转回环，须结合词语区别读音。'),
 '惯':('习惯、习以为常。','惯常、习惯，表示某种情形经常经历而熟悉。'),
 '皮':('人或动物体表的组织；物体表层。','射不主皮的皮是箭靶上的兽皮，联系射礼不以贯穿靶皮为主要标准。'),
 '猜':('猜测；疑忌。','嫌猜指嫌疑猜忌，两小无嫌猜写童年相处毫无猜忌。'),
 '呵':('呵斥；呼气；语气词。','呵手指向手上呼气取暖，读hē；曲中句末呵常相当于啊，不把语气词解成呵斥。'),
 '筝':('弹拨弦乐器，读zhēng。','哀筝指声调哀怨的筝声。'),
 '债':('欠下的钱财或应偿还的事物，读zhài。','酒债指赊欠的酒钱。'),
 '缄':('封闭；封口；书信，读jiān。','开缄指拆开书信，缄口指闭口不言。'),
 '活':('生存；使有生机；灵动。','成活指植物栽种后存活，不把它解作灵活。'),
 '累':('积聚、连续，读lěi；牵连、劳倦，常读lèi；累累还有léi音。','累十觞写接连饮下多杯酒；簪组累写官职的拘束牵累，须随词辨音义。'),
 '萝':('松萝、藤萝等攀缘植物。','青萝写青绿的藤蔓；牵萝补屋写牵引藤萝修补茅屋。'),
 '朦':('朦胧指模糊不清、隐约的样子，读méng。','用于朦胧等词，写月色、景物或感受不清晰。'),
 '麟':('麒麟，传说中的瑞兽，读lín。','卧麒麟可写陵墓前倒卧的石麒麟，联系凭吊旧迹的语境。'),
 '酬':('以酒相劝；报答；应答。','诗题中酬常指以诗作答，酬佳节则写以饮酒等方式度过节日。'),
 '季':('一年中的一季；排行最小；姓氏用字。','四季指春夏秋冬；季氏为鲁国卿大夫家族名，不据单字解释其人物。'),
 '沟':('水道、沟渠。','沟陇联系田野中的沟渠与田垄。'),
 '砧':('捣衣、切物或锻打时垫在下面的石块、木板等，读zhēn。','古诗词中的砧声常指捣衣声，不能一概解为砍切声。'),
 '救':('救助；制止、纠正。','女弗能救与中的救是阻止、纠正季氏的越礼行为，不只是救人性命。'),
 '慰':('安慰、宽解。','自慰指自我宽慰。'),
}

def main():
    sys.stdout.reconfigure(encoding='utf-8');p=Pipeline()
    path=ROOT/'data/dict.json';old=path.read_bytes();document=read(path)
    additions={}
    for ch,(a,b) in DEFS.items():
        if ch in document['chars']:continue
        entry=normalize_definition(dict(meanings=[a],ancient=[b]))
        additions[ch]=dict(pinyin=sorted({x for g in pinyin(ch,heteronym=True,style=Style.TONE3) for x in g}),**entry)
    if not additions:print('Already present; no change.');return
    checkpoint=ROOT/'expansion/checkpoints/pre-dictionary-priority-v1.0.0'
    checkpoint.mkdir(parents=True,exist_ok=True)
    with (checkpoint/'dict.json').open('xb') as f:f.write(old)
    version=list(map(int,document['dataVersion'].split('.')));version[-1]+=1
    document['dataVersion']='.'.join(map(str,version))
    report=dict(version='1.0.0',dictionaryVersion=document['dataVersion'],newCharacters=additions,
        reviewer='Codex common-character and selected-context review 2026-11-04',
        policy='只新增词典，不将原文条目标为完成；按正文语境核对候选常用古义，多音分别说明。',
        contextIds={ch:[pid for pid,q in p.pending.items() if ch in q['content']] for ch in additions})
    write_once(ROOT/'expansion/dictionary/priority-v1.0.0.json',report)
    document['chars'].update(additions)
    encoded=(json.dumps(document,ensure_ascii=False,indent=2)+'\n').encode('utf-8')
    assets=ROOT/'app/assets/data/dict.json';previous_assets=assets.read_bytes()
    try:
        path.write_bytes(encoded);assets.write_bytes(encoded)
        subprocess.run([sys.executable,str(ROOT/'scripts/audit_expansion.py')],check=True)
        subprocess.run([sys.executable,str(ROOT/'scripts/validate_data.py'),'--original-only'],check=True)
    except BaseException:
        path.write_bytes(old);assets.write_bytes(previous_assets);raise
    print('Added',len(additions),'frequent missing dictionary characters; poem statuses unchanged.')

if __name__=='__main__':main()
