# 红妆

基于 Flutter 的诗词阅读应用，提供诗词正文、译文、字典与浅色/深色模式。

## 项目入口

- [当前工程说明](START_HERE.md)
- [交接文档](docs/交接文档.md)
- [安装包与发布说明索引](release/安装包索引.md)

`app/` 保存应用源码和测试，`data/` 保存正式数据库，`scripts/` 保存构建、采集与校验脚本，`expansion/` 保存内容补充及校验资料。

## 当前状态

最新 Android 轻量版本为 1.1.3+10，适用于 arm64、Android 10 及以上。已完成自动化测试、静态分析及安装包检查，尚未真机测试。部分诗词译注、字典和异文校勘仍待完善，以当前工程说明和发布清单为准。

## 开发

需要 Flutter、Android SDK 和 JDK。在项目目录运行：

```powershell
./scripts/workspace_build.ps1 -Action analyze
./scripts/workspace_build.ps1 -Action test
./scripts/workspace_build.ps1 -Action apk -TargetPlatform android-arm64
```

脚本依赖原工作区的工具布局，迁移电脑或目录时请先核对构建路径。

## 本地文件

签名密钥、构建缓存、下载的第三方工具及来源缓存、APK 和发布 ZIP 备份不纳入 Git；已有本地文件完整保留。仓库保留发布说明、正式数据和开发记录。
