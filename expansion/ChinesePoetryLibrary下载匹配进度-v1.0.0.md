# ChinesePoetryLibrary 下载与匹配进度 v1.0.0

2026-11-09，用户电脑重启后已继续断点任务。当前只允许下载资料和生成匹配候选；正式导入必须用户明确同意。下一APK也必须另行批准。

来源 byj233/ChinesePoetryLibrary，固定版本30bc128b3b100a0b62863e7877df1363837d2cbf。原始文件及版本清单位于 expansion/sources/chinesepoetrylibrary-v1.0.0/。整个八卷文本约9.3GB，排除了向量数据和作者简介表。

古文、唐诗、宋词、元代、其他五卷已下载并校验通过，宋诗/明代/清代利用.part连续前缀及.segments内分段继续下载。日志中的分卷匹配记录数包含启用与归档篇目，最终以全部完成后的去重报告为准。不要把试匹配16篇当成全量结果。

执行入口 scripts/match_chinesepoetrylibrary_v1_0_0.py --phase full --workers 3。固定源文件按声明大小和Git blob/LFS散列校验；首次已通过古文卷试运行。可以复用全部完整文件、完整分段和未完成分段。若再次重启，先确认没有重复运行的下载进程，再执行同一命令续跑。

输出目录为 expansion/chinesepoetrylibrary-matching-v1.0.0/，当前只有pilot小样本。完整结果应有full-时间戳目录，包含candidates-v1.0.0.json、report-v1.0.0.json和unmatched-active-v1.0.0.json。完整报告必须核查volumesCompleted=8且errors为空；任务中断时不会把部分扫描冒充全量报告。

候选按作者及规范化全文匹配，另列原文异文、无译文、疑似残缺和译文冲突。原始译文、注释和来源记录均保留到候选，不进行AI补译。脚本运行前后比较正式data及app/assets/data四个文件SHA256，确保只读。当前正式译文仍为空，字典仍为新华dict1.1.28。
