"""Export and check explicit original-only markers for the next maintainer."""
import json
from collections import Counter
from pathlib import Path
from data_scope import active_items,disabled_ids
from translation_overlay_v1_0_0 import overlay_for

ROOT = Path(__file__).resolve().parents[1]
PENDING = ['translation', 'notes', 'themeTags', 'dictionary']


def main():
    document=json.loads((ROOT / 'data/poems.json').read_text(encoding='utf-8'))
    poems = document['items']
    active=active_items(document)
    disabled=disabled_ids(document)
    disabled_info={p['id']:p for p in document.get('disabledEntries',[])}
    queue = []
    for p in poems:
        incomplete = p.get('editorialStatus') == 'original_only'
        if not p.get('translation', '').strip() and not incomplete:
            raise ValueError(f'{p["id"]}: empty translation without pending marker')
        if incomplete:
            if p['translation'] != '' or p['notes'] != [] or set(p.get('pending', [])) != set(PENDING):
                raise ValueError(f'{p["id"]}: inconsistent original-only marker')
            extra=overlay_for(document,p)
            queue.append(dict(id=p['id'], category=p['category'], title=p['title'],
                              subtitle=p['subtitle'], author=p['author'],
                              editorialStatus='original_only', pending=p['pending'],
                              translationAvailable=bool(extra),
                              importedPending=extra['pending'] if extra else None))
    active_ids={p['id'] for p in active}
    active_queue=[p for p in queue if p['id'] in active_ids]
    disabled_queue=[dict(p,disabled=True,disabledReason=disabled_info[p['id']]['reason'],
                         replacementId=disabled_info[p['id']]['replacementId']) for p in queue if p['id'] in disabled]
    partial=sum(bool(overlay_for(document,p)) and not p.get('translation','').strip() for p in active)
    available=sum(bool(p.get('translation','').strip()) or bool(overlay_for(document,p)) for p in active)
    report = dict(
        schemaVersion=1, sourceOfTruth='data/poems.json',
        markerField='editorialStatus', markerValue='original_only',
        meaning='仅原文；翻译、注释、主题标签、字词典尚未补齐，不得计为完整译注',
        totalEntries=len(active),storedTotal=len(poems),disabledCount=len(disabled),
        completeWithTranslation=len(active)-len(active_queue),
        sourceImportedTranslations=partial, availableTranslations=available, translationsMissing=len(active)-available,
        pendingCount=len(active_queue),storedPendingCount=len(queue),
        pendingByCategory=dict(Counter(p['category'] for p in active_queue)),
        idsStable=True, nextIds={cat: f'{prefix}-{1+max(int(p["id"].split("-")[-1]) for p in poems if p["category"]==cat):03}'
            for cat,prefix in [('唐诗','tang'),('宋词','song'),('元曲','yuan'),('古文','guwen')]},
        items=active_queue,disabledItems=disabled_queue,
        archivedUnselectedItems=[p for p in queue if p['id'] not in active_ids and p['id'] not in disabled],
    )
    (ROOT/'expansion/pending-enrichment.json').write_text(
        json.dumps(report, ensure_ascii=False, indent=2)+'\n', encoding='utf-8')
    dictionary = json.loads((ROOT/'data/dict.json').read_text(encoding='utf-8'))
    missing = sorted({c for p in active if p.get('editorialStatus') == 'original_only'
                      for c in p['content'] if '\u4e00' <= c <= '\u9fff'} - set(dictionary['chars']))
    (ROOT/'expansion/pending-dictionary.json').write_text(json.dumps(dict(
        sourceOfTruth='data/poems.json', productionTotal=len(active), missingCharacters=missing,
        count=len(missing), stage='pending_not_completed'), ensure_ascii=False, indent=2)+'\n',encoding='utf-8')
    glyph_issues = [dict(id=p['id'],title=p['title'],
        codepoints=sorted({f'U+{ord(c):04X}' for c in p['content'] if 0xe000<=ord(c)<=0xf8ff}),
        reason='原来源使用私用区编码；须对照可靠版本恢复通用汉字，不得凭读音猜字',
        disabled=p['id'] in disabled,
        replacementId=disabled_info.get(p['id'],{}).get('replacementId'),
        blocksFullRelease=p['id'] not in disabled,blocksReactivation=True)
        for p in poems if any(0xe000<=ord(c)<=0xf8ff for c in p['content'])]
    (ROOT/'expansion/source-review-issues.json').write_text(json.dumps(dict(
        productionTotal=len(active),storedTotal=len(poems),issueCount=len(glyph_issues),items=glyph_issues,
        note='本清单不修改已交付的稳定ID或正文；后续校勘须同步对应批次与应用资源并记录依据。'),
        ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    counts = Counter(p['category'] for p in active)
    current_version = json.loads((ROOT/'data/poems.json').read_text(encoding='utf-8'))['dataVersion']
    next_batch = 1+max(int(p.name.split('-')[0].split('.')[0]) for p in (ROOT/'expansion/batches').glob('*.json'))
    next_enrichment = 1+max((int(p.stem) for p in (ROOT/'expansion/enrichment').glob('*.json')
                            if p.stem.isdigit()), default=0)
    state = '\n'.join([
        '# 当前接手状态（自动生成）', '',
        '由 data/poems.json 生成。selectionProfile限定当前精选库，未入选原文仍保留归档，不属于当前待补目标。', '',
        f'- 可用原文：{len(active)}；四类数量：'+ '、'.join(f'{c} {counts[c]}' for c in ['唐诗','宋词','元曲','古文'])+'。',
        f'- 保存条目：{len(poems)}；停用归档：{len(disabled)}，从 data/poems.json 顶层 disabledEntries 读取，应用不加载到阅读/搜索/随机复习。',
        f'- 可用库完整译注：{len(active)-len(active_queue)}；可用原文待补：{len(active_queue)}；归档待补另计 {len(disabled_queue)}。',
        f'- 有可读译文：{available}；其中补充表自动导入 {partial} 篇（未逐篇复核、注释/标签/字典可待补）；仍无译文 {len(active)-available}。完整译注数不因此增加。',
        f'- 字典：{len(dictionary["chars"])} 字、{len(dictionary["words"])} 词；原文阶段待补缺字 {len(missing)} 个。',
        f'- poems 数据版本：{current_version}；dict 数据版本：{dictionary["dataVersion"]}。',
        f'- 下一译注批次：{next_enrichment:03}（enrichment/）；下一原文批次：{next_batch:03}（batches/，原文已达目标无需继续扩充）。',
        f'- 来源文字编码待校勘：{len(glyph_issues)} 篇，当前停用 {sum(p["disabled"] for p in glyph_issues)} 篇。详见 source-review-issues.json；新批次不导入此类私用区编码。',
        '- 下一可用 ID：'+ '、'.join(report['nextIds'].values())+'。', '',
        '## 立即可执行的当前检查', '', '```text',
        f'python scripts/validate_data.py --original-only --expected-per-category {next(iter(counts.values()))}',
        'python scripts/audit_expansion.py', 'python scripts/export_pending_enrichment.py', '```', '',
        'pending-enrichment.json 是逐篇待补列表，pending-dictionary.json 是当前缺字队列；两者由本脚本生成，不能只改清单。',
        'AI_HANDOFF.md 说明状态转换及后续扩充方法。batches/ 保存来源定位与批次，checkpoints/ 保存变更前数据。',
        '原文规模不是完整译注完成数。新增原文包括完整作品、明确标注的古文章则或数据段、元曲曲牌条目；组题保留整条且标明范围，不拆分计数。',
        '来源文本匹配及数据结构校验不等于逐字版本校勘。Flutter 测试及 APK 构建状态请查最新进度日志，不能从本数量报表推断。', '',
    ])
    (ROOT/'expansion/CURRENT_STATE.md').write_text(state,encoding='utf-8')
    print(f'Checked stored {len(poems)}, active {len(active)}, disabled {len(disabled)}; active pending {len(active_queue)}; unmarked empty translations 0.')


if __name__ == '__main__':
    main()
