# -*- coding: utf-8 -*-
"""
dict.json 生成/合并脚本
用法:
  python scripts/gen_dict.py                   # 扫描 poems.json 生成骨架（pypinyin 自动填充拼音）
  python scripts/gen_dict.py --merge MX目录    # 合并 MX目录/mx_part*.py 中的释义(MX)与词表(WORDS)
"""
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
DICT_FP = DATA / "dict.json"

PRINT_BATCH = 40  # 缺释义字符按批打印, 便于拆分录入


def scan_chars():
    poems = json.loads((DATA / "poems.json").read_text(encoding="utf-8"))
    chars = set()
    for it in poems["items"]:
        for ch in it["content"]:
            if ch.strip() and ("\u4e00" <= ch <= "\u9fff" or ch == "\u3007"):
                chars.add(ch)
    return sorted(chars)


def build_skeleton():
    from pypinyin import pinyin
    chars = scan_chars()
    d = {"dataVersion": "1.0.0", "chars": {}, "words": {}}
    miss = []
    for ch in chars:
        try:
            r = pinyin(ch, heteronym=True)
        except Exception:
            r = []
        ps = []
        for grp in r:
            for p in grp:
                if p not in ps:
                    ps.append(p)
        if not ps:
            miss.append(ch)
        d["chars"][ch] = {"pinyin": ps, "meanings": [], "ancient": []}
    DICT_FP.write_text(json.dumps(d, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    print(f"骨架生成: {len(chars)} 字, 无拼音 {len(miss)}: {''.join(miss)}")


def merge(mxdir):
    d = json.loads(DICT_FP.read_text(encoding="utf-8"))
    poems = json.loads((DATA / "poems.json").read_text(encoding="utf-8"))
    corpus = "\n".join(it["content"] for it in poems["items"])
    mx, words, unknown_chars, unknown_words = {}, {}, [], []
    for fp in sorted(Path(mxdir).glob("mx_part*.py")):
        spec = importlib.util.spec_from_file_location("mx_" + fp.stem, fp)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        for k, v in getattr(mod, "MX", {}).items():
            if k not in d["chars"]:
                unknown_chars.append(k)
            mx[k] = v
        for k, v in getattr(mod, "WORDS", {}).items():
            if k not in corpus:
                unknown_words.append(k)
            words[k] = v
        print(f"  加载 {fp.name}: {len(getattr(mod, 'MX', {}))} 字, {len(getattr(mod, 'WORDS', {}))} 词")
    for ch, v in mx.items():
        entry = d["chars"].get(ch)
        if entry is None:
            continue
        entry["meanings"] = v.get("m", [])
        entry["ancient"] = v.get("a", [])
    for w, m in words.items():
        d["words"][w] = m
    DICT_FP.write_text(json.dumps(d, ensure_ascii=True, indent=2) + "\n", encoding="utf-8")
    if unknown_chars:
        print(f"  [警告] 忽略不在字库中的字符: {''.join(unknown_chars)}")
    if unknown_words:
        print(f"  [警告] 忽略正文中不存在的词: {'、'.join(unknown_words)}")
    missing = sorted(c for c in d["chars"] if not d["chars"][c]["meanings"])
    (ROOT.parent / "_tmp" / "missing_chars.txt").write_text("".join(missing), encoding="utf-8")
    print(f"合并完成: 有效 {len(mx) - len(unknown_chars)} 字释义, {len(words) - len(unknown_words)} 词。"
          f"仍缺释义 {len(missing)} 字, 清单已写入 _tmp/missing_chars.txt")
    print("  预览: " + "".join(missing[:120]))


if __name__ == "__main__":
    if "--merge" in sys.argv:
        merge(sys.argv[sys.argv.index("--merge") + 1])
    else:
        build_skeleton()