"""Three-page, cached, serial acquisition test. No production writes or APK."""
from datetime import datetime, timezone
import hashlib
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import sys
import time
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen
from urllib.robotparser import RobotFileParser

from enrichment_pipeline import ROOT, Pipeline, write_once
from convert_downloaded_materials_v1_0_0 import normal

BASE = 'https://www.gushiwenku.cn'
OUT = ROOT/'expansion/gushiwenku-samples-v1.0.0'
VOID = {'br','img','input','meta','link','hr','source','wbr','area','base','embed','param','track','col'}


class Node:
    def __init__(self, tag='', attrs=()):
        self.tag = tag; self.attrs = dict(attrs); self.children = []

    def all(self):
        yield self
        for child in self.children:
            if isinstance(child, Node): yield from child.all()

    def text(self):
        if self.tag in ('script','style'): return ''
        return ''.join(c.text() if isinstance(c, Node) else c for c in self.children).strip()

    def has(self, name): return name in self.attrs.get('class','').split()


class Document(HTMLParser):
    def __init__(self, html):
        super().__init__(); self.root = Node(); self.stack = [self.root]; self.feed(html)

    def handle_starttag(self, tag, attrs):
        n = Node(tag,attrs); self.stack[-1].children.append(n)
        if tag not in VOID: self.stack.append(n)

    def handle_endtag(self, tag):
        for i in range(len(self.stack)-1,0,-1):
            if self.stack[i].tag == tag:
                del self.stack[i:]; break

    def handle_data(self, data): self.stack[-1].children.append(data)


def parse(html):
    root = Document(html).root
    nodes = list(root.all())
    title = next(n.text() for n in nodes if n.attrs.get('id') == 'poem-title')
    poem = next(n for n in nodes if n.tag == 'article' and n.has('poem-content'))
    content = '\n'.join(n.text() for n in poem.all() if n.tag == 'p' and n.has('original'))
    author = next(n.text() for n in nodes if n.has('poem-author'))
    section = next(n for n in nodes if n.tag == 'section' and n.attrs.get('aria-labelledby') == 'poem-translation')
    translations = [n.text() for n in section.all() if n.has('translate')]
    notes = []; mode = False
    for n in section.all():
        if n.tag in ('h2','h3','h4'): mode = n.text() == '注释'
        if mode and n.tag == 'p' and not n.has('translate') and n.text():
            notes.append(re.sub(r'^\s*[（(]\d+[）)]\s*', '', n.text()))
    if not content or not translations: raise ValueError('Missing body/translation')
    return dict(title=title,writer=author,content=content,translation='\n'.join(translations),
                remark='\n'.join(notes),type=[],
                extraction=dict(originalParagraphs=len(content.splitlines()),
                                translationParagraphs=len(translations),noteParagraphs=len(notes)))


def fetch(url, key):
    if urlparse(url).netloc != 'www.gushiwenku.cn': raise ValueError('Outside test host')
    path = OUT/(key+'.html'); meta = OUT/(key+'.metadata.json')
    if path.exists():
        saved = json.loads(meta.read_text(encoding='utf-8'))
        if hashlib.sha256(path.read_bytes()).hexdigest()!=saved['sha256']: raise ValueError('Cache changed')
        return path.read_text(encoding='utf-8'), saved
    time.sleep(2)
    with urlopen(Request(url, headers={'User-Agent':'HongzhuangSampleCheck/1.0 (three-page test)'}),timeout=25) as response:
        if urlparse(response.url).netloc != 'www.gushiwenku.cn': raise ValueError('Redirect outside host')
        raw = response.read(2_000_001)
        if len(raw)>2_000_000: raise ValueError('Page limit exceeded')
        record = dict(url=url,finalUrl=response.url,status=response.status,
                      fetchedAt=datetime.now(timezone.utc).isoformat(),sha256=hashlib.sha256(raw).hexdigest())
    html = raw.decode('utf-8')
    visible = Document(html).root.text()
    if any(s in visible[:2500].lower() for s in ('access denied','verify you are human','人机验证','请输入验证码')):
        raise ValueError('Access challenge; stopping')
    path.write_bytes(raw); write_once(meta,record)
    return html,record


def main():
    sys.stdout.reconfigure(encoding='utf-8'); OUT.mkdir(parents=True,exist_ok=True)
    robots = RobotFileParser(); robots_url=BASE+'/robots.txt'
    try:
        body, record = fetch(robots_url,'robots')
        robots.parse(body.splitlines()); robots_state=dict(status=record['status'], available=True)
    except HTTPError as error:
        if error.code not in (404,410): raise
        robots.parse([]); robots_state=dict(status=error.code, available=False)
        write_once(OUT/'robots-status.json',robots_state)
    seed=BASE+'/shiwen/064809f/'
    if not robots.can_fetch('HongzhuangSampleCheck',seed): raise ValueError('robots disallows seed')
    html, record = fetch(seed,'064809f')
    links = {n.text():urljoin(seed,n.attrs['href']) for n in Document(html).root.all()
             if n.tag=='a' and n.attrs.get('href','').startswith('/shiwen/')}
    urls=[seed]+[links[title] for title in ('过故人庄','春晓')]
    pipe = Pipeline(); records=[]; summaries=[]
    for url in urls:
        if not robots.can_fetch('HongzhuangSampleCheck',url): raise ValueError('robots disallows sample')
        html, meta = fetch(url,urlparse(url).path.strip('/').split('/')[-1])
        row=parse(html); row['sourceUrl']=url; row['sourceSha256']=meta['sha256']
        matches=[p for p in pipe.active.values() if normal(p['content'])==normal(row['content'])
                 and normal(p['author'])==normal(row['writer'])]
        summaries.append(dict(title=row['title'],url=url,httpStatus=meta['status'],
            **row['extraction'],matchedSelectedIds=[p['id'] for p in matches],
            pendingMatchedIds=[p['id'] for p in matches if p['id'] in pipe.pending]))
        records.append(row)
    write_once(OUT/'downloaded-records-v1.0.0.json',records)
    report=dict(toolVersion='1.0.0',robots=robots_state,requestedPoems=3,parsedPoems=len(records),
        samples=summaries,productionChanged=False,apkBuilt=False,
        reuseStatus='Reference samples only; publication permission not established.',
        scope='Three Tang poems using the same page template; no claim of whole-site completeness or unrestricted bulk access.')
    write_once(OUT/'report-v1.0.0.json',report)
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__=='__main__': main()
