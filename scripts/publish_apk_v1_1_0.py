"""Publish v1.1.0+7 only after signature, assets, content and ZIP verification."""
import hashlib,json,re,shutil,sys,zipfile
from enrichment_pipeline import ROOT,read,write_once
from data_scope import active_items

def main():
    sys.stdout.reconfigure(encoding='utf-8');audit=ROOT/'expansion/release-audits'
    badging=(audit/'apk-v1.1.0-badging.txt').read_text(encoding='utf-8-sig')
    assert "name='com.hongzhuang.hongzhuang_app'" in badging
    assert "versionName='1.1.0'" in badging and "versionCode='7'" in badging
    assert re.search(r"(?:minSdkVersion|sdkVersion):'29'",badging)
    def cert(name):
        raw=(audit/name).read_text(encoding='utf-8-sig')
        return re.search(r'Signer #1 certificate SHA-256 digest:\s*([0-9a-fA-F]+)',raw)[1].lower()
    certificate=cert('apk-v1.1.0-signature.txt')
    assert certificate==cert('apk-v1.0.5-signature-check.txt')
    previous=read(ROOT/'release/红妆-v1.0.5-manifest.json')
    assert hashlib.sha256((ROOT/'release/红妆-v1.0.5.apk').read_bytes()).hexdigest()==previous['sha256']
    source=ROOT.parents[1]/'.tools/hz-build/build/app/outputs/flutter-apk/app-release.apk'
    with zipfile.ZipFile(source) as apk:
        assert apk.testzip() is None
        for name in ('poems.json','dict.json'):
            expected=(ROOT/'data'/name).read_bytes()
            assert apk.read('assets/flutter_assets/assets/data/'+name)==expected
            assert (ROOT/'app/assets/data'/name).read_bytes()==expected
    doc=read(ROOT/'data/poems.json');dictionary=read(ROOT/'data/dict.json');items=active_items(doc)
    content=read(audit/('content-data-v'+doc['dataVersion']+'-dict-v'+dictionary['dataVersion']+'-v1.0.0.json'))
    assert not content['errors']
    variants=sum('sourceVariant' in b for b in doc.get('poetryApiBindings',{}).values())
    release=ROOT/'release';destination=release/'红妆-v1.1.0.apk'
    archive=release/'红妆-v1.1.0-源码数据备份.zip';note=release/'红妆-v1.1.0-说明.md';manifest_path=release/'红妆-v1.1.0-manifest.json'
    assert not any(p.exists() for p in (destination,archive,note,manifest_path)), 'Refusing to overwrite a release'
    with destination.open('xb') as f,source.open('rb') as incoming:shutil.copyfileobj(incoming,f)
    digest=hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest=dict(versionName='1.1.0',versionCode=7,package='com.hongzhuang.hongzhuang_app',minSdk=29,
        selected=len(items),stored=len(doc['items']),availableTranslations=content['availableTranslations'],missingTranslations=content['missingTranslations'],
        dataVersion=doc['dataVersion'],dictionaryVersion=dictionary['dataVersion'],dictionaryCharacters=len(dictionary['chars']),dictionaryWords=len(dictionary['words']),
        sourceBindings=len(doc.get('poetryApiBindings',{})),variantBindingsPendingReview=variants,
        missingDictionarySelected=len(content['missingDictionarySelected']),missingDictionaryTranslated=len(content['missingDictionaryTranslated']),
        sha256=digest,bytes=destination.stat().st_size,certificateSha256=certificate,signatureMatchesPrevious=True,assetsMatch=True,
        contentAuditErrors=0,noteReviewFlags=len(content['reviewFlags']),flutterTests=6,flutterAnalyze='no issues',deviceTested=False,
        sourceBackup=archive.name,stage='负责人明确按当前内容发布1.1.0；仍有缺译注、字典及异文待复核。')
    explanation=f'''# 红妆 v1.1.0（内部版本号7）

按负责人要求将当前软件和数据库打包为1.1.0；本次明确发布要求覆盖此前等待全部译注完成再打包的限制。旧APK、数据快照和备份保留。

- 可用原文{len(items)}篇，保存{len(doc['items'])}条；含张若虚《春江花月夜》全文252字。
- 可读译文{content['availableTranslations']}篇，仍缺{content['missingTranslations']}篇。字典{len(dictionary['chars'])}字、{len(dictionary['words'])}词。
- 诗泉名单来源绑定{len(doc.get('poetryApiBindings',{}))}/2000，含{variants}个待校勘异文；来源绑定不等于新增独立作品，名录尚未全量完成。已有通行本、译文及学习ID保留。
- 全部可用正文仍有{len(content['missingDictionarySelected'])}个字待补释义，已有译文正文中缺{len(content['missingDictionaryTranslated'])}字。保留未收录提示，不填占位释义。
- 原文结构/来源审计通过，内容审计阻断错误0；{len(content['reviewFlags'])}项旧词注提示保留待核。6项Flutter测试和静态分析通过，包名/版本/签名/ZIP及包内数据逐字节核验通过；未真机安装测试。
- 最低Android 10，沿用v1.0.5签名，支持覆盖安装；数据版本{doc['dataVersion']}，字典版本{dictionary['dataVersion']}。

APK SHA256：{digest}

源码数据备份ZIP不含SDK、构建缓存、签名密钥与大体积下载缓存；完整采集来源和过程仍在原项目expansion目录中。
'''
    with note.open('x',encoding='utf-8') as f:f.write(explanation)
    headline=f'**最新交付：红妆v1.1.0+7已构建核验。** 安装包 `release/红妆-v1.1.0.apk`；{len(items)}篇可用原文、{content["availableTranslations"]}篇译文、{content["missingTranslations"]}篇待译，字典2956字/1884词，poems{doc["dataVersion"]}/dict{dictionary["dataVersion"]}。历史签名一致、包内数据一致，旧包/备份保留。6项Flutter测试、静态分析及内容/来源审计通过；未真机测试，仍有词典及异文待补校。先读release/红妆-v1.1.0-说明.md。下方未打包/待构建节点为历史；下次默认v1.1.1+8。'
    for path in (ROOT/'AGENTS.md',ROOT/'START_HERE.md',ROOT/'docs/交接文档.md'):
        raw=path.read_text(encoding='utf-8')
        path.write_text(headline+'\n\n'+raw,encoding='utf-8')
    excluded={'build','.dart_tool','.gradle','.git','__pycache__','.idea','ephemeral','node_modules','versions'}
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as out:
        for folder in ('app','data','scripts','docs'):
            for p in (ROOT/folder).rglob('*'):
                if p.is_file() and not any(part in excluded for part in p.relative_to(ROOT).parts) and p.name!='local.properties':
                    out.write(p,p.relative_to(ROOT).as_posix())
        for p in (ROOT/'AGENTS.md',ROOT/'START_HERE.md',note):out.write(p,p.relative_to(ROOT).as_posix())
        for p in audit.glob('*'):
            if p.is_file():out.write(p,p.relative_to(ROOT).as_posix())
        for name in ('CURRENT_STATE.md','诗泉名单自动同步-v1.0.1.md','诗泉采集成果-v1.0.1.md'):
            p=ROOT/'expansion'/name
            if p.exists():out.write(p,p.relative_to(ROOT).as_posix())
        p=ROOT/'expansion/poetry-2000-v1.0.0/catalog-v1.0.2.json';out.write(p,p.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as z:assert z.testzip() is None
    manifest['sourceBackupSha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
    write_once(manifest_path,manifest,accept_identical=False)
    print(json.dumps(manifest,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
