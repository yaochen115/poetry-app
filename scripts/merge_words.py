# -*- coding: utf-8 -*-
"""合并 Workflow 生成的四类双字词到 data/dict.json 的 words 字段。

- 输入：_tmp/words_唐诗.json 等 4 个文件（顶层 {"words": [{"word","meaning"}, ...]}）
- 输出：data/dict.json 的 words 字段（word -> 释义字符串）
- 去重策略：同一词的多条释义若不同，用「；」连接；相同则只保留一条。
"""
import json
import os
import sys

sys.stdout.reconfigure(encoding="utf-8")

HERE = os.path.dirname(os.path.abspath(__file__))
PROJ = os.path.dirname(HERE)
TMP = os.path.join(os.path.dirname(PROJ), "_tmp")  # _tmp 在项目上一级
DATA = os.path.join(PROJ, "data")

CATS = ["唐诗", "宋词", "元曲", "古文"]


def main():
    merged = {}  # word -> list[str] 保持顺序去重
    total = 0
    for cat in CATS:
        path = os.path.join(TMP, f"words_{cat}.json")
        if not os.path.exists(path):
            print(f"[跳过] 未找到 {path}")
            continue
        with open(path, encoding="utf-8") as f:
            ws = json.load(f)["words"]
        total += len(ws)
        for w in ws:
            k = w["word"].strip()
            m = w["meaning"].strip()
            if not k or not m:
                continue
            lst = merged.setdefault(k, [])
            if m not in lst:
                lst.append(m)

    words = {k: "；".join(v) for k, v in merged.items()}

    dict_path = os.path.join(DATA, "dict.json")
    with open(dict_path, encoding="utf-8") as f:
        d = json.load(f)

    d["words"] = words
    # 词库补全，数据版本微调
    d["dataVersion"] = "1.1.0"

    with open(dict_path, "w", encoding="utf-8") as f:
        json.dump(d, f, ensure_ascii=False, indent=2)

    print(f"总词条 {total}，去重后 {len(words)} 条，已写入 {dict_path}")


if __name__ == "__main__":
    main()
