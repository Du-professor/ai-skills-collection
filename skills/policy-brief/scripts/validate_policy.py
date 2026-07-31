#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
validate_policy.py — 校验政策解读模型输出的结构化 JSON。

唯一规则来源：references/policy-rubric.md / references/output-contract.md
本文件顶部常量须与 rubric 保持一致。

用法：
  python validate_policy.py --mode summary < input.json
  python validate_policy.py --input data.json          # mode 取自 data["mode"]
  cat data.json | python validate_policy.py

退出码：
  0  校验通过
  2  需重试（结构/字段错误，stderr 输出字段级错误，供模型重试 ≤2 次）
  1  致命（无法读取输入 / JSON 解析失败 / 空输入）
"""
import sys
import json
import argparse

# ── 与 references/policy-rubric.md 同步的常量 ──────────────────────────────
MODES = {"summary", "extract", "compare", "qa"}
SUMMARY_SECTIONS = {"background", "targets", "measures", "support", "timeline", "impact"}
KEYPOINT_CATEGORIES = {
    "fiscal_subsidy", "tax_pref", "reg_compliance", "approval_flow",
    "support_target", "time_limit", "penalty", "other",
}
COMPARE_DIMENSIONS = {
    "target", "support_strength", "threshold", "timeline",
    "region", "authority", "diff",
}
# POLICY_DOMAINS 仅 store 使用，校验不强制。


def _err(msg, errors):
    errors.append(msg)


def _is_str(v):
    return isinstance(v, str) and v.strip() != ""


def _load_input(args):
    try:
        if args.input:
            with open(args.input, "r", encoding="utf-8") as f:
                raw = f.read()
        else:
            raw = sys.stdin.read()
    except Exception as e:  # noqa: BLE001
        print(f"FATAL: 无法读取输入: {e}", file=sys.stderr)
        sys.exit(1)
    if not raw or raw.strip() == "":
        print("FATAL: 输入为空", file=sys.stderr)
        sys.exit(1)
    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"FATAL: JSON 解析失败: {e}", file=sys.stderr)
        sys.exit(1)


def validate_summary(data, errors):
    if not _is_str(data.get("title")):
        _err("summary.title 必须为非空字符串", errors)
    for opt in ("issued_by", "issued_date"):
        if opt in data and not _is_str(data.get(opt)):
            _err(f"summary.{opt} 若存在必须为非空字符串", errors)
    sections = data.get("sections")
    if not isinstance(sections, list) or len(sections) == 0:
        _err("summary.sections 必须为非空数组", errors)
        return
    seen = set()
    for i, s in enumerate(sections):
        if not isinstance(s, dict):
            _err(f"summary.sections[{i}] 必须为对象", errors)
            continue
        key = s.get("key")
        if key not in SUMMARY_SECTIONS:
            _err(f"summary.sections[{i}].key 非法: {key!r}（须为 {sorted(SUMMARY_SECTIONS)}）", errors)
        else:
            seen.add(key)
        if not _is_str(s.get("heading")):
            _err(f"summary.sections[{i}].heading 必须为非空字符串", errors)
        if not _is_str(s.get("content")):
            _err(f"summary.sections[{i}].content 必须为非空字符串", errors)
    missing = SUMMARY_SECTIONS - seen
    if missing:
        _err(f"summary.sections 缺少必填段落: {sorted(missing)}", errors)
    refs = data.get("source_refs")
    if refs is not None and (not isinstance(refs, list) or not all(_is_str(r) for r in refs)):
        _err("summary.source_refs 若存在必须为字符串数组", errors)


def validate_extract(data, errors):
    if not _is_str(data.get("title")):
        _err("extract.title 必须为非空字符串", errors)
    categories = data.get("categories")
    if not isinstance(categories, list) or len(categories) == 0:
        _err("extract.categories 必须为非空数组", errors)
        return
    total = 0
    for i, c in enumerate(categories):
        if not isinstance(c, dict):
            _err(f"extract.categories[{i}] 必须为对象", errors)
            continue
        cat = c.get("category")
        if cat not in KEYPOINT_CATEGORIES:
            _err(f"extract.categories[{i}].category 非法: {cat!r}（须为 {sorted(KEYPOINT_CATEGORIES)}）", errors)
        if not _is_str(c.get("label")):
            _err(f"extract.categories[{i}].label 必须为非空字符串", errors)
        points = c.get("points")
        if not isinstance(points, list) or len(points) == 0:
            _err(f"extract.categories[{i}].points 必须为非空数组", errors)
            continue
        for j, p in enumerate(points):
            if not isinstance(p, dict):
                _err(f"extract.categories[{i}].points[{j}] 必须为对象", errors)
                continue
            if not _is_str(p.get("point")):
                _err(f"extract.categories[{i}].points[{j}].point 必须为非空字符串", errors)
            if not _is_str(p.get("quote")):
                _err(f"extract.categories[{i}].points[{j}].quote 必须为非空字符串（须为原文逐字）", errors)
            if not _is_str(p.get("location")):
                _err(f"extract.categories[{i}].points[{j}].location 必须为非空字符串", errors)
            total += 1
    tp = data.get("total_points")
    if not isinstance(tp, int) or tp != total:
        _err(f"extract.total_points 须为整数且等于要点总数（期望 {total}，实际 {tp!r}）", errors)


def validate_compare(data, errors):
    policies = data.get("policies")
    if not isinstance(policies, list) or len(policies) < 2:
        _err("compare.policies 必须为长度 ≥2 的数组", errors)
        return
    ids = []
    for i, p in enumerate(policies):
        if not isinstance(p, dict):
            _err(f"compare.policies[{i}] 必须为对象", errors)
            continue
        pid = p.get("id")
        if not _is_str(pid):
            _err(f"compare.policies[{i}].id 必须为非空字符串", errors)
            continue
        if pid in ids:
            _err(f"compare.policies 存在重复 id: {pid!r}", errors)
        ids.append(pid)
        if not _is_str(p.get("title")):
            _err(f"compare.policies[{i}].title 必须为非空字符串", errors)
    if not ids:
        return
    dimensions = data.get("dimensions")
    if not isinstance(dimensions, list) or len(dimensions) == 0:
        _err("compare.dimensions 必须为非空数组", errors)
        return
    for i, d in enumerate(dimensions):
        if not isinstance(d, dict):
            _err(f"compare.dimensions[{i}] 必须为对象", errors)
            continue
        dim = d.get("dimension")
        if dim not in COMPARE_DIMENSIONS:
            _err(f"compare.dimensions[{i}].dimension 非法: {dim!r}（须为 {sorted(COMPARE_DIMENSIONS)}）", errors)
        if not _is_str(d.get("label")):
            _err(f"compare.dimensions[{i}].label 必须为非空字符串", errors)
        rows = d.get("rows")
        if not isinstance(rows, list) or len(rows) == 0:
            _err(f"compare.dimensions[{i}].rows 必须为非空数组", errors)
            continue
        row_pids = set()
        for j, r in enumerate(rows):
            if not isinstance(r, dict):
                _err(f"compare.dimensions[{i}].rows[{j}] 必须为对象", errors)
                continue
            rpid = r.get("policy_id")
            if rpid not in ids:
                _err(f"compare.dimensions[{i}].rows[{j}].policy_id 须匹配 policies[].id（{rpid!r}）", errors)
            else:
                row_pids.add(rpid)
            if not _is_str(r.get("value")):
                _err(f"compare.dimensions[{i}].rows[{j}].value 必须为非空字符串", errors)
        missing_rows = set(ids) - row_pids
        if missing_rows:
            _err(f"compare.dimensions[{i}] 缺少政策行: {sorted(missing_rows)}", errors)
    if not _is_str(data.get("diff_summary")):
        _err("compare.diff_summary 必须为非空字符串", errors)
    rec = data.get("recommendation")
    if rec is not None and not _is_str(rec):
        _err("compare.recommendation 若存在必须为字符串", errors)


def validate_qa(data, errors):
    pairs = data.get("qa_pairs")
    if not isinstance(pairs, list) or len(pairs) == 0:
        _err("qa.qa_pairs 必须为非空数组", errors)
        return
    for i, q in enumerate(pairs):
        if not isinstance(q, dict):
            _err(f"qa.qa_pairs[{i}] 必须为对象", errors)
            continue
        if not _is_str(q.get("question")):
            _err(f"qa.qa_pairs[{i}].question 必须为非空字符串", errors)
        ans = q.get("answer")
        if not _is_str(ans):
            _err(f"qa.qa_pairs[{i}].answer 必须为非空字符串", errors)
            continue
        cites = q.get("citations")
        if not isinstance(cites, list):
            _err(f"qa.qa_pairs[{i}].citations 必须为数组", errors)
            continue
        if ans.strip() == "原文未提及":
            if len(cites) != 0:
                _err(f"qa.qa_pairs[{i}] answer 为「原文未提及」时 citations 必须为空数组", errors)
        else:
            if len(cites) == 0:
                _err(f"qa.qa_pairs[{i}] answer 非「原文未提及」时 citations 必须非空", errors)
            for j, c in enumerate(cites):
                if not isinstance(c, dict):
                    _err(f"qa.qa_pairs[{i}].citations[{j}] 必须为对象", errors)
                    continue
                if not _is_str(c.get("quote")):
                    _err(f"qa.qa_pairs[{i}].citations[{j}].quote 必须为非空字符串", errors)
                if not _is_str(c.get("location")):
                    _err(f"qa.qa_pairs[{i}].citations[{j}].location 必须为非空字符串", errors)


VALIDATORS = {
    "summary": validate_summary,
    "extract": validate_extract,
    "compare": validate_compare,
    "qa": validate_qa,
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--mode", choices=sorted(MODES), default=None)
    ap.add_argument("--input", default=None, help="JSON 文件路径；缺省读 stdin")
    args = ap.parse_args()

    data = _load_input(args)
    if not isinstance(data, dict):
        print("FATAL: 顶层 JSON 必须为对象", file=sys.stderr)
        sys.exit(1)

    mode = args.mode or data.get("mode")
    if mode not in MODES:
        print(f"FATAL: 无法确定合法 mode（得到 {mode!r}）", file=sys.stderr)
        sys.exit(1)

    errors = []
    VALIDATORS[mode](data, errors)

    if errors:
        print(f"校验失败（mode={mode}），共 {len(errors)} 处：", file=sys.stderr)
        for e in errors:
            print(f"  - {e}", file=sys.stderr)
        sys.exit(2)
    print(f"OK: mode={mode} 校验通过")
    sys.exit(0)


if __name__ == "__main__":
    main()
