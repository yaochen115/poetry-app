# -*- coding: utf-8 -*-
"""
「红妆」数据校验脚本
用法: python scripts/validate_data.py [--scan-chars]
  - 默认: 校验 data/poems.json、data/categories.json；若 dict.json 存在则一并校验覆盖度
  - --scan-chars: 扫描全部正文用字, 输出到 scripts/unique_chars.txt
退出码: 0 通过；1 存在错误
"""
import json
import argparse
import re
import sys
from collections import Counter
from pathlib import Path
from data_scope import active_items
from translation_overlay_v1_0_0 import overlay_for

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
CATS = ("唐诗", "宋词", "元曲", "古文")
ID_RE = re.compile(r"^(tang|song|yuan|guwen)-\d{3,4}$")
EXPECTED_PER_CATEGORY = 1050
EXPECTED_COUNTS = None
ORIGINAL_ONLY_MODE = False

errors = []


def fail(msg: str):
    errors.append(msg)


def load(name: str):
    fp = DATA / name
    if not fp.exists():
        fail(f"缺少文件 {name}")
        return None
    try:
        return json.loads(fp.read_text(encoding="utf-8"))
    except Exception as e:
        fail(f"{name} JSON 解析失败: {e}")
        return None


def check_categories(c: dict):
    if c is None:
        return {}
    if c.get("dataVersion") != "1.0.0":
        fail("categories.json dataVersion 应为 1.0.0")
    cats = c.get("categories", [])
    keys = [x.get("key") for x in cats]
    if set(keys) != set(CATS):
        fail(f"categories 键应为 {set(CATS)}, 实际 {set(keys)}")
    tag_map = {}
    for x in cats:
        if x.get("label") != x.get("key"):
            fail(f"类别 {x.get('key')} label 与 key 不一致")
        tags = x.get("tags", [])
        tag_map[x["key"]] = set(tags)
        if len(tags) != len(set(tags)):
            fail(f"类别 {x['key']} tags 有重复")
    for k, v in tag_map.items():
        if not v:
            fail(f"类别 {k} 无标签")
    return tag_map


def check_poems(p: dict, tag_map: dict):
    if p is None:
        return
    if not re.fullmatch(r'\d+\.\d+\.\d+', str(p.get('dataVersion', ''))):
        fail('poems.json dataVersion 格式错误')
    items = p.get("items", [])
    expected = EXPECTED_COUNTS or dict.fromkeys(CATS, EXPECTED_PER_CATEGORY)
    if len(items) != sum(expected.values()):
        fail(f"poems.json 应为 {sum(expected.values())} 首, 实际 {len(items)}")
    ids = [str(i.get("id")) for i in items]
    for k, v in Counter(ids).items():
        if v > 1:
            fail(f"id 重复: {k}")
    by_cat = Counter()
    for idx, it in enumerate(items):
        iid = str(it.get("id", f"<第{idx}条>"))
        if not ID_RE.fullmatch(iid):
            fail(f"{iid}: id 格式应为 体裁-三或四位序号")
        cat = it.get("category")
        if not ORIGINAL_ONLY_MODE and any(0xe000<=ord(ch)<=0xf8ff for ch in it.get('content','')):
            fail(f'{iid}: 来源含私用区字形编码，完整验收前须完成原文校勘')
        by_cat[cat] += 1
        if cat not in CATS:
            fail(f"{iid}: category 非法: {cat}")
            continue
        tags = it.get("tags", [])
        original_only = it.get('editorialStatus') == 'original_only'
        if original_only and not ORIGINAL_ONLY_MODE:
            fail(f'{iid}: 原文阶段篇目尚未补齐译注，不能通过完整验收')
        if not isinstance(tags, list) or (not tags and not (ORIGINAL_ONLY_MODE and original_only)):
            fail(f"{iid}: tags 不能为空")
        for t in tags:
            if t not in tag_map.get(cat, set()):
                fail(f"{iid}: 标签 {t} 不在 {cat} 枚举中")
        fields = ('title', 'author', 'dynasty', 'content') if ORIGINAL_ONLY_MODE and original_only else ('title', 'author', 'dynasty', 'content', 'translation')
        for field in fields:
            if not str(it.get(field, "")).strip():
                fail(f"{iid}: 字段 {field} 为空")
        if not isinstance(it.get("subtitle", None), str):
            fail(f"{iid}: subtitle 应为字符串")
        if "excerptOf" not in it:
            fail(f"{iid}: 缺少 excerptOf 字段")
        elif it["excerptOf"] is not None and not isinstance(it["excerptOf"], str):
            fail(f"{iid}: excerptOf 应为 null 或字符串")
        if not isinstance(it.get("excerptNote", None), str):
            fail(f"{iid}: excerptNote 应为字符串")
        notes = it.get("notes", [])
        if original_only and ORIGINAL_ONLY_MODE:
            if it.get('translation') != '' or notes != []:
                fail(f'{iid}: 原文阶段条目应明确留空译注，已完成时应更新状态')
            if set(it.get('pending', [])) != {'translation', 'notes', 'themeTags', 'dictionary'}:
                fail(f'{iid}: 原文阶段待补项目不完整')
        elif not isinstance(notes, list) or not 3 <= len(notes) <= 18:
            fail(f"{iid}: notes 数量 {len(notes) if isinstance(notes, list) else '非列表'} 应在 3~18 条")
        for n in notes:
            if not str(n.get("term", "")).strip() or not str(n.get("meaning", "")).strip():
                fail(f"{iid}: 存在空注释条目")
    for c, expect in expected.items():
        if by_cat[c] != expect:
            fail(f"{c} 应有 {expect} 首, 实际 {by_cat[c]}")


def unique_chars(p: dict):
    chars = set()
    for it in p["items"]:
        for ch in it["content"]:
            if ch.strip() and ("\u4e00" <= ch <= "\u9fff" or ch == "\u3007"):
                chars.add(ch)
    return sorted(chars)


def check_dict(d: dict, all_chars: set):
    if d is None:
        return
    if not re.fullmatch(r'\d+\.\d+\.\d+', str(d.get('dataVersion', ''))):
        fail('dict.json dataVersion 格式错误')
    for ch, entry in d.get('chars', {}).items():
        if not entry.get('pinyin') or not (entry.get('meanings') or entry.get('ancient')):
            fail(f'字典 {ch}: 缺少拼音或释义')
    chars = set(d.get("chars", {}).keys())
    missing = set(all_chars) - chars
    if missing:
        fail(f"dict.json 缺字 {len(missing)} 个: {''.join(sorted(missing))}")
    else:
        print(f"dict.json 覆盖全部 {len(all_chars)} 个用字 ✅")


def scan_chars(p: dict):
    out = unique_chars(p)
    fp = ROOT / "scripts" / "unique_chars.txt"
    fp.write_text("".join(out), encoding="utf-8")
    print(f"共 {len(out)} 个用字, 已写入 {fp}")


def main():
    global EXPECTED_PER_CATEGORY, ORIGINAL_ONLY_MODE, EXPECTED_COUNTS
    parser = argparse.ArgumentParser()
    parser.add_argument('--scan-chars', action='store_true')
    parser.add_argument('--original-only', action='store_true',
                        help='仅用于负责人批准的原文阶段，不代表完整译注验收')
    parser.add_argument('--expected-per-category', type=int, default=1050,
                        help='分批验收时指定当前每类篇数；默认最终目标 1050')
    args = parser.parse_args()
    if args.expected_per_category < 1:
        parser.error('每类篇数必须大于零')
    EXPECTED_PER_CATEGORY = args.expected_per_category
    ORIGINAL_ONLY_MODE = args.original_only
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    scan = args.scan_chars
    cats = load("categories.json")
    tag_map = check_categories(cats)
    poems = load("poems.json")
    if poems is not None:
        if poems.get('selectionProfile'):
            EXPECTED_COUNTS = poems['selectionProfile']['expectedCounts']
        stored_total=len(poems['items'])
        poems=dict(poems,items=active_items(poems))
        if stored_total != len(poems['items']):
            print(f'保存 {stored_total} 条，可用 {len(poems["items"])} 条；停用条目不计入可用库验收')
        if scan:
            scan_chars(poems)
        check_poems(poems, tag_map)
        for it in poems['items']:
            if it['id'] not in poems.get('translationImports', {}): continue
            extra=overlay_for(poems,it)
            if not extra:
                fail(f'{it["id"]}: stale or invalid imported translation')
                continue
            if extra.get('literaryApproved') is not False or not extra.get('pending'):
                fail(f'{it["id"]}: partial imports must preserve review/pending markers')
        if ORIGINAL_ONLY_MODE:
            glyph_issues = sum(any(0xe000<=ord(ch)<=0xf8ff for ch in p.get('content','')) for p in poems['items'])
            if glyph_issues:
                print(f'保留旧来源编码待校勘 {glyph_issues} 篇，详见 source-review-issues.json；完整验收仍会拒绝这些条目')
        if (DATA / "dict.json").exists():
            complete = dict(poems, items=[p for p in poems['items'] if p.get('editorialStatus') != 'original_only'])
            if ORIGINAL_ONLY_MODE:
                print(f"字典仅核验已完成译注的 {len(complete['items'])} 篇；原文阶段新增字词仍待补齐")
            check_dict(load("dict.json"), unique_chars(complete if ORIGINAL_ONLY_MODE else poems))
    else:
        fail("poems.json 无法加载, 跳过详细校验")
    print("=" * 40)
    if errors:
        for e in errors:
            print("[错误]", e)
        print(f"共 {len(errors)} 个错误 ❌")
        sys.exit(1)
    print('原文阶段校验通过（译注、主题标签及新增字词典仍待补齐） ✅' if ORIGINAL_ONLY_MODE else "全部校验通过 ✅")


if __name__ == "__main__":
    main()
