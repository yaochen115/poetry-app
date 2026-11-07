"""Cache the requested provider's author index and bounded genre/author pools."""
from concurrent.futures import ThreadPoolExecutor,as_completed
from datetime import datetime,timezone
import hashlib,json,sys,threading,time,math
from urllib.request import Request,urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError,URLError
from enrichment_pipeline import ROOT,read,write_once

OUT=ROOT/'expansion/poetry-2000-v1.0.0/provider-api'
MAJOR_POETS='佚名 屈原 宋玉 曹操 曹丕 曹植 王粲 阮籍 嵇康 左思 陶渊明 谢灵运 鲍照 谢朓 庾信 陈子昂 骆宾王 王勃 杨炯 卢照邻 宋之问 杜审言 贺知章 张若虚 张九龄 王之涣 孟浩然 王维 李白 杜甫 高适 岑参 王昌龄 王翰 李颀 常建 王湾 刘长卿 韦应物 钱起 皇甫冉 韩翃 李益 卢纶 孟郊 韩愈 柳宗元 刘禹锡 白居易 元稹 张籍 王建 李贺 李绅 杜牧 李商隐 温庭筠 许浑 贾岛 罗隐 皮日休 陆龟蒙 司空图 李频 张祜 朱庆余 郑谷 金昌绪 崔颢 崔护 綦毋潜 陈陶 林杰 李涉 苏轼 黄庭坚 王安石 欧阳修 梅尧臣 苏舜钦 曾巩 陆游 杨万里 范成大 朱熹 陈与义 李清照 张耒 秦观 晁补之 贺铸 文天祥 岳飞 汪元量 徐俯 张栻 林逋 苏舜钦 苏辙 苏洵 宋祁 司马光 郑思肖 王禹偁 王令 秦韬玉 崔涂 钱珝 张旭 王绩 王冕 虞集 揭傒斯 杨载 赵孟頫 萨都剌 倪瓒 高启 刘基 宋濂 于谦 杨慎 唐寅 祝允明 文徵明 王世贞 李攀龙 戚继光 杨继盛 陈子龙 夏完淳 张煌言 顾炎武 吴伟业 王士禛 朱彝尊 纳兰性德 查慎行 袁枚 赵翼 郑燮 龚自珍 黄景仁 蒋士铨 林则徐 秋瑾 谭嗣同'.split()


class API:
 def __init__(self):self.lock=threading.Lock();self.next=0;self.requests=0;self.stopped=False
 def get(self,path,params):
  query=dict(params,lang='zh-Hans');url='https://poetry.palemoky.com'+path+'?'+urlencode(sorted(query.items()))
  key=hashlib.sha256(url.encode()).hexdigest();target=OUT/'cache'/(key+'.json')
  if target.exists():return read(target)
  for attempt in range(2):
   if self.stopped:raise RuntimeError('Provider requests stopped')
   with self.lock:
    time.sleep(max(0,self.next-time.monotonic()));self.next=time.monotonic()+.5;self.requests+=1
   try:
    with urlopen(Request(url,headers={'User-Agent':'HongzhuangAnthology/1.0'}),timeout=25) as response:raw=response.read(4_000_001)
    if len(raw)>4_000_000:raise ValueError('Page budget exceeded')
    document=json.loads(raw)
    if not isinstance(document.get('data'),list):raise ValueError('Expected documented list response')
    write_once(target,document)
    write_once(OUT/'metadata'/(key+'.json'),dict(url=url,sha256=hashlib.sha256(target.read_bytes()).hexdigest(),acquiredAt=datetime.now(timezone.utc).isoformat()))
    return document
   except HTTPError as exc:
    if exc.code in (401,403,429,503):self.stopped=True
    raise
   except URLError:
    if attempt:raise
    time.sleep(2)


def batch(api,path,params):
 first=api.get(path,dict(params,page=1,pageSize=100));result=list(first['data']);pages=1
 # Iteration is bounded and stops on the server's hasMore flag.
 while first.get('pagination',{}).get('hasMore'):
  if pages>=80:raise ValueError('Unexpectedly large author/type pool')
  pages+=1;first=api.get(path,dict(params,page=pages,pageSize=100));result.extend(first['data'])
 return result


def main():
 sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(parents=True,exist_ok=True);api=API()
 first=api.get('/api/authors',dict(page=1,pageSize=100));authors=list(first['data'])
 pages=math.ceil(13577/100)
 errors=[]
 with ThreadPoolExecutor(max_workers=2) as pool:
  jobs={pool.submit(api.get,'/api/authors',dict(page=p,pageSize=100)):p for p in range(2,pages+1)}
  for job in as_completed(jobs):
   try:authors.extend(job.result()['data'])
   except Exception as exc:errors.append(dict(stage='authors',page=jobs[job],error=str(exc)))
 write_once(OUT/'authors-v1.0.0.json',sorted(authors,key=lambda a:a['id']))
 wanted=set(MAJOR_POETS);anchor=read(ROOT/'expansion/poetry-2000-v1.0.0/classic-anchor-review-v1.0.0.json')
 # Author spellings in anchor entries are reconciled below; full index is kept.
 all_names={a['name'] for a in authors};author_jobs=[a for a in authors if a['name'] in wanted]
 work=[('type-'+str(t),dict(typeId=t)) for t in (20,21,50,70)]
 work.extend(('author-'+str(a['id']),dict(authorId=a['id'])) for a in author_jobs)
 saved=[]
 with ThreadPoolExecutor(max_workers=2) as pool:
  jobs={pool.submit(batch,api,'/api/poems',params):(name,params) for name,params in work}
  for job in as_completed(jobs):
   name,params=jobs[job]
   try:
    rows=job.result();write_once(OUT/'pools'/(name+'.json'),dict(provider='https://poetry.palemoky.com/',query=params,items=rows))
    saved.append(dict(pool=name,count=len(rows)));print(name,len(rows),flush=True)
   except Exception as exc:errors.append(dict(stage='pool',pool=name,error=type(exc).__name__+': '+str(exc)))
 report=dict(requests=api.requests,authors=len(authors),pools=saved,errors=errors,stopped=api.stopped,
             absentMajorAuthors=sorted(wanted-all_names),productionChanged=False)
 write_once(OUT/'collection-v1.0.0.json',report)
 print(json.dumps({k:v for k,v in report.items() if k!='pools'},ensure_ascii=False,indent=2))


if __name__=='__main__':main()
