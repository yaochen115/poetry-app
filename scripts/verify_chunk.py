# -*- coding: utf-8 -*-
"""校验单个 agent 输出块 out-NNN.json 是否符合批次格式（对照 in-NNN.json）。"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "expansion" / "working" / "chunks"
PLACEHOLDERS = ("待补", "（译文略", "（略）", "原文见", "省略", "同原文", "待译", "暂无")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    n = sys.argv[1]
    inpath = WORK / f"in-{n}.json"
    outpath = WORK / f"out-{n}.json"
    if not outpath.exists():
        print(f"out-{n}.json 缺失"); sys.exit(1)
    try:
        out = json.loads(outpath.read_text(encoding="utf-8"))
    except Exception as e:
        print(f"out-{n}.json JSON 解析失败: {e}"); sys.exit(1)
    errors = []
    inp = json.loads(inpath.read_text(encoding="utf-8"))
    want_ids = [p["id"] for p in inp["poems"]]
    enum = set(inp["tagEnum"])
    missing_chars = {c for p in inp["poems"] for c in p["missingChars"]}

    patches = out.get("patches")
    if not isinstance(patches, list) or not patches:
        errors.append("patches 缺失或为空"); patches = []
    got_ids = [str(p.get("id")) for p in patches]
    if len(got_ids) != len(set(got_ids)):
        errors.append("patches id 有重复")
    if set(got_ids) != set(want_ids):
        errors.append(f"id 集合不符: 缺 {sorted(set(want_ids)-set(got_ids))[:10]} 多 {sorted(set(got_ids)-set(want_ids))[:10]}")

    add = out.get("dictionaryAdditions")
    if not isinstance(add, dict):
        errors.append("dictionaryAdditions 缺失或非对象")
    else:
        need = missing_chars - set(add)
        if need:
            errors.append(f"dictionaryAdditions 缺字 {len(need)}: {sorted(need)[:40]}")
        extra = set(add) - missing_chars
        if extra:
            errors.append(f"dictionaryAdditions 多余字 {len(extra)}: {sorted(extra)[:20]}")
        for ch, e in add.items():
            if not isinstance(e, dict) or not e.get("meanings") or not e.get("ancient"):
                errors.append(f"字典 {ch}: 缺少 meanings/ancient")

    for p in patches:
        pid = str(p.get("id"))
        if set(p) != {"id", "translation", "notes", "tags"}:
            errors.append(f"{pid}: 字段须仅含 id/translation/notes/tags, 实际 {sorted(p)}")
            continue
        t = p.get("translation")
        if not isinstance(t, str) or not t.strip():
            errors.append(f"{pid}: translation 空"); continue
        if len(t.strip()) < 8 or any(x in t for x in PLACEHOLDERS):
            errors.append(f"{pid}: translation 疑似占位/过短")
        notes = p.get("notes")
        if not isinstance(notes, list) or not 3 <= len(notes) <= 18:
            errors.append(f"{pid}: notes 数量 {len(notes) if isinstance(notes, list) else type(notes)} 应在 3~18")
        else:
            for nd in notes:
                if not isinstance(nd, dict) or not str(nd.get("term", "")).strip() or not str(nd.get("meaning", "")).strip():
                    errors.append(f"{pid}: 存在空注释条目"); break
            for nd in notes:
                term = str(nd.get("term", "")).strip()
                if len(term) == 2 and term not in p.get("translation", "") and not any(term in x["content"] for x in inp["poems"] if x["id"] == pid):
                    pass  # term 不必在正文，仅提示词库收录以正文双字词为准
        tags = p.get("tags")
        if not isinstance(tags, list) or not tags or any(t not in enum for t in tags):
            errors.append(f"{pid}: tags 非法 {tags} (枚举: {sorted(enum)})")

    if errors:
        print(f"out-{n}.json ❌ {len(errors)} 个问题:")
        for e in errors[:40]:
            print(" -", e)
        sys.exit(1)
    print(f"out-{n}.json ✅ {len(patches)} patches, 缺字 {len(missing_chars)} 已补")


if __name__ == "__main__":
    main()
