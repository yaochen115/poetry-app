# 当前接手状态（自动生成）

由 data/poems.json 生成。selectionProfile限定当前精选库，未入选原文仍保留归档，不属于当前待补目标。

- 可用原文：981；四类数量：唐诗 300、宋词 300、元曲 281、古文 100。
- 保存条目：4206；停用归档：6，从 data/poems.json 顶层 disabledEntries 读取，应用不加载到阅读/搜索/随机复习。
- 可用库完整译注：418；可用原文待补：563；归档待补另计 6。
- 有可读译文：803；其中补充表自动导入 385 篇（未逐篇复核、注释/标签/字典可待补）；仍无译文 178。完整译注数不因此增加。
- 字典：2956 字、1884 词；原文阶段待补缺字 697 个。
- poems 数据版本：1.2.25；dict 数据版本：1.1.24。
- 下一译注批次：027（enrichment/）；下一原文批次：010（batches/，原文已达目标无需继续扩充）。
- 来源文字编码待校勘：6 篇，当前停用 6 篇。详见 source-review-issues.json；新批次不导入此类私用区编码。
- 下一可用 ID：tang-1051、song-1051、yuan-1051、guwen-1057。

## 立即可执行的当前检查

```text
python scripts/validate_data.py --original-only --expected-per-category 300
python scripts/audit_expansion.py
python scripts/export_pending_enrichment.py
```

pending-enrichment.json 是逐篇待补列表，pending-dictionary.json 是当前缺字队列；两者由本脚本生成，不能只改清单。
AI_HANDOFF.md 说明状态转换及后续扩充方法。batches/ 保存来源定位与批次，checkpoints/ 保存变更前数据。
原文规模不是完整译注完成数。新增原文包括完整作品、明确标注的古文章则或数据段、元曲曲牌条目；组题保留整条且标明范围，不拆分计数。
来源文本匹配及数据结构校验不等于逐字版本校勘。Flutter 测试及 APK 构建状态请查最新进度日志，不能从本数量报表推断。
