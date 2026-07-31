#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""职配雷达 · 确定性匹配算分脚本。

规则唯一来源: references/scoring-rubric.md。本脚本只依据输入证据 JSON 中的
status / strength / relevance 枚举与固定公式计算分数, 不做任何语义判断。

用法:
    python calculate_match_score.py evidence.json [--resume-text resume.txt] [--jd-text jd.txt]

退出码:
    0  成功, stdout 输出结果 JSON
    2  输入校验失败, stderr 逐行输出字段级错误清单
    1  运行错误 (文件不可读 / JSON 解析失败)

确定性保证: 无随机数、无时间戳、输出按键名排序; 同一输入多次运行字节级一致。
仅使用 Python 标准库。
"""

import argparse
import json
import sys

if sys.platform == "win32":
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

SCHEMA_VERSION = "1.0"

COVERAGE = {"met": 1.0, "weak_expression": 0.6, "gap": 0.0, "unknown": 0.0}
STRENGTH = {"strong": 1.0, "medium": 0.6, "weak": 0.3}
RELEVANCE = {"high": 1.0, "medium": 0.6, "low": 0.2}
CATEGORIES = {"skill", "experience", "education", "cert", "other"}
REQ_TYPES = {"must", "plus"}
JD_SOURCES = {"text", "link"}
ATS_KEYS = (
    "has_text_layer", "encoding_ok", "has_contact",
    "has_education", "has_dates", "uses_complex_tables",
)

# 模型禁止输出的分数字段 (键名, 小写精确匹配)
FORBIDDEN_SCORE_KEYS = {
    "score", "scores", "total", "total_score", "points", "grade",
    "rating", "stars", "confidence", "verdict", "verdict_band", "dimensions",
}


def normalize_ws(text):
    """去除全部空白字符, 用于跨行/空差容忍的包含性校验。"""
    return "".join(str(text).split())


def find_forbidden_keys(node, path, errors):
    """递归检查输入中是否混入模型私加的分数字段。"""
    if isinstance(node, dict):
        for key, value in node.items():
            if str(key).lower() in FORBIDDEN_SCORE_KEYS:
                errors.append(f"{path or '$'}: 禁止出现分数字段 '{key}' (分数只能由脚本计算)")
            find_forbidden_keys(value, f"{path}.{key}", errors)
    elif isinstance(node, list):
        for index, item in enumerate(node):
            find_forbidden_keys(item, f"{path}[{index}]", errors)


def is_str(value):
    return isinstance(value, str)


def validate(data, errors):
    """结构与枚举校验, 全部错误收集到 errors (字段级路径)。"""
    if not isinstance(data, dict):
        errors.append("$: 顶层必须是 JSON 对象")
        return

    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"$.schema_version: 必须等于 \"{SCHEMA_VERSION}\"")

    jd = data.get("jd")
    if not isinstance(jd, dict):
        errors.append("$.jd: 缺失或不是对象")
    else:
        if not is_str(jd.get("title")) or not jd.get("title").strip():
            errors.append("$.jd.title: 缺失或不是非空字符串")
        if jd.get("source") not in JD_SOURCES:
            errors.append("$.jd.source: 必须是 text 或 link")

    reqs = data.get("requirements")
    if not isinstance(reqs, list):
        errors.append("$.requirements: 缺失或不是数组")
        reqs = []

    req_ids = set()
    for i, req in enumerate(reqs):
        p = f"$.requirements[{i}]"
        if not isinstance(req, dict):
            errors.append(f"{p}: 必须是对象")
            continue
        rid = req.get("requirement_id")
        if not is_str(rid) or not rid.strip():
            errors.append(f"{p}.requirement_id: 缺失或不是非空字符串")
        elif rid in req_ids:
            errors.append(f"{p}.requirement_id: '{rid}' 重复")
        else:
            req_ids.add(rid)
        if req.get("category") not in CATEGORIES:
            errors.append(f"{p}.category: 非法取值 {req.get('category')!r}")
        if req.get("type") not in REQ_TYPES:
            errors.append(f"{p}.type: 必须是 must 或 plus")
        if not is_str(req.get("jd_quote")) or not req.get("jd_quote").strip():
            errors.append(f"{p}.jd_quote: 缺失或不是非空字符串")
        status = req.get("status")
        if status not in COVERAGE:
            errors.append(f"{p}.status: 非法取值 {status!r}")
        if "note" in req and not is_str(req.get("note")):
            errors.append(f"{p}.note: 必须是字符串")
        evidence = req.get("evidence")
        if not isinstance(evidence, list):
            errors.append(f"{p}.evidence: 缺失或不是数组")
            continue
        if status in ("met", "weak_expression") and len(evidence) == 0:
            errors.append(f"{p}.evidence: status={status} 时至少 1 条证据")
        if status in ("gap", "unknown") and len(evidence) > 0:
            errors.append(f"{p}.evidence: status={status} 时证据必须为空数组")
        for j, ev in enumerate(evidence):
            ep = f"{p}.evidence[{j}]"
            if not isinstance(ev, dict):
                errors.append(f"{ep}: 必须是对象")
                continue
            if not is_str(ev.get("resume_section")) or not ev.get("resume_section").strip():
                errors.append(f"{ep}.resume_section: 缺失或不是非空字符串")
            if not is_str(ev.get("quote")) or not ev.get("quote").strip():
                errors.append(f"{ep}.quote: 缺失或不是非空字符串")
            if ev.get("strength") not in STRENGTH:
                errors.append(f"{ep}.strength: 非法取值 {ev.get('strength')!r}")

    projects = data.get("projects")
    if not isinstance(projects, list):
        errors.append("$.projects: 缺失或不是数组")
        projects = []
    for i, proj in enumerate(projects):
        p = f"$.projects[{i}]"
        if not isinstance(proj, dict):
            errors.append(f"{p}: 必须是对象")
            continue
        if not is_str(proj.get("project_id")) or not proj.get("project_id").strip():
            errors.append(f"{p}.project_id: 缺失或不是非空字符串")
        if not is_str(proj.get("title")) or not proj.get("title").strip():
            errors.append(f"{p}.title: 缺失或不是非空字符串")
        if proj.get("relevance") not in RELEVANCE:
            errors.append(f"{p}.relevance: 非法取值 {proj.get('relevance')!r}")
        matched = proj.get("matched_requirements")
        if not isinstance(matched, list) or not all(is_str(m) for m in matched):
            errors.append(f"{p}.matched_requirements: 缺失或不是字符串数组")
        else:
            for m in matched:
                if m not in req_ids:
                    errors.append(f"{p}.matched_requirements: 引用了不存在的 requirement_id '{m}'")

    ats = data.get("ats_checklist")
    if not isinstance(ats, dict):
        errors.append("$.ats_checklist: 缺失或不是对象")
    else:
        for key in ATS_KEYS:
            if not isinstance(ats.get(key), bool):
                errors.append(f"$.ats_checklist.{key}: 缺失或不是布尔值")

    sensitive = data.get("sensitive_removed")
    if not isinstance(sensitive, list) or not all(is_str(s) for s in sensitive):
        errors.append("$.sensitive_removed: 缺失或不是字符串数组")


def validate_quotes(data, resume_text, jd_text, errors):
    """逐字包含性校验 (对空白差异容忍, 见 normalize_ws)。"""
    resume_norm = normalize_ws(resume_text) if resume_text is not None else None
    jd_norm = normalize_ws(jd_text) if jd_text is not None else None
    for i, req in enumerate(data.get("requirements", [])):
        if not isinstance(req, dict):
            continue
        if jd_norm is not None and is_str(req.get("jd_quote")):
            if normalize_ws(req["jd_quote"]) not in jd_norm:
                errors.append(
                    f"$.requirements[{i}].jd_quote: 未在 JD 原文中找到逐字出处: "
                    f"{req['jd_quote'][:30]!r}...")
        for j, ev in enumerate(req.get("evidence") or []):
            if resume_norm is not None and isinstance(ev, dict) and is_str(ev.get("quote")):
                if normalize_ws(ev["quote"]) not in resume_norm:
                    errors.append(
                        f"$.requirements[{i}].evidence[{j}].quote: 未在简历原文中找到逐字出处: "
                        f"{ev['quote'][:30]!r}...")


def calculate(data):
    """按 scoring-rubric 固定公式计算, 返回结果 dict。"""
    reqs = data["requirements"]
    n_req = len(reqs)
    musts = [r for r in reqs if r["type"] == "must"]
    n_must = len(musts)

    d1 = 0.0 if n_must == 0 else 35.0 * sum(COVERAGE[r["status"]] for r in musts) / n_must

    skills = [r for r in reqs if r["category"] == "skill"]
    weights = [1.0 if r["type"] == "must" else 0.5 for r in skills]
    d2 = 0.0 if not skills else (
        20.0 * sum(w * COVERAGE[r["status"]] for w, r in zip(weights, skills)) / sum(weights)
    )

    rels = sorted((RELEVANCE[p["relevance"]] for p in data["projects"]), reverse=True)
    d3 = 0.0 if not rels else 20.0 * (sum(rels[:3]) / len(rels[:3]))

    strengths = [
        STRENGTH[ev["strength"]]
        for r in reqs for ev in r["evidence"]
    ]
    d4 = 0.0 if not strengths else 15.0 * (sum(strengths) / len(strengths))

    ats = data["ats_checklist"]
    passed = sum([
        ats["has_text_layer"], ats["encoding_ok"], ats["has_contact"],
        ats["has_education"], ats["has_dates"], not ats["uses_complex_tables"],
    ])
    d5 = 10.0 * passed / 6.0

    total = round(d1 + d2 + d3 + d4 + d5, 1)

    if n_req == 0:
        confidence = 10
        unknown_ratio = 1.0
    else:
        n_unknown = sum(1 for r in reqs if r["status"] == "unknown")
        n_weak_only = sum(
            1 for r in reqs
            if r["status"] in ("met", "weak_expression")
            and all(ev["strength"] == "weak" for ev in r["evidence"])
        )
        unknown_ratio = n_unknown / n_req
        confidence = max(10, round(
            100
            - 50 * unknown_ratio
            - 30 * (n_weak_only / n_req)
            - 20 * (0 if ats["has_text_layer"] else 1)
        ))

    if n_req == 0 or n_must == 0 or unknown_ratio >= 0.4:
        verdict = "信息不足"
    elif total >= 75:
        verdict = "高匹配"
    elif total >= 60:
        verdict = "中匹配"
    elif total >= 40:
        verdict = "部分匹配"
    else:
        verdict = "低匹配"

    status_counts = {key: 0 for key in COVERAGE}
    for r in reqs:
        status_counts[r["status"]] += 1

    return {
        "total_score": total,
        "confidence": confidence,
        "verdict_band": verdict,
        "dimensions": {
            "D1": round(d1, 2), "D2": round(d2, 2), "D3": round(d3, 2),
            "D4": round(d4, 2), "D5": round(d5, 2),
        },
        "status_counts": status_counts,
        "calculation_mode": "script",
        "warnings": [],
    }


def main():
    parser = argparse.ArgumentParser(description="职配雷达确定性算分 (规则: references/scoring-rubric.md)")
    parser.add_argument("evidence_json", help="匹配证据 JSON 文件路径")
    parser.add_argument("--resume-text", help="简历提取纯文本文件 (可选, 用于 quote 逐字校验)")
    parser.add_argument("--jd-text", help="JD 纯文本文件 (可选, 用于 jd_quote 逐字校验)")
    args = parser.parse_args()

    try:
        with open(args.evidence_json, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"运行错误: 无法读取或解析证据 JSON: {exc}", file=sys.stderr)
        sys.exit(1)

    def read_text(path):
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return fh.read()
        except OSError as exc:
            print(f"运行错误: 无法读取原文文件 {path}: {exc}", file=sys.stderr)
            sys.exit(1)

    resume_text = read_text(args.resume_text) if args.resume_text else None
    jd_text = read_text(args.jd_text) if args.jd_text else None

    errors = []
    find_forbidden_keys(data, "$", errors)
    validate(data, errors)
    if not errors and (resume_text is not None or jd_text is not None):
        validate_quotes(data, resume_text, jd_text, errors)

    if errors:
        for line in errors:
            print(line, file=sys.stderr)
        sys.exit(2)

    result = calculate(data)
    if resume_text is None and jd_text is None:
        result["warnings"].append("quote_check: skipped")
    elif resume_text is None or jd_text is None:
        result["warnings"].append("quote_check: partial")

    print(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2))
    sys.exit(0)


if __name__ == "__main__":
    main()
