"""Acquire the original-text provider's officially linked bulk database."""
from datetime import datetime,timezone
import gzip,hashlib,json,os,shutil,sqlite3,sys
from urllib.request import Request,urlopen
from enrichment_pipeline import ROOT,read,write_once

OUT=ROOT/'expansion/poetry-2000-v1.0.0/provider'


def main():
 sys.stdout.reconfigure(encoding='utf-8');OUT.mkdir(parents=True,exist_ok=True)
 release=read(ROOT/'expansion/poetry-2000-v1.0.0/provider-probe/release--data.json')
 asset=next(x for x in release['assets'] if x['name']=='poetry.db.gz')
 checks=(ROOT/'expansion/poetry-2000-v1.0.0/provider-probe/checksums--data.raw').read_text(encoding='utf-8')
 expected=next(line.split()[0] for line in checks.splitlines() if line.split()[-1]=='poetry.db.gz')
 compressed=OUT/'poetry-v0.8.0.db.gz';database=OUT/'poetry-v0.8.0.db'
 if not compressed.exists():
  if shutil.disk_usage(OUT).free<12_000_000_000:raise ValueError('Need 12 GB free space for bounded download/extraction')
  temporary=compressed.with_suffix('.partial');sha=hashlib.sha256();total=0
  with urlopen(Request(asset['browser_download_url'],headers={'User-Agent':'HongzhuangAnthology/1.0','Accept-Encoding':'identity'}),timeout=60) as response,temporary.open('wb') as output:
   if response.status!=200:raise ValueError('Expected official full asset response')
   while True:
    block=response.read(1_048_576)
    if not block:break
    total+=len(block)
    if total>asset['size']:raise ValueError('Unexpected asset size')
    sha.update(block);output.write(block)
    if total%52_428_800==0:print('Downloaded',total//1_048_576,'MiB',flush=True)
  if total!=asset['size'] or sha.hexdigest()!=expected:raise ValueError('Official asset checksum/size mismatch')
  temporary.rename(compressed)
 else:
  sha=hashlib.file_digest(compressed.open('rb'),'sha256').hexdigest()
  if sha!=expected:raise ValueError('Cached asset changed')
 if not database.exists():
  temporary=database.with_suffix('.partial');total=0
  with gzip.open(compressed,'rb') as incoming,temporary.open('wb') as output:
   while True:
    block=incoming.read(4_194_304)
    if not block:break
    total+=len(block)
    if total>8_000_000_000:raise ValueError('Extraction budget exceeded')
    output.write(block)
  temporary.rename(database)
 connection=sqlite3.connect(database.resolve().as_uri()+'?mode=ro',uri=True)
 tables=connection.execute("SELECT name,sql FROM sqlite_master WHERE type='table'").fetchall()
 report=dict(provider='https://poetry.palemoky.com/',sourceUrl=asset['browser_download_url'],release=release['tag_name'],
   compressedBytes=compressed.stat().st_size,compressedSha256=expected,databaseBytes=database.stat().st_size,
   databaseSha256=hashlib.file_digest(database.open('rb'),'sha256').hexdigest(),acquiredAt=datetime.now(timezone.utc).isoformat(),
   schema=tables)
 write_once(OUT/'provider-v0.8.0-manifest.json',report)
 print(json.dumps({k:v for k,v in report.items() if k!='schema'},ensure_ascii=False,indent=2))
 print(json.dumps(tables,ensure_ascii=False)[:12000])


if __name__=='__main__':main()
