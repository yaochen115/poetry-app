> **最新：停止阶段APK构建，全部译注完成后统一打包。** 当前数据poems1.2.6、dict1.1.16；精选981篇中368完整/613待补，字典2842字/1751词，仍缺811字。本轮新增38篇；v1.0.5构建请求已取消，未执行，最后实际APK为v1.0.4。先读AGENTS.md及expansion/PROGRESS_data-v1.2.6.md；下方打包计划属历史。

> **最新APK v1.0.4+5**：release/红妆-v1.0.4.apk。精选981篇、330完整译注、651待补；字典2774字/1626词。签名及包内资源已核验，所有旧包保留。网站解析器已修复；后续待办及已知体裁问题见expansion/PROGRESS_v1.0.4.md。下次发布v1.0.5+6。

> **v1.0.3+4 已构建并核验**：release/红妆-v1.0.3.apk；精选981篇/完整译注330/待补651；签名与旧包一致，旧版保留。下一发布v1.0.4+5。尚未全量完成，详见release/红妆-v1.0.3-说明.md。

> **精选981篇已启用，v1.0.3构建节点**：330篇完整译注、651待补，2774字/1625词；poems1.2.1、dict1.1.9。原4206档案及旧学习记录保留。网站搜索实测跳转登录；公开详情页可取。先读expansion/PROGRESS_v1.0.3.md、CURRENT_STATE.md；完整补齐尚未完成。

> **精选名单长度更新 v1.0.1**：元曲正文100字及以上已剔除19篇，现候选981篇（诗300、词300、曲281、文100）；有效名单expansion/selected-1000/selection-v1.0.1.json。旧名单保留，正式数据及APK未改。详见expansion/SELECTED_LENGTH_v1.0.1.md。

> **最新目标变更：精选1000篇（2026-11-04）**：诗/词/曲各300，古文100，负责人已授权尝试获取古诗文网译文及字典。先读expansion/SELECTED_1000_v1.0.0.md；旧4200全量补译注目标被覆盖。原库已备份，当前1000名单为待审候选，应用尚未切换范围。

> **v1.0.2 已构建（2026-11-04）**：release/红妆-v1.0.2.apk；4200原文/341完整译注/3859待补，阶段版。签名与旧版一致，包内资源与正式数据一致；旧APK保留，未真机测试。下一安装包v1.0.3+4。

> **2026-11-04 资料优先节点**：正式完整341、待补3859，字典2756字/1566词；poems1.1.9、dict1.1.7。资料匹配/筛查已运行，当前588篇参考候选；详见 expansion/REFERENCE_FIRST_v1.0.0.md。下一译注批次014；完整目标仍未达到。

# 「红妆」诗词背诵软件 — 接手 AI 速查

> 交付前最新：先读根目录START_HERE.md及expansion/CURRENT_STATE.md。本轮新增20条完整译注，当前完整264/可用待补3936，原文可用4200、停用6、保存4206。poems1.1.6、dict1.1.4（2698字/1342词）。补译注用scripts/apply_enrichment_batch.py，参考enrichment/010.json，下批011。当前只有源码与数据更新，未构建新版APK；历史说明不应覆盖最新状态。

> 最新4200可用原文节点：每类1050；保存4206，停用归档6。244完整译注、3956可用待补。先读expansion/CURRENT_STATE.md、AI_HANDOFF和QUARANTINE。009已入库，原文目标已达，后续是补译注/标签/字词典与校勘；不能宣称完整项目完成。poems1.1.5、dict1.1.3，默认原文检查加--original-only；完整检查仍应失败。未运行Flutter测试/打包APK。下方旧数量是历史。

> 最新C停用方案：先读expansion/QUARANTINE.md、CURRENT_STATE.md。保存2806条，停用6，可用2800（每类700），244完整译注/2556可用待补。data/poems.json顶层disabledEntries是停用表；已保留旧正文/ID/学习记录并补6篇替代。应用与Python工具都按可用库计算。下一批009，唐/宋/元ID701、古文707。poems1.1.4；未运行Flutter测试、未打包APK。下方旧统计/旧问题发布阻塞规则为历史。

> 最新2800：每类700，完整译注244、original_only待补2556。先读自动生成的expansion/CURRENT_STATE.md，再读AI_HANDOFF。下一批008、ID各类701；阶段校验参数700。007新增1000，旧1800条和字词典不变。旧库6条来源编码待校勘见source-review-issues.json，新增已排除此类字形；完整验收不得绕过。未打包APK。以下数字均为历史。

> 最新1800节点：每类450；完整译注244、original_only待补1556，poems版本1.1.2。**先读 expansion/CURRENT_STATE.md**，该文件从正式数据自动生成；再读AI_HANDOFF。当前原文阶段参数450，下一批007、ID各类451。006批次已入库，旧1200篇及字词典不变，未构建APK。下方数量均为历史说明。

> 最新节点1200：原文1200篇，每类300；完整译注244、标记original_only待补956。005-originals已完成。下一批006、各类ID从301起。以expansion/AI_HANDOFF.md、pending-enrichment.json和audit-report.json为准。阶段校验 `--original-only --expected-per-category 300`；后续用通用build_original_batch.py/import_original_batch.py，勿复用硬编码600的历史脚本。下方其他数量均为历史。

> 接手先读 `expansion/AI_HANDOFF.md`：明确 original_only 未译注标记、pending 字段、356 篇待补清单生成方式、后续新增原文与补全译注步骤。`data/poems.json` 是事实来源，`expansion/pending-enrichment.json` 是生成的逐篇待办，不能只改清单。

> 最新覆盖说明：负责人改选 D（原文优先）。现原文 600 篇、每类 150；完整译注 244、原文待补 356，务必分开计数。旧译注三批已全部完成，无遗留稿。原文阶段校验用 `--original-only --expected-per-category 150`；完整校验仍须补齐译注/主题标签/字词典。详见 `expansion/ORIGINAL_FIRST.md`、`expansion/README.md`；下方其他数量及待办描述是历史记录。

> 当前负责人已批准事项 3，扩充正在进行。正式库现为 244 篇（各 61）、2685 字、1298 词，已完成 3 个批次共新增 44 篇译注，仍余 3956 篇。最新入口为 `expansion/README.md`、`expansion/audit-report.json`。阶段校验加 `--expected-per-category 61`，默认校验仍按最终 4200 篇验收。原 APK v1.0.1 未重构建；下文原有“唯一待办未启动”“200 首”等为交接历史，不代表当前状态。

纯离线、极简奶白风格的安卓诗词背诵应用（Flutter/Dart）。项目已完成至 **v1.0.1（200 首诗词）**，
当前唯一待办是**诗词库扩充至 4200 首（等负责人明确指令后启动）**。

## 先读这三份文档（按顺序）

1. `docs/交接文档.md` — 交接唯一事实来源：状态、21+8 条不可更改的决策、扩充流水线（§6.2）、构建环境（§4）
2. `docs/进度日志.md` — 每次工作记录（最新在最上）
3. `docs/数据规范.md` — poems.json / dict.json / categories.json 格式与录入规则

## 当前状态（2026-11-03）

- 已交付：`release/红妆-v1.0.1.apk`（versionCode 2）+ 保留的 `红妆-v1.0.0.apk`
- 数据：200 首（唐诗/宋词/元曲/古文各 50）+ 字库 2612 字 + 双字词 1156 条，校验全绿
- 全部界面/交互项完成：垂直居中、熟练度折叠按钮、翻译排版、唐诗不折行、省己两档等

## 待办（等负责人指令，不要自行启动）

**扩充诗词库 200 → 4200 首**（每类 1050，+4000）。负责人已确认：包体约 50.8MB、耗时 5~7 小时、
古文超出名篇后接受质量取舍。执行流水线见《交接文档》§6.2。启动前必改
`scripts/validate_data.py`：总数 4200、每类 1050、ID 正则 `\d{3}$` → `\d{3,4}$`。

## 负责人铁律（违反即返工）

1. **版本号**：每次更新 +0.0.1，APK 文件名带版本号，**绝不覆盖旧 APK**（release\ 保留全部历史）。三处同步：
   `app/pubspec.yaml` version、`scripts/build_sync.ps1` versionName/versionCode、`scripts/build_apk.ps1` 输出文件名。
2. **数据改动必须跑** `python scripts/validate_data.py` **全绿**才能打包。
3. 构建**全程 ASCII 路径**：Flutter SDK `D:\flutter`、Android SDK `D:\android-sdk`、JDK 17 `D:\jdk17\jdk-17.0.20.1+1`、构建目录 `D:\hz-app`。中文路径会让 Dart 原生工具链崩溃；JDK 26 触发 Gradle jlink 报错。
4. **不要用** `powershell -ExecutionPolicy Bypass`（Claude Code 权限系统会拒绝）。直接执行等价命令（见下）。
5. flutter 用全路径 `D:\flutter\bin\flutter.bat` 调用；不要用管道接它的输出（.bat 会被 PowerShell 当作文档执行）。

## 构建（每次发版）

```powershell
# 1) 源码同步到 ASCII 构建目录（/MIR 镜像，排除 build/.dart_tool；退出码 0~7 正常）
robocopy "D:\WORK\丢给ai玩\诗词软件\app" "D:\hz-app" /MIR /XD build .dart_tool /NFL /NDL /NJH /NJS /NC /NS /NP /R:1 /W:1
# 2) 写回 ASCII 版 local.properties（版本号按当前版本）
#    sdk.dir=D:/android-sdk  flutter.sdk=D:/flutter  flutter.buildMode=release
#    flutter.versionName=X.Y.Z  flutter.versionCode=N
# 3) 构建
$env:JAVA_HOME="D:\jdk17\jdk-17.0.20.1+1"; $env:PATH="D:\jdk17\jdk-17.0.20.1+1\bin;$env:PATH"
$env:ANDROID_HOME="D:\android-sdk"; $env:ANDROID_SDK_ROOT="D:\android-sdk"
cd D:\hz-app; & D:\flutter\bin\flutter.bat build apk --release
# 4) 拷贝 D:\hz-app\build\app\outputs\flutter-apk\app-release.apk → release\红妆-vX.Y.Z.apk
```

（完整说明与手写等价命令见《交接文档》§4。）

## 关键 UI 规格（勿回退）

- 唐诗：两句一行、居中、**绝不折行**（按最长行自动缩字号，下限 10px）；词/曲/古文每行开头两个全角空格、靠左
- 翻译页：每行开头两个全角空格、靠左，整块垂直居中；首页诗词同样垂直居中
- 熟练度操作区：默认只显示当前档位单图标（空圈/半满/实心），点击展开三图标，**纯图标无文字**，点选即收起；打勾不弹 toast
- 首页整屏点击切换正文↔翻译；手势右滑返回；全部列表页点击条目直达首页；无返回图标；省己仅初习/熟习两档
- 三档统称「未习/初习/熟习」（0/1/2）；打勾后弹出 诗/词/曲/文 四选一
- 无滚动光晕；奶白底 #FBF8F3；印章图标；无第三方状态库（ChangeNotifier + InheritedNotifier）

## 目录

- `app/` Flutter 工程（lib/pages 各页面、lib/widgets 排版/弹层、assets/data 内置数据）
- `data/` 数据源（poems.json / dict.json / categories.json）
- `scripts/` validate_data.py（质量闸门）、build_sync.ps1 / build_apk.ps1（构建）、gen_dict.py / merge_words.py（数据生成）
- `release/` 历史 APK（勿删勿覆盖）；`docs/` 文档；`prototype/` 原型 v5.9
