"""Select references first, bind quality-checked provider originals second; no production mutation."""
import csv,hashlib,json,re,sys
from collections import Counter,defaultdict
from difflib import SequenceMatcher
from enrichment_pipeline import ROOT,read,write_once,digest
from convert_downloaded_materials_v1_0_0 import records,normal,text
from select_poetry_2000_v1_0_0 import BASE,provider_rows,norm

PRIMARY={'唐诗三百首','宋词三百首','古诗三百首','宋词精选','千家诗','小学古诗','初中古诗','高中古诗','早教古诗100首'}
TUNES=set('浣溪沙 山花子 摊破浣溪沙 菩萨蛮 虞美人 浪淘沙令 浪淘沙慢 清平乐 更漏子 望江南 忆江南 梦江南 忆秦娥 忆少年 忆王孙 长相思 如梦令 生查子 卜算子 卜算子慢 点绛唇 浣溪沙慢 蝶恋花 鹊踏枝 鹊桥仙 采桑子 丑奴儿 临江仙 临江仙慢 定风波 苏幕遮 渔家傲 渔父 渔歌子 江城子 江神子 一剪梅 踏莎行 木兰花 玉楼春 减字木兰花 木兰花令 木兰花慢 南乡子 南歌子 破阵子 相见欢 乌夜啼 长命女 谒金门 醉花间 望海潮 凤栖梧 八声甘州 雨霖铃 桂枝香 水调歌头 水龙吟 念奴娇 酹江月 沁园春 满江红 满庭芳 满朝欢 行香子 洞仙歌 好事近 好事近慢 一丛花 少年游 迷神引 望远行 蓦山溪 风流子 醉翁操 西江月 虞美人影 柳梢青 柳初新 御街行 青门引 青玉案 千秋岁 千秋岁引 六州歌头 望湘人 醉落魄 醉太平 醉蓬莱 鹧鸪天 瑞鹤仙 瑞龙吟 兰陵王 六丑 夜游宫 夜飞鹊 解语花 解连环 过秦楼 绕佛阁 大酺 天香 齐天乐 疏影 暗香 扬州慢 淡黄柳 长亭怨慢 杏花天 念奴娇序 八归 霓裳中序第一 扬州慢 诉衷情 诉衷情令 画堂春 庆清朝 武陵春 声声慢 永遇乐 凤凰台上忆吹箫 醉花阴 孤雁儿 钗头凤 金缕曲 贺新郎 贺新凉 丑奴儿近 摸鱼儿 摸鱼子 祝英台近 汉宫春 最高楼 粉蝶儿 霜天晓角 风入松 双双燕 海棠春 唐多令 唐多令慢 绮罗香 三姝媚 金明池 祝英台近 解佩令 渡江云 高阳台 天香 忆旧游 庆春宫 宴清都 莺啼序 玉漏迟 减字浣溪沙 一萼红 三台 太常引 贺圣朝 桂殿秋 秋蕊香 锦缠道 锦堂春 风入松 小重山 水仙子 洞庭春色 踏莎行慢 琵琶仙 朝中措 临江仙引 步蟾宫 浦南村 行路难 春光好 酒泉子 应天长 思帝乡 遐方怨 何满子 破阵乐 捣练子 思远人 离亭燕 望江东 七娘子 沙塞子 感皇恩'.split())

def clean_body(s):
 # Only explicit editorial variants, not arbitrary parenthesized verse/prefaces.
 return re.sub(r'[（(][^（）()\n]*(?:一作|又作|通：|通:)[^（）()\n]*[）)]','',text(s)).strip()

def genre_for(title,content,labels):
 name=norm(title.split('·')[0].split(' ')[0]);body=clean_body(content)
 if any(x in ''.join(labels) for x in ('文言文','古文观止')):return None
 if any(x in title for x in ('卜居','渔父','滕王阁序','论语','孟子','大学','中庸')):return None
 if name in {norm(x) for x in TUNES}:return '词'
 if labels & {'宋词三百首','宋词精选'}:
  clauses=[norm(x) for x in re.split('[，。！？；]',body) if norm(x)]
  if len(clauses)==4 and len({len(x) for x in clauses})==1 and len(clauses[0]) in (5,7):return '诗'
  return '词'
 if name in {'浪淘沙','杨柳枝','竹枝词','采莲曲'}:return '诗'
 if re.search(r'(?:赋|铭|说|记|论|序|表|书)$',title) and not labels&{'唐诗三百首','古诗三百首','千家诗'}:return None
 clauses=[norm(x) for x in re.split('[，。！？；]',body) if norm(x)]
 if labels & {'唐诗三百首','古诗三百首','千家诗','诗经','乐府','楚辞','小学古诗','初中古诗','高中古诗','早教古诗100首'}:return '诗'
 if len(clauses)>=4 and len({len(x) for x in clauses})==1 and len(clauses[0]) in (5,7):return '诗'
 return None

def main():
 sys.stdout.reconfigure(encoding='utf-8');anchor=read(BASE/'classic-anchor-review-v1.0.0.json');pool=[]
 for path in sorted((ROOT/'expansion/sources/chinese-gushiwen/guwen').glob('*.json')):
  for i,r in enumerate(records(path)):
   labs=r.get('type',[]);labs=set([labs] if isinstance(labs,str) else labs)
   pool.append(dict(title=r.get('title',''),author=r.get('writer',''),dynasty=r.get('dynasty',''),body=clean_body(r.get('content','')),
                    labels=labs,reference=dict(path=path.relative_to(ROOT).as_posix(),row=i)))
 for filename,label in [('全唐诗--唐诗三百首.json','唐诗三百首'),('宋词--宋词三百首.json','宋词三百首')]:
  path=BASE/'evidence'/filename
  for i,r in enumerate(read(path)):
   pool.append(dict(title=r.get('title',r.get('rhythmic','')),author=r['author'],dynasty='唐' if label.startswith('唐') else '宋',
                    body=clean_body(r['paragraphs']),labels={label},reference=dict(path=path.relative_to(ROOT).as_posix(),row=i)))
 # Explicit anchor row identity overrides broad same-title/short-incipit retrieval.
 locators=defaultdict(list)
 for genre,key in [('诗','poems'),('词','ci')]:
  for a in anchor[key]:
   for loc in a.get('localEvidence',[]):
    source=anchor['sources']['local'][loc['source']]['path'];locators[(source,loc['row'])].append((genre,a))
 # A blank-line-separated member is selected independently, not the parent collection.
 members=[]
 for p in pool:
  key=(p['reference']['path'],p['reference']['row'])
  if not re.search(r'[二三四五六七八九十百]+首',p['title']):continue
  for genre,a in locators.get(key,[]):
   blocks=[b for b in re.split(r'\n\s*\n',p['body']) if norm(a['incipit']) in norm(b)[:160]]
   if len(blocks)==1:
    members.append(dict(p,title=a['title'],body=blocks[0],explicitAnchor=(genre,a),
                        reference=dict(p['reference'],parentTitle=p['title'],memberIncipit=a['incipit'])))
 pool.extend(members)
 # Locate remaining anchor references in the existing 50k corpus; no translations read/imported.
 extra=ROOT/'expansion/sources/poems-db-translations-v1.0.0/poems1.jsonl'
 missing=[(g,a) for g,k in [('诗','poems'),('词','ci')] for a in anchor[k]
          if not any(norm(p['author'])==norm(a['author']) and norm(a['incipit']) in norm(p['body'])[:160] for p in pool)]
 for i,line in enumerate(extra.open(encoding='utf-8-sig')):
  r=json.loads(line);body=clean_body(r.get('content',[]))
  for genre,a in missing:
   if norm(r.get('author',''))==norm(a['author']) and norm(a['incipit']) in norm(body)[:160]:
    pool.append(dict(title=a['title'],author=a['author'],dynasty=a['era'],body=body,labels=set(r.get('tags',[])),
                     explicitAnchor=(genre,a),reference=dict(path=extra.relative_to(ROOT).as_posix(),row=i)))
 grouped={};rejected=[]
 for p in pool:
  body=norm(p['body']);ak=norm(p['author']);title=p['title']
  if not body or len(body)<10 or not ak:continue
  # Whole unsplit collections cannot occupy a separate slot alongside their members.
  if re.search(r'[二三四五六七八九十百]+首',title) and not re.search(r'其[一二三四五六七八九十百]+|[· ](?:一|二|三|四|五|六|七|八|九|十)$',title):
   rejected.append(dict(title=title,author=p['author'],reason='unsplit_group',reference=p['reference']));continue
  if any(x in p['dynasty'] for x in ('近现代','近代','现代','当代')):continue
  loc=(p['reference']['path'],p['reference']['row']);found=locators.get(loc,[])
  ah=p.get('explicitAnchor') or (found[0] if len(found)==1 else None)
  genre=ah[0] if ah else genre_for(title,p['body'],p['labels'])
  if not genre:continue
  identity=body # Global same-text identity, even if attribution differs.
  score=100000*bool(ah)+1000*bool(p['labels']&{'唐诗三百首','宋词三百首'})+800*bool(p['labels']&{'小学古诗','初中古诗','高中古诗','早教古诗100首'})+600*bool(p['labels']&{'古诗三百首','宋词精选','千家诗'})+min(15,len(p['labels']))*4
  entry=grouped.get(identity)
  if entry is None:
   entry=dict(id=('poem' if genre=='诗' else 'ci')+'-'+digest(dict(author=ak,body=body))[:16],genre=genre,title=title,author=p['author'],dynasty=p['dynasty'],
              matchingText=p['body'],canonicalFingerprint=body,selectionLabels=set(),selectionEvidence=[],anchorKeys=[],rankScore=score,attributionAlternatives=[])
   grouped[identity]=entry
  if ah:
   entry.update(genre=genre,title=ah[1]['title'],author=ah[1]['author'],dynasty=ah[1]['era'])
   entry['anchorKeys']=sorted(set(entry['anchorKeys']+[ah[1]['key']]))
  elif norm(entry['author'])!=ak:entry['attributionAlternatives'].append(dict(author=p['author'],title=title,reference=p['reference']))
  entry['selectionLabels'].update(p['labels']);entry['rankScore']=max(score,entry['rankScore'])
  entry['selectionEvidence'].append(dict(**p['reference'],title=title,labels=sorted(p['labels'])))
 # Anchors without a locator are resolved by author+distinctive complete reference body.
 missing_anchor=[]
 for key,genre in [('poems','诗'),('ci','词')]:
  for a in anchor[key]:
   if any(a['key'] in p['anchorKeys'] for p in grouped.values()):continue
   matches=[p for p in grouped.values() if norm(p['author'])==norm(a['author']) and norm(a['incipit']) in p['canonicalFingerprint'][:160]]
   matches.sort(key=lambda p:(-SequenceMatcher(None,norm(p['title']),norm(a['title'])).ratio(),-len(p['canonicalFingerprint'])))
   if matches:
    p=matches[0];p['anchorKeys'].append(a['key']);p['rankScore']+=100000;p['genre']=genre;p['title']=a['title']
   else:
    # A classic remains selected even when the named provider does not contain its original.
    marker='anchor-'+a['key'];grouped[marker]=dict(id=('poem' if genre=='诗' else 'ci')+'-anchor-'+a['key'],genre=genre,title=a['title'],author=a['author'],dynasty=a['era'],
       matchingText='',canonicalFingerprint='',selectionLabels=set(),selectionEvidence=[dict(path='expansion/poetry-2000-v1.0.0/classic-anchor-review-v1.0.0.json',anchorKey=a['key'],basis=a['basis'])],
       anchorKeys=[a['key']],rankScore=100000,attributionAlternatives=[],referenceOriginalMissing=True)
    missing_anchor.append(a)
 # Bind provider records only after selection criteria are fixed.
 originals=defaultdict(list);by_title=defaultdict(list)
 for row,path in provider_rows():
  content=text(row['content']);b=norm(content);a=norm(row['author']['name']);t=norm(row['title'])
  if any(x in content for x in ['记忆体','海内存','�']):continue
  record=(row,path,content,b);originals[b].append(record);by_title[a].append(record)
 selected=[];summary={}
 for genre in ('诗','词'):
  items=[];authors=Counter()
  ranked=sorted((p for p in grouped.values() if p['genre']==genre),key=lambda p:(-p['rankScore'],-len(p['selectionEvidence']),p['id']))
  for p in ranked:
   if len(items)>=1000:break
   if authors[p['author']]>=35 and not p['anchorKeys'] and not p['selectionLabels']&{'唐诗三百首','宋词三百首'}:continue
   items.append(p);authors[p['author']]+=1
  if len(items)<1000:raise ValueError('Insufficient reference-backed '+genre+' works: '+str(len(items)))
  for p in items:
   p['selectionLabels']=sorted(p['selectionLabels']);p['requiresPopularityReview']=not bool(p['anchorKeys'] or set(p['selectionLabels'])&PRIMARY)
   p['content']='';p['translation']='';p['notes']=[];p['originalStatus']='provider_original_missing';p['originalSource']=None
   hits=[x for x in originals[p['canonicalFingerprint']] if norm(x[0]['author']['name'])==norm(p['author'])]
   if not hits and p['canonicalFingerprint']:
    for record in by_title[norm(p['author'])]:
     row,path,content,b=record
     if not .93<=len(b)/len(p['canonicalFingerprint'])<=1.08:continue
     # The title is an extra check when allowing a full-length textual variant.
     rt=norm(row['title']);pt=norm(p['title'].split('·')[0])
     if not (pt in rt or rt in pt):continue
     ratio=SequenceMatcher(None,p['canonicalFingerprint'],b,autojunk=False).ratio()
     if ratio>=.9:hits.append(record)
   if hits:
    hits.sort(key=lambda x:(x[3]!=p['canonicalFingerprint'],-SequenceMatcher(None,x[3],p['canonicalFingerprint'],autojunk=False).ratio(),x[0]['id']))
    r,path,content,b=hits[0];p['content']=content;p['originalStatus']='provider_exact_normalized' if b==p['canonicalFingerprint'] else 'provider_full_length_variant_pending_review'
    p['originalSource']=dict(provider='https://poetry.palemoky.com',providerId=r['id'],providerTitle=r['title'],providerAuthor=r['author'],providerDynasty=r.get('dynasty'),providerType=r.get('type'),
                             cacheFile=path.relative_to(ROOT).as_posix(),sha256=hashlib.sha256(path.read_bytes()).hexdigest())
   p['editorialStatus']='selection_reference_backed_not_literary_approval'
  selected.extend(items);summary[genre]=dict(count=len(items),authors=len(authors),originals=sum(bool(x['content']) for x in items),
      weakPopularityEvidence=sum(x['requiresPopularityReview'] for x in items),eras=dict(Counter(x['dynasty'] for x in items)))
 covered={k for p in selected for k in p['anchorKeys']}
 report=dict(schemaVersion='1.0.2',status='selected_2000_provider_acquisition_in_progress',target={'诗':1000,'词':1000},summary=summary,
             policy='先按具体作品的教材/选本/本地语料交叉选择，经典锚点必收；仅语料收录不是热度证明，扩展项标注待知名度复核。正式正文只填诗泉已获取且全篇身份匹配的文本，不以参考文本冒充诗泉原文；缺项保留。',
             anchorsTotal=len(anchor['poems'])+len(anchor['ci']),anchorsCovered=len(covered),unlocatedAnchors=missing_anchor,
             productionChanged=False,apkBuilt=False,rejectedReferenceGroups=rejected,items=selected)
 dest=BASE/'catalog-v1.0.2.json';write_once(dest,report)
 with (BASE/'catalog-v1.0.2.csv').open('x',encoding='utf-8-sig',newline='') as f:
  w=csv.writer(f);w.writerow(['id','体裁','题名','作者','朝代','经典锚点','依据标签','诗泉原文状态'])
  for p in selected:w.writerow([p['id'],p['genre'],p['title'],p['author'],p['dynasty'],';'.join(p['anchorKeys']),';'.join(p['selectionLabels']),p['originalStatus']])
 print(json.dumps(dict(summary=summary,anchorsCovered=len(covered),unlocatedAnchors=missing_anchor,path=str(dest)),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
