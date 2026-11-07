"""Bounded, serial site search using its public HTML form. Cache all attempts.

No authentication, CAPTCHA solving, hidden API or proxy rotation. Results are
source candidates, not literary approvals or evidence of redistribution rights.
"""
import argparse,hashlib,html,json,re,sys,time,urllib.request,urllib.parse
from datetime import datetime,timezone
from pathlib import Path
from fetch_site_samples_v1_0_0 import Text
from enrichment_pipeline import read,write_once,digest
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'expansion/site-selected/v1.0.0'

def get(url):
    key=hashlib.sha256(url.encode()).hexdigest();meta=OUT/'pages'/f'{key}.json';body=meta.with_suffix('.html')
    if meta.exists():
        m=read(meta)
        if '/user/login' in m.get('finalUrl',''):
            raise ValueError('Login required; cached search cannot be used')
        if m.get('error'):raise ValueError('Cached failure: '+m['error'])
        return body.read_text(encoding='utf-8'),m
    m=dict(url=url,at=datetime.now(timezone.utc).isoformat())
    time.sleep(2)
    try:
        req=urllib.request.Request(url,headers={'User-Agent':'Hongzhuang-Research/1.0 (public-page collection)'})
        with urllib.request.urlopen(req,timeout=25) as response:
            raw=response.read(2_000_001);m.update(status=response.status,finalUrl=response.url)
        if '/user/login' in m['finalUrl']:
            raise ValueError('Login required; stop this acquisition path')
        if len(raw)>2_000_000:raise ValueError('Page size limit')
        text=raw.decode('utf-8','replace')
        if '访问过于频繁' in text or '请输入验证码' in text:raise ValueError('Access challenge; stop requests')
        m.update(sha256=hashlib.sha256(raw).hexdigest(),bytes=len(raw))
        body.parent.mkdir(parents=True,exist_ok=True);body.write_bytes(raw)
        write_once(meta,m);return text,m
    except Exception as e:
        m['error']=str(e);write_once(meta,m);raise

def plain(s):
    parser=Text();parser.feed(s);return ''.join(parser.parts)

def main():
    sys.stdout.reconfigure(encoding='utf-8')
    ap=argparse.ArgumentParser();ap.add_argument('--limit',type=int,default=5);args=ap.parse_args()
    if not 1<=args.limit<=30:ap.error('Use bounded batches of 1..30')
    OUT.mkdir(parents=True,exist_ok=True)
    selection=read(ROOT/'expansion/selected-1000/selection-v1.0.1.json')
    poems={p['id']:p for p in read(ROOT/'data/poems.json')['items']}
    candidates=[poems[p['id']] for p in selection['items'] if not poems[p['id']].get('translation','').strip()]
    jobs=[p for p in candidates if not (OUT/'attempts'/f"{p['id']}.json").exists()][:args.limit]
    for p in jobs:
        result=dict(id=p['id'],title=p['title'],sourceInputHash=digest(p),
                    status='not_matched',reuseStatus='permission_not_established_reference_only')
        try:
            url='https://www.guwendao.net/search.aspx?value='+urllib.parse.quote(p['title'])
            text,meta=get(url);result['search']=meta
            links=list(dict.fromkeys(html.unescape(x) for x in re.findall(r'href=[\"\x27]([^\"\x27]*shiwenv_[0-9a-f]+\.aspx)[\"\x27]',text)))
            result['candidateLinks']=links[:3]
            for link in links[:3]:
                url=urllib.parse.urljoin('https://www.guwendao.net',link)
                if urllib.parse.urlparse(url).hostname!='www.guwendao.net':continue
                article,metadata=get(url)
                body=re.search(r'<div[^>]+class="contson"[^>]*>(.*?)</div>',article,re.S)
                norm=lambda s:re.sub(r'[^\u3400-\u9fff〇]','',s)
                if body and norm(plain(body[1]))==norm(p['content']) and p['author'] in plain(article):
                    result.update(status='body_and_author_matched_requires_editorial_review',article=metadata,
                                  translationHeadingFound='译文及注释' in article or '>译文<' in article)
                    break
        except Exception as exc:result.update(status='fetch_failed',error=str(exc))
        write_once(OUT/'attempts'/f"{p['id']}.json",result)
        print(json.dumps(dict(id=p['id'],title=p['title'],status=result['status'],
                              links=len(result.get('candidateLinks',[]))),ensure_ascii=False),flush=True)
        if any(x in result.get('error','').lower() for x in ('captcha','challenge','429','login required')):break

if __name__=='__main__':main()
