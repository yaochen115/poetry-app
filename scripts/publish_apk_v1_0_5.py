"""Publish the verified APK without overwriting historical releases."""
import hashlib,json,re,shutil,sys,zipfile
from pathlib import Path
from enrichment_pipeline import ROOT,read,write_once
from data_scope import active_items
from translation_overlay_v1_0_0 import overlay_for


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    audit=ROOT/'expansion/release-audits'
    badging=(audit/'apk-v1.0.5-badging.txt').read_text(encoding='utf-8-sig')
    assert "name='com.hongzhuang.hongzhuang_app'" in badging
    assert "versionCode='6'" in badging and "versionName='1.0.5'" in badging
    assert re.search(r"(?:minSdkVersion|sdkVersion):'29'",badging)
    def certificate(name):
        raw=(audit/name).read_text(encoding='utf-8-sig')
        return re.search(r'Signer #1 certificate SHA-256 digest:\s*([0-9a-fA-F]+)',raw)[1].lower()
    cert=certificate('apk-v1.0.5-signature.txt')
    assert cert==certificate('apk-v1.0.4-signature-check.txt')
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
    old_manifest=read(ROOT/'release/红妆-v1.0.4-manifest.json')
    assert hashlib.sha256((ROOT/'release/红妆-v1.0.4.apk').read_bytes()).hexdigest()==old_manifest['sha256']
    destination=ROOT/'release/红妆-v1.0.5.apk'
    with destination.open('xb') as output,source.open('rb') as incoming:shutil.copyfileobj(incoming,output)
    sha=hashlib.sha256(destination.read_bytes()).hexdigest()
    manifest=dict(versionName='1.0.5',versionCode=6,package='com.hongzhuang.hongzhuang_app',minSdk=29,
        selected=len(items),stored=len(doc['items']),availableTranslations=content['availableTranslations'],
        missingTranslations=content['missingTranslations'],complete=sum(p.get('editorialStatus')!='original_only' for p in items),partialImports=len(doc['translationImports']),
        dictionaryCharacters=len(dictionary['chars']),dictionaryWords=len(dictionary['words']),
        missingDictionarySelected=len(content['missingDictionarySelected']),missingDictionaryTranslated=len(content['missingDictionaryTranslated']),
        dataVersion=doc['dataVersion'],dictionaryVersion=dictionary['dataVersion'],sha256=sha,bytes=destination.stat().st_size,
        certificateSha256=cert,signatureMatchesPrevious=True,assetsMatch=True,
        contentAuditErrors=len(content['errors']),noteReviewFlags=len(content['reviewFlags']),
        pythonAuditTests=4,flutterTests=5,flutterAnalyze='no issues',deviceTested=False,
        stage='负责人明确要求当前内容检查后发布；仍有缺译文、缺释义及未逐篇语义复核内容。')
    explanation=f'''# 红妆 v1.0.5（版本号6）

本次按负责人最新要求，对当前已录入译文和字典进行检查后打包；此前“全部完成后再打包”的等待要求由这次明确指令覆盖。旧APK与源码数据备份保留。

- 当前精选981篇，803篇有可读译文、178篇仍无译文。原文、ID和学习记录结构保留。
- 字典2956字、1884词；本轮从已有明确正文注释中补入54个单字古义，不覆盖旧释义。有歧义或混入其他词条的候选保留未补。
- 对803篇译文、5088条注释和全部字词条目进行结构检查，385篇补充译文逐条回放来源及散列比对，阻断错误0项。
- 51项词注不逐字出现在正文原串，涉及题名、组合词及节选上下文；作为编辑复核提示保留，没有为消除提示而删除原200条基线注释。
- 词典在已有译文正文中仍缺527个用字，全部精选正文仍缺698个（统计含〇）。未收录字保留软件的未收录提示，不以占位释义补数。
- 结构/来源检查不等于全文学与词典义项逐条精校；补充译文和本次来源古义的复核标记继续保留。
- 4项Python审计测试、5项Flutter测试通过，flutter analyze无问题。APK版本、最低Android 10、历史签名一致、ZIP完整性和包内资源逐字节核验通过；未真机安装测试。
- poems数据{doc['dataVersion']}、dict数据{dictionary['dataVersion']}。沿用历史签名，包名com.hongzhuang.hongzhuang_app。

APK SHA256：{sha}

完整计数及校验证据见同名manifest与expansion/release-audits/。当前包确实包含补充译文读取代码及本次新数据，历史v1.0.4不含这些更新。
'''
    with (ROOT/'release/红妆-v1.0.5-说明.md').open('x',encoding='utf-8') as stream:stream.write(explanation)
    archive=ROOT/'release/红妆-v1.0.5-源码数据备份.zip'
    excluded={'build','.dart_tool','.gradle','.git','__pycache__','.idea','ephemeral','node_modules'}
    with zipfile.ZipFile(archive,'x',compression=zipfile.ZIP_DEFLATED) as output:
        for folder in ('app','data','scripts','docs'):
            for path in (ROOT/folder).rglob('*'):
                if path.is_file() and not any(p in excluded for p in path.relative_to(ROOT).parts) and path.name!='local.properties':
                    output.write(path,path.relative_to(ROOT).as_posix())
        for name in ('AGENTS.md','START_HERE.md'):
            output.write(ROOT/name,name)
        output.write(ROOT/'release/红妆-v1.0.5-说明.md','release/红妆-v1.0.5-说明.md')
        for path in audit.glob('*'):
            if path.is_file():output.write(path,path.relative_to(ROOT).as_posix())
    with zipfile.ZipFile(archive) as package:assert package.testzip() is None
    manifest['sourceBackup']=archive.name
    manifest['sourceBackupSha256']=hashlib.sha256(archive.read_bytes()).hexdigest()
    write_once(ROOT/'release/红妆-v1.0.5-manifest.json',manifest,accept_identical=False)
    print(json.dumps(manifest,ensure_ascii=False,indent=2))


if __name__=='__main__':main()
