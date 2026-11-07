# -*- coding: utf-8 -*-
"""把一组已校验的 out-NNN.json 合并为一个 enrichment 批次并应用。

用法: python scripts/merge_wave.py --batch 011 --poems 1.1.7 --dict 1.1.5 001 002 ...
之后自动跑 apply_enrichment_batch.py 与 export_pending_enrichment.py。
"""
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORK = ROOT / "expansion" / "working" / "chunks"
ENR = ROOT / "expansion" / "enrichment"
POLICY = ("独立编写全文译文和重点注释；保留原ID、作者、正文、来源及停用关系。"
          "逐篇全部通过数据要求后再解除original_only。")


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    args = sys.argv[1:]
    batch_no, poems_ver, dict_ver, nums = None, None, None, []
    i = 0
    while i < len(args):
        if args[i] == "--batch":
            batch_no, i = args[i + 1], i + 2
        elif args[i] == "--poems":
            poems_ver, i = args[i + 1], i + 2
        elif args[i] == "--dict":
            dict_ver, i = args[i + 1], i + 2
        else:
            nums.append(args[i]); i += 1
    if not batch_no or not poems_ver or not dict_ver or not nums:
        print(__doc__); sys.exit(2)

    patches, additions = [], {}
    for n in nums:
        out = json.loads((WORK / f"out-{n}.json").read_text(encoding="utf-8"))
        patches.extend(out["patches"])
        for ch, e in out.get("dictionaryAdditions", {}).items():
            if ch in additions and additions[ch] != e:
                raise ValueError(f"字典字 {ch} 在多个块中释义冲突")
            additions[ch] = e
    ids = [p["id"] for p in patches]
    if len(ids) != len(set(ids)):
        raise ValueError("合并后 id 重复")
    batch = dict(dataVersion=poems_ver, dictionaryVersion=dict_ver, policy=POLICY,
                 patches=patches, dictionaryAdditions=additions)
    out_path = ENR / f"{batch_no}.json"
    out_path.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"合并 {len(patches)} patches / {len(additions)} 缺字 -> {out_path.name}")

    for cmd in (["apply_enrichment_batch.py", str(out_path)],
                ["export_pending_enrichment.py"]):
        r = subprocess.run([sys.executable, str(ROOT / "scripts" / cmd[0]), *cmd[1:]],
                           capture_output=True, text=True, encoding="utf-8")
        print(r.stdout)
        if r.stderr.strip():
            print(r.stderr)
        if r.returncode != 0:
            print(f"❌ {cmd[0]} 失败, 退出码 {r.returncode}")
            sys.exit(1)
    print(f"✅ 批次 {batch_no} 已应用（poems {poems_ver} / dict {dict_ver}）")


if __name__ == "__main__":
    main()
