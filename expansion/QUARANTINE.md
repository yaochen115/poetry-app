# C 方案：停用问题原文并补足可用数量

2026-11-03，负责人明确选择C：保留6篇有旧字形编码的《国语》记录，暂时不进入阅读、搜索和随机背诵，另补6篇正常原文。

## 数据与标记

唯一事实来源为 `data/poems.json`：

- `items` 保存所有条目，包括暂时停用的旧记录；目前2806条。
- 顶层 `disabledEntries` 记录停用ID、原因、待校勘状态及替补ID；目前6条。
- 可用库为 `items` 排除 `disabledEntries` 的ID；目前2800条，每类700。
- 可用库完整译注244、待补译注2556。停用归档的6篇另计，不进入可用库的完成率和扩库目标。
- 补入原文仍使用 original_only/pending 标记；没有伪造翻译或注释。旧2800条的正文、原ID及原字词典全部保留。

对应关系：

| 停用ID | 停用篇名 | 替补ID |
|---|---|---|
| guwen-252 | 国语·太子晋谏灵王壅谷水 | guwen-701 |
| guwen-382 | 国语·展禽论祭爰居非政之宜 | guwen-702 |
| guwen-386 | 国语·里革断宣公罟而弃之 | guwen-703 |
| guwen-393 | 国语·襄公如楚 | guwen-704 |
| guwen-398 | 国语·季桓子穿井获羊 | guwen-705 |
| guwen-403 | 国语·公父文伯之母别于男女之礼 | guwen-706 |

008-originals.json保存6篇替补原文与来源定位，dataVersion为1.1.4。停用信息位于同一诗词数据文件顶层，已同步到app/assets/data/poems.json；不用维护另一份人工排除名单。

## 应用如何停用

Repo.fromJson在载入时过滤停用ID，因此阅读查找、搜索、分类、随机背诵统一使用可用库。收藏显示会过滤查不到的停用条目。学习统计和按熟练度随机复习也过滤停用ID。

旧收藏和掌握度仍留在本地偏好记录中，没有删除。若旧的当前阅读ID已停用，启动时沿用原来的失效ID兜底逻辑，转到一篇可用原文。

## 后续AI必须遵守

1. 数量目标默认指可用库。不能以items.length=2806当作可用数量，也不能重新启用旧6篇来凑数量。
2. Python工具统一使用scripts/data_scope.py中的active_items/disabled_ids；应用使用poems.json顶层disabledEntries。build_original_batch.py和import_original_batch.py已经区分targetTotal（全部保存）与targetActiveTotal（可用目标）。
3. 下一批009；唐诗/宋词/元曲下一ID为701，古文为707。现有ID不回收，停用记录不删除、不改成另一作品。以后可用库达到4200时，若这6篇仍停用，保存总数将是4206。
4. pending-enrichment.json的items仅含可用待补；disabledItems保留停用待补记录。source-review-issues.json保留编码问题和替补关系，disabled=true的条目阻止直接恢复，不再阻止不包含它们的可用库验收。
5. 恢复前必须依据可靠版本校勘，并同步对应批次及应用数据。需明确是否保留替补继续增加可用数量，或停用替补来维持数量；不能静默重复启用。
6. 含停用项的全部存储记录仍参加来源审核与ID完整性检查；原文阶段数量、字典覆盖及后续完整译注验收针对可用库。

检查命令：

```text
python scripts/validate_data.py --original-only --expected-per-category 700
python scripts/audit_expansion.py
python scripts/export_pending_enrichment.py
python scripts/prepare_expansion.py
```

数据检查已执行，可用库的私用区字形问题为0，归档问题保留6篇。Flutter回归测试已补到app/test/quarantine_test.dart，原数据测试已更新为D阶段；本机当前未找到可用Flutter/Dart命令，本轮没有运行Flutter测试，也没有构建APK。具备工具链后，在app目录执行flutter test并检查旧当前ID/收藏/掌握度的停用行为，发版时按版本规则递增APK版本。
