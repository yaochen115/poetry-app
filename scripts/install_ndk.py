# -*- coding: utf-8 -*-
"""手动安装 NDK r28c（28.2.13676358）到 Android SDK（腾讯镜像下载的 zip）。

- 输入：_tmp/android-ndk-r28c-windows.zip
- 输出：$ANDROID_HOME/ndk/28.2.13676358/（含 source.properties 与 package.xml）
"""
import shutil
import sys
import zipfile
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

SDK = Path(r"d:\WORK\丢给ai玩\android-sdk")
TMP = Path(r"d:\WORK\丢给ai玩\_tmp")
NDK_VER = "28.2.13676358"

PKG_XML = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<ns2:repository xmlns:ns2="http://schemas.android.com/repository/android/common/01">
  <license id="android-sdk-license" type="text">Software License Agreement</license>
  <localPackage path="ndk;{ver}" obsolete="false">
    <type-details xsi:type="ns2:ndkDetailsType">
      <installed-by>manual-mirror</installed-by>
    </type-details>
    <revision><major>{maj}</major></revision>
    <display-name>NDK (Side by side) {ver}</display-name>
  </localPackage>
</ns2:repository>
'''


def main():
    zip_path = TMP / "android-ndk-r28c-windows.zip"
    if not zip_path.exists():
        print(f"[错误] 未找到 {zip_path}")
        return 1

    dest = SDK / "ndk" / NDK_VER
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True, exist_ok=True)

    xdir = TMP / "x-ndk"
    if xdir.exists():
        shutil.rmtree(xdir)
    xdir.mkdir(parents=True)

    print("解压中（约 748MB，请稍候）…")
    with zipfile.ZipFile(zip_path) as z:
        z.extractall(xdir)

    tops = [p for p in xdir.iterdir() if p.is_dir()]
    src = tops[0] if tops else xdir  # android-ndk-r28c/
    for item in src.iterdir():
        item.rename(dest / item.name)
    shutil.rmtree(xdir, ignore_errors=True)

    # source.properties 已由官方 zip 提供（Pkg.Revision = 28.2.13676358）
    sp = dest / "source.properties"
    assert sp.exists(), "缺少 source.properties"

    (dest / "package.xml").write_text(
        PKG_XML.format(ver=NDK_VER, maj=NDK_VER.split(".")[0]),
        encoding="utf-8",
    )

    n = sum(1 for _ in dest.rglob("*") if _.is_file())
    print(f"OK 安装 NDK {NDK_VER}，{n} 个文件 → {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
