"""Locate local SDKs and extract the existing JDK archive inside the workspace.

All new tool files remain inside D:/WORK/丢给ai玩/.tools. Never removes tools
or changes system PATH/JAVA_HOME. ASCII aliases, if needed, are separate from
the physical storage locations and must be tested before a build.
"""
from pathlib import Path
import hashlib
import json
import shutil
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PARENT = ROOT.parent.parent
DEST = PARENT / '.tools'


def same_file(a, b):
    if a.stat().st_size != b.stat().st_size:
        return False
    with a.open('rb') as left, b.open('rb') as right:
        return hashlib.file_digest(left, 'sha256').digest() == hashlib.file_digest(right, 'sha256').digest()


def copy_missing(src, dst, skip=()):
    if src.is_dir():
        dst.mkdir(parents=True, exist_ok=True)
        for item in src.iterdir():
            if item.name not in skip:
                copy_missing(item, dst/item.name)
    elif dst.exists():
        if not same_file(src, dst):
            raise RuntimeError(f'Existing different file, refusing overwrite: {dst}')
    else:
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)


def main():
    sys.stdout.reconfigure(encoding='utf-8')
    flutter=PARENT/'flutter-sdk/flutter'
    android=PARENT/'android-sdk'
    archive=PARENT/'_tmp/jdk17.zip'
    for path in (flutter/'bin/flutter.bat', android/'platforms/android-36/android.jar', archive):
        if not path.exists():
            raise FileNotFoundError(path)
    DEST.mkdir(parents=True, exist_ok=True)
    print('Reusing existing Flutter and Android SDK inside the workspace.', flush=True)
    print('Extracting existing JDK17 archive...', flush=True)
    jdk_root=DEST/'jdk17'
    with zipfile.ZipFile(archive) as z:
        for entry in z.infolist():
            target=(jdk_root/entry.filename).resolve()
            if not target.is_relative_to(jdk_root.resolve()):
                raise ValueError('Unsafe ZIP path: '+entry.filename)
            if entry.is_dir():
                target.mkdir(parents=True,exist_ok=True)
            elif not target.exists():
                target.parent.mkdir(parents=True,exist_ok=True)
                with z.open(entry) as src, target.open('xb') as dst:
                    shutil.copyfileobj(src,dst)
    jdks=list(jdk_root.glob('*/bin/javac.exe'))
    if len(jdks)!=1:
        raise RuntimeError('Expected one JDK17 javac.exe')
    config=dict(flutter=str(flutter),androidSdk=str(android),
                javaHome=str(jdks[0].parent.parent),buildDirectory=str(DEST/'hz-build'),
                note='All physical paths stay inside the workspace; Chinese-path build compatibility still requires validation.')
    output=ROOT/'expansion/working/build-environment-20261104.json'
    output.write_text(json.dumps(config,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(config,ensure_ascii=False,indent=2),flush=True)


if __name__=='__main__':
    main()
