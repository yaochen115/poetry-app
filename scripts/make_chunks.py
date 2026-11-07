# -*- coding: utf-8 -*-
"""把待补译注队列切成 per-agent 工作块（含预计算的缺字清单）。

每块一首类、50 首，输出 expansion/working/chunks/in-NNN.json：
  {chunk, category, tagEnum, poems:[{id,title,subtitle,author,dynasty,
    excerptOf,excerptNote,content,missingChars}]}
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
WORK = ROOT / "expansion" / "working" / "chunks"
CHUNK_SIZE = 50
CAT_ORDER = ["唐诗", "宋词", "元曲", "古文"]


def main():
    poems = json.loads((DATA / "poems.json").read_text(encoding="utf-8"))
    dictionary = json.loads((DATA / "dict.json").read_text(encoding="utf-8"))
    cats = json.loads((DATA / "categories.json").read_text(encoding="utf-8"))
    tag_map = {c["key"]: c["tags"] for c in cats["categories"]}
    disabled = {e["id"] for e in poems.get("disabledEntries", [])}
    dict_chars = set(dictionary["chars"])

    pending = [p for p in poems["items"]
               if p.get("editorialStatus") == "original_only" and p["id"] not in disabled]
    by_cat = {}
    for p in pending:
        by_cat.setdefault(p["category"], []).append(p)
    for k in by_cat:
        by_cat[k].sort(key=lambda p: p["id"])

    WORK.mkdir(parents=True, exist_ok=True)
    # 工作块包含未入库成果；重建队列不得删除或改写它们。
    if any(WORK.glob("in-*.json")) or any(WORK.glob("out-*.json")):
        raise SystemExit(
            "已有工作块，已拒绝覆盖。请使用 enrichment_pipeline.py prepare "
            "创建支持断点恢复的新队列。"
        )

    chunk_no = 0
    for cat in CAT_ORDER:
        items = by_cat.get(cat, [])
        for i in range(0, len(items), CHUNK_SIZE):
            slice_ = items[i:i + CHUNK_SIZE]
            poems_out = []
            for p in slice_:
                missing = sorted({c for c in p["content"] if "一" <= c <= "鿿"} - dict_chars)
                poems_out.append(dict(
                    id=p["id"], title=p["title"], subtitle=p.get("subtitle", ""),
                    author=p["author"], dynasty=p["dynasty"],
                    excerptOf=p.get("excerptOf"), excerptNote=p.get("excerptNote", ""),
                    content=p["content"], missingChars=missing))
            chunk_no += 1
            out = dict(chunk=chunk_no, category=cat, tagEnum=tag_map[cat], poems=poems_out)
            (WORK / f"in-{chunk_no:03d}.json").write_text(
                json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{chunk_no} chunks -> {WORK} (共 {len(pending)} 首待补)")


if __name__ == "__main__":
    main()
